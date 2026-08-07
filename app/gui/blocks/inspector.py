"""Context Inspector dock: edits the selected Block / Layout / Slot."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QFileDialog,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.blocks.asset_import import import_image
from app.core.formula_input import recognize_formula
from app.gui.blocks.commands import ChangeLayoutCommand
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.workspace_controller import BlockWorkspaceController


class BlockInspector(QWidget):
    """Shows and edits properties of the currently selected object."""

    def __init__(self, session: ProjectSession, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.controller = BlockWorkspaceController(session)
        self.layout_editor = None
        self.workspace = None
        self._current_block_id: str | None = None

        self.title = QLabel("未选择")
        self.title.setWordWrap(True)
        self.alias_edit = QLineEdit()
        self.type_label = QLabel("")
        self.content_edit = QPlainTextEdit()
        self.content_edit.setPlaceholderText("内容…")
        self.heading_level = QComboBox()
        self.heading_level.addItems(["1", "2", "3", "4"])
        self.image_width = QDoubleSpinBox()
        self.image_width.setRange(0.0, 500.0)
        self.image_width.setSuffix(" mm")
        self.image_height = QDoubleSpinBox()
        self.image_height.setRange(0.0, 500.0)
        self.image_height.setSuffix(" mm")
        self.image_source_label = QLabel("")
        self.image_source_label.setWordWrap(True)
        self.image_replace_button = QPushButton("替换图片…")
        self.image_replace_button.clicked.connect(self._replace_image)
        self.caption_edit = QLineEdit()
        self.apply_button = QPushButton("应用修改")
        self.apply_button.clicked.connect(self._apply_block_edit)
        self.formula_button = QPushButton("打开完整公式编辑器…")
        self.formula_button.clicked.connect(self._open_formula_editor)
        self.table_button = QPushButton("打开完整表格编辑器")
        self.table_button.clicked.connect(self._open_table_editor)
        self.formula_info = QLabel("")
        self.formula_info.setWordWrap(True)

        self.layout_kind = QLabel("")
        self.layout_gap = QDoubleSpinBox()
        self.layout_gap.setRange(0.0, 100.0)
        self.layout_gap.setSuffix(" mm")
        self.layout_alignment = QComboBox()
        self.layout_alignment.addItems(["top", "middle", "bottom"])
        self.layout_fallback = QComboBox()
        self.layout_fallback.addItems(["stackVertically", "error", "wrapRows", "normalizeWeights", "reduceGap"])
        self.layout_apply = QPushButton("应用布局属性")
        self.layout_apply.clicked.connect(self._apply_layout_edit)

        self.form = QFormLayout()
        self.form.addRow("类型", self.type_label)
        self.form.addRow("别名", self.alias_edit)
        self.form.addRow("内容", self.content_edit)
        self.form.addRow("标题级别", self.heading_level)
        self.form.addRow("宽度", self.image_width)
        self.form.addRow("高度", self.image_height)
        self.form.addRow("图片源", self.image_source_label)
        self.form.addRow("", self.image_replace_button)
        self.form.addRow("标题", self.caption_edit)
        self.form.addRow("", self.formula_button)
        self.form.addRow("", self.table_button)
        self.form.addRow("", self.formula_info)
        self.form.addRow("容器类型", self.layout_kind)
        self.form.addRow("gap", self.layout_gap)
        self.form.addRow("对齐", self.layout_alignment)
        self.form.addRow("回退", self.layout_fallback)
        self.form.addRow("", self.layout_apply)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addLayout(self.form)
        layout.addWidget(self.apply_button)
        layout.addStretch()

        session.selection.selection_changed.connect(self._on_selection)
        session.model_changed.connect(lambda _reason: self.refresh())

    def set_layout_editor(self, panel) -> None:
        self.layout_editor = panel

    def set_workspace(self, workspace) -> None:
        self.workspace = workspace

    # --- selection handling ----------------------------------------------
    def _on_selection(self, context, _source: str) -> None:
        self._current_block_id = context.block_id
        self.refresh()

    def refresh(self) -> None:
        self._refresh_block()
        self._refresh_layout()

    def _refresh_block(self) -> None:
        block_id = self._current_block_id
        block = self.session.registry.get(block_id) if block_id else None
        if block is None:
            self.title.setText("未选择 Block")
            for widget in (
                self.type_label,
                self.alias_edit,
                self.content_edit,
                self.heading_level,
                self.image_width,
                self.image_height,
                self.image_source_label,
                self.image_replace_button,
                self.caption_edit,
                self.formula_button,
                self.table_button,
                self.formula_info,
            ):
                widget.setEnabled(False)
            return
        self.title.setText(f"{block.type}: {block.alias}")
        self.type_label.setText(block.type)
        self.alias_edit.setText(block.alias)
        content = block.content or {}
        self._content_edit_for(block.type, content)
        for widget in (
            self.type_label,
            self.alias_edit,
            self.content_edit,
            self.heading_level,
            self.image_width,
            self.image_height,
            self.image_source_label,
            self.image_replace_button,
            self.caption_edit,
            self.formula_button,
            self.table_button,
            self.formula_info,
        ):
            widget.setEnabled(True)
        self.formula_button.setVisible(block.type == "formula")
        self.table_button.setVisible(block.type == "table")
        self.formula_info.setVisible(block.type == "formula")
        self.image_replace_button.setVisible(block.type == "image")
        self.image_source_label.setVisible(block.type == "image")
        if block.type == "formula":
            self.formula_info.setText(str(content.get("latexCache", "")))
        if block.type == "image":
            self.image_source_label.setText(str(content.get("source", "（未设置）")))

    def _content_edit_for(self, block_type: str, content: dict) -> None:
        self.content_edit.setPlainText(str(content.get("text", "")))
        self.heading_level.setCurrentText(str(content.get("level", "1")))
        if block_type == "image":
            self.image_width.setValue(float(content.get("widthMm", 0.0) or 0.0))
            self.image_height.setValue(float(content.get("heightMm", 0.0) or 0.0))
            caption = content.get("caption", "") or ""
            self.caption_edit.setText(str(caption))
        if block_type == "rawLatex":
            self.content_edit.setPlainText(str(content.get("latex", "")))

    def _refresh_layout(self) -> None:
        context = self.session.selection.current
        if context.layout_node_id is None and context.slot_id is None:
            self.layout_kind.setText("（未选择布局对象）")
            return
        self.layout_kind.setText("选择布局对象后可在布局面板调整")

    # --- apply actions ----------------------------------------------------
    def _apply_block_edit(self) -> None:
        block_id = self._current_block_id
        block = self.session.registry.get(block_id) if block_id else None
        if block is None:
            return
        patch: dict = {"alias": self.alias_edit.text().strip() or block.alias}
        content = deepcopy(block.content)
        if block.type in ("text", "heading", "quote", "list"):
            content["text"] = self.content_edit.toPlainText()
            if block.type == "heading":
                content["level"] = int(self.heading_level.currentText())
        elif block.type == "rawLatex":
            content["latex"] = self.content_edit.toPlainText()
        elif block.type == "image":
            content["widthMm"] = self.image_width.value() or None
            content["heightMm"] = self.image_height.value() or None
            content["caption"] = self.caption_edit.text().strip()
        patch["content"] = content
        self.controller.update_block(block.id, patch, text=f"修改 {block.type} 属性")

    def _open_formula_editor(self) -> None:
        block_id = self._current_block_id
        block = self.session.registry.get(block_id) if block_id else None
        if block is None:
            return
        from PySide6.QtWidgets import QDialog
        from app.gui.formula_dialog import FormulaDialog

        latex = str((block.content or {}).get("latexCache", ""))
        dialog = FormulaDialog(self, "", 0, 0, seed_text=f"\\({latex}\\)")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        plan = dialog.plan()
        if plan is None:
            return
        envelope = recognize_formula(plan.text)
        if envelope is None:
            return
        adapter = FormulaBlockAdapter()
        content = adapter.update_ast(adapter.latex_to_ast(envelope.body))
        self.controller.update_block(block.id, {"content": content}, text="修改公式")

    def _open_table_editor(self) -> None:
        if self.workspace is not None:
            self.workspace.tabs.setCurrentIndex(1)

    def _replace_image(self) -> None:
        block_id = self._current_block_id
        block = self.session.registry.get(block_id) if block_id else None
        if block is None or self.session.project_dir is None:
            return
        file_name, _ = QFileDialog.getOpenFileName(self, "替换图片", str(Path.home()), "图片 (*.png *.jpg *.jpeg *.gif *.pdf *.svg *.bmp)")
        if not file_name:
            return
        relative = import_image(self.session.project_dir, Path(file_name))
        self.controller.update_block(
            block.id,
            {"content": {**block.content, "source": relative}},
            text="替换图片",
        )

    def _apply_layout_edit(self) -> None:
        if self.layout_editor is None or self.layout_editor.layout is None:
            return
        panel = self.layout_editor
        old = deepcopy(panel.layout)
        new = _with_layout_props(old, self.layout_gap.value(), self.layout_alignment.currentText(), self.layout_fallback.currentText())
        panel.command_stack.push(ChangeLayoutCommand(panel, old, new)) if panel.command_stack is not None else panel._commit(new)


def _with_layout_props(layout, gap: float, alignment: str, fallback: str):
    from app.core.blocks.layout import LayoutNode, Size

    return LayoutNode(
        schemaVersion=layout.schemaVersion,
        id=layout.id,
        kind=layout.kind,
        children=layout.children,
        columns=layout.columns,
        gap=Size(value=gap, unit="mm"),
        rowGap=layout.rowGap,
        alignment=alignment,
        keepTogether=layout.keepTogether,
        fallback={"strategy": fallback},
    )
