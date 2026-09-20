from __future__ import annotations

import inspect
import os
import signal
import subprocess
import sys
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


class PythonToolchain(LaTeXToolchain):
    """Use a real portable process; only replace the external compiler command."""
    def compile_command(self, root_file, output_dir, engine=LaTeXEngine.AUTO):
        return [sys.executable, "-u", str(root_file.parent / "fake_compiler.py")]


def python_manager(tex: Path, script: str) -> CompileManager:
    (tex.parent / "fake_compiler.py").write_text(
        "import os, signal, subprocess, sys, time\nfrom pathlib import Path\n" + script + "\n",
        encoding="utf-8",
    )
    return CompileManager(tex, toolchain=PythonToolchain(latexmk=None, pdflatex=sys.executable), debounce_ms=1)


class CompileManagerTests(TestCase):
    @patch("app.core.compiler.sys.platform", "linux")
    def test_fast_lossless_compression_is_only_for_unrestricted_xelatex_preview(self):
        for engine in (LaTeXEngine.XELATEX, LaTeXEngine.PDFLATEX, LaTeXEngine.LUALATEX):
            for purpose in (BuildPurpose.PREVIEW, BuildPurpose.FINAL):
                for restricted in (False, True):
                    with self.subTest(engine=engine, purpose=purpose, restricted=restricted), TemporaryDirectory() as directory:
                        root = Path(directory) / "main.tex"
                        root.write_text("\\documentclass{article}", encoding="utf-8")
                        manager = CompileManager(root, engine=engine, restricted_io=restricted,
                            toolchain=LaTeXToolchain("/bin/latexmk", "/bin/pdflatex", "/bin/xelatex", "/bin/lualatex"))

                        class FakeProcess:
                            returncode = 1

                            def communicate(self, timeout=None):
                                return "", ""

                        with patch("app.core.compiler.subprocess.Popen", return_value=FakeProcess()) as popen:
                            manager.compile_now(purpose)
                        command = popen.call_args.args[0]
                        optimized = engine is LaTeXEngine.XELATEX and purpose is BuildPurpose.PREVIEW and not restricted
                        self.assertEqual("-e" in command, optimized)
                        if optimized:
                            self.assertIn("-z 1", command[command.index("-e") + 1])
                        self.assertIn("-no-shell-escape", command)
                        self.assertIn("-norc", command)
                        self.assertEqual("-g" in command, purpose is BuildPurpose.FINAL)

    def test_final_captures_only_actual_stdout_without_another_tool_process(self) -> None:
        from app.core.build_evidence import final_build_evidence
        from tests.test_build_tool_versions import PDF
        for purpose in (BuildPurpose.FINAL, BuildPurpose.PREVIEW):
            with self.subTest(purpose=purpose), TemporaryDirectory() as directory:
                root = Path(directory) / "main.tex"
                root.write_text("\\documentclass{article}", encoding="utf-8")
                manager = CompileManager(root, toolchain=LaTeXToolchain(None, "/bin/pdflatex"))
                manager.set_input_revision(17)

                class FakeProcess:
                    returncode = 0

                    def communicate(self, timeout=None):
                        manager.pdf_file_for(purpose).write_bytes(b"%PDF-1.4 synthetic")
                        # Cached log is not version evidence; current stdout is.
                        manager.log_file_for(purpose).write_text(PDF.replace("1.40.27", "1.40.99"))
                        return PDF, "This is pdfTeX, Version 9.9"

                with patch("app.core.compiler.subprocess.Popen", return_value=FakeProcess()) as popen:
                    result = manager.compile_now(purpose)
                self.assertEqual(popen.call_count, 1)
                self.assertTrue(result.ok)
                if purpose is BuildPurpose.FINAL:
                    self.assertEqual(result.tool_versions.engine.version, "3.141592653-2.6-1.40.27")
                    proof = final_build_evidence(result)
                    self.assertEqual(proof.job_key.source_revision, 17)
                    self.assertIs(proof.tool_versions, result.tool_versions)
                    manager.engine = LaTeXEngine.XELATEX
                    self.assertEqual(proof.tool_versions.engine.program, "pdfTeX")
                else:
                    self.assertIsNone(result.tool_versions)
                    self.assertIsNone(final_build_evidence(result))

    def test_final_forces_latexmk_rules_without_cleaning_or_changing_preview(self) -> None:
        for driver in (None, "/bin/latexmk"):
            for purpose in (BuildPurpose.FINAL, BuildPurpose.PREVIEW):
                with self.subTest(driver=driver, purpose=purpose), TemporaryDirectory() as directory:
                    tex = Path(directory) / "main.tex"
                    tex.write_text("\\documentclass{article}", encoding="utf-8")
                    manager = CompileManager(
                        tex, toolchain=LaTeXToolchain(latexmk=driver, pdflatex="/bin/pdflatex"),
                    )
                    pdf = manager.pdf_file_for(purpose)
                    pdf.parent.mkdir(parents=True)
                    pdf.write_bytes(b"%PDF-1.4 cached but unrelated")

                    class FakeProcess:
                        returncode = 0

                        def communicate(self, timeout=None):
                            return "", ""

                    with patch("app.core.compiler.subprocess.Popen", return_value=FakeProcess()) as popen:
                        result = manager.compile_now(purpose)
                    self.assertIsNotNone(result)
                    command = popen.call_args.args[0]
                    self.assertEqual("-g" in command, bool(driver and purpose is BuildPurpose.FINAL))
                    self.assertFalse({"-gg", "-C", "-c", "-f"}.intersection(command))
                    self.assertIn("-no-shell-escape", command)
                    if driver:
                        self.assertIn("-norc", command)
                    self.assertEqual(pdf.read_bytes(), b"%PDF-1.4 cached but unrelated")

    @patch("app.core.compiler.sys.platform", "linux")
    def test_non_macos_restricted_io_keeps_relative_arguments_and_paranoid_environment(self) -> None:
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

    def _started_manager(self, body: str):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        tex = root / "main.tex"
        tex.write_text("\\documentclass{article}", encoding="utf-8")
        manager = python_manager(tex, body)
        self.addCleanup(lambda: manager.retire(3))
        manager.compile_async()
        ready = root / "ready"
        deadline = time.monotonic() + 5
        while not ready.exists() and manager.is_busy and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(ready.exists(), "fixture did not finish process/signal setup")
        self.assertIsNotNone(manager._process)
        return manager, manager._process, ready

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
            popen.call_args.kwargs["env"]["TEXINPUTS"].startswith(overlay.resolve().as_posix())
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

    def test_timeout_cleanup_signals_children_even_after_leader_exit(self) -> None:
        from unittest.mock import Mock, call
        process = Mock()
        process.wait.return_value = 0
        with patch.object(CompileManager, "_signal_process_tree") as signal_tree:
            CompileManager._terminate_process(process)
        self.assertEqual(signal_tree.call_args_list, [
            call(process, force=False, budget=0.5),
            call(process, force=True, budget=0.5),
        ])

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

            self.assertEqual(thread_type.call_args.kwargs["args"][0].key.purpose, BuildPurpose.FINAL)
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

    def test_pending_deadline_keeps_only_unelapsed_debounce(self) -> None:
        for finished_at, remaining in ((10.4, 0.3), (12.0, 0.0)):
            with self.subTest(finished_at=finished_at), TemporaryDirectory() as directory:
                manager = CompileManager(
                    Path(directory) / "main.tex", debounce_ms=700,
                    toolchain=LaTeXToolchain(None, None),
                )
                with patch("app.core.compiler.time.monotonic", return_value=9.0) as now, \
                     patch("app.core.compiler.threading.Timer") as timer:
                    def running(build_id, purpose, **kwargs):
                        now.return_value = 10.0
                        manager.set_input_revision(7, 3)
                        manager.schedule_compile("edit", BuildPurpose.PREVIEW)
                        now.return_value = finished_at
                        return manager._simple_result(
                            build_id, CompileOutcome.LATEX_ERROR, returncode=1,
                            stderr="test", purpose=purpose,
                        )

                    with patch.object(manager, "_run_compile", side_effect=running):
                        manager.compile_now()
                    self.assertAlmostEqual(timer.call_args.args[0], remaining)
                    self.assertEqual(manager._scheduled_request.key.source_revision, 7)
                    self.assertEqual(manager._scheduled_request.key.dependency_generation, 3)
                    self.assertEqual(manager._scheduled_request.key.purpose, BuildPurpose.PREVIEW)
                    manager.cancel_pending()

    def test_async_burst_has_one_worker_and_latest_pending_identity(self) -> None:
        manager = CompileManager("/tmp/main.tex", toolchain=LaTeXToolchain(None, None))
        with patch("app.core.compiler.threading.Thread") as thread:
            manager.compile_async(BuildPurpose.PREVIEW)
            for revision in range(1, 101):
                manager.set_input_revision(revision, revision // 2)
                purpose = BuildPurpose.FINAL if revision == 2 else BuildPurpose.PREVIEW
                manager.compile_async(purpose)
            self.assertEqual(thread.call_count, 1)
            self.assertEqual(manager._pending_request.key.source_revision, 100)
            self.assertEqual(manager._pending_request.key.dependency_generation, 50)
            self.assertEqual(manager._pending_request.key.purpose, BuildPurpose.FINAL)
            manager.cancel_pending()

    def test_cancel_invalidates_timer_and_already_launched_request(self) -> None:
        manager = CompileManager("/tmp/main.tex", toolchain=LaTeXToolchain(None, None))
        with patch("app.core.compiler.threading.Timer"), \
             patch("app.core.compiler.threading.Thread") as thread:
            manager.schedule_compile()
            stale_generation = manager._timer_generation
            manager.cancel_pending()
            manager._fire_scheduled_compile(stale_generation, BuildPurpose.FINAL)
            thread.assert_not_called()
            manager.compile_async()
            request = thread.call_args.kwargs["args"][0]
            manager.cancel_pending()
            with patch.object(manager, "_run_compile") as run:
                manager._run_async(request)
            run.assert_not_called()
            self.assertTrue(manager.wait_until_idle(0))

    @patch("app.core.compiler.sys.platform", "linux")
    def test_job_configuration_and_recorder_are_captured_before_callback(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            tex = root / "main.tex"
            tex.write_text("x")
            toolchain = LaTeXToolchain(None, "/bin/pdflatex")
            manager = CompileManager(tex, toolchain=toolchain, restricted_io=True)
            manager.set_input_revision(4, 2)

            def prepare(_root, _output):
                manager.engine = LaTeXEngine.XELATEX
                manager.toolchain = LaTeXToolchain(None, None)
                manager.restricted_io = False
                manager.set_input_revision(5, 3)
                return PreviewPreparation()

            manager.preview_preparer = prepare
            output = manager.preview_output_dir

            class Process:
                returncode = 0

                def communicate(self, timeout=None):
                    (output / "main.pdf").write_bytes(b"%PDF-1.4 test")
                    (output / "main.fls").write_text("INPUT dynamic.csv\nOUTPUT main.pdf\n")
                    return "", ""

            manager.on_finished = lambda result: (output / "main.fls").write_text("INPUT changed.csv\n")
            with patch("app.core.compiler.subprocess.Popen", return_value=Process()) as popen:
                result = manager.compile_now(BuildPurpose.PREVIEW)
            self.assertTrue(result.ok)
            self.assertEqual(result.job_key.source_revision, 4)
            self.assertEqual(result.job_key.dependency_generation, 2)
            self.assertEqual(result.job_key.toolchain, toolchain)
            self.assertEqual(result.command[0], "/bin/pdflatex")
            self.assertEqual(popen.call_args.kwargs["env"]["openin_any"], "p")
            self.assertIn(root / "dynamic.csv", result.recorder_inputs)
            self.assertNotIn(root / "changed.csv", result.recorder_inputs)

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
        manager, process, _ = self._started_manager("Path('ready').touch()\ntime.sleep(120)")
        self.assertTrue(manager.stop_current())
        self.assertFalse(manager.is_running)
        self.assertIsNotNone(process.poll())

    def test_stop_current_confirms_exit_before_returning(self) -> None:
        # A real LaTeX run is latexmk driving child pdflatex/bibtex processes.
        # stop_current() must not return until the process is actually gone,
        # otherwise callers that immediately rmtree() the build dir can race
        # with a still-writing process (see clean_build_cache()).
        manager, process, _ = self._started_manager("Path('ready').touch()\ntime.sleep(120)")
        self.assertTrue(manager.stop_current())
        self.assertIsNotNone(process.poll())
        self.assertTrue(manager.wait_until_idle(0))
        if os.name != "nt":
            with self.assertRaises(ProcessLookupError):
                os.kill(process.pid, 0)

    def test_stop_current_kills_unresponsive_process(self) -> None:
        manager, process, _ = self._started_manager(
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\nPath('ready').touch()\ntime.sleep(120)"
        )
        started = time.monotonic()
        self.assertTrue(manager.stop_current(timeout=0.3))
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertIsNotNone(process.poll())
        self.assertTrue(manager.wait_until_idle(0))

    def test_stop_kills_child_holding_pipe_after_parent_exits(self):
        child_code = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready',flush=True); time.sleep(120)"
        manager, process, ready = self._started_manager(
            f"child = subprocess.Popen([sys.executable, '-u', '-c', {child_code!r}], stdout=subprocess.PIPE)\n"
            "assert child.stdout.readline().strip() == b'ready'\n"
            "Path('ready').write_text(str(child.pid))\ntime.sleep(120)"
        )
        child_pid = int(ready.read_text())
        try:
            self.assertTrue(manager.stop_current(timeout=1.5))
            self.assertIsNotNone(process.poll())
            self.assertTrue(manager.wait_until_idle(0), "inherited stderr must be closed before success")
        finally:
            # Fixture-owned child cleanup also runs against the pre-fix implementation.
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(child_pid), "/T", "/F"], capture_output=True, timeout=5)
            else:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

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
        manager = python_manager(self.tex, script_body)
        self.addCleanup(lambda: manager.retire(3))
        return manager

    def _stop_and_collect(self, manager: CompileManager, ready_marker: Path | None = None) -> CompileResult:
        results: list[CompileResult] = []
        manager.on_finished = results.append
        manager.compile_async()
        deadline = time.monotonic() + 5
        while manager._process is None and manager.is_busy and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIsNotNone(manager._process, "stop classification requires a launched process")
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
        manager = self._fake_manager("sys.exit(1)")
        result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.LATEX_ERROR)

    def test_zero_exit_without_pdf_is_output_missing(self) -> None:
        manager = self._fake_manager("sys.exit(0)")
        result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.OUTPUT_MISSING)
        self.assertFalse(result.ok)

    def test_zero_exit_with_empty_pdf_is_output_missing(self) -> None:
        manager = self._fake_manager("Path('.latex_build/main.pdf').touch()")
        result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.OUTPUT_MISSING)

    def test_valid_pdf_is_success(self) -> None:
        manager = self._fake_manager(
            "Path('.latex_build/main.pdf').write_bytes(b'%PDF-1.4 fake')"
        )
        result = manager.compile_now()
        assert result is not None
        self.assertEqual(result.outcome, CompileOutcome.SUCCESS)
        self.assertTrue(result.ok)

    def test_user_stop_with_negative_returncode_is_stopped(self) -> None:
        manager = self._fake_manager("time.sleep(120)")
        result = self._stop_and_collect(manager)
        self.assertEqual(result.outcome, CompileOutcome.STOPPED)
        if os.name == "nt":
            self.assertGreater(result.returncode, 0)
        else:
            self.assertLess(result.returncode, 0)

    def test_user_stop_with_positive_returncode_is_stopped(self) -> None:
        # Windows terminate() produces a positive exit code. Mock the process
        # result directly so this test is about ICSTeX classification, not
        # platform-specific /bin/sh signal timing.
        manager = self._fake_manager("sys.exit(0)")

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
        manager = self._fake_manager("sys.exit(0)")
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
        manager = self._fake_manager("time.sleep(120)")
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
        self._assert_timeout_kills_ready_process_tree(startup_delay=0)

    @skipIf(os.name == "nt", "process groups differ on Windows")
    def test_timeout_tree_fixture_waits_for_slow_engine_startup(self) -> None:
        self._assert_timeout_kills_ready_process_tree(startup_delay=1.2)

    @skipIf(os.name == "nt", "process groups differ on Windows")
    def test_timeout_tree_fixture_detects_driver_only_termination(self) -> None:
        # A broken kill must fail before the sleeping child exits naturally;
        # the fixture's cleanup must not turn it into a false green result.
        with patch.object(CompileManager, "_terminate_process", side_effect=lambda process: process.terminate()):
            with self.assertLogs("app.core.compiler", level="ERROR") as captured:
                with self.assertRaisesRegex(AssertionError, "INTERNAL_ERROR.*TIMEOUT"):
                    self._assert_timeout_kills_ready_process_tree(startup_delay=0)
            self.assertIn("TimeoutExpired", captured.output[0])

    def _assert_timeout_kills_ready_process_tree(self, *, startup_delay: float) -> None:
        # A real driver (like latexmk) spawns an engine child that inherits the
        # stdout/stderr pipes. Killing only the driver would leave the engine
        # holding the pipe open, so the post-timeout communicate() could block
        # forever (the observed 28-minute macOS CI hang). The timeout must
        # terminate the whole process tree.
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tex = root / "main.tex"
            tex.write_text("\\documentclass{article}", encoding="utf-8")
            driver = root / "fake_compiler.py"
            driver.write_text(
                "#!/usr/bin/env python3\n"
                "import subprocess, sys, time\n"
                f"time.sleep({startup_delay!r})\n"
                "child = subprocess.Popen([sys.executable, '-c', "
                "\"import os, time; from pathlib import Path; "
                "Path('grandchild.pid').write_text(str(os.getpid())); time.sleep(30)\"])\n"
                "child.wait()\n",
                encoding="utf-8",
            )
            manager = CompileManager(
                tex,
                # Use the test interpreter, not an unrelated python3 on PATH.
                toolchain=PythonToolchain(latexmk=None, pdflatex=sys.executable),
            )

            real_popen = subprocess.Popen
            processes = []
            ready_children = []

            def ready_driver(command, **kwargs):
                process = real_popen(command, **kwargs)
                processes.append(process)
                real_communicate = process.communicate

                def bounded_communicate(input=None, timeout=None):
                    # Only bound the fixture's post-kill pipe drain. The actual
                    # production timeout remains unchanged and runs for real.
                    return real_communicate(input=input, timeout=3 if timeout is None else timeout)

                process.communicate = bounded_communicate
                # This case tests termination of an existing descendant, not
                # interpreter startup speed. Wait outside communicate's real
                # timeout; missing/failed setup is a bounded assertion failure.
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    self.assertIsNone(process.poll(), "test driver exited before engine readiness")
                    try:
                        child_pid = int((root / "grandchild.pid").read_text(encoding="utf-8"))
                    except (FileNotFoundError, ValueError):
                        time.sleep(0.01)
                        continue
                    os.kill(child_pid, 0)
                    self.assertEqual(os.getpgid(child_pid), process.pid)
                    ready_children.append(child_pid)
                    return process
                self.fail("test engine did not report readiness within 10 seconds")

            try:
                with patch("app.core.compiler.subprocess.Popen", side_effect=ready_driver):
                    result = manager.compile_now(timeout_seconds=1.0)
                self.assertIsNotNone(result)
                assert result is not None
                self.assertEqual(result.outcome, CompileOutcome.TIMEOUT)
                self.assertEqual(len(ready_children), 1)
                grandchild_pid = ready_children[0]
                dead = False
                for _ in range(30):
                    try:
                        os.kill(grandchild_pid, 0)
                    except ProcessLookupError:
                        dead = True
                        break
                    time.sleep(0.1)
                self.assertTrue(dead, "engine child survived the compile timeout")
            finally:
                # Cleanup happens after the descendant-death assertion. It
                # cannot manufacture a pass if production termination fails.
                for process in processes:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.communicate(timeout=3)
