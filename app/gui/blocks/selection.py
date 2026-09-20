"""Unified cross-panel selection for the Block workspace."""
from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class SelectionContext:
    block_id: str | None = None
    layout_node_id: str | None = None
    slot_id: str | None = None
    source_id: str | None = None

    def is_empty(self) -> bool:
        return not (self.block_id or self.layout_node_id or self.slot_id or self.source_id)

    def with_block(self, block_id: str | None) -> "SelectionContext":
        return replace(self, block_id=block_id)

    def with_layout_node(self, layout_node_id: str | None) -> "SelectionContext":
        return replace(self, layout_node_id=layout_node_id)

    def with_slot(self, slot_id: str | None) -> "SelectionContext":
        return replace(self, slot_id=slot_id)

    def with_source(self, source_id: str | None) -> "SelectionContext":
        return replace(self, source_id=source_id)


class SelectionManager(QObject):
    """Single source of truth for what is selected in the Block workspace.

    ``selection_changed(context, source)`` is emitted only when the context
    actually changes; a ``source`` label lets receivers update their own
    highlight without re-broadcasting the same selection (loop guard).
    """

    selection_changed = Signal(object, str)  # SelectionContext, source

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._current = SelectionContext()

    @property
    def current(self) -> SelectionContext:
        return self._current

    def select(self, context: SelectionContext, *, source: str) -> None:
        if context == self._current:
            return
        self._current = context
        self.selection_changed.emit(self._current, source)

    def select_block(self, block_id: str | None, *, source: str) -> None:
        self.select(self._current.with_block(block_id), source=source)

    def select_layout_node(self, layout_node_id: str | None, *, source: str) -> None:
        self.select(replace(self._current, layout_node_id=layout_node_id, slot_id=None), source=source)

    def select_slot(self, slot_id: str | None, *, source: str) -> None:
        self.select(replace(self._current, slot_id=slot_id, layout_node_id=None), source=source)

    def select_source(self, source_id: str | None, *, source: str) -> None:
        self.select(self._current.with_source(source_id), source=source)

    def clear(self, *, source: str) -> None:
        self.select(SelectionContext(), source=source)
