"""Optional local formula OCR: sanitizer, protocol, sidecar client, review."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.formula.sanitizer import sanitize_formula_latex, strip_wrappers
from app.optional_tools.pix2tex.client import Pix2TexClient, WorkerState
from app.optional_tools.pix2tex.protocol import RecognitionRequest, decode_message, encode_message


ROOT = Path(__file__).resolve().parents[1]


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


class SanitizerTests(TestCase):
    def test_strips_wrappers(self) -> None:
        self.assertEqual(strip_wrappers(r"$x+1$"), "x+1")
        self.assertEqual(strip_wrappers(r"$$x$$"), "x")
        self.assertEqual(strip_wrappers(r"\(x\)"), "x")
        self.assertEqual(strip_wrappers(r"\[x\]"), "x")

    def test_ok_candidate_passes(self) -> None:
        result = sanitize_formula_latex(r"$\frac{x^2+1}{\sqrt{y}}$")
        self.assertTrue(result.ok)
        self.assertEqual(result.text, r"\frac{x^2+1}{\sqrt{y}}")

    def test_forbidden_commands_rejected(self) -> None:
        for latex in (r"\input{secret}", r"\usepackage{x}", r"\def\x{1}", r"\write18{rm -rf}"):
            result = sanitize_formula_latex(latex)
            self.assertFalse(result.ok, latex)
            self.assertTrue(any("forbidden" in error for error in result.errors), latex)

    def test_url_and_control_chars_rejected(self) -> None:
        self.assertFalse(sanitize_formula_latex("https://evil.example/x").ok)
        self.assertFalse(sanitize_formula_latex("a\x00b").ok)

    def test_length_and_depth_limits(self) -> None:
        self.assertFalse(sanitize_formula_latex("x" * 2500).ok)
        self.assertFalse(sanitize_formula_latex("{" * 80 + "x" + "}" * 80).ok)


class ProtocolTests(TestCase):
    def test_request_message_round_trip(self) -> None:
        request = RecognitionRequest(request_id="r1", image_path=Path("/tmp/a.png"), temperature=0.01)
        message = request.to_message()
        self.assertEqual(message["method"], "recognize")
        self.assertEqual(message["params"]["temperature"], 0.01)
        decoded = decode_message(encode_message(message))
        self.assertEqual(decoded["id"], "r1")


class SidecarClientTests(TestCase):
    def _client(self, mode: str = "ok") -> Pix2TexClient:
        return Pix2TexClient(
            sys.executable,
            ["-m", "app.optional_tools.pix2tex.fake_worker"],
            env={"ICSTEX_FAKE_OCR_MODE": mode, "PYTHONPATH": str(ROOT)},
        )

    def test_ready_recognize_result_shutdown(self) -> None:
        _app()
        client = self._client()
        client.start()
        self.assertTrue(_spin(lambda: client.state is WorkerState.READY), "worker ready")
        with TemporaryDirectory() as directory:
            image = Path(directory) / "formula.png"
            image.write_bytes(b"\x89PNG fake")
            results: list = []
            client.result_ready.connect(results.append)
            client.recognize(RecognitionRequest(request_id="r1", image_path=image))
            self.assertTrue(_spin(lambda: bool(results)), "recognition result")
            self.assertEqual(results[0].latex, r"\frac{x^2+1}{\sqrt{y}}")
        client.shutdown()

    def test_crash_reports_exit(self) -> None:
        _app()
        client = self._client(mode="crash")
        exits: list[int] = []
        client.exited.connect(exits.append)
        client.start()
        self.assertTrue(_spin(lambda: bool(exits)), "worker exited")
        self.assertNotEqual(exits[0], 0)

    def test_load_failure_reports_error(self) -> None:
        _app()
        client = self._client(mode="load_fail")
        errors: list[tuple[str, str]] = []
        client.error.connect(lambda code, msg: errors.append((code, msg)))
        client.start()
        self.assertTrue(_spin(lambda: bool(errors)), "error emitted")
        self.assertEqual(errors[0][0], "MODEL_LOAD_FAILED")


class ReviewDialogTests(TestCase):
    def test_confirm_returns_edited_latex(self) -> None:
        _app()
        from app.core.formula.sanitizer import SanitizeResult
        from app.gui.formula_ocr.review_dialog import RecognitionReviewDialog

        with TemporaryDirectory() as directory:
            image = Path(directory) / "a.png"
            image.write_bytes(b"\x89PNG fake")
            dialog = RecognitionReviewDialog(image, r"\frac{x}{y}", SanitizeResult(text=r"\frac{x}{y}"))
            dialog.latex_edit.setPlainText(r"\frac{x^2}{y}")
            self.assertEqual(dialog.confirmed_latex(), r"\frac{x^2}{y}")
            dialog.close()


class ImageInputTests(TestCase):
    def test_preprocess_composites_transparency_on_white(self) -> None:
        _app()
        from PySide6.QtGui import QColor, QImage

        from app.gui.formula_ocr.image_input import preprocess

        image = QImage(32, 32, QImage.Format.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))  # fully transparent
        processed = preprocess(image)
        self.assertFalse(processed.hasAlphaChannel())
        self.assertEqual(processed.pixelColor(0, 0), QColor("white"))


class LineSplitterTests(TestCase):
    def test_splits_two_bands(self) -> None:
        _app()
        from PySide6.QtGui import QColor, QImage, QPainter, QPen

        from app.core.formula.line_splitter import split_formula_lines

        image = QImage(300, 120, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setPen(QPen(QColor("black"), 3))
        painter.drawLine(30, 20, 270, 20)  # line 1 band
        painter.drawLine(30, 80, 270, 80)  # line 2 band
        painter.end()
        crops = split_formula_lines(image)
        self.assertEqual(len(crops), 2)
        self.assertLess(crops[0].height(), crops[1].y() if hasattr(crops[1], "y") else 120)
        # top crop sits in the upper band, bottom crop in the lower band
        self.assertTrue(crops[0].height() < 60)
        self.assertTrue(crops[1].height() < 60)

    def test_blank_image_returns_nothing(self) -> None:
        _app()
        from PySide6.QtGui import QColor, QImage

        from app.core.formula.line_splitter import split_formula_lines

        image = QImage(200, 80, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        self.assertEqual(split_formula_lines(image), [])


class MultiLineDialogTests(TestCase):
    def test_result_latex_joins_lines_in_aligned(self) -> None:
        _app()
        from app.gui.formula_ocr.multi_line_dialog import MultiLineOcrDialog

        dialog = MultiLineOcrDialog([r"a &= b", r"c &= d"])
        dialog.line_edits[0].setText(r"x &= 1")
        latex = dialog.result_latex()
        self.assertIn(r"\begin{aligned}", latex)
        self.assertIn(r"x &= 1", latex)
        self.assertIn(r"c &= d", latex)
        self.assertIn(r"\end{aligned}", latex)
        dialog.close()
