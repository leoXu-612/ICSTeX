from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest import TestCase
from unittest.mock import patch

from app.core.block_submission import BlockCheckInput
from app.core.build_evidence import FinalBuildEvidence, capture_compile_inputs, finish_compile_inputs
from app.core.compiler import BuildPurpose, CompileJobKey, CompileOutcome
from app.core.latex_tools import LaTeXEngine, LaTeXToolchain
from app.core.pdf_state import PdfBuildRecord, PdfFreshness
from app.core.project_dependencies import observe_input, static_dependencies
from app.core.submission_check import (BufferInput, CheckCancelled, CheckRequest, CheckStatus,
                                       check_submission)
from tests.v1_fixtures import create_project


def request_for(sample, **kwargs):
    tools = LaTeXToolchain(None, None)
    final = kwargs.get("final")
    if final:
        before = capture_compile_inputs(sample.root, sample.root.parent)
        proof = finish_compile_inputs(before, sample.root, sample.root.parent, (), final.last_successful_pdf)
        key = CompileJobKey(sample.root, final.last_successful_pdf.parent, BuildPurpose.FINAL,
                            LaTeXEngine.PDFLATEX, tools, False, final.source_revision, 0)
        kwargs["build_evidence"] = FinalBuildEvidence(key, final.latest_build_id, CompileOutcome.SUCCESS,
                                                     final.last_successful_pdf, proof, (), (), True)
    return CheckRequest((str(sample.root), 1), sample.root.parent, sample.root,
                        (BufferInput(sample.root, sample.root.read_text(), 1),),
                        tools, LaTeXEngine.PDFLATEX,
                        baseline_observations=tuple((p, observe_input(p, sample.root.parent))
                            for p in static_dependencies(sample.root, sample.root.parent).paths), **kwargs)


def by_rule(report, rule):
    return [item for item in report.items if item.rule_id == rule]


class SubmissionCheckTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.sample = create_project(self.base)

    def test_root_child_references_resources_and_count_are_read_only(self):
        before = {p: p.read_bytes() for p in self.sample.root.parent.rglob("*") if p.is_file()}
        report = check_submission(request_for(self.sample))
        self.assertTrue(report.stable)
        for rule in ("root", "resources", "references", "saved", "word_count"):
            self.assertEqual(by_rule(report, rule)[0].status, CheckStatus.PASS, (rule, report))
        self.assertEqual(by_rule(report, "toolchain")[0].status, CheckStatus.FAIL)
        self.assertEqual(by_rule(report, "final_build")[0].status, CheckStatus.UNKNOWN)
        self.assertEqual(by_rule(report, "word_target")[0].status, CheckStatus.NOT_APPLICABLE)
        self.assertEqual(by_rule(report, "input_coverage")[0].status, CheckStatus.UNKNOWN)
        self.assertIn("fallback", by_rule(report, "word_count")[0].reason)
        self.assertTrue(all(i.rule_id and i.scope and i.input_id == report.input_id for i in report.items))
        self.assertEqual(before, {p: p.read_bytes() for p in self.sample.root.parent.rglob("*") if p.is_file()})

    def test_unopened_child_error_navigates_to_child_line_and_buffer_overrides_disk(self):
        child = self.sample.draft_path
        text = child.read_text() + "\\cite{absent}\n\\ref{missing}\n"
        req = request_for(self.sample)
        req = replace(req, buffers=(*req.buffers, BufferInput(child, text, 2, True)))
        report = check_submission(req)
        self.assertEqual(by_rule(report, "saved")[0].status, CheckStatus.FAIL)
        error = by_rule(report, "citation_missing")[0]
        self.assertEqual((error.file, error.line), (child, 4))
        self.assertEqual(by_rule(report, "reference_missing")[0].file, child)
        self.assertNotIn("absent", child.read_text())

    def test_missing_alternative_extensions_are_not_false_missing_resources(self):
        report = check_submission(request_for(self.sample))
        self.assertFalse(by_rule(report, "resource_missing"))
        (self.sample.root.parent / "figures" / "plot.png").unlink()
        report = check_submission(request_for(self.sample))
        error = by_rule(report, "resource_missing")[0]
        self.assertIn("plot", error.reason)
        self.assertEqual(error.file, self.sample.root)

    def test_dynamic_unsafe_and_non_utf8_inputs_are_unknown_not_read(self):
        outside = self.base / "private.tex"
        outside.write_text("private")
        project = self.sample.root.parent
        (project / "link.tex").symlink_to(outside)
        (project / "invalid.tex").write_bytes(b"\xff\xfe\xff")
        root = self.sample.root
        root.write_text(root.read_text().replace("\\end{document}",
                        "\\input{link}\n\\input{\\computed{key}}\n\\input{invalid}\n\\end{document}"))
        report = check_submission(request_for(self.sample))
        self.assertTrue(by_rule(report, "resource_unresolved"))
        self.assertTrue(by_rule(report, "input_unreadable"))
        self.assertNotIn(outside, dict(report.observations))

    def test_cancelled_check_does_not_start_analysis(self):
        cancel = Event()
        cancel.set()
        with patch("app.core.submission_check.static_dependencies") as scan:
            with self.assertRaises(CheckCancelled):
                check_submission(request_for(self.sample), cancel)
            scan.assert_not_called()

    def test_profile_change_during_count_rejects_report_and_changes_identity(self):
        from app.core.project_profile import ProjectProfile, load_profile, save_profile
        from app.core.word_count import count_project_snapshot
        root = self.sample.root.parent
        first = check_submission(request_for(self.sample))
        def changing(*args, **kwargs):
            save_profile(root, ProjectProfile(word_max=2), expected=load_profile(root))
            return count_project_snapshot(*args, **kwargs)
        with patch("app.core.submission_check.count_project_snapshot", side_effect=changing):
            report = check_submission(request_for(self.sample))
        self.assertFalse(report.stable)
        current = check_submission(request_for(self.sample))
        self.assertNotEqual(first.input_id, current.input_id)
        self.assertEqual(by_rule(current, "word_target")[0].status, CheckStatus.FAIL)

    def test_profile_cannot_disable_final_guards_or_turn_invalid_config_into_pass(self):
        from app.core.project_profile import ProjectProfile, load_profile, save_profile
        root = self.sample.root.parent
        profile = ProjectProfile(check_resources=False, check_references=False, engine="xelatex")
        save_profile(root, profile, expected=load_profile(root))
        report = check_submission(request_for(self.sample))
        self.assertEqual(by_rule(report, "profile_engine")[0].status, CheckStatus.FAIL)
        for rule in ("resources", "references"):
            self.assertEqual(by_rule(report, rule)[0].status, CheckStatus.NOT_APPLICABLE)
        self.assertEqual(by_rule(report, "final_build")[0].status, CheckStatus.UNKNOWN)
        self.assertEqual(by_rule(report, "saved")[0].status, CheckStatus.PASS)

    def test_same_size_same_mtime_change_during_check_is_rejected(self):
        image = self.sample.root.parent / "figures" / "plot.png"
        before = image.stat()
        calls = 0
        original = observe_input
        def observe(path, scope):
            nonlocal calls
            result = original(path, scope)
            if path == image:
                calls += 1
                if calls == 1:
                    data = bytearray(path.read_bytes())
                    data[-1] ^= 1
                    path.write_bytes(data)
                    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            return result
        with patch("app.core.submission_check.observe_input", side_effect=observe):
            report = check_submission(request_for(self.sample))
        self.assertFalse(report.stable)

    def test_input_identity_changes_for_image_engine_and_buffer(self):
        req = request_for(self.sample)
        first = check_submission(req)
        other_engine = check_submission(replace(req, engine=LaTeXEngine.XELATEX))
        self.assertNotEqual(first.input_id, other_engine.input_id)
        image = self.sample.root.parent / "figures" / "plot.png"
        image.write_bytes(image.read_bytes() + b"x")
        self.assertNotEqual(first.input_id, check_submission(req).input_id)
        self.assertNotEqual(first.input_id, check_submission(replace(req, buffers=(
            replace(req.buffers[0], text=req.buffers[0].text + "draft", modified=True),))).input_id)

    def test_changed_dependency_cannot_reuse_current_record_before_watcher_delivery(self):
        root = self.sample.root
        out = root.parent / ".latex_build" / "main.pdf"
        out.parent.mkdir()
        out.write_bytes(b"%PDF test fixture")
        record = PdfBuildRecord(root, PdfFreshness.CURRENT, out, 4, 4, 4, 7)
        req = request_for(self.sample, final=record)
        self.sample.draft_path.write_text(self.sample.conflict_text)
        report = check_submission(req)
        self.assertEqual(by_rule(report, "pdf_current")[0].status, CheckStatus.FAIL)

    def test_preview_stale_wrong_root_and_unsaved_are_never_current_final(self):
        root = self.sample.root
        out = root.parent / ".latex_build" / "main.pdf"
        out.parent.mkdir()
        out.write_bytes(b"%PDF-1.4 synthetic test record")
        record = PdfBuildRecord(root, PdfFreshness.CURRENT, out, 4, 4, 4, 7)
        req = request_for(self.sample, final=record)
        self.assertEqual(by_rule(check_submission(req), "pdf_current")[0].status, CheckStatus.PASS)
        for changed in (replace(record, freshness=PdfFreshness.DIRTY),
                        replace(record, source_revision=5), replace(record, root_file=self.base / "other.tex")):
            self.assertEqual(by_rule(check_submission(replace(req, final=changed)), "pdf_current")[0].status, CheckStatus.FAIL)
        preview = root.parent / ".icstex" / "preview" / "main.pdf"
        preview.parent.mkdir(parents=True)
        preview.write_bytes(out.read_bytes())
        self.assertEqual(by_rule(check_submission(replace(req, final=replace(record, last_successful_pdf=preview))),
                                 "pdf_current")[0].status, CheckStatus.FAIL)
        dirty = replace(req, buffers=(replace(req.buffers[0], modified=True),))
        self.assertEqual(by_rule(check_submission(dirty), "pdf_current")[0].status, CheckStatus.FAIL)

    def test_targets_are_explicit_and_unsaved_root_is_unknown(self):
        req = request_for(self.sample, word_target=(1, 2))
        self.assertEqual(by_rule(check_submission(req), "word_target")[0].status, CheckStatus.FAIL)
        req = replace(req, root=None, scope=None, buffers=(BufferInput(None, "draft", 1, True),))
        report = check_submission(req)
        self.assertEqual(by_rule(report, "root")[0].status, CheckStatus.UNKNOWN)
        self.assertEqual(by_rule(report, "word_count")[0].status, CheckStatus.UNKNOWN)

    def test_configured_but_removed_engine_is_not_available(self):
        req = replace(request_for(self.sample), tools=LaTeXToolchain(None, "/missing/pdflatex"))
        self.assertEqual(by_rule(check_submission(req), "toolchain")[0].status, CheckStatus.FAIL)

    def block_request(self):
        sample = create_project(self.base, "block")
        root = sample.root.parent
        snapshot = BlockCheckInput(
            (root / ".icstex/blocks.json").read_text(), (root / ".icstex/layouts.json").read_text(),
            (root / ".icstex/sources.json").read_text(), (root / "styles/document-theme.json").read_text())
        return sample, replace(request_for(sample), buffers=(), block=snapshot)

    def test_block_metadata_and_generated_source_are_read_only_and_final_is_unknown(self):
        sample, req = self.block_request()
        before = {p: p.read_bytes() for p in sample.root.parent.rglob("*") if p.is_file()}
        report = check_submission(req)
        self.assertEqual(by_rule(report, "saved")[0].status, CheckStatus.PASS)
        self.assertEqual(by_rule(report, "block_generated")[0].status, CheckStatus.PASS)
        self.assertEqual(by_rule(report, "final_build")[0].status, CheckStatus.UNKNOWN)
        self.assertEqual(by_rule(report, "pdf_current")[0].status, CheckStatus.UNKNOWN)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_block_external_generated_change_does_not_count_as_current_model(self):
        sample, req = self.block_request()
        sample.draft_path.write_text(sample.conflict_text)
        report = check_submission(req)
        self.assertEqual(by_rule(report, "saved")[0].status, CheckStatus.PASS)
        self.assertEqual(by_rule(report, "block_generated")[0].status, CheckStatus.FAIL)
        self.assertEqual(by_rule(report, "word_count")[0].status, CheckStatus.UNKNOWN)
        self.assertEqual(sample.draft_path.read_text(), sample.conflict_text)

    def test_block_unreadable_metadata_is_unknown_and_symlink_target_is_never_opened(self):
        sample, req = self.block_request()
        metadata = sample.root.parent / ".icstex/sources.json"
        outside = self.base / "outside.json"
        outside.write_text('{"sources":[]}')
        metadata.unlink()
        metadata.symlink_to(outside)
        report = check_submission(req)
        self.assertEqual(by_rule(report, "saved")[0].status, CheckStatus.UNKNOWN)
        self.assertNotIn(metadata, report.watched_paths)
        self.assertNotIn(outside, report.watched_paths)
        metadata.unlink()
        metadata.write_bytes(b"invalid-json")
        report = check_submission(req)
        self.assertEqual(by_rule(report, "saved")[0].status, CheckStatus.UNKNOWN)

    def test_block_metadata_change_during_check_rejects_snapshot(self):
        from app.core.project_dependencies import read_project_bytes
        sample, req = self.block_request()
        metadata = sample.root.parent / ".icstex/sources.json"
        first = True
        def changed(path, scope, **kwargs):
            nonlocal first
            data = read_project_bytes(path, scope, **kwargs)
            if path == metadata and first:
                first = False
                path.write_bytes(data + b" ")
            return data
        with patch("app.core.block_submission.read_project_bytes", side_effect=changed):
            self.assertFalse(check_submission(req).stable)

    def test_missing_saved_root_is_not_reported_readable_from_buffer_only(self):
        req = request_for(self.sample)
        self.sample.root.unlink()
        self.assertEqual(by_rule(check_submission(req), "root")[0].status, CheckStatus.UNKNOWN)
