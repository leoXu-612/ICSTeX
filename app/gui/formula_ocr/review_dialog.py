"""Recognition review dialog: image + candidate, human confirms before use."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.formula.sanitizer import SanitizeResult


class RecognitionReviewDialog(QDialog):
    """Shows the source image and the OCR candidate for explicit confirmation."""

    def __init__(self, image_path, candidate: str, sanitize: SanitizeResult, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("公式识别预览")
        self.resize(860, 520)
        self._candidate = candidate
        self._sanitize = sanitize
        self._submitted = False

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
        image_panel.setObjectName("ocrImagePanel")
        image_layout = QVBoxLayout(image_panel)
        image_layout.addWidget(QLabel("原始公式图片"))
        image_layout.addWidget(image_label)
        image_layout.addStretch()

        self.latex_edit = QPlainTextEdit()
        self.latex_edit.setPlainText(candidate)
        self.latex_edit.setAccessibleName("识别候选 LaTeX")
        status = "解析/安全检查通过" if sanitize.ok else "存在警告或错误：" + "; ".join(sanitize.errors or sanitize.warnings)
        self.status_label = QLabel(status)
        self.status_label.setWordWrap(True)

        buttons = QHBoxLayout()
        self.reject_button = QPushButton("取消")
        self.apply_button = QPushButton("应用候选公式")
        self.reject_button.clicked.connect(self.reject)
        self.apply_button.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(self.reject_button)
        buttons.addWidget(self.apply_button)

        right = QVBoxLayout()
        right.addWidget(QLabel("识别候选（请人工核对）"))
        right.addWidget(self.latex_edit)
        right.addWidget(self.status_label)
        right.addLayout(buttons)

        layout = QHBoxLayout(self)
        layout.addWidget(image_panel, 1)
        layout.addLayout(right, 2)

    def confirmed_latex(self) -> str:
        return self.latex_edit.toPlainText().strip()

    def accept(self) -> None:
        """Idempotent submit: a repeated OK event must not emit output twice."""

        if self._submitted:
            return
        self._submitted = True
        super().accept()
