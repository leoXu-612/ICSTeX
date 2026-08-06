"""Project-wide panel orchestration: diagnostics, search, outline jumps,
references/labels/images/history refresh.

Pulled out of MainWindow so each sidebar panel's refresh logic can be reasoned
about together. The controller refreshes panels from whatever editor tab is
currently active and routes "jump" events back into the editor.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt

from app.core.diagnostics import Diagnostic, analyze_project
from app.core.history import list_snapshots
from app.core.image_assets import scan_image_assets
from app.core.latex_outline import scan_outline
from app.core.log_parser import LaTeXError
from app.core.project_search import search_project
from app.core.project_tools import (
    bib_keys,
    duplicate_labels,
    scan_labels,
    undefined_citations,
    undefined_references,
)
from app.gui import bib_helpers
from app.gui import editor_view_state

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.gui.main_window import MainWindow


class ProjectPanelController:
    def __init__(self, window: "MainWindow") -> None:
        self.window = window

    # --- diagnostics --------------------------------------------------------

    def run_project_check(
        self,
        log_errors: list[LaTeXError] | None = None,
        *,
        switch_to_panel: bool = True,
    ) -> list[Diagnostic]:
        window = self.window
        tab = window.current_tab()
        if tab is None:
            diagnostics = analyze_project(
                "", root_file=None, bib_text="", toolchain=window.toolchain, log_errors=log_errors,
            )
        else:
            diagnostics = analyze_project(
                tab.editor.toPlainText(),
                root_file=tab.path,
                bib_text=bib_helpers.bib_text_for_tab(tab),
                toolchain=window.toolchain,
                log_errors=log_errors,
            )
        window.diagnostic_panel.set_diagnostics(diagnostics)
        index = window.bottom_tabs.indexOf(window.diagnostic_panel)
        if index >= 0:
            window.bottom_tabs.setTabText(index, f"检查 {len(diagnostics)}" if diagnostics else "检查")
        if switch_to_panel:
            window.bottom_tabs.setCurrentWidget(window.diagnostic_panel)
        if diagnostics:
            window.statusBar().showMessage(f"检查完成：发现 {len(diagnostics)} 个项目提示。", 4000)
        else:
            window.statusBar().showMessage("检查完成：未发现明显问题。", 4000)
        return diagnostics

    def fix_diagnostic(self, index: int) -> None:
        window = self.window
        if index < 0 or index >= len(window.diagnostic_panel.diagnostics):
            return
        diagnostic = window.diagnostic_panel.diagnostics[index]
        if diagnostic.fix is None or not diagnostic.fix.packages:
            window.statusBar().showMessage("这个问题暂时没有可自动修复的操作。", 4000)
            return
        tab = window.current_tab()
        if tab is None:
            window.statusBar().showMessage("请先打开或新建一个 .tex 文档。", 4000)
            return
        before = tab.editor.toPlainText()
        window.insertions.ensure_packages(tab, diagnostic.fix.packages)
        after = tab.editor.toPlainText()
        if before == after:
            window.statusBar().showMessage("对应 package 已经存在，无需重复修复。", 4000)
        else:
            window.statusBar().showMessage(f"已修复：{diagnostic.fix.title}", 4000)
        self.run_project_check(switch_to_panel=False)

    def jump_to_diagnostic(self, index: int) -> None:
        window = self.window
        if index < 0 or index >= len(window.diagnostic_panel.diagnostics):
            return
        diagnostic = window.diagnostic_panel.diagnostics[index]
        if diagnostic.file is not None and diagnostic.file.exists():
            window.open_file(diagnostic.file, diagnostic.line)
            return
        tab = window.current_tab()
        if tab is not None and diagnostic.line:
            editor_view_state.jump_to_line(tab.editor, diagnostic.line)

    # --- outline / search --------------------------------------------------

    def jump_to_outline(self, line: int) -> None:
        window = self.window
        tab = window.current_tab()
        if tab is None:
            return
        editor_view_state.jump_to_line(tab.editor, line)
        window.statusBar().showMessage(f"已跳转到大纲第 {line} 行。", 2500)

    def run_project_search(self, query: str, case_sensitive: bool, whole_word: bool) -> None:
        window = self.window
        tab = window.current_tab()
        if tab is None or tab.path is None:
            window.search_panel.status_label.setText("请先打开或保存一个项目文件")
            return
        results = search_project(
            tab.path.parent,
            query,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
        )
        window.search_panel.set_results(tab.path.parent, results)
        window.statusBar().showMessage(f"项目搜索完成：{len(results)} 个结果。", 3000)

    def jump_to_project_search_result(self, path: str, line: int, column: int) -> None:
        window = self.window
        window.open_file(Path(path), line)
        tab = window.current_tab()
        if tab is not None:
            editor_view_state.jump_to_position(tab.editor, line, column)

    # --- error table -------------------------------------------------------

    def jump_to_error(self, row: int) -> None:
        window = self.window
        file_item = window.error_table.item(row, 0)
        line_item = window.error_table.item(row, 1)
        if not file_item:
            return
        file_path = Path(file_item.data(Qt.ItemDataRole.UserRole) or file_item.text())
        try:
            line = int(line_item.text()) if line_item and line_item.text() else 1
        except ValueError:
            line = 1
        if file_path.exists():
            window.open_file(file_path, line)

    # --- panel refresh -----------------------------------------------------

    def refresh(self) -> None:
        window = self.window
        tab = window.current_tab()
        if not tab:
            window.outline_panel.set_outline([])
            window.images_panel.set_assets([])
            window.history_panel.set_snapshots([])
            window.references_panel.set_references([])
            window.labels_panel.set_labels([], set(), set())
            return

        tex_text = tab.editor.toPlainText()
        window.outline_panel.set_outline(scan_outline(tex_text))
        if tab.path:
            window.images_panel.set_assets(scan_image_assets(tab.path.parent, current_text=tex_text))
            window.history_panel.set_snapshots(list_snapshots(tab.path))
        else:
            window.images_panel.set_assets([])
            window.history_panel.set_snapshots([])
        labels = scan_labels(tex_text)
        window.labels_panel.set_labels(labels, duplicate_labels(tex_text), undefined_references(tex_text))

        bib_text = bib_helpers.bib_text_for_tab(tab)
        keys = sorted(bib_keys(bib_text))
        window.references_panel.set_references(keys, undefined_citations(tex_text, bib_text))
        tab.editor.set_completion_context(labels=[label.name for label in labels], citations=keys)
