"""Controller that turns GUI actions into commands on the shared session."""
from __future__ import annotations

from PySide6.QtCore import QObject

from app.gui.blocks.commands import (
    AddBlockCommand,
    AssignBlockToSlotCommand,
    DeleteBlockCommand,
    DuplicateBlockCommand,
    RenameBlockCommand,
    UpdateBlockCommand,
)


class BlockWorkspaceController(QObject):
    """All structured edits go through ``session.undo_stack`` commands."""

    def __init__(self, session, workspace=None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.workspace = workspace

    def add_block(self, block_type: str, alias: str | None = None, content: dict | None = None) -> str:
        command = AddBlockCommand(self.session, block_type, alias=alias, content=content)
        self.session.undo_stack.push(command)
        return command._block_id or ""

    def delete_block(self, block_id: str) -> None:
        if self.session.registry.find_references_to(block_id):
            raise ValueError("Block 仍被其他 Block 引用，无法删除")
        self.session.undo_stack.push(DeleteBlockCommand(self.session, block_id))

    def duplicate_block(self, block_id: str) -> None:
        self.session.undo_stack.push(DuplicateBlockCommand(self.session, block_id))

    def rename_block(self, block_id: str, alias: str) -> None:
        self.session.undo_stack.push(RenameBlockCommand(self.session, block_id, alias))

    def update_block(self, block_id: str, patch: dict, *, text: str = "修改 Block") -> None:
        self.session.undo_stack.push(UpdateBlockCommand(self.session, block_id, patch, text=text))

    def assign_block_to_slot(self, block_id: str, slot_id: str) -> None:
        self.session.undo_stack.push(AssignBlockToSlotCommand(self.session, block_id, slot_id))

    def undo(self) -> None:
        self.session.undo_stack.undo()

    def redo(self) -> None:
        self.session.undo_stack.redo()

    @property
    def can_undo(self) -> bool:
        return self.session.undo_stack.canUndo()

    @property
    def can_redo(self) -> bool:
        return self.session.undo_stack.canRedo()
