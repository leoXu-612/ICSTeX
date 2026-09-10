"""Breakpoints, layout-mode resolution and font-aware control sizing."""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLayout, QSizePolicy, QTabWidget, QWidget

from app.gui.theme.ui_metrics import UiMetrics


class LayoutBreakpoints:
    WIDE = 1100
    MEDIUM = 760


def resolve_layout_mode(width: int) -> str:
    if width >= LayoutBreakpoints.WIDE:
        return "wide"
    if width >= LayoutBreakpoints.MEDIUM:
        return "medium"
    return "narrow"


def update_button_minimum_size(button, metrics: UiMetrics) -> None:
    """Set a button's minimum size from its text + icon at the current font."""
    font_metrics = QFontMetrics(button.font())
    text_width = font_metrics.horizontalAdvance(button.text())
    text_height = font_metrics.height()
    icon_width = button.iconSize().width() if not button.icon().isNull() else 0
    icon_height = button.iconSize().height() if not button.icon().isNull() else 0
    gap = metrics.spacing_sm if icon_width else 0
    minimum_width = text_width + icon_width + gap + 2 * metrics.spacing_md
    minimum_height = max(text_height, icon_height) + 2 * metrics.spacing_sm
    button.setMinimumSize(minimum_width, minimum_height)
    button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)


def configure_tab_bar(tab_widget: QTabWidget) -> None:
    """Tabs scroll/elide instead of shrinking font or height."""
    tab_bar = tab_widget.tabBar()
    tab_bar.setExpanding(False)
    tab_bar.setUsesScrollButtons(True)
    tab_bar.setElideMode(Qt.TextElideMode.ElideRight)


def layout_reflow(widget: QWidget, grid, widgets: list, columns: int) -> None:
    """Place ``widgets`` into ``grid`` in ``columns`` columns (instance-stable)."""
    while grid.count():
        item = grid.takeAt(0)
        child = item.widget()
        if child is not None:
            grid.removeWidget(child)
            child.setParent(widget)
    for index, child in enumerate(widgets):
        row, column = divmod(index, columns)
        grid.addWidget(child, row, column)
    for column in range(columns):
        grid.setColumnStretch(column, 1)


class ButtonFlowLayout(QLayout):
    """Wrap existing buttons without recreating or reparenting focused widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(6)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), measure=True)

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            if not item.isEmpty():
                size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        return size + QSize(left + right, top + bottom)

    def sizeHint(self):
        return self.minimumSize()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, measure=False)

    def _arrange(self, rect, *, measure):
        left, top, right, bottom = self.getContentsMargins()
        bounds = rect.adjusted(left, top, -right, -bottom)
        x, y, row_height = bounds.x(), bounds.y(), 0
        gap = max(0, self.spacing())
        for item in self._items:
            if item.isEmpty():
                continue
            size = item.sizeHint().expandedTo(item.minimumSize())
            if row_height and x + size.width() > bounds.right() + 1:
                x, y, row_height = bounds.x(), y + row_height + gap, 0
            if not measure:
                item.setGeometry(QRect(x, y, size.width(), size.height()))
            x += size.width() + gap
            row_height = max(row_height, size.height())
        return y + row_height - rect.y() + bottom
