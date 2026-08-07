"""Application UI scale manager.

Scale changes recompute the unified ``UiMetrics``/``TypographyMetrics`` from
the *base* font (never from the current scaled font), update toolbar icon
sizes, rebuild the stylesheet, and re-clamp docks/splitters.  Window and
splitter size changes are handled separately by responsive layout code and
never touch the font.
"""
from __future__ import annotations

import os
import sys
import time
from weakref import WeakSet

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QDockWidget, QSplitter, QToolBar, QWidget

from app.gui.theme import stylesheet
from app.gui.theme.ui_metrics import TypographyMetrics, UiMetrics


SCALE_TIERS = (0.90, 1.00, 1.10, 1.25, 1.50)
_PROFILE = os.environ.get("ICSTEX_UI_SCALE_PROFILE") == "1"

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
        self._windows: WeakSet = WeakSet()
        self._stylesheet_cache: dict[tuple[float, float], str] = {}
        self._applied_stylesheet = ""

    def register_window(self, window) -> None:
        if window is not None:
            self._windows.add(window)

    def unregister_window(self, window) -> None:
        self._windows.discard(window)

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
        profile_start = time.perf_counter()

        font = QFont(self._base_font)
        font.setPointSizeF(self._base_point_size * scale)
        self._app.setFont(font)

        t_icons = time.perf_counter()
        icon_size = self._metrics.toolbar_icon_size
        for window in list(self._windows):
            try:
                for toolbar in window.findChildren(QToolBar):
                    toolbar.setIconSize(QSize(icon_size, icon_size))
                refresh_window_metrics(window, self._metrics)
            except RuntimeError:
                # The window was destroyed between iterations.
                self._windows.discard(window)
        t_refresh = time.perf_counter()

        cache_key = (self._metrics.scale, self._metrics.density)
        qss = self._stylesheet_cache.get(cache_key)
        if qss is None:
            qss = stylesheet(self._metrics, self._typography)
            self._stylesheet_cache[cache_key] = qss
        t_build = time.perf_counter()
        if qss != self._applied_stylesheet:
            self._app.setStyleSheet(qss)
            self._applied_stylesheet = qss
        t_apply = time.perf_counter()
        if _PROFILE:
            print(
                "ui-scale: "
                f"scale={scale} windows={len(self._windows)} "
                f"icons+refresh_ms={(t_refresh - t_icons) * 1000:.1f} "
                f"build_ms={(t_build - t_refresh) * 1000:.1f} "
                f"apply_ms={(t_apply - t_build) * 1000:.1f} "
                f"total_ms={(t_apply - profile_start) * 1000:.1f}",
                file=sys.stderr,
            )
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
    diagnostics = window.findChild(QDockWidget, "blockDiagnosticsDock")
    if diagnostics is not None:
        diagnostics.setMinimumHeight(round(120 * metrics.scale))

    for toolbar in window.findChildren(QToolBar):
        toolbar.setMinimumHeight(metrics.control_height)

    # The heavy re-layout pass only runs for visible windows: iterating every
    # widget of every hidden/lingering window makes test suites pathologically
    # slow without any visual benefit.
    if window.isVisible():
        for splitter in window.findChildren(QSplitter):
            clamp_splitter_sizes(splitter)
        layout_getter = getattr(window, "layout", None)
        if callable(layout_getter):
            layout = layout_getter()
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
