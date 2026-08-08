"""Review RapidOCR text output before creating a Text Block."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


def _confidence_summary(payload: dict) -> str:
    regions = payload.get("regions") or []
    if not regions:
        return "未返回区域置信度"
    scores = [float(r.get("confidence", 0.0)) for r in regions if r.get("confidence") is not None]
    if not scores:
        return f"识别区域 {len(regions)} 个"
    average = sum(scores) / len(scores)
    return f"识别区域 {len(regions)} 个，平均置信度 {average:.2f}"


class TextReviewDialog(QDialog):
    """Shows the source image and the editable recognized text."""

    def __init__(self, image_path: Path, text: str, payload: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("文字识别预览")
        self.resize(780, 480)
        self._submitted = False

        body = QHBoxLayout(self)

        image_label = QLabel()
        pixmap = QPixmap(str(image_path))
        if not pixmap.isNull():
            image_label.setPixmap(
                pixmap.scaled(
                    360,
                    360,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_panel = QWidget()
        image_layout = QVBoxLayout(image_panel)
        image_layout.addWidget(QLabel("原始图片"))
        image_layout.addWidget(image_label)
        image_layout.addStretch()
        body.addWidget(image_panel, 2)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("识别文字（可修改，空内容不会创建 Block）："))
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setAccessibleName("识别文字")
        right_layout.addWidget(self.text_edit, 1)
        self.status_label = QLabel(_confidence_summary(payload))
        self.status_label.setWordWrap(True)
        right_layout.addWidget(self.status_label)
        body.addWidget(right, 3)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("创建 Text Block")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        body.addWidget(buttons, 0, Qt.AlignmentFlag.AlignRight)

    def accept(self) -> None:
        """Idempotent submit: a repeated OK event must not create twice."""

        if self._submitted:
            return
        self._submitted = True
        super().accept()

    def result_text(self) -> str:
        return self.text_edit.toPlainText().strip()
