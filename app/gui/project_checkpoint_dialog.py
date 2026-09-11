"""Explicit project checkpoints; disk bytes and GUI drafts never replace each other."""
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import threading

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout)
from shiboken6 import isValid

from app.core.project_checkpoint import (DraftInput, CheckpointCancelled, MAX_DRAFT_BYTES,
    MAX_DRAFTS, checkpoint_candidates, checkpoint_review, create_checkpoint, restore_checkpoint)


def _windows(owner):
    return tuple(dict.fromkeys([owner, *(widget for widget in QApplication.topLevelWidgets()
        if hasattr(widget, "documents") and hasattr(widget, "tabs") and isValid(widget))]))


def _belongs(path, project):
    return path is not None and Path(path).absolute().is_relative_to(project)


class CaptureLease:
    """Pause only captured tabs/sessions; preserve their pre-existing save intent."""
    def __init__(self, owner, project):
        self.project = project
        self.cancelled = threading.Event()
        self.tabs, self.sessions, self.connections, self.windows = [], [], [], []
        self.drafts = []
        self.released = False
        try:
            for wi, window in enumerate(_windows(owner)):
                related = [tab for tab in window.tabs.values() if _belongs(tab.path, project)
                           or (window is owner and tab.path is None)]
                session = getattr(window, "block_session", None)
                session = session if session and session.project_dir == project and not session._closed else None
                if not related and session is None:
                    continue
                self.windows.append(window)
                if any(manager.is_busy or manager._scheduled_request is not None or manager._pending_request is not None
                       for root, manager in window.compile_managers.items()
                       if _belongs(root, project)):
                    raise ValueError("项目正在编译或排队；请先停止或等待完成，再创建检查点。")
                worker = getattr(window.insertions, "_drop_worker", None)
                if worker is not None and isValid(worker) and worker.isRunning():
                    raise ValueError("图片正在导入；请等待导入结束后创建检查点。")
                self._watch(window.destroyed)
                self._watch(window.signals.external_changed, lambda path: _belongs(path, project))
                for ti, tab in enumerate(related):
                    revision = tab.editor.document().revision()
                    remaining = tab.save_timer.remainingTime() if tab.save_timer else -1
                    self.tabs.append((window, tab, tab.path, revision, remaining, tab.pending_compile_after_save))
                    window.documents.checkpoint_tabs.add(id(tab))
                    window.documents.cancel_save_timer(tab)
                    self._watch(tab.editor.document().contentsChange,
                                lambda _position, removed, added: bool(removed or added))
                    if tab.dirty or tab.modified:
                        target = tab.path.relative_to(project).as_posix() if tab.path else None
                        self.drafts.append(DraftInput(f"source-{wi}-{ti}", "source-text", target,
                                                     tab.editor.toPlainText().encode("utf-8")))
                if session is not None:
                    if session.compile_manager and (session.compile_manager.is_busy
                            or session.compile_manager._scheduled_request is not None
                            or session.compile_manager._pending_request is not None):
                        raise ValueError("Block 项目正在编译；请先停止或等待完成。")
                    if session._writes_paused or session._checkpoint_paused:
                        raise ValueError("Block 项目已有保存/修复操作；请先完成或取消该操作。")
                    pending = session.pause_writes()
                    session._checkpoint_paused = True
                    key = session._revision, session.editor_draft_revision
                    self.sessions.append((session, pending, key))
                    self._watch(session.model_changed)
                    self._watch(session.editor_drafts_changed)
                    self._watch(session.destroyed)
                    if session.has_unsaved_changes:
                        payload = {"format": "icstex-block-draft", "version": 1,
                            "model": {"blocks": [b.to_dict() for b in session.registry.blocks()],
                                      "layout": session.layout.to_dict() if session.layout else None,
                                      "sources": [s.to_dict() for s in session.sources],
                                      "document_theme": session.document_theme.to_dict()},
                            "unapplied": [asdict(draft) for draft in session.editor_drafts.values()]}
                        self.drafts.append(DraftInput(f"block-{wi}", "block-state", None,
                            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")))
            if len(self.drafts) > MAX_DRAFTS or any(len(d.payload) > MAX_DRAFT_BYTES for d in self.drafts):
                raise ValueError("草稿超过检查点上限；没有丢弃、截断或保存草稿。")
        except BaseException:
            self.release()
            raise

    def _watch(self, signal, predicate=None):
        def cancel(*args):
            if predicate is None or predicate(*args):
                self.cancelled.set()
        signal.connect(cancel)
        self.connections.append((signal, cancel))

    def validate(self):
        if self.cancelled.is_set():
            raise ValueError("采集期间草稿或窗口变化；请取消后重新创建检查点。")
        for window, tab, path, revision, _, _ in self.tabs:
            if (not isValid(window) or not isValid(tab.editor) or window.tabs.get(id(tab.editor)) is not tab
                    or tab.path != path or tab.editor.document().revision() != revision):
                self.cancelled.set()
                raise ValueError("采集目标变化；当前内容保持不变。")
        for session, _, key in self.sessions:
            if not isValid(session) or session._closed or (session._revision, session.editor_draft_revision) != key:
                self.cancelled.set()
                raise ValueError("Block 草稿变化；请重新创建检查点。")

    def release(self):
        if self.released:
            return
        self.released = True
        for signal, callback in self.connections:
            try:
                signal.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        for window, tab, path, revision, remaining, pending in self.tabs:
            if not isValid(window):
                continue
            window.documents.checkpoint_tabs.discard(id(tab))
            if (isValid(tab.editor) and window.tabs.get(id(tab.editor)) is tab
                    and tab.path == path and tab.editor.document().revision() == revision
                    and remaining >= 0 and not tab.external_conflict and not window.readiness._closed):
                tab.pending_compile_after_save = pending
                tab.save_timer.start(max(1, remaining))
        for session, pending, key in self.sessions:
            if isValid(session):
                session._checkpoint_paused = False
                session.resume_writes(pending if (session._revision, session.editor_draft_revision) == key else (False, False))


class _Signals(QObject):
    finished = Signal(object, str)


def _run(work, cancel, signals):
    result, error = None, ""
    try:
        result = work(cancel.is_set)
    except CheckpointCancelled:
        error = "已取消；原项目和草稿未被修改。"
    except Exception as exc:
        error = f"未完成，原件保留：{exc}"
    try:
        signals.finished.emit(result, error)
    except RuntimeError:
        pass


class ProjectCheckpointDialog(QDialog):
    def __init__(self, window, *, restore=False):
        super().__init__(window)
        self.window, self.restore_mode = window, restore
        self.lease = None
        self.info = self.archive = self.result_path = None
        self.previews, self.drafts = {}, {}
        self.busy = self.closing = False
        self.cancel = threading.Event()
        self.setWindowTitle("项目检查点 · 恢复为新目录" if restore else "项目检查点 · 文件与独立草稿")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(880, 640)
        outer = QVBoxLayout(self)
        self.status = QLabel("只处理用户选定的本地文件；不保存、编译、联网或覆盖原项目。")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(self.status)
        row = QHBoxLayout()
        self.open_button = QPushButton("选择检查点文件…" if restore else "加入项目文件…")
        self.select_button = QPushButton("全选清单")
        self.clear_button = QPushButton("清空勾选")
        row.addWidget(self.open_button)
        row.addWidget(self.select_button)
        row.addWidget(self.clear_button)
        outer.addLayout(row)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["种类 / 纳入", "项目相对路径或草稿", "字节 / SHA-256"])
        self.tree.setRootIsDecorated(False)
        self.tree.setColumnWidth(0, 140)
        self.tree.setColumnWidth(1, 360)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("选择草稿查看独立恢复内容；预览不应用到项目。")
        splitter.addWidget(self.tree)
        splitter.addWidget(self.preview)
        outer.addWidget(splitter, 1)
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("新恢复目录：" if restore else "新检查点文件："))
        self.target = QLineEdit()
        self.target.setAccessibleName("新恢复目录" if restore else "新检查点文件")
        self.target.setPlaceholderText("必须是尚不存在的目标；父目录由你显式选择")
        self.target_button = QPushButton("选择位置…")
        target_row.addWidget(self.target, 1)
        target_row.addWidget(self.target_button)
        outer.addLayout(target_row)
        self.policy = QLabel("仅覆盖清单中选定的文件。已保存文件保留原始编码/换行；草稿为独立 UTF-8。"
            "同目录副本不等于独立备份；目录可列出不证明云端文件已下载。单次最多 2000 文件、200 草稿、256 MiB。")
        self.policy.setWordWrap(True)
        outer.addWidget(self.policy)
        bottom = QHBoxLayout()
        self.reveal_button = QPushButton("显示已验证结果的位置")
        self.reveal_button.hide()
        self.action_button = QPushButton("审阅后恢复到新目录" if restore else "创建选定文件检查点")
        self.action_button.setDefault(False)
        self.close_button = QPushButton("取消 / 关闭")
        bottom.addWidget(self.reveal_button)
        bottom.addStretch(1)
        bottom.addWidget(self.action_button)
        bottom.addWidget(self.close_button)
        outer.addLayout(bottom)
        self.signals = _Signals(self)
        self.signals.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self.open_button.clicked.connect(self.choose_archive if restore else self.add_files)
        self.target_button.clicked.connect(self.choose_target)
        self.action_button.clicked.connect(self.perform)
        self.close_button.clicked.connect(self.reject)
        self.select_button.clicked.connect(lambda: self._check_all(Qt.CheckState.Checked))
        self.clear_button.clicked.connect(lambda: self._check_all(Qt.CheckState.Unchecked))
        self.tree.currentItemChanged.connect(self._preview)
        self.reveal_button.clicked.connect(self.reveal)
        self.destroyed.connect(self.cancel.set)
        if restore:
            self.select_button.hide()
            self.clear_button.hide()
            self.action_button.setEnabled(False)
        else:
            _, project, _, _, _, _ = window.readiness._context()
            if project is None:
                self.deleteLater()
                raise ValueError("请先打开本地项目；未命名草稿不能单独冒充项目检查点。")
            self.project = project.resolve(strict=True)
            try:
                self.lease = CaptureLease(window, self.project)
            except BaseException:
                self.deleteLater()
                raise
            self.destroyed.connect(self.lease.release)
            self.cancel = self.lease.cancelled
            self.destroyed.connect(self.cancel.set)
            self.drafts = {draft.id: draft for draft in self.lease.drafts}
            self.status.setText(f"项目：{self.project}\n已暂停相关源文件/Block 写入；请审阅和勾选要保留的内容。")
            self._launch("inventory", lambda stop: checkpoint_candidates(self.project, cancelled=stop))

    def _launch(self, operation, work):
        if self.busy:
            return
        self.operation = operation
        self.busy = True
        for widget in (self.open_button, self.target_button, self.target, self.tree,
                       self.action_button, self.select_button, self.clear_button):
            widget.setEnabled(False)
        self.status.setText(self.status.text().split("\n处理中")[0] + "\n处理中，可取消；不会改写原项目。")
        self.thread = threading.Thread(target=_run, args=(work, self.cancel, self.signals),
                                       name="icstex-checkpoint", daemon=True)
        self.thread.start()

    def _row(self, kind, name, detail, key, *, checked=True):
        item = QTreeWidgetItem([kind, name, detail])
        item.setData(0, Qt.ItemDataRole.UserRole, key)
        if not self.restore_mode:
            item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.tree.addTopLevelItem(item)

    @Slot(object, str)
    def _finished(self, result, error):
        self.busy = False
        if not error and self.operation == "create":
            try:
                self.lease.validate()
            except ValueError:
                self.result_path = self._job_target
                self.reveal_button.show()
                error = f"文件已生成于 {self.result_path}，但草稿或窗口已变化；不接受为当前状态检查点，请重新采集。"
        if error:
            self.status.setText(error + "\n未保存草稿仍留在原窗口；重新打开此界面后重试。")
        elif self.operation == "inventory":
            paths, warnings = result
            for path in paths:
                self._row("磁盘文件", path, "创建时读取并核对原始字节", ("file", path))
            for draft in self.drafts.values():
                self._row("独立草稿", f"{draft.id} · {draft.target or '未命名 / Block 状态'}",
                          str(len(draft.payload)), ("draft", draft.id))
            self.status.setText(f"项目：{self.project}\n候选清单已列出，请明确勾选；不是完整依赖扫描。"
                                + ("\n" + "\n".join(warnings) if warnings else ""))
        elif self.operation == "review":
            self.info, self.previews = result
            self.tree.clear()
            for entry in self.info.files:
                self._row("磁盘原始字节", entry.path, f"{entry.size} / {entry.sha256}", ("file", entry.path))
            for entry in self.info.drafts:
                self._row("独立草稿", f"{entry.id} · {entry.target or entry.kind}",
                          f"{entry.size} / {entry.sha256}", ("draft", entry.id))
            self.status.setText(f"检查点已完整校验：{self.archive}\n时间：{self.info.created_at}。请审阅文件与草稿，选择新目录。")
        else:
            self.result_path = self._job_target
            if self.operation == "restore":
                self.status.setText(f"已核验并恢复到新目录：{result.directory}\n磁盘文件：project/；独立草稿：drafts/。"
                                    "恢复操作未改写原项目，也未切换项目、应用草稿或触发编译。")
            else:
                self.info = result
                self.status.setText(f"已核验选定文件检查点：{self.result_path}\n{len(result.files)} 个原始字节文件，"
                                    f"{len(result.drafts)} 份独立草稿。未保存或编译原项目。")
            self.reveal_button.show()
        if self.closing:
            # A publication which won the final cancellation race is retained and
            # reported, never deleted or falsely described as cancelled.
            if (error and result is None) or self.operation in {"inventory", "review"}:
                self._close()
                return
            self.close_button.setText("关闭（结果已生成）")
        for widget in (self.open_button, self.target_button, self.target, self.tree,
                       self.select_button, self.clear_button):
            widget.setEnabled(not self.closing and not self.cancel.is_set())
        self.action_button.setEnabled(not self.cancel.is_set() and (self.info is not None if self.restore_mode else True)
                                      and (bool(error) or self.operation in {"inventory", "review"}))

    def _check_all(self, state):
        for index in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(index).setCheckState(0, state)

    def _preview(self, item, _old=None):
        self.preview.clear()
        if item is None:
            return
        kind, key = item.data(0, Qt.ItemDataRole.UserRole)
        if kind == "draft":
            text = self.previews.get(key, "") if self.restore_mode else self.drafts[key].payload.decode("utf-8")
            self.preview.setPlainText(text[:64000] + ("\n[预览截断；完整草稿仍会保留。]" if len(text) > 64000 else ""))
        else:
            self.preview.setPlainText(f"{key}\n{item.text(2)}\n磁盘文件与未保存草稿分开保留；不自动应用草稿。")

    def add_files(self):
        names, _ = QFileDialog.getOpenFileNames(self, "显式选择项目内文件", str(self.project))
        known = {self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) for i in range(self.tree.topLevelItemCount())}
        for name in names:
            try:
                path = Path(name).absolute().relative_to(self.project).as_posix()
            except ValueError:
                self.status.setText("项目外文件未加入；请选择项目内文件。")
                continue
            if ("file", path) not in known:
                self._row("磁盘文件", path, "创建时核验；不支持的内部路径会拒绝", ("file", path))
                known.add(("file", path))

    def choose_archive(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择要审阅的检查点", "", "ICSTeX checkpoint (*.icstex-checkpoint);;所有文件 (*)")
        if path:
            self.load_archive(Path(path))

    def load_archive(self, path):
        if self.busy:
            return
        self.info = None
        self.result_path = None
        self.reveal_button.hide()
        self.archive = path
        self.tree.clear()
        self.previews.clear()
        self._launch("review", lambda stop: checkpoint_review(path, cancelled=stop))

    def choose_target(self):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        name = f"恢复副本-{stamp}" if self.restore_mode else f"{self.project.name}-{stamp}.icstex-checkpoint"
        target, _ = QFileDialog.getSaveFileName(self, "选择尚不存在的新恢复目录名称" if self.restore_mode else "检查点另存到新文件", name)
        if target:
            self.target.setText(target)

    def perform(self):
        if self.busy or self.cancel.is_set():
            return
        target = self.target.text().strip()
        if not target:
            self.status.setText("请显式选择尚不存在的输出目标；没有保存或恢复任何文件。")
            return
        try:
            if self.restore_mode:
                if self.info is None:
                    return
                files, drafts = self.info.files, self.info.drafts
            else:
                self.lease.validate()
                selected = [self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
                            for i in range(self.tree.topLevelItemCount())
                            if self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked]
                files = tuple(name for kind, name in selected if kind == "file")
                drafts = tuple(self.drafts[name] for kind, name in selected if kind == "draft")
                if not files:
                    raise ValueError("至少选择一个磁盘文件；草稿单独保存，不替换磁盘版本。")
            choice = QMessageBox.question(self, "确认选定内容与新目标",
                f"文件：{len(files)}；独立草稿：{len(drafts)}\n目标：{target}\n\n"
                "只处理清单中选定内容，不覆盖原项目、不自动应用草稿或编译。确认继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if choice != QMessageBox.StandardButton.Yes:
                return
            self._job_target = Path(target).expanduser().absolute()
            if self.restore_mode:
                archive, info = self.archive, self.info
                self._launch("restore", lambda stop: restore_checkpoint(archive, target, cancelled=stop, expected_info=info))
            else:
                self.lease.validate()
                self._launch("create", lambda stop: create_checkpoint(self.project, files, target, drafts=drafts, cancelled=stop))
        except (OSError, ValueError) as exc:
            self.status.setText(f"未执行，原件与草稿保留：{exc}")

    def reveal(self):
        if self.result_path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result_path if self.restore_mode else self.result_path.parent)))

    def reject(self):
        if self.busy:
            self.closing = True
            self.cancel.set()
            self.status.setText("正在取消；等待当前文件读取/清理返回。原项目与草稿保持不变。")
            self.close_button.setText("正在取消…")
            return
        self._close()

    def _close(self):
        self.cancel.set()
        if self.lease:
            self.lease.release()
        super().reject()


def show_project_checkpoint(window, *, restore=False):
    app = QApplication.instance()
    previous = getattr(app, "_icstex_checkpoint_dialog", None)
    if previous is not None and isValid(previous):
        previous.raise_()
        previous.activateWindow()
        return
    dialog = None
    try:
        dialog = ProjectCheckpointDialog(window, restore=restore)
        app._icstex_checkpoint_dialog = dialog
        dialog.exec()
    except (OSError, ValueError) as exc:
        QMessageBox.warning(window, "项目检查点未开始", str(exc))
    finally:
        if dialog is not None and isValid(dialog):
            dialog._close()
            dialog.deleteLater()
        app._icstex_checkpoint_dialog = None


def checkpoint_close_guard(window):
    dialog = getattr(QApplication.instance(), "_icstex_checkpoint_dialog", None)
    if dialog is None or not isValid(dialog):
        return True
    if dialog.parent() is window or (dialog.lease and window in dialog.lease.windows):
        dialog.reject()
        return not dialog.busy
    return True
