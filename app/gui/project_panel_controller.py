"""Project-wide panel orchestration: diagnostics, search, outline jumps,
references/labels/images/history refresh.

Pulled out of MainWindow so each sidebar panel's refresh logic can be reasoned
about together. The controller refreshes panels from whatever editor tab is
currently active and routes "jump" events back into the editor.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImageReader

from app.core.diagnostics import Diagnostic, analyze_project
from app.core.history import list_snapshots
from app.core.asset_index import AssetIndex
from app.core.file_observation import file_signature
from app.core.import_metrics import import_metrics
from app.core.latex_outline import scan_outline
from app.core.log_parser import LaTeXError
from app.core.project_search import search_project
from app.core.project_tools import (
    LabelInfo,
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


def _read_image_size(path: Path) -> tuple[int | None, int | None]:
    """Read image dimensions from the header without a full decode."""

    reader = QImageReader(str(path))
    size = reader.size()
    if size.isValid():
        return size.width(), size.height()
    return None, None


class ProjectPanelController:
    _ALL = frozenset({"outline", "assets", "image_usage", "history", "labels", "references", "completion"})
    _TEXT = frozenset({"outline", "image_usage", "labels", "references", "completion"})
    _PANEL_DOMAINS = {
        1: {"outline"}, 3: {"assets", "image_usage"}, 4: {"history"},
        7: {"references"}, 8: {"labels"},
    }

    def __init__(self, window: "MainWindow") -> None:
        self.window = window
        self._asset_indexes: dict[Path, AssetIndex] = {}
        self._dirty = set(self._ALL)
        self._source_key: tuple[object, ...] | None = None
        self._source_text = ""
        self._labels: list[LabelInfo] = []
        self._bib_key: tuple[object, ...] | None = None
        self._bib_text = ""
        self._bib_keys: list[str] = []
        self._timer = QTimer(window)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self.refresh_visible)
        self._reconcile_timer = QTimer(window)
        self._reconcile_timer.setInterval(30_000)
        self._reconcile_timer.timeout.connect(self.reconcile)
        self._reconcile_timer.start()

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
            window.statusBar().showMessage(f"当前源码静态检查：{len(diagnostics)} 项提示；不代表完整提交检查。", 4000)
        else:
            window.statusBar().showMessage("当前源码静态检查未发现提示；完整提交状态请查看提交检查。", 4000)
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
        scope = window.selected_project_scope or tab.path.parent
        results = search_project(
            scope,
            query,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
        )
        window.search_panel.set_results(scope, results)
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
        """Explicit refresh remains comprehensive, including hidden panels."""
        self._timer.stop()
        self._source_key = None
        self._bib_key = None
        self._dirty.update(self._ALL)
        self._refresh_domains(set(self._ALL))

    def context_changed(self) -> None:
        self._dirty.update(self._ALL)
        self._source_key = None
        self._bib_key = None
        self.refresh_visible()

    def source_changed(self, tab: object) -> None:
        if tab is self.window.current_tab():
            self.invalidate(self._TEXT)

    def invalidate(self, domains: frozenset[str] | set[str]) -> None:
        self._dirty.update(domains)
        self._timer.start()

    def external_changed(self, path: Path) -> None:
        tab = self.window.current_tab()
        if tab is None or tab.path is None:
            return
        if path.suffix.lower() in {".bib", ".tex", ".sty", ".cls", ".ltx"}:
            self._bib_key = None
            self.invalidate(self._TEXT)
        else:
            self.invalidate({"assets", "image_usage"})

    def reconcile(self) -> None:
        """Low-frequency recovery for missed events; hidden panels stay dirty."""
        self._dirty.update(self._ALL)
        self._source_key = None
        self._bib_key = None
        if self.window.isVisible():
            self.refresh_visible()

    def refresh_visible(self, *_args: object) -> None:
        domains = {"completion"}
        if self.window.toolbox_dock.isVisible():
            domains.update(self._PANEL_DOMAINS.get(self.window.sidebar_tabs.currentIndex(), set()))
        self._refresh_domains(domains & self._dirty)

    def shutdown(self) -> None:
        self._timer.stop()
        self._reconcile_timer.stop()

    def _refresh_domains(self, domains: set[str]) -> None:
        if not domains:
            return
        window = self.window
        tab = window.current_tab()
        if not tab:
            if "outline" in domains:
                window.outline_panel.set_outline([])
            if domains & {"assets", "image_usage"}:
                window.images_panel.set_assets([])
            if "history" in domains:
                window.history_panel.set_snapshots([])
            if "references" in domains:
                window.references_panel.set_references([])
            if "labels" in domains:
                window.labels_panel.set_labels([], set(), set())
            self._dirty.difference_update(domains)
            return

        key = (id(tab.editor), tab.editor.document().revision(), tab.path)
        if key != self._source_key:
            self._source_key = key
            self._source_text = tab.editor.toPlainText()
            self._labels = scan_labels(self._source_text)
        tex_text = self._source_text
        if "outline" in domains:
            window.outline_panel.set_outline(scan_outline(tex_text))
        if tab.path and domains & {"assets", "image_usage"}:
            scope = window.selected_project_scope or tab.path.parent
            index = self._asset_indexes.get(scope)
            if index is None:
                index = AssetIndex(scope)
                index.load()
                if len(self._asset_indexes) >= 8:
                    self._asset_indexes.pop(next(iter(self._asset_indexes)))
                self._asset_indexes[scope] = index
                domains.add("assets")
            if "assets" in domains:
                import_metrics.record_index_scan(full=not index.was_cached)
                index.scan(read_metadata=_read_image_size)
                index.save()
            window.images_panel.set_assets(index.image_assets(current_text=tex_text))
        elif domains & {"assets", "image_usage"}:
            window.images_panel.set_assets([])
        if tab.path and "history" in domains:
            window.history_panel.set_snapshots(list_snapshots(tab.path))
        elif "history" in domains:
            window.history_panel.set_snapshots([])
        if "labels" in domains:
            window.labels_panel.set_labels(self._labels, duplicate_labels(tex_text), undefined_references(tex_text))

        if domains & {"references", "completion"}:
            bib_path = bib_helpers.bib_file_for_tab(tab)
            bib_key = (bib_path, file_signature(bib_path) if bib_path else None)
            if bib_key != self._bib_key:
                self._bib_key = bib_key
                self._bib_text = bib_helpers.bib_text_for_tab(tab)
                self._bib_keys = sorted(bib_keys(self._bib_text))
            if "references" in domains:
                window.references_panel.set_references(
                    self._bib_keys, undefined_citations(tex_text, self._bib_text),
                )
            if "completion" in domains:
                tab.editor.set_completion_context(
                    labels=[label.name for label in self._labels], citations=self._bib_keys,
                )
        self._dirty.difference_update(domains)
