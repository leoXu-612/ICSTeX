"""Explicit recovery-copy review and new-window editing; originals stay separate."""
from copy import deepcopy
from pathlib import Path
import threading

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout)
from shiboken6 import isValid

from app.core.project_recovery import (check_recovery_identity, parse_block_draft,
    read_recovery_copy, saved_block_model, selected_drafts)
from app.core.text_encoding import decode_latex_bytes
from app.gui.main_window_support import EditorTab
from app.gui.project_checkpoint_dialog import _Signals, _run, _windows, _belongs


def open_recovered_drafts(owner, copy, ids):
    """Install only reviewed input in a NEW window, with initial autosave paused."""
    entries = selected_drafts(copy, ids)
    for window in _windows(owner):
        session = getattr(window, "block_session", None)
        if (any(_belongs(tab.path, copy.project) for tab in window.tabs.values())
                or session is not None and session.project_dir == copy.project):
            raise ValueError("恢复副本已在窗口中打开；请先处理并关闭该副本，避免并行覆盖。")
    check_recovery_identity(copy)
    payloads, files = dict(copy.drafts), dict(copy.files)
    block = entries[0].kind == "block-state"
    session = None
    sources = []
    if block:
        from app.gui.blocks.project_session import ProjectSession
        model, drafts = parse_block_draft(payloads[entries[0].id])
        baseline = saved_block_model(copy)
        session = ProjectSession(project_dir=copy.project, **baseline)
        if session.save_error:
            error = session.save_error
            session.shutdown()
            session.deleteLater()
            raise ValueError("恢复副本无法建立保存基线；" + error)
        # Establish the writer from verified SAVED state, then populate the new
        # session before any widgets retain its model objects. No format rewrite.
        session.recovery_pending = True
        for key, value in model.items():
            setattr(session, key, value)
        session.editor_drafts = deepcopy(drafts)
        session._table_editors.clear()
        tables = [b.id for b in session.registry.blocks() if b.type == "table"]
        session.table_target_id = tables[0] if tables else None
        session.ensure_table_model()
        session.notify_model_changed("recovered_draft_loaded")
    else:
        for entry in entries:
            target = entry.target if (entry.target in files and
                Path(entry.target).suffix.lower() in {".tex", ".ltx", ".bib", ".sty", ".cls"}) else None
            decoded = decode_latex_bytes(files[target]) if target else None
            sources.append((entry, target, decoded, payloads[entry.id].decode("utf-8")))
    new = None
    try:
        check_recovery_identity(copy)
        new = owner.spawn_window()
        new.project_files.set_project_root(copy.project)
        if session is not None:
            from app.gui.block_mode import _install_session, _set_block_mode
            if not _install_session(new, session):
                raise ValueError("新窗口未接受恢复的 Block 会话。")
            _set_block_mode(new, True)
            first = next(iter(session.editor_drafts.values()), None)
            if first is not None:
                if first.kind == "layout":
                    session.selection.select_layout_node(first.target_id, source="recovery")
                else:
                    session.selection.select_block(first.target_id, source="recovery")
            elif session.registry.blocks():
                session.selection.select_block(session.registry.blocks()[0].id, source="recovery")
        else:
            if "main.tex" in files and not any(target == "main.tex" for _, target, _, _ in sources):
                decoded = decode_latex_bytes(files["main.tex"])
                tab = EditorTab(new._make_editor(decoded.text), copy.project / "main.tex", decoded.encoding)
                new._add_tab(tab, "main.tex")
                new._watch_file(tab.path)
                new.dependencies.remember_disk(tab.path, files["main.tex"])
            for entry, target, decoded, text in sources:
                tab = EditorTab(new._make_editor(decoded.text if decoded else ""),
                    copy.project / target if target else None, decoded.encoding if decoded else "utf-8",
                    recovery_pending=True, recovery_base=files[target] if target else None)
                new._add_tab(tab, Path(target).name if target else f"恢复草稿-{entry.id}.tex")
                cursor = QTextCursor(tab.editor.document())
                cursor.beginEditBlock()
                cursor.select(QTextCursor.SelectionType.Document)
                cursor.insertText(text)
                cursor.endEditBlock()
                tab.dirty = tab.modified = True
                new._set_tab_title(tab)
                if tab.path:
                    new._watch_file(tab.path)
                    new.dependencies.remember_disk(tab.path, files[target])
        check_recovery_identity(copy)
        new.workspace.refresh()
        new.statusBar().showMessage("已在独立窗口载入恢复草稿；首次显式保存前暂停自动写入，尚未编译。", 15000)
        return new
    except BaseException:
        if session is not None:
            session.editor_drafts.clear()
            session._dirty = False
            session.shutdown()
        if new is not None:
            for tab in new.tabs.values():
                tab.dirty = tab.modified = False
            new.close()
            new.deleteLater()
        elif session is not None:
            session.deleteLater()
        raise


class RecoveryDraftDialog(QDialog):
    def __init__(self, window, directory=None):
        super().__init__(window)
        self.window = window
        self.copy = self.opened_window = None
        self.busy = self.closing = False
        self.cancel = threading.Event()
        self.setWindowTitle("恢复副本 · 审阅草稿并继续编辑")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(900, 660)
        layout = QVBoxLayout(self)
        self.status = QLabel("选择已恢复的目录（内含 project/、drafts/、manifest.json），核验后明确选择草稿。")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.choose_button = QPushButton("选择恢复副本目录…")
        layout.addWidget(self.choose_button)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["继续编辑", "原目标 / 种类", "字节 / SHA-256"])
        self.tree.setRootIsDecorated(False)
        self.tree.setColumnWidth(0, 170)
        self.tree.setColumnWidth(1, 300)
        layout.addWidget(self.tree, 1)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview, 1)
        policy = QLabel("仅在新窗口载入选定草稿；首次显式保存前不自动写入。磁盘版本与原草稿文件保留。"
                        "同目标多份草稿须择一；Block 与源码草稿分别处理，不自动混合。未知格式不迁移。")
        policy.setWordWrap(True)
        layout.addWidget(policy)
        row = QHBoxLayout()
        self.apply_button = QPushButton("确认后在新窗口继续编辑")
        self.apply_button.setEnabled(False)
        self.close_button = QPushButton("取消 / 关闭")
        row.addStretch(1)
        row.addWidget(self.apply_button)
        row.addWidget(self.close_button)
        layout.addLayout(row)
        self.signals = _Signals(self)
        self.signals.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self.destroyed.connect(self.cancel.set)
        self.choose_button.clicked.connect(self.choose)
        self.tree.currentItemChanged.connect(self.show_preview)
        self.apply_button.clicked.connect(self.perform)
        self.close_button.clicked.connect(self.reject)
        if directory is not None:
            self.load_directory(directory)

    def _launch(self, work):
        self.busy = True
        for widget in (self.choose_button, self.tree, self.apply_button):
            widget.setEnabled(False)
        self.status.setText("正在核验所有清单文件与独立草稿，可取消；不保存或编译。")
        self.thread = threading.Thread(target=_run, args=(work, self.cancel, self.signals),
                                       name="icstex-recovery-review", daemon=True)
        self.thread.start()

    def choose(self):
        directory = QFileDialog.getExistingDirectory(self, "选择已恢复副本的容器目录")
        if directory:
            self.load_directory(directory)

    def load_directory(self, directory):
        if self.busy:
            return
        self.copy = None
        self.ids = None
        self.tree.clear()
        self.preview.clear()
        self._launch(lambda stop: read_recovery_copy(directory, cancelled=stop))

    @Slot(object, str)
    def _finished(self, result, error):
        self.busy = False
        if self.closing or self.cancel.is_set():
            super().reject()
            return
        if error:
            self.status.setText(error)
        elif self.ids is not None:
            try:
                self.opened_window = open_recovered_drafts(self.window, result, self.ids)
            except (OSError, ValueError, TypeError, RecursionError) as exc:
                error = str(exc)
                self.status.setText("未载入草稿，原件保留：" + error)
            else:
                self.accept()
                return
        else:
            self.copy = result
            for entry in result.info.drafts:
                item = QTreeWidgetItem([entry.id, entry.target or entry.kind, f"{entry.size} / {entry.sha256}"])
                item.setData(0, Qt.ItemDataRole.UserRole, entry.id)
                item.setCheckState(0, Qt.CheckState.Unchecked)
                self.tree.addTopLevelItem(item)
            self.status.setText(f"已核验：{result.directory}\n{len(result.info.files)} 个文件，{len(result.info.drafts)} 份草稿。请审阅后勾选。")
        self.ids = None
        self.choose_button.setEnabled(True)
        self.tree.setEnabled(True)
        self.apply_button.setEnabled(self.copy is not None and bool(self.copy.info.drafts))

    def show_preview(self, item, _old=None):
        self.preview.clear()
        if self.copy is not None and item is not None:
            text = dict(self.copy.drafts)[item.data(0, Qt.ItemDataRole.UserRole)].decode("utf-8")
            self.preview.setPlainText(text[:64000] + ("\n[预览截断；完整草稿仍保留。]" if len(text) > 64000 else ""))

    def perform(self):
        if self.busy or self.copy is None:
            return
        ids = tuple(self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
                    for i in range(self.tree.topLevelItemCount())
                    if self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked)
        try:
            selected_drafts(self.copy, ids)
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        copy = self.copy
        answer = QMessageBox.question(self, "确认独立恢复编辑", f"载入 {len(ids)} 份草稿到新窗口？\n"
            "不改原项目，不自动保存或编译；保存时仅写入已恢复副本。未绑定目标的草稿需另存为。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            if self.copy is not copy or self.cancel.is_set():
                self.status.setText("审阅目标已切换或取消；未载入草稿。")
                return
            self.ids = ids
            self._launch(lambda stop: read_recovery_copy(copy.directory, expected=copy, cancelled=stop))

    def reject(self):
        self.cancel.set()
        if self.busy:
            self.closing = True
            self.status.setText("正在取消，等待读取返回；不会载入或保存草稿。")
        else:
            super().reject()


def show_recovery_drafts(window, directory=None):
    app = QApplication.instance()
    previous = getattr(app, "_icstex_recovery_dialog", None)
    if previous is not None and isValid(previous):
        previous.raise_()
        return
    dialog = RecoveryDraftDialog(window, directory)
    app._icstex_recovery_dialog = dialog
    try:
        dialog.exec()
    finally:
        dialog.cancel.set()
        dialog.deleteLater()
        app._icstex_recovery_dialog = None
