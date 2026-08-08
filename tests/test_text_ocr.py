"""RapidOCR Review -> Text Block flow tests."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402


def _app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class TextReviewDialogTests(TestCase):
    def test_accept_is_idempotent(self) -> None:
        _app()
        from app.gui.text_ocr.text_review_dialog import TextReviewDialog

        with TemporaryDirectory() as directory:
            image = Path(directory) / "a.png"
            image.write_bytes(b"\x89PNG fake")
            dialog = TextReviewDialog(image, "hello world", {"regions": []})
            original_accept = QDialog.accept
            accept_calls: list = []

            def spy(self) -> None:
                accept_calls.append(self)
                original_accept(self)

            with patch.object(QDialog, "accept", new=spy):
                dialog.accept()
                dialog.accept()
            self.assertEqual(len(accept_calls), 1)
            self.assertTrue(dialog._submitted)
            dialog.close()

    def test_result_text_returns_edited_text(self) -> None:
        _app()
        from app.gui.text_ocr.text_review_dialog import TextReviewDialog

        with TemporaryDirectory() as directory:
            image = Path(directory) / "a.png"
            image.write_bytes(b"\x89PNG fake")
            dialog = TextReviewDialog(image, "raw", {"regions": [{"text": "raw", "confidence": 0.9}]})
            dialog.text_edit.setPlainText("  edited  ")
            self.assertEqual(dialog.result_text(), "edited")
            dialog.close()


class TextOcrManagerTests(TestCase):
    def test_not_installed_emits_failed(self) -> None:
        _app()
        from app.gui.text_ocr.text_ocr_manager import TextOcrManager
        from app.gui.text_ocr import text_ocr_manager as module

        with patch.object(module, "provider_python", return_value=Path("/nonexistent/rapidocr/bin/python")):
            manager = TextOcrManager()
            self.assertEqual(manager.status(), "NOT_INSTALLED")
            failures: list = []
            manager.failed.connect(lambda _rid, code, _msg: failures.append(code))
            manager.recognize(Path("/tmp/x.png"))
            self.assertEqual(failures, ["NOT_INSTALLED"])


class TextBlockFlowTests(TestCase):
    def test_run_creates_text_block_from_recognized_text(self) -> None:
        _app()
        import app.gui.text_ocr.text_block_flow as flow
        from app.gui.text_ocr.text_review_dialog import TextReviewDialog

        class FakeController:
            def __init__(self) -> None:
                self.added: list = []

            def add_block(self, block_type, alias=None, content=None) -> str:
                self.added.append((block_type, alias, content))
                return "b1"

        controller = FakeController()
        with TemporaryDirectory() as directory:
            image = Path(directory) / "a.png"
            image.write_bytes(b"\x89PNG fake")
            payload = {"regions": [{"text": "Hello world", "confidence": 0.95}]}

            class StubManager:
                def status(self) -> str:
                    return "STOPPED"

                def recognize(self, image_path):
                    return "req1"

            with (
                patch.object(flow, "get_manager", return_value=StubManager()),
                patch.object(flow, "_pick_image", return_value=image),
                patch.object(flow, "wait_text", return_value=("Hello world", payload)),
                patch.object(TextReviewDialog, "exec", return_value=QDialog.DialogCode.Accepted),
                patch.object(flow.QMessageBox, "information"),
            ):
                flow.run_text_block_ocr(None, controller)
        self.assertEqual(len(controller.added), 1)
        block_type, alias, content = controller.added[0]
        self.assertEqual(block_type, "text")
        self.assertEqual(content.get("text"), "Hello world")
        self.assertTrue(alias)

    def test_get_manager_is_singleton_on_app(self) -> None:
        _app()
        from app.gui.text_ocr.text_block_flow import get_manager

        first = get_manager()
        second = get_manager()
        self.assertIs(first, second)
