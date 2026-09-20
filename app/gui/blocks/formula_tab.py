"""FormulaBlock editing in the Block MVP console (FormulaBlockEditor)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.registry import BlockRegistry
from app.gui.formula_dialog import FormulaDialog
from app.gui.blocks.formula_edit import edit_formula_block


class FormulaBlockTab(QWidget):
    def __init__(self, registry: BlockRegistry, *, session=None, parent=None) -> None:
        super().__init__(parent)
        self.registry = registry
        if session is None:
            from app.gui.blocks.project_session import ProjectSession
            session = ProjectSession(registry=registry, parent=self)
        self._session = session
        self.block_list = QListWidget()
        self.edit_button = QPushButton("编辑公式…")
        self.edit_button.clicked.connect(self._edit_selected)
        self.hint = QLabel("通过现有可视化公式编辑器修改公式 Block 的受管理 AST。")
        self.hint.setWordWrap(True)

        buttons = QHBoxLayout()
        buttons.addWidget(self.edit_button)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.addWidget(self.hint)
        layout.addWidget(self.block_list)
        layout.addLayout(buttons)
        self.refresh()
        session.model_changed.connect(lambda _reason: self.refresh())
        session.editor_drafts_changed.connect(self.refresh)

    def refresh(self) -> None:
        selected = self.block_list.currentItem()
        selected_id = selected.data(256) if selected is not None else None
        self.block_list.clear()
        seen = set()
        for block in self.registry.blocks():
            if block.type == "formula":
                draft = self._session.editor_drafts.get(("formula", block.id))
                latex = (draft.values if draft else block.content).get("latexCache", "")
                item = QListWidgetItem(f"{block.alias}：{latex}")
                item.setData(256, block.id)
                self.block_list.addItem(item)
                seen.add(block.id)
                if block.id == selected_id:
                    self.block_list.setCurrentItem(item)
        for draft in self._session.editor_drafts.values():
            if draft.kind == "formula" and draft.target_id not in seen:
                item = QListWidgetItem(f"{draft.label}（原对象不可用）：{draft.values['latexCache']}")
                item.setData(256, draft.target_id)
                self.block_list.addItem(item)
                if draft.target_id == selected_id:
                    self.block_list.setCurrentItem(item)

    def _edit_selected(self) -> None:
        selected = self.block_list.selectedItems()
        if not selected:
            return
        block_id = selected[0].data(256)
        edit_formula_block(self, self._session, block_id, dialog_factory=FormulaDialog)
        self.refresh()
