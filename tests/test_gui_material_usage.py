import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from app.core.material_usage import check_materials
from app.gui.main_window import MainWindow
from tests.test_gui_editor import isolated_settings


class MaterialUsageGuiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-material-gui-")
        self.addCleanup(self.temp.cleanup)
        self.scope = Path(self.temp.name).resolve()
        self.root, self.child, self.asset = (self.scope / "main.tex", self.scope / "child.tex", self.scope / "plot.png")
        self.root.write_text("\\documentclass{article}\n\\input{child}\n")
        self.child.write_text("% !TeX root = main.tex\n\\includegraphics{plot.png}\n")
        self.asset.write_bytes(b"synthetic image")
        self.window = MainWindow(settings_store=isolated_settings())
        self.window.auto_compile_action.setChecked(False)
        self.window.save_debounce_ms = 3600000
        self.window._watch_file = lambda _path: None
        self.window.open_file(self.root)
        self.addCleanup(self.dispose)

    def dispose(self):
        if self.window is None:
            return
        for tab in self.window.tabs.values():
            self.window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 4
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.002)
        self.assertTrue(predicate())

    def inspect(self):
        self.window.images_panel.check_button.click()
        self.wait_for(lambda: not self.window.materials.is_busy)
        report = self.window.images_panel.material_report
        self.assertIsNotNone(report, self.window.images_panel.check_status.text())
        return report

    def test_check_and_navigation_are_read_only_and_do_not_write_inventory_cache(self):
        before = {path: path.read_bytes() for path in self.scope.rglob("*") if path.is_file()}
        with patch("app.gui.project_panel_controller.AssetIndex.save", side_effect=AssertionError("no cache write")), \
                patch.object(self.window, "save_current", side_effect=AssertionError("read-only")), \
                patch.object(self.window, "compile_current", side_effect=AssertionError("read-only")):
            report = self.inspect()
            self.assertTrue(report.complete, report.items)
            row = next(i for i, item in enumerate(report.items) if item.path == self.asset)
            self.window.materials.navigate(row, 0)
            self.assertEqual(self.window.current_tab().path, self.child)
            self.assertEqual(self.window.current_tab().editor.textCursor().blockNumber(), 1)
            self.window.materials.reconcile()
            self.assertIs(self.window.images_panel.material_report, report)
        self.assertEqual({path: path.read_bytes() for path in self.scope.rglob("*") if path.is_file()}, before)
        self.assertFalse(self.window.compile_authorized_roots)

    def test_noncurrent_draft_removes_disk_use_without_saving(self):
        self.window.open_file(self.child)
        draft = self.window.current_tab()
        draft.editor.setPlainText("% !TeX root = main.tex\nRemoved from draft")
        self.window.editor_tabs.setCurrentWidget(self.window._tab_for_path(self.root).editor)
        report = self.inspect()
        self.assertTrue(any(item.path == self.asset and item.rule == "asset_unused" for item in report.items))
        self.assertIn("includegraphics", self.child.read_text())
        draft.editor.insertPlainText(" more")
        self.assertIsNone(self.window.images_panel.material_report)

    def test_refresh_compares_prior_readable_digest_but_external_change_invalidates_view(self):
        self.inspect()
        self.asset.write_bytes(b"changed bytes")
        self.window.signals.external_changed.emit(str(self.asset))
        self.assertIsNone(self.window.images_panel.material_report)
        report = self.inspect()
        item = next(item for item in report.items if item.path == self.asset)
        self.assertEqual(item.rule, "asset_changed")
        self.assertIsNotNone(item.baseline)

    def test_typing_never_starts_check_or_scans_all_source_usage(self):
        self.window.images_panel.material_tabs.setCurrentIndex(0)
        self.window.show()
        self.window.set_toolbox_visible(True)
        self.window.sidebar_tabs.setCurrentIndex(3)
        self.app.processEvents()
        with patch("app.gui.material_usage_controller.check_materials") as worker, \
                patch("app.core.asset_index._graphics_references", side_effect=AssertionError("typing source scan")):
            self.window.current_tab().editor.insertPlainText("ordinary typing")
            self.wait_for(lambda: not self.window.project_panels._timer.isActive())
        worker.assert_not_called()

    def test_health_tab_refresh_does_not_run_legacy_inventory_scan(self):
        self.inspect()
        with patch("app.gui.project_panel_controller.AssetIndex.scan") as scan:
            self.window.refresh_project_panels()
            self.window.project_panels.reconcile()
        scan.assert_not_called()

    def test_stale_source_line_is_rejected_before_navigation(self):
        report = self.inspect()
        row = next(i for i, item in enumerate(report.items) if item.path == self.asset)
        self.child.write_text("external content")
        self.window.materials.navigate(row, 0)
        self.assertEqual(self.window.current_tab().path, self.root)
        self.assertIsNone(self.window.images_panel.material_report)

    def test_cancel_and_close_discard_late_success(self):
        for action in ("cancel", "close"):
            with self.subTest(action=action):
                entered, release = threading.Event(), threading.Event()
                self.addCleanup(release.set)

                def blocked(request, cancelled):
                    result = check_materials(request)
                    entered.set()
                    release.wait(4)
                    return result

                with patch("app.gui.material_usage_controller.check_materials", blocked):
                    self.window.images_panel.check_button.click()
                    self.wait_for(entered.is_set)
                    if action == "cancel":
                        self.window.images_panel.check_cancel_button.click()
                    else:
                        self.window.close()
                    release.set()
                    self.wait_for(lambda: not self.window.materials.is_busy)
                self.assertIsNone(self.window.images_panel.material_report)

    def test_latest_pending_request_is_bounded(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []

        def blocked(request, cancelled):
            calls.append(request)
            if len(calls) == 1:
                entered.set()
                release.wait(4)
            return check_materials(request)

        with patch("app.gui.material_usage_controller.check_materials", blocked):
            self.window.images_panel.check_button.click()
            self.wait_for(entered.is_set)
            for _ in range(5):
                self.window.images_panel.check_refresh_button.click()
            self.assertEqual(len(calls), 1)
            release.set()
            self.wait_for(lambda: not self.window.materials.is_busy)
        self.assertEqual(len(calls), 2)

