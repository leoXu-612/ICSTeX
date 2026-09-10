from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from itertools import count
import logging
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from typing import Callable

from app.core.latex_tools import LaTeXEngine, LaTeXToolchain, detect_toolchain
from app.core.log_parser import LaTeXError, parse_latex_errors, parse_log_file, parse_reference_warnings
from app.core.build_evidence import BuildInputEvidence, capture_compile_inputs, finish_compile_inputs
from app.core.paths import (
    build_dir_for,
    built_log_for,
    built_pdf_for,
    normalize_path,
    preview_build_dir_for,
)
from app.core.process_env import latex_subprocess_env
from app.core.project_dependencies import read_project_bytes, read_recorder_dependencies


logger = logging.getLogger(__name__)

# Shared across managers so two tabs compiling the same root still get
# strictly ordered build ids; the GUI uses them to drop late stale results.
_BUILD_IDS = count(1)
PREVIEW_TIMEOUT_SECONDS = 120.0
FINAL_TIMEOUT_SECONDS = 300.0


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
class CompileJobKey:
    root_file: Path
    output_dir: Path
    purpose: BuildPurpose
    engine: LaTeXEngine
    toolchain: LaTeXToolchain
    restricted_io: bool
    source_revision: int
    dependency_generation: int


@dataclass(frozen=True)
class _CompileRequest:
    key: CompileJobKey
    deadline: float
    cancel_generation: int
    sequence: int


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
    job_key: CompileJobKey | None = None
    recorder_inputs: tuple[Path, ...] | None = None
    input_evidence: BuildInputEvidence | None = None
    warnings: tuple[LaTeXError, ...] = ()
    log_complete: bool = False

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
        restricted_io: bool = False,
        project_scope: str | Path | None = None,
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
        self.restricted_io = restricted_io
        self.project_scope = normalize_path(project_scope) if project_scope else self.root_file.parent
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
        self._cancel_generation = 0
        self._request_sequence = 0
        self._source_revision = 0
        self._dependency_generation = 0
        self._scheduled_request: _CompileRequest | None = None
        self._pending_request: _CompileRequest | None = None
        self._active_job_key: CompileJobKey | None = None

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

    @property
    def active_job_key(self) -> CompileJobKey | None:
        with self._lock:
            return self._active_job_key

    def set_input_revision(self, source_revision: int, dependency_generation: int = 0) -> None:
        with self._lock:
            self._source_revision = source_revision
            self._dependency_generation = dependency_generation

    def _request_locked(self, purpose: BuildPurpose, deadline: float) -> _CompileRequest:
        self._request_sequence += 1
        return _CompileRequest(
            CompileJobKey(
                self.root_file, self.output_dir_for(purpose), purpose, self.engine,
                self.toolchain, self.restricted_io, self._source_revision,
                self._dependency_generation,
            ),
            deadline, self._cancel_generation, self._request_sequence,
        )

    def _merge_request_locked(self, request: _CompileRequest) -> _CompileRequest:
        purpose = request.key.purpose
        for previous in (self._scheduled_purpose, self._pending_purpose):
            purpose = self._merge_purpose(previous, purpose)
        for previous in (self._scheduled_request, self._pending_request):
            if previous is not None and previous.sequence > request.sequence:
                request = previous
        return replace(request, key=replace(
            request.key, purpose=purpose, output_dir=self.output_dir_for(purpose),
        ))

    def _clear_timer_locked(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = None
        self._timer_generation += 1
        self._scheduled_request = None
        self._scheduled_purpose = None

    def _queue_locked(self, request: _CompileRequest) -> None:
        self._pending_request = request
        self._pending_purpose = request.key.purpose

    def _arm_locked(self, request: _CompileRequest) -> None:
        self._clear_timer_locked()
        self._scheduled_request = request
        self._scheduled_purpose = request.key.purpose
        generation = self._timer_generation
        self._timer = threading.Timer(
            max(0.0, request.deadline - time.monotonic()),
            lambda: self._fire_scheduled_compile(generation, request.key.purpose),
        )
        self._timer.daemon = True
        self._timer.start()

    def _launch_locked(self, request: _CompileRequest) -> None:
        self._launch_count += 1
        self._idle_event.clear()
        threading.Thread(target=self._run_async, args=(request,), daemon=True).start()

    def _drain_locked(self) -> None:
        if self._running or self._launch_count:
            return
        request = self._pending_request
        self._pending_request = None
        self._pending_purpose = None
        if request is not None and not self._retired and not self._stop_requested:
            self._arm_locked(request)
        self._stop_requested = False
        self._idle_event.set()

    def schedule_compile(
        self,
        reason: str = "change",
        purpose: BuildPurpose | str = BuildPurpose.FINAL,
    ) -> None:
        selected = BuildPurpose(purpose)
        with self._lock:
            if self._retired:
                return
            request = self._merge_request_locked(self._request_locked(
                selected, time.monotonic() + self.debounce_ms / 1000,
            ))
            selected = request.key.purpose
            if self._running or self._launch_count:
                self._clear_timer_locked()
                self._queue_locked(self._merge_request_locked(request))
            else:
                self._arm_locked(request)
        self._log(f"已安排{self._purpose_label(selected)}：{reason}")

    def compile_async(self, purpose: BuildPurpose | str = BuildPurpose.FINAL) -> None:
        selected = BuildPurpose(purpose)
        with self._lock:
            if self._retired:
                return
            request = self._merge_request_locked(self._request_locked(selected, time.monotonic()))
            self._clear_timer_locked()
            if self._running or self._launch_count:
                self._queue_locked(request)
            else:
                self._launch_locked(request)

    def _fire_scheduled_compile(self, generation: int, purpose: BuildPurpose) -> None:
        with self._lock:
            if self._retired or generation != self._timer_generation:
                return
            request = self._scheduled_request
            self._clear_timer_locked()
            if request is None or request.cancel_generation != self._cancel_generation:
                return
            if self._running or self._launch_count:
                self._queue_locked(self._merge_request_locked(request))
            else:
                self._launch_locked(request)

    def _run_async(self, request: _CompileRequest) -> None:
        purpose = request.key.purpose
        if self.metrics_hook is not None:
            self.metrics_hook("start", purpose.value)
        try:
            timeout = PREVIEW_TIMEOUT_SECONDS if purpose is BuildPurpose.PREVIEW else FINAL_TIMEOUT_SECONDS
            self.compile_now(purpose, timeout_seconds=timeout, _request=request)
        finally:
            if self.metrics_hook is not None:
                self.metrics_hook("finish", purpose.value)
            with self._lock:
                self._launch_count = max(0, self._launch_count - 1)
                self._drain_locked()

    def compile_now(
        self,
        purpose: BuildPurpose | str = BuildPurpose.FINAL,
        *,
        timeout_seconds: float | None = FINAL_TIMEOUT_SECONDS,
        _request: _CompileRequest | None = None,
    ) -> CompileResult | None:
        selected = BuildPurpose(purpose)
        with self._lock:
            request = _request or self._merge_request_locked(
                self._request_locked(selected, time.monotonic())
            )
            if (
                self._retired or self._stop_requested
                or request.cancel_generation != self._cancel_generation
            ):
                return None
            selected = request.key.purpose
            if self._running:
                self._queue_locked(self._merge_request_locked(request))
                self._log(f"编译正在进行；已排队一次{self._purpose_label(self._pending_purpose)}。")
                return None
            if _request is None:
                self._clear_timer_locked()
            self._running = True
            self._active_purpose = selected
            self._active_job_key = request.key
            self._stop_requested = False
            self._idle_event.clear()

        build_id = next(_BUILD_IDS)
        try:
            if self.on_started:
                self.on_started(self.root_file, build_id)
            before = None
            if selected is BuildPurpose.FINAL:
                previous = read_recorder_dependencies(
                    request.key.output_dir / f"{self.root_file.stem}.fls",
                    root=self.root_file, scope=self.project_scope,
                )
                before = capture_compile_inputs(self.root_file, self.project_scope,
                                                tuple(previous.paths) if previous else ())
            result = self._run_compile(build_id, selected, timeout_seconds=timeout_seconds)
            # Read the recorder before another job can overwrite the same FLS.
            recorder = None
            if result.ok:
                inputs = read_recorder_dependencies(
                    result.output_dir / f"{self.root_file.stem}.fls",
                    root=self.root_file, scope=self.project_scope,
                )
                if inputs is not None:
                    recorder = tuple(sorted(inputs.paths))
            evidence = (finish_compile_inputs(before, self.root_file, self.project_scope,
                                              recorder or (), result.pdf_file if result.ok else None)
                        if before is not None else None)
            result = replace(result, job_key=request.key, recorder_inputs=recorder, input_evidence=evidence)
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
            result = replace(result, job_key=request.key)
            if self.on_finished:
                self.on_finished(result)
            return result
        finally:
            with self._lock:
                self._running = False
                self._active_purpose = None
                self._active_job_key = None
                self._drain_locked()

    def cancel_pending(self) -> None:
        with self._lock:
            self._cancel_pending_locked()

    def _cancel_pending_locked(self) -> None:
        self._clear_timer_locked()
        self._cancel_generation += 1
        self._pending_request = None
        self._pending_purpose = None

    def stop_current(self, timeout: float = 1.5) -> bool:
        """Request cancellation and wait at most ``timeout`` for worker exit."""
        deadline = time.monotonic() + max(0.0, timeout)
        with self._lock:
            self._cancel_pending_locked()
            busy = self._running or self._launch_count > 0
            if not busy:
                return False
            self._stop_requested = True
            process = self._process
        if process is not None and process.poll() is None:
            self._terminate_process(process)
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
        key = self.active_job_key
        toolchain = key.toolchain if key is not None else self.toolchain
        engine = key.engine if key is not None else self.engine
        restricted_io = key.restricted_io if key is not None else self.restricted_io
        output_dir = key.output_dir if key is not None else self.output_dir_for(purpose)
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_file = built_pdf_for(self.root_file, output_dir)
        log_file = built_log_for(self.root_file, output_dir)

        if not self.root_file.exists():
            return self._simple_result(
                build_id,
                CompileOutcome.ROOT_FILE_MISSING,
                returncode=2,
                stderr=f"根 LaTeX 文件不存在：{self.root_file}",
                purpose=purpose,
            )

        if not toolchain.supports_engine(engine):
            return self._simple_result(
                build_id,
                CompileOutcome.TOOLCHAIN_MISSING,
                returncode=127,
                stderr=self._missing_engine_message(toolchain, engine),
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

        command_root = self.root_file
        command_output = output_dir
        if restricted_io:
            command_root = Path(os.path.relpath(self.root_file, self.root_file.parent))
            command_output = Path(os.path.relpath(output_dir, self.root_file.parent))
        command = toolchain.compile_command(command_root, command_output, engine)
        self._log("运行命令：" + " ".join(command))
        timed_out = False
        try:
            popen_kwargs: dict[str, object] = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "cwd": self.root_file.parent,
                "env": self._compile_environment(preparation.overlay_dir, restricted_io=restricted_io),
            }
            if os.name == "nt":
                # A new process group lets stop/timeout kill latexmk and the
                # engine children it spawns (taskkill /T targets the tree).
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                # Session leader: os.killpg(pid, SIGTERM/SIGKILL) covers the
                # whole driver+engine tree so engine children cannot survive
                # and hold the stdout/stderr pipes open after a timeout.
                popen_kwargs["start_new_session"] = True
            process = subprocess.Popen(command, **popen_kwargs)
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
        try:
            log_text = read_project_bytes(log_file, self.project_scope, allow_internal=True).decode("utf-8", errors="replace")
            log_complete = True
        except (OSError, ValueError):
            log_text, log_complete = combined, False

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
            warnings=parse_reference_warnings(log_text),
            log_complete=log_complete,
            preview_fidelity=preparation.fidelity if purpose is BuildPurpose.PREVIEW else None,
            preview_manifest_digest=(
                preparation.manifest_digest if purpose is BuildPurpose.PREVIEW else None
            ),
            preview_asset_paths=(
                preparation.asset_paths if purpose is BuildPurpose.PREVIEW else ()
            ),
        )

    def _compile_environment(
        self, overlay_dir: Path | None, *, restricted_io: bool | None = None,
    ) -> dict[str, str]:
        environment = latex_subprocess_env(texinputs_prefix=overlay_dir)
        if self.restricted_io if restricted_io is None else restricted_io:
            # TeX's paranoid mode rejects absolute and parent-path document IO
            # while retaining reads from the working tree and installed TeX
            # distribution.  This complements -no-shell-escape; it does not
            # replace project-root validation at the caller boundary.
            environment["openin_any"] = "p"
            environment["openout_any"] = "p"
        return environment

    @staticmethod
    def _terminate_process(process: subprocess.Popen[str]) -> None:
        """Terminate the whole compile tree, not just the direct child.

        latexmk drives engine children (xelatex/pdflatex) that inherit the
        stdout/stderr pipes. Killing only the driver leaves the engine holding
        the pipe write ends open, so a subsequent communicate() can block
        forever waiting for EOF.
        """
        process_pid = getattr(process, "pid", None)
        group_kill = process_pid is not None and os.name != "nt"
        windows_tree_kill = process_pid is not None and os.name == "nt"
        if group_kill:
            try:
                os.killpg(os.getpgid(process_pid), signal.SIGTERM)
            except OSError:
                group_kill = False
        if windows_tree_kill:
            try:
                subprocess.run(
                    ["taskkill", "/pid", str(process_pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError:
                windows_tree_kill = False
        if not group_kill and not windows_tree_kill:
            try:
                process.terminate()
            except OSError:
                pass
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            if group_kill:
                try:
                    os.killpg(os.getpgid(process_pid), signal.SIGKILL)
                    return
                except OSError:
                    pass
            if windows_tree_kill:
                try:
                    subprocess.run(
                        ["taskkill", "/pid", str(process_pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    return
                except OSError:
                    pass
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

    def _missing_engine_message(self, toolchain: LaTeXToolchain, engine: LaTeXEngine) -> str:
        if not toolchain.is_compile_ready:
            return toolchain.missing_compile_message
        return (
            f"{engine.display_name} 不在 PATH 中。"
            "请通过 MacTeX、TeX Live 或 MiKTeX 安装它，或选择其他编译器。"
        )
