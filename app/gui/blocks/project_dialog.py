"""Block MVP host dialog (GUI milestones host)."""
from __future__ import annotations

from pathlib import Path

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
from app.core.blocks.registry import BlockRegistry
from app.core.blocks.source_merge import MergeResult
from app.core.blocks.table_model import TableData, TableEditorModel
from app.core.blocks.theme import AppTheme
from app.gui.blocks.layout_panel import BlockLayoutPanel
from app.gui.blocks.merge_dialog import MergeDialog
from app.gui.blocks.table_editor import TableEditor
from app.gui.blocks.theme_settings import ThemeSettings


class BlockProjectDialog(QDialog):
    def __init__(
        self,
        registry: BlockRegistry,
        *,
        layout=None,
        table_model: TableEditorModel | None = None,
        merge_result: MergeResult | None = None,
        theme: AppTheme | None = None,
        project_dir: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Block 项目（MVP）")
        self.resize(900, 640)
        self.registry = registry
        self.project_dir = project_dir
        self.merge_result = merge_result

        tabs = QTabWidget(self)
        tabs.addTab(BlockLayoutPanel(registry, layout), "布局")
        tabs.addTab(TableEditor(table_model or TableEditorModel(TableData())), "表格")
        tabs.addTab(self._build_sync_tab(), "同步")
        tabs.addTab(ThemeSettings(theme), "主题")
        tabs.addTab(self._build_export_tab(), "导出")

        layout_box = QVBoxLayout(self)
        layout_box.addWidget(tabs)

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
                label.setText(f"已解决；剩余冲突 0 处")

        resolve.clicked.connect(open_resolver)
        box.addWidget(resolve)
        box.addStretch()
        return widget

    def _build_export_tab(self) -> QWidget:
        widget = QWidget()
        box = QVBoxLayout(widget)
        box.addWidget(QLabel(f"项目目录：{self.project_dir or '（未指定）'}"))
        button = QPushButton("导出可移植包…")

        def do_export() -> None:
            if self.project_dir is None:
                return
            target = QFileDialog.getExistingDirectory(self, "选择导出目标目录")
            if not target:
                return
            result = export_package(self.project_dir, Path(target) / (self.project_dir.name + "-export"))
            QMessageBox.information(self, "导出完成", f"已导出 {len(result.files)} 个文件。")

        button.clicked.connect(do_export)
        box.addWidget(button)
        box.addStretch()
        return widget
