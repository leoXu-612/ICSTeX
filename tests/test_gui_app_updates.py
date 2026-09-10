from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QSettings
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QMessageBox, QTabWidget, QTextEdit

from app.core.app_updates import UpdateAvailability
from app.gui.app_update_controller import AppUpdateController, _ShutdownRequest
from tests.test_app_updates import update_config


class UpdateTestWindow(QMainWindow):
    def __init__(self, path: Path | None = None):
        super().__init__()
        self.editor_tabs = QTabWidget()
        self.setCentralWidget(self.editor_tabs)
        self.editor = QTextEdit("synthetic document")
        self.editor_tabs.addTab(self.editor, "Synthetic")
        self.tab = SimpleNamespace(editor=self.editor, path=path, modified=False,
                                   dirty=False, external_conflict=False)
        self.tabs = {id(self.editor): self.tab}
        self.compile_managers = {}
        self.block_session = None
        self.pdf_export = SimpleNamespace(_pending={})
        self.insertions = SimpleNamespace()
        self.save_result = True
        self.closed_count = 0
        self.saved_count = 0
        self.show()

    def flush_pending_save(self, tab, *, compile_after_save):
        assert compile_after_save is False
        self.saved_count += 1
        if self.save_result:
            tab.modified = tab.dirty = False
        return self.save_result

    def save_current_as(self):
        return self.flush_pending_save(self.tab, compile_after_save=False)

    def closeEvent(self, event):
        self.closed_count += 1
        event.accept()


class ApplicationUpdateControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.settings = QSettings(str(Path(self.temporary.name) / "updates.ini"), QSettings.Format.IniFormat)
        self.windows = [UpdateTestWindow(Path(self.temporary.name) / "a.tex"),
                        UpdateTestWindow(Path(self.temporary.name) / "b.tex")]
        self.backend = SimpleNamespace(check=Mock(), close=Mock())
        self.factory = Mock(return_value=self.backend)
        self.controller = AppUpdateController(
            self.app, settings=self.settings,
            availability=UpdateAvailability(update_config(), library_path=Path("/fixture/bridge")),
            backend_factory=self.factory, windows_provider=lambda: self.windows, now=lambda: 100000.0)
        self.original_quit = self.app.quitOnLastWindowClosed()

    def tearDown(self):
        self.controller._release_prepared_windows()
        self.controller.close()
        self.controller.deleteLater()
        for window in self.windows:
            window.close()
            window.deleteLater()
        self.app.setQuitOnLastWindowClosed(self.original_quit)
        self.app.processEvents()
        self.temporary.cleanup()

    def test_start_and_show_are_offline_by_default(self):
        self.controller.start()
        self.controller.show_dialog()
        self.app.processEvents()
        self.factory.assert_not_called()
        self.assertFalse(self.controller._timer.isActive())
        self.assertFalse(self.controller._dialog.automatic.isChecked())
        self.assertTrue(self.controller._dialog.check_button.isEnabled())

    def test_manual_check_explicitly_loads_backend_once(self):
        self.controller.check(user_initiated=True)
        self.controller.check(user_initiated=True)
        self.factory.assert_called_once()
        self.assertEqual(self.backend.check.call_count, 2)
        self.backend.check.assert_called_with(user_initiated=True)
        self.assertEqual(float(self.settings.value("updates/last_attempt")), 100000)

    def test_manual_check_can_restore_active_native_progress(self):
        self.controller.show_dialog()
        self.controller.check(user_initiated=True)
        self.assertFalse(self.controller._dialog.isVisible())
        self.controller.show_dialog()
        self.assertTrue(self.controller._dialog.check_button.isEnabled())
        self.assertEqual(self.controller._dialog.check_button.text(), "查看更新进度")
        self.controller._now = lambda: 200000.0
        self.controller._dialog.check_button.click()
        self.assertFalse(self.controller._dialog.isVisible())
        self.assertTrue(self.controller._checking)
        self.assertEqual(self.backend.check.call_count, 2)
        self.assertEqual(float(self.settings.value("updates/last_attempt")), 100000)
        self.controller._on_native_event("cancelled")
        self.assertEqual(self.controller._dialog.check_button.text(), "检查更新")

    def test_progress_focus_failure_keeps_active_session_and_windows(self):
        self.controller.check(user_initiated=True)
        self.backend.check.side_effect = RuntimeError("native window not ready")
        self.controller.check(user_initiated=True)
        self.assertTrue(self.controller._checking)
        self.assertTrue(self.controller._dialog.isVisible())
        self.assertTrue(all(window.isEnabled() for window in self.windows))
        self.assertIn("仍在处理", self.controller.message)

    def test_automatic_check_does_not_reenter_active_session(self):
        self.controller.set_automatic(True)
        self.controller.check(user_initiated=True)
        self.controller.check(user_initiated=False)
        self.backend.check.assert_called_once_with(user_initiated=True)

    def test_opt_in_persists_and_daily_check_is_bounded(self):
        self.controller.set_automatic(True)
        self.assertTrue(self.controller.automatic)
        self.assertTrue(self.controller._startup_timer.isActive())
        self.controller._automatic_tick()
        self.backend.check.assert_called_once_with(user_initiated=False)
        self.controller._on_native_event("no_update")
        self.controller._automatic_tick()
        self.assertEqual(self.backend.check.call_count, 1)
        self.controller.set_automatic(False)
        self.assertFalse(self.controller._timer.isActive())
        self.assertFalse(self.controller._startup_timer.isActive())

    def test_automatic_request_cannot_bypass_consent(self):
        self.controller.check(user_initiated=False)
        self.factory.assert_not_called()

    def test_unavailable_build_never_initializes_backend(self):
        self.controller.availability = UpdateAvailability(None, "not_configured")
        self.controller.set_automatic(True)
        self.controller.check(user_initiated=True)
        self.factory.assert_not_called()
        self.assertFalse(self.controller.automatic)

    def test_failure_is_not_reported_as_latest(self):
        self.factory.side_effect = RuntimeError("synthetic connection failure")
        self.controller.check(user_initiated=True)
        self.assertIn("失败", self.controller.message)
        self.assertNotIn("最新版", self.controller.message)
        self.assertFalse(self.controller._checking)

    def test_save_cancel_leaves_all_windows_open_and_operational(self):
        self.windows[0].tab.modified = True
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
            self.assertFalse(self.controller._prepare_for_install())
        self.assertTrue(all(window.isVisible() and window.isEnabled() for window in self.windows))
        self.assertTrue(self.windows[0].tab.modified)
        self.assertEqual([window.closed_count for window in self.windows], [0, 0])

    def test_later_save_failure_does_not_close_earlier_window(self):
        for window in self.windows:
            window.tab.modified = True
        self.windows[1].save_result = False
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Save):
            self.assertFalse(self.controller._prepare_for_install())
        self.assertEqual([window.saved_count for window in self.windows], [1, 1])
        self.assertEqual([window.closed_count for window in self.windows], [0, 0])
        self.assertTrue(all(window.isEnabled() for window in self.windows))

    def test_real_main_window_save_preserves_cursor_scroll_and_stays_open(self):
        from app.core.settings import AppSettings
        from app.gui.main_window import EditorTab, MainWindow

        for old in self.windows:
            old.close()
            old.deleteLater()
        window = MainWindow(settings_store=AppSettings(self.settings))
        self.windows[:] = [window]
        window.auto_compile_action.setChecked(False)
        window._watch_file = lambda _path: None
        source = Path(self.temporary.name) / "synthetic.tex"
        source.write_text("Original", encoding="utf-8")
        editor = window._make_editor("Original")
        tab = EditorTab(editor=editor, path=source)
        window._add_tab(tab, source.name)
        window.show()
        self.app.processEvents()
        text = "\n".join(f"Synthetic line {index}" for index in range(120))
        editor.setPlainText(text)
        window.documents.cancel_save_timer(tab)
        cursor = editor.textCursor()
        cursor.setPosition(420)
        cursor.setPosition(427, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        editor.verticalScrollBar().setValue(25)
        before = (cursor.position(), cursor.anchor(), editor.verticalScrollBar().value())
        self.assertTrue(tab.modified)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Save):
            self.assertTrue(self.controller._prepare_for_install())
        self.assertEqual(source.read_text(encoding="utf-8"), text)
        self.assertEqual((editor.textCursor().position(), editor.textCursor().anchor(),
                          editor.verticalScrollBar().value()), before)
        self.assertTrue(window.isVisible())
        self.assertFalse(tab.modified or tab.dirty)
        self.assertFalse(window.isEnabled())
        self.controller._on_native_event("error")
        self.assertTrue(window.isEnabled())

    def test_success_freezes_windows_until_native_handoff_or_error(self):
        self.windows[1].tab.modified = True
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Save):
            self.assertTrue(self.controller._prepare_for_install())
        self.assertTrue(all(not window.isEnabled() for window in self.windows))
        self.assertEqual([window.closed_count for window in self.windows], [0, 0])
        self.controller._on_native_event("error")
        self.assertTrue(all(window.isEnabled() for window in self.windows))

    def test_busy_compile_export_block_and_conflict_each_block_install(self):
        window = self.windows[0]
        for apply, restore in (
            (lambda: setattr(window, "compile_managers", {1: SimpleNamespace(is_busy=True)}),
             lambda: setattr(window, "compile_managers", {})),
            (lambda: setattr(window.pdf_export, "_pending", {1: object()}),
             lambda: setattr(window.pdf_export, "_pending", {})),
            (lambda: setattr(window, "block_session", object()),
             lambda: setattr(window, "block_session", None)),
            (lambda: setattr(window.tab, "external_conflict", True),
             lambda: setattr(window.tab, "external_conflict", False)),
        ):
            apply()
            with patch.object(QMessageBox, "information"):
                self.assertFalse(self.controller._prepare_for_install())
            self.assertTrue(window.isEnabled())
            restore()

    def test_open_draft_dialog_blocks_install(self):
        draft = QDialog(self.windows[0])
        draft.show()
        try:
            with patch.object(QMessageBox, "information"):
                self.assertFalse(self.controller._prepare_for_install())
        finally:
            draft.close()

    def test_shutdown_uses_existing_window_close_then_queued_quit(self):
        self.assertTrue(self.controller._prepare_for_install())
        with patch("app.gui.app_update_controller.QTimer.singleShot") as timer:
            self.controller._finish_shutdown()
        self.assertEqual([window.closed_count for window in self.windows], [1, 1])
        timer.assert_called_once()
        self.assertTrue(self.controller._handoff)

    def test_native_shutdown_without_preparation_does_nothing(self):
        self.controller._finish_shutdown()
        self.assertEqual([window.closed_count for window in self.windows], [0, 0])

    def test_cancelled_close_preserves_application_quit_policy(self):
        self.app.setQuitOnLastWindowClosed(False)
        self.assertTrue(self.controller._prepare_for_install())
        with patch.object(self.windows[0], "close", return_value=False):
            self.controller._finish_shutdown()
        self.assertFalse(self.app.quitOnLastWindowClosed())
        self.assertFalse(self.controller._handoff)
        self.assertTrue(all(window.isEnabled() for window in self.windows))

    def test_windows_worker_callback_is_marshaled_to_gui_thread(self):
        result = []
        seen_threads = []
        original = self.controller._prepare_for_install
        def prepare():
            seen_threads.append(threading.current_thread())
            return original()
        self.controller._prepare_for_install = prepare
        worker = threading.Thread(target=lambda: result.append(self.controller._native_can_shutdown()))
        worker.start()
        deadline = time.monotonic() + 2
        while worker.is_alive() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.controller.close() if worker.is_alive() else None
        worker.join(1)
        self.assertEqual(result, [True])
        self.assertEqual(seen_threads, [threading.main_thread()])

    def test_expired_worker_request_cannot_prepare_or_close(self):
        request = _ShutdownRequest(active=False)
        self.controller._prepare_request(request)
        self.assertTrue(request.event.is_set())
        self.assertFalse(request.allowed)
        self.assertFalse(self.controller._prepared_windows)

    def test_closed_controller_ignores_late_callbacks(self):
        self.controller.close()
        message = self.controller.message
        self.controller._on_native_event("available")
        self.assertEqual(self.controller.message, message)
        self.assertFalse(self.controller._native_can_shutdown())

    def test_native_dialog_dismissal_does_not_revoke_successful_install_handoff(self):
        self.assertTrue(self.controller._prepare_for_install())
        self.controller._on_native_event("installing")
        self.controller._on_native_event("finished")
        self.assertEqual(len(self.controller._prepared_windows), 2)
        with patch("app.gui.app_update_controller.QTimer.singleShot"):
            self.controller._finish_shutdown()
        self.assertEqual([window.closed_count for window in self.windows], [1, 1])

    def test_launch_failure_restores_windows_after_installing_event(self):
        self.assertTrue(self.controller._prepare_for_install())
        self.controller._on_native_event("installing")
        self.controller._on_native_event("error")
        self.assertFalse(self.controller._installing)
        self.assertFalse(self.controller._prepared_windows)
        self.assertTrue(all(window.isEnabled() for window in self.windows))

    def test_other_process_or_unknown_process_state_blocks_install(self):
        for probe in (Mock(return_value=True), Mock(side_effect=OSError("process lookup failed"))):
            self.controller._instance_probe = probe
            with patch.object(QMessageBox, "information"):
                self.assertFalse(self.controller._prepare_for_install())
        self.assertEqual([window.closed_count for window in self.windows], [0, 0])
