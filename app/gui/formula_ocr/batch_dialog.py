"""Unified batch image recognition window: queue + progress + review."""
from __future__ import annotations

import time
import uuid
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.formula.line_splitter import split_formula_lines
from app.core.formula.sanitizer import sanitize_formula_latex
from app.gui.formula_ocr.image_input import (
    image_fingerprint,
    image_from_clipboard,
    preprocess,
    save_temp,
)
from app.gui.formula_ocr.multi_line_dialog import MultiLineOcrDialog, _wait_ocr
from app.optional_tools.pix2tex.protocol import RecognitionRequest


class BatchRecognitionDialog(QDialog):
    """Batch formula images -> queue -> sequential OCR -> combined LaTeX."""

    def __init__(self, manager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("图片识别")
        self.resize(760, 520)
        self._manager = manager
        self._images: list[tuple[str, QImage]] = []
        self._results: dict[int, str] = {}
        self._cancel = False
        self._starting = False
        self._submitted = False
        self._fine_tune_open = False
        self._fine_tune_ts = 0.0
        self._fingerprints: set[str] = set()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("批量添加公式图片，顺序识别；识别后可在右侧核对/修改，再插入编辑器。"))

        body = QHBoxLayout()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.image_list = QListWidget()
        left_layout.addWidget(QLabel("识别队列："))
        left_layout.addWidget(self.image_list)
        buttons = QHBoxLayout()
        self.add_files_button = QPushButton("添加图片…")
        self.add_clipboard_button = QPushButton("从剪贴板添加")
        self.remove_button = QPushButton("移除选中")
        self.clear_button = QPushButton("清空队列")
        self.add_files_button.clicked.connect(self._add_files)
        self.add_clipboard_button.clicked.connect(self._add_clipboard)
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button.clicked.connect(self._clear_queue)
        for button in (self.add_files_button, self.add_clipboard_button, self.remove_button, self.clear_button):
            buttons.addWidget(button)
        left_layout.addLayout(buttons)
        self.start_button = QPushButton("开始识别")
        self.cancel_button = QPushButton("取消识别")
        self.fine_tune_button = QPushButton("精调当前（逐行/ROI）")
        self.start_button.clicked.connect(self._start)
        self.cancel_button.clicked.connect(self._request_cancel)
        self.fine_tune_button.clicked.connect(self._fine_tune_current)
        action_row = QHBoxLayout()
        action_row.addWidget(self.start_button)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.fine_tune_button)
        left_layout.addLayout(action_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        left_layout.addWidget(self.progress)
        self.status_label = QLabel("就绪")
        left_layout.addWidget(self.status_label)
        body.addWidget(left, 2)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("识别结果（LaTeX，可编辑）："))
        self.result_edit = QPlainTextEdit()
        self.result_edit.setAccessibleName("识别结果 LaTeX")
        right_layout.addWidget(self.result_edit)
        body.addWidget(right, 3)
        layout.addLayout(body, 1)

        buttons_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons_box.button(QDialogButtonBox.StandardButton.Ok).setText("插入到编辑器")
        buttons_box.button(QDialogButtonBox.StandardButton.Cancel).setText("关闭")
        buttons_box.accepted.connect(self.accept)
        buttons_box.rejected.connect(self.reject)
        layout.addWidget(buttons_box)

    def accept(self) -> None:
        """Idempotent submit: a repeated OK event must not emit output twice."""

        if self._submitted:
            return
        self._submitted = True
        super().accept()

    # --- queue -----------------------------------------------------------
    def _add_files(self) -> None:
        file_names, _ = QFileDialog.getOpenFileNames(self, "选择公式图片", "", "图片 (*.png *.jpg *.jpeg *.webp)")
        for file_name in file_names:
            from app.gui.formula_ocr.image_input import image_from_file

            image = image_from_file(Path(file_name))
            if image is not None:
                self._append_image(Path(file_name).name, image)

    def _add_clipboard(self) -> None:
        image = image_from_clipboard()
        if image is None:
            QMessageBox.information(self, "图片识别", "剪贴板中没有图片。")
            return
        self._append_image("剪贴板图片", image)

    def _append_image(self, name: str, image: QImage) -> None:
        fingerprint = image_fingerprint(image)
        if fingerprint in self._fingerprints:
            self.status_label.setText(f"已跳过重复图片：{name}")
            return
        self._fingerprints.add(fingerprint)
        self._images.append((name, preprocess(image)))
        self.image_list.addItem(name)
        self.progress.setRange(0, max(1, len(self._images)))

    def _remove_selected(self) -> None:
        rows = sorted({self.image_list.row(item) for item in self.image_list.selectedItems()}, reverse=True)
        for row in rows:
            del self._images[row]
            self.image_list.takeItem(row)
        self._rebuild_fingerprints()
        self.progress.setRange(0, max(1, len(self._images)))

    def _clear_queue(self) -> None:
        self._images = []
        self.image_list.clear()
        self._results = {}
        self._fingerprints = set()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

    def _rebuild_fingerprints(self) -> None:
        self._fingerprints = {image_fingerprint(image) for _name, image in self._images}

    def _request_cancel(self) -> None:
        self._cancel = True

    # --- recognition -----------------------------------------------------
    def _start(self) -> None:
        if not self._images:
            QMessageBox.information(self, "图片识别", "请先添加图片。")
            return
        if self._starting:
            return
        self._starting = True
        self._cancel = False
        self.start_button.setEnabled(False)
        blocks: list[str] = []
        try:
            for index, (_name, image) in enumerate(self._images):
                if self._cancel:
                    break
                self.status_label.setText(f"识别中 {index + 1}/{len(self._images)}…")
                QApplication.processEvents()
                try:
                    lines = self._recognize_image(image)
                except Exception:  # noqa: BLE001 - one bad image must not abort the queue
                    lines = []
                if lines:
                    if len(lines) > 1:
                        blocks.append("\\begin{aligned}\n" + " \\\\\n".join(lines) + "\n\\end{aligned}")
                    else:
                        blocks.append(lines[0])
                self._results[index] = "\n\n".join(blocks)
                self.progress.setValue(index + 1)
                QApplication.processEvents()
        finally:
            self._starting = False
        self.start_button.setEnabled(True)
        self.status_label.setText("完成" if not self._cancel else "已取消")
        combined = "\n\n".join(block for block in blocks if block)
        self._results["_combined"] = combined
        self.result_edit.setPlainText(combined)

    def _recognize_image(self, image: QImage) -> list[str]:
        crops = split_formula_lines(image)
        lines: list[str] = []
        for crop in crops:
            if self._cancel:
                break
            temp = save_temp(crop)
            result = _wait_ocr(self._manager, temp)
            if result is None:
                continue
            sanitized = sanitize_formula_latex(result.latex)
            lines.append(sanitized.text if sanitized.ok else result.latex)
        return lines

    def _fine_tune_current(self) -> None:
        if self._fine_tune_open or time.monotonic() - self._fine_tune_ts < 0.4:
            return
        row = self.image_list.currentRow()
        if row < 0 or row >= len(self._images):
            return
        _name, image = self._images[row]
        self._fine_tune_open = True
        self.fine_tune_button.setEnabled(False)
        try:
            dialog = MultiLineOcrDialog(None, image=image, manager=self._manager, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                latex = dialog.result_latex()
                if latex:
                    self._results[row] = latex
                    self._refresh_result_text()
        finally:
            self._fine_tune_open = False
            self._fine_tune_ts = time.monotonic()
            self.fine_tune_button.setEnabled(True)

    def _refresh_result_text(self) -> None:
        parts = [self._results.get(index) for index in range(len(self._images)) if self._results.get(index)]
        self.result_edit.setPlainText("\n\n".join(parts))

    def combined_latex(self) -> str:
        text = self.result_edit.toPlainText().strip()
        if text:
            return text
        return self._results.get("_combined", "")
