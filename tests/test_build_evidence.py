from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
from unittest import TestCase
from unittest.mock import patch

from app.core.build_evidence import capture_compile_inputs, finish_compile_inputs, final_build_evidence
from app.core.compiler import BuildPurpose, CompileManager, CompileOutcome
from app.core.latex_tools import LaTeXEngine, LaTeXToolchain
from app.core.log_parser import parse_reference_warnings
from app.core.pdf_state import PdfBuildRecord, PdfFreshness
from app.core.submission_check import CheckStatus, check_submission
from tests.test_submission_check import by_rule, request_for
from tests.v1_fixtures import create_project


class BuildEvidenceTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.sample = create_project(self.base)
        self.root = self.sample.root

    def test_before_after_detects_changed_removed_and_newly_recorded_inputs(self):
        before = capture_compile_inputs(self.root, self.root.parent)
        self.assertTrue(finish_compile_inputs(before, self.root, self.root.parent, (), None).stable)
        dynamic = self.root.parent / "data.csv"
        dynamic.write_bytes(b"value\n1\n")
        self.assertFalse(finish_compile_inputs(before, self.root, self.root.parent, (dynamic,), None).stable)
        before = capture_compile_inputs(self.root, self.root.parent, (dynamic,))
        self.assertTrue(finish_compile_inputs(before, self.root, self.root.parent, (dynamic,), None).stable)
        dynamic.unlink()
        self.assertFalse(finish_compile_inputs(before, self.root, self.root.parent, (), None).stable)
        before = capture_compile_inputs(self.root, self.root.parent)
        self.sample.draft_path.write_text(self.sample.conflict_text)
        self.assertFalse(finish_compile_inputs(before, self.root, self.root.parent, (), None).stable)

    def test_compiler_captures_job_inputs_pdf_and_log_before_completion_callback(self):
        manager = CompileManager(self.root, toolchain=LaTeXToolchain(None, "/bin/fixture"),
                                 engine=LaTeXEngine.PDFLATEX)
        manager.set_input_revision(7, 3)
        class Process:
            returncode = 0
            def communicate(inner, timeout=None):
                manager.pdf_file.write_bytes(b"%PDF-1.4 synthetic")
                manager.log_file.write_text("LaTeX Warning: Citation `dynamic' on page 1 undefined on input line 4.\n\n")
                return "", ""
        manager.on_finished = lambda result: manager.pdf_file.write_bytes(b"%PDF changed after capture")
        with patch("app.core.compiler.subprocess.Popen", return_value=Process()):
            result = manager.compile_now()
        evidence = final_build_evidence(result)
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.job_key.source_revision, 7)
        self.assertEqual(evidence.job_key.dependency_generation, 3)
        self.assertTrue(evidence.inputs.stable)
        self.assertTrue(evidence.log_complete)
        self.assertEqual(len(evidence.warnings), 1)
        self.assertIsNone(evidence.warnings[0].file, "do not invent included-file ownership from line alone")
        record = PdfBuildRecord(self.root, PdfFreshness.CURRENT, manager.pdf_file, 7, 7, 7, result.build_id)
        req = replace(request_for(self.sample, final=record), build_evidence=evidence,
                      tools=manager.toolchain, source_revision=7)
        report = check_submission(req)
        self.assertEqual(by_rule(report, "pdf_current")[0].status, CheckStatus.FAIL)
        self.assertEqual(by_rule(report, "final_log")[0].status, CheckStatus.FAIL)
        self.assertIsNone(final_build_evidence(replace(result, purpose=BuildPurpose.PREVIEW)))

    def test_input_change_during_actual_job_makes_evidence_unstable(self):
        manager = CompileManager(self.root, toolchain=LaTeXToolchain(None, "/bin/fixture"))
        class Process:
            returncode = 0
            def communicate(inner, timeout=None):
                manager.pdf_file.write_bytes(b"%PDF test")
                self.sample.draft_path.write_text(self.sample.conflict_text)
                return "", ""
        with patch("app.core.compiler.subprocess.Popen", return_value=Process()):
            result = manager.compile_now()
        self.assertEqual(result.outcome, CompileOutcome.SUCCESS)
        self.assertFalse(result.input_evidence.stable, "process success is not input consistency")

    def test_current_record_without_actual_evidence_never_passes(self):
        output = self.root.parent / ".latex_build/main.pdf"
        output.parent.mkdir()
        output.write_bytes(b"%PDF fixture")
        record = PdfBuildRecord(self.root, PdfFreshness.CURRENT, output, 1, 1, 1, 4)
        req = replace(request_for(self.sample, final=record), build_evidence=None)
        self.assertEqual(by_rule(check_submission(req), "final_build")[0].status, CheckStatus.UNKNOWN)

    def test_stale_log_and_engine_change_are_not_current_evidence(self):
        from app.core.log_parser import LaTeXError
        output = self.root.parent / ".latex_build/main.pdf"
        output.parent.mkdir()
        output.write_bytes(b"%PDF fixture")
        record = PdfBuildRecord(self.root, PdfFreshness.CURRENT, output, 1, 1, 1, 4)
        req = request_for(self.sample, final=record)
        req = replace(req, build_evidence=replace(req.build_evidence, warnings=(LaTeXError("undefined"),)))
        self.assertEqual(by_rule(check_submission(req), "final_log")[0].status, CheckStatus.FAIL)
        changed = replace(req, source_revision=2)
        report = check_submission(changed)
        self.assertEqual(by_rule(report, "final_log")[0].status, CheckStatus.UNKNOWN)
        self.assertFalse(by_rule(report, "final_log_issue"), "do not navigate a stale warning against changed source")
        changed = replace(req, engine=LaTeXEngine.XELATEX)
        self.assertEqual(by_rule(check_submission(changed), "final_build")[0].status, CheckStatus.FAIL)

    def test_reference_warning_parser_is_bounded_to_technical_warnings(self):
        warnings = parse_reference_warnings(
            "LaTeX Warning: Reference `x' on page 1 undefined on input line 9.\n\n"
            "LaTeX Warning: There were multiply-defined labels.\n\n"
            "Package graphicx Warning: Benign package advice.\n\n")
        self.assertEqual(len(warnings), 2)
        self.assertEqual(warnings[0].line, 9)

    def test_stop_during_input_capture_does_not_start_tex_later(self):
        manager = CompileManager(self.root, toolchain=LaTeXToolchain(None, "/bin/fixture"))
        entered, release = threading.Event(), threading.Event()
        original = capture_compile_inputs
        def delayed(*args, **kwargs):
            entered.set()
            release.wait(5)
            return original(*args, **kwargs)
        results = []
        manager.on_finished = results.append
        with patch("app.core.compiler.capture_compile_inputs", side_effect=delayed), \
             patch("app.core.compiler.subprocess.Popen") as process:
            manager.compile_async(BuildPurpose.FINAL)
            self.assertTrue(entered.wait(2))
            manager.stop_current(timeout=0.01)
            release.set()
            self.assertTrue(manager.wait_until_idle(5))
            process.assert_not_called()
        self.assertEqual(results[0].outcome, CompileOutcome.STOPPED)
