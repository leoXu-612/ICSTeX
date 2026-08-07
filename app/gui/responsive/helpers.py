"""Breakpoints, layout-mode resolution and font-aware control sizing."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QSizePolicy, QTabWidget, QWidget

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
