"""Unified batch image recognition window: queue + per-item status + retry."""
from __future__ import annotations

import functools
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QImage, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.formula.line_splitter import split_formula_lines
from app.core.formula.sanitizer import sanitize_formula_latex
from app.gui.formula_ocr import DIALOG_OPEN_DEBOUNCE_SECONDS
from app.gui.formula_ocr.image_input import (
    image_fingerprint,
    image_from_clipboard,
    preprocess,
    save_temp,
)
from app.gui.formula_ocr.multi_line_dialog import MultiLineOcrDialog, _wait_ocr


STATUS_PENDING = "pending"
STATUS_RECOGNIZING = "recognizing"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_REFINED = "refined"

STATUS_LABELS = {
    STATUS_PENDING: "待识别",
    STATUS_RECOGNIZING: "识别中…",
    STATUS_SUCCEEDED: "成功",
    STATUS_FAILED: "失败",
    STATUS_CANCELLED: "已取消",
    STATUS_REFINED: "已精调",
}
STATUS_COLORS = {
    STATUS_PENDING: "#6b7280",
    STATUS_RECOGNIZING: "#2563eb",
    STATUS_SUCCEEDED: "#15803d",
    STATUS_FAILED: "#b91c1c",
    STATUS_CANCELLED: "#9ca3af",
    STATUS_REFINED: "#7c3aed",
}


@dataclass
class QueueItem:
    """One queued formula image with its independent recognition state."""

    name: str
    image: QImage
    status: str = STATUS_PENDING
    error: str = ""
    result: str = ""


class _RowFrame(QFrame):
    """Selectable row: click selects, buttons stay independent of selection."""

    def __init__(self, index: int, select_callback) -> None:
        super().__init__()
        self._index = index
        self._select_callback = select_callback
        self.setObjectName("ocrRow")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.set_selected(False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._select_callback(self._index)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet(
                "QFrame#ocrRow { background:#eef4ff; border:1px solid #2563eb; border-radius:6px; }"
            )
        else:
            self.setStyleSheet(
                "QFrame#ocrRow { background:#ffffff; border:1px solid #d9d9d4; border-radius:6px; }"
            )


class BatchRecognitionDialog(QDialog):
    """Batch formula images -> queue -> sequential OCR -> combined LaTeX.

    Every queue item carries an explicit status (Pending / Recognizing /
    Succeeded / Failed / Cancelled / Refined) so a failed item is visible
    instead of being silently skipped, and can be retried or inspected.
    """

    def __init__(self, manager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("图片识别")
        self.resize(820, 560)
        self._manager = manager
        self._items: list[QueueItem] = []
        self._rows: list[_RowFrame] = []
        self._current_row = -1
        self._cancel = False
        self._starting = False
        self._submitted = False
        self._fine_tune_open = False
        self._fine_tune_ts = 0.0
        self._fingerprints: set[str] = set()
        self._result_manual = False
        self._syncing_result = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("批量添加公式图片，顺序识别；每行可重试/查看错误/移除，识别后可在右侧核对再插入编辑器。"))

        body = QHBoxLayout()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("识别队列（点击行选中，用于精调）："))

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        self.rows_scroll = QScrollArea()
        self.rows_scroll.setWidgetResizable(True)
        self.rows_scroll.setWidget(self.rows_container)
        self.rows_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        left_layout.addWidget(self.rows_scroll, 1)

        add_row = QHBoxLayout()
        self.add_files_button = QPushButton("添加图片…")
        self.add_clipboard_button = QPushButton("从剪贴板添加")
        self.clear_button = QPushButton("清空队列")
        self.add_files_button.clicked.connect(self._add_files)
        self.add_clipboard_button.clicked.connect(self._add_clipboard)
        self.clear_button.clicked.connect(self._clear_queue)
        for button in (self.add_files_button, self.add_clipboard_button, self.clear_button):
            add_row.addWidget(button)
        add_row.addStretch()
        left_layout.addLayout(add_row)

        opts_row = QHBoxLayout()
        self.allow_duplicates_check = QCheckBox("允许相同图片重复入队")
        self.allow_duplicates_check.setChecked(False)
        self.allow_duplicates_check.setToolTip("默认按图片内容去重；勾选后完全相同的图片可多次入队。")
        opts_row.addWidget(self.allow_duplicates_check)
        opts_row.addStretch()
        left_layout.addLayout(opts_row)

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
        self.result_edit.textChanged.connect(self._on_result_edited)
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
        if not self.allow_duplicates_check.isChecked() and fingerprint in self._fingerprints:
            self.status_label.setText(f"已跳过重复图片：{name}")
            return
        self._fingerprints.add(fingerprint)
        item = QueueItem(name=name, image=preprocess(image))
        self._items.append(item)
        self._insert_row(len(self._items) - 1)
        self.progress.setRange(0, max(1, len(self._items)))

    def _insert_row(self, index: int) -> None:
        item = self._items[index]
        row = _RowFrame(index, self._select_row)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 4, 6, 4)

        name_label = QLabel(item.name)
        name_label.setToolTip(item.name)
        status_label = QLabel(STATUS_LABELS[item.status])
        retry_button = QPushButton("重试此项")
        retry_button.setToolTip("重新识别当前项")
        retry_button.setEnabled(False)
        error_button = QPushButton("查看错误")
        error_button.setEnabled(False)
        remove_button = QPushButton("从批次移除")

        row.name_label = name_label
        row.status_label = status_label
        row.retry_button = retry_button
        row.error_button = error_button
        row.remove_button = remove_button

        retry_button.clicked.connect(functools.partial(self._retry_row, row))
        error_button.clicked.connect(functools.partial(self._view_error_row, row))
        remove_button.clicked.connect(functools.partial(self._remove_row, row))

        row_layout.addWidget(name_label, 1)
        row_layout.addWidget(status_label)
        row_layout.addWidget(retry_button)
        row_layout.addWidget(error_button)
        row_layout.addWidget(remove_button)

        self._rows.append(row)
        self.rows_layout.addWidget(row)
        self._update_row_ui(index)

    def _select_row(self, index: int) -> None:
        if not (0 <= index < len(self._rows)):
            return
        self._current_row = index
        for row_index, row in enumerate(self._rows):
            row.set_selected(row_index == index)

    def select_row(self, index: int) -> None:
        """Public helper (used by tests and fine-tune flow)."""

        self._select_row(index)

    def _row_index(self, row: QWidget) -> int:
        try:
            return self._rows.index(row)
        except ValueError:
            return -1

    def _remove_selected(self) -> None:
        if 0 <= self._current_row < len(self._rows):
            self._remove_row(self._rows[self._current_row])

    def _remove_row(self, row: QWidget) -> None:
        if self._starting:
            return
        index = self._row_index(row)
        if index < 0:
            return
        name = self._items[index].name
        del self._items[index]
        self.rows_layout.removeWidget(row)
        row.setParent(None)
        del self._rows[index]
        if self._current_row == index:
            self._current_row = -1
        elif self._current_row > index:
            self._current_row -= 1
        self._rebuild_fingerprints()
        self.progress.setRange(0, max(1, len(self._items)))
        self.status_label.setText(f"已从批次移除：{name}")
        self._refresh_result_text()

    def _clear_queue(self) -> None:
        self._items = []
        for row in self._rows:
            self.rows_layout.removeWidget(row)
            row.setParent(None)
        self._rows = []
        self._current_row = -1
        self._fingerprints = set()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status_label.setText("队列已清空")
        self._syncing_result = True
        try:
            self.result_edit.clear()
        finally:
            self._syncing_result = False
        self._result_manual = False

    def _rebuild_fingerprints(self) -> None:
        self._fingerprints = {image_fingerprint(item.image) for item in self._items}

    def _request_cancel(self) -> None:
        self._cancel = True

    # --- per-item UI -----------------------------------------------------
    def _set_status(self, index: int, status: str) -> None:
        self._items[index].status = status
        self._update_row_ui(index)

    def _update_row_ui(self, index: int) -> None:
        item = self._items[index]
        row = self._rows[index]
        row.status_label.setText(STATUS_LABELS[item.status])
        row.status_label.setStyleSheet(f"color:{STATUS_COLORS[item.status]}; font-weight:600;")
        row.retry_button.setEnabled(item.status in (STATUS_FAILED, STATUS_CANCELLED) and not self._starting)
        row.error_button.setEnabled(bool(item.error))

    def _set_rows_enabled(self, enabled: bool) -> None:
        for index, row in enumerate(self._rows):
            row.remove_button.setEnabled(enabled)
            row.name_label.setEnabled(enabled)
            self._update_row_ui(index)

    # --- recognition -----------------------------------------------------
    def _start(self) -> None:
        if not self._items:
            QMessageBox.information(self, "图片识别", "请先添加图片。")
            return
        if self._starting:
            return
        if not self._confirm_overwrite_manual_result():
            return
        self._starting = True
        self._cancel = False
        self.start_button.setEnabled(False)
        self._set_rows_enabled(False)
        total = len(self._items)
        try:
            for index, item in enumerate(self._items):
                if self._cancel:
                    self._set_status(index, STATUS_CANCELLED)
                    continue
                self.status_label.setText(f"识别中 {index + 1}/{total}…")
                self._set_status(index, STATUS_RECOGNIZING)
                QApplication.processEvents()
                try:
                    lines = self._recognize_image(item.image)
                    error = ""
                except Exception as exc:  # noqa: BLE001 - one bad image must not abort the queue
                    lines = []
                    error = f"识别异常：{exc}"
                if lines:
                    item.result = self._join_lines(lines)
                    item.error = ""
                    self._set_status(index, STATUS_SUCCEEDED)
                else:
                    item.result = ""
                    item.error = error or "未识别到内容（图片可能过空或模型未输出）"
                    self._set_status(index, STATUS_FAILED)
                self.progress.setValue(index + 1)
                QApplication.processEvents()
        finally:
            self._starting = False
            self.start_button.setEnabled(True)
            self._set_rows_enabled(True)
        self.status_label.setText("完成" if not self._cancel else "已取消")
        self._refresh_result_text()

    def _retry_row(self, row: QWidget) -> None:
        index = self._row_index(row)
        if index < 0 or self._starting:
            return
        self._retry_item(index)

    def _retry_item(self, index: int) -> None:
        if self._starting or not (0 <= index < len(self._items)):
            return
        if not self._confirm_overwrite_manual_result():
            return
        self._starting = True
        self.start_button.setEnabled(False)
        self._set_rows_enabled(False)
        item = self._items[index]
        try:
            self._set_status(index, STATUS_RECOGNIZING)
            QApplication.processEvents()
            try:
                lines = self._recognize_image(item.image)
                error = ""
            except Exception as exc:  # noqa: BLE001 - one bad image must not abort the queue
                lines = []
                error = f"识别异常：{exc}"
            if lines:
                item.result = self._join_lines(lines)
                item.error = ""
                self._set_status(index, STATUS_SUCCEEDED)
            else:
                item.result = ""
                item.error = error or "未识别到内容（图片可能过空或模型未输出）"
                self._set_status(index, STATUS_FAILED)
        finally:
            self._starting = False
            self.start_button.setEnabled(True)
            self._set_rows_enabled(True)
        self.status_label.setText("重试完成")
        self._refresh_result_text()

    def _view_error_row(self, row: QWidget) -> None:
        index = self._row_index(row)
        if index < 0:
            return
        item = self._items[index]
        QMessageBox.warning(
            self,
            "识别失败详情",
            f"图片：{item.name}\n\n{item.error or '未知错误'}",
        )

    def _on_result_edited(self) -> None:
        if not self._syncing_result:
            self._result_manual = True

    def _confirm_overwrite_manual_result(self) -> bool:
        if not self._result_manual:
            return True
        answer = QMessageBox.question(
            self,
            "重新识别",
            "你已手动修改合并结果，重新识别将覆盖手动修改。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        self._result_manual = False
        return True

    def _join_lines(self, lines: list[str]) -> str:
        if len(lines) > 1:
            return "\\begin{aligned}\n" + " \\\\\n".join(lines) + "\n\\end{aligned}"
        return lines[0]

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
        if self._fine_tune_open or time.monotonic() - self._fine_tune_ts < DIALOG_OPEN_DEBOUNCE_SECONDS:
            return
        index = self._current_row
        if index < 0 or index >= len(self._items):
            QMessageBox.information(self, "精调", "请先在左侧队列中点击选择要精调的图片。")
            return
        item = self._items[index]
        self._fine_tune_open = True
        self.fine_tune_button.setEnabled(False)
        try:
            dialog = MultiLineOcrDialog(None, image=item.image, manager=self._manager, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                latex = dialog.result_latex()
                if latex:
                    item.result = latex
                    item.error = ""
                    self._set_status(index, STATUS_REFINED)
                    self._refresh_result_text()
        finally:
            self._fine_tune_open = False
            self._fine_tune_ts = time.monotonic()
            self.fine_tune_button.setEnabled(True)

    def _refresh_result_text(self) -> None:
        parts = [
            item.result
            for item in self._items
            if item.status in (STATUS_SUCCEEDED, STATUS_REFINED) and item.result
        ]
        self._syncing_result = True
        try:
            self.result_edit.setPlainText("\n\n".join(parts))
        finally:
            self._syncing_result = False

    def combined_latex(self) -> str:
        text = self.result_edit.toPlainText().strip()
        if text:
            return text
        parts = [
            item.result
            for item in self._items
            if item.status in (STATUS_SUCCEEDED, STATUS_REFINED) and item.result
        ]
        return "\n\n".join(parts)
