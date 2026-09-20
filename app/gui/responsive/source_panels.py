"""Keep the existing source toolbox/console usable in compact windows."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QApplication

from app.gui.theme.ui_metrics import UiMetrics


class SourcePanelController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._active = False
        self._welcome = False
        self._applying = False
        self._compact = None
        self._last_requested = None
        self._wide = {"toolbox": not window.toolbox_dock.isHidden(),
                      "console": not window.bottom_tabs.isHidden()}
        self._toolbox_width = None
        self._console_height = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._arrange)
        for widget in (window, window.toolbox_dock, window.bottom_panel):
            widget.installEventFilter(self)
        window.toolbox_dock.visibilityChanged.connect(self._toolbox_changed)

    def _is_compact(self):
        manager = getattr(QApplication.instance(), "ui_scale_manager", None)
        metrics = manager.metrics if manager is not None else UiMetrics()
        return self.window.width() < max(1200,
            self.window.fontMetrics().horizontalAdvance("M") * 75 + metrics.dock_min_width)

    def eventFilter(self, watched, event):
        if not self._active or self._applying:
            return False
        if watched is self.window and event.type() in (QEvent.Type.Resize, QEvent.Type.FontChange,
                                                        QEvent.Type.StyleChange, QEvent.Type.Show):
            self._timer.start(0)
        elif event.type() == QEvent.Type.Resize and not self._compact and not self._is_compact():
            if watched is self.window.toolbox_dock and not watched.isHidden():
                self._toolbox_width = watched.width()
            elif watched is self.window.bottom_panel and not self.window.bottom_tabs.isHidden():
                self._console_height = watched.height()
        return False

    def set_active(self, active):
        if active == self._active:
            return
        self._active = active
        self._timer.stop()
        if active:
            self._compact = None
            self._arrange()

    def set_welcome(self, welcome):
        if welcome == self._welcome:
            return
        self._welcome = welcome
        self._applying = True
        try:
            self.window.toolbox_dock.setVisible(not welcome and self._wide["toolbox"])
        finally:
            self._applying = False

    def window_state(self):
        """Persist writing preferences, not a temporary welcome-page collapse."""
        if not self._welcome:
            return self.window.saveState()
        dock = self.window.toolbox_dock
        visible = not dock.isHidden()
        self._applying = True
        try:
            dock.setVisible(self._wide["toolbox"])
            return self.window.saveState()
        finally:
            dock.setVisible(visible)
            self._applying = False

    def _focused(self, widget):
        focus = QApplication.focusWidget()
        return focus is not None and (focus is widget or widget.isAncestorOf(focus))

    def _arrange(self):
        if not self._active:
            return
        compact = self._is_compact()
        if compact == self._compact:
            return
        was_compact = self._compact
        self._compact = compact
        if compact:
            if self._focused(self.window.toolbox_dock):
                selected = "toolbox"
            elif self._focused(self.window.bottom_tabs):
                selected = "console"
            else:
                selected = self._last_requested
            visible = {selected} if selected else set()
        else:
            if was_compact:
                # Widening must not close the task the user just opened in
                # compact mode, even if it was absent from the old wide layout.
                if not self.window.toolbox_dock.isHidden():
                    self._wide["toolbox"] = True
                if not self.window.bottom_tabs.isHidden():
                    self._wide["console"] = True
            visible = {key for key, shown in self._wide.items() if shown}
        self._apply(visible, restore_sizes=not compact)

    def _apply(self, visible, *, restore_sizes=False):
        from app.gui.main_window_layout import _set_bottom_panel_collapsed
        window = self.window
        self._applying = True
        try:
            window.toolbox_dock.setVisible("toolbox" in visible)
            _set_bottom_panel_collapsed(window, "console" not in visible)
            if restore_sizes:
                if "toolbox" in visible and self._toolbox_width:
                    window.resizeDocks([window.toolbox_dock], [self._toolbox_width], Qt.Orientation.Horizontal)
                if "console" in visible and self._console_height:
                    total = sum(window.vertical_splitter.sizes())
                    window.vertical_splitter.setSizes([max(1, total - self._console_height), self._console_height])
        finally:
            self._applying = False

    def _toolbox_changed(self, visible):
        if self._applying or not self._active:
            return
        if not visible and not self.window.toolbox_dock.isHidden():
            return
        if not self._compact:
            self._wide["toolbox"] = visible
        elif visible:
            self.set_toolbox(True)

    def set_toolbox(self, visible):
        if self._applying:
            return
        if not self._active:
            self.window.toolbox_dock.setVisible(visible)
            self._wide["toolbox"] = visible
            return
        # A click can arrive before the coalesced resize callback. Interpret
        # it in the actual current width, not the previous layout mode.
        self._arrange()
        if visible:
            self._last_requested = "toolbox"
        if self._compact:
            self._apply({"toolbox"} if visible else
                        ({"console"} if not self.window.bottom_tabs.isHidden() else set()))
        else:
            self._wide["toolbox"] = visible
            self._apply({key for key, shown in self._wide.items() if shown})

    def set_console(self, expanded, *, page=None, error_notice=False):
        if self._applying:
            return
        self._arrange()
        if page is not None:
            self._applying = True
            try:
                self.window.bottom_tabs.setCurrentWidget(page)
            finally:
                self._applying = False
        if expanded and error_notice and self._compact and self._focused(self.window.toolbox_dock):
            self.window.statusBar().showMessage("编译有错误；当前输入保留，可展开控制台查看。", 8000)
            return
        if expanded:
            self._last_requested = "console"
        if self._compact:
            self._apply({"console"} if expanded else
                        ({"toolbox"} if not self.window.toolbox_dock.isHidden() else set()))
        else:
            if not error_notice:
                self._wide["console"] = expanded
            visible = {key for key, shown in self._wide.items() if shown}
            if expanded:
                visible.add("console")
            else:
                visible.discard("console")
            self._apply(visible)
