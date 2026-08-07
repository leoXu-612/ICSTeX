"""FormulaBlock editing in the Block MVP console (FormulaBlockEditor)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.blocks.registry import BlockRegistry
from app.gui.formula_dialog import FormulaDialog
from app.core.formula_input import recognize_formula
from app.gui.blocks.commands import UpdateBlockCommand


class FormulaBlockTab(QWidget):
    def __init__(self, registry: BlockRegistry, *, session=None, parent=None) -> None:
        super().__init__(parent)
        self.registry = registry
        self._session = session
        self.adapter = FormulaBlockAdapter()
        self.block_list = QListWidget()
        self.edit_button = QPushButton("编辑公式…")
        self.edit_button.clicked.connect(self._edit_selected)
        self.hint = QLabel("通过现有可视化公式编辑器修改公式 Block 的受管理 AST。")

        buttons = QHBoxLayout()
        buttons.addWidget(self.edit_button)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.addWidget(self.hint)
        layout.addWidget(self.block_list)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self) -> None:
        self.block_list.clear()
        for block in self.registry.blocks():
            if block.type == "formula":
                latex = block.content.get("latexCache", "")
                item = QListWidgetItem(f"{block.alias}：{latex}")
                item.setData(256, block.id)
                self.block_list.addItem(item)

    def _edit_selected(self) -> None:
        selected = self.block_list.selectedItems()
        if not selected:
            return
        block_id = selected[0].data(256)
        block = self.registry.get(block_id)
        if block is None:
            return
        latex = block.content.get("latexCache", "")
        dialog = FormulaDialog(self, "", 0, 0, seed_text=f"\\({latex}\\)")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        plan = dialog.plan()
        if plan is None:
            return
        envelope = recognize_formula(plan.text)
        if envelope is None:
            return
        content = self.adapter.update_ast(self.adapter.latex_to_ast(envelope.body))
        if self._session is not None:
            self._session.undo_stack.push(
                UpdateBlockCommand(self._session, block.id, {"content": content}, text="修改公式")
            )
        else:
            self.registry.update(block.id, {"content": content})
        self.refresh()
