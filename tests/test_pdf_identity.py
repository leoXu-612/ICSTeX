import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from dataclasses import replace
from types import SimpleNamespace

from app.core.file_observation import file_signature
from app.core.pdf_identity import capture_pdf_identity
from app.core.project_dependencies import observe_input


class PdfIdentityTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.scope = Path(self.temp.name).resolve()
        self.path = self.scope / "main.pdf"
        self.path.write_bytes(b"%PDF synthetic identity fixture")

    def test_identity_uses_actual_bytes_not_path_or_mtime(self):
        identity = capture_pdf_identity(self.path, self.scope)
        self.assertEqual(identity.digest, hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertTrue(identity.still_matches(self.path))
        before = self.path.stat()
        self.path.write_bytes(b"%PDF synthetic identity fixturE")
        os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertFalse(identity.still_matches(self.path))
        self.assertNotEqual(capture_pdf_identity(self.path, self.scope).digest, identity.digest)

    def test_final_observation_is_reused_without_rehashing(self):
        before = file_signature(self.path)
        observation = observe_input(self.path, self.scope)
        with patch("app.core.pdf_identity.observe_input") as reread:
            identity = capture_pdf_identity(self.path, self.scope, observation=observation, observed_from=before)
        reread.assert_not_called()
        self.assertEqual(identity.digest, observation.digest)
        self.assertIsNone(capture_pdf_identity(self.path, self.scope, observation=observation))

    def test_changed_file_during_existing_observation_is_not_certified(self):
        before = file_signature(self.path)
        observation = observe_input(self.path, self.scope)
        self.path.write_bytes(b"changed")
        self.assertIsNone(capture_pdf_identity(self.path, self.scope, observation=observation, observed_from=before))

    def test_missing_link_and_outside_scope_have_no_identity(self):
        link = self.scope / "link.pdf"
        link.symlink_to(self.path)
        self.assertIsNone(capture_pdf_identity(link, self.scope))
        self.assertIsNone(capture_pdf_identity(self.scope / "missing.pdf", self.scope))
        self.assertIsNone(capture_pdf_identity(self.path, self.scope / "other"))

    def test_display_identity_does_not_change_mcp_compile_response(self):
        from app.core.agent_workspace import AgentWorkspace
        from app.core.compiler import CompileOutcome, CompileResult
        result = CompileResult(self.scope / "main.tex", self.scope, self.path, self.scope / "main.log",
                               [], 0, "", "", .1, CompileOutcome.SUCCESS)
        host = SimpleNamespace(_relative=lambda path: path.name)
        before = AgentWorkspace._compile_result(host, result)
        after = AgentWorkspace._compile_result(host, replace(result,
            pdf_identity=capture_pdf_identity(self.path, self.scope)))
        self.assertEqual(before, after)
