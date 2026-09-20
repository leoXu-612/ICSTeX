"""Local table editor over TableEditorModel (Sprint 3 GUI milestone).

Cell editing, rectangular paste, row/column operations, and undo/redo all
drive the core TableEditorModel; the widget is a thin projection and never
duplicates table state. Source status (linked/ok/missing/changed) is shown
from SourceStatus.
"""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QPersistentModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QApplication,
    QLineEdit,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.table_import import infer_cell, parse_clipboard_grid
from app.core.blocks.table_model import Cell, ColumnSpec, TableEditorModel
from app.gui.table_grid import TableGrid
from app.gui.responsive.helpers import ButtonFlowLayout


class _CellDelegate(QStyledItemDelegate):
    editor_opened = Signal(object, object)

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            self.editor_opened.emit(editor, QPersistentModelIndex(index))
        return editor


class TableEditor(QWidget):
    model_changed = Signal()
    live_cell_changed = Signal(object)

    def __init__(self, model: TableEditorModel, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self.table = TableGrid()
        self._cell_editor = None
        self._committing_cell = False
        self._cell_delegate = _CellDelegate(self.table)
        self.table.setItemDelegate(self._cell_delegate)
        self._cell_delegate.editor_opened.connect(self._begin_cell_edit)
        self._cell_delegate.closeEditor.connect(self._delegate_closed)
        self.table.itemChanged.connect(self._cell_changed)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.pasteRequested.connect(self.paste_clipboard_text)
        self.table.clearRequested.connect(self.clear_selection)
        self.table.undoRequested.connect(self.undo)
        self.table.redoRequested.connect(self.redo)
        self.status_label = QLabel("未链接")
        self.detail_label = QLabel()
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextFormat(Qt.TextFormat.PlainText)
        self._validation_issue = ""

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
        self.paste_button = QPushButton("粘贴")
        self.paste_button.clicked.connect(lambda: self.paste_clipboard_text(QApplication.clipboard().text()))
        self.clear_button = QPushButton("清空所选")
        self.clear_button.clicked.connect(self.clear_selection)

        buttons = ButtonFlowLayout()
        for widget in (
            self.undo_button,
            self.redo_button,
            self.paste_button,
            self.clear_button,
            self.insert_row_button,
            self.delete_row_button,
            self.insert_column_button,
            self.delete_column_button,
        ):
            buttons.addWidget(widget)

        layout = QVBoxLayout(self)
        hint = QLabel("直接编辑单元格；Tab 移动，复制 / 粘贴支持矩形区域。行列操作与整块粘贴均可撤销。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addLayout(buttons)
        layout.addWidget(self.table)
        layout.addWidget(self.status_label)
        layout.addWidget(self.detail_label)
        self.refresh()

    def _begin_cell_edit(self, editor, index):
        self._cell_editor = editor
        row = self.model.data.rows[index.row()].id
        column = self.model.data.columns[index.column()].id
        initial = str(index.data(Qt.ItemDataRole.EditRole) or "")
        self._cell_payload = {"row": row, "column": column, "initial": initial}
        editor.textEdited.connect(self._live_text_edited)

    def _live_text_edited(self, text):
        if self.sender() is self._cell_editor:
            self.live_cell_changed.emit({**self._cell_payload, "text": text})

    def _delegate_closed(self, editor, _hint):
        self._end_cell_edit(editor)

    def _end_cell_edit(self, editor):
        if self._cell_editor is editor:
            self._cell_editor = None
            self.live_cell_changed.emit(None)

    def commit_pending_edit(self):
        """Finish the existing delegate before Save, Apply or target replacement."""
        if self._cell_editor is None or self._committing_cell:
            return
        self._committing_cell = True
        try:
            # Return queues the delegate's normal commit/close. Finish that
            # existing request before an immediate Save or target switch closes
            # the editor manually; otherwise the queued call uses a stale view.
            # Only this delegate's queued calls are delivered, not GUI events.
            QCoreApplication.sendPostedEvents(self._cell_delegate, QEvent.Type.MetaCall)
            editor = self._cell_editor
            if editor is None:
                return
            self.table.commitData(editor)
            self.table.closeEditor(editor, QAbstractItemDelegate.EndEditHint.NoHint)
            self._end_cell_edit(editor)
        finally:
            self._committing_cell = False

    def resume_cell_draft(self, initial, values):
        """Reopen a recovered live input, without applying it to the table model."""
        self.commit_pending_edit()
        rows = [row.id for row in self.model.data.rows]
        columns = [column.id for column in self.model.data.columns]
        if initial["row"] not in rows or initial["column"] not in columns:
            return False
        row, column = rows.index(initial["row"]), columns.index(initial["column"])
        item = self.table.item(row, column)
        if item is None or str(item.data(Qt.ItemDataRole.EditRole) or "") != initial["text"]:
            return False
        self.table.setCurrentCell(row, column)
        self.table.editItem(item)
        if self._cell_editor is None:
            return False
        self._cell_editor.setText(values["text"])
        self.live_cell_changed.emit({**self._cell_payload, "text": values["text"]})
        self._cell_editor.setFocus()
        return True

    def refresh(self) -> None:
        self.commit_pending_edit()
        data = self.model.data
        current = (self.table.currentRow(), self.table.currentColumn())
        scroll = (self.table.horizontalScrollBar().value(), self.table.verticalScrollBar().value())
        self.table.blockSignals(True)
        self.table.setColumnCount(len(data.columns))
        self.table.setRowCount(max(0, len(data.rows)))
        self.table.setHorizontalHeaderLabels(
            [f"{column.name}（{column.dataType}）" for column in data.columns]
        )
        for row_index, row in enumerate(data.rows):
            for column_index, column in enumerate(data.columns):
                cell = row.cells.get(column.id, Cell())
                item = QTableWidgetItem("" if cell.kind == "empty" or cell.value is None else str(cell.value))
                if cell.kind == "number":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_index, column_index, item)
        if data.rows and data.columns:
            self.table.setCurrentCell(max(0, min(current[0], len(data.rows) - 1)), max(0, min(current[1], len(data.columns) - 1)))
        self.table.blockSignals(False)
        self.table.horizontalScrollBar().setValue(scroll[0])
        self.table.verticalScrollBar().setValue(scroll[1])
        self._update_status()
        self._update_actions(validate=True)

    def _update_actions(self, *, validate: bool = False) -> None:
        self.undo_button.setEnabled(self.model.can_undo)
        self.redo_button.setEnabled(self.model.can_redo)
        self.delete_row_button.setEnabled(self.table.currentRow() >= 0)
        self.delete_column_button.setEnabled(self.table.currentColumn() >= 0)
        self.clear_button.setEnabled(bool(self.table.selectedItems()))
        if validate:
            issues = self.model.data.validate()
            self._validation_issue = issues[0] if issues else ""
        summary = f"{len(self.model.data.rows)} 行 · {len(self.model.data.columns)} 列"
        self.detail_label.setText(summary + (" · " + self._validation_issue if self._validation_issue else ""))

    def _cell_changed(self, item: QTableWidgetItem) -> None:
        row = self.model.data.rows[item.row()]
        column = self.model.data.columns[item.column()]
        cell = Cell(kind="latex", value=item.text()) if column.dataType == "latex" and item.text() else infer_cell(item.text())
        if self.model.data.cell(row.id, column.id) == cell:
            return
        self.model.set_cell(row.id, column.id, cell)
        self._update_actions(validate=True)
        self.model_changed.emit()

    def _update_status(self) -> None:
        state = getattr(self.model, "source_state", None)
        self.status_label.setText({None: "本地表格（未链接外部数据）", "ok": "已同步", "changed": "源已变化", "missing": "源缺失"}.get(state, state))

    def undo(self) -> None:
        self.commit_pending_edit()
        if not self.model.can_undo:
            return
        self.model.undo()
        self.refresh()
        self.model_changed.emit()

    def redo(self) -> None:
        self.commit_pending_edit()
        if not self.model.can_redo:
            return
        self.model.redo()
        self.refresh()
        self.model_changed.emit()

    def insert_row(self) -> None:
        self.commit_pending_edit()
        index = max(0, self.table.currentRow())
        row_id = self.model.next_row_id()
        self.model.insert_row(index, row_id)
        self.refresh()
        if self.model.data.columns:
            self.table.setCurrentCell(index, max(0, self.table.currentColumn()))
        self.model_changed.emit()

    def delete_row(self) -> None:
        self.commit_pending_edit()
        rows = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        if not rows and self.table.currentRow() >= 0:
            rows = [self.table.currentRow()]
        if rows:
            with self.model.batch_edit():
                for row in rows:
                    self.model.delete_row(self.model.data.rows[row].id)
            self.refresh()
            self.model_changed.emit()

    def insert_column(self) -> None:
        self.commit_pending_edit()
        index = max(0, self.table.currentColumn())
        column_id = self.model.next_column_id()
        self.model.insert_column(index, ColumnSpec(id=column_id, name=f"列{column_id.removeprefix('col_')}"))
        self.refresh()
        if self.model.data.rows:
            self.table.setCurrentCell(max(0, self.table.currentRow()), index)
        self.model_changed.emit()

    def delete_column(self) -> None:
        self.commit_pending_edit()
        columns = sorted({item.column() for item in self.table.selectedItems()}, reverse=True)
        if not columns and self.table.currentColumn() >= 0:
            columns = [self.table.currentColumn()]
        if columns:
            with self.model.batch_edit():
                for column in columns:
                    self.model.delete_column(self.model.data.columns[column].id)
            self.refresh()
            self.model_changed.emit()

    def paste_clipboard_text(self, text: str) -> None:
        self.commit_pending_edit()
        top = max(0, self.table.currentRow())
        left = max(0, self.table.currentColumn())
        try:
            grid = parse_clipboard_grid(text, max_rows=5000 - top, max_columns=200 - left)
        except ValueError:
            self.detail_label.setText("未粘贴：数据格式无效，或超过 5000 行、200 列、10 万格的限制；原数据不变。")
            return
        if not grid:
            return
        with self.model.batch_edit():
            while len(self.model.data.rows) < top + len(grid):
                self.model.insert_row(len(self.model.data.rows), self.model.next_row_id())
            while len(self.model.data.columns) < left + len(grid[0]):
                column_id = self.model.next_column_id()
                self.model.insert_column(len(self.model.data.columns), ColumnSpec(id=column_id, name=f"列{column_id.removeprefix('col_')}"))
            for row, cells in enumerate(grid, top):
                for column, value in enumerate(cells, left):
                    spec = self.model.data.columns[column]
                    cell = Cell(kind="latex", value=value) if spec.dataType == "latex" and value else infer_cell(value)
                    self.model.set_cell(self.model.data.rows[row].id, spec.id, cell)
        self.refresh()
        self.table.setCurrentCell(top, left)
        self.model_changed.emit()

    def clear_selection(self) -> None:
        self.commit_pending_edit()
        if not self.table.selectedItems():
            return
        with self.model.batch_edit():
            for item in self.table.selectedItems():
                row = self.model.data.rows[item.row()]
                column = self.model.data.columns[item.column()]
                self.model.set_cell(row.id, column.id, Cell())
        self.refresh()
        self.model_changed.emit()
