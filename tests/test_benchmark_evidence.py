"""Diagnostic probes must retain failure evidence without claiming completion."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QEvent, QObject, Signal
from PySide6.QtPdf import QPdfDocument
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QWidget

from tools import bench_pdf_pipeline as probe
from tools.bench_dependency_membership import sample_summary
from tools.bench_writing_latency import WritingPaintProbe


class DocumentStub(QObject):
    statusChanged = Signal(object)
    viewChanged = Signal(object)

    def status(self):
        return QPdfDocument.Status.Ready

    def pageCount(self):
        return 2


class ProbeEvidenceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_probe(self):
        window = QWidget()
        viewport = QWidget(window)
        document = DocumentStub(window)
        window.pdf_panel = SimpleNamespace(_view=SimpleNamespace(viewport=lambda: viewport),
            _document=document, current_pdf=Path("/synthetic/main.pdf"), viewChanged=document.viewChanged)
        window.current_tab = lambda: None
        observed = probe.PaintProbe(window, None)
        self.addCleanup(window.deleteLater)
        return window, viewport, observed

    def setUp(self):
        self.addCleanup(self.app.setQuitOnLastWindowClosed, self.app.quitOnLastWindowClosed())

    def test_percentile_requires_thirty_samples_and_retains_failures(self):
        self.assertIsNone(sample_summary([1, 2, 3])["p95_ms"])
        values = list(range(1, 30)) + [90]
        self.assertEqual(sample_summary(values), {
            "count": 30, "p50_ms": 15.5, "p95_ms": 29, "max_ms": 90, "over_50_ms": 1})

    def test_new_case_does_not_inherit_ready_or_visible_evidence(self):
        _, _, observed = self.make_probe()
        observed.reset("first")
        observed.status_changed(QPdfDocument.Status.Ready)
        observed.events["visible_content_observed"] = 1
        observed.reset("second")
        self.assertIsNone(observed.ready_state)
        self.assertEqual(set(observed.events), {"request"})
        self.assertEqual(list(observed.transitions), [])
        self.assertEqual(observed.start_state["case"], "second")

    def test_window_paint_is_not_pdf_viewport_paint(self):
        window, viewport, observed = self.make_probe()
        observed.reset("case")
        observed.status_changed(QPdfDocument.Status.Ready)
        with patch.object(probe.QTimer, "singleShot") as scheduled:
            observed.eventFilter(window, QEvent(QEvent.Type.Paint))
            self.assertNotIn("first_paint_event", observed.events)
            scheduled.assert_not_called()
            observed.eventFilter(viewport, QEvent(QEvent.Type.Paint))
            self.assertIn("first_paint_event", observed.events)
            scheduled.assert_called_once()
            self.assertIs(scheduled.call_args.args[1], observed)

    def test_transition_history_is_bounded(self):
        window, _, observed = self.make_probe()
        observed.reset("case")
        for _ in range(100):
            observed.eventFilter(window, QEvent(QEvent.Type.Show))
        self.assertEqual(len(observed.transitions), 64)

    def test_failed_run_keeps_prior_samples_and_remains_failed(self):
        with TemporaryDirectory() as folder:
            output = Path(folder) / "evidence.json"

            def fail(root, screenshots, *, reports):
                reports.append({"case": "completed-first-case"})
                raise AssertionError("synthetic visible-content failure")

            with patch.object(probe.sys, "argv", ["probe", "--output", str(output)]), \
                 patch.object(probe, "source_digest", return_value="source-identity"), \
                 patch.object(probe, "make_project", side_effect=lambda root: (root / "main.tex", {})), \
                 patch.object(probe, "image_probe", return_value={}), \
                 patch.object(probe, "visible_probe", side_effect=fail):
                with self.assertRaisesRegex(AssertionError, "visible-content failure"):
                    probe.main()
            report = json.loads(output.read_text())
            self.assertFalse(report["completed"])
            self.assertFalse(report["trials"][0]["completed"])
            self.assertEqual(report["trials"][0]["visible_pdf"], [{"case": "completed-first-case"}])
            self.assertNotIn("closed_window_destroyed", report["trials"][0])
            self.assertEqual(report["failure"]["type"], "AssertionError")
            self.assertTrue(report["app_hash_matches_after_run"])

    def test_existing_evidence_is_not_overwritten(self):
        with TemporaryDirectory() as folder:
            output = Path(folder) / "evidence.json"
            output.write_bytes(b"original evidence")
            with patch.object(probe.sys, "argv", ["probe", "--output", str(output)]):
                with self.assertRaises(SystemExit):
                    probe.main()
            self.assertEqual(output.read_bytes(), b"original evidence")

    def test_writing_observer_rejects_caret_only_and_accepts_changed_text(self):
        editor = QPlainTextEdit("A distinct synthetic baseline with enough text to observe shifting glyphs.")
        editor.resize(800, 200)
        editor.current_tab = lambda: SimpleNamespace(editor=editor)
        self.addCleanup(editor.deleteLater)
        editor.show()
        self.app.processEvents()
        editor.moveCursor(QTextCursor.MoveOperation.Start)
        observer = WritingPaintProbe(editor)
        observer.start()
        editor.moveCursor(QTextCursor.MoveOperation.Right)
        self.app.processEvents()
        observer.observe()
        self.assertNotIn("visible_change", observer.events)
        observer.start()
        editor.insertPlainText("x")
        self.app.processEvents()
        observer.observe()
        self.assertIn("visible_change", observer.events)
        editor.close()
