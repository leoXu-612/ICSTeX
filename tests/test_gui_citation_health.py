import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
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

    def test_quick_library_explains_exact_read_path_without_importing_declared_library(self):
        panel = self.window.references_panel
        source_before, bib_before = self.root.read_bytes(), self.bib.read_bytes()
        nested = self.scope / "bib/references.bib"
        self.window.project_panels._refresh_domains({"references"})
        self.assertEqual(panel.library_path.text(), str(nested))
        self.assertTrue(panel.library_path.isReadOnly())
        self.assertEqual(panel.table.rowCount(), 0)
        self.assertIn("不代表项目没有引用", panel.status_label.text())
        self.assertIn("检查引用", panel.status_label.text())
        self.assertFalse(nested.exists())
        flat = self.scope / "references.bib"
        flat.write_text("@book{Flat,title={Synthetic flat library}}\n")
        self.window.project_panels._refresh_domains({"references"})
        self.assertEqual(panel.library_path.text(), str(flat))
        self.assertEqual(panel.table.item(0, 0).text(), "Flat")
        nested.parent.mkdir()
        nested.write_text("@book{Nested,title={Synthetic nested library}}\n")
        self.window.project_panels._refresh_domains({"references"})
        self.assertEqual(panel.library_path.text(), str(nested))
        self.assertEqual(panel.table.item(0, 0).text(), "Nested")
        self.assertEqual(self.root.read_bytes(), source_before)
        self.assertEqual(self.bib.read_bytes(), bib_before)

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

    def test_preedit_and_cancel_preserve_report_until_actual_commit(self):
        from PySide6.QtGui import QInputMethodEvent
        report = self.inspect()
        editor = self.window.current_tab().editor
        before = {path: path.read_bytes() for path in (self.root, self.child, self.bib)}
        for text in ("zhong", "zhongwen", ""):
            QApplication.sendEvent(editor, QInputMethodEvent(text, []))
            self.window.citations.reconcile()
            self.assertIs(self.window.references_panel.citation_report, report)
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        event = QInputMethodEvent()
        event.setCommitString("\u4e2d\u6587")
        QApplication.sendEvent(editor, event)
        self.assertIsNone(self.window.references_panel.citation_report)

    def test_repeated_report_refresh_repopulates_first_row_detail_and_locations(self):
        report = self.inspect()
        panel = self.window.references_panel
        first = report.items[0]
        self.assertTrue(first.locations)
        for _ in range(2):
            panel.set_citation_report(report, self.scope, "synthetic refresh")
            self.assertIn(panel._CITATION_RULES[first.rule], panel.check_detail.toPlainText())
            self.assertIn(first.key, panel.check_detail.toPlainText())
            self.assertIn("synthetic refresh", panel.check_detail.toPlainText())
            self.assertEqual(panel.check_locations.count(), len(first.locations))
            self.assertTrue(panel.check_locate_button.isEnabled())
            self.assertEqual(panel.health_table.item(0, 0).toolTip(), panel._CITATION_STATES[first.status])

    def test_read_only_health_table_tabs_to_detail_and_location(self):
        self.window.show()
        self.window.set_toolbox_visible(True)
        self.window.sidebar_tabs.setCurrentIndex(7)
        report = self.inspect()
        panel = self.window.references_panel
        missing = next(i for i, item in enumerate(report.items) if item.rule == "citation_missing")
        panel.health_table.setCurrentCell(missing, 0)
        panel.health_table.setFocus(Qt.FocusReason.TabFocusReason)
        self.app.processEvents()
        QTest.keyClick(panel.health_table, Qt.Key.Key_Down)
        self.assertNotEqual(panel.health_table.currentRow(), missing)
        QTest.keyClick(panel.health_table, Qt.Key.Key_Up)
        self.assertEqual(panel.health_table.currentRow(), missing)
        QTest.keyClick(panel.health_table, Qt.Key.Key_Tab)
        self.assertIs(self.app.focusWidget(), panel.check_detail)
        QTest.keyClick(panel.check_detail, Qt.Key.Key_Backtab)
        self.assertIs(self.app.focusWidget(), panel.health_table)
        QTest.keyClick(panel.health_table, Qt.Key.Key_Backtab)
        self.assertIs(self.app.focusWidget(), panel.check_refresh_button)
        QTest.keyClick(panel.check_refresh_button, Qt.Key.Key_Tab)
        QTest.keyClick(panel.health_table, Qt.Key.Key_Tab)
        QTest.keyClick(panel.check_detail, Qt.Key.Key_Tab)
        self.assertIs(self.app.focusWidget(), panel.check_locations)
        QTest.keyClick(panel.check_locations, Qt.Key.Key_Tab)
        self.assertIs(self.app.focusWidget(), panel.check_locate_button)
        QTest.keyClick(panel.check_locate_button, Qt.Key.Key_Space)
        self.assertEqual(self.window.current_tab().path, self.child)
        self.assertEqual(self.window.current_tab().editor.textCursor().blockNumber(), 1)
        self.assertFalse(self.window.compile_authorized_roots)

    def test_read_only_library_table_tabs_to_insert_and_refresh(self):
        self.window.show()
        self.window.set_toolbox_visible(True)
        self.window.sidebar_tabs.setCurrentIndex(7)
        panel = self.window.references_panel
        panel.set_references(["Known", "Unused"])
        panel.table.setCurrentCell(0, 0)
        panel.table.setFocus(Qt.FocusReason.TabFocusReason)
        self.app.processEvents()
        QTest.keyClick(panel.table, Qt.Key.Key_Tab)
        self.assertIs(self.app.focusWidget(), panel.insert_button)
        QTest.keyClick(panel.insert_button, Qt.Key.Key_Backtab)
        self.assertIs(self.app.focusWidget(), panel.table)
        QTest.keyClick(panel.table, Qt.Key.Key_Backtab)
        self.assertIs(self.app.focusWidget(), panel.library_path)
        QTest.keyClick(panel.library_path, Qt.Key.Key_Backtab)
        self.assertIs(self.app.focusWidget(), panel.refresh_button)

    def test_external_change_and_navigation_recheck_reject_stale_line(self):
        self.wait_for(lambda: not self.window.dependencies.is_busy)
        report = self.inspect()
        row = next(i for i, item in enumerate(report.items) if item.rule == "citation_missing")
        changes = []
        self.window.signals.external_changed.connect(changes.append)
        self.child.write_text("changed externally")
        self.window.citations.navigate(row, 0)
        self.assertEqual(self.window.current_tab().path, self.root)
        self.assertIsNone(self.window.references_panel.citation_report)
        # B1 observation and the watcher's queued notification are separate.
        # Request again only after the actual event and its new generation.
        self.wait_for(lambda: str(self.child) in changes and not self.window.dependencies.is_busy)
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

    def test_preedit_preserves_late_report_but_edit_undo_rejects_old_identity(self):
        for action in ("preedit", "edit_undo"):
            with self.subTest(action=action):
                self._late_result(action)

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
            elif action == "close":
                self.window.close()
            else:
                from PySide6.QtGui import QInputMethodEvent
                editor = self.window.current_tab().editor
                if action == "preedit":
                    QApplication.sendEvent(editor, QInputMethodEvent("zhong", []))
                else:
                    editor.blockSignals(True)
                    try:
                        editor.insertPlainText("changed ")
                        editor.undo()
                    finally:
                        editor.blockSignals(False)
                self.window.citations.reconcile()
            release.set()
            self.wait_for(lambda: not self.window.citations.is_busy)
        if action == "preedit":
            self.assertIsNotNone(self.window.references_panel.citation_report)
            QApplication.sendEvent(editor, QInputMethodEvent())
        else:
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

    def test_worker_failure_without_report_stops_monitoring(self):
        with self.assertLogs("app.gui.citation_health_controller", level="ERROR") as logs, \
             patch("app.gui.citation_health_controller.check_citations", side_effect=ValueError("private fixture text")):
            self.window.citations.request()
            self.wait_for(lambda: not self.window.citations.is_busy)
        self.assertIsNone(self.window.references_panel.citation_report)
        self.assertIn("结果未知", self.window.references_panel.check_status.text())
        self.assertFalse(self.window.citations._timer.isActive())
        self.assertIn("ValueError", " ".join(logs.output))
        self.assertNotIn("private fixture text", " ".join(logs.output))

    def test_monitoring_survives_failed_old_owner_and_pending_handoff(self):
        controller = self.window.citations
        def launch(request):
            controller._active, controller._cancelled = request, threading.Event()
        with patch.object(controller, "_launch", side_effect=launch):
            controller.request()
            first = controller._active
            controller.request()
            pending = controller._pending
            self.assertTrue(controller._cancelled.is_set())
            controller._finished(first, None, "failed old request")
            self.assertIs(controller._active, pending)
            self.assertTrue(controller._timer.isActive())
            controller._finished(first, check_citations(first), "")
            self.assertIs(controller._active, pending)
            self.assertIsNone(controller._report)
            controller._finished(pending, check_citations(pending), "")
        self.assertFalse(controller.is_busy)
        self.assertTrue(controller._timer.isActive())
        self.assertIsNotNone(controller._report)
        with patch.object(self.window.dependencies, "generation_for", return_value=controller._key()[-1] + 1):
            controller.reconcile()
        self.assertIsNone(controller._report)
        self.assertFalse(controller._timer.isActive())

    def test_shared_identity_retains_every_original_field_and_revision(self):
        from app.gui.main_window_support import source_check_key
        window = self.window
        before = source_check_key(window, self.root)
        self.assertEqual(tuple(before), (window.selected_project_scope, self.root, id(window.current_tab()),
            window.block_mode_action.isChecked(),
            tuple((tab.path, id(tab.editor), tab.editor.source_revision, tab.modified, tab.dirty,
                   tab.external_conflict) for tab in window.tabs.values()),
            window.dependencies.generation_for(self.root)))
        window.citations._root = window.materials._root = self.root
        self.assertEqual(window.citations._key(), window.materials._key())
        for field in ("modified", "dirty", "external_conflict"):
            tab = window.current_tab()
            with patch.object(tab, field, not getattr(tab, field)):
                self.assertNotEqual(source_check_key(window, self.root), before)
        editor = window.current_tab().editor
        text = editor.toPlainText()
        editor.blockSignals(True)
        try:
            editor.insertPlainText("changed")
            editor.undo()
        finally:
            editor.blockSignals(False)
        self.assertEqual(editor.toPlainText(), text)
        self.assertNotEqual(source_check_key(window, self.root), before)

    def test_worker_signal_error_is_logged_unless_controller_is_closed(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from app.gui import citation_health_controller, material_usage_controller
        for module, checker in ((citation_health_controller, "check_citations"),
                                (material_usage_controller, "check_materials")):
            closed = threading.Event()
            signals = SimpleNamespace(finished=SimpleNamespace(emit=Mock(side_effect=RuntimeError("private signal text"))))
            with patch.object(module, checker, return_value=None), self.assertLogs(module.__name__, level="ERROR") as logs:
                module._run(None, threading.Event(), closed, signals)
            self.assertIn("RuntimeError", " ".join(logs.output))
            self.assertNotIn("private signal text", " ".join(logs.output))
            closed.set()
            with patch.object(module, checker, return_value=None), self.assertNoLogs(module.__name__):
                module._run(None, threading.Event(), closed, signals)
