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

from app.core.citation_health import check_citations
from app.gui.main_window import MainWindow
from tests.test_gui_editor import isolated_settings


class CitationHealthGuiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-citation-gui-")
        self.addCleanup(self.temp.cleanup)
        self.scope = Path(self.temp.name).resolve()
        self.root = self.scope / "main.tex"
        self.child = self.scope / "child.tex"
        self.bib = self.scope / "catalog.bib"
        self.root.write_text("\\documentclass{article}\n\\begin{document}\n\\input{child}\n"
                             "\\bibliography{catalog}\n\\end{document}\n")
        self.child.write_text("% !TeX root = main.tex\n\\cite[see]{Known,Missing}\n")
        self.bib.write_text("@article{Known,title={Synthetic}}\n@book{Unused,title={Unused}}\n")
        self.window = MainWindow(settings_store=isolated_settings())
        self.window.auto_compile_action.setChecked(False)
        self.window.save_debounce_ms = 3600000
        self.window._watch_file = lambda _path: None
        self.window.open_file(self.root)
        self.addCleanup(self.dispose)

    def dispose(self):
        for tab in self.window.tabs.values():
            self.window._cancel_save_timer(tab)
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
        self.window.references_panel.check_button.click()
        self.wait_for(lambda: not self.window.citations.is_busy)
        result = self.window.references_panel.citation_report
        self.assertIsNotNone(result)
        return result

    def test_read_only_cross_file_check_navigates_and_preserves_checked_record(self):
        before = {p: p.read_bytes() for p in self.scope.rglob("*") if p.is_file()}
        with patch.object(self.window, "save_current", side_effect=AssertionError("read-only")), \
                patch.object(self.window, "compile_current", side_effect=AssertionError("read-only")):
            report = self.inspect()
            self.assertTrue(report.complete, report.items)
            row = next(i for i, item in enumerate(report.items) if item.rule == "citation_missing")
            self.window.citations.navigate(row, 0)
            self.assertEqual(self.window.current_tab().path, self.child)
            self.assertEqual(self.window.current_tab().editor.textCursor().blockNumber(), 1)
            self.assertIs(self.window.references_panel.citation_report, report)
            self.app.processEvents()
            self.window.citations.reconcile()
            self.assertIs(self.window.references_panel.citation_report, report)
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertFalse(self.window.compile_authorized_roots)

    def test_bib_draft_is_checked_without_saving_and_edit_invalidates(self):
        self.window.open_file(self.bib)
        bib_tab = self.window.current_tab()
        bib_tab.editor.setPlainText("@book{Missing,title={Draft}}\n@article{Known,title={Known}}")
        self.window.editor_tabs.setCurrentWidget(self.window._tab_for_path(self.root).editor)
        report = self.inspect()
        self.assertFalse(any(item.rule == "citation_missing" for item in report.items))
        self.assertNotIn("Draft", self.bib.read_text())
        bib_tab.editor.insertPlainText("\n ")
        self.assertIsNone(self.window.references_panel.citation_report)

    def test_external_change_and_navigation_recheck_reject_stale_line(self):
        report = self.inspect()
        row = next(i for i, item in enumerate(report.items) if item.rule == "citation_missing")
        self.child.write_text("changed externally")
        self.window.citations.navigate(row, 0)
        self.assertEqual(self.window.current_tab().path, self.root)
        self.assertIsNone(self.window.references_panel.citation_report)
        self.inspect()
        self.window.signals.external_changed.emit(str(self.bib))
        self.assertIsNone(self.window.references_panel.citation_report)

    def test_tab_switch_discards_result_but_typing_never_launches_a_worker(self):
        self.inspect()
        with patch("app.gui.citation_health_controller.check_citations") as worker:
            self.window.open_file(self.child)
            self.assertIsNone(self.window.references_panel.citation_report)
            self.window.current_tab().editor.insertPlainText("change")
            self.app.processEvents()
        worker.assert_not_called()

    def test_cancel_discards_a_late_success_and_keeps_sources_unchanged(self):
        self._late_result("cancel")

    def test_close_discards_a_late_success(self):
        self._late_result("close")

    def _late_result(self, action):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        before = {p: p.read_bytes() for p in (self.root, self.child, self.bib)}

        def blocked(request, cancelled):
            report = check_citations(request)
            entered.set()
            release.wait(4)
            return report

        with patch("app.gui.citation_health_controller.check_citations", blocked):
            self.window.references_panel.check_button.click()
            self.wait_for(entered.is_set)
            if action == "cancel":
                self.window.references_panel.check_cancel_button.click()
            else:
                self.window.close()
            release.set()
            self.wait_for(lambda: not self.window.citations.is_busy)
        self.assertIsNone(self.window.references_panel.citation_report)
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_repeated_refresh_keeps_only_one_active_and_latest_pending(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []

        def blocked(request, cancelled):
            calls.append(request)
            if len(calls) == 1:
                entered.set()
                release.wait(4)
            return check_citations(request)

        with patch("app.gui.citation_health_controller.check_citations", blocked):
            self.window.references_panel.check_button.click()
            self.wait_for(entered.is_set)
            for _ in range(5):
                self.window.references_panel.check_refresh_button.click()
            self.assertEqual(len(calls), 1)
            release.set()
            self.wait_for(lambda: not self.window.citations.is_busy)
        self.assertEqual(len(calls), 2)
        self.assertIsNotNone(self.window.references_panel.citation_report)
