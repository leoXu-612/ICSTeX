"""Tab routing helpers extracted from MainWindow.

Owns the ``{id(editor): EditorTab}`` mapping bookkeeping and the per-tab title
update logic. Close/closeEvent flow still asks the host window for save
prompting because it reaches into ``save_current_as`` / ``flush_pending_save``
that remain MainWindow methods.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox

from app.gui.main_window_support import EditorTab

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.gui.main_window import MainWindow


class EditorTabManager:
    def __init__(self, window: "MainWindow") -> None:
        self.window = window

    # --- lookup -------------------------------------------------------------

    def current(self) -> EditorTab | None:
        window = self.window
        widget = window.editor_tabs.currentWidget()
        return window.tabs.get(id(widget)) if widget else None

    def ensure_editable(self) -> EditorTab | None:
        window = self.window
        tab = self.current()
        if tab is None:
            window.new_document()
            tab = self.current()
        return tab

    def require_saved_for_assets(self) -> EditorTab | None:
        window = self.window
        tab = self.ensure_editable()
        if tab is None:
            return None
        if tab.path is None and not window.save_current_as():
            return None
        return tab

    def for_path(self, path: Path) -> EditorTab | None:
        resolved = path.expanduser().resolve()
        for tab in self.window.tabs.values():
            if tab.path and tab.path.expanduser().resolve() == resolved:
                return tab
        return None

    def index_for_tab_id(self, tab_id: int) -> int:
        editor_tabs = self.window.editor_tabs
        for index in range(editor_tabs.count()):
            if id(editor_tabs.widget(index)) == tab_id:
                return index
        return -1

    # --- mutation -----------------------------------------------------------

    def add(self, tab: EditorTab, title: str) -> None:
        window = self.window
        # The first addTab emits currentChanged immediately.
        window.tabs[id(tab.editor)] = tab
        index = window.editor_tabs.addTab(tab.editor, title)
        window.editor_tabs.setTabToolTip(index, self._tab_tooltip(tab))
        window.editor_tabs.setCurrentIndex(index)
        window.update_document_view_state()
        window.dependencies.refresh_memberships()

    def set_title(self, tab: EditorTab) -> None:
        window = self.window
        index = self.index_for_tab_id(id(tab.editor))
        if index < 0:
            return
        base = tab.path.name if tab.path else window.editor_tabs.tabText(index).rstrip("*") or "未命名.tex"
        window.editor_tabs.setTabText(index, f"{base}{'*' if tab.modified else ''}")
        window.editor_tabs.setTabToolTip(index, self._tab_tooltip(tab))

    @staticmethod
    def _tab_tooltip(tab: EditorTab) -> str:
        location = str(tab.path) if tab.path else "未保存文档"
        return f"{location}\n编码：{tab.encoding}"

    def watch_path(self, path: Path) -> None:
        self.window.file_watcher.watch(path)

    # --- close / shutdown ---------------------------------------------------

    def _ask_unsaved_choice(self, tab: EditorTab) -> QMessageBox.StandardButton:
        label = tab.path.name if tab.path else "未命名.tex"
        buttons = (
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        return QMessageBox.warning(
            self.window,
            "存在未保存修改",
            f"“{label}”有尚未保存的修改。关闭前是否保存？",
            buttons,
            QMessageBox.StandardButton.Save,
        )

    def close_at(self, index: int) -> None:
        window = self.window
        widget = window.editor_tabs.widget(index)
        tab_id = id(widget)
        tab = window.tabs.get(tab_id)
        if tab and tab.modified:
            window.editor_tabs.setCurrentIndex(index)
            choice = self._ask_unsaved_choice(tab)
            if choice == QMessageBox.StandardButton.Cancel:
                return
            if choice == QMessageBox.StandardButton.Save:
                if tab.path is None:
                    if not window.save_current_as():
                        return
                elif not window.flush_pending_save(tab, compile_after_save=False):
                    return
        if tab:
            window.documents.cancel_save_timer(tab)
            if tab.manager:
                shared = any(
                    other is not tab and other.manager is tab.manager
                    for other in window.tabs.values()
                )
                if not shared:
                    window.compile.retire_manager(tab.manager)
                    window.compile.release_preview_assets(tab.manager.root_file)
                    if hasattr(window, "pdf_export"):
                        window.pdf_export.cancel_root(tab.manager.root_file)
        if tab and tab.path:
            window.file_watcher.unwatch(tab.path)
        window.editor_tabs.removeTab(index)
        window.tabs.pop(tab_id, None)
        window.update_document_view_state()
        window.dependencies.refresh_memberships()

    def handle_close_event(self, event: QCloseEvent) -> None:
        window = self.window
        open_tabs: list[EditorTab] = []
        for index in range(window.editor_tabs.count()):
            widget = window.editor_tabs.widget(index)
            tab = window.tabs.get(id(widget))
            if tab is None:
                continue
            open_tabs.append(tab)
            if tab.modified:
                window.editor_tabs.setCurrentIndex(index)
                choice = self._ask_unsaved_choice(tab)
                if choice == QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return
                if choice == QMessageBox.StandardButton.Save:
                    if tab.path is None:
                        if not window.save_current_as():
                            event.ignore()
                            return
                    elif not window.flush_pending_save(tab, compile_after_save=False):
                        event.ignore()
                        return
            elif tab.path and tab.dirty:
                if not window.flush_pending_save(tab, compile_after_save=False):
                    event.ignore()
                    return

        # Shutdown side effects are deferred until every document has agreed
        # to close. A later Cancel must leave earlier tabs fully operational.
        retired: set[object] = set()
        for tab in open_tabs:
            window.documents.cancel_save_timer(tab)
            if tab.manager and tab.manager not in retired:
                retired.add(tab.manager)
                window.compile.retire_manager(tab.manager)
        window.word_counts.shutdown()
        window.project_panels.shutdown()
        window.dependencies.shutdown()
        window.file_watcher.stop()
        if hasattr(window, "_log_bridge"):
            window._log_bridge.uninstall()
        event.accept()
