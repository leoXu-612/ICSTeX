"""Application UI scale manager.

Scale changes recompute the unified ``UiMetrics``/``TypographyMetrics`` from
the *base* font (never from the current scaled font), update toolbar icon
sizes and fixed style-rule markers, and re-clamp docks/splitters. Window and
splitter size changes are handled separately by responsive layout code and
never touch the font.
"""
from __future__ import annotations

import os
import sys
import time
from weakref import WeakSet

from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QDockWidget, QSplitter, QToolBar, QWidget
from shiboken6 import isValid

from app.gui.theme import fixed_stylesheet, stylesheet
from app.gui.theme.ui_metrics import SCALE_TIERS, TypographyMetrics, UiMetrics


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
        self._fixed_stylesheet = fixed_stylesheet()

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.Type.Polish and isinstance(watched, QWidget)
                and self._scale in SCALE_TIERS and self._scale != 1.0):
            token = str(round(self._scale * 100))
            if watched.property("icstexUiScale") != token:
                watched.setProperty("icstexUiScale", token)
                watched.style().unpolish(watched)
                watched.style().polish(watched)
        return False

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
        # Default/legacy styles need no per-widget marker. Do not route every
        # application event through Python when the filter has nothing to do.
        self._app.removeEventFilter(self)
        if scale in SCALE_TIERS and scale != 1.0:
            self._app.installEventFilter(self)
        profile_start = time.perf_counter()

        # Font/style events re-enter Python while Qt traverses raw widget
        # pointers. Keep wrappers alive so cyclic GC cannot delete a different
        # Python-owned widget mid-traversal. This local snapshot neither changes
        # GC policy nor retains closed widgets after the synchronous update.
        live_widgets = self._app.allWidgets()
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

        t_build = time.perf_counter()
        if scale in SCALE_TIERS:
            token = str(round(scale * 100))
            for widget in live_widgets:
                if isValid(widget):
                    widget.setProperty("icstexUiScale", token)
            if self._app.styleSheet() != self._fixed_stylesheet:
                self._app.setStyleSheet(self._fixed_stylesheet)
            else:
                # Parents first: their font restoration can affect children.
                for widget in sorted(live_widgets, key=_widget_depth):
                    if isValid(widget):
                        widget.style().unpolish(widget)
                        widget.style().polish(widget)
                        self._app.sendEvent(widget, QEvent(QEvent.Type.StyleChange))
            self._applied_stylesheet = self._fixed_stylesheet
        else:
            # ponytail: non-menu scales keep the legacy path; precompile only new UI tiers.
            cache_key = (self._metrics.scale, self._metrics.density)
            qss = self._stylesheet_cache.get(cache_key)
            if qss is None:
                qss = stylesheet(self._metrics, self._typography)
                self._stylesheet_cache[cache_key] = qss
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
        del live_widgets


def _widget_depth(widget: QWidget) -> int:
    depth = 0
    parent = widget.parentWidget()
    while parent is not None:
        depth += 1
        parent = parent.parentWidget()
    return depth


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
