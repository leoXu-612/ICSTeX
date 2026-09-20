"""RapidOCR text recognition manager (wraps the generic worker client)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.services.recognition.client import RecognitionWorkerClient
from app.services.recognition.runtime_manager import provider_python


class TextOcrManager(QObject):
    """Lifecycle + routing for the RapidOCR text worker.

    Mirrors the pix2tex OcrManager shape but stays independent: one kind
    (text), one provider (rapidocr), and its own worker process.
    """

    text_ready = Signal(str, str, object)  # request_id, text, payload
    failed = Signal(str, str, str)  # request_id, code, message
    status_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._client: RecognitionWorkerClient | None = None
        self._pending_id = ""

    def status(self) -> str:
        if not provider_python("rapidocr").exists():
            return "NOT_INSTALLED"
        if self._client is None:
            return "STOPPED"
        return self._client.state.value

    def recognize(self, image_path: Path) -> str:
        if self.status() == "NOT_INSTALLED":
            self.failed.emit("", "NOT_INSTALLED", "RapidOCR 未安装或运行环境缺失。")
            return ""
        client = self._ensure_client()
        request_id = client.recognize("text", str(image_path))
        self._pending_id = request_id
        return request_id

    def shutdown(self) -> None:
        if self._client is not None:
            self._client.shutdown()
            self._client = None

    def _ensure_client(self) -> RecognitionWorkerClient:
        if self._client is not None:
            return self._client
        worker_args = ["-m", "app.services.recognition.worker_entry", "--kind", "text"]
        client = RecognitionWorkerClient(provider_python("rapidocr"), worker_args, self)
        client.result_ready.connect(self._on_result)
        client.error.connect(self._on_error)
        client.state_changed.connect(lambda _state: self.status_changed.emit(self.status()))
        client.start()
        self._client = client
        return client

    def _on_result(self, payload: dict) -> None:
        request_id = str(payload.get("requestId", ""))
        if request_id != self._pending_id:
            return
        if not payload.get("ok") or payload.get("kind") != "text":
            error = payload.get("error", {})
            self.failed.emit(request_id, str(error.get("code", "UNKNOWN")), str(error.get("message", "")))
            return
        self.text_ready.emit(request_id, str(payload.get("text", "")), payload)

    def _on_error(self, code: str, message: str) -> None:
        self.failed.emit(self._pending_id, code, message)
