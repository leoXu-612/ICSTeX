"""Chinese, keyboard-accessible presentation of identified read-only checks."""
from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel,
                              QPlainTextEdit, QPushButton, QSplitter, QStackedWidget, QTreeWidget,
                              QTreeWidgetItem, QVBoxLayout, QWidget)

from app.core.submission_check import CheckReport, CheckStatus, STATUS_LABELS
from app.gui.theme import COLOR_ERROR, COLOR_SUCCESS, COLOR_TEXT_MUTED, COLOR_WARNING, PRIMARY_BUTTON_STATE_STYLE


_ACTIONS = {"save": "保存项目文档", "compile": "正式编译", "navigate": "定位源码",
            "environment": "环境医生", "word_count": "查看字数", "profile": "项目配置"}
_PRIORITY = {CheckStatus.FAIL: 0, CheckStatus.UNKNOWN: 1, CheckStatus.CHECKING: 2,
             CheckStatus.PASS: 3, CheckStatus.NOT_APPLICABLE: 4}


class SubmissionCheckPanel(QWidget):
    refreshRequested = Signal()
    cancelRequested = Signal()
    actionRequested = Signal(int)

    def __init__(self):
        super().__init__()
        self.report: CheckReport | None = None
        self.setObjectName("submissionCheckPanel")
        self.summary = QLabel("尚未检查")
        self.summary.setObjectName("submissionSummary")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.refresh_button = QPushButton("重新检查")
        self.cancel_button = QPushButton("取消检查")
        self.cancel_button.setEnabled(False)
        self.action_button = QPushButton("下一步")
        self.action_button.setObjectName("primaryButton")
        self.action_button.setStyleSheet(PRIMARY_BUTTON_STATE_STYLE)
        self.action_button.setEnabled(False)
        self.expand_button = QPushButton("展开阅读")
        self.expand_button.setCheckable(True)
        self.expand_button.setEnabled(False)
        self.technical_button = QPushButton("技术详情")
        self.technical_button.setCheckable(True)
        self.technical_button.setEnabled(False)
        for button in (self.refresh_button, self.cancel_button, self.action_button,
                       self.expand_button, self.technical_button):
            button.setAutoDefault(False)
            button.setDefault(False)
        self.tree = QTreeWidget()
        self.tree.setAccessibleName("提交检查结果")
        self.tree.setHeaderLabels(["状态", "检查项"])
        self.tree.setRootIsDecorated(False)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(True)
        self.detail = QPlainTextEdit()
        self.detail.setObjectName("submissionReason")
        self.detail.setReadOnly(True)
        self.detail.setTabChangesFocus(True)
        self.detail.setAccessibleName("检查原因与下一步")
        self.detail.setPlaceholderText("选择检查项查看原因与下一步。")
        self.technical_detail = QPlainTextEdit()
        self.technical_detail.setReadOnly(True)
        self.technical_detail.setTabChangesFocus(True)
        self.technical_detail.setAccessibleName("技术详情：完整证据位置、规则与输入身份")
        self.reading = QStackedWidget()
        self.reading.addWidget(self.detail)
        self.reading.addWidget(self.technical_detail)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(self.reading)
        self.splitter.setSizes([220, 520])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setMinimumHeight(80)
        self._list_sizes = None
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.timeout.connect(self._size_reading_area)
        self.tree.viewport().installEventFilter(self)
        row = QHBoxLayout()
        row.addWidget(self.summary, 1)
        self.policy = QLabel("只读技术检查；未知不算通过，也不保证学术合规。")
        self.policy.setObjectName("panelHint")
        self.policy.setTextFormat(Qt.TextFormat.PlainText)
        self.policy.setWordWrap(False)
        row.addWidget(self.policy)
        footer = QHBoxLayout()
        footer.addWidget(self.expand_button)
        footer.addWidget(self.technical_button)
        footer.addWidget(self.refresh_button)
        footer.addWidget(self.cancel_button)
        footer.addStretch()
        footer.addWidget(self.action_button)
        # Only the reading area scrolls. Main actions stay reachable at either
        # end of a long reason or technical identity.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(6)
        outer.addLayout(row)
        outer.addWidget(self.splitter, 1)
        outer.addLayout(footer)
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)
        self.tree.currentItemChanged.connect(self._selection_changed)
        self.tree.itemActivated.connect(lambda *_: self._activate())
        self.action_button.clicked.connect(self._activate)
        self.expand_button.toggled.connect(self._expand_reading)
        self.technical_button.toggled.connect(self._show_technical)
        self.setTabOrder(self.refresh_button, self.cancel_button)
        self.setTabOrder(self.cancel_button, self.tree)
        self.setTabOrder(self.tree, self.detail)
        self.setTabOrder(self.detail, self.technical_detail)
        self.setTabOrder(self.technical_detail, self.expand_button)
        self.setTabOrder(self.expand_button, self.technical_button)
        self.setTabOrder(self.technical_button, self.action_button)

    def _size_reading_area(self):
        row_height = max(self.tree.sizeHintForRow(0), self.tree.fontMetrics().height())
        self.splitter.setMinimumHeight(max(80, self.reading.minimumSizeHint().height(),
                                          self.tree.header().height() + row_height + 4))
        self.updateGeometry()
        if self.tree.isVisible() and self.tree.currentItem() is not None:
            self.tree.scrollToItem(self.tree.currentItem())

    def eventFilter(self, watched, event):
        if watched is self.tree.viewport() and event.type() == QEvent.Type.Resize:
            self._layout_timer.start(0)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_timer.start(0)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange) and hasattr(self, "_layout_timer"):
            self._layout_timer.start(0)

    def _expand_reading(self, expanded):
        if expanded:
            self._list_sizes = self.splitter.sizes()
            self.tree.hide()
            self.summary.hide()
            self.policy.hide()
            self.expand_button.setText("返回列表")
        else:
            self.tree.show()
            self.summary.show()
            self.policy.show()
            if self._list_sizes:
                self.splitter.setSizes(self._list_sizes)
            self.expand_button.setText("展开阅读")
        self._layout_timer.start(0)

    def _show_technical(self, shown):
        self.reading.setCurrentWidget(self.technical_detail if shown else self.detail)

    def pending(self, message: str, *, busy: bool = False):
        self.report = None
        self.tree.clear()
        self.detail.clear()
        self.technical_detail.clear()
        self.technical_button.setChecked(False)
        self.technical_button.setEnabled(False)
        self.expand_button.setChecked(False)
        self.expand_button.setEnabled(False)
        self.summary.setText(message)
        self.action_button.setEnabled(False)
        self.action_button.setText("下一步")
        # Refresh already coalesces into one latest request in the controller.
        # Disabling the focused button would move keyboard focus mid-check.
        self.refresh_button.setEnabled(True)
        self.cancel_button.setEnabled(busy)

    def set_report(self, report: CheckReport):
        self.tree.clear()
        self.report = report
        self.refresh_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        stamp = datetime.fromtimestamp(report.checked_at).strftime("%H:%M:%S")
        counts = {status: sum(item.status is status for item in report.items) for status in CheckStatus}
        self.summary.setText(" · ".join(f"{STATUS_LABELS[status]} {counts[status]}" for status in
            (CheckStatus.FAIL, CheckStatus.UNKNOWN, CheckStatus.PASS, CheckStatus.NOT_APPLICABLE)
            if counts[status] or status in (CheckStatus.FAIL, CheckStatus.UNKNOWN, CheckStatus.PASS)))
        if counts[CheckStatus.CHECKING]:
            self.summary.setText(self.summary.text() + f" · 检查中 {counts[CheckStatus.CHECKING]}")
        self.summary.setToolTip(f"检查时间 {stamp} · 对应本次捕获输入")
        for index, item in sorted(enumerate(report.items), key=lambda pair: _PRIORITY[pair[1].status]):
            row = QTreeWidgetItem([STATUS_LABELS[item.status], item.title])
            row.setData(0, Qt.ItemDataRole.UserRole, index)
            row.setToolTip(1, f"{item.title}\n{item.reason}")
            color = {CheckStatus.FAIL: COLOR_ERROR, CheckStatus.UNKNOWN: COLOR_WARNING,
                     CheckStatus.PASS: COLOR_SUCCESS}.get(item.status, COLOR_TEXT_MUTED)
            row.setForeground(0, QColor(color))
            self.tree.addTopLevelItem(row)
        if self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self._layout_timer.start(0)

    def _selection_changed(self, *_):
        row = self.tree.currentItem()
        if row is None or self.report is None:
            self.detail.clear()
            self.technical_detail.clear()
            self.action_button.setEnabled(False)
            self.expand_button.setEnabled(False)
            self.technical_button.setEnabled(False)
            return
        item = self.report.items[row.data(0, Qt.ItemDataRole.UserRole)]
        self.tree.scrollToItem(row)
        location = str(item.file) + (f":{item.line}" if item.line else "") if item.file else "当前项目"
        self.detail.setPlainText(
            f"{item.title} · {STATUS_LABELS[item.status]}\n{item.reason}\n\n"
            f"下一步：{_ACTIONS.get(item.action, '阅读说明并确认未解决项')}。"
        )
        stamp = datetime.fromtimestamp(self.report.checked_at).strftime("%Y-%m-%d %H:%M:%S")
        self.technical_detail.setPlainText(
            f"证据：{location}\n规则：{item.rule_id}\n输入身份：{item.input_id}\n"
            f"范围：{item.scope}\n检查时间：{stamp}")
        self.expand_button.setEnabled(True)
        self.technical_button.setEnabled(True)
        self.action_button.setText(_ACTIONS.get(item.action, "无自动操作"))
        self.action_button.setEnabled(item.action in _ACTIONS and
                                      (item.action != "navigate" or item.file is not None))

    def _activate(self):
        row = self.tree.currentItem()
        if row is not None and self.report is not None and self.action_button.isEnabled():
            self.actionRequested.emit(row.data(0, Qt.ItemDataRole.UserRole))
