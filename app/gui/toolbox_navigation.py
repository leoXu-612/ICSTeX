from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.gui.icons import icon
from app.gui.theme import COLOR_ACCENT, COLOR_TEXT_MUTED


class ToolboxNavigation(QWidget):
    """Compact vertical navigation for the docked project tools."""

    currentChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("toolboxNavigation")
        self._labels: list[str] = []
        self._buttons: list[QToolButton] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.rail = QWidget()
        self.rail.setObjectName("toolboxRail")
        self.rail.setFixedWidth(72)
        self.rail_layout = QVBoxLayout(self.rail)
        self.rail_layout.setContentsMargins(4, 6, 4, 6)
        self.rail_layout.setSpacing(2)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.idClicked.connect(self.setCurrentIndex)

        self.stack = QStackedWidget()
        self.stack.setObjectName("toolboxStack")
        layout.addWidget(self.rail)
        layout.addWidget(self.stack, 1)

    def addTab(
        self,
        widget: QWidget,
        text: str,
        icon_name: str,
        tooltip: str = "",
        *,
        section_break: bool = False,
    ) -> int:
        if section_break and self._buttons:
            divider = QFrame()
            divider.setObjectName("toolboxDivider")
            divider.setFrameShape(QFrame.Shape.HLine)
            self.rail_layout.addWidget(divider)

        index = self.stack.addWidget(widget)
        button = QToolButton()
        button.setObjectName("toolboxNavButton")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setIcon(icon(icon_name, COLOR_TEXT_MUTED, 18))
        button.setIconSize(QSize(18, 18))
        button.setText(text)
        button.setToolTip(tooltip or text)
        button.setFixedWidth(64)
        button.setMinimumHeight(48)
        self.group.addButton(button, index)
        button.toggled.connect(
            lambda checked, target=button, name=icon_name: target.setIcon(
                icon(name, COLOR_ACCENT if checked else COLOR_TEXT_MUTED, 18)
            )
        )
        self.rail_layout.addWidget(button)
        self._buttons.append(button)
        self._labels.append(text)
        if index == 0:
            button.setChecked(True)
        return index

    def finish(self) -> None:
        self.rail_layout.addStretch(1)

    def count(self) -> int:
        return self.stack.count()

    def currentIndex(self) -> int:
        return self.stack.currentIndex()

    def setCurrentIndex(self, index: int) -> None:
        if not 0 <= index < self.stack.count():
            return
        changed = index != self.stack.currentIndex()
        self.stack.setCurrentIndex(index)
        self._buttons[index].setChecked(True)
        if changed:
            self.currentChanged.emit(index)

    def currentWidget(self) -> QWidget | None:
        return self.stack.currentWidget()

    def widget(self, index: int) -> QWidget | None:
        return self.stack.widget(index) if 0 <= index < self.stack.count() else None

    def tabText(self, index: int) -> str:
        return self._labels[index] if 0 <= index < len(self._labels) else ""

    def setTabToolTip(self, index: int, tooltip: str) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setToolTip(tooltip)

    def navigationButton(self, index: int) -> QToolButton | None:
        return self._buttons[index] if 0 <= index < len(self._buttons) else None
