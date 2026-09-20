"""Explicit selected-file migration review and separately confirmed new window."""
from pathlib import Path
import threading

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QScrollArea, QWidget)
from shiboken6 import isValid

from app.core.project_checkpoint import checkpoint_candidates
from app.core.project_migration import inspect_project_migration, migrate_project_copy, read_migration_copy, _sha
from app.core.project_recovery import check_recovery_identity, saved_block_model
from app.gui.project_checkpoint_dialog import CaptureLease, _Signals, _run, _windows, _belongs
from app.gui.dialog_combo_box import DialogComboBox
from app.gui.responsive.helpers import ButtonFlowLayout
from app.gui.theme import PRIMARY_BUTTON_STATE_STYLE


def open_migration_project(owner, reviewed, source=None):
    """Use verified saved bytes in a new window; no draft application or build."""
    copy = reviewed.copy
    for window in _windows(owner):
        session = getattr(window, "block_session", None)
        if (any(_belongs(tab.path, copy.project) for tab in window.tabs.values())
                or session is not None and session.project_dir == copy.project):
            raise ValueError("副本已在窗口中打开；请先处理该窗口，避免并行覆盖。")
    check_recovery_identity(copy)
    session = new = None
    try:
        if reviewed.kind != "source-copy":
            from app.gui.blocks.project_session import ProjectSession
            session = ProjectSession(project_dir=copy.project, **saved_block_model(copy))
            if session.save_error:
                raise ValueError(session.save_error)
        elif source not in dict(copy.files) or Path(source).suffix.lower() not in {".tex", ".ltx"}:
            raise ValueError("请选择已核验清单中的 LaTeX 入口。")
        check_recovery_identity(copy)
        new = owner.spawn_window()
        new.project_files.set_project_root(copy.project)
        if session is not None:
            from app.gui.block_mode import _install_session, _set_block_mode
            if not _install_session(new, session):
                raise ValueError("新窗口未接受副本会话。")
            _set_block_mode(new, True)
        else:
            target = copy.project / source
            new.open_file(target)
            if not any(tab.path == target for tab in new.tabs.values()):
                raise ValueError("入口未打开（可能取消了编码选择）；副本仍保留。")
        check_recovery_identity(copy)
        new.workspace.refresh()
        new.statusBar().showMessage("已打开独立迁移副本；未应用草稿，尚未授权编译。", 15000)
        return new
    except BaseException:
        if session is not None:
            session.shutdown()
        if new is not None:
            for tab in new.tabs.values():
                tab.modified = tab.dirty = False
            new.close()
            new.deleteLater()
        elif session is not None:
            session.deleteLater()
        raise


class ProjectMigrationDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.project = self.review = self.result = self.lease = self.opened = None
        self.busy = self.closing = False
        self.cancel = threading.Event()
        self.selection = ()
        self.inventory_warnings = ()
        self.setWindowTitle("迁移到新副本 · 选文件、比较、再决定是否打开")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(960, 780)
        outer = QVBoxLayout(self)
        self.scroller = QScrollArea()
        self.scroller.setWidgetResizable(True)
        body = QWidget()
        self.scroller.setWidget(body)
        outer.addWidget(self.scroller)
        layout = QVBoxLayout(body)
        self.status = QLabel("选择原项目。只处理明确选择的本地文件；原目录不会移动或覆盖。")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.project_label = QLabel("")
        self.project_label.setTextFormat(Qt.TextFormat.PlainText)
        self.project_label.setWordWrap(True)
        layout.addWidget(self.project_label)
        self.choose_button = QPushButton("选择原项目目录…")
        layout.addWidget(self.choose_button)
        self.tabs = QTabWidget()
        self.tabs.tabBar().setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.files = QTreeWidget()
        self.files.setHeaderLabels(["选择纳入的原文件"])
        self.files.setRootIsDecorated(False)
        self.files.setMinimumHeight(160)
        self.output = QTreeWidget()
        self.output.setHeaderLabels(["副本路径", "处理方式", "SHA-256"])
        self.output.setColumnWidth(0, 380)
        self.output.setRootIsDecorated(False)
        self.output.setMinimumHeight(160)
        self.tabs.addTab(self.files, "1 · 选择文件")
        self.tabs.addTab(self.output, "2 · 审阅副本")
        layout.addWidget(self.tabs, 2)
        self.review_button = QPushButton("审阅所选文件")
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(160)
        self.preview.setTabChangesFocus(True)
        layout.addWidget(self.preview, 2)
        policy = QLabel("仅复制选定且实际可读的本地文件，不证明依赖或云端下载完整。旧 LaTeX 片段保留原文，"
                        "默认禁止执行；未映射字段和被重新生成的原文件另行保留。草稿独立存放，不自动套用。")
        policy.setWordWrap(True)
        layout.addWidget(policy)
        row = QHBoxLayout()
        self.target = QLineEdit()
        self.target.setPlaceholderText("原项目之外、尚不存在的新目录")
        self.target_button = QPushButton("选择位置…")
        row.addWidget(self.target, 1)
        row.addWidget(self.target_button)
        layout.addLayout(row)
        self.action_button = QPushButton("确认生成新副本…")
        self.action_button.setObjectName("primaryButton")
        self.action_button.setStyleSheet(PRIMARY_BUTTON_STATE_STYLE)
        row = QHBoxLayout()
        self.source = DialogComboBox()
        self.source.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.source.setMinimumContentsLength(20)
        self.open_button = QPushButton("核验并打开副本…")
        self.open_button.setToolTip("打开前会再次核验，并单独询问是否在新窗口打开。")
        self.open_button.setObjectName("primaryButton")
        self.open_button.setStyleSheet(PRIMARY_BUTTON_STATE_STYLE)
        row.addWidget(self.source, 1)
        layout.addLayout(row)
        self.close_button = QPushButton("取消 / 关闭")
        footer = ButtonFlowLayout()
        for button in (self.close_button, self.review_button, self.action_button, self.open_button):
            footer.addWidget(button)
        outer.addLayout(footer)
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
        self.setTabOrder(self.source, self.open_button)
        self.setTabOrder(self.open_button, self.close_button)
        self.signals = _Signals(self)
        self.signals.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self.destroyed.connect(self.cancel.set)
        self.choose_button.clicked.connect(self.choose_project)
        self.review_button.clicked.connect(self.inspect_selection)
        self.action_button.clicked.connect(self.perform)
        self.open_button.clicked.connect(self.prepare_open)
        self.target_button.clicked.connect(self.choose_target)
        self.close_button.clicked.connect(self.reject)
        self.files.itemChanged.connect(self.selection_changed)
        self.output.currentItemChanged.connect(self.show_preview)
        self._controls()

    def _controls(self):
        editable = not self.busy and not self.closing and self.result is None
        for widget in (self.choose_button, self.files, self.target, self.target_button):
            widget.setEnabled(editable)
        self.review_button.setEnabled(editable and self.project is not None)
        self.action_button.setEnabled(editable and self.review is not None)
        self.source.setEnabled(not self.busy and self.result is not None and not self.closing)
        self.open_button.setEnabled(not self.busy and not self.closing
                                    and self.result is not None and self.opened is None)
        self.review_button.setVisible(self.result is None)
        self.action_button.setVisible(self.result is None)
        self.source.setVisible(self.result is not None)
        self.open_button.setVisible(self.result is not None)

    def choose_project(self):
        project = QFileDialog.getExistingDirectory(self, "选择原项目（不会移动或改写）")
        if project:
            self.load_project(project)

    def load_project(self, project):
        if self.busy:
            return
        if self.lease is not None:
            self.lease.release()
        self.project = self.review = self.result = self.lease = self.opened = None
        self.project_label.clear()
        self.files.clear()
        self.output.clear()
        self.source.clear()
        self.preview.clear()
        try:
            raw = Path(project).expanduser().absolute()
            if raw.is_symlink():
                raise ValueError("请选择实际目录，不使用目录链接。")
            self.project = raw.resolve(strict=True)
            self.project_label.setText("原项目：" + str(self.project))
            self.lease = CaptureLease(self.window, self.project)
            self.cancel = self.lease.cancelled
            self.destroyed.connect(self.cancel.set)
            self._launch("inventory", lambda stop: checkpoint_candidates(self.project, cancelled=stop))
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))
            self.project = None
            self._controls()

    def selected(self):
        return tuple(self.files.topLevelItem(i).text(0) for i in range(self.files.topLevelItemCount())
                     if self.files.topLevelItem(i).checkState(0) == Qt.CheckState.Checked)

    def selection_changed(self, *_):
        self.review = None
        self.output.clear()
        self.preview.clear()
        self._controls()

    def inspect_selection(self):
        if self.busy or self.project is None or self.result is not None:
            return
        try:
            self.lease.validate()
            self.selection = self.selected()
            if not self.selection:
                raise ValueError("请先勾选要复制的文件。")
            project, paths = self.project, self.selection
            self.review = None
            self.output.clear()
            self._launch("inspect", lambda stop: inspect_project_migration(project, paths=paths, cancelled=stop))
        except ValueError as exc:
            self.status.setText(str(exc))

    def _launch(self, operation, work):
        if self.busy:
            return
        self.busy, self.operation = True, operation
        self._controls()
        self.status.setText("正在后台核验，可取消；不会写入原项目。")
        self.thread = threading.Thread(target=_run, args=(work, self.cancel, self.signals),
                                       name="icstex-project-migration", daemon=True)
        self.thread.start()

    @Slot(object, str)
    def _finished(self, result, error):
        self.busy = False
        if self.operation == "publish" and result is not None:
            self.result = result
            suffix = ""
            try:
                self.lease.validate()
            except ValueError:
                suffix = "\n发布后原窗口已变化；此副本不包含较新的草稿，请另行保留新输入。"
            self.status.setText(f"副本已验证并生成：{result.directory}\n"
                "原件未移动；project/ 是副本，drafts/ 是独立草稿。可关闭此窗口，或单独确认打开副本。" + suffix)
            if self.review.kind != "source-copy":
                self.source.addItem("以 Block 模式打开（不应用草稿）", None)
            else:
                for path in sorted((e.path for e in result.info.files if Path(e.path).suffix.lower() in {".tex", ".ltx"}),
                                   key=lambda p: (p != "main.tex", p)):
                    self.source.addItem(path, path)
            if self.closing:
                self.close_button.setText("关闭（副本已生成）")
        elif self.closing or self.cancel.is_set():
            self._close()
            return
        elif error:
            self.status.setText(error + "\n没有覆盖原件；可重新审阅或关闭后重试。")
        elif self.operation == "inventory":
            paths, self.inventory_warnings = result
            self.files.blockSignals(True)
            for path in paths:
                item = QTreeWidgetItem([path])
                item.setCheckState(0, Qt.CheckState.Checked)
                self.files.addTopLevelItem(item)
            self.files.blockSignals(False)
            self.status.setText(f"已列出 {len(paths)} 个候选文件；目录可列出不代表字节可读。"
                                "请勾选后生成预览。\n" + "\n".join(self.inventory_warnings))
        elif self.operation == "inspect":
            from dataclasses import replace
            self.review = replace(result, warnings=tuple(dict.fromkeys((*self.inventory_warnings, *result.warnings))))
            original = dict(result.original)
            for path, payload in result.candidate:
                state = "原字节复制" if original.get(path) == payload else ("副本中重新生成" if path in original else "副本中新增")
                item = QTreeWidgetItem([path, state, _sha(payload)])
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                self.output.addTopLevelItem(item)
            self.tabs.setCurrentWidget(self.output)
            unmapped = "、".join(result.unmapped_keys[:100])
            if len(result.unmapped_keys) > 100:
                unmapped += "（列表显示截断，完整字段留在原 JSON 与决定报告中）"
            self.preview.setPlainText("\n".join(self.review.warnings) +
                f"\n未映射字段（{len(result.unmapped_keys)}）：{unmapped or '无'}\n"
                "选择副本文件以比较原件与候选字节。")
            self.status.setText(f"已核验 {len(result.original)} 个原文件 → {len(result.candidate)} 个副本文件；"
                                f"另留 {len(self.lease.drafts)} 份窗口草稿。请审阅清单和差异，再指定新目录。")
        elif self.operation == "open-review":
            source = self.source.currentData()
            answer = QMessageBox.question(self, "单独确认打开迁移副本",
                f"已核验项目、迁移决定及所列原件证据。\n在独立窗口打开：\n{result.copy.project}\n"
                "当前项目不关闭、不替换；草稿不自动套用，打开不授权编译。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer == QMessageBox.StandardButton.Yes:
                self.open_source = source
                self._launch("open-check", lambda stop: read_migration_copy(result.copy.directory,
                                                                          cancelled=stop, expected=result))
                return
            self.status.setText("已取消打开；生成的副本和原件仍保留。")
        elif self.operation == "open-check":
            try:
                self.opened = open_migration_project(self.window, result, self.open_source)
                self.status.setText("已在独立窗口打开副本；原窗口与草稿保留，未授权编译。")
                self._close()
                return
            except (OSError, ValueError, TypeError) as exc:
                self.status.setText("副本未打开，文件保留：" + str(exc))
        self._controls()

    def show_preview(self, item, _old=None):
        if self.review is None or item is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        parts = [path]
        for title, files in (("原件", self.review.original), ("副本", self.review.candidate)):
            payload = dict(files).get(path)
            if payload is None:
                parts.append(f"\n[{title}] 不存在")
                continue
            try:
                text = payload.decode("utf-8")
            except UnicodeError:
                text = "非 UTF-8 字节；原样保留，以下仅显示十六进制开头：\n" + payload[:128].hex(" ")
            parts.append(f"\n[{title}] {len(payload)} bytes / SHA-256 {_sha(payload)}\n" + text[:20000] +
                         ("\n[预览截断；完整字节保留。]" if len(text) > 20000 else ""))
        self.preview.setPlainText("\n".join(parts))

    def choose_target(self):
        path, _ = QFileDialog.getSaveFileName(self, "新副本目录名称（必须尚不存在）", self.target.text())
        if path:
            self.target.setText(path)

    def perform(self):
        if self.busy or self.review is None or self.result is not None:
            return
        review, target = self.review, self.target.text().strip()
        if not target:
            self.status.setText("请指定原项目之外、尚不存在的新目录。")
            return
        answer = QMessageBox.question(self, "确认生成独立迁移副本",
            f"按已审阅清单生成 {len(review.candidate)} 个副本文件到：\n{target}\n"
            f"副本中重新生成 {len(review.replaced)} 个原有路径，未映射字段 {len(review.unmapped_keys)} 项。\n"
            "旧格式的全部选定原件另行保留。草稿独立保存；不自动打开或编译。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.lease.validate()
            if self.review is not review or self.selected() != self.selection:
                raise ValueError("确认期间清单已变化；请重新审阅。")
            drafts = tuple(self.lease.drafts)
            self._launch("publish", lambda stop: migrate_project_copy(review, target, drafts=drafts, cancelled=stop))
        except ValueError as exc:
            self.status.setText(str(exc))

    def prepare_open(self):
        if self.busy or self.result is None or self.opened is not None:
            return
        # Publication has its own stable result; later original edits do not
        # change those saved bytes. Keep its separate opening check cancellable.
        self.cancel = threading.Event()
        self.destroyed.connect(self.cancel.set)
        result = self.result
        self._launch("open-review", lambda stop: read_migration_copy(result.directory, cancelled=stop))

    def _close(self):
        if self.lease is not None:
            self.lease.release()
        super().reject()

    def reject(self):
        self.cancel.set()
        if self.busy:
            self.closing = True
            self.status.setText("正在取消，等待活动读取/发布返回；原件保留。")
        else:
            self._close()


def show_project_migration(window):
    app = QApplication.instance()
    previous = getattr(app, "_icstex_migration_dialog", None)
    if previous is not None and isValid(previous):
        previous.raise_()
        return
    dialog = ProjectMigrationDialog(window)
    app._icstex_migration_dialog = dialog
    try:
        dialog.exec()
    finally:
        dialog.cancel.set()
        if dialog.lease is not None:
            dialog.lease.release()
        dialog.deleteLater()
        app._icstex_migration_dialog = None
    # Closing the application-modal dialog can reactivate its original owner.
    # Present the explicitly opened copy only after that modal scope has ended.
    if dialog.opened is not None and isValid(dialog.opened):
        dialog.opened.raise_()
        dialog.opened.activateWindow()
