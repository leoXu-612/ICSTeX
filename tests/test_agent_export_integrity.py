"""Actual AgentWorkspace export seams; synthetic compile proof is unit-only."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.agent_workspace import AgentGrants, AgentWorkspace, AgentWorkspaceError
from app.core import artifact_export
from app.core.build_evidence import capture_compile_inputs, finish_compile_inputs
from app.core.compiler import BuildPurpose, CompileJobKey, CompileOutcome, CompileResult
from app.core.latex_tools import LaTeXEngine, LaTeXToolchain
from tests.v1_fixtures import create_project


class AgentPdfIntegrityTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.project, self.exports = self.base / "project", self.base / "exports"
        self.project.mkdir()
        self.exports.mkdir()
        self.root, self.child = self.project / "main.tex", self.project / "child.tex"
        self.root.write_bytes(b"\\documentclass{article}\n\\begin{document}\\input{child}\\end{document}\n")
        self.child.write_bytes(b"old child\n")
        self.pdf = self.project / ".latex_build/main.pdf"
        self.pdf.parent.mkdir()
        self.pdf.write_bytes(b"%PDF-1.4 synthetic unit evidence, not real TeX output")
        self.workspace = AgentWorkspace(self.project,
            grants=AgentGrants(allow_compile=True, export_root=self.exports))
        inputs = capture_compile_inputs(self.root, self.project)
        proof = finish_compile_inputs(inputs, self.root, self.project, (), self.pdf)
        self.assertTrue(proof.stable)
        key = CompileJobKey(self.root, self.pdf.parent, BuildPurpose.FINAL,
            LaTeXEngine.AUTO, LaTeXToolchain(None, None), True, 0, 0)
        self.result = CompileResult(self.root, self.pdf.parent, self.pdf,
            self.pdf.with_suffix(".log"), ["synthetic"], 0, "", "", 0.01,
            CompileOutcome.SUCCESS, build_id=7, job_key=key, input_evidence=proof)

    def export(self, result=None, effect=None):
        with patch("app.core.agent_workspace.CompileManager.compile_now",
                   side_effect=effect, return_value=result or self.result):
            return self.workspace.export_artifact("pdf", "final.pdf")

    def test_pdf_wire_shape_and_exact_bytes_remain_compatible(self):
        value = self.export()
        self.assertEqual(set(value), {"kind", "target", "sha256", "size"})
        self.assertEqual((self.exports / "final.pdf").read_bytes(), self.pdf.read_bytes())

    def test_same_size_mtime_input_change_after_final_refuses(self):
        def finished(*args, **kwargs):
            info = self.child.stat()
            self.child.write_bytes(b"new child\n")
            os.utime(self.child, ns=(info.st_atime_ns, info.st_mtime_ns))
            return self.result
        with self.assertRaises((AgentWorkspaceError, OSError, ValueError)):
            self.export(effect=finished)
        self.assertFalse((self.exports / "final.pdf").exists())
        self.assertEqual(self.child.read_bytes(), b"new child\n")

    def test_pdf_changed_after_final_refuses(self):
        def finished(*args, **kwargs):
            self.pdf.write_bytes(b"%PDF-1.4 changed synthetic output")
            return self.result
        with self.assertRaises((AgentWorkspaceError, OSError, ValueError)):
            self.export(effect=finished)
        self.assertFalse((self.exports / "final.pdf").exists())

    def test_missing_or_preview_build_proof_never_exports(self):
        for value in (replace(self.result, input_evidence=None),
                      replace(self.result, purpose=BuildPurpose.PREVIEW),
                      replace(self.result, job_key=None)):
            with self.subTest(result=value), self.assertRaises((AgentWorkspaceError, OSError, ValueError)):
                self.export(value)
        self.assertFalse((self.exports / "final.pdf").exists())

    def test_profile_appearing_during_compile_refuses(self):
        def finished(*args, **kwargs):
            (self.project / ".icstex").mkdir()
            (self.project / ".icstex/project-profile.json").write_bytes(b'{"changed":true}')
            return self.result
        with self.assertRaises((AgentWorkspaceError, OSError, ValueError)):
            self.export(effect=finished)
        self.assertFalse((self.exports / "final.pdf").exists())

    def test_stop_after_compile_refuses_publication(self):
        def finished(*args, **kwargs):
            self.workspace.compile_project(action="stop")
            return self.result
        with self.assertRaises((AgentWorkspaceError, OSError, ValueError)):
            self.export(effect=finished)
        self.assertFalse((self.exports / "final.pdf").exists())

    def test_late_existing_file_or_symlink_never_overwritten(self):
        original = artifact_export._OutputParent.publish_file
        outside = self.base / "outside.pdf"
        outside.write_bytes(b"outside owner bytes")
        target = self.exports / "final.pdf"
        for linked in (False, True):
            def occupy(parent, name, signature):
                if linked:
                    target.symlink_to(outside)
                else:
                    target.write_bytes(b"late winner")
                return original(parent, name, signature)
            with self.subTest(linked=linked), patch.object(
                    artifact_export._OutputParent, "publish_file", occupy), self.assertRaises(FileExistsError):
                self.export()
            self.assertEqual(outside.read_bytes(), b"outside owner bytes")
            if not linked:
                self.assertEqual(target.read_bytes(), b"late winner")
            self.assertEqual(list(self.exports.iterdir()), [target])
            target.unlink()

    def test_changes_or_stop_during_staged_readback_refuse_and_cleanup(self):
        original = artifact_export._read_file
        for action in ("child", "profile", "stop"):
            applied = False
            def read(project, relative, *args, **kwargs):
                nonlocal applied
                value = original(project, relative, *args, **kwargs)
                if project == self.exports and relative.startswith(".icstex-export.") and not applied:
                    applied = True
                    if action == "child":
                        self.child.write_bytes(b"new child\n")
                    elif action == "profile":
                        (self.project / ".icstex").mkdir(exist_ok=True)
                        (self.project / ".icstex/project-profile.json").write_bytes(b"changed")
                    else:
                        self.workspace.compile_project(action="stop")
                return value
            with self.subTest(action=action), patch.object(artifact_export, "_read_file", read), self.assertRaises(
                    (AgentWorkspaceError, OSError, ValueError)):
                self.export()
            self.assertTrue(applied)
            self.assertEqual(list(self.exports.iterdir()), [])
            self.child.write_bytes(b"old child\n")
            (self.project / ".icstex/project-profile.json").unlink(missing_ok=True)
            before = capture_compile_inputs(self.root, self.project)
            self.result = replace(self.result,
                input_evidence=finish_compile_inputs(before, self.root, self.project, (), self.pdf))

    def test_pending_journal_refuses_before_compiler_or_assembly(self):
        (self.project / ".icstex").mkdir()
        marker = self.project / ".icstex/block-write.pending"
        marker.write_bytes(b"synthetic unresolved recovery evidence")
        with patch.object(self.workspace, "mutate_blocks") as mutate, patch(
                "app.core.agent_workspace.CompileManager") as manager, self.assertRaises(ValueError):
            self.workspace.export_artifact("pdf", "final.pdf", assemble_blocks=True,
                expected_project_sha256="synthetic")
        mutate.assert_not_called()
        manager.assert_not_called()
        self.assertEqual(marker.read_bytes(), b"synthetic unresolved recovery evidence")

    def test_staging_io_failure_retains_prior_delivery_and_removes_owned_partial(self):
        prior = self.exports / "earlier.pdf"
        prior.write_bytes(b"prior successful delivery")
        with patch.object(artifact_export.os, "fsync", side_effect=OSError("synthetic disk full")), self.assertRaises(OSError):
            self.export()
        self.assertEqual(prior.read_bytes(), b"prior successful delivery")
        self.assertEqual(list(self.exports.iterdir()), [prior])

    def test_auto_engine_respects_magic_and_explicit_engine_selection(self):
        self.root.write_bytes(b"% !TeX program = lualatex\n" + self.root.read_bytes())
        self.assertIs(self.workspace._compile_engine("main.tex", self.root, LaTeXEngine.AUTO), LaTeXEngine.LUALATEX)
        self.assertIs(self.workspace._compile_engine("main.tex", self.root, LaTeXEngine.PDFLATEX), LaTeXEngine.PDFLATEX)
        self.child.write_bytes(b"% !TeX program = xelatex\n" + self.child.read_bytes())
        self.assertIs(self.workspace._compile_engine("child.tex", self.root, LaTeXEngine.AUTO), LaTeXEngine.XELATEX)

    def test_auto_engine_uses_xelatex_only_for_known_generated_block_root(self):
        sample = create_project(self.base, "block")
        workspace = AgentWorkspace(sample.root.parent)
        original = sample.root.read_bytes()
        # A real GUI default theme must also remain readable through the existing
        # MCP inspect/query/assembly seam, not merely the engine-selection helper.
        state = workspace._load_block_state()
        self.assertEqual(state["document_theme"].page, {})
        self.assertEqual(state["document_theme"].typography, {})
        self.assertIs(workspace._compile_engine("main.tex", sample.root, LaTeXEngine.AUTO), LaTeXEngine.XELATEX)
        self.assertEqual(sample.root.read_bytes(), original)
        sample.root.write_bytes(original + b"\n% user-owned custom source\n")
        self.assertIs(workspace._compile_engine("main.tex", sample.root, LaTeXEngine.AUTO), LaTeXEngine.AUTO)
