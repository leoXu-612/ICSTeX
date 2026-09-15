"""Pure frozen delivery rules; mock build records are not native PDF proof."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event
from unittest import TestCase
from unittest.mock import patch

from app.core import project_checkpoint as storage
from app.core import submission_delivery as delivery
from app.core.latex_tools import LaTeXToolchain
from app.core.pdf_state import PdfBuildRecord, PdfFreshness
from app.core.project_profile import ProjectProfile, load_profile, save_profile
from tests.test_submission_check import request_for
from tests.v1_fixtures import create_project


class SubmissionDeliveryTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-delivery-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.sample = create_project(self.home)
        self.project = self.sample.root.parent
        self.pdf = self.project / ".latex_build/main.pdf"
        self.pdf.parent.mkdir()
        self.pdf.write_bytes(b"%PDF-1.4 synthetic unit evidence only")
        record = PdfBuildRecord(self.sample.root, PdfFreshness.CURRENT, self.pdf, 4, 4, 4, 7)
        req = request_for(self.sample, final=record)
        tools = LaTeXToolchain(None, sys.executable)
        self.request = replace(req, tools=tools,
            build_evidence=replace(req.build_evidence, job_key=replace(req.build_evidence.job_key, toolchain=tools)))
        self.paths = ("main.tex", "chapters/analysis.tex", "refs.bib", "figures/plot.png")
        self.target = self.home / "delivery"

    def prepare(self, **kwargs):
        return delivery.prepare_submission(self.request, **kwargs)

    def publish(self, prepared, **kwargs):
        return delivery.publish_submission(prepared, self.target, accept_unconfirmed=True, **kwargs)

    def test_pdf_only_default_and_report_source_are_independent_choices(self):
        prepared = self.prepare()
        with self.assertRaisesRegex(ValueError, "unconfirmed"):
            delivery.publish_submission(prepared, self.target)
        result = self.publish(prepared)
        self.assertEqual(result, self.target)
        self.assertEqual([p.name for p in self.target.iterdir()], ["submission.pdf"])
        self.assertEqual((self.target / "submission.pdf").read_bytes(), self.pdf.read_bytes())
        self.assertEqual(prepared.options, delivery.DeliveryOptions())

    def test_selected_source_bytes_and_user_readme_manifest_are_not_overwritten(self):
        originals = {"README.md": b"User original README\r\n", "manifest.json": b'{"user":true}\r\n',
                     "encoding-note.tex": b"% \x81\xff\r\n"}
        for path, raw in originals.items():
            (self.project / path).write_bytes(raw)
        options = delivery.DeliveryOptions(True, True, self.paths + tuple(originals), "final.pdf")
        prepared = self.prepare(options=options)
        self.publish(prepared)
        for path in options.source_paths:
            self.assertEqual((self.target / "source" / path).read_bytes(), (self.project / path).read_bytes())
        report_bytes = (self.target / "submission-report.json").read_bytes()
        self.assertNotIn(str(self.home).encode(), report_bytes)
        report = json.loads(report_bytes)
        self.assertEqual(report["purpose"], "final")
        self.assertEqual(report["word_count"]["mode"], "fallback")
        for row in report["outputs"]:
            raw = (self.target / row["path"]).read_bytes()
            self.assertEqual(row["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(row["size"], len(raw))
        self.assertTrue(any(c["status"] == "unknown" for c in report["checks"]))

    def test_report_versions_are_frozen_build_labels_not_export_time_tool_queries(self):
        from app.core.build_tool_versions import capture_tool_versions
        from app.core.latex_tools import LaTeXEngine
        from tests.test_build_tool_versions import wrapped
        captured = capture_tool_versions(wrapped(), LaTeXEngine.AUTO, via_latexmk=True)
        self.request = replace(self.request, build_evidence=replace(self.request.build_evidence,
                                                                  tool_versions=captured))
        prepared = self.prepare(options=delivery.DeliveryOptions(include_report=True))
        with patch("subprocess.Popen", side_effect=AssertionError("report must not execute tools")):
            reviewed = dict(delivery.delivery_payloads(prepared))["submission-report.json"]
        report = json.loads(reviewed)
        self.assertEqual(report["build_tool_versions"]["driver"]["version"], "4.86a")
        self.assertEqual(report["build_tool_versions"]["engine"]["program"], "pdfTeX")
        self.assertEqual(report["build_id"], self.request.build_evidence.build_id)
        self.assertTrue(all(value["version"] is None for value in report["toolchain"].values()))
        self.assertNotIn(str(self.home).encode(), reviewed)
        self.publish(prepared)
        self.assertEqual((self.target / "submission-report.json").read_bytes(), reviewed)
        changed = replace(self.request, build_evidence=replace(self.request.build_evidence, tool_versions=None))
        with self.assertRaisesRegex(OSError, "changed after review"):
            delivery.prepare_submission(changed, prepared.options, expected=prepared)

    def test_report_missing_build_versions_are_unknown_not_current_environment(self):
        report = json.loads(delivery.delivery_report(self.prepare(), ()))
        self.assertIsNone(report["build_tool_versions"]["source"])
        self.assertIsNone(report["build_tool_versions"]["driver"])
        self.assertIsNone(report["build_tool_versions"]["engine"])
        self.assertIn("unknown", report["tool_version_status"])

    def test_source_selection_is_explicit_complete_for_known_inputs_and_private_names_refused(self):
        for options in (delivery.DeliveryOptions(True), delivery.DeliveryOptions(False, False, self.paths),
                        delivery.DeliveryOptions(True, False, ("main.tex",)),
                        delivery.DeliveryOptions(True, False, self.paths + ("signing.pem",)),
                        delivery.DeliveryOptions(True, False, self.paths + (".venv/cache.txt",)),
                        delivery.DeliveryOptions(True, False, self.paths + ("../outside.tex",)),
                        delivery.DeliveryOptions(pdf_name="../escape.pdf"),
                        delivery.DeliveryOptions(include_report=1)):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.prepare(options=options)
        (self.project / "selected.txt").write_bytes(b"-----BEGIN PRIVATE KEY-----\nnot a real key\n")
        with self.assertRaisesRegex(ValueError, "private-key"):
            self.prepare(options=delivery.DeliveryOptions(True, False, self.paths + ("selected.txt",)))
        self.assertFalse(self.target.exists())

    def test_preview_failed_missing_evidence_dirty_and_wrong_revision_never_prepare(self):
        proof = self.request.build_evidence
        from app.core.compiler import BuildPurpose, CompileOutcome
        requests = [
            replace(self.request, build_evidence=None),
            replace(self.request, build_evidence=replace(proof, outcome=CompileOutcome.LATEX_ERROR)),
            replace(self.request, build_evidence=replace(proof, job_key=replace(proof.job_key, purpose=BuildPurpose.PREVIEW))),
            replace(self.request, final=replace(self.request.final, freshness=PdfFreshness.DIRTY)),
            replace(self.request, source_revision=999),
            replace(self.request, buffers=(replace(self.request.buffers[0], modified=True),)),
        ]
        for request in requests:
            with self.subTest(request=request), self.assertRaises(ValueError):
                delivery.prepare_submission(request)
        self.assertFalse(self.target.exists())

    def test_same_mtime_child_change_before_watcher_rejects_old_final(self):
        info = self.sample.draft_path.stat()
        self.sample.draft_path.write_bytes(self.sample.draft_path.read_bytes() + b"\nexternal winner\n")
        os.utime(self.sample.draft_path, ns=(info.st_atime_ns, info.st_mtime_ns))
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.target.exists())

    def test_changed_image_pdf_and_profile_after_review_refuse_publication(self):
        for relative in ("figures/plot.png", ".latex_build/main.pdf", ".icstex/project-profile.json"):
            with self.subTest(relative=relative):
                prepared = self.prepare()
                path = self.project / relative
                before = path.read_bytes() if path.exists() else None
                if relative.endswith("project-profile.json"):
                    save_profile(self.project, ProjectProfile(word_max=2), expected=load_profile(self.project))
                else:
                    info = path.stat()
                    path.write_bytes(before + b"x")
                    os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
                with self.assertRaises((ValueError, OSError)):
                    self.publish(prepared)
                self.assertFalse(self.target.exists())
                if before is None:
                    path.unlink()
                else:
                    path.write_bytes(before)

    def test_between_pass_change_and_late_source_change_preserve_old_target(self):
        prepared = self.prepare()
        self.target.mkdir()
        (self.target / "previous.pdf").write_bytes(b"previous successful delivery")
        with self.assertRaises(FileExistsError):
            self.publish(prepared)
        self.assertEqual((self.target / "previous.pdf").read_bytes(), b"previous successful delivery")
        other = self.home / "new"
        actual = storage._write_restored
        def change(directory, relative, payload, **kwargs):
            result = actual(directory, relative, payload, **kwargs)
            self.sample.draft_path.write_bytes(b"external winner")
            return result
        with patch.object(storage, "_write_restored", side_effect=change):
            with self.assertRaises((ValueError, OSError)):
                delivery.publish_submission(prepared, other, accept_unconfirmed=True)
        self.assertFalse(other.exists())
        self.assertEqual(self.sample.draft_path.read_bytes(), b"external winner")
        self.assertEqual((self.target / "previous.pdf").read_bytes(), b"previous successful delivery")

    def test_cancel_partial_write_link_and_target_inside_project_refuse(self):
        prepared = self.prepare()
        stop = Event()
        stop.set()
        with self.assertRaises(OSError):
            self.publish(prepared, cancelled=stop)
        with patch.object(storage, "_write_restored", side_effect=OSError("synthetic disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.publish(prepared)
        with self.assertRaises(ValueError):
            delivery.publish_submission(prepared, self.project / "nested", accept_unconfirmed=True)
        self.target.symlink_to(self.project, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            self.publish(prepared)
        self.assertTrue(self.target.is_symlink())
        self.assertFalse((self.project / "submission.pdf").exists())

    def test_forged_payload_cannot_be_published(self):
        prepared = self.prepare()
        forged = replace(prepared, inputs=tuple(replace(item, payload=b"forged")
                         if item.path == prepared.pdf_relative else item for item in prepared.inputs))
        with self.assertRaises(OSError):
            self.publish(forged)
        self.assertFalse(self.target.exists())

    def test_report_only_and_source_only_do_not_imply_the_other_output(self):
        for source, report in ((False, True), (True, False)):
            options = delivery.DeliveryOptions(source, report, self.paths if source else ())
            prepared = self.prepare(options=options)
            target = self.home / f"selected-{source}-{report}"
            delivery.publish_submission(prepared, target, accept_unconfirmed=True)
            self.assertEqual((target / "source").exists(), source)
            self.assertEqual((target / "submission-report.json").exists(), report)
            self.assertEqual((target / "SOURCE_README.txt").exists(), source)
            if source:
                self.assertIn("source/main.tex", (target / "SOURCE_README.txt").read_text())
                self.assertIn("pdflatex", (target / "SOURCE_README.txt").read_text())

    def test_candidate_filter_does_not_read_or_select_private_name_variants(self):
        private = ("token.txt", "TOKENS.json", "credentials.txt", "API_KEY.tex", "secret.csv")
        for name in private:
            (self.project / name).write_bytes(b"synthetic placeholder")
        paths, warnings = delivery.submission_source_candidates(self.project)
        self.assertTrue(warnings)
        self.assertTrue(set(private).isdisjoint(paths))
        self.assertIn("main.tex", paths)
        for name in private:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.prepare(options=delivery.DeliveryOptions(True, False, self.paths + (name,)))

    def test_delivery_inventory_includes_optional_documents_without_changing_checkpoint_defaults(self):
        for path in ("README.md", "manifest.json", "notes.txt", "sample.xlsx"):
            (self.project / path).write_bytes(b"synthetic optional file")
        candidates, _ = delivery.submission_source_candidates(self.project)
        self.assertTrue({"README.md", "manifest.json", "notes.txt", "sample.xlsx"}.issubset(candidates))
        checkpoint_candidates, _ = storage.checkpoint_candidates(self.project)
        self.assertNotIn("README.md", checkpoint_candidates)
        self.assertNotIn("manifest.json", checkpoint_candidates)
        self.assertIn("sample.xlsx", checkpoint_candidates)

    def test_selected_non_dependency_change_between_passes_and_after_review_refuses(self):
        path = self.project / "notes.md"
        path.write_bytes(b"original note")
        options = delivery.DeliveryOptions(True, False, self.paths + ("notes.md",))
        prepared = self.prepare(options=options)
        path.write_bytes(b"later note")
        with self.assertRaises(OSError):
            self.publish(prepared)
        self.assertFalse(self.target.exists())
        path.write_bytes(b"original note")
        actual = delivery._read_file
        changed = []
        def read(root, relative, *args):
            result = actual(root, relative, *args)
            if relative == "notes.md" and not changed:
                changed.append(True)
                path.write_bytes(b"changed inside read pass")
            return result
        with patch.object(delivery, "_read_file", side_effect=read):
            with self.assertRaises(OSError):
                self.prepare(options=options)
        self.assertFalse(self.target.exists())

    def test_new_missing_alternative_input_after_review_rejects_output(self):
        prepared = self.prepare()
        self.assertTrue(any(f.payload is None for f in prepared.inputs))
        absent = next(f for f in prepared.inputs if f.payload is None and not f.path.startswith(".icstex"))
        path = self.project / absent.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"newly available candidate")
        with self.assertRaises((ValueError, OSError)):
            self.publish(prepared)
        self.assertFalse(self.target.exists())

    def test_absent_input_created_after_last_report_is_rechecked_before_acceptance(self):
        prepared = self.prepare()
        absent = next(f for f in prepared.inputs if f.payload is None and not f.path.startswith(".icstex"))
        path = self.project / absent.path
        actual = delivery._report
        calls = []
        def report(*args):
            result = actual(*args)
            calls.append(True)
            if len(calls) == 2:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"late local dependency")
            return result
        with patch.object(delivery, "_report", side_effect=report):
            with self.assertRaises(OSError):
                self.prepare()
        self.assertFalse(self.target.exists())

    def test_source_path_collisions_and_existing_selected_link_are_refused(self):
        for paths in (self.paths + ("main.tex",), self.paths + ("MAIN.tex",),
                      self.paths + ("notes", "notes/file.tex")):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                self.prepare(options=delivery.DeliveryOptions(True, False, paths))
        outside = self.home / "outside.tex"
        outside.write_bytes(b"outside")
        (self.project / "link.tex").symlink_to(outside)
        with self.assertRaises(ValueError):
            self.prepare(options=delivery.DeliveryOptions(True, False, self.paths + ("link.tex",)))
        self.assertEqual(outside.read_bytes(), b"outside")

    def test_count_identity_excludes_only_transient_details_not_numeric_mode_or_warnings(self):
        prepared = self.prepare()
        count = prepared.report.word_count
        self.assertEqual(delivery._count_identity(count), delivery._count_identity(replace(count, details="another temp path")))
        for changed in (replace(count, source="texcount"), replace(count, effective_words=count.effective_words + 1),
                        replace(count, warnings=("unknown",))):
            self.assertNotEqual(delivery._count_identity(count), delivery._count_identity(changed))

    def test_known_metadata_is_optional_and_byte_exact_but_private_history_is_not_selectable(self):
        save_profile(self.project, ProjectProfile(word_max=500), expected=load_profile(self.project))
        profile_path = ".icstex/project-profile.json"
        paths, _ = delivery.submission_source_candidates(self.project)
        self.assertIn(profile_path, paths)
        prepared = self.prepare(options=delivery.DeliveryOptions(True, False, self.paths + (profile_path,)))
        self.publish(prepared)
        self.assertEqual((self.target / "source" / profile_path).read_bytes(), (self.project / profile_path).read_bytes())
        for path in (".icstex/history.json", ".icstex/backups/old.tex", "source/.icstex/blocks.json"):
            self.assertFalse(delivery.source_path_allowed(path))

    def test_pending_write_and_late_marker_refuse_without_cleaning_evidence(self):
        marker = self.project / ".icstex/block-write.pending"
        marker.mkdir(parents=True)
        (marker / "evidence.json").write_bytes(b"keep journal")
        with self.assertRaisesRegex(ValueError, "journal"):
            self.prepare()
        self.assertEqual((marker / "evidence.json").read_bytes(), b"keep journal")
        (marker / "evidence.json").unlink()
        marker.rmdir()
        actual = delivery._report
        calls = []
        def report(*args):
            result = actual(*args)
            calls.append(True)
            if len(calls) == 2:
                marker.mkdir()
            return result
        with patch.object(delivery, "_report", side_effect=report):
            with self.assertRaisesRegex(ValueError, "journal"):
                self.prepare()
        self.assertTrue(marker.is_dir())
        self.assertFalse(self.target.exists())
