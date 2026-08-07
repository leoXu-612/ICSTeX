"""Multi-line OCR: split image into lines, review each, join as aligned."""
from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.formula.line_splitter import split_formula_lines
from app.core.formula.sanitizer import sanitize_formula_latex
from app.gui.formula_ocr.image_input import save_temp
from app.optional_tools.pix2tex.protocol import RecognitionRequest


class MultiLineOcrDialog(QDialog):
    """Per-line review before applying an ``aligned`` formula."""

    def __init__(self, lines: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("多行公式识别")
        self.resize(620, 320)
        self.line_edits: list[QLineEdit] = []
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("逐行识别结果（可修改）："))
        for index, latex in enumerate(lines):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(QLabel(f"L{index + 1}"))
            edit = QLineEdit(latex)
            self.line_edits.append(edit)
            row_layout.addWidget(edit, 1)
            layout.addWidget(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("应用为 aligned")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_latex(self) -> str:
        lines = [edit.text().strip() for edit in self.line_edits if edit.text().strip()]
        if not lines:
            return ""
        body = " \\\\\n".join(lines)
        return f"\\begin{{aligned}}\n{body}\n\\end{{aligned}}"


def split_and_recognize(image, manager, *, timeout_ms: int = 90000) -> list[str]:
    """Split ``image`` into lines and recognize each; returns sanitized latex lines."""
    crops = split_formula_lines(image)
    if not crops:
        return []
    lines: list[str] = []
    for crop in crops:
        temp = save_temp(crop)
        result = _wait_ocr(manager, temp, timeout_ms=timeout_ms)
        if result is None:
            continue
        sanitized = sanitize_formula_latex(result.latex)
        lines.append(sanitized.text if sanitized.ok else result.latex)
    return lines


def _wait_ocr(manager, image_path: Path, *, timeout_ms: int) -> object | None:
    request = RecognitionRequest(request_id=f"ml-{uuid.uuid4().hex[:10]}", image_path=image_path)
    box: dict = {}

    def on_result(payload) -> None:
        request_id, _session, result = payload
        if request_id == request.request_id:
            box["result"] = result

    manager.recognition_finished.connect(on_result)
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)
    manager.recognition_finished.connect(loop.quit)
    manager.recognition_failed.connect(loop.quit)
    manager.recognize(request, session_id="multi-line")
    loop.exec()
    manager.recognition_finished.disconnect(on_result)
    manager.recognition_finished.disconnect(loop.quit)
    manager.recognition_failed.disconnect(loop.quit)
    timer.stop()
    return box.get("result")
