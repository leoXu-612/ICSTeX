"""One updater per application, with explicit network consent and safe exit."""
from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Callable
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, QProcess, QSettings, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.core.app_updates import (UpdateAvailability, automatic_check_due,
                                   installed_update_availability, other_installed_instances)
from app.gui.update_backends import create_native_updater
from app.gui.update_dialog import AppUpdateDialog


UNAVAILABLE_MESSAGES = {
    "development_build": "当前是源码开发模式，未启用应用内更新。请在带更新器的正式安装包中使用。",
    "not_configured": "此安装包尚未配置更新源与签名公钥，需要手动安装首个带更新器的版本。",
    "invalid_config": "更新配置无效，已停止检查。现有应用仍可正常使用。",
    "wrong_target": "更新配置与当前系统或应用架构不一致，已停止检查。",
    "not_installed": "当前不是可更新的安装位置，请使用正式安装包。",
    "missing_runtime": "此安装包缺少原生更新组件，已停止检查。",
}


@dataclass(eq=False)
class _ShutdownRequest:
    event: threading.Event = field(default_factory=threading.Event)
    active: bool = True
    allowed: bool = False


class AppUpdateController(QObject):
    changed = Signal()
    native_event = Signal(str)
    shutdown_requested = Signal()
    preparation_requested = Signal(object)

    def __init__(self, app: QApplication, *, settings: QSettings | None = None,
                 availability: UpdateAvailability | None = None,
                 backend_factory: Callable = create_native_updater,
                 windows_provider: Callable | None = None,
                 instance_probe: Callable[[], bool] = other_installed_instances,
                 now: Callable[[], float] = time.time) -> None:
        super().__init__(app)
        self.app = app
        self.settings = settings if settings is not None else QSettings("ICSTeX", "ICSTeX")
        self.availability = availability if availability is not None else installed_update_availability()
        self._backend_factory = backend_factory
        self._windows_provider = windows_provider or self._main_windows
        self._instance_probe = instance_probe
        self._now = now
        self._backend = None
        self._dialog: AppUpdateDialog | None = None
        self._closed = False
        self._checking = False
        self._preparing = False
        self._handoff = False
        self._installing = False
        self._prepared_windows: list[tuple[object, bool]] = []
        self._requests: set[_ShutdownRequest] = set()
        self._request_lock = threading.Lock()
        self.message = UNAVAILABLE_MESSAGES.get(self.availability.reason, "可手动检查更新；自动检查默认关闭。")
        self.native_event.connect(self._on_native_event)
        self.shutdown_requested.connect(self._finish_shutdown)
        self.preparation_requested.connect(self._prepare_request)
        self.changed.connect(self._refresh_dialog)
        self.app.aboutToQuit.connect(self.close)
        self._timer = QTimer(self)
        self._timer.setInterval(60_000)
        self._timer.timeout.connect(self._automatic_tick)
        self._startup_timer = QTimer(self)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.timeout.connect(self._automatic_tick)

    @staticmethod
    def _main_windows() -> list:
        from app.gui.main_window import MainWindow
        app = QApplication.instance()
        registered = set(getattr(app, "_icstex_windows", []))
        return [widget for widget in QApplication.topLevelWidgets() if isinstance(widget, MainWindow)
                and (widget.isVisible() or widget in registered)]

    @property
    def automatic(self) -> bool:
        value = self.settings.value("updates/automatic_checks", False)
        return value is True or str(value).lower() in ("1", "true", "yes")

    def start(self) -> None:
        # No backend is loaded here. Opted-in users get a deferred first check.
        if self.availability.available and self.automatic and not self._closed:
            self._startup_timer.start(30_000)
            self._timer.start()

    def show_dialog(self, parent=None) -> None:
        if self._closed:
            return
        if self._dialog is None:
            # App-owned instead of document-owned: closing a project must not
            # destroy a shared update dialog or native callbacks.
            self._dialog = AppUpdateDialog()
            self._dialog.check_requested.connect(lambda: self.check(user_initiated=True))
            self._dialog.automatic_changed.connect(self.set_automatic)
        self._refresh_dialog()
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    @Slot()
    def _refresh_dialog(self) -> None:
        if self._dialog is None:
            return
        config = self.availability.config
        self._dialog.set_state(
            available=self.availability.available and not self._closed and not self._checking,
            automatic=self.automatic,
            message=self.message,
            source=f"更新源：{urlsplit(config.feed_url).hostname}" if config else "",
            channel=("Beta 通道" if config.channel == "beta" else "稳定通道") if config else "",
        )
        # Consent can still be withdrawn while a native check/download is active.
        self._dialog.automatic.setEnabled(self.availability.available and not self._closed)
        self._dialog.automatic.blockSignals(True)
        self._dialog.automatic.setChecked(self.automatic if self.availability.available else False)
        self._dialog.automatic.blockSignals(False)

    @Slot(bool)
    def set_automatic(self, enabled: bool) -> None:
        if self._closed or not self.availability.available:
            return
        self.settings.setValue("updates/automatic_checks", bool(enabled))
        self.settings.sync()
        self._timer.stop()
        self._startup_timer.stop()
        if enabled:
            self.start()
        self.changed.emit()

    @Slot()
    def _automatic_tick(self) -> None:
        if self._closed or not self.automatic or self._checking or self._handoff:
            return
        if not self._windows_provider() or QApplication.activeModalWidget() is not None:
            return
        try:
            previous = float(self.settings.value("updates/last_attempt", 0))
        except (TypeError, ValueError):
            previous = 0
        if automatic_check_due(previous, self._now()):
            self.check(user_initiated=False)

    def check(self, *, user_initiated: bool) -> None:
        if self._closed or self._checking or self._handoff or not self.availability.available:
            return
        if not user_initiated and not self.automatic:
            return
        try:
            if self._backend is None:
                self._backend = self._backend_factory(
                    self.availability.config, self.availability.library_path,
                    self._native_can_shutdown, self.shutdown_requested.emit, self.native_event.emit)
            self._checking = True
            self.message = "正在检查更新；下载和安装状态将在原生更新窗口中显示。"
            # Persist attempts, including failures, to avoid a retry/network loop.
            self.settings.setValue("updates/last_attempt", self._now())
            self.settings.sync()
            self._backend.check(user_initiated=user_initiated)
        except Exception:
            self._checking = False
            self.message = "更新检查无法启动或连接失败。未安装任何更新，请稍后重试。"
        self.changed.emit()

    @Slot(str)
    def _on_native_event(self, event: str) -> None:
        if self._closed or self._handoff:
            return
        if event == "installing":
            self._installing = True
            return
        if event == "finished" and self._installing:
            # WinSparkle closes its own dialog immediately before its shutdown
            # callback. That dismissal must not revoke our prepared exit.
            return
        messages = {
            "available": "发现可用更新，请在原生更新窗口查看并确认下载。",
            "no_update": "本次未发现可安装的新版本。兼容性详情以原生更新窗口为准。",
            "error": "更新未完成。请查看原生更新窗口的错误信息，现有文档未被关闭。",
            "cancelled": "已取消本次更新，您可以继续编辑。",
        }
        if event in messages:
            self.message = messages[event]
        if event in ("no_update", "error", "cancelled", "finished"):
            self._installing = False
            self._checking = False
            self._release_prepared_windows()
        self.changed.emit()

    def _native_can_shutdown(self) -> bool:
        """Sparkle calls on main thread; WinSparkle calls on a worker thread."""
        try:
            if self._closed:
                return False
            if QThread.currentThread() == self.thread():
                return self._prepare_for_install()
            request = _ShutdownRequest()
            with self._request_lock:
                if self._closed:
                    return False
                self._requests.add(request)
            self.preparation_requested.emit(request)
            request.event.wait(300)
            with self._request_lock:
                request.active = False
                self._requests.discard(request)
                return request.allowed and not self._closed
        except Exception:
            self.native_event.emit("error")
            return False

    @Slot(object)
    def _prepare_request(self, request: _ShutdownRequest) -> None:
        with self._request_lock:
            active = request.active and not self._closed
        if not active:
            request.event.set()
            return
        allowed = False
        try:
            allowed = self._prepare_for_install()
        except Exception:
            self.message = "更新退出检查失败，未授权安装。"
        finally:
            with self._request_lock:
                request.allowed = allowed and request.active and not self._closed
                accepted = request.allowed
                request.event.set()
            if not accepted:
                self._release_prepared_windows()

    def _blocker(self, windows: list) -> str:
        try:
            if self._instance_probe():
                return "另一个 ICSTeX 进程仍在运行。请先保存并退出其他实例，再安装更新。"
        except Exception:
            return "暂时无法确认其他 ICSTeX 实例是否已退出，已停止安装。"
        if any(widget.isVisible() and widget is not self._dialog and isinstance(widget, QDialog)
               for widget in self.app.topLevelWidgets()):
            return "请先确认或关闭当前编辑对话框，再安装更新。"
        for window in windows:
            if getattr(window, "block_session", None) is not None:
                return "请先保存并关闭打开的 Block 项目，再安装更新。"
            if any(manager.is_busy for manager in window.compile_managers.values()):
                return "编译仍在进行，请等待完成或手动停止后再更新。"
            if getattr(getattr(window, "pdf_export", None), "_pending", {}):
                return "PDF 导出尚未完成，请稍后再更新。"
            worker = getattr(getattr(window, "insertions", None), "_drop_worker", None)
            if worker is not None:
                try:
                    if worker.isRunning():
                        return "图片导入尚未完成，请稍后再更新。"
                except RuntimeError:
                    pass  # The finished Qt worker may already have been deleted.
            if any(tab.external_conflict for tab in window.tabs.values()):
                return "存在尚未处理的外部文件冲突。请先确认磁盘与编辑器内容，再更新。"
        for name in ("ocr_manager", "text_ocr_manager"):
            manager = getattr(self.app, name, None)
            if manager is None:
                continue
            process = getattr(manager, "_install_process", None)
            if process is not None and process.state() != QProcess.ProcessState.NotRunning:
                return "本地识别组件正在安装，请完成后再更新。"
            if manager.status().lower() not in ("not_installed", "model_missing", "stopped", "ready", "error"):
                return "本地识别任务仍在运行，请完成或取消后再更新。"
        return ""

    def _prepare_for_install(self) -> bool:
        if self._closed or self._preparing:
            return False
        if self._prepared_windows:
            return True
        windows = list(self._windows_provider())
        if not windows:
            return False
        self._preparing = True
        selected = [(window, window.editor_tabs.currentWidget()) for window in windows]
        try:
            blocker = self._blocker(windows)
            if blocker:
                self._show_blocker(blocker, windows[0])
                return False
            if any(tab.modified or tab.dirty for window in windows for tab in window.tabs.values()):
                choice = QMessageBox.question(
                    windows[0], "保存后更新", "更新需要退出全部 ICSTeX 窗口。是否先保存所有未保存文档？\n"
                    "取消会保留全部窗口，不会安装更新。",
                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Save)
                if choice != QMessageBox.StandardButton.Save:
                    self.message = "已取消安装，全部窗口保持打开。"
                    return False
            for window in windows:
                for tab in tuple(window.tabs.values()):
                    if not (tab.modified or tab.dirty):
                        continue
                    if tab.path is None:
                        window.editor_tabs.setCurrentWidget(tab.editor)
                        saved = window.save_current_as()
                    else:
                        saved = window.flush_pending_save(tab, compile_after_save=False)
                    if not saved:
                        self.message = "文档尚未全部保存，已取消安装；全部窗口保持打开。"
                        return False
            # Dialog event loops above can deliver new worker/conflict events.
            blocker = self._blocker(windows)
            if blocker or any(tab.modified or tab.dirty for window in windows for tab in window.tabs.values()):
                self._show_blocker(blocker or "文档在确认期间发生变化，请检查后重新更新。", windows[0])
                return False
            if set(windows) != set(self._windows_provider()):
                self.message = "窗口列表已变化，请重新确认更新。"
                return False
            self._prepared_windows = [(window, window.isEnabled()) for window in windows]
            for window, _enabled in self._prepared_windows:
                window.setEnabled(False)
                for manager in window.compile_managers.values():
                    manager.cancel_pending()
            self.message = "文档已保存，正在交接原生安装器。"
            return True
        finally:
            for window, widget in selected:
                if widget is not None and window.editor_tabs.indexOf(widget) >= 0:
                    window.editor_tabs.setCurrentWidget(widget)
            self._preparing = False
            self.changed.emit()

    def _show_blocker(self, message: str, parent) -> None:
        self.message = message
        QMessageBox.information(parent, "暂不能安装更新", message)

    def _release_prepared_windows(self) -> None:
        for window, enabled in self._prepared_windows:
            window.setEnabled(enabled)
        self._prepared_windows.clear()

    @Slot()
    def _finish_shutdown(self) -> None:
        if self._closed or not self._prepared_windows or self._handoff:
            return
        self._handoff = True
        self._timer.stop()
        self._startup_timer.stop()
        # Do not bypass MainWindow.closeEvent: it retires compilers, watchers,
        # analysis workers and log bridges. All save decisions have happened.
        previous_quit_policy = self.app.quitOnLastWindowClosed()
        self.app.setQuitOnLastWindowClosed(False)
        if self._dialog is not None:
            self._dialog.close()
        for window, _enabled in tuple(self._prepared_windows):
            if not window.close():
                self._handoff = False
                self.app.setQuitOnLastWindowClosed(previous_quit_policy)
                self._release_prepared_windows()
                self.message = "窗口取消了退出，安装交接未完成。"
                self.changed.emit()
                return
        # Native callbacks return first so Sparkle can finish notifying its helper.
        QTimer.singleShot(0, self.app.quit)

    @Slot()
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._timer.stop()
        self._startup_timer.stop()
        with self._request_lock:
            for request in self._requests:
                request.active = False
                request.allowed = False
                request.event.set()
            self._requests.clear()
        if self._backend is not None:
            self._backend.close()
        if self._dialog is not None:
            self._dialog.close()


def application_updates() -> AppUpdateController:
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("An application is required")
    controller = getattr(app, "_icstex_updates", None)
    if controller is None:
        controller = AppUpdateController(app)
        app._icstex_updates = controller
    return controller
