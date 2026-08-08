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
    QScrollArea,
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
        self.lines_scroll = QScrollArea()
        self.lines_scroll.setWidgetResizable(True)
        self.lines_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        lines_container = QWidget()
        lines_container.setLayout(self.lines_box)
        self.lines_scroll.setWidget(lines_container)
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.setInterval(500)
        self._auto_timer.timeout.connect(self._recognize_current)
        self._recognizing = False
        self._submitted = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("逐行识别结果（可修改；右侧画布：按住 Shift 拖拽新建 ROI，直接拖拽移动，角点缩放，选中后按 Delete 删除）："))

        body = QHBoxLayout()
        if image is not None and not image.isNull():
            self.canvas = RoiCanvas()
            self.canvas.set_image(image)
            if manager is not None:
                rois = split_formula_line_rects(image)
                self.canvas.set_rois(rois)
            self.canvas.rois_changed.connect(lambda: self._auto_timer.start())
            body.addWidget(self.canvas, 3)
            right = QWidget()
            right_layout = QVBoxLayout(right)
            right_layout.addWidget(self.lines_scroll, 1)
            buttons = QHBoxLayout()
            auto_button = QPushButton("自动拆分")
            recognize_button = QPushButton("识别选中 ROI")
            clear_roi_button = QPushButton("清空 ROI")
            clear_content_button = QPushButton("清空识别内容")
            auto_button.clicked.connect(self._auto_split)
            recognize_button.clicked.connect(self._recognize_selected)
            clear_roi_button.clicked.connect(self.canvas.clear)
            clear_content_button.clicked.connect(self._clear_content)
            buttons.addWidget(auto_button)
            buttons.addWidget(recognize_button)
            buttons.addWidget(clear_roi_button)
            buttons.addWidget(clear_content_button)
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
            layout.addWidget(self.lines_scroll, 1)
        layout.addLayout(body, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("应用为 aligned")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        """Idempotent submit: a repeated OK event must not emit output twice."""

        if self._submitted:
            return
        self._submitted = True
        super().accept()

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
        if self._image is None or self._manager is None or self._recognizing:
            return
        self._recognizing = True
        try:
            rois = self.canvas.rois()
            lines = [self._recognize_one(index, rois) for index in range(len(rois))]
        finally:
            self._recognizing = False
        self._set_lines(lines)

    def _recognize_selected(self) -> None:
        index = getattr(self.canvas, "_selected", None)
        if index is None or self._recognizing:
            return
        latex = self._recognize_one(index, self.canvas.rois())
        if index < len(self.line_edits):
            self.line_edits[index].setText(latex)
        else:
            self._add_line_edit(latex)

    def _recognize_one(self, index: int, rois: list) -> str:
        if self._image is None or self._manager is None or not (0 <= index < len(rois)):
            return ""
        crop = self._image.copy(rois[index])
        temp = save_temp(crop)
        result = _wait_ocr(self._manager, temp)
        if result is None:
            return ""
        sanitized = sanitize_formula_latex(result.latex)
        return sanitized.text if sanitized.ok else result.latex

    def _clear_content(self) -> None:
        for edit in self.line_edits:
            edit.setText("")

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
