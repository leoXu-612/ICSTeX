"""One explicit, captured-target formula edit path for Block entry points."""
from copy import deepcopy

from PySide6.QtWidgets import QDialog, QMessageBox

from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.blocks.property_draft import PropertyDraft, draft_conflict
from app.core.blocks.schema import validate_block
from app.core.formula_input import recognize_formula


def edit_formula_block(parent, session, block_id, *, dialog_factory=None):
    if session._closed:
        return False
    key = ("formula", block_id)
    previous = session.editor_drafts.get(key)
    block = session.registry.get(block_id)
    base = deepcopy(previous.base if previous else block.to_dict() if block is not None else None)
    if base is None or base["type"] != "formula" or validate_block(base):
        QMessageBox.warning(parent, "公式未修改", "原公式缺失或格式未知，不能安全编辑；原内容保留。")
        return False
    if dialog_factory is None:
        from app.gui.formula_dialog import FormulaDialog
        dialog_factory = FormulaDialog
    seed = (previous.values if previous else base["content"])["latexCache"]
    dialog = dialog_factory(parent, "", 0, 0, seed_text=f"\\({seed}\\)")
    try:
        if dialog.exec() != QDialog.DialogCode.Accepted or session._closed:
            return False
        plan = dialog.plan()
        envelope = recognize_formula(plan.text) if plan is not None else None
        if envelope is None:
            return False
        content = FormulaBlockAdapter().content_for(envelope.body)
        draft = PropertyDraft("formula", block_id, f"公式 {base['alias']}",
                              base, deepcopy(base["content"]), content)
        # Opening and confirming unchanged source must not normalize a managed
        # AST, including opaque data that the visual projection cannot represent.
        if envelope.body == base["content"]["latexCache"]:
            conflict = draft_conflict(draft, session.registry, session.layout)
            if conflict:
                QMessageBox.warning(parent, "公式未应用", conflict)
                return False
            session.discard_editor_draft(key)
            return True
        if session.editor_drafts.get(key) != previous:
            QMessageBox.warning(parent, "公式草稿已变化", "已有较新的公式草稿，未覆盖；请重新打开核对。")
            return False
        session.set_editor_draft(draft)
        if not session.apply_editor_drafts((key,)):
            QMessageBox.warning(parent, "公式草稿未应用", session.editor_draft_error)
            return False
        return True
    finally:
        if isinstance(dialog, QDialog):
            dialog.deleteLater()
