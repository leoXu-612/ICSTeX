"""Document save/load/watch/snapshot logic, extracted from MainWindow.

The controller holds a reference to the host window so it can reach the parts of
state that still live there (``tabs``, ``editor_tabs``, ``signals``, the
status bar, etc.). This is a deliberate transitional split: pulling the methods
out shrinks ``main_window.py`` without changing how the Qt signal graph is
wired, so existing tests and callers do not need to change.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from app.core.compiler import BuildPurpose
from app.core.build_events import automatic_build_purpose
from app.core.history import create_snapshot
from app.core.project_dependencies import safe_project_input
from app.core.text_encoding import LatexTextDecodeError, decode_latex_bytes, write_latex_text_atomic
from app.gui import editor_view_state
from app.gui.latex_editor import LaTeXEditor
from app.gui.main_window_support import EditorTab
from app.gui.theme import editor_font

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.gui.main_window import MainWindow


logger = logging.getLogger(__name__)


class DocumentLifecycle:
    """Owns editor factory, debounced save timer, history snapshots, and external
    change reloading. All public methods either mutate ``EditorTab`` state or
    schedule work on the host window."""

    def __init__(self, window: "MainWindow") -> None:
        self.window = window

    # --- editor factory -----------------------------------------------------

    def make_editor(self, text: str) -> LaTeXEditor:
        window = self.window
        editor = LaTeXEditor()
        editor.setPlainText(text)
        self.apply_editor_font(editor)
        editor.document().setDocumentMargin(18)
        window.apply_editor_options(editor)
        editor.textChanged.connect(window._on_editor_changed)
        editor.imageDropped.connect(window.insert_dropped_images)
        editor.texFilesDropped.connect(window.open_dropped_tex_files)
        return editor

    def apply_editor_font(self, editor: LaTeXEditor) -> None:
        editor.setFont(editor_font(self.window.preferences.editor_font_size))
        editor.setTabStopDistance(editor.fontMetrics().horizontalAdvance(" ") * 4)

    # --- save coordination --------------------------------------------------

    def schedule_save(self, tab: EditorTab, *, compile_after_save: bool = False) -> None:
        if not tab.path:
            return
        window = self.window
        if tab.external_conflict:
            self.cancel_save_timer(tab)
            tab.pending_compile_after_save = False
            window.statusBar().showMessage("存在外部文件冲突；自动保存已暂停，请保存确认或另存为。", 6000)
            return
        tab.pending_compile_after_save = tab.pending_compile_after_save or compile_after_save
        if tab.save_timer is None:
            tab.save_timer = QTimer(window)
            tab.save_timer.setSingleShot(True)
            tab.save_timer.timeout.connect(lambda tab=tab: window.flush_pending_save(tab))
        tab.save_timer.start(window.save_debounce_ms)
        if compile_after_save:
            window.statusBar().showMessage("等待输入暂停后自动编译...", 1500)
        else:
            window.statusBar().showMessage("等待保存...", 1500)

    def flush_pending_save(
        self,
        tab: EditorTab,
        *,
        compile_after_save: bool | None = None,
    ) -> bool:
        if tab.path is None or tab.external_conflict:
            return False
        should_compile = tab.pending_compile_after_save if compile_after_save is None else compile_after_save
        tab.pending_compile_after_save = False
        if not tab.dirty and not tab.modified:
            self.cancel_save_timer(tab)
            if should_compile and tab.manager:
                self.compile_after_idle(tab)
            return True
        if not self.save_tab(tab, tab.path):
            return False
        if should_compile and tab.manager:
            self.compile_after_idle(tab)
        return True

    def cancel_save_timer(self, tab: EditorTab) -> None:
        if tab.save_timer is not None and tab.save_timer.isActive():
            tab.save_timer.stop()

    def compile_after_idle(self, tab: EditorTab) -> None:
        if tab.manager is None:
            return
        purpose = automatic_build_purpose(
            enabled=self.window.auto_compile_action.isChecked(),
            authorized=tab.manager.root_file in self.window.compile_authorized_roots,
            fast_preview=self.window.preferences.fast_preview,
        )
        if purpose is None:
            return
        if not self.flush_root_documents(tab.manager.root_file):
            return
        logger.info("已安排%s：编辑器空闲", "快速预览" if purpose is BuildPurpose.PREVIEW else "最终编译")
        tab.manager.compile_async(purpose)

    def flush_root_documents(self, root: Path) -> bool:
        """Persist every open document that belongs to ``root`` before export."""
        target = root.expanduser().resolve()
        dependencies = self.window.dependencies.paths_for(target)
        for tab in tuple(self.window.tabs.values()):
            if tab.path is None or (
                self.window._compile_root_for_tab(tab) != target and tab.path.resolve() not in dependencies
            ):
                continue
            if tab.external_conflict:
                return False
            if not (tab.dirty or tab.modified or (tab.save_timer and tab.save_timer.isActive())):
                continue
            if not self.flush_pending_save(tab, compile_after_save=False):
                return False
        return True

    def save_tab(self, tab: EditorTab, path: Path) -> bool:
        window = self.window
        old_path = tab.path
        old_manager = tab.manager
        self.cancel_save_timer(tab)
        if tab.external_conflict and old_path == path:
            window.statusBar().showMessage("外部文件冲突尚未确认；未覆盖磁盘文件。", 5000)
            return False
        try:
            text = tab.editor.toPlainText()
            path.parent.mkdir(parents=True, exist_ok=True)
            write_latex_text_atomic(path, text, encoding=tab.encoding)
        except UnicodeEncodeError:
            QMessageBox.warning(
                window,
                "保存失败",
                (
                    f"当前文件编码 {tab.encoding} 无法表示新输入的某些字符。\n"
                    "原文件未被覆盖；请撤销这些字符，或先将文件转换为 UTF-8。"
                ),
            )
            return False
        except (OSError, UnicodeError) as exc:
            QMessageBox.warning(window, "保存失败", str(exc))
            return False
        window.local_save_contents[path] = text
        tab.path = path
        tab.dirty = False
        tab.modified = False
        tab.external_conflict = False
        window._invalidate_include_cache()
        if tab.manager is None or old_path != path:
            tab.manager = window.create_compile_manager(path)
        if old_manager is not None and old_manager is not tab.manager:
            shared = any(
                other is not tab and other.manager is old_manager
                for other in window.tabs.values()
            )
            if not shared:
                window.compile.retire_manager(old_manager)
                window.compile.release_preview_assets(old_manager.root_file)
                if hasattr(window, "pdf_export"):
                    window.pdf_export.cancel_root(old_manager.root_file)
        if old_path and old_path != path:
            window.file_watcher.unwatch(old_path)
        if old_path != path and tab is window.current_tab():
            # Save-As changed the compile root: bind the new root's record and
            # never leave the old root's PDF visible/exportable.
            window._sync_pdf_panel_to_active_root()
            window._sync_compile_indicators_to_active_root()
        window._set_tab_title(tab)
        window._watch_file(path)
        window._remember_recent_file(path)
        self.create_history_snapshot(path, text, "保存")
        window.dependencies.refresh_memberships()
        if old_path != path:
            window.project_panels.context_changed()
        return True

    # --- history snapshot ---------------------------------------------------

    def create_history_snapshot(self, path: Path, text: str, label: str) -> None:
        window = self.window
        try:
            snapshot = create_snapshot(path, text, label)
        except OSError as exc:
            logger.warning("历史快照保存失败：%s", exc)
            return
        current = window.current_tab()
        if snapshot is not None and current is not None and current.path == path:
            window.project_panels.invalidate({"history"})

    # --- external change reload --------------------------------------------

    def reload_external_change(self, file_name: str) -> None:
        window = self.window
        raw = Path(file_name).expanduser().absolute()
        path = raw if window.dependencies.roots_for(raw) else raw.parent.resolve() / raw.name
        scope = window.selected_project_scope or path.parent
        if safe_project_input(scope, path) is None:
            window.dependencies.handle_external_change(path)
            return
        tab = window._tab_for_path(path)
        if not tab:
            window.dependencies.handle_external_change(path)
            return
        try:
            data = path.read_bytes()
            decoded = decode_latex_bytes(data, encoding=tab.encoding)
            disk_text = decoded.text
        except OSError as exc:
            window.statusBar().showMessage(f"外部修改读取失败：{exc}", 5000)
            self._external_conflict(tab, path)
            window._watch_file(path)
            return
        except LatexTextDecodeError:
            window.statusBar().showMessage(
                f"外部修改的编码与 {tab.encoding} 不一致；已保留当前编辑内容。",
                6000,
            )
            self._external_conflict(tab, path)
            window._watch_file(path)
            return
        if disk_text == tab.editor.toPlainText():
            tab.external_conflict = False
            window.dependencies.remember_disk(path, data)
            window._watch_file(path)
            return
        if disk_text == window.local_save_contents.get(path):
            # The watcher woke up on our own save; the editor has moved on
            # since (more typing), so this is an echo, not an external edit.
            window.dependencies.remember_disk(path, data)
            window._watch_file(path)
            return
        if tab.modified:
            window.statusBar().showMessage(
                f"检测到外部修改：{path.name}；已保留当前本地编辑。", 6000
            )
            changed = window.dependencies.remember_disk(path, data)
            if changed or not tab.external_conflict:
                self._external_conflict(tab, path)
            window._watch_file(path)
            return
        captured_state = editor_view_state.capture(tab.editor)
        try:
            self.cancel_save_timer(tab)
            tab.dirty = False
            tab.pending_compile_after_save = False
            tab.editor.blockSignals(True)
            tab.editor.setPlainText(disk_text)
            editor_view_state.restore(tab.editor, captured_state)
        finally:
            tab.editor.blockSignals(False)
            window._watch_file(path)
        # setPlainText above ran with signals blocked, so mark the root's PDF
        # stale explicitly: the displayed PDF no longer matches the new source.
        window._invalidate_include_cache()
        window._mark_source_edited(tab)
        tab.external_conflict = False
        window.dependencies.remember_disk(path, data)
        window.dependencies.refresh_memberships()
        window.word_counts.schedule()
        window.project_panels.source_changed(tab)
        if tab is window.current_tab():
            window._update_pdf_action_state()
        root = window._compile_root_for_tab(tab)
        for affected in window.dependencies.roots_for(path) - {root}:
            window.dependencies.schedule_root(affected)
        purpose = automatic_build_purpose(
            enabled=window.auto_compile_action.isChecked(),
            authorized=root in window.compile_authorized_roots,
            fast_preview=window.preferences.fast_preview,
        )
        if purpose is None:
            return
        if root is not None and not self.flush_root_documents(root):
            return
        if tab.manager is not None:
            tab.manager.schedule_compile("外部修改", purpose)
        else:
            window.compile_current(purpose=purpose, user_initiated=False)

    def _external_conflict(self, tab: EditorTab, path: Path) -> None:
        window = self.window
        self.cancel_save_timer(tab)
        tab.pending_compile_after_save = False
        tab.external_conflict = True
        roots = set(window.dependencies.roots_for(path))
        root = window._compile_root_for_tab(tab)
        if root is not None:
            roots.add(root)
        window.dependencies.invalidate_roots(roots)
        window.word_counts.schedule()
