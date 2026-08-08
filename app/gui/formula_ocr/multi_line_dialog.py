"""Multi-line OCR: auto-split or manual ROI selection, review, join as aligned."""
from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.formula.line_splitter import split_formula_line_rects, split_formula_lines
from app.core.formula.sanitizer import sanitize_formula_latex
from app.gui.formula_ocr.image_input import save_temp
from app.gui.formula_ocr.roi_canvas import RoiCanvas
from app.optional_tools.pix2tex.protocol import RecognitionRequest


class MultiLineOcrDialog(QDialog):
    """Per-line review; optionally lets the user box ROIs on the image."""

    def __init__(
        self,
        lines: list[str] | None = None,
        *,
        image: QImage | None = None,
        manager=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("多行公式识别")
        self.resize(860, 420)
        self._image = image
        self._manager = manager
        self.line_edits: list[QLineEdit] = []
        self.lines_box = QVBoxLayout()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("逐行识别结果（可修改；右侧画布：按住 Shift 拖拽新建 ROI，直接拖拽移动，角点缩放，选中后按 Delete 删除）："))

        body = QHBoxLayout()
        if image is not None and not image.isNull():
            self.canvas = RoiCanvas()
            self.canvas.set_image(image)
            if manager is not None:
                rois = split_formula_line_rects(image)
                self.canvas.set_rois(rois)
            body.addWidget(self.canvas, 3)
            right = QWidget()
            right_layout = QVBoxLayout(right)
            right_layout.addLayout(self.lines_box)
            buttons = QHBoxLayout()
            auto_button = QPushButton("自动拆分")
            recognize_button = QPushButton("识别所选 ROI")
            clear_button = QPushButton("清空")
            auto_button.clicked.connect(self._auto_split)
            recognize_button.clicked.connect(self._recognize_current)
            clear_button.clicked.connect(self.canvas.clear)
            buttons.addWidget(auto_button)
            buttons.addWidget(recognize_button)
            buttons.addWidget(clear_button)
            right_layout.addLayout(buttons)
            right_layout.addStretch()
            body.addWidget(right, 2)
            if lines:
                self._set_lines(lines)
            elif manager is not None:
                self._recognize_current()
        else:
            for latex in lines or []:
                self._add_line_edit(latex)
            layout.addLayout(self.lines_box)
        layout.addLayout(body, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("应用为 aligned")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_line_edit(self, latex: str) -> QLineEdit:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        index = len(self.line_edits)
        row_layout.addWidget(QLabel(f"L{index + 1}"))
        edit = QLineEdit(latex)
        self.line_edits.append(edit)
        row_layout.addWidget(edit, 1)
        if hasattr(self, "lines_box"):
            self.lines_box.addWidget(row)
        return edit

    def _set_lines(self, lines: list[str]) -> None:
        for edit in self.line_edits:
            edit.setText("")
        for index, latex in enumerate(lines):
            if index < len(self.line_edits):
                self.line_edits[index].setText(latex)
            else:
                self._add_line_edit(latex)

    def _auto_split(self) -> None:
        if self._image is None:
            return
        self.canvas.set_rois(split_formula_line_rects(self._image))
        self._recognize_current()

    def _recognize_current(self) -> None:
        if self._image is None or self._manager is None:
            return
        crops = [self._image.copy(rect) for rect in self.canvas.rois()]
        lines: list[str] = []
        for crop in crops:
            temp = save_temp(crop)
            result = _wait_ocr(self._manager, temp)
            if result is None:
                lines.append("")
                continue
            sanitized = sanitize_formula_latex(result.latex)
            lines.append(sanitized.text if sanitized.ok else result.latex)
        self._set_lines(lines)

    def result_latex(self) -> str:
        lines = [edit.text().strip() for edit in self.line_edits if edit.text().strip()]
        if not lines:
            return ""
        body = " \\\\\n".join(lines)
        return f"\\begin{{aligned}}\n{body}\n\\end{{aligned}}"


def split_and_recognize(image, manager, *, timeout_ms: int = 90000) -> list[str]:
    """Legacy helper: auto-split and recognize every line."""
    crops = split_formula_lines(image)
    lines: list[str] = []
    for crop in crops:
        temp = save_temp(crop)
        result = _wait_ocr(manager, temp, timeout_ms=timeout_ms)
        if result is None:
            continue
        sanitized = sanitize_formula_latex(result.latex)
        lines.append(sanitized.text if sanitized.ok else result.latex)
    return lines


def _wait_ocr(manager, image_path: Path, *, timeout_ms: int = 90000) -> object | None:
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
