"""Reusable Block workspace body extracted from ``BlockProjectDialog``.

The widget only renders and interacts; it receives one ``ProjectSession``,
emits selection/edit signals, and routes model changes through the session
(which owns save + the single CompileManager).  It never loads a project,
never writes JSON directly and never starts a compiler by itself.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.export_package import export_package
from app.core.blocks.source_merge import MergeResult
from app.gui.blocks.formula_tab import FormulaBlockTab
from app.gui.blocks.layout_panel import BlockLayoutPanel
from app.gui.blocks.merge_dialog import MergeDialog
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.table_editor import TableEditor
from app.gui.blocks.theme_settings import ThemeSettings
from app.gui.responsive.helpers import configure_tab_bar


class BlockWorkspaceWidget(QWidget):
    block_selected = Signal(str)
    layout_selected = Signal(str)
    source_selected = Signal(str)
    edit_requested = Signal(str)
    preview_requested = Signal()

    def __init__(self, session: ProjectSession, *, merge_result: MergeResult | None = None, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.merge_result = merge_result
        self._selection_syncing = False

        self.layout_panel = BlockLayoutPanel(session.registry, session.layout)
        self.layout_panel.layoutChanged.connect(self._on_layout_changed)
        self.layout_panel.block_list.itemSelectionChanged.connect(self._on_block_selection_changed)
        self.layout_panel.slot_list.itemSelectionChanged.connect(self._on_slot_selection_changed)
        self.layout_panel.block_list.itemDoubleClicked.connect(lambda _item: self._emit_edit_requested())

        self.table_editor = TableEditor(session.table_model)
        self.table_editor.model_changed.connect(self._on_table_changed)
        self.formula_tab = FormulaBlockTab(session.registry, session=session)
        self.theme_settings = ThemeSettings(session.app_theme)

        tabs = QTabWidget(self)
        tabs.addTab(self.layout_panel, "布局")
        tabs.addTab(self.table_editor, "表格")
        tabs.addTab(self.formula_tab, "公式")
        tabs.addTab(self._build_sync_tab(), "同步")
        tabs.addTab(self.theme_settings, "主题")
        tabs.addTab(self._build_export_tab(), "导出")
        configure_tab_bar(tabs)
        self.tabs = tabs

        self.preview_label = QLabel("尚未生成 PDF")
        self.preview_button = QPushButton("生成并编译 PDF")
        self.preview_button.clicked.connect(self.preview_requested)
        preview_row = QHBoxLayout()
        preview_row.addWidget(self.preview_button)
        preview_row.addWidget(self.preview_label, stretch=1)

        layout = QVBoxLayout(self)
        layout.addLayout(preview_row)
        layout.addWidget(tabs)

        session.compile_finished.connect(self._on_compile_finished)
        session.model_changed.connect(lambda _reason: self.layout_panel.refresh_block_list())
        session.selection.selection_changed.connect(self._on_session_selection)

    # --- signal sources --------------------------------------------------
    def _on_layout_changed(self) -> None:
        self.session.set_layout(self.layout_panel.layout, reason="layout_changed")

    def _on_block_selection_changed(self) -> None:
        selected = self.layout_panel.selected_block_ids()
        if selected:
            self.block_selected.emit(selected[0])

    def _on_slot_selection_changed(self) -> None:
        items = self.layout_panel.slot_list.selectedItems()
        if items:
            instance_id = items[0].text().split(" -> ")[0]
            self.layout_selected.emit(instance_id)

    def _emit_edit_requested(self) -> None:
        selected = self.layout_panel.selected_block_ids()
        if selected:
            self.edit_requested.emit(selected[0])

    def _on_table_changed(self) -> None:
        self.session.table_edited()
        self.session.notify_model_changed("table_updated")

    def _on_session_selection(self, context, source: str) -> None:
        if source == "workspace" or self._selection_syncing:
            return
        if context.block_id is None:
            return
        self._selection_syncing = True
        try:
            for index in range(self.layout_panel.block_list.count()):
                item = self.layout_panel.block_list.item(index)
                item.setSelected(item.data(256) == context.block_id)
        finally:
            self._selection_syncing = False

    def _on_compile_finished(self, result: object) -> None:
        pdf = getattr(result, "pdf_file", None)
        if pdf is not None and Path(pdf).exists():
            self.preview_label.setText(f"已更新：{Path(pdf).name}")
        elif result is not None and not getattr(result, "ok", False):
            self.preview_label.setText("编译失败：查看日志")

    # --- secondary tabs --------------------------------------------------
    def _build_sync_tab(self) -> QWidget:
        widget = QWidget()
        box = QVBoxLayout(widget)
        count = len(self.merge_result.conflicts) if self.merge_result else 0
        label = QLabel(f"冲突 {count} 处")
        box.addWidget(label)
        resolve = QPushButton("解决冲突…")

        def open_resolver() -> None:
            if self.merge_result is None:
                return
            dialog = MergeDialog(self.merge_result, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                label.setText("已解决；剩余冲突 0 处")

        resolve.clicked.connect(open_resolver)
        box.addWidget(resolve)
        box.addStretch()
        return widget

    def _build_export_tab(self) -> QWidget:
        widget = QWidget()
        box = QVBoxLayout(widget)
        box.addWidget(QLabel(f"项目目录：{self.session.project_dir or '（未指定）'}"))
        button = QPushButton("导出可移植包…")

        def do_export() -> None:
            if self.session.project_dir is None:
                return
            target = QFileDialog.getExistingDirectory(self, "选择导出目标目录")
            if not target:
                return
            result = export_package(self.session.project_dir, Path(target) / (self.session.project_dir.name + "-export"))
            QMessageBox.information(self, "导出完成", f"已导出 {len(result.files)} 个文件。")

        button.clicked.connect(do_export)
        box.addWidget(button)
        box.addStretch()
        return widget
