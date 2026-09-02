from __future__ import annotations

import inspect
import os
import subprocess
import threading
from tempfile import TemporaryDirectory
from pathlib import Path
import time
from unittest import TestCase, skipIf
from unittest.mock import patch

from app.core.compiler import (
    BuildPurpose,
    CompileManager,
    CompileOutcome,
    CompileResult,
    PreviewPreparation,
)
from app.core.latex_tools import LaTeXEngine, LaTeXToolchain


class CompileManagerTests(TestCase):
    def test_restricted_io_uses_relative_arguments_and_paranoid_tex_environment(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tex = root / "main.tex"
            tex.write_text("\\documentclass{article}", encoding="utf-8")
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(
                    latexmk=None,
                    pdflatex="/bin/pdflatex",
                    texcount=None,
                    synctex=None,
                ),
                restricted_io=True,
            )

            class FakeProcess:
                returncode = 0

                def communicate(self, timeout=None):  # type: ignore[no-untyped-def]  # noqa: ARG002
                    manager.pdf_file.write_bytes(b"%PDF-1.4 restricted")
                    return "", ""

            with patch("app.core.compiler.subprocess.Popen", return_value=FakeProcess()) as popen:
                result = manager.compile_now()

        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.SUCCESS)
        command = popen.call_args.args[0]
        self.assertIn("main.tex", command)
        self.assertNotIn(str(tex), command)
        self.assertIn("-output-directory=.latex_build", command)
        self.assertEqual(popen.call_args.kwargs["env"]["openin_any"], "p")
        self.assertEqual(popen.call_args.kwargs["env"]["openout_any"], "p")

    def test_preview_uses_separate_output_and_overlay_environment(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tex = root / "main.tex"
            tex.write_text("\\documentclass{article}", encoding="utf-8")
            overlay = root / ".icstex" / "preview" / "assets"
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(
                    latexmk=None,
                    pdflatex="/bin/pdflatex",
                    texcount=None,
                    synctex=None,
                ),
                preview_preparer=lambda _root, _output: PreviewPreparation(
                    overlay_dir=overlay,
                    fidelity="proxy",
                    manifest_digest="abc",
                ),
            )

            class FakeProcess:
                returncode = 0

                def communicate(self, timeout=None):  # type: ignore[no-untyped-def]  # noqa: ARG002
                    manager.pdf_file_for(BuildPurpose.PREVIEW).write_bytes(b"%PDF-1.4 preview")
                    return "", ""

            with patch("app.core.compiler.subprocess.Popen", return_value=FakeProcess()) as popen:
                result = manager.compile_now(BuildPurpose.PREVIEW)

        assert result is not None
        self.assertEqual(result.purpose, BuildPurpose.PREVIEW)
        self.assertNotEqual(result.output_dir, manager.output_dir)
        self.assertEqual(result.preview_fidelity, "proxy")
        self.assertTrue(
            popen.call_args.kwargs["env"]["TEXINPUTS"].startswith(str(overlay.resolve()))
        )

    def test_explicit_timeout_terminates_and_reports_timeout(self) -> None:
        class HangingProcess:
            returncode: int | None = None
            terminated = False
            killed = False

            def communicate(self, timeout: float | None = None) -> tuple[str, str]:
                if timeout is not None:
                    time.sleep(0.2)
                    raise subprocess.TimeoutExpired(cmd="latexmk", timeout=timeout)
                self.returncode = -9
                return "stdout", "stderr"

            def terminate(self) -> None:
                self.terminated = True

            def wait(self, timeout: float | None = None) -> int:
                if self.terminated:
                    return self.returncode or 0
                raise subprocess.TimeoutExpired(cmd="latexmk", timeout=timeout or 1)

            def kill(self) -> None:
                self.killed = True

        with TemporaryDirectory() as directory:
            tex = Path(directory) / "main.tex"
            tex.write_text("\\documentclass{article}", encoding="utf-8")
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(latexmk="/bin/latexmk", pdflatex=None, texcount=None, synctex=None),
            )
            process = HangingProcess()
            with patch("app.core.compiler.subprocess.Popen", return_value=process):
                start = time.monotonic()
                result = manager.compile_now(timeout_seconds=0.05)
                elapsed = time.monotonic() - start

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.TIMEOUT)
        self.assertLess(elapsed, 2.0)
        self.assertTrue(process.terminated)

    def test_pending_final_request_cannot_be_downgraded_by_preview(self) -> None:
        with TemporaryDirectory() as directory:
            tex = Path(directory) / "main.tex"
            tex.write_text("x", encoding="utf-8")
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(
                    latexmk=None,
                    pdflatex="/bin/pdflatex",
                    texcount=None,
                    synctex=None,
                ),
            )
            with manager._lock:
                manager._running = True

            self.assertIsNone(manager.compile_now(BuildPurpose.FINAL))
            self.assertIsNone(manager.compile_now(BuildPurpose.PREVIEW))

            self.assertEqual(manager._pending_purpose, BuildPurpose.FINAL)

    def test_scheduled_final_request_cannot_be_downgraded_by_preview(self) -> None:
        with TemporaryDirectory() as directory:
            tex = Path(directory) / "main.tex"
            tex.write_text("x", encoding="utf-8")
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(latexmk=None, pdflatex="/bin/pdflatex"),
            )

            class FakeTimer:
                daemon = False

                def cancel(self) -> None:
                    pass

                def start(self) -> None:
                    pass

            with patch("app.core.compiler.threading.Timer", return_value=FakeTimer()):
                manager.schedule_compile("export", BuildPurpose.FINAL)
                manager.schedule_compile("auto preview", BuildPurpose.PREVIEW)

            self.assertEqual(manager._scheduled_purpose, BuildPurpose.FINAL)

    def test_compile_async_merges_scheduled_final_before_starting_thread(self) -> None:
        with TemporaryDirectory() as directory:
            tex = Path(directory) / "main.tex"
            tex.write_text("x", encoding="utf-8")
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(latexmk=None, pdflatex="/bin/pdflatex"),
            )
            manager._scheduled_purpose = BuildPurpose.FINAL

            with patch("app.core.compiler.threading.Thread") as thread_type:
                manager.compile_async(BuildPurpose.PREVIEW)

            self.assertEqual(thread_type.call_args.kwargs["args"], (BuildPurpose.FINAL,))
            self.assertIsNone(manager._scheduled_purpose)

    def test_missing_compiler_returns_friendly_result(self) -> None:
        with TemporaryDirectory() as directory:
            tex = Path(directory) / "main.tex"
            tex.write_text("\\documentclass{article}", encoding="utf-8")
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
                debounce_ms=1,
            )

            result = manager.compile_now()

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.returncode, 127)
        self.assertIn("未找到 LaTeX 编译器", result.stderr)

    def test_missing_root_file_returns_error(self) -> None:
        with TemporaryDirectory() as directory:
            manager = CompileManager(
                Path(directory) / "missing.tex",
                toolchain=LaTeXToolchain(latexmk="/bin/latexmk", pdflatex=None, texcount=None, synctex=None),
            )

            result = manager.compile_now()

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.returncode, 2)
        self.assertIn("根 LaTeX 文件不存在", result.stderr)

    def test_missing_selected_engine_returns_friendly_result(self) -> None:
        with TemporaryDirectory() as directory:
            tex = Path(directory) / "main.tex"
            tex.write_text("\\documentclass{article}", encoding="utf-8")
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(latexmk="/bin/latexmk", pdflatex="/bin/pdflatex"),
                engine=LaTeXEngine.XELATEX,
            )

            result = manager.compile_now()

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.returncode, 127)
        self.assertIn("XeLaTeX 不在 PATH 中", result.stderr)

    def test_running_compile_can_be_stopped(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tex = root / "main.tex"
            tex.write_text("\\documentclass{article}", encoding="utf-8")
            fake_compiler = root / "fake-pdflatex.sh"
            fake_compiler.write_text("#!/bin/sh\nsleep 10\n", encoding="utf-8")
            fake_compiler.chmod(0o755)
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(latexmk=None, pdflatex=str(fake_compiler), texcount=None, synctex=None),
                debounce_ms=1,
            )

            manager.compile_async()
            stopped = False
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if manager.stop_current():
                    stopped = True
                    break
                time.sleep(0.05)

            self.assertTrue(stopped)
            deadline = time.monotonic() + 2
            while manager.is_running and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(manager.is_running)

    def test_stop_current_confirms_exit_before_returning(self) -> None:
        # A real LaTeX run is latexmk driving child pdflatex/bibtex processes.
        # stop_current() must not return until the process is actually gone,
        # otherwise callers that immediately rmtree() the build dir can race
        # with a still-writing process (see clean_build_cache()).
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tex = root / "main.tex"
            tex.write_text("\\documentclass{article}", encoding="utf-8")
            fake_compiler = root / "fake-pdflatex.sh"
            fake_compiler.write_text("#!/bin/sh\nsleep 10\n", encoding="utf-8")
            fake_compiler.chmod(0o755)
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(latexmk=None, pdflatex=str(fake_compiler), texcount=None, synctex=None),
                debounce_ms=1,
            )

            manager.compile_async()
            deadline = time.monotonic() + 2
            while manager._process is None and time.monotonic() < deadline:
                time.sleep(0.02)
            pid = manager._process.pid

            stopped = manager.stop_current()

            self.assertTrue(stopped)
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_stop_current_kills_unresponsive_process(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tex = root / "main.tex"
            tex.write_text("\\documentclass{article}", encoding="utf-8")
            fake_compiler = root / "fake-pdflatex.sh"
            fake_compiler.write_text(
                "#!/bin/sh\ntrap '' TERM\nsleep 10\n",
                encoding="utf-8",
            )
            fake_compiler.chmod(0o755)
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(latexmk=None, pdflatex=str(fake_compiler), texcount=None, synctex=None),
                debounce_ms=1,
            )

            manager.compile_async()
            deadline = time.monotonic() + 2
            while manager._process is None and time.monotonic() < deadline:
                time.sleep(0.02)
            pid = manager._process.pid

            stopped = manager.stop_current(timeout=0.3)

            self.assertTrue(stopped)
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_stop_during_preview_preparation_waits_and_skips_subprocess(self) -> None:
        with TemporaryDirectory() as directory:
            tex = Path(directory) / "main.tex"
            tex.write_text("x", encoding="utf-8")
            preparation_started = threading.Event()
            release_preparation = threading.Event()
            results: list[CompileResult] = []

            def prepare(_root: Path, _output: Path) -> PreviewPreparation:
                preparation_started.set()
                release_preparation.wait(2)
                return PreviewPreparation()

            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(latexmk=None, pdflatex="/bin/pdflatex"),
                preview_preparer=prepare,
            )
            manager.on_finished = results.append

            with patch("app.core.compiler.subprocess.Popen") as popen:
                manager.compile_async(BuildPurpose.PREVIEW)
                self.assertTrue(preparation_started.wait(1))
                stopped: list[bool] = []
                stopper = threading.Thread(
                    target=lambda: stopped.append(manager.stop_current(timeout=1.0))
                )
                stopper.start()
                time.sleep(0.05)
                self.assertTrue(stopper.is_alive(), "stop_current did not wait for preparation")
                release_preparation.set()
                stopper.join(1)

            self.assertEqual(stopped, [True])
            self.assertTrue(manager.wait_until_idle(0))
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].outcome, CompileOutcome.STOPPED)
            popen.assert_not_called()

    def test_stop_before_worker_enters_compile_does_not_poison_next_build(self) -> None:
        with TemporaryDirectory() as directory:
            tex = Path(directory) / "main.tex"
            tex.write_text("x", encoding="utf-8")
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(latexmk=None, pdflatex="/bin/pdflatex"),
            )
            worker_entered = threading.Event()
            release_worker = threading.Event()
            original_compile_now = manager.compile_now

            def delayed_compile(purpose: BuildPurpose, **kwargs) -> CompileResult | None:  # noqa: ARG001
                worker_entered.set()
                release_worker.wait(1)
                return original_compile_now(purpose)

            try:
                with patch.object(manager, "compile_now", side_effect=delayed_compile):
                    manager.compile_async(BuildPurpose.PREVIEW)
                    self.assertTrue(worker_entered.wait(1))
                    self.assertFalse(manager.stop_current(timeout=0.02))
                    release_worker.set()
                    self.assertTrue(manager.wait_until_idle(1))
            finally:
                release_worker.set()

            self.assertFalse(manager._stop_requested)
            manager.toolchain = LaTeXToolchain(latexmk=None, pdflatex=None)
            next_result = manager.compile_now(BuildPurpose.FINAL)
            self.assertIsNotNone(next_result)
            assert next_result is not None
            self.assertEqual(next_result.outcome, CompileOutcome.TOOLCHAIN_MISSING)


class CompileOutcomeTests(TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root_dir = Path(self._tmp.name)
        self.tex = self.root_dir / "main.tex"
        self.tex.write_text("\\documentclass{article}", encoding="utf-8")

    def _fake_manager(self, script_body: str) -> CompileManager:
        fake_compiler = self.root_dir / "fake-pdflatex.sh"
        fake_compiler.write_text(f"#!/bin/sh\n{script_body}\n", encoding="utf-8")
        fake_compiler.chmod(0o755)
        return CompileManager(
            self.tex,
            toolchain=LaTeXToolchain(latexmk=None, pdflatex=str(fake_compiler), texcount=None, synctex=None),
            debounce_ms=1,
        )

    def _stop_and_collect(self, manager: CompileManager, ready_marker: Path | None = None) -> CompileResult:
        results: list[CompileResult] = []
        manager.on_finished = results.append
        manager.compile_async()
        if ready_marker is not None:
            deadline = time.monotonic() + 2
            while not ready_marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if manager.stop_current():
                break
            time.sleep(0.05)
        deadline = time.monotonic() + 5
        while not results and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(results, "stopped compile never reported a result")
        return results[0]

    def test_missing_root_is_root_file_missing(self) -> None:
        manager = CompileManager(
            self.root_dir / "missing.tex",
            toolchain=LaTeXToolchain(latexmk="/bin/latexmk", pdflatex=None, texcount=None, synctex=None),
        )
        result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.ROOT_FILE_MISSING)
        self.assertFalse(result.ok)

    def test_missing_engine_is_toolchain_missing(self) -> None:
        manager = CompileManager(
            self.tex,
            toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
        )
        result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.TOOLCHAIN_MISSING)

    def test_unlaunchable_compiler_is_process_start_failed(self) -> None:
        not_executable = self.root_dir / "not-executable"
        not_executable.write_text("plain text", encoding="utf-8")
        manager = CompileManager(
            self.tex,
            toolchain=LaTeXToolchain(latexmk=None, pdflatex=str(not_executable), texcount=None, synctex=None),
        )
        result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.PROCESS_START_FAILED)
        self.assertFalse(result.ok)

    def test_nonzero_exit_is_latex_error(self) -> None:
        manager = self._fake_manager("exit 1")
        result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.LATEX_ERROR)

    def test_zero_exit_without_pdf_is_output_missing(self) -> None:
        manager = self._fake_manager("exit 0")
        result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.OUTPUT_MISSING)
        self.assertFalse(result.ok)

    def test_zero_exit_with_empty_pdf_is_output_missing(self) -> None:
        manager = self._fake_manager("mkdir -p .latex_build && : > .latex_build/main.pdf")
        result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.OUTPUT_MISSING)

    def test_valid_pdf_is_success(self) -> None:
        manager = self._fake_manager(
            "mkdir -p .latex_build && printf '%%PDF-1.4 fake' > .latex_build/main.pdf"
        )
        result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.SUCCESS)
        self.assertTrue(result.ok)

    def test_user_stop_with_negative_returncode_is_stopped(self) -> None:
        manager = self._fake_manager("sleep 10")
        result = self._stop_and_collect(manager)
        self.assertEqual(result.outcome, CompileOutcome.STOPPED)
        self.assertLess(result.returncode, 0)

    def test_user_stop_with_positive_returncode_is_stopped(self) -> None:
        # Windows terminate() produces a positive exit code. Mock the process
        # result directly so this test is about ICSTeX classification, not
        # platform-specific /bin/sh signal timing.
        manager = self._fake_manager("exit 0")

        class FakeProcess:
            returncode = 3

            def communicate(self, timeout=None):  # type: ignore[no-untyped-def]  # noqa: ARG002
                with manager._lock:
                    manager._stop_requested = True
                return "", ""

        with patch("app.core.compiler.subprocess.Popen", return_value=FakeProcess()):
            result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.STOPPED)
        self.assertGreater(result.returncode, 0)

    def test_internal_failure_is_internal_error_and_does_not_raise(self) -> None:
        manager = self._fake_manager("exit 0")
        results: list[CompileResult] = []
        manager.on_finished = results.append
        with patch.object(CompileManager, "_run_compile", side_effect=RuntimeError("boom")), self.assertLogs(
            "app.core.compiler", level="ERROR"
        ):
            result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.INTERNAL_ERROR)
        self.assertIn("boom", result.stderr)
        self.assertEqual(results, [result])

    def test_second_compile_while_running_queues_instead_of_running_parallel(self) -> None:
        manager = self._fake_manager("sleep 5")
        manager.compile_async()
        deadline = time.monotonic() + 2
        while not manager.is_running and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(manager.is_running)

        # A shared root+child manager must serialize: the second request is
        # queued, never a second concurrent process on the same .latex_build.
        self.assertIsNone(manager.compile_now())

        deadline = time.monotonic() + 2
        while not manager.stop_current() and time.monotonic() < deadline:
            time.sleep(0.02)
        deadline = time.monotonic() + 2
        while manager.is_running and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(manager.is_running)

    def test_compile_timeout_is_finite_by_default(self) -> None:
        signature = inspect.signature(CompileManager.compile_now)
        self.assertEqual(signature.parameters["timeout_seconds"].default, 300.0)

    @skipIf(os.name == "nt", "process groups differ on Windows")
    def test_timeout_kills_entire_process_tree(self) -> None:
        # A real driver (like latexmk) spawns an engine child that inherits the
        # stdout/stderr pipes. Killing only the driver would leave the engine
        # holding the pipe open, so the post-timeout communicate() could block
        # forever (the observed 28-minute macOS CI hang). The timeout must
        # terminate the whole process tree.
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tex = root / "main.tex"
            tex.write_text("\\documentclass{article}", encoding="utf-8")
            driver = root / "fake-driver.py"
            driver.write_text(
                "#!/usr/bin/env python3\n"
                "import subprocess, sys\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
                "open('grandchild.pid', 'w').write(str(child.pid))\n"
                "child.wait()\n",
                encoding="utf-8",
            )
            driver.chmod(0o755)
            manager = CompileManager(
                tex,
                toolchain=LaTeXToolchain(
                    latexmk=str(driver),
                    pdflatex=None,
                    texcount=None,
                    synctex=None,
                ),
            )

            result = manager.compile_now(timeout_seconds=1.0)

            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.outcome, CompileOutcome.TIMEOUT)
            grandchild_pid = int((root / "grandchild.pid").read_text(encoding="utf-8").strip())
            dead = False
            for _ in range(30):
                try:
                    os.kill(grandchild_pid, 0)
                except ProcessLookupError:
                    dead = True
                    break
                time.sleep(0.1)
            self.assertTrue(dead, "engine child survived the compile timeout")
