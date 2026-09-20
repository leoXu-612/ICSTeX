"""Widget-scoped keyboard activation for read-only navigation tables."""
from __future__ import annotations

import weakref

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QTableWidget


def enable_table_key_activation(table: QTableWidget) -> None:
    """Emit cellActivated once for Return/Enter on the selected current cell."""
    reference = weakref.ref(table)

    def activate():
        current = reference()
        if current is None:
            return
        index = current.currentIndex()
        if index.isValid() and current.selectionModel().isSelected(index):
            current.cellActivated.emit(index.row(), index.column())

    for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
        shortcut = QShortcut(QKeySequence(key), table)
        shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        shortcut.setAutoRepeat(False)
        shortcut.activated.connect(activate)
