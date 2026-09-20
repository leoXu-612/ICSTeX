"""QUndoCommand implementations for structured Block/Layout edits.

Every command mutates the shared ``ProjectSession`` models and notifies the
session so it can run its debounced save + single CompileManager preview.
Commands keep the small amount of state needed for a full undo (original
block snapshots, removed layout slots, table data snapshots).
"""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtGui import QUndoCommand

from app.core.blocks.model import Block
from app.core.blocks.layout import BlockSlot, LayoutNode
from app.core.blocks.registry import BlockRegistry, CreateBlockInput


def _layout_slots_removed(layout: LayoutNode | None, block_id: str) -> tuple[LayoutNode | None, list]:
    """Remove every BlockSlot referencing ``block_id``; returns (new, removed)."""
    if layout is None:
        return None, []

    def rebuild(node) -> tuple[object | None, list]:
        removed: list = []
        if not hasattr(node, "kind"):
            if node.blockId == block_id:
                return None, [node]
            return node, []
        if node.kind == "block":
            if node.blockId == block_id:
                return None, [node]
            return node, []
        new_children: list = []
        for child in node.children:
            rebuilt, dropped = rebuild(child)
            removed.extend(dropped)
            if rebuilt is not None:
                new_children.append(rebuilt)
        if not new_children:
            return None, removed
        return LayoutNode(
            schemaVersion=node.schemaVersion,
            id=node.id,
            kind=node.kind,
            children=tuple(new_children),
            columns=node.columns,
            gap=node.gap,
            rowGap=node.rowGap,
            alignment=node.alignment,
            keepTogether=node.keepTogether,
            fallback=node.fallback,
        ), removed

    rebuilt, removed = rebuild(layout)
    return rebuilt, removed


class _SessionCommand(QUndoCommand):
    def __init__(self, session, text: str) -> None:
        super().__init__(text)
        self._session = session

    def _notify(self, reason: str) -> None:
        self._session.notify_model_changed(reason)


class AddBlockCommand(_SessionCommand):
    def __init__(self, session, block_type: str, alias: str | None = None, content: dict | None = None) -> None:
        super().__init__(session, f"新建 {block_type} Block")
        self._block_type = block_type
        self._alias = alias or session.next_alias(block_type)
        self._content = content
        self._block_id: str | None = None

    def redo(self) -> None:
        block = self._session.registry.create(
            CreateBlockInput(type=self._block_type, alias=self._alias, content=self._content or {})
        )
        self._block_id = block.id
        self._notify(f"block_added:{self._block_id}")

    def undo(self) -> None:
        if self._block_id is not None:
            self._session.registry.remove(self._block_id)
        self._notify(f"block_removed:{self._block_id}")


class DeleteBlockCommand(_SessionCommand):
    def __init__(self, session, block_id: str) -> None:
        super().__init__(session, "删除 Block")
        self._block_id = block_id
        self._snapshot: Block | None = None
        self._removed_slots: list = []

    def redo(self) -> None:
        registry: BlockRegistry = self._session.registry
        block = registry.get(self._block_id)
        if block is None:
            return
        if registry.find_references_to(self._block_id):
            raise ValueError("Block 仍被其他 Block 引用，无法删除")
        self._snapshot = deepcopy(block)
        layout = self._session.layout
        new_layout, removed = _layout_slots_removed(layout, self._block_id)
        self._removed_slots = removed
        registry.remove(self._block_id)
        if new_layout is not layout:
            self._session.set_layout(new_layout, reason="block_deleted_layout")
        self._notify(f"block_deleted:{self._block_id}")

    def undo(self) -> None:
        if self._snapshot is not None:
            self._session.registry.restore(deepcopy(self._snapshot))
        for slot in self._removed_slots:
            self._session.set_layout(
                _insert_slot_back(self._session.layout, slot),
                reason="block_restored_layout",
            )
        self._notify(f"block_restored:{self._block_id}")


def _insert_slot_back(layout: LayoutNode | None, slot) -> LayoutNode | None:
    if layout is None:
        return LayoutNode(id="lyt_row", kind="row", children=(slot,))
    return LayoutNode(
        schemaVersion=layout.schemaVersion,
        id=layout.id,
        kind=layout.kind,
        children=layout.children + (slot,),
        columns=layout.columns,
        gap=layout.gap,
        rowGap=layout.rowGap,
        alignment=layout.alignment,
        keepTogether=layout.keepTogether,
        fallback=layout.fallback,
    )


class DuplicateBlockCommand(_SessionCommand):
    def __init__(self, session, block_id: str) -> None:
        super().__init__(session, "复制 Block")
        self._block_id = block_id
        self._copy_id: str | None = None

    def redo(self) -> None:
        source = self._session.registry.get(self._block_id)
        if source is None:
            return
        copy = self._session.registry.create(
            CreateBlockInput(
                type=source.type,
                alias=f"{source.alias} 副本",
                content=deepcopy(source.content),
                semantic=deepcopy(source.semantic),
            )
        )
        self._copy_id = copy.id
        self._notify(f"block_duplicated:{self._copy_id}")

    def undo(self) -> None:
        if self._copy_id is not None:
            self._session.registry.remove(self._copy_id)
        self._notify(f"block_duplicate_removed:{self._copy_id}")


class RenameBlockCommand(_SessionCommand):
    def __init__(self, session, block_id: str, alias: str) -> None:
        super().__init__(session, "重命名 Block")
        self._block_id = block_id
        self._alias = alias
        self._old_alias: str = ""

    def redo(self) -> None:
        block = self._session.registry.get(self._block_id)
        if block is None:
            return
        self._old_alias = block.alias
        self._session.registry.rename_alias(self._block_id, self._alias)
        self._notify(f"block_renamed:{self._block_id}")

    def undo(self) -> None:
        if self._old_alias:
            self._session.registry.rename_alias(self._block_id, self._old_alias)
        self._notify(f"block_renamed:{self._block_id}")


class UpdateBlockCommand(_SessionCommand):
    """Generic content/semantic patch with a snapshot-based undo."""

    def __init__(self, session, block_id: str, patch: dict, text: str = "修改 Block") -> None:
        super().__init__(session, text)
        self._block_id = block_id
        self._patch = patch
        self._snapshot: dict = {}

    def redo(self) -> None:
        block = self._session.registry.get(self._block_id)
        if block is None:
            return
        self._snapshot = {
            "alias": block.alias,
            "semantic": deepcopy(block.semantic),
            "content": deepcopy(block.content),
            "references": deepcopy(block.references),
            "metadata": deepcopy(block.metadata),
            "extensions": deepcopy(block.extensions),
        }
        self._session.registry.update(self._block_id, deepcopy(self._patch))
        self._notify(f"block_updated:{self._block_id}")

    def undo(self) -> None:
        if self._snapshot:
            self._session.registry.update(self._block_id, deepcopy(self._snapshot))
        self._notify(f"block_updated:{self._block_id}")


class ApplyPropertyDraftsCommand(_SessionCommand):
    """One explicitly confirmed property batch after all bases were checked."""

    def __init__(self, session, patches, layout):
        super().__init__(session, "应用编辑草稿")
        self._after = deepcopy(patches)
        self._before = {block_id: {key: deepcopy(getattr(session.registry.get(block_id), key))
                                  for key in patch} for block_id, patch in patches.items()}
        self._old_layout = deepcopy(session.layout)
        self._new_layout = deepcopy(layout)
        self._reason = (f"block_updated:{next(iter(patches))}" if len(patches) == 1 and layout == session.layout
                        else "property_drafts_applied")

    def _apply(self, patches, layout):
        for block_id, patch in patches.items():
            self._session.registry.update(block_id, deepcopy(patch))
        self._session.layout = deepcopy(layout)
        self._notify(self._reason)

    def redo(self):
        self._apply(self._after, self._new_layout)

    def undo(self):
        self._apply(self._before, self._old_layout)


class AssignBlockToSlotCommand(_SessionCommand):
    def __init__(self, session, block_id: str, slot_id: str) -> None:
        super().__init__(session, "分配到布局槽位")
        self._block_id = block_id
        self._slot_id = slot_id
        self._old_block_id: str | None = None

    def _apply(self, block_id: str) -> None:
        layout = self._session.layout
        if layout is None:
            return
        updated = _replace_slot_block(layout, self._slot_id, block_id)
        self._session.set_layout(updated, reason="slot_assigned")

    def redo(self) -> None:
        layout = self._session.layout
        if layout is not None:
            slot = _find_slot(layout, self._slot_id)
            if slot is not None:
                self._old_block_id = slot.blockId
        self._apply(self._block_id)
        self._notify(f"slot_assigned:{self._slot_id}")

    def undo(self) -> None:
        self._apply(self._old_block_id)
        self._notify(f"slot_assigned:{self._slot_id}")


def _find_slot(layout: LayoutNode | None, slot_id: str):
    if layout is None:
        return None
    if not hasattr(layout, "kind"):
        return layout if layout.instanceId == slot_id else None
    if layout.kind == "block":
        return layout if layout.instanceId == slot_id else None
    for child in layout.children:
        found = _find_slot(child, slot_id)
        if found is not None:
            return found
    return None


def _replace_slot_block(layout: LayoutNode, slot_id: str, block_id: str | None) -> LayoutNode:
    if not hasattr(layout, "kind"):
        if layout.instanceId == slot_id:
            return BlockSlot(
                instanceId=layout.instanceId,
                blockId=block_id,
                weight=layout.weight,
                minWidthPt=layout.minWidthPt,
            )
        return layout
    if layout.kind == "block":
        if layout.instanceId == slot_id:
            return BlockSlot(
                instanceId=layout.instanceId,
                blockId=block_id,
                weight=layout.weight,
                minWidthPt=layout.minWidthPt,
            )
        return layout
    return LayoutNode(
        schemaVersion=layout.schemaVersion,
        id=layout.id,
        kind=layout.kind,
        children=tuple(
            _replace_slot_block(child, slot_id, block_id) if hasattr(child, "kind") else child
            for child in layout.children
        ),
        columns=layout.columns,
        gap=layout.gap,
        rowGap=layout.rowGap,
        alignment=layout.alignment,
        keepTogether=layout.keepTogether,
        fallback=layout.fallback,
    )


class ChangeLayoutCommand(QUndoCommand):
    """Apply a complete layout-tree replacement (row/grid/reorder/property).

    Operates on the layout editor panel: ``redo``/``undo`` set the panel's
    layout state, which emits ``layoutChanged`` so the workspace keeps
    ``ProjectSession.layout`` in sync through the normal model-change route.
    """

    def __init__(self, panel, old_layout: LayoutNode | None, new_layout: LayoutNode | None) -> None:
        super().__init__("修改布局")
        self._panel = panel
        self._old_layout = deepcopy(old_layout)
        self._new_layout = deepcopy(new_layout)

    def redo(self) -> None:
        self._panel.apply_layout_state(self._new_layout)

    def undo(self) -> None:
        self._panel.apply_layout_state(self._old_layout)
