"""High-level OCR manager: status, install lifecycle, recognition routing."""
from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from app.optional_tools.pix2tex.client import Pix2TexClient
from app.optional_tools.pix2tex.environment import manifest_path, models_dir, python_executable
from app.optional_tools.pix2tex.protocol import RecognitionRequest, RecognitionResult


class OcrManager(QObject):
    status_changed = Signal(str)
    recognition_finished = Signal(object)  # (request_id, session_id, result)
    recognition_failed = Signal(str, str, str)  # request_id, code, message
    install_finished = Signal(bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._client: Pix2TexClient | None = None
        self._session_id: str = ""
        self._pending_session: str = ""
        self._install_process: QProcess | None = None
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self.shutdown_worker)

    def status(self) -> str:
        if not python_executable().exists():
            return "NOT_INSTALLED"
        if not manifest_path().is_file() or not manifest_path().exists():
            return "MODEL_MISSING"
        if self._client is None:
            return "STOPPED"
        return self._client.state.value

    def install(self, *, with_models: bool = False, python: str | None = None) -> None:
        import sys

        from app.optional_tools.pix2tex.installer_cli import __file__ as cli_file

        process = QProcess(self)
        process.setProgram(str(python or sys.executable))
        args = [cli_file, "install"]
        if python:
            args += ["--python", python]
        if with_models:
            args.append("--with-models")
        process.setArguments(args)
        process.finished.connect(lambda code: self.install_finished.emit(code == 0, self.status()))
        process.start()
        self._install_process = process

    def remove(self) -> None:
        import sys

        from app.optional_tools.pix2tex.installer_cli import __file__ as cli_file

        process = QProcess(self)
        process.setProgram(str(sys.executable))
        process.setArguments([cli_file, "remove"])
        process.finished.connect(lambda code: self.install_finished.emit(code == 0, self.status()))
        process.start()
        self._install_process = process

    def recognize(self, request: RecognitionRequest, session_id: str) -> None:
        if self.status() in ("NOT_INSTALLED", "MODEL_MISSING"):
            self.recognition_failed.emit(request.request_id, "NOT_INSTALLED", "pix2tex 未安装")
            return
        self._session_id = session_id
        self._pending_session = session_id
        client = self._ensure_client()
        if client.state.value in ("ready", "error"):
            client.recognize(request)
        else:
            client.queue(request)

    def cancel(self) -> None:
        if self._client is not None:
            self._client.cancel()

    def shutdown_worker(self) -> None:
        if self._client is not None:
            self._client.shutdown()
            self._client = None
        self.status_changed.emit(self.status())

    def _ensure_client(self) -> Pix2TexClient:
        if self._client is not None:
            return self._client
        import sys

        worker_args = [
            "-m",
            "app.optional_tools.pix2tex.worker_entry",
            "--manifest",
            str(manifest_path()),
        ]
        client = Pix2TexClient(python_executable(), worker_args, self)
        client.result_ready.connect(self._on_result)
        client.error.connect(lambda code, msg: self.recognition_failed.emit("", code, msg))
        client.state_changed.connect(lambda _state: self.status_changed.emit(self.status()))
        client.start()
        self._client = client
        return client

    def _on_result(self, result: RecognitionResult) -> None:
        self.recognition_finished.emit((result.request_id, self._pending_session, result))
        self._idle_timer.start(600_000)
