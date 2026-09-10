"""Block canvas operations and layout inspector (Sprint 2 GUI milestone).

Multi-selected Blocks can be grouped into a Row or Grid, ungrouped, and
inspected (weight/gap/alignment/fallback). Every operation mutates the core
LayoutNode with an undo stack; Block content is never modified.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.ids import new_instance_id
from app.core.blocks.layout import BlockSlot, LayoutNode, Size, block_slot
from app.core.blocks.registry import BlockRegistry
from app.core.blocks.property_draft import layout_gap_mm
from app.gui.blocks.commands import ChangeLayoutCommand
from app.gui.responsive.helpers import ButtonFlowLayout


class BlockLayoutPanel(QWidget):
    layoutChanged = Signal()

    def __init__(self, registry: BlockRegistry, layout: LayoutNode | None = None, parent=None) -> None:
        super().__init__(parent)
        self.registry = registry
        self.layout: LayoutNode | None = layout
        self._undo: list[LayoutNode | None] = []
        # When set, every mutation is pushed onto the shared QUndoStack as a
        # ChangeLayoutCommand instead of the panel-local undo list.
        self.command_stack: QUndoStack | None = None

        self.block_list = QListWidget()
        self.block_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.block_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.refresh_block_list()

        self.row_button = QPushButton("组合为 Row")
        self.grid_button = QPushButton("组合为 Grid")
        self.ungroup_button = QPushButton("取消组合")
        self.undo_button = QPushButton("撤销")
        self.row_button.clicked.connect(self.apply_row)
        self.grid_button.clicked.connect(self.apply_grid)
        self.ungroup_button.clicked.connect(self.ungroup)
        self.undo_button.clicked.connect(self.undo)

        self.slot_list = QListWidget()
        self.slot_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.slot_list.model().rowsMoved.connect(self._on_slots_moved)

        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(1.0, 100.0)
        self.weight_spin.setValue(1.0)
        self.gap_spin = QDoubleSpinBox()
        self.gap_spin.setRange(0.0, 100.0)
        self.gap_spin.setSuffix(" mm")
        self.alignment_combo = QComboBox()
        self.alignment_combo.addItems(["top", "middle", "bottom"])
        self.fallback_combo = QComboBox()
        self.fallback_combo.addItems(["stackVertically", "error", "wrapRows", "normalizeWeights", "reduceGap"])
        self.weight_spin.valueChanged.connect(self._weight_changed)
        self.slot_list.currentRowChanged.connect(lambda _row: self._sync_weight())
        self.gap_spin.valueChanged.connect(lambda _value: self._inspector_changed("gap"))
        self.alignment_combo.currentTextChanged.connect(lambda _text: self._inspector_changed("alignment"))
        self.fallback_combo.currentTextChanged.connect(lambda _text: self._inspector_changed("fallback"))

        inspector = QFormLayout()
        inspector.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        inspector.addRow("权重", self.weight_spin)
        inspector.addRow("gap", self.gap_spin)
        inspector.addRow("对齐", self.alignment_combo)
        inspector.addRow("回退", self.fallback_combo)

        buttons = ButtonFlowLayout()
        for widget in (self.row_button, self.grid_button, self.ungroup_button, self.undo_button):
            buttons.addWidget(widget)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("选择 Block 后组合："))
        layout.addWidget(self.block_list)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("布局槽位（可拖拽调整顺序）："))
        layout.addWidget(self.slot_list)
        layout.addWidget(QLabel("布局属性："))
        layout.addLayout(inspector)
        self._sync_inspector()
        self._refresh_slots()

    def selected_block_ids(self) -> list[str]:
        return [
            self.block_list.item(index).data(256)
            for index in range(self.block_list.count())
            if self.block_list.item(index).isSelected()
        ]

    def refresh_block_list(self) -> None:
        selected_ids = set(self.selected_block_ids())
        self.block_list.blockSignals(True)
        self.block_list.clear()
        for block in self.registry.blocks():
            item = QListWidgetItem(f"{block.alias}（{block.id}）")
            item.setData(256, block.id)
            item.setSelected(block.id in selected_ids)
            self.block_list.addItem(item)
        self.block_list.blockSignals(False)

    def apply_row(self) -> None:
        self._apply(lambda children: LayoutNode(id="lyt_row", kind="row", children=tuple(children)))

    def apply_grid(self) -> None:
        self._apply(
            lambda children: LayoutNode(id="lyt_grid", kind="grid", columns=2, children=tuple(children))
        )

    def ungroup(self) -> None:
        self._commit(None)

    def undo(self) -> None:
        if self.command_stack is not None:
            self.command_stack.undo()
            return
        if not self._undo:
            return
        self.apply_layout_state(self._undo.pop())

    def _apply(self, builder) -> None:
        block_ids = self.selected_block_ids()
        if not block_ids:
            return
        self._commit(builder([block_slot(block_id) for block_id in block_ids]))

    def _commit(self, new_layout: LayoutNode | None) -> None:
        old_layout = deepcopy(self.layout)
        if new_layout == old_layout:
            return
        if self.command_stack is not None:
            self.command_stack.push(ChangeLayoutCommand(self, old_layout, new_layout))
        else:
            self._push()
            self.apply_layout_state(new_layout)

    def apply_layout_state(self, layout: LayoutNode | None) -> None:
        self.layout = layout
        self.layoutChanged.emit()
        self._sync_inspector()

    def _push(self) -> None:
        self._undo.append(deepcopy(self.layout))
        if len(self._undo) > 100:
            self._undo.pop(0)

    def _sync_inspector(self) -> None:
        has_layout = self.layout is not None
        for widget in (self.gap_spin, self.alignment_combo, self.fallback_combo, self.slot_list):
            widget.setEnabled(has_layout)
        if not has_layout:
            self._refresh_slots()
            return
        with QSignalBlocker(self.gap_spin), QSignalBlocker(self.alignment_combo), QSignalBlocker(self.fallback_combo):
            self.gap_spin.setValue(layout_gap_mm(self.layout))
            self.alignment_combo.setCurrentText(self.layout.alignment)
            strategy = self.layout.fallback.get("strategy", "stackVertically")
            if self.fallback_combo.findText(strategy) >= 0:
                self.fallback_combo.setCurrentText(strategy)
        self._refresh_slots()

    def _refresh_slots(self) -> None:
        current = self.slot_list.currentItem()
        selected_id = current.data(256) if current is not None else None
        self.slot_list.blockSignals(True)
        self.slot_list.clear()
        if self.layout is not None:
            for child in self.layout.children:
                instance_id = getattr(child, "instanceId", "")
                block_id = getattr(child, "blockId", "")
                item = QListWidgetItem(f"{instance_id} -> {block_id}")
                item.setData(256, instance_id or getattr(child, "id", None))
                self.slot_list.addItem(item)
                if selected_id is not None and item.data(256) == selected_id:
                    self.slot_list.setCurrentItem(item)
        self.slot_list.blockSignals(False)
        self._sync_weight()

    def _selected_slot(self) -> BlockSlot | None:
        row = self.slot_list.currentRow()
        if self.layout is not None and 0 <= row < len(self.layout.children):
            child = self.layout.children[row]
            if isinstance(child, BlockSlot):
                return child
        return None

    def _sync_weight(self) -> None:
        slot = self._selected_slot()
        self.weight_spin.setEnabled(slot is not None)
        with QSignalBlocker(self.weight_spin):
            self.weight_spin.setValue(slot.weight if slot is not None else 1.0)

    def _weight_changed(self, value: float) -> None:
        slot = self._selected_slot()
        if self.layout is None or slot is None:
            return
        children = list(self.layout.children)
        children[self.slot_list.currentRow()] = replace(slot, weight=value)
        self._commit(replace(self.layout, children=tuple(children)))

    def move_slot(self, source_row: int, destination_row: int) -> None:
        """Reorder the current layout's children (drag-drop state operation)."""

        if self.layout is None:
            return
        children = list(self.layout.children)
        if not (0 <= source_row < len(children) and 0 <= destination_row <= len(children)):
            return
        item = children.pop(source_row)
        children.insert(destination_row, item)
        self._commit(
            LayoutNode(
                schemaVersion=self.layout.schemaVersion,
                id=self.layout.id,
                kind=self.layout.kind,
                children=tuple(children),
                columns=self.layout.columns,
                gap=self.layout.gap,
                rowGap=self.layout.rowGap,
                alignment=self.layout.alignment,
                keepTogether=self.layout.keepTogether,
                fallback=self.layout.fallback,
            )
        )

    def _on_slots_moved(self, *_args: object) -> None:
        if self.layout is None:
            return
        order: list[int] = []
        for index in range(self.slot_list.count()):
            text = self.slot_list.item(index).text()
            for child_index, child in enumerate(self.layout.children):
                if getattr(child, "instanceId", "") == text.split(" -> ")[0]:
                    order.append(child_index)
                    break
        if order and order != list(range(len(order))):
            children = [self.layout.children[index] for index in order]
            self._commit(
                LayoutNode(
                    schemaVersion=self.layout.schemaVersion,
                    id=self.layout.id,
                    kind=self.layout.kind,
                    children=tuple(children),
                    columns=self.layout.columns,
                    gap=self.layout.gap,
                    rowGap=self.layout.rowGap,
                    alignment=self.layout.alignment,
                    keepTogether=self.layout.keepTogether,
                    fallback=self.layout.fallback,
                )
            )

    def _inspector_changed(self, field: str) -> None:
        if self.layout is None:
            return
        values = {"gap": Size(value=self.gap_spin.value(), unit="mm"),
                  "alignment": self.alignment_combo.currentText(),
                  "fallback": {**self.layout.fallback, "strategy": self.fallback_combo.currentText()}}
        self._commit(replace(self.layout, **{field: values[field]}))
