from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core import macos_compiler_sandbox as sandbox
from app.core.compiler import BuildPurpose, CompileManager, CompileOutcome, PreviewPreparation
from app.core.latex_tools import LaTeXEngine, LaTeXToolchain


class SandboxPolicyTests(TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.project = self.base / 'project "quoted"'
        self.project.mkdir()
        self.root = self.project / "main.tex"
        self.root.write_text("synthetic")
        self.output = self.project / ".latex_build"
        self.output.mkdir()
        self.texparent = self.base / "texlive"
        self.texroot = self.texparent / "2025"
        self.bin = self.texroot / "bin" / "universal-darwin"
        self.bin.mkdir(parents=True)
        (self.texroot / "texmf-dist").mkdir()
        self.engine = self.bin / "lualatex"
        self.engine.write_text("synthetic executable")
        self.engine.chmod(0o755)
        self.toolchain = LaTeXToolchain(None, None, lualatex=str(self.engine))
        self.addCleanup(patch.stopall)
        patch.object(sandbox, "TEXLIVE_PARENT", self.texparent).start()
        patch.object(sandbox, "SANDBOX_EXEC", self.engine).start()

    def launch(self, **kwargs):
        return sandbox.macos_sandbox_launch(
            [str(self.engine), "-no-shell-escape", "main.tex"],
            toolchain=self.toolchain, engine=LaTeXEngine.LUALATEX,
            project_scope=self.project, root_file=self.root,
            output_dir=kwargs.pop("output_dir", self.output), **kwargs)

    def test_only_verified_wrapped_launch_receives_absolute_input_policy(self):
        observed = {}
        def verify(profile, environment, guard, cwd):
            self.assertEqual(cwd, self.project)
            self.assertEqual(environment["openin_any"], "p")
            self.assertNotIn("SECRET_TEST_VALUE", environment)
            self.assertNotIn("PERL5LIB", environment)
            observed.update(profile=profile, guard=guard)
        with patch.dict(os.environ, {"SECRET_TEST_VALUE": "synthetic", "PERL5LIB": "/outside"}), \
                patch.object(sandbox, "_verify_kernel", side_effect=verify):
            with self.launch() as launch:
                self.assertEqual(launch.command[:2], [str(self.engine), "-p"])
                self.assertIn("-no-shell-escape", launch.command)
                self.assertEqual(launch.environment["openin_any"], "a")
                self.assertEqual(launch.environment["openout_any"], "p")
                self.assertTrue(observed["guard"].exists())
                self.assertIn(json.dumps(str(self.project)), observed["profile"])
                self.assertNotIn("(allow network", observed["profile"])
                self.assertIn("(allow process-fork)", observed["profile"])
                self.assertNotIn('(subpath "/usr/bin")', observed["profile"])
                self.assertNotIn('(import "system.sb")', observed["profile"])
        self.assertFalse(observed["guard"].exists())

    def test_missing_sandbox_and_failed_guard_never_yield_a_launch(self):
        with patch.object(sandbox, "SANDBOX_EXEC", self.base / "missing"):
            with self.assertRaisesRegex(OSError, "unavailable"):
                with self.launch():
                    self.fail("must not yield")
        with patch.object(sandbox, "_verify_kernel", side_effect=OSError("guard failed")):
            with self.assertRaisesRegex(OSError, "guard failed"):
                with self.launch():
                    self.fail("must not yield")

    def test_external_tools_output_overlay_and_symlink_cache_are_refused(self):
        with patch.object(sandbox, "_verify_kernel") as guard:
            with self.assertRaises(OSError):
                with self.launch(output_dir=self.base):
                    self.fail("unsafe output")
            with self.assertRaises(OSError):
                with self.launch(overlay_dir=self.base):
                    self.fail("unsafe overlay")
            (self.output / ".sandbox-cache").symlink_to(self.base)
            with self.assertRaises(OSError):
                with self.launch():
                    self.fail("unsafe cache")
            guard.assert_not_called()
        external = LaTeXToolchain("/usr/bin/true", None, lualatex=str(self.engine))
        with self.assertRaises(OSError):
            sandbox._tool_paths(external, LaTeXEngine.LUALATEX)

    def test_guard_nonzero_wrong_marker_and_timeout_fail_closed(self):
        for index, result in enumerate((
            subprocess.CompletedProcess([], 1, "", "denied"),
            subprocess.CompletedProcess([], 0, "unexpected", ""),
            subprocess.TimeoutExpired([], 5),
        )):
            directory = self.base / f"guard-{index}"
            directory.mkdir()
            with self.subTest(result=result), patch.object(sandbox.subprocess, "run") as run:
                if isinstance(result, Exception):
                    run.side_effect = result
                else:
                    run.return_value = result
                with self.assertRaises(OSError):
                    sandbox._verify_kernel("profile", {}, directory, self.project)
                self.assertEqual(run.call_args.kwargs["timeout"], sandbox.GUARD_TIMEOUT_SECONDS)
                self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_preexisting_hardlinked_output_is_refused_before_guard(self):
        os.link(self.root, self.output / "aliased-source")
        with patch.object(sandbox, "_verify_kernel") as guard:
            with self.assertRaisesRegex(OSError, "Hardlinked"):
                with self.launch():
                    self.fail("hardlink permitted")
            guard.assert_not_called()
        self.assertEqual(self.root.read_text(), "synthetic")


class SandboxCompileIntegrationTests(TestCase):
    @patch("app.core.compiler.sys.platform", "darwin")
    def test_stop_during_guard_prevents_compile_launch_and_cleans_up(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            root.write_text("synthetic")
            manager = CompileManager(root, toolchain=LaTeXToolchain(None, "/bin/pdflatex"), restricted_io=True)
            closed = []
            @contextmanager
            def launch(command, **kwargs):
                manager.stop_current(timeout=0)
                try:
                    yield sandbox.SandboxLaunch(command, {})
                finally:
                    closed.append(True)
            with patch("app.core.compiler.macos_sandbox_launch", side_effect=launch), \
                    patch("app.core.compiler.subprocess.Popen") as popen:
                result = manager.compile_now()
            self.assertEqual(result.outcome, CompileOutcome.STOPPED)
            self.assertEqual(closed, [True])
            popen.assert_not_called()

    @patch("app.core.compiler.sys.platform", "darwin")
    def test_guard_time_is_charged_to_compile_deadline(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            root.write_text("synthetic")
            manager = CompileManager(root, toolchain=LaTeXToolchain(None, "/bin/pdflatex"), restricted_io=True)
            @contextmanager
            def launch(command, **kwargs):
                yield sandbox.SandboxLaunch(command, {})
            with patch("app.core.compiler.macos_sandbox_launch", side_effect=launch), \
                    patch("app.core.compiler.time.perf_counter", side_effect=[0, 2, 2]), \
                    patch("app.core.compiler.subprocess.Popen") as popen:
                result = manager._run_compile(1, BuildPurpose.FINAL, timeout_seconds=1)
            self.assertEqual(result.outcome, CompileOutcome.TIMEOUT)
            popen.assert_not_called()

    @patch("app.core.compiler.sys.platform", "darwin")
    def test_restricted_compile_uses_frozen_engine_and_closes_sandbox(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            root.write_text("synthetic")
            toolchain = LaTeXToolchain("/bin/latexmk", None, lualatex="/bin/lualatex")
            manager = CompileManager(root, toolchain=toolchain,
                restricted_io=True, engine=LaTeXEngine.LUALATEX)
            def prepare(*_):
                manager.restricted_io = False
                manager.engine = LaTeXEngine.XELATEX
                return PreviewPreparation()
            manager.preview_preparer = prepare
            state = []
            @contextmanager
            def launch(command, **kwargs):
                self.assertEqual(kwargs["engine"], LaTeXEngine.LUALATEX)
                self.assertEqual(kwargs["toolchain"], toolchain)
                state.append("entered")
                try:
                    yield sandbox.SandboxLaunch(["sandbox", *command], {"openin_any": "a"})
                finally:
                    state.append("closed")
            class Process:
                returncode = 0
                def communicate(self, timeout=None):
                    self_test.assertEqual(state, ["entered"])
                    manager.pdf_file_for(BuildPurpose.PREVIEW).write_bytes(b"%PDF-1.4 synthetic")
                    return "", ""
            self_test = self
            with patch("app.core.compiler.macos_sandbox_launch", side_effect=launch), \
                    patch("app.core.compiler.subprocess.Popen", return_value=Process()) as popen:
                result = manager.compile_now(BuildPurpose.PREVIEW)
            self.assertTrue(result.ok)
            self.assertEqual(state, ["entered", "closed"])
            self.assertEqual(result.command[:2], ["sandbox", "/bin/latexmk"])
            self.assertIn("-norc", result.command)
            self.assertEqual(popen.call_args.kwargs["env"]["openin_any"], "a")
            self.assertTrue(popen.call_args.kwargs["start_new_session"])
            self.assertTrue(popen.call_args.kwargs["close_fds"])

    @patch("app.core.compiler.sys.platform", "darwin")
    def test_guard_failure_does_not_launch_unisolated_compiler(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            root.write_text("synthetic")
            manager = CompileManager(root, toolchain=LaTeXToolchain(None, "/bin/pdflatex"), restricted_io=True)
            with patch("app.core.compiler.macos_sandbox_launch", side_effect=OSError("isolation unavailable")), \
                    patch("app.core.compiler.subprocess.Popen") as popen:
                result = manager.compile_now()
            popen.assert_not_called()
            self.assertEqual(result.outcome, CompileOutcome.PROCESS_START_FAILED)
            self.assertIn("isolation unavailable", result.stderr)

    @patch("app.core.compiler.sys.platform", "darwin")
    def test_ordinary_gui_policy_does_not_enter_sandbox(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            root.write_text("synthetic")
            manager = CompileManager(root, toolchain=LaTeXToolchain(None, "/bin/pdflatex"))
            with patch("app.core.compiler.macos_sandbox_launch") as launch, \
                    patch("app.core.compiler.subprocess.Popen", side_effect=OSError("synthetic stop")):
                manager.compile_now()
            launch.assert_not_called()
