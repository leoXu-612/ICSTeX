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
from app.core.history import create_snapshot, list_snapshots
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
        if tab.path is None:
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
        if tab.manager.root_file not in self.window.compile_authorized_roots:
            return
        purpose = (
            BuildPurpose.PREVIEW
            if self.window.preferences.fast_preview
            else BuildPurpose.FINAL
        )
        logger.info("已安排%s：编辑器空闲", "快速预览" if purpose is BuildPurpose.PREVIEW else "最终编译")
        tab.manager.compile_async(purpose)

    def flush_root_documents(self, root: Path) -> bool:
        """Persist every open document that belongs to ``root`` before export."""
        target = root.expanduser().resolve()
        for tab in tuple(self.window.tabs.values()):
            if tab.path is None or self.window._compile_root_for_tab(tab) != target:
                continue
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
        window.refresh_project_panels()
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
            window.history_panel.set_snapshots(list_snapshots(path))

    # --- external change reload --------------------------------------------

    def reload_external_change(self, file_name: str) -> None:
        window = self.window
        path = Path(file_name).resolve()
        if window.compile.handle_external_asset_change(path):
            return
        tab = window._tab_for_path(path)
        if not tab:
            return
        try:
            decoded = decode_latex_bytes(path.read_bytes(), encoding=tab.encoding)
            disk_text = decoded.text
        except OSError as exc:
            window.statusBar().showMessage(f"外部修改读取失败：{exc}", 5000)
            window._watch_file(path)
            return
        except LatexTextDecodeError:
            window.statusBar().showMessage(
                f"外部修改的编码与 {tab.encoding} 不一致；已保留当前编辑内容。",
                6000,
            )
            window._watch_file(path)
            return
        if disk_text == tab.editor.toPlainText():
            window._watch_file(path)
            return
        if disk_text == window.local_save_contents.get(path):
            # The watcher woke up on our own save; the editor has moved on
            # since (more typing), so this is an echo, not an external edit.
            window._watch_file(path)
            return
        if tab.modified:
            window.statusBar().showMessage(
                f"检测到外部修改：{path.name}；已保留当前本地编辑。", 6000
            )
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
        if tab is window.current_tab():
            window._update_pdf_action_state()
        if tab.manager is not None and tab.manager.root_file in window.compile_authorized_roots:
            purpose = (
                BuildPurpose.PREVIEW
                if window.preferences.fast_preview
                else BuildPurpose.FINAL
            )
            tab.manager.schedule_compile("外部修改", purpose)
        else:
            purpose = (
                BuildPurpose.PREVIEW
                if window.preferences.fast_preview
                else BuildPurpose.FINAL
            )
            window.compile_current(purpose=purpose, user_initiated=False)
