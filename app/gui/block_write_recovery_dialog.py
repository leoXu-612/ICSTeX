"""Review an interrupted Block transaction and recover a separate project copy."""
from pathlib import Path
import threading

from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QScrollArea, QWidget)
from shiboken6 import isValid

from app.core.blocks.write_recovery import inspect_write_journal, recover_write_journal, _sha
from app.gui.project_checkpoint_dialog import CaptureLease, _Signals, _run
from app.gui.responsive.helpers import ButtonFlowLayout
from app.gui.theme import PRIMARY_BUTTON_STATE_STYLE


class BlockWriteRecoveryDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.review = self.result = self.lease = None
        self.busy = self.closing = False
        self.cancel = threading.Event()
        self.choices = {}
        self.setWindowTitle("中断 Block 写入 · 比较并恢复为新目录")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(980, 740)
        frame = QVBoxLayout(self)
        self.scroller = QScrollArea()
        self.scroller.setWidgetResizable(True)
        body = QWidget()
        self.scroller.setWidget(body)
        frame.addWidget(self.scroller, 1)
        layout = QVBoxLayout(body)
        self.status = QLabel("选择保留 .icstex/block-write.pending 的原项目。原项目和日志不会被清理或覆盖。")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.choose_button = QPushButton("选择中断写入的项目…")
        layout.addWidget(self.choose_button)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["纳入文件", "当前磁盘 / 范围", "明确选择恢复版本"])
        self.tree.setRootIsDecorated(False)
        self.tree.setColumnWidth(0, 360)
        self.tree.setColumnWidth(1, 210)
        self.tree.setMinimumHeight(160)
        layout.addWidget(self.tree, 2)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(160)
        self.preview.setTabChangesFocus(True)
        layout.addWidget(self.preview, 2)
        row = QHBoxLayout()
        self.target = QLineEdit()
        self.target.setPlaceholderText("原项目之外、尚不存在的新目录")
        self.target_button = QPushButton("选择新目录位置…")
        row.addWidget(self.target, 1)
        row.addWidget(self.target_button)
        layout.addLayout(row)
        policy = QLabel("日志不是完整历史快照。未变更文件来自本次选定的磁盘版本；全部日志目标须明确择一。"
                        "模型与生成源码不一致时拒绝发布。原项目、日志及全部冲突版本保留；不自动打开或编译。")
        policy.setWordWrap(True)
        layout.addWidget(policy)
        buttons = ButtonFlowLayout()
        self.reveal_button = QPushButton("显示已验证恢复结果")
        self.reveal_button.hide()
        self.action_button = QPushButton("确认选择并恢复到新目录")
        self.action_button.setObjectName("primaryButton")
        self.action_button.setStyleSheet(PRIMARY_BUTTON_STATE_STYLE)
        self.action_button.setEnabled(False)
        self.close_button = QPushButton("取消 / 关闭")
        buttons.addWidget(self.reveal_button)
        buttons.addWidget(self.action_button)
        buttons.addWidget(self.close_button)
        self.resume_button = QPushButton("审阅副本中的独立草稿并继续编辑…")
        self.resume_button.hide()
        buttons.addWidget(self.resume_button)
        frame.addLayout(buttons)
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
        self.signals = _Signals(self)
        self.signals.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self.destroyed.connect(self.cancel.set)
        self.choose_button.clicked.connect(self.choose_project)
        self.target_button.clicked.connect(self.choose_target)
        self.action_button.clicked.connect(self.perform)
        self.close_button.clicked.connect(self.reject)
        self.tree.currentItemChanged.connect(self.show_preview)
        self.reveal_button.clicked.connect(self.reveal)
        self.resume_button.clicked.connect(self.resume_drafts)

    def choose_project(self):
        project = QFileDialog.getExistingDirectory(self, "选择中断写入的原项目")
        if project:
            self.load_project(project)

    def load_project(self, project):
        if self.busy:
            return
        if self.lease is not None:
            self.lease.release()
        self.review = self.result = self.lease = None
        self.tree.clear()
        self.choices.clear()
        self.preview.clear()
        self.reveal_button.hide()
        self.resume_button.hide()
        self.action_button.setEnabled(False)
        try:
            raw = Path(project).expanduser().absolute()
            if raw.is_symlink():
                raise ValueError("请选择实际项目目录，不使用目录链接。")
            project = raw.resolve(strict=True)
            self.lease = CaptureLease(self.window, project)
            self.cancel = self.lease.cancelled
            self.destroyed.connect(self.cancel.set)
            self._launch("inspect", lambda stop: inspect_write_journal(project, cancelled=stop))
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))

    def _launch(self, operation, work):
        if self.busy:
            return
        self.busy, self.operation = True, operation
        for widget in (self.choose_button, self.tree, self.target, self.target_button, self.action_button):
            widget.setEnabled(False)
        self.status.setText("正在核验清单与字节，可取消；不会写入原项目。")
        self.thread = threading.Thread(target=_run, args=(work, self.cancel, self.signals),
                                       name="icstex-write-recovery", daemon=True)
        self.thread.start()

    @Slot(object, str)
    def _finished(self, result, error):
        self.busy = False
        if self.operation == "recover" and result is not None:
            self.result = result
            self.reveal_button.show()
            self.resume_button.setVisible(bool(result.info.drafts))
            suffix = ""
            try:
                self.lease.validate()
            except ValueError:
                suffix = "\n生成结果后原窗口发生变化；此结果不代表较新的草稿，请另行保留新输入。"
            self.status.setText(f"已验证并恢复：{result.directory}\n"
                "project/ 为所选结果；recovery-evidence/ 保留全部日志版本与决定，drafts/ 保留独立草稿。"
                "原项目仍保持保护状态；请明确打开副本后再决定编译。" + suffix)
            if self.closing:
                self.close_button.setText("关闭（恢复结果已生成）")
        elif self.closing or self.cancel.is_set():
            self._close()
            return
        elif error:
            self.status.setText(error + "\n原窗口与日志保留。重新选择项目或关闭后重试。")
        else:
            self.review = result
            entries = {entry.path: entry for entry in result.entries}
            for path, payload in result.files:
                entry = entries.get(path)
                state = {"before": "写入前", "after": "计划写入后", "external": "外部版本 / 冲突"}.get(
                    entry.state if entry else "", "未记录于日志 · 当前磁盘")
                item = QTreeWidgetItem([path, state, ""])
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                item.setCheckState(0, Qt.CheckState.Checked)
                if entry:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                self.tree.addTopLevelItem(item)
                if entry:
                    choice = QComboBox()
                    choice.addItem("请选择版本…", None)
                    for label, side in (("写入前", "before"), ("计划写入后", "after"), ("当前磁盘", "current")):
                        choice.addItem(label + ("（文件不存在）" if getattr(entry, side) is None else ""), side)
                    self.choices[path] = choice
                    self.tree.setItemWidget(item, 2, choice)
            count = sum(entry.state == "external" for entry in result.entries)
            self.status.setText(f"已核验 {len(result.files)} 个选定文件，{len(result.entries)} 个写入目标，"
                f"{count} 个外部版本。请比较并选择每个写入目标的版本。\n"
                f"另行保留 {len(self.lease.drafts)} 份窗口草稿，不自动应用。" +
                ("\n" + "\n".join(result.warnings) if result.warnings else ""))
        enabled = not self.closing and not self.cancel.is_set()
        for widget in (self.choose_button, self.tree, self.target, self.target_button):
            widget.setEnabled(enabled)
        self.action_button.setEnabled(enabled and self.review is not None and self.result is None)

    def show_preview(self, item, _old=None):
        self.preview.clear()
        if self.review is None or item is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        entry = next((entry for entry in self.review.entries if entry.path == path), None)
        versions = [("写入前", entry.before), ("计划写入后", entry.after), ("当前磁盘", entry.current)] if entry else [
            ("当前磁盘（不在日志中）", dict(self.review.files)[path])]
        text = [path]
        for title, payload in versions:
            if payload is None:
                text.append(f"\n[{title}] 文件不存在")
                continue
            try:
                preview = payload.decode("utf-8")
            except UnicodeError:
                preview = "非 UTF-8 字节；仅显示开头的十六进制，不转换原件：\n" + payload[:128].hex(" ")
            text.append(f"\n[{title}] {len(payload)} bytes / SHA-256 {_sha(payload)}\n" + preview[:20000]
                        + ("\n[显示截断；完整字节会保留。]" if len(preview) > 20000 else ""))
        self.preview.setPlainText("\n".join(text))

    def choose_target(self):
        path, _ = QFileDialog.getSaveFileName(self, "选择尚不存在的恢复目录名称", self.target.text())
        if path:
            self.target.setText(path)

    def perform(self):
        if self.busy or self.review is None or self.result is not None:
            return
        review = self.review
        choices = {path: combo.currentData() for path, combo in self.choices.items()}
        if not all(choices.values()) or not self.target.text().strip():
            self.status.setText("请为全部日志目标明确选择版本，并指定原项目之外的新目录。")
            return
        selected = tuple(self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
                         for i in range(self.tree.topLevelItemCount())
                         if self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked)
        target = Path(self.target.text().strip())
        answer = QMessageBox.question(self, "确认独立写入恢复", f"恢复 {len(selected)} 个选定目标到：\n{target}\n"
            "未变更文件使用已审阅的当前磁盘字节；各日志目标使用所选版本。\n"
            "全部冲突版本另行保留，不清理原日志，不自动打开或编译。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.lease.validate()
            if self.review is not review:
                raise ValueError("审阅项目已切换；未恢复。")
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        drafts = tuple(self.lease.drafts)
        self._launch("recover", lambda stop: recover_write_journal(review, choices, target,
            selected=selected, drafts=drafts, cancelled=stop))

    def reveal(self):
        if self.result is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result.directory)))

    def resume_drafts(self):
        if self.result is not None and not self.busy:
            from app.gui.project_recovery_dialog import show_recovery_drafts
            show_recovery_drafts(self.window, self.result.directory)

    def _close(self):
        if self.lease is not None:
            self.lease.release()
        super().reject()

    def reject(self):
        self.cancel.set()
        if self.busy:
            self.closing = True
            self.status.setText("正在取消，等待活动读取/发布返回；原项目不变。")
        else:
            self._close()


def show_block_write_recovery(window):
    app = QApplication.instance()
    previous = getattr(app, "_icstex_write_recovery_dialog", None)
    if previous is not None and isValid(previous):
        previous.raise_()
        return
    dialog = BlockWriteRecoveryDialog(window)
    app._icstex_write_recovery_dialog = dialog
    try:
        dialog.exec()
    finally:
        dialog.cancel.set()
        if dialog.lease is not None:
            dialog.lease.release()
        dialog.deleteLater()
        app._icstex_write_recovery_dialog = None
