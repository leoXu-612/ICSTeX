"""Independent merge candidate preview; confirmation never writes a project."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QDialogButtonBox, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QRadioButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

from app.core.blocks.source_merge import MergeResult, resolve_merge
from app.core.blocks.table_model import Cell

MAX_PREVIEW_CHARS = 262144
MAX_CONFLICT_CONTROLS = 200


def _preview_json(value):
    chunks, size = [], 0
    for chunk in json.JSONEncoder(ensure_ascii=False, indent=2).iterencode(value):
        size += len(chunk)
        if size > MAX_PREVIEW_CHARS:
            return "预览超过显示上限，未确认；请缩小本次比较范围。", False
        chunks.append(chunk)
    return "".join(chunks), True


class MergeDialog(QDialog):
    """Choose conflicts, inspect a fresh candidate, then confirm a detached result."""

    def __init__(self, result: MergeResult, parent=None) -> None:
        super().__init__(parent)
        self._input = deepcopy(result)
        self.result = deepcopy(result)
        self._candidate = None
        self.setWindowTitle("合并候选预览（不应用）")
        self.resize(760, 640)
        self._remote_buttons = []
        self._local_buttons = []
        self._manual_buttons = []
        self._manual_edits = []
        self._complete_preview = True
        layout = QVBoxLayout(self)
        self.status = QLabel("选择后更新预览，再确认候选；不会修改表格、来源基线或文件。")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        controls = QWidget()
        choices_layout = QVBoxLayout(controls)
        self.table_remote_button = QRadioButton("采用完整外部表格（不混入本地修改）")
        self.table_local_button = QRadioButton("保留完整本地表格（不混入外部修改）")
        if result.table_conflict is not None:
            label = QLabel("两侧同时变化，且行列、顺序或表格属性不同；不能按位置猜测合并。请比较三份完整内容。")
            label.setWordWrap(True)
            choices_layout.addWidget(label)
            choices_layout.addWidget(self.table_local_button)
            choices_layout.addWidget(self.table_remote_button)
            group = QButtonGroup(self)
            group.addButton(self.table_remote_button)
            group.addButton(self.table_local_button)
            self.table_local_button.setChecked(True)
            self.table_remote_button.toggled.connect(self._invalidate_preview)
        else:
            for conflict in result.conflicts[:MAX_CONFLICT_CONTROLS]:
                row = QWidget()
                row_layout = QVBoxLayout(row)
                label = QLabel(f"{conflict.rowId[:256]}/{conflict.columnId[:256]} · 基线：{_value(conflict.base)[:256]}")
                label.setTextFormat(Qt.TextFormat.PlainText)
                label.setWordWrap(True)
                row_layout.addWidget(label)
                remote = QRadioButton(f"采用外部：{_value(conflict.remote)[:256]}")
                local = QRadioButton(f"采用本地：{_value(conflict.local)[:256]}")
                manual_button = QRadioButton("手动文本（保留空白，可为空；完整值见预览）")
                manual = QLineEdit()
                manual.setMaxLength(MAX_PREVIEW_CHARS)
                group = QButtonGroup(self)
                for button in (local, remote, manual_button):
                    group.addButton(button)
                    row_layout.addWidget(button)
                local.setChecked(True)
                group.buttonToggled.connect(self._invalidate_preview)
                manual.textChanged.connect(lambda _text, button=manual_button: button.setChecked(True))
                manual.textChanged.connect(self._invalidate_preview)
                row_layout.addWidget(manual)
                self._remote_buttons.append(remote)
                self._local_buttons.append(local)
                self._manual_buttons.append(manual_button)
                self._manual_edits.append(manual)
                choices_layout.addWidget(row)
            if len(result.conflicts) > MAX_CONFLICT_CONTROLS:
                self._complete_preview = False
                choices_layout.addWidget(QLabel("冲突超过 200 处，本次不能确认不完整预览。"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        layout.addWidget(scroll, 1)
        self.preview_button = QPushButton("更新差异预览")
        self.preview_button.clicked.connect(self._update_preview)
        layout.addWidget(self.preview_button)
        self.preview_tabs = QTabWidget()
        self.preview = self._add_preview("候选（未应用）", {})
        if result.table_conflict:
            for name, data in (("基线", result.table_conflict.base), ("外部", result.table_conflict.remote),
                               ("本地", result.table_conflict.local)):
                self._add_preview(name, {"tableId": data.table_id, **data.to_content_dict()})
        else:
            self._add_preview("冲突原值", [asdict(conflict) for conflict in result.conflicts])
        layout.addWidget(self.preview_tabs, 2)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确认候选（未应用）")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.accepted.connect(self._resolve)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._update_preview()

    def _add_preview(self, name, value):
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        text, complete = _preview_json(value)
        self._complete_preview &= complete
        editor.setPlainText(text)
        self.preview_tabs.addTab(editor, name)
        return editor

    def _invalidate_preview(self, *_args):
        self._candidate = None
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.status.setText("选择已变化；请更新差异预览后再确认。原始内容未修改。")

    def _update_preview(self):
        try:
            choices = tuple(Cell("text", edit.text()) if manual.isChecked() else
                            "remote" if remote.isChecked() else "local"
                            for edit, manual, remote in zip(self._manual_edits, self._manual_buttons, self._remote_buttons))
            table_choice = ("remote" if self.table_remote_button.isChecked() else "local") if self._input.table_conflict else None
            candidate = resolve_merge(self._input, choices, table_choice=table_choice)
            text, complete = _preview_json({"tableId": candidate.data.table_id, **candidate.data.to_content_dict()})
            self.preview.setPlainText(text)
            self._candidate = candidate if complete and self._complete_preview else None
            self.status.setText("候选已更新；确认仅返回这份独立候选，尚未应用或保存。" if self._candidate else
                                "无法完整显示本次比较；未确认、未修改，请缩小范围。")
        except (ValueError, TypeError) as exc:
            self._candidate = None
            self.status.setText(f"不能生成候选：{exc}")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(self._candidate is not None)

    def _resolve(self):
        if self._candidate is None:
            self.status.setText("请先生成完整、最新的差异预览；没有修改原始内容。")
            return
        self.result = deepcopy(self._candidate)
        self.accept()


def _value(cell: Cell | None) -> str:
    if cell is None:
        return "（无此单元格）"
    return f"[{cell.kind}] " + ("" if cell.kind == "empty" else str(cell.value))
