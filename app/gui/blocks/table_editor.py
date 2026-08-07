"""Local table editor over TableEditorModel (Sprint 3 GUI milestone).

Cell editing, rectangular paste, row/column operations, and undo/redo all
drive the core TableEditorModel; the widget is a thin projection and never
duplicates table state. Source status (linked/ok/missing/changed) is shown
from SourceStatus.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.table_import import parse_clipboard
from app.core.blocks.table_model import Cell, TableEditorModel


class TableEditor(QWidget):
    model_changed = Signal()

    def __init__(self, model: TableEditorModel, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self.table = QTableWidget(0, 0)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.status_label = QLabel("未链接")

        self.undo_button = QPushButton("撤销")
        self.redo_button = QPushButton("重做")
        self.insert_row_button = QPushButton("插入行")
        self.delete_row_button = QPushButton("删除行")
        self.insert_column_button = QPushButton("插入列")
        self.delete_column_button = QPushButton("删除列")
        self.undo_button.clicked.connect(self.undo)
        self.redo_button.clicked.connect(self.redo)
        self.insert_row_button.clicked.connect(self.insert_row)
        self.delete_row_button.clicked.connect(self.delete_row)
        self.insert_column_button.clicked.connect(self.insert_column)
        self.delete_column_button.clicked.connect(self.delete_column)

        buttons = QHBoxLayout()
        for widget in (
            self.undo_button,
            self.redo_button,
            self.insert_row_button,
            self.delete_row_button,
            self.insert_column_button,
            self.delete_column_button,
        ):
            buttons.addWidget(widget)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self.table)
        layout.addWidget(self.status_label)
        self.refresh()

    def refresh(self) -> None:
        data = self.model.data
        self.table.blockSignals(True)
        self.table.setColumnCount(len(data.columns))
        self.table.setRowCount(max(0, len(data.rows)))
        self.table.setHorizontalHeaderLabels(
            [f"{column.name}（{column.dataType}）" for column in data.columns]
        )
        for row_index, row in enumerate(data.rows):
            for column_index, column in enumerate(data.columns):
                cell = row.cells.get(column.id, Cell())
                item = QTableWidgetItem("" if cell.kind == "empty" else str(cell.value or ""))
                if cell.kind == "number":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_index, column_index, item)
        self.table.blockSignals(False)
        self._update_status()

    def _update_status(self) -> None:
        state = getattr(self.model, "source_state", "ok")
        self.status_label.setText({"ok": "已同步", "changed": "源已变化", "missing": "源缺失"}.get(state, state))

    def undo(self) -> None:
        self.model.undo()
        self.refresh()
        self.model_changed.emit()

    def redo(self) -> None:
        self.model.redo()
        self.refresh()
        self.model_changed.emit()

    def insert_row(self) -> None:
        index = max(0, self.table.currentRow())
        row_id = f"row_{len(self.model.data.rows) + 1:03d}"
        self.model.insert_row(index, row_id)
        self.refresh()
        self.model_changed.emit()

    def delete_row(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.model.data.rows):
            self.model.delete_row(self.model.data.rows[row].id)
            self.refresh()
            self.model_changed.emit()

    def insert_column(self) -> None:
        index = max(0, self.table.currentColumn())
        from app.core.blocks.table_model import ColumnSpec

        self.model.insert_column(index, ColumnSpec(id=f"col_{index + 1}", name=f"列{index + 1}"))
        self.refresh()
        self.model_changed.emit()

    def delete_column(self) -> None:
        column = self.table.currentColumn()
        if 0 <= column < len(self.model.data.columns):
            self.model.delete_column(self.model.data.columns[column].id)
            self.refresh()
            self.model_changed.emit()

    def paste_clipboard_text(self, text: str) -> None:
        parsed = parse_clipboard(text)
        if parsed is None or not parsed.rows:
            return
        top = max(0, self.table.currentRow())
        left = max(0, self.table.currentColumn())
        for row_offset, parsed_row in enumerate(parsed.rows):
            target_row_id = f"row_{top + row_offset + 1:03d}"
            for column_offset, column in enumerate(parsed.columns):
                cell = parsed_row.cells.get(column.id, Cell())
                target_column_id = (
                    self.model.data.columns[left + column_offset].id
                    if left + column_offset < len(self.model.data.columns)
                    else None
                )
                if target_column_id is not None:
                    self.model.set_cell(target_row_id, target_column_id, cell)
        self.refresh()
        self.model_changed.emit()
