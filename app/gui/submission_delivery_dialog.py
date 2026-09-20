"""Explicit saved/FINAL review and exact-byte delivery; no implicit compilation."""
from dataclasses import replace
import hashlib
from pathlib import Path
import threading

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QStackedWidget, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
from shiboken6 import isValid

from app.core.latex_tools import LaTeXEngine, LaTeXToolchain
from app.core.submission_check import BufferInput, CheckRequest, STATUS_LABELS, check_submission
from app.core.submission_delivery import (DeliveryOptions, delivery_payloads, prepare_submission,
    publish_submission, submission_source_candidates)
from app.gui.blocks.close_guard import compile_block_session, save_block_session
from app.gui.blocks.project_session import ProjectSession
from app.gui.project_checkpoint_dialog import CaptureLease, _Signals, _run
from app.gui.submission_check_controller import SubmissionCheckController
from app.gui.responsive.helpers import ButtonFlowLayout
from app.gui.theme import PRIMARY_BUTTON_STATE_STYLE


def _block_key(session):
    manager = session.compile_manager
    return (id(session), session.project_dir, session._revision, session.editor_draft_revision,
            session.compile_generation, session._closed,
            manager.engine if manager else LaTeXEngine.XELATEX,
            manager.toolchain if manager else LaTeXToolchain(None, None))


def _prepare(request, options, cancel):
    try:
        prepared = prepare_submission(request, options, cancelled=cancel)
        payloads = delivery_payloads(prepared)
        details = []
        for path, raw in payloads:
            if cancel.is_set():
                raise ValueError("已取消固定内容核验。")
            details.append(f"{path}\n{len(raw)} bytes / SHA-256 {hashlib.sha256(raw).hexdigest()}")
        return prepared.report, prepared, payloads, "", "\n\n".join(details)
    except (OSError, ValueError) as exc:
        if cancel.is_set():
            raise
        # A failed prerequisite still needs actionable, non-fabricated M1 rows.
        return check_submission(request, cancel), None, (), str(exc), ""


class SubmissionDeliveryDialog(QDialog):
    def __init__(self, window, *, session=None):
        super().__init__(window)
        self.window = window
        self.main_window = window if hasattr(window, "readiness") else None
        if self.main_window is not None:
            _, project, root, _, _, active = window.readiness._context()
            if session is not None and session is not active:
                raise ValueError("导出目标不是当前可见 Block 项目；请从对应窗口重新打开。")
            self.session = active
        else:
            if session is None or getattr(window, "session", None) is not session:
                raise ValueError("独立 Block 导出必须绑定其实际会话窗口。")
            self.session = session
            project = session.project_dir
            root = project / "main.tex" if project else None
        if project is None or root is None:
            raise ValueError("请先保存并打开本地项目及 LaTeX 入口，再准备提交。")
        self.project, self.root = project.resolve(strict=True), root
        self.prepared = self.report = self.result = self.lease = None
        self.payloads = ()
        self._payload_details = ""
        self.busy = self.closing = self.inventory_loaded = False
        self.cancel = threading.Event()
        self.key = None
        self.setObjectName("submissionDeliveryDialog")
        self.setWindowTitle("准备提交 · 核对当前 FINAL 与交付内容")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(960, 780)
        outer = QVBoxLayout(self)
        self.stage_heading = QLabel()
        outer.addWidget(self.stage_heading)
        self.status = QLabel("先保存、正式编译，再主动检查并固定版本。打开此窗口不会保存、编译或联网。")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        self.scroller = QScrollArea()
        self.scroller.setWidgetResizable(True)
        self.content = QStackedWidget()
        self.pages = QStackedWidget()
        self.content.addWidget(self.pages)
        self.technical = QPlainTextEdit()
        self.technical.setReadOnly(True)
        self.technical.setTabChangesFocus(True)
        self.technical.setAccessibleName("完整项目路径、固定输入与交付文件摘要，可选择复制")
        self.content.addWidget(self.technical)
        self.scroller.setWidget(self.content)
        outer.addWidget(self.scroller, 1)
        self.prepare_page, self.review_page, self.target_page, self.success_page = (QWidget() for _ in range(4))
        for page in (self.prepare_page, self.review_page, self.target_page, self.success_page):
            self.pages.addWidget(page)
        prepare = QVBoxLayout(self.prepare_page)
        prepare.addWidget(QLabel("保存与正式编译"))
        self.save_button = QPushButton("保存当前项目输入…")
        self.compile_button = QPushButton("正式编译（FINAL）…")
        actions = ButtonFlowLayout()
        for button in (self.save_button, self.compile_button):
            actions.addWidget(button)
        prepare.addLayout(actions)
        self.review_button = QPushButton("检查并固定内容")
        prepare.addWidget(QLabel("默认只交付正式 PDF；以下内容分别选择。"))
        self.pdf_name = QLineEdit(self.root.stem + ".pdf")
        self.pdf_name.setAccessibleName("交付 PDF 文件名")
        prepare.addWidget(QLabel("交付 PDF 文件名"))
        prepare.addWidget(self.pdf_name)
        self.include_source = QCheckBox("另附选定源码（先勾选并审阅清单）")
        self.include_report = QCheckBox("另附检查报告（相对路径、摘要和未确认项）")
        prepare.addWidget(self.include_source)
        prepare.addWidget(self.include_report)
        self.source_selection = QWidget()
        source_layout = QVBoxLayout(self.source_selection)
        source_layout.setContentsMargins(0, 0, 0, 0)
        prepare.addWidget(self.source_selection)
        self.tabs = QTabWidget()
        self.tabs.tabBar().setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.files = QTreeWidget()
        self.files.setHeaderLabels(["源码纳入清单（默认不勾选）"])
        source_layout.addWidget(self.files)
        self.checks = QTreeWidget()
        self.checks.setHeaderLabels(["检查项", "状态", "原因"])
        self.outputs = QTreeWidget()
        self.outputs.setHeaderLabels(["实际交付路径", "字节"])
        for tree in (self.files, self.checks, self.outputs):
            tree.setRootIsDecorated(False)
            tree.setMinimumHeight(150)
            tree.setColumnWidth(0, 280)
        self.tabs.addTab(self.checks, "检查与未确认项")
        self.tabs.addTab(self.outputs, "审阅交付字节")
        self.select_button = QPushButton("全选源码")
        self.clear_button = QPushButton("清空选择")
        self.inventory_button = QPushButton("重新读取清单")
        selection_actions = ButtonFlowLayout()
        for button in (self.select_button, self.clear_button, self.inventory_button):
            selection_actions.addWidget(button)
        source_layout.addLayout(selection_actions)
        policy = QLabel("不含个人历史或独立草稿。静态依赖可能不完整，字体和 TeX 环境需另行准备。"
                        "名称过滤不是隐私认证，选定元数据可能保留本地引用。")
        policy.setWordWrap(True)
        prepare.addWidget(policy)
        prepare.addStretch()
        review = QVBoxLayout(self.review_page)
        review.addWidget(self.tabs, 1)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setTabChangesFocus(True)
        self.preview.setAccessibleName("已固定文件内容或检查原因")
        self.preview.setMinimumHeight(160)
        self.preview.setPlaceholderText("选中检查项查看原因，或选中已固定的交付文件查看原始字节。")
        review.addWidget(self.preview, 1)
        self.acknowledge = QCheckBox("已审阅全部未确认项；不代表通过或满足学校要求")
        outer.addWidget(self.acknowledge)
        target_layout = QVBoxLayout(self.target_page)
        self.target_summary = QPlainTextEdit()
        self.target_summary.setReadOnly(True)
        self.target_summary.setTabChangesFocus(True)
        self.target_summary.setAccessibleName("待交付的固定文件清单")
        target_layout.addWidget(self.target_summary)
        target_layout.addWidget(QLabel("选择原项目之外、尚不存在的新目录"))
        row = QHBoxLayout()
        self.target = QLineEdit()
        self.target.setPlaceholderText("原项目之外、尚不存在的新交付目录")
        self.target.setAccessibleName("新交付目录")
        self.target_button = QPushButton("选择位置…")
        row.addWidget(self.target, 1)
        row.addWidget(self.target_button)
        target_layout.addLayout(row)
        target_policy = QLabel("只生成已审阅的固定文件，不覆盖已有目录、不上传内容。输入变化后须重新检查。")
        target_policy.setWordWrap(True)
        target_layout.addWidget(target_policy)
        success = QVBoxLayout(self.success_page)
        self.success_details = QPlainTextEdit()
        self.success_details.setReadOnly(True)
        self.success_details.setTabChangesFocus(True)
        self.success_details.setAccessibleName("已生成的新目录与实际交付文件")
        success.addWidget(self.success_details)
        self.action_button = QPushButton("生成新交付目录…")
        self.continue_button = QPushButton("选择目标并确认")
        self.open_button = QPushButton("打开交付目录")
        self.back_button = QPushButton("上一步")
        self.technical_button = QPushButton("技术详情")
        self.technical_button.setCheckable(True)
        self.close_button = QPushButton("取消")
        for button in (self.review_button, self.continue_button, self.action_button, self.open_button):
            button.setObjectName("primaryButton")
            button.setStyleSheet(PRIMARY_BUTTON_STATE_STYLE)
        footer = ButtonFlowLayout()
        for button in (self.close_button, self.back_button, self.technical_button, self.review_button,
                       self.continue_button, self.action_button, self.open_button):
            footer.addWidget(button)
        outer.addLayout(footer)
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
        self.signals = _Signals(self)
        self.signals.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self.destroyed.connect(self._destroyed)
        self.save_button.clicked.connect(self.save_inputs)
        self.compile_button.clicked.connect(self.compile_final)
        self.review_button.clicked.connect(self.inspect)
        self.include_source.toggled.connect(self.source_toggled)
        self.include_report.toggled.connect(self.invalidate)
        self.pdf_name.textChanged.connect(self.invalidate)
        self.files.itemChanged.connect(self.invalidate)
        self.acknowledge.toggled.connect(self._controls)
        self.outputs.currentItemChanged.connect(self.preview_output)
        self.checks.currentItemChanged.connect(self.preview_check)
        self.select_button.clicked.connect(self.select_all)
        self.clear_button.clicked.connect(self.clear_selection)
        self.inventory_button.clicked.connect(self.inventory)
        self.target_button.clicked.connect(self.choose_target)
        self.action_button.clicked.connect(self.perform)
        self.continue_button.clicked.connect(self.continue_to_target)
        self.back_button.clicked.connect(self.previous_stage)
        self.technical_button.toggled.connect(self.show_technical)
        self.open_button.clicked.connect(self.open_result)
        self.target.textChanged.connect(self._controls)
        self.close_button.clicked.connect(self.reject)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.poll)
        self.timer.start()
        self._show_stage(self.prepare_page)

    def _show_stage(self, page):
        # Presentation only. PreparedSubmission, CaptureLease and result remain
        # the sole authorities for review, cancellation and publication.
        self.pages.setCurrentWidget(page)
        self.technical_button.setChecked(False)
        self.content.setCurrentWidget(self.pages)
        self.scroller.verticalScrollBar().setValue(0)
        self.stage_heading.setText({self.prepare_page: "第 1 步 / 共 3 步 · 准备",
            self.review_page: "第 2 步 / 共 3 步 · 审阅固定内容",
            self.target_page: "第 3 步 / 共 3 步 · 选择目标并确认",
            self.success_page: "交付已生成"}[page])
        self._controls()
        self._technical_details()

    def show_technical(self, checked):
        self._technical_details()
        self.content.setCurrentWidget(self.technical if checked else self.pages)
        self.technical_button.setText("返回内容" if checked else "技术详情")

    def _technical_details(self):
        lines = [f"项目：{self.project}", f"入口：{self.root}"]
        if self.report is not None:
            lines.append(f"输入身份：{self.report.input_id}")
        item = self.checks.currentItem()
        if item is not None and (check := item.data(0, Qt.ItemDataRole.UserRole)) is not None:
            lines.append(f"选中检查：{check.title}\n位置：{check.file or ''}:{check.line or ''}\n{check.input_id}")
        lines.append("内容已固定" if self.prepared is not None else "内容尚未固定，不能交付")
        if self._payload_details:
            lines.append(self._payload_details)
        if self.result is not None:
            lines.append(f"实际交付目录：{self.result}")
        self.technical.setPlainText("\n\n".join(lines))

    def previous_stage(self):
        if self.busy or self.closing or self.result is not None:
            return
        self._show_stage(self.review_page if self.pages.currentWidget() is self.target_page else self.prepare_page)

    def continue_to_target(self):
        if (self.busy or self.closing or self.prepared is None or self.result is not None
                or (self.prepared.unconfirmed and not self.acknowledge.isChecked())):
            return
        try:
            self._validate()
        except (ValueError, RuntimeError) as exc:
            self.invalidate()
            self.status.setText(str(exc))
            return
        self.target_summary.setPlainText(f"将生成 {len(self.payloads)} 个固定文件；"
            f"{len(self.prepared.unconfirmed)} 项未确认。\n\n" + "\n".join(path for path, _ in self.payloads))
        self._show_stage(self.target_page)
        self.target.setFocus()

    def open_result(self):
        if self.result is not None and not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result))):
            self.status.setText("目录已生成，但未能打开；可从结果中复制完整路径。")

    def _context(self):
        if not isValid(self.window):
            raise ValueError("原窗口已关闭；请重新打开准备提交。")
        if self.main_window is not None:
            key, scope, root, _, _, session = self.window.readiness._context()
            if scope != self.project or root != self.root or session is not self.session:
                raise ValueError("活动项目、入口或模式已切换；请从对应窗口重新准备。")
            return key
        if (getattr(self.window, "session", None) is not self.session or not isValid(self.session)
                or self.session._closed or self.session.project_dir != self.project):
            raise ValueError("Block 会话或目录已变化；请重新准备。")
        return _block_key(self.session)

    def _snapshot(self):
        key = self._context()
        if self.main_window is not None:
            return self.window.readiness.capture_request()
        session = self.session
        manager = session.compile_manager
        proof = session.final_evidence
        return CheckRequest(key, self.project, self.root, (),
            manager.toolchain if manager else LaTeXToolchain(None, None),
            manager.engine if manager else LaTeXEngine.XELATEX,
            block=SubmissionCheckController._block_input(session), build_evidence=proof,
            source_revision=session._revision, building=session.final_is_running)

    def _controls(self, *_):
        editable = not self.busy and not self.closing and self.result is None
        for widget in (self.save_button, self.compile_button, self.review_button, self.include_source,
                       self.include_report, self.pdf_name, self.target, self.target_button):
            widget.setEnabled(editable)
        for widget in (self.files, self.select_button, self.clear_button, self.inventory_button):
            widget.setEnabled(editable and self.include_source.isChecked())
        self.source_selection.setVisible(self.include_source.isChecked())
        self.acknowledge.setEnabled(editable and self.prepared is not None and bool(self.prepared.unconfirmed))
        self.acknowledge.setVisible(self.pages.currentWidget() is self.review_page and self.prepared is not None
                                    and bool(self.prepared.unconfirmed))
        ready = editable and self.prepared is not None and (not self.prepared.unconfirmed or self.acknowledge.isChecked())
        self.continue_button.setEnabled(ready)
        self.action_button.setEnabled(ready and bool(self.target.text()))
        page = self.pages.currentWidget()
        for button, shown in ((self.review_button, page is self.prepare_page),
                (self.continue_button, page is self.review_page), (self.action_button, page is self.target_page),
                (self.open_button, self.result is not None),
                (self.back_button, page in (self.review_page, self.target_page))):
            button.setVisible(shown)
        self.back_button.setEnabled(editable)
        self.open_button.setEnabled(self.result is not None)

    def _release(self):
        if self.lease is not None:
            self.lease.release()
            self.lease = None
        self.key = None

    def _destroyed(self, *_):
        self.cancel.set()
        self._release()

    def invalidate(self, *_):
        self.cancel.set()
        self.prepared = self.report = None
        self.payloads = ()
        self._payload_details = ""
        self.outputs.clear()
        self.checks.clear()
        self.preview.clear()
        self.target_summary.clear()
        self.acknowledge.setChecked(False)
        if not self.busy:
            self._release()
        self.status.setText("内容尚未固定，请在准备后重新检查；原项目和已有交付保持不变。")
        self._show_stage(self.prepare_page)

    def source_toggled(self, checked):
        self.invalidate()
        if checked and not self.inventory_loaded:
            self.inventory()

    def options(self):
        paths = tuple(self.files.topLevelItem(i).text(0) for i in range(self.files.topLevelItemCount())
            if self.files.topLevelItem(i).checkState(0) == Qt.CheckState.Checked) if self.include_source.isChecked() else ()
        return DeliveryOptions(self.include_source.isChecked(), self.include_report.isChecked(),
                               paths, self.pdf_name.text())

    def select_all(self):
        self._select_sources(Qt.CheckState.Checked)

    def clear_selection(self):
        self._select_sources(Qt.CheckState.Unchecked)

    def _select_sources(self, state):
        self.files.blockSignals(True)
        for i in range(self.files.topLevelItemCount()):
            self.files.topLevelItem(i).setCheckState(0, state)
        self.files.blockSignals(False)
        self.invalidate()

    def _launch(self, operation, work):
        if self.busy:
            return
        self.operation, self.busy = operation, True
        self._controls()
        self.status.setText("正在后台核验，可取消；不会保存、编译或覆盖原项目。")
        self.thread = threading.Thread(target=_run, args=(work, self.cancel, self.signals),
                                       name="icstex-submission-delivery", daemon=True)
        self.thread.start()

    def inventory(self):
        if self.busy or self.result is not None:
            return
        self.invalidate()
        try:
            self._context()
            self.cancel = threading.Event()
            project = self.project
            self._launch("inventory", lambda stop: submission_source_candidates(project, cancelled=stop))
        except ValueError as exc:
            self.status.setText(str(exc))

    def inspect(self):
        if self.busy or self.result is not None:
            return
        self.invalidate()
        try:
            self._context()
            owners = tuple((widget, current) for widget in QApplication.topLevelWidgets()
                if isValid(widget) and isinstance(current := getattr(widget, "session", None), ProjectSession)
                and current.project_dir == self.project and not current._closed)
            if self.session is not None:
                self.session.finish_editor_inputs.emit()
                owners = (*owners, (self.window, self.session))
            for _, session in owners:
                session.finish_editor_inputs.emit()
            self.lease = CaptureLease(self.window, self.project, block_owners=owners)
            self.cancel = self.lease.cancelled
            request = self._snapshot()
            # Do not accept hidden dirty buffers or another Block writer for the
            # same project as saved delivery inputs. Never apply those drafts.
            buffers = {id(tab.editor): BufferInput(tab.path, tab.editor.toPlainText(), revision,
                       tab.modified or tab.dirty) for _, tab, _, revision, _, _ in self.lease.tabs if tab.path}
            if buffers:
                request = replace(request, buffers=tuple(buffers.values()))
            if any(session is not self.session and session.has_unsaved_changes
                   for session, _, _ in self.lease.sessions):
                raise ValueError("同项目另一 Block 窗口有未保存草稿；请先处理，不会自动应用。")
            self.key = request.key
            options, cancel = self.options(), self.cancel
            self._launch("review", lambda stop: _prepare(request, options, cancel))
        except (OSError, ValueError) as exc:
            self._release()
            self.status.setText(str(exc))
            self._controls()

    def _validate(self):
        if self.lease is None or self.key != self._context():
            raise ValueError("窗口输入、配置或构建身份变化；请重新检查。")
        self.lease.validate()

    def poll(self):
        if self.lease is None or self.result is not None:
            return
        try:
            self._validate()
        except (ValueError, RuntimeError) as exc:
            self.invalidate()
            self.status.setText(str(exc))

    def _finished(self, value, error):
        self.busy = False
        if self.operation == "publish" and value is not None:
            # The verified exclusive rename can win a late cancellation. Report
            # that real result instead of pretending nothing was written.
            self.result = value
            self.closing = False
            self.status.setText("已生成交付目录，对应已审阅的固定版本；之后的修改不属于此交付。")
            self.success_details.setPlainText(f"新目录：{value}\n\n实际交付文件：\n" +
                "\n".join(f"{path} · {len(raw)} bytes" for path, raw in self.payloads))
            self.close_button.setText("关闭")
            self._release()
            self._show_stage(self.success_page)
        elif self.cancel.is_set():
            self.invalidate()
            self.status.setText("已取消或输入已变化；未生成交付，请重新检查。")
            if self.closing:
                self._close()
        elif value is None:
            self.invalidate()
            self.status.setText(error or "未完成；原项目和已有交付保留。")
        else:
            try:
                self._context()
                if self.operation == "inventory":
                    paths, warnings = value
                    self.files.blockSignals(True)
                    self.files.clear()
                    for path in paths:
                        item = QTreeWidgetItem([path])
                        item.setCheckState(0, Qt.CheckState.Unchecked)
                        self.files.addTopLevelItem(item)
                    self.files.blockSignals(False)
                    self.inventory_loaded = True
                    self._show_stage(self.prepare_page)
                    self.status.setText("请明确勾选源码文件，再重新检查。候选清单不是完整性或隐私认证。\n" + "\n".join(warnings))
                elif self.operation == "review":
                    self._validate()
                    self.report, self.prepared, self.payloads, failure, self._payload_details = value
                    for check in self.report.items:
                        row = QTreeWidgetItem([check.title, STATUS_LABELS[check.status], check.reason])
                        row.setData(0, Qt.ItemDataRole.UserRole, check)
                        self.checks.addTopLevelItem(row)
                    if self.prepared is None:
                        self._release()
                        self.status.setText("尚不能交付，请处理检查项后重新检查：" + failure)
                        self.tabs.setCurrentWidget(self.checks)
                    else:
                        for path, raw in self.payloads:
                            self.outputs.addTopLevelItem(QTreeWidgetItem([path, str(len(raw))]))
                        self.status.setText(f"已固定内容；{len(self.prepared.unconfirmed)} 项未确认。"
                                            "请审阅交付字节和全部检查，再确认新目录。")
                        self.tabs.setCurrentWidget(self.outputs)
                        self.outputs.setCurrentItem(self.outputs.topLevelItem(0))
                    self._show_stage(self.review_page)
                    if self.prepared is None:
                        self.stage_heading.setText("检查未满足前提 · 内容尚未固定")
            except (OSError, ValueError, RuntimeError) as exc:
                self.invalidate()
                self.status.setText(str(exc))
        self._controls()

    def preview_output(self, item, *_):
        if item is None:
            return
        raw = dict(self.payloads).get(item.text(0))
        if raw is None:
            return
        prefix = f"{item.text(0)}\n{len(raw)} bytes · 完整摘要见技术详情\n\n"
        if item.text(0).lower().endswith(".pdf"):
            text = "此处不预览版面。交付使用本次固定的 PDF 原始字节，完整摘要见技术详情。"
        else:
            try:
                text = raw[:65536].decode("utf-8")
            except UnicodeDecodeError:
                text = "非 UTF-8，按原字节保留；十六进制预览：\n" + raw[:4096].hex(" ")
            if len(raw) > 65536:
                text += "\n[预览有长度上限；交付仍为完整原字节，请另行完整审阅。]"
        self.preview.setPlainText(prefix + text)

    def preview_check(self, item, *_):
        if item is not None and (check := item.data(0, Qt.ItemDataRole.UserRole)) is not None:
            self.preview.setPlainText(f"{check.title} · {STATUS_LABELS[check.status]}\n{check.reason}\n"
                "\n完整位置与输入身份见技术详情。")

    def choose_target(self):
        path, _ = QFileDialog.getSaveFileName(self, "选择尚不存在的新交付目录（不覆盖已有交付）")
        if path:
            self.target.setText(path)

    def perform(self):
        if self.busy or self.prepared is None or self.result is not None:
            return
        try:
            self._validate()
            prepared, target, options = self.prepared, self.target.text(), self.options()
            if not target:
                raise ValueError("请指定原项目之外的新交付目录。")
            accept = self.acknowledge.isChecked()
            if prepared.unconfirmed and not accept:
                raise ValueError("请逐项审阅未确认项并明确勾选知悉；未知不等于通过。")
            choice = QMessageBox.question(self, "确认生成固定版本交付", f"将生成新目录：{target}\n"
                f"共 {len(self.payloads)} 个已审阅文件；{len(prepared.unconfirmed)} 项未确认。\n"
                "只输出已固定的文件，不覆盖已有交付，不上传内容。继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if choice != QMessageBox.StandardButton.Yes:
                return
            self._validate()
            if (self.prepared is not prepared or self.options() != options or self.target.text() != target
                    or accept != self.acknowledge.isChecked()):
                raise ValueError("确认期间交付选择变化；请重新审阅。")
            cancel = self.cancel
            self._launch("publish", lambda stop: publish_submission(prepared, target,
                accept_unconfirmed=accept, cancelled=cancel))
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))

    def _explicit_action(self, compile_after):
        if self.busy or self.result is not None:
            return
        try:
            self._context()
            self.invalidate()
            if self.session is not None:
                (compile_block_session if compile_after else save_block_session)(self, self.session)
            elif compile_after:
                self.window.compile_action.trigger()
            else:
                self.cancel = threading.Event()
                self.window.documents.request_root_save(self.root, cancelled=self.cancel)
            self.status.setText("已调用现有保存 / FINAL 流程；请处理其结果，完成后主动重新检查。")
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))

    def save_inputs(self):
        self._explicit_action(False)

    def compile_final(self):
        self._explicit_action(True)

    def reject(self):
        if self.busy:
            self.closing = True
            self.cancel.set()
            self.status.setText("正在取消并等待核验/清理返回；原项目和已有交付保留。")
            self._controls()
            return
        self._close()

    def _close(self):
        self.cancel.set()
        self.timer.stop()
        self._release()
        super().reject()


def show_submission_delivery(window, *, session=None):
    app = QApplication.instance()
    previous = getattr(app, "_icstex_delivery_dialog", None)
    if previous is not None and isValid(previous):
        previous.raise_()
        previous.activateWindow()
        return None
    dialog = None
    try:
        dialog = SubmissionDeliveryDialog(window, session=session)
        app._icstex_delivery_dialog = dialog
        dialog.exec()
        return dialog.result
    except (OSError, ValueError) as exc:
        QMessageBox.warning(window, "准备提交未开始", str(exc))
        return None
    finally:
        if dialog is not None and isValid(dialog):
            dialog._close()
            dialog.deleteLater()
        app._icstex_delivery_dialog = None
