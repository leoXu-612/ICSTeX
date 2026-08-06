"""Block MVP host dialog (GUI milestones host)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
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

from app.core.blocks.block_renderer import render_block, required_packages_for_block
from app.core.blocks.export_package import export_package
from app.core.blocks.layout_renderer import render_layout
from app.core.blocks.layout_solver import solve_layout
from app.core.blocks.registry import BlockRegistry
from app.core.blocks.source_merge import MergeResult
from app.core.blocks.table_model import TableData, TableEditorModel
from app.core.blocks.theme import AppTheme, DocumentTheme
from app.core.blocks.theme_renderer import render_document_theme_sty
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain
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
        self.theme_settings = ThemeSettings(theme)
        self.layout_panel = BlockLayoutPanel(registry, layout)
        self.table_editor = TableEditor(table_model or TableEditorModel(TableData()))

        tabs = QTabWidget(self)
        tabs.addTab(self.layout_panel, "布局")
        tabs.addTab(self.table_editor, "表格")
        tabs.addTab(self._build_sync_tab(), "同步")
        tabs.addTab(self.theme_settings, "主题")
        tabs.addTab(self._build_export_tab(), "导出")

        self.preview_label = QLabel("尚未生成 PDF")
        self.preview_button = QPushButton("生成并编译 PDF")
        self.preview_button.clicked.connect(self._schedule_preview)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(700)
        self._preview_timer.timeout.connect(self._compile_preview)
        self.layout_panel.layoutChanged.connect(self._schedule_preview)
        self._preview_manager: CompileManager | None = None
        self._preview_pdf: Path | None = None

        preview_row = QHBoxLayout()
        preview_row.addWidget(self.preview_button)
        preview_row.addWidget(self.preview_label, stretch=1)

        layout_box = QVBoxLayout(self)
        layout_box.addLayout(preview_row)
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

    def _schedule_preview(self) -> None:
        if self.project_dir is None:
            return
        self._preview_timer.start()

    def _compile_preview(self) -> None:
        if self.project_dir is None:
            return
        result = self._build_pdf_sync()
        if result is None or not result.ok:
            self.preview_label.setText("编译失败：查看日志")
            return
        if result.pdf_file is not None:
            self._preview_pdf = result.pdf_file
            self.preview_label.setText(f"已更新：{result.pdf_file.name}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.pdf_file)))

    def _build_pdf_sync(self) -> object:
        """Assemble main.tex from dialog state and compile it synchronously."""

        if self.project_dir is None:
            return None
        project = self.project_dir.expanduser().resolve()
        self._sync_table_to_registry()
        blocks_dir = project / "blocks"
        blocks_dir.mkdir(parents=True, exist_ok=True)
        block_latex: dict[str, str] = {}
        for block in self.registry.blocks():
            (blocks_dir / f"{block.id}.tex").write_text(render_block(block, in_box=True), encoding="utf-8")
            block_latex[block.id] = f"\\input{{blocks/{block.id}.tex}}\n"
        layout = self.layout_panel.layout
        body = render_layout(solve_layout(layout, 426.0), block_latex) if layout is not None else ""
        packages = sorted(
            {package for block in self.registry.blocks() for package in required_packages_for_block(block, in_box=True)}
        )
        styles = project / "styles"
        styles.mkdir(parents=True, exist_ok=True)
        document_theme = DocumentTheme(
            id="doc_preview",
            name="Preview",
            page={"size": "a4", "orientation": "portrait", "columns": 1, "margin": {"leftMm": 30, "rightMm": 25, "topMm": 25, "bottomMm": 25}},
            typography={"textFamily": "", "mathFamily": "", "monoFamily": "", "baseSizePt": 11, "lineSpacing": 1.15},
            tables={"preset": "booktabs"},
            layout={"blockGapPt": 10},
        )
        (styles / "icstex-generated.sty").write_text(render_document_theme_sty(document_theme), encoding="utf-8")
        main = project / "main.tex"
        main.write_text(
            "\\documentclass{ctexart}\n"
            + "".join(f"\\usepackage{{{package}}}\n" for package in packages)
            + "\\input{styles/icstex-generated.sty}\n"
            + "\\graphicspath{{assets/images/}}\n"
            + "\\begin{document}\n"
            + body
            + "\\end{document}\n",
            encoding="utf-8",
        )
        if self._preview_manager is None:
            self._preview_manager = CompileManager(
                main,
                toolchain=detect_toolchain(),
                engine=LaTeXEngine.XELATEX,
            )
        return self._preview_manager.compile_now(BuildPurpose.FINAL)

    def _sync_table_to_registry(self) -> None:
        table_block = next((block for block in self.registry.blocks() if block.type == "table"), None)
        if table_block is not None:
            self.registry.update(table_block.id, {"content": self.table_editor.model.data.to_content_dict()})
