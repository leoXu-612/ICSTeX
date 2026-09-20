"""Shared spreadsheet keyboard behavior; data ownership stays with callers."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QAbstractItemView, QHeaderView, QTableWidget

from app.core.table_clipboard import format_grid


class TableGrid(QTableWidget):
    pasteRequested = Signal(str)
    clearRequested = Signal()
    undoRequested = Signal()
    redoRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ContiguousSelection)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.AnyKeyPressed)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setDefaultSectionSize(140)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setDefaultSectionSize(30)
        self.setAccessibleName("表格单元格编辑区")

    def copy_selection(self) -> None:
        ranges = self.selectedRanges()
        if not ranges:
            return
        area = ranges[0]
        rows = []
        for row in range(area.topRow(), area.bottomRow() + 1):
            rows.append([self.item(row, col).text() if self.item(row, col) else ""
                         for col in range(area.leftColumn(), area.rightColumn() + 1)])
        QApplication.clipboard().setText(format_grid(rows))

    def keyPressEvent(self, event) -> None:
        # A live cell delegate handles its own text editing shortcuts.
        if self.state() != QAbstractItemView.State.EditingState:
            for key, action in (
                (QKeySequence.StandardKey.Paste, lambda: self.pasteRequested.emit(QApplication.clipboard().text())),
                (QKeySequence.StandardKey.Copy, self.copy_selection),
                (QKeySequence.StandardKey.Cut, lambda: (self.copy_selection(), self.clearRequested.emit())),
                (QKeySequence.StandardKey.Undo, self.undoRequested.emit),
                (QKeySequence.StandardKey.Redo, self.redoRequested.emit),
            ):
                if event.matches(key):
                    action()
                    event.accept()
                    return
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                self.clearRequested.emit()
                event.accept()
                return
        super().keyPressEvent(event)
