"""QProcess JSON Lines client for the generic recognition worker."""
from __future__ import annotations

import json
import uuid
from enum import Enum

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


class WorkerState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    ERROR = "error"


class RecognitionWorkerClient(QObject):
    state_changed = Signal(object)
    health_ok = Signal(str)
    result_ready = Signal(object)  # dict payload
    error = Signal(str, str)
    exited = Signal(int)

    START_TIMEOUT_MS = 60_000
    RECOGNIZE_TIMEOUT_MS = 30_000

    def __init__(self, python_exe, worker_args: list[str], parent=None, *, env: dict[str, str] | None = None) -> None:
        super().__init__(parent)
        self._python_exe = python_exe
        self._worker_args = worker_args
        self._env = env or {}
        self._process: QProcess | None = None
        self._state = WorkerState.STOPPED
        self._buffer = ""
        self._pending: str | None = None
        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.setInterval(self.START_TIMEOUT_MS)
        self._start_timer.timeout.connect(self._on_timeout)
        self._recognize_timer = QTimer(self)
        self._recognize_timer.setSingleShot(True)
        self._recognize_timer.setInterval(self.RECOGNIZE_TIMEOUT_MS)
        self._recognize_timer.timeout.connect(self._on_timeout)

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

    def health(self) -> None:
        self._write({"action": "health", "requestId": f"h-{uuid.uuid4().hex[:8]}"})

    def recognize(self, kind: str, image_path, temperature: float = 0.01) -> str:
        request_id = f"ocr-{uuid.uuid4().hex[:12]}"
        self._write(
            {
                "action": "recognize",
                "requestId": request_id,
                "kind": kind,
                "imagePath": str(image_path),
                "temperature": temperature,
            }
        )
        self._pending = request_id
        self._recognize_timer.start()
        return request_id

    def cancel(self) -> None:
        self._recognize_timer.stop()
        self._pending = None
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()

    def shutdown(self) -> None:
        if self._process is None or self._process.state() == QProcess.ProcessState.NotRunning:
            return
        self._write({"action": "shutdown", "requestId": None})
        if not self._process.waitForFinished(3000):
            self._process.kill()
            self._process.waitForFinished(1000)
        self._set_state(WorkerState.STOPPED)

    def _write(self, payload: dict) -> None:
        if self._process is not None:
            self._process.write((json.dumps(payload) + "\n").encode("utf-8"))

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        self._buffer += bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            self._handle(line)

    def _handle(self, line: str) -> None:
        try:
            message = json.loads(line)
        except ValueError:
            self.error.emit("BAD_PROTOCOL", line[:120])
            return
        request_id = message.get("requestId")
        if message.get("action") == "health":
            self.health_ok.emit(str(message.get("provider", "")))
            return
        if message.get("ok"):
            if request_id == self._pending or message.get("action") == "shutdown":
                self._recognize_timer.stop()
                self._pending = None
                self._set_state(WorkerState.READY)
                self.result_ready.emit(message)
        else:
            self._recognize_timer.stop()
            self._pending = None
            error = message.get("error", {})
            self._set_state(WorkerState.ERROR)
            self.error.emit(str(error.get("code", "UNKNOWN")), str(error.get("message", "")))

    def _on_finished(self, code: int) -> None:
        self._start_timer.stop()
        self._recognize_timer.stop()
        self._process = None
        self._pending = None
        self._set_state(WorkerState.STOPPED)
        self.exited.emit(code)

    def _on_timeout(self) -> None:
        self.error.emit("TIMEOUT", "worker did not respond in time")
        self.cancel()

    def _set_state(self, state: WorkerState) -> None:
        if state is self._state:
            return
        self._state = state
        self.state_changed.emit(state)
