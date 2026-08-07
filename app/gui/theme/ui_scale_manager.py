"""Application UI scale manager.

Scale changes recompute the unified ``UiMetrics``/``TypographyMetrics`` from
the *base* font (never from the current scaled font), update toolbar icon
sizes, rebuild the stylesheet, and re-clamp docks/splitters.  Window and
splitter size changes are handled separately by responsive layout code and
never touch the font.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QDockWidget, QSplitter, QToolBar, QWidget

from app.gui.theme import stylesheet
from app.gui.theme.ui_metrics import TypographyMetrics, UiMetrics


SCALE_TIERS = (0.90, 1.00, 1.10, 1.25, 1.50)

TIER_LABELS: dict[float, str] = {
    0.90: "紧凑 90%",
    1.00: "默认 100%",
    1.10: "舒适 110%",
    1.25: "较大 125%",
    1.50: "特大 150%",
}


class UiScaleManager(QObject):
    scale_changed = Signal(float)

    MIN_SCALE = 0.90
    MAX_SCALE = 1.50

    def __init__(self, app: QApplication, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._app = app
        self._base_font = QFont(app.font())
        self._base_point_size = max(1.0, self._base_font.pointSizeF())
        self._scale = 1.0
        self._metrics = UiMetrics(1.0)
        self._typography = TypographyMetrics(1.0)

    @property
    def scale(self) -> float:
        return self._scale

    @property
    def metrics(self) -> UiMetrics:
        return self._metrics

    @property
    def typography(self) -> TypographyMetrics:
        return self._typography

    def apply_scale(self, scale: float) -> None:
        scale = max(self.MIN_SCALE, min(float(scale), self.MAX_SCALE))
        if abs(scale - self._scale) < 0.001:
            return
        self._scale = scale
        self._metrics = UiMetrics(scale)
        self._typography = TypographyMetrics(scale)

        font = QFont(self._base_font)
        font.setPointSizeF(self._base_point_size * scale)
        self._app.setFont(font)

        icon_size = self._metrics.toolbar_icon_size
        for window in self._app.topLevelWidgets():
            for toolbar in window.findChildren(QToolBar):
                toolbar.setIconSize(QSize(icon_size, icon_size))
            refresh_window_metrics(window, self._metrics)

        self._app.setStyleSheet(stylesheet(self._metrics, self._typography))
        self.scale_changed.emit(scale)


def refresh_window_metrics(window: QWidget, metrics: UiMetrics) -> None:
    """Re-apply metric-derived constraints after a scale change."""
    dock_minima = {
        "toolboxDock": metrics.dock_min_width,
        "blockNavDock": metrics.dock_min_width,
        "blockInspectorDock": metrics.inspector_min_width,
    }
    for object_name, minimum in dock_minima.items():
        dock = window.findChild(QDockWidget, object_name)
        if dock is not None:
            dock.setMinimumWidth(minimum)

    for toolbar in window.findChildren(QToolBar):
        toolbar.setMinimumHeight(metrics.control_height)

    for splitter in window.findChildren(QSplitter):
        clamp_splitter_sizes(splitter)

    for widget in window.findChildren(QWidget):
        layout = widget.layout()
        if layout is not None:
            layout.invalidate()
            layout.activate()
    window.updateGeometry()


def clamp_splitter_sizes(splitter: QSplitter) -> None:
    """Clamp pane sizes to their minimum hints and redistribute the rest."""
    sizes = splitter.sizes()
    if not sizes:
        return
    total = max(1, sum(sizes))
    horizontal = splitter.orientation() == Qt.Orientation.Horizontal
    minimums: list[int] = []
    for index in range(splitter.count()):
        widget = splitter.widget(index)
        hint = widget.minimumSizeHint()
        minimums.append(max(1, hint.width() if horizontal else hint.height()))
    corrected = [max(size, minimum) for size, minimum in zip(sizes, minimums)]
    if sum(corrected) <= total:
        corrected[-1] += total - sum(corrected)
        splitter.setSizes(corrected)
