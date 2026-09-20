"""QProcess JSONL client for the pix2tex sidecar worker."""
from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from app.optional_tools.pix2tex.protocol import RecognitionRequest, RecognitionResult, decode_message, encode_message


class WorkerState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    LOADING = "loading"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    STOPPING = "stopping"


class Pix2TexClient(QObject):
    state_changed = Signal(object)
    result_ready = Signal(object)
    error = Signal(str, str)
    exited = Signal(int)

    START_TIMEOUT_MS = 90_000
    INFERENCE_TIMEOUT_MS = 180_000

    def __init__(
        self,
        python_exe,
        worker_args: list[str],
        parent: QObject | None = None,
        *,
        env: dict[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._python_exe = python_exe
        self._worker_args = worker_args
        self._env = env or {}
        self._process: QProcess | None = None
        self._state = WorkerState.STOPPED
        self._pending: RecognitionRequest | None = None
        self._active: RecognitionRequest | None = None
        self._buffer = ""
        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.setInterval(self.START_TIMEOUT_MS)
        self._start_timer.timeout.connect(self._on_start_timeout)
        self._infer_timer = QTimer(self)
        self._infer_timer.setSingleShot(True)
        self._infer_timer.setInterval(self.INFERENCE_TIMEOUT_MS)
        self._infer_timer.timeout.connect(self._on_infer_timeout)

    @property
    def state(self) -> WorkerState:
        return self._state

    def start(self) -> None:
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            return
        self._set_state(WorkerState.STARTING)
        process = QProcess(self)
        process.setProgram(str(self._python_exe))
        process.setArguments(self._worker_args)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        if self._env:
            environment = QProcessEnvironment.systemEnvironment()
            for key, value in self._env.items():
                environment.insert(key, value)
            process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(self._on_stdout)
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.finished.connect(self._on_finished)
        process.start()
        self._process = process
        self._buffer = ""
        self._start_timer.start()

    def recognize(self, request: RecognitionRequest) -> None:
        if self._state in (WorkerState.STARTING, WorkerState.LOADING, WorkerState.BUSY):
            self._pending = request
            return
        self._active = request
        self._set_state(WorkerState.BUSY)
        self._write(encode_message(request.to_message()))
        self._infer_timer.start()

    def queue(self, request: RecognitionRequest) -> None:
        self._pending = request

    def cancel(self) -> None:
        self._infer_timer.stop()
        self._active = None
        self._pending = None
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()

    def shutdown(self) -> None:
        if self._process is None or self._process.state() == QProcess.ProcessState.NotRunning:
            return
        self._set_state(WorkerState.STOPPING)
        self._write(encode_message({"id": None, "method": "shutdown"}))
        if not self._process.waitForFinished(3000):
            self._process.kill()
            self._process.waitForFinished(1000)
        self._set_state(WorkerState.STOPPED)

    def _write(self, line: str) -> None:
        if self._process is not None:
            self._process.write(line.encode("utf-8"))

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        self._buffer += bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        try:
            message = decode_message(line)
        except ValueError as exc:
            self.error.emit("BAD_PROTOCOL", str(exc))
            return
        event = message.get("event")
        if event == "loading_model":
            self._start_timer.stop()
            self._set_state(WorkerState.LOADING)
        elif event == "ready":
            self._start_timer.stop()
            self._set_state(WorkerState.READY)
            if self._pending is not None:
                request = self._pending
                self._pending = None
                self.recognize(request)
        elif event == "inference_started":
            pass
        elif event == "shutdown":
            self._set_state(WorkerState.STOPPED)
        elif "result" in message:
            self._infer_timer.stop()
            payload = message["result"]
            result = RecognitionResult(
                request_id=str(message.get("id", "")),
                latex=str(payload.get("latex", "")),
                elapsed_ms=int(payload.get("elapsed_ms", 0)),
                model_version=str(payload.get("model_version", "")),
            )
            self._active = None
            self._set_state(WorkerState.READY)
            self.result_ready.emit(result)
        elif "error" in message:
            self._infer_timer.stop()
            self._active = None
            self._set_state(WorkerState.ERROR)
            error = message["error"]
            self.error.emit(str(error.get("code", "UNKNOWN")), str(error.get("message", "")))

    def _on_finished(self, code: int) -> None:
        self._start_timer.stop()
        self._infer_timer.stop()
        self._process = None
        self._active = None
        self._set_state(WorkerState.STOPPED)
        self.exited.emit(code)

    def _on_start_timeout(self) -> None:
        self._set_state(WorkerState.ERROR)
        self.error.emit("START_TIMEOUT", "worker did not become ready")
        self.cancel()

    def _on_infer_timeout(self) -> None:
        self.error.emit("INFERENCE_TIMEOUT", "inference timed out")
        self.cancel()

    def _set_state(self, state: WorkerState) -> None:
        if state is self._state:
            return
        self._state = state
        self.state_changed.emit(state)
