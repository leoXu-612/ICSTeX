"""Chinese, keyboard-accessible presentation of identified read-only checks."""
from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel,
                              QPlainTextEdit, QPushButton, QSplitter, QTreeWidget,
                              QTreeWidgetItem, QVBoxLayout, QWidget)

from app.core.submission_check import CheckReport, STATUS_LABELS


class SubmissionCheckPanel(QWidget):
    refreshRequested = Signal()
    cancelRequested = Signal()
    actionRequested = Signal(int)

    def __init__(self):
        super().__init__()
        self.report: CheckReport | None = None
        self.setObjectName("submissionCheckPanel")
        self.summary = QLabel("尚未检查。只读检查不会保存、编译或联网。")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.refresh_button = QPushButton("重新检查")
        self.cancel_button = QPushButton("取消检查")
        self.cancel_button.setEnabled(False)
        self.action_button = QPushButton("下一步")
        self.action_button.setEnabled(False)
        self.tree = QTreeWidget()
        self.tree.setAccessibleName("提交检查结果")
        self.tree.setHeaderLabels(["状态", "检查项"])
        self.tree.setRootIsDecorated(False)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(True)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setAccessibleName("原因、证据和输入身份")
        self.detail.setPlaceholderText("选择检查项查看原因、证据位置与下一步。")
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self.tree)
        split.addWidget(self.detail)
        split.setSizes([220, 520])
        split.setChildrenCollapsible(False)
        row = QHBoxLayout()
        row.addWidget(self.summary, 1)
        row.addWidget(self.refresh_button)
        row.addWidget(self.cancel_button)
        row.addWidget(self.action_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addLayout(row)
        layout.addWidget(split)
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)
        self.tree.currentItemChanged.connect(self._selection_changed)
        self.tree.itemActivated.connect(lambda *_: self._activate())
        self.action_button.clicked.connect(self._activate)

    def pending(self, message: str, *, busy: bool = False):
        self.report = None
        self.tree.clear()
        self.detail.clear()
        self.summary.setText(message)
        self.action_button.setEnabled(False)
        self.cancel_button.setEnabled(busy)

    def set_report(self, report: CheckReport):
        self.tree.clear()
        self.report = report
        self.cancel_button.setEnabled(False)
        stamp = datetime.fromtimestamp(report.checked_at).strftime("%H:%M:%S")
        self.summary.setText(f"检查时间 {stamp} · 当前捕获输入 · 技术检查不等于学术合规。")
        for index, item in enumerate(report.items):
            row = QTreeWidgetItem([STATUS_LABELS[item.status], item.title])
            row.setData(0, Qt.ItemDataRole.UserRole, index)
            row.setToolTip(1, item.reason)
            self.tree.addTopLevelItem(row)
        if self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def _selection_changed(self, *_):
        row = self.tree.currentItem()
        if row is None or self.report is None:
            self.action_button.setEnabled(False)
            return
        item = self.report.items[row.data(0, Qt.ItemDataRole.UserRole)]
        location = str(item.file) + (f":{item.line}" if item.line else "") if item.file else "当前项目"
        self.detail.setPlainText(
            f"{item.title} · {STATUS_LABELS[item.status]}\n{item.reason}\n\n"
            f"证据：{location}\n规则：{item.rule_id}\n输入身份：{item.input_id}"
        )
        labels = {"save": "保存项目文档", "compile": "正式编译", "navigate": "定位源码",
                  "environment": "环境医生", "word_count": "查看字数", "profile": "项目配置"}
        self.action_button.setText(labels.get(item.action, "查看说明"))
        self.action_button.setEnabled(item.action in labels and
                                      (item.action != "navigate" or item.file is not None))

    def _activate(self):
        row = self.tree.currentItem()
        if row is not None and self.report is not None and self.action_button.isEnabled():
            self.actionRequested.emit(row.data(0, Qt.ItemDataRole.UserRole))
