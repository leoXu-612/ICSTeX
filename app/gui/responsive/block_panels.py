"""Present existing Block docks without changing their widgets or session state."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QApplication

from app.gui.theme.ui_metrics import UiMetrics


class BlockPanelController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.docks = {"navigation": window.block_nav_dock,
                      "inspector": window.block_inspector_dock,
                      "diagnostics": window.block_diagnostics_dock,
                      "submission": window.readiness._block_dock}
        settings = window.app_settings.settings
        self._wide_visible = {"navigation": True, "inspector": False,
                              "diagnostics": False, "submission": False}
        saved = settings.value("window/block_panel_visibility", {})
        if isinstance(saved, dict):
            self._wide_visible.update({key: bool(value) for key, value in saved.items() if key in self.docks})
        saved_sizes = settings.value("window/block_panel_sizes", {})
        self._wide_sizes = saved_sizes if isinstance(saved_sizes, dict) else {}
        self._compact_selected = settings.value("window/block_compact_panel", "")
        self._compact_preference = self._compact_selected
        self._temporary_notice = False
        self._active = False
        self._compact = None
        self._applying = False
        self._source_toolbox_visible = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._arrange)
        window.installEventFilter(self)
        for key, dock in self.docks.items():
            dock.hide()
            dock.toggleViewAction().setEnabled(False)
            dock.installEventFilter(self)
            dock.visibilityChanged.connect(lambda visible, key=key: self._visibility_changed(key, visible))

    def _is_compact(self):
        manager = getattr(QApplication.instance(), "ui_scale_manager", None)
        metrics = manager.metrics if manager is not None else UiMetrics()
        canvas = max(720, self.window.fontMetrics().horizontalAdvance("M") * 60)
        return self.window.width() < metrics.dock_min_width + metrics.inspector_min_width + canvas

    def eventFilter(self, watched, event):
        if not self._active or self._applying:
            return False
        if watched is self.window and event.type() in (QEvent.Type.Resize, QEvent.Type.FontChange,
                                                        QEvent.Type.StyleChange, QEvent.Type.Show):
            self._timer.start(0)
        elif event.type() == QEvent.Type.Resize and not self._compact and not self._is_compact():
            for key, dock in self.docks.items():
                if watched is dock and not dock.isHidden():
                    self._wide_sizes[key] = dock.width() if key in ("navigation", "inspector") else dock.height()
                    break
        return False

    def set_active(self, active):
        if self._active == active:
            return
        self._timer.stop()
        self._active = active
        for dock in self.docks.values():
            dock.toggleViewAction().setEnabled(active)
        if active:
            self._source_toolbox_visible = not self.window.toolbox_dock.isHidden()
            self.window.toolbox_dock.hide()
            self._compact = None
            self._arrange()
        else:
            self._apply(set())
            if self._temporary_notice:
                self._compact_selected = self._compact_preference
                self._temporary_notice = False
            self.window.toolbox_dock.setVisible(self._source_toolbox_visible)

    def _focused_panel(self):
        focus = QApplication.focusWidget()
        return next((key for key, dock in self.docks.items()
                     if focus is not None and (focus is dock or dock.isAncestorOf(focus))), "")

    def _arrange(self):
        if not self._active:
            return
        compact = self._is_compact()
        if compact == self._compact:
            return
        was_compact = self._compact
        if compact:
            focused = self._focused_panel()
            if focused:
                self._compact_selected = focused
        self._compact = compact
        visible = ({self._compact_selected} if compact else
                   {key for key, shown in self._wide_visible.items() if shown})
        if not compact and was_compact and self._compact_selected in self.docks:
            selected = self._compact_selected
            if not self.docks[selected].isHidden():
                visible.add(selected)
                if not self._temporary_notice:
                    self._wide_visible[selected] = True
        self._apply(visible, restore_sizes=not compact)

    def _apply(self, visible, *, restore_sizes=False):
        self._applying = True
        try:
            # Show before hiding so an explicit panel change has a live target.
            for key, dock in self.docks.items():
                if key in visible:
                    dock.show()
            for key, dock in self.docks.items():
                if key not in visible:
                    dock.hide()
            if restore_sizes:
                for key in visible:
                    size = self._wide_sizes.get(key)
                    if isinstance(size, int) and size > 0:
                        orientation = Qt.Orientation.Horizontal if key in ("navigation", "inspector") else Qt.Orientation.Vertical
                        self.window.resizeDocks([self.docks[key]], [size], orientation)
        finally:
            self._applying = False

    def _visibility_changed(self, key, visible):
        if self._applying or not self._active:
            return
        # An ancestor window hiding is not a user's panel preference.
        if not visible and not self.docks[key].isHidden():
            return
        if self._compact:
            if visible:
                self._compact_selected = key
                self._apply({key})
            elif self._compact_selected == key:
                self._compact_selected = ""
            self._compact_preference = self._compact_selected
        else:
            self._wide_visible[key] = visible
        self._temporary_notice = False

    def request(self, key, *, error_notice=False):
        if not self._active:
            return
        if error_notice and self._compact and self._focused_panel() not in ("", key):
            self.window.statusBar().showMessage("Block 有错误；当前输入保留，可从项目导航打开诊断。", 8000)
            return
        if self._compact:
            self._compact_selected = key
            if not error_notice:
                self._compact_preference = key
            self._apply({key})
        else:
            if not error_notice:
                self._wide_visible[key] = True
            self._apply({name for name, shown in self._wide_visible.items() if shown} | {key})
        self._temporary_notice = error_notice

    def save_preferences(self):
        settings = self.window.app_settings.settings
        settings.setValue("window/block_panel_visibility", self._wide_visible)
        settings.setValue("window/block_panel_sizes", self._wide_sizes)
        settings.setValue("window/block_compact_panel", self._compact_preference)
