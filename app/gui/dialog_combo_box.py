"""Keyboard selection without implicitly confirming a parent dialog."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox


class DialogComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        # Qt can close the popup during ShortcutOverride, then deliver this
        # same Return to the combo. Do not let it activate the dialog default.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()
