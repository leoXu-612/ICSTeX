from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from itertools import count
import logging
from pathlib import Path
import subprocess
import threading
import time
from typing import Callable

from app.core.latex_tools import LaTeXEngine, LaTeXToolchain, detect_toolchain
from app.core.log_parser import LaTeXError, parse_latex_errors, parse_log_file
from app.core.paths import (
    build_dir_for,
    built_log_for,
    built_pdf_for,
    normalize_path,
    preview_build_dir_for,
)
from app.core.process_env import latex_subprocess_env


logger = logging.getLogger(__name__)

# Shared across managers so two tabs compiling the same root still get
# strictly ordered build ids; the GUI uses them to drop late stale results.
_BUILD_IDS = count(1)


class CompileOutcome(Enum):
    SUCCESS = "success"
    STOPPED = "stopped"
    TIMEOUT = "timeout"
    TOOLCHAIN_MISSING = "toolchain_missing"
    ROOT_FILE_MISSING = "root_file_missing"
    PROCESS_START_FAILED = "process_start_failed"
    LATEX_ERROR = "latex_error"
    OUTPUT_MISSING = "output_missing"
    INTERNAL_ERROR = "internal_error"


class BuildPurpose(str, Enum):
    PREVIEW = "preview"
    FINAL = "final"


@dataclass(frozen=True)
class PreviewPreparation:
    overlay_dir: Path | None = None
    fidelity: str = "original_fallback"
    manifest_digest: str | None = None
    asset_paths: tuple[Path, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class CompileResult:
    root_file: Path
    output_dir: Path
    pdf_file: Path
    log_file: Path
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    outcome: CompileOutcome
    errors: list[LaTeXError] = field(default_factory=list)
    build_id: int = 0
    purpose: BuildPurpose = BuildPurpose.FINAL
    preview_fidelity: str | None = None
    preview_manifest_digest: str | None = None
    preview_asset_paths: tuple[Path, ...] = ()

    @property
    def ok(self) -> bool:
        return self.outcome is CompileOutcome.SUCCESS and _pdf_is_valid(self.pdf_file)

    @property
    def combined_output(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part)


def _pdf_is_valid(pdf_file: Path) -> bool:
    try:
        return pdf_file.exists() and pdf_file.stat().st_size > 0
    except OSError:
        return False


StartedCallback = Callable[[Path, int], None]
FinishedCallback = Callable[[CompileResult], None]
PreviewPreparer = Callable[[Path, Path], PreviewPreparation]


class CompileManager:
    def __init__(
        self,
        root_file: str | Path,
        *,
        toolchain: LaTeXToolchain | None = None,
        output_dir: str | Path | None = None,
        engine: LaTeXEngine | str = LaTeXEngine.AUTO,
        debounce_ms: int = 700,
        on_started: StartedCallback | None = None,
        on_finished: FinishedCallback | None = None,
        preview_preparer: PreviewPreparer | None = None,
        metrics_hook: Callable[[str, str], None] | None = None,
    ) -> None:
        self.root_file = normalize_path(root_file)
        self.output_dir = normalize_path(output_dir) if output_dir else build_dir_for(self.root_file)
        self.toolchain = toolchain or detect_toolchain()
        self.engine = LaTeXEngine(engine)
        self.debounce_ms = debounce_ms
        self.on_started = on_started
        self.on_finished = on_finished
        self.preview_preparer = preview_preparer
        self.metrics_hook = metrics_hook
        self._timer: threading.Timer | None = None
        self._timer_generation = 0
        self._lock = threading.Lock()
        self._running = False
        self._launch_count = 0
        self._idle_event = threading.Event()
        self._idle_event.set()
        self._retired = False
        self._scheduled_purpose: BuildPurpose | None = None
        self._pending_purpose: BuildPurpose | None = None
        self._active_purpose: BuildPurpose | None = None
        self._process: subprocess.Popen[str] | None = None
        self._stop_requested = False

    @property
    def pdf_file(self) -> Path:
        return built_pdf_for(self.root_file, self.output_dir)

    @property
    def log_file(self) -> Path:
        return built_log_for(self.root_file, self.output_dir)

    @property
    def preview_output_dir(self) -> Path:
        return preview_build_dir_for(self.root_file)

    def output_dir_for(self, purpose: BuildPurpose | str) -> Path:
        selected = BuildPurpose(purpose)
        return self.preview_output_dir if selected is BuildPurpose.PREVIEW else self.output_dir

    def pdf_file_for(self, purpose: BuildPurpose | str) -> Path:
        return built_pdf_for(self.root_file, self.output_dir_for(purpose))

    def log_file_for(self, purpose: BuildPurpose | str) -> Path:
        return built_log_for(self.root_file, self.output_dir_for(purpose))

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def is_busy(self) -> bool:
        """Whether a worker has launched or a compile is currently running."""
        return not self._idle_event.is_set()

    @property
    def is_retired(self) -> bool:
        with self._lock:
            return self._retired

    @property
    def active_purpose(self) -> BuildPurpose:
        with self._lock:
            return self._active_purpose or BuildPurpose.FINAL

    def schedule_compile(
        self,
        reason: str = "change",
        purpose: BuildPurpose | str = BuildPurpose.FINAL,
    ) -> None:
        selected = BuildPurpose(purpose)
        with self._lock:
            if self._retired:
                return
            selected = self._merge_purpose(self._scheduled_purpose, selected)
            if self._timer:
                self._timer.cancel()
            self._timer_generation += 1
            generation = self._timer_generation
            self._scheduled_purpose = selected
            self._timer = threading.Timer(
                self.debounce_ms / 1000,
                lambda: self._fire_scheduled_compile(generation, selected),
            )
            self._timer.daemon = True
            self._timer.start()
        self._log(f"已安排{self._purpose_label(selected)}：{reason}")

    def compile_async(self, purpose: BuildPurpose | str = BuildPurpose.FINAL) -> None:
        selected = BuildPurpose(purpose)
        with self._lock:
            if self._retired:
                return
            if self._timer:
                self._timer.cancel()
                self._timer = None
                self._timer_generation += 1
            selected = self._merge_purpose(self._scheduled_purpose, selected)
            self._scheduled_purpose = None
            self._launch_count += 1
            self._idle_event.clear()
        thread = threading.Thread(target=self._run_async, args=(selected,), daemon=True)
        thread.start()

    def _fire_scheduled_compile(self, generation: int, purpose: BuildPurpose) -> None:
        with self._lock:
            if self._retired or generation != self._timer_generation:
                return
            self._timer = None
        self.compile_async(purpose)

    def _run_async(self, purpose: BuildPurpose) -> None:
        if self.metrics_hook is not None:
            self.metrics_hook("start", purpose.value)
        try:
            self.compile_now(purpose)
        finally:
            if self.metrics_hook is not None:
                self.metrics_hook("finish", purpose.value)
            with self._lock:
                self._launch_count = max(0, self._launch_count - 1)
                if self._launch_count == 0 and not self._running:
                    self._stop_requested = False
                    self._idle_event.set()

    def compile_now(
        self,
        purpose: BuildPurpose | str = BuildPurpose.FINAL,
        *,
        timeout_seconds: float | None = None,
    ) -> CompileResult | None:
        selected = BuildPurpose(purpose)
        with self._lock:
            if self._retired or (self._stop_requested and not self._running):
                return None
            if self._running:
                self._pending_purpose = self._merge_purpose(self._pending_purpose, selected)
                self._log(f"编译正在进行；已排队一次{self._purpose_label(self._pending_purpose)}。")
                return None
            self._running = True
            self._active_purpose = selected
            self._stop_requested = False
            self._idle_event.clear()

        build_id = next(_BUILD_IDS)
        try:
            if self.on_started:
                self.on_started(self.root_file, build_id)
            result = self._run_compile(build_id, selected, timeout_seconds=timeout_seconds)
            if self.on_finished:
                self.on_finished(result)
            return result
        except Exception as exc:  # noqa: BLE001 - must never crash the Qt loop
            logger.exception("编译过程发生内部错误")
            result = self._simple_result(
                build_id,
                CompileOutcome.INTERNAL_ERROR,
                returncode=1,
                stderr=f"ICSTeX 处理编译结果时发生错误：{exc}",
                purpose=selected,
            )
            if self.on_finished:
                self.on_finished(result)
            return result
        finally:
            pending_purpose: BuildPurpose | None = None
            with self._lock:
                pending_purpose = self._pending_purpose
                self._pending_purpose = None
                self._running = False
                self._active_purpose = None
                retired = self._retired
                if self._launch_count == 0:
                    self._stop_requested = False
                    self._idle_event.set()
            if pending_purpose is not None and not retired:
                self.schedule_compile("排队的修改", pending_purpose)

    def cancel_pending(self) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            self._timer_generation += 1
            self._scheduled_purpose = None
            self._pending_purpose = None

    def stop_current(self, timeout: float = 1.5) -> bool:
        """Request cancellation and wait at most ``timeout`` for worker exit."""
        self.cancel_pending()
        deadline = time.monotonic() + max(0.0, timeout)
        with self._lock:
            self._pending_purpose = None
            busy = self._running or self._launch_count > 0
            if not busy:
                return False
            self._stop_requested = True
            process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
            remaining = max(0.0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except OSError:
                    pass
        return self.wait_until_idle(max(0.0, deadline - time.monotonic()))

    def wait_until_idle(self, timeout: float = 1.5) -> bool:
        return self._idle_event.wait(max(0.0, timeout))

    def retire(self, timeout: float = 1.5) -> bool:
        """Permanently reject new work and suppress callbacks from this manager."""
        with self._lock:
            self._retired = True
            self.on_started = None
            self.on_finished = None
        stopped = self.stop_current(timeout)
        return stopped or self.wait_until_idle(0)

    def _run_compile(
        self,
        build_id: int,
        purpose: BuildPurpose,
        *,
        timeout_seconds: float | None = None,
    ) -> CompileResult:
        start = time.perf_counter()
        output_dir = self.output_dir_for(purpose)
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_file = self.pdf_file_for(purpose)
        log_file = self.log_file_for(purpose)

        if not self.root_file.exists():
            return self._simple_result(
                build_id,
                CompileOutcome.ROOT_FILE_MISSING,
                returncode=2,
                stderr=f"根 LaTeX 文件不存在：{self.root_file}",
                purpose=purpose,
            )

        if not self.toolchain.supports_engine(self.engine):
            return self._simple_result(
                build_id,
                CompileOutcome.TOOLCHAIN_MISSING,
                returncode=127,
                stderr=self._missing_engine_message(),
                purpose=purpose,
            )

        preparation = PreviewPreparation()
        if purpose is BuildPurpose.PREVIEW and self.preview_preparer is not None:
            try:
                preparation = self.preview_preparer(self.root_file, output_dir)
                if preparation.message:
                    self._log(preparation.message)
            except Exception as exc:  # noqa: BLE001 - preview safely uses originals
                self._log(f"快速预览代理准备失败，已回退原图：{exc}")

        with self._lock:
            stop_requested = self._stop_requested or self._retired
        if stop_requested:
            return self._simple_result(
                build_id,
                CompileOutcome.STOPPED,
                returncode=-15,
                stderr="编译已在准备阶段停止。",
                duration_seconds=time.perf_counter() - start,
                purpose=purpose,
            )

        command = self.toolchain.compile_command(self.root_file, output_dir, self.engine)
        self._log("运行命令：" + " ".join(command))
        timed_out = False
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.root_file.parent,
                env=latex_subprocess_env(texinputs_prefix=preparation.overlay_dir),
            )
            with self._lock:
                self._process = process
                stop_requested = self._stop_requested or self._retired
            if stop_requested:
                try:
                    process.terminate()
                except OSError:
                    pass
            timed_out = False
            if timeout_seconds is None:
                stdout, stderr = process.communicate()
            else:
                try:
                    stdout, stderr = process.communicate(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    self._terminate_process(process)
                    stdout, stderr = process.communicate()
            returncode = process.returncode
        except OSError as exc:
            duration = time.perf_counter() - start
            return self._simple_result(
                build_id,
                CompileOutcome.PROCESS_START_FAILED,
                command=command,
                returncode=126,
                stderr=str(exc),
                duration_seconds=duration,
                purpose=purpose,
            )
        finally:
            with self._lock:
                self._process = None
        with self._lock:
            stop_requested = self._stop_requested or self._retired

        if stop_requested:
            stderr = "\n".join(part for part in (stderr, "编译已停止。") if part)

        duration = time.perf_counter() - start
        combined = "\n".join(part for part in (stdout, stderr) if part)
        errors = parse_log_file(log_file, self.root_file.parent) or parse_latex_errors(combined, self.root_file.parent)

        if timed_out:
            stderr = "\n".join(part for part in (stderr, "编译超时，已终止进程。") if part)
            outcome = CompileOutcome.TIMEOUT
        elif stop_requested:
            outcome = CompileOutcome.STOPPED
        elif returncode != 0 or errors:
            outcome = CompileOutcome.LATEX_ERROR
        elif not _pdf_is_valid(pdf_file):
            outcome = CompileOutcome.OUTPUT_MISSING
        else:
            outcome = CompileOutcome.SUCCESS

        return CompileResult(
            root_file=self.root_file,
            output_dir=output_dir,
            pdf_file=pdf_file,
            log_file=log_file,
            command=command,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            outcome=outcome,
            errors=errors,
            build_id=build_id,
            purpose=purpose,
            preview_fidelity=preparation.fidelity if purpose is BuildPurpose.PREVIEW else None,
            preview_manifest_digest=(
                preparation.manifest_digest if purpose is BuildPurpose.PREVIEW else None
            ),
            preview_asset_paths=(
                preparation.asset_paths if purpose is BuildPurpose.PREVIEW else ()
            ),
        )

    @staticmethod
    def _terminate_process(process: subprocess.Popen[str]) -> None:
        try:
            process.terminate()
        except OSError:
            pass
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except OSError:
                pass

    def _simple_result(
        self,
        build_id: int,
        outcome: CompileOutcome,
        *,
        returncode: int,
        stderr: str,
        command: list[str] | None = None,
        duration_seconds: float = 0,
        purpose: BuildPurpose = BuildPurpose.FINAL,
    ) -> CompileResult:
        output_dir = self.output_dir_for(purpose)
        return CompileResult(
            root_file=self.root_file,
            output_dir=output_dir,
            pdf_file=self.pdf_file_for(purpose),
            log_file=self.log_file_for(purpose),
            command=command or [],
            returncode=returncode,
            stdout="",
            stderr=stderr,
            duration_seconds=duration_seconds,
            outcome=outcome,
            errors=[],
            build_id=build_id,
            purpose=purpose,
        )

    @staticmethod
    def _merge_purpose(
        current: BuildPurpose | None,
        incoming: BuildPurpose,
    ) -> BuildPurpose:
        if current is BuildPurpose.FINAL or incoming is BuildPurpose.FINAL:
            return BuildPurpose.FINAL
        return BuildPurpose.PREVIEW

    @staticmethod
    def _purpose_label(purpose: BuildPurpose) -> str:
        return "最终编译" if purpose is BuildPurpose.FINAL else "快速预览"

    def _log(self, message: str) -> None:
        logger.info(message)

    def _missing_engine_message(self) -> str:
        if not self.toolchain.is_compile_ready:
            return self.toolchain.missing_compile_message
        return (
            f"{self.engine.display_name} 不在 PATH 中。"
            "请通过 MacTeX、TeX Live 或 MiKTeX 安装它，或选择其他编译器。"
        )
