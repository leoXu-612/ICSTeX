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

    def test_accept_ignores_repeated_submit(self) -> None:
        _app()
        from unittest.mock import patch

        from PySide6.QtWidgets import QDialog

        from app.core.formula.sanitizer import SanitizeResult
        from app.gui.formula_ocr.review_dialog import RecognitionReviewDialog

        with TemporaryDirectory() as directory:
            image = Path(directory) / "a.png"
            image.write_bytes(b"\x89PNG fake")
            dialog = RecognitionReviewDialog(image, r"\frac{x}{y}", SanitizeResult(text=r"\frac{x}{y}"))
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

    def test_image_fingerprint_is_content_based(self) -> None:
        _app()
        from PySide6.QtGui import QColor, QImage

        from app.gui.formula_ocr.image_input import image_fingerprint

        first = QImage(64, 32, QImage.Format.Format_RGB32)
        first.fill(QColor("white"))
        same = QImage(64, 32, QImage.Format.Format_RGB32)
        same.fill(QColor("white"))
        different = QImage(64, 32, QImage.Format.Format_RGB32)
        different.fill(QColor("black"))
        self.assertEqual(image_fingerprint(first), image_fingerprint(same))
        self.assertNotEqual(image_fingerprint(first), image_fingerprint(different))


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
    def test_accept_ignores_repeated_submit(self) -> None:
        _app()
        from unittest.mock import patch

        from PySide6.QtWidgets import QDialog

        from app.gui.formula_ocr.multi_line_dialog import MultiLineOcrDialog

        dialog = MultiLineOcrDialog([r"a &= b"])
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

    def test_roi_canvas_add_and_clear(self) -> None:
        _app()
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor, QImage

        from app.gui.formula_ocr.roi_canvas import RoiCanvas

        canvas = RoiCanvas()
        canvas.set_image(QImage(300, 120, QImage.Format.Format_RGB32))
        canvas.add_rect(QRect(10, 10, 100, 20))
        canvas.add_rect(QRect(10, 60, 100, 20))
        self.assertEqual(len(canvas.rois()), 2)
        canvas.clear()
        self.assertEqual(canvas.rois(), [])

    def test_roi_canvas_select_and_delete(self) -> None:
        _app()
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor, QImage

        from app.gui.formula_ocr.roi_canvas import RoiCanvas

        canvas = RoiCanvas()
        canvas.set_image(QImage(300, 120, QImage.Format.Format_RGB32))
        canvas.add_rect(QRect(10, 10, 100, 20))
        canvas.add_rect(QRect(10, 60, 100, 20))
        canvas.select_roi(0)
        canvas.delete_selected()
        self.assertEqual(len(canvas.rois()), 1)
        self.assertEqual(canvas.rois()[0].y(), 60)

    def test_roi_canvas_edge_handles(self) -> None:
        _app()
        from PySide6.QtCore import QPoint, QRect
        from PySide6.QtGui import QColor, QImage

        from app.gui.formula_ocr.roi_canvas import RoiCanvas

        canvas = RoiCanvas()
        image = QImage(400, 240, QImage.Format.Format_RGB32)
        canvas.set_image(image)
        canvas.resize(400, 240)
        canvas.add_rect(QRect(40, 30, 100, 50))
        canvas.select_roi(0)
        handle = canvas._handle_at(QPoint(140, 55))  # right-edge midpoint
        self.assertEqual(handle, "r")
        bottom = canvas._handle_at(QPoint(90, 80))
        self.assertEqual(bottom, "b")

    def test_roi_canvas_selected_index_accessor(self) -> None:
        _app()
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor, QImage

        from app.gui.formula_ocr.roi_canvas import RoiCanvas

        canvas = RoiCanvas()
        canvas.set_image(QImage(300, 120, QImage.Format.Format_RGB32))
        canvas.add_rect(QRect(10, 10, 100, 20))
        canvas.add_rect(QRect(10, 60, 100, 20))
        canvas.select_roi(0)
        self.assertEqual(canvas.selected_index(), 0)
        canvas.select_roi(1)
        self.assertEqual(canvas.selected_index(), 1)
        canvas.clear()
        self.assertIsNone(canvas.selected_index())

    def test_roi_canvas_click_without_move_does_not_emit_change(self) -> None:
        _app()
        from PySide6.QtCore import QPoint, QRect, Qt
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtTest import QTest

        from app.gui.formula_ocr.roi_canvas import RoiCanvas

        canvas = RoiCanvas()
        image = QImage(400, 240, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        canvas.set_image(image)
        canvas.resize(400, 240)
        canvas.add_rect(QRect(40, 30, 100, 50))
        emitted: list = []
        canvas.rois_changed.connect(lambda: emitted.append(True))

        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(90, 55))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(90, 55))
        self.assertEqual(len(emitted), 0)

        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(90, 55))
        QTest.mouseMove(canvas, QPoint(120, 75))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(120, 75))
        self.assertEqual(len(emitted), 1)

    def test_dialog_with_image_auto_recognizes_rois(self) -> None:
        _app()
        from PySide6.QtCore import QObject, QTimer, Signal
        from PySide6.QtGui import QColor, QImage, QPainter, QPen

        from app.gui.formula_ocr.multi_line_dialog import MultiLineOcrDialog

        class StubResult:
            latex = r"x=1"
            elapsed_ms = 1
            model_version = "stub"

        class StubManager(QObject):
            recognition_finished = Signal(object)
            recognition_failed = Signal(str, str, str)

            def recognize(self, request, session_id):
                QTimer.singleShot(0, lambda: self.recognition_finished.emit((request.request_id, session_id, StubResult())))

        image = QImage(300, 120, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setPen(QPen(QColor("black"), 3))
        painter.drawLine(30, 20, 270, 20)
        painter.drawLine(30, 80, 270, 80)
        painter.end()

        dialog = MultiLineOcrDialog(None, image=image, manager=StubManager())
        self.assertEqual(len(dialog.line_edits), 2)
        self.assertTrue(all(edit.text() for edit in dialog.line_edits))
        dialog.close()

    def test_dialog_manual_recognize_selected(self) -> None:
        _app()
        from PySide6.QtCore import QObject, QTimer, Signal
        from PySide6.QtGui import QColor, QImage, QPainter, QPen

        from app.gui.formula_ocr.multi_line_dialog import MultiLineOcrDialog

        class StubResult:
            latex = r"y=1"
            elapsed_ms = 1
            model_version = "stub"

        class StubManager(QObject):
            recognition_finished = Signal(object)
            recognition_failed = Signal(str, str, str)

            def recognize(self, request, session_id):
                QTimer.singleShot(0, lambda: self.recognition_finished.emit((request.request_id, session_id, StubResult())))

        image = QImage(300, 120, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setPen(QPen(QColor("black"), 3))
        painter.drawLine(30, 20, 270, 20)
        painter.drawLine(30, 80, 270, 80)
        painter.end()
        dialog = MultiLineOcrDialog(None, image=image, manager=StubManager())
        dialog.canvas.select_roi(1)
        dialog._recognize_selected()
        self.assertTrue(dialog.line_edits[1].text())
        dialog.close()

    def test_lines_area_is_scrollable(self) -> None:
        _app()
        from app.gui.formula_ocr.multi_line_dialog import MultiLineOcrDialog

        dialog = MultiLineOcrDialog([r"a", r"b", r"c", r"d", r"e"])
        self.assertTrue(dialog.lines_scroll.widgetResizable())
        dialog.close()

    def test_batch_dialog_recognizes_queue_with_progress(self) -> None:
        _app()
        from PySide6.QtCore import QObject, QTimer, Signal
        from PySide6.QtGui import QColor, QImage, QPainter, QPen

        from app.gui.formula_ocr.batch_dialog import BatchRecognitionDialog

        class StubResult:
            latex = r"x=1"
            elapsed_ms = 1
            model_version = "stub"

        class StubManager(QObject):
            recognition_finished = Signal(object)
            recognition_failed = Signal(str, str, str)

            def recognize(self, request, session_id):
                QTimer.singleShot(0, lambda: self.recognition_finished.emit((request.request_id, session_id, StubResult())))

        image = QImage(300, 120, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setPen(QPen(QColor("black"), 3))
        painter.drawLine(30, 20, 270, 20)
        painter.drawLine(30, 80, 270, 80)
        painter.end()
        dialog = BatchRecognitionDialog(StubManager())
        dialog._append_image("a.png", image)
        dialog._start()
        self.assertEqual(dialog.progress.value(), 1)
        combined = dialog.combined_latex()
        self.assertIn(r"\begin{aligned}", combined)
        dialog.close()

    def test_accept_ignores_repeated_submit(self) -> None:
        _app()
        from unittest.mock import patch

        from PySide6.QtWidgets import QDialog

        from app.gui.formula_ocr.batch_dialog import BatchRecognitionDialog

        dialog = BatchRecognitionDialog(None)
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

    def test_append_skips_duplicate_image(self) -> None:
        _app()
        from PySide6.QtGui import QColor, QImage

        from app.gui.formula_ocr.batch_dialog import BatchRecognitionDialog

        dialog = BatchRecognitionDialog(None)
        image = QImage(120, 60, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        dialog._append_image("a.png", image)
        dialog._append_image("a.png", image)
        self.assertEqual(len(dialog._items), 1)
        self.assertIn("重复", dialog.status_label.text())
        different = QImage(120, 60, QImage.Format.Format_RGB32)
        different.fill(QColor("black"))
        dialog._append_image("b.png", different)
        self.assertEqual(len(dialog._items), 2)
        dialog.close()

    def test_remove_then_readd_same_image_is_allowed(self) -> None:
        _app()
        from PySide6.QtGui import QColor, QImage

        from app.gui.formula_ocr.batch_dialog import BatchRecognitionDialog

        dialog = BatchRecognitionDialog(None)
        image = QImage(120, 60, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        dialog._append_image("a.png", image)
        dialog.select_row(0)
        dialog._remove_selected()
        self.assertEqual(len(dialog._items), 0)
        dialog._append_image("a.png", image)
        self.assertEqual(len(dialog._items), 1)
        dialog.close()

    def test_fine_tune_ignores_rapid_repeated_clicks(self) -> None:
        _app()
        from unittest.mock import patch

        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QDialog

        from app.gui.formula_ocr.batch_dialog import BatchRecognitionDialog
        from app.gui.formula_ocr.multi_line_dialog import MultiLineOcrDialog

        image = QImage(120, 60, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        dialog = BatchRecognitionDialog(None)
        dialog._append_image("a.png", image)
        dialog.select_row(0)

        opens: list = []

        def fake_exec(self):
            opens.append(self)
            return QDialog.DialogCode.Rejected

        with patch.object(MultiLineOcrDialog, "exec", new=fake_exec):
            dialog._fine_tune_current()
            dialog._fine_tune_current()
        self.assertEqual(len(opens), 1)
        self.assertTrue(dialog.fine_tune_button.isEnabled())
        self.assertFalse(dialog._fine_tune_open)

        dialog._fine_tune_ts = 0.0  # debounce window expired
        with patch.object(MultiLineOcrDialog, "exec", new=fake_exec):
            dialog._fine_tune_current()
        self.assertEqual(len(opens), 2)
        dialog.close()

    def test_start_marks_failed_item_with_error_and_retry(self) -> None:
        _app()
        from PySide6.QtCore import QObject, QTimer, Signal
        from PySide6.QtGui import QColor, QImage, QPainter, QPen

        from app.gui.formula_ocr.batch_dialog import (
            STATUS_FAILED,
            STATUS_SUCCEEDED,
            BatchRecognitionDialog,
        )

        class StubResult:
            latex = r"x=1"
            elapsed_ms = 1
            model_version = "stub"

        class FlakyManager(QObject):
            recognition_finished = Signal(object)
            recognition_failed = Signal(str, str, str)

            def recognize(self, request, session_id):
                self.call_count = getattr(self, "call_count", 0) + 1
                if self.call_count == 2:
                    raise RuntimeError("stub model crash")
                QTimer.singleShot(0, lambda: self.recognition_finished.emit((request.request_id, session_id, StubResult())))

        def make_image(color) -> QImage:
            image = QImage(200, 80, QImage.Format.Format_RGB32)
            image.fill(color)
            painter = QPainter(image)
            painter.setPen(QPen(QColor("black"), 3))
            painter.drawLine(30, 20, 170, 20)
            painter.end()
            return image

        manager = FlakyManager()
        dialog = BatchRecognitionDialog(manager)
        dialog._append_image("a.png", make_image(QColor("white")))
        dialog._append_image("b.png", make_image(QColor("lightgray")))
        dialog._start()

        self.assertEqual(dialog._items[0].status, STATUS_SUCCEEDED)
        self.assertEqual(dialog._items[1].status, STATUS_FAILED)
        self.assertIn("识别异常", dialog._items[1].error)
        self.assertIn("stub model crash", dialog._items[1].error)
        self.assertTrue(dialog._rows[1].retry_button.isEnabled())
        self.assertTrue(dialog._rows[1].error_button.isEnabled())
        combined = dialog.combined_latex()
        self.assertEqual(combined.count("x=1"), 1)
        self.assertNotIn("stub model crash", combined)

        dialog._retry_item(1)
        self.assertEqual(dialog._items[1].status, STATUS_SUCCEEDED)
        self.assertEqual(dialog._items[1].error, "")
        combined = dialog.combined_latex()
        self.assertEqual(combined.count("x=1"), 2)
        dialog.close()

    def test_allow_duplicates_check_controls_dedupe(self) -> None:
        _app()
        from PySide6.QtGui import QColor, QImage

        from app.gui.formula_ocr.batch_dialog import BatchRecognitionDialog

        dialog = BatchRecognitionDialog(None)
        image = QImage(120, 60, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        self.assertFalse(dialog.allow_duplicates_check.isChecked())
        dialog._append_image("a.png", image)
        dialog._append_image("a.png", image)
        self.assertEqual(len(dialog._items), 1)

        dialog.allow_duplicates_check.setChecked(True)
        dialog._append_image("a.png", image)
        self.assertEqual(len(dialog._items), 2)
        dialog.close()

    def test_debounce_constant_is_named_and_used(self) -> None:
        _app()
        from app.gui.formula_ocr import DIALOG_OPEN_DEBOUNCE_SECONDS

        self.assertEqual(DIALOG_OPEN_DEBOUNCE_SECONDS, 0.4)

    def test_manual_result_edit_requires_confirmation_before_rerun(self) -> None:
        _app()
        from PySide6.QtGui import QColor, QImage

        from app.gui.formula_ocr.batch_dialog import STATUS_PENDING, STATUS_SUCCEEDED, BatchRecognitionDialog

        dialog = BatchRecognitionDialog(None)
        image = QImage(120, 60, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        dialog._append_image("a.png", image)
        dialog.result_edit.setPlainText("manual edit")
        self.assertTrue(dialog._result_manual)

        dialog._recognize_image = lambda _image: ["x=1"]
        dialog._confirm_overwrite_manual_result = lambda: False
        dialog._start()
        self.assertEqual(dialog._items[0].status, STATUS_PENDING)

        def confirm_true() -> bool:
            dialog._result_manual = False
            return True

        dialog._confirm_overwrite_manual_result = confirm_true
        dialog._start()
        self.assertEqual(dialog._items[0].status, STATUS_SUCCEEDED)
        self.assertFalse(dialog._result_manual)
        dialog.close()

    def test_wait_ocr_ignores_foreign_sessions(self) -> None:
        _app()
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from PySide6.QtCore import QObject, QTimer, Signal

        from app.gui.formula_ocr.multi_line_dialog import _wait_ocr

        class StubManager(QObject):
            recognition_finished = Signal(object)
            recognition_failed = Signal(str, str, str)

            def recognize(self, request, session_id):
                # foreign result first, then our matching result
                QTimer.singleShot(0, lambda: self.recognition_finished.emit(("foreign-1", session_id, "FOREIGN")))
                QTimer.singleShot(0, lambda: self.recognition_failed.emit("foreign-2", "ERR", "other session failed"))
                QTimer.singleShot(15, lambda: self.recognition_finished.emit((request.request_id, session_id, "MATCH")))

        with TemporaryDirectory() as directory:
            image = Path(directory) / "a.png"
            image.write_bytes(b"\x89PNG fake")
            manager = StubManager()
            result = _wait_ocr(manager, image, timeout_ms=2000)
        self.assertEqual(result, "MATCH")
