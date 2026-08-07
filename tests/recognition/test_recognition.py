"""Local recognition runtime: models, router, manager, worker client."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.services.recognition.models import (
    RecognitionKind,
    RecognitionRequest,
    RecognitionResult,
    RecognitionRouter,
)


ROOT = Path(__file__).resolve().parents[2]


def _app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def _spin(predicate, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return predicate()


class FakeProvider:
    provider_id = "fake"

    def __init__(self, kinds) -> None:
        self._kinds = set(kinds)

    def capabilities(self) -> set[RecognitionKind]:
        return self._kinds

    def recognize(self, request: RecognitionRequest) -> RecognitionResult:
        return RecognitionResult(request_id=request.request_id, kind=request.kind, provider_id=self.provider_id, text="ok")


class RouterTests(TestCase):
    def test_routes_by_kind(self) -> None:
        pix2tex = FakeProvider({RecognitionKind.FORMULA})
        pix2tex.provider_id = "pix2tex"
        rapidocr = FakeProvider({RecognitionKind.TEXT})
        rapidocr.provider_id = "rapidocr"
        router = RecognitionRouter([pix2tex, rapidocr])
        formula = router.recognize(RecognitionRequest(request_id="r1", kind=RecognitionKind.FORMULA))
        text = router.recognize(RecognitionRequest(request_id="r2", kind=RecognitionKind.TEXT))
        self.assertEqual(formula.provider_id, "pix2tex")
        self.assertEqual(text.provider_id, "rapidocr")

    def test_no_provider_raises(self) -> None:
        router = RecognitionRouter([FakeProvider({RecognitionKind.FORMULA})])
        with self.assertRaises(ValueError):
            router.recognize(RecognitionRequest(request_id="r", kind=RecognitionKind.TEXT))


class RuntimeManagerTests(TestCase):
    def test_install_commands_force_official_pypi(self) -> None:
        from app.services.recognition import runtime_manager

        for commands in (runtime_manager.install_commands("pix2tex"), runtime_manager.install_commands("rapidocr")):
            self.assertTrue(any("--index-url" in command for command in commands))
            self.assertTrue(any(runtime_manager.PYPi_URL in command for command in commands))

    def test_venv_root_honors_env_override(self) -> None:
        from app.services.recognition import runtime_manager

        with TemporaryDirectory() as directory:
            os.environ["ICSTEX_RAPIDOCR_ENV"] = directory
            try:
                self.assertEqual(runtime_manager.provider_venv_root("rapidocr"), Path(directory))
            finally:
                del os.environ["ICSTEX_RAPIDOCR_ENV"]


class WorkerClientTests(TestCase):
    def _client(self, kind: str = "formula") -> "RecognitionWorkerClient":
        from app.services.recognition.client import RecognitionWorkerClient

        return RecognitionWorkerClient(
            sys.executable,
            ["-m", "app.services.recognition.fake_worker", "--kind", kind],
            env={"PYTHONPATH": str(ROOT)},
        )

    def test_health_recognize_formula_shutdown(self) -> None:
        _app()
        client = self._client()
        results: list = []
        client.result_ready.connect(results.append)
        client.start()
        client.health()
        with TemporaryDirectory() as directory:
            image = Path(directory) / "a.png"
            image.write_bytes(b"\x89PNG fake")
            client.recognize("formula", image)
            self.assertTrue(_spin(lambda: bool(results)))
            self.assertEqual(results[0]["latex"], r"\frac{x^2+1}{\sqrt{y}}")
        client.shutdown()

    def test_text_recognize_returns_regions(self) -> None:
        _app()
        client = self._client(kind="text")
        results: list = []
        client.result_ready.connect(results.append)
        client.start()
        with TemporaryDirectory() as directory:
            image = Path(directory) / "b.png"
            image.write_bytes(b"\x89PNG fake")
            client.recognize("text", image)
            self.assertTrue(_spin(lambda: bool(results)))
            self.assertEqual(results[0]["text"], "Experimental Results")
            self.assertGreaterEqual(len(results[0]["regions"]), 1)
        client.shutdown()
