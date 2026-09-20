"""Small source-only ZIP export surface using the existing capture lifetime guard."""
from __future__ import annotations

from pathlib import Path
import threading

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Slot
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout)
from shiboken6 import isValid

from app.core.project_archive import (
    archive_selection_warnings, export_project_archive, review_project_archive,
)
from app.gui.project_checkpoint_dialog import CaptureLease, _Signals, _run


class ProjectArchiveDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        _, project, root, _, _, _ = window.readiness._context()
        if project is None or root is None:
            raise ValueError("请先打开并保存要导出的 LaTeX 工程。")
        self.window = window
        self.project, self.root = project.resolve(strict=True), root
        self.lease = self.review = self.result = None
        self.busy = self.closing = False
        self.cancel = threading.Event()
        self.setWindowTitle("导出为工程文件")
        self.setObjectName("projectArchiveDialog")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(760, 600)
        layout = QVBoxLayout(self)
        description = QLabel("把工程带到另一台电脑\n"
            "将选中的源码、图片、表格、引用库和本地样式打成 ZIP，保留原文件夹结构。"
            "解压后打开 project 文件夹即可继续写作，不需要先编译 PDF。")
        description.setWordWrap(True)
        layout.addWidget(description)
        self.status = QLabel("正在整理文件…")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.files = QTreeWidget()
        self.files.setHeaderLabels(["要带走的文件（可取消勾选）", "大小"])
        self.files.setRootIsDecorated(False)
        self.files.setColumnWidth(0, 540)
        layout.addWidget(self.files, 1)
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setTabChangesFocus(True)
        self.notes.setMaximumHeight(125)
        self.notes.setAccessibleName("工程导出提示")
        layout.addWidget(self.notes)
        policy = QLabel("仅整理当前项目文件夹内的本地文件，不收集历史、草稿、缓存或系统字体。"
                        "请检查清单中是否有不想分享的资料。另一台电脑仍需安装 LaTeX 环境和所需字体。")
        policy.setWordWrap(True)
        layout.addWidget(policy)
        row = QHBoxLayout()
        self.close_button = QPushButton("取消")
        self.export_button = QPushButton("导出 ZIP…")
        self.export_button.setObjectName("primaryButton")
        row.addWidget(self.close_button)
        row.addStretch()
        row.addWidget(self.export_button)
        layout.addLayout(row)
        self.signals = _Signals(self)
        self.signals.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self.destroyed.connect(self.cancel.set)
        self.close_button.clicked.connect(self.reject)
        self.export_button.clicked.connect(self.choose_target)
        self.files.itemChanged.connect(self.selection_changed)
        self._controls()
        QTimer.singleShot(0, self.scan)

    def _controls(self):
        enabled = not self.busy and not self.closing and self.result is None
        self.files.setEnabled(enabled)
        self.export_button.setEnabled(enabled and self.review is not None and not self.cancel.is_set())

    def scan(self):
        """GUI thread freezes save intent; the worker sees only local snapshots."""
        if self.closing:
            return
        try:
            self.lease = CaptureLease(self.window, self.project)
            self.cancel = self.lease.cancelled
            self.destroyed.connect(self.cancel.set)
            if self.lease.drafts:
                raise ValueError("还有未保存的修改。请关闭此窗口，保存后再导出，以免漏掉刚写的内容。")
            if any(tab.external_conflict for _, tab, *_ in self.lease.tabs):
                raise ValueError("有文件在外部被修改，请先处理冲突再导出。")
            project, root = self.project, self.root
            self._launch("scan", lambda stop: review_project_archive(project, root, cancelled=stop))
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))
            self._release()
            self._controls()

    def selected(self):
        return tuple(self.files.topLevelItem(i).text(0) for i in range(self.files.topLevelItemCount())
                     if self.files.topLevelItem(i).checkState(0) == Qt.CheckState.Checked)

    def selection_changed(self, *_):
        if self.review is None:
            return
        selected = self.selected()
        size = sum(len(entry.payload) for entry in self.review.inputs.files if entry.path in selected)
        self.status.setText(f"已选择 {len(selected)} 个文件，共 {size / 1024 / 1024:.2f} MiB。主文件：{self.review.root}")
        warnings = archive_selection_warnings(self.review, selected)
        self.notes.setPlainText("\n".join(warnings) if warnings else
            "未发现已识别引用的缺失文件。动态路径和自定义宏不一定能识别，请保留所需的额外材料。")

    def _launch(self, operation, work):
        self.operation, self.busy = operation, True
        self._controls()
        self.thread = threading.Thread(target=_run, args=(work, self.cancel, self.signals),
                                       name="icstex-project-archive", daemon=True)
        self.thread.start()

    @Slot(object, str)
    def _finished(self, result, error):
        """Apply results only on the GUI thread; closing waits for worker cleanup."""
        self.busy = False
        if self.operation == "export" and result is not None:
            self.result = result
            self.status.setText(f"工程文件已导出：\n{result}\n在另一台电脑解压后，打开 project 文件夹。")
            self.close_button.setText("关闭")
            self._release()
        elif error:
            self.review = None
            self.status.setText(error)
            self._release()
        elif not self.closing and not self.cancel.is_set():
            try:
                self.lease.validate()
                self.review = result
                with QSignalBlocker(self.files):
                    for entry in result.inputs.files:
                        item = QTreeWidgetItem([entry.path, f"{len(entry.payload) / 1024:.1f} KiB"])
                        item.setCheckState(0, Qt.CheckState.Checked)
                        if entry.path == result.root:
                            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                        self.files.addTopLevelItem(item)
                self.selection_changed()
            except ValueError as exc:
                self.review = None
                self.status.setText(str(exc))
                self._release()
        else:
            self.status.setText("内容在整理后变化，请关闭此窗口并重新导出。")
            self._release()
        if self.closing:
            self._close()
        self._controls()

    def choose_target(self):
        if self.review is None or self.busy or self.result is not None:
            return
        suggested = self.project.parent / (self.project.name + "-工程.zip")
        path, _ = QFileDialog.getSaveFileName(self, "保存工程 ZIP（使用新文件名）", str(suggested), "ZIP 工程文件 (*.zip)")
        if path:
            self.export_to(Path(path) if Path(path).suffix.lower() == ".zip" else Path(path + ".zip"))

    def export_to(self, target):
        if self.review is None or self.busy or self.result is not None:
            return
        try:
            self.lease.validate()
            selected, review = self.selected(), self.review
            warnings = archive_selection_warnings(review, selected)
            if warnings:
                answer = QMessageBox.question(self, "有些文件可能没有带齐",
                    "\n".join(warnings[:8]) + "\n\n仍导出选中的现有文件？提示会保留在包内说明中。",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    return
            self.lease.validate()
            self.status.setText("正在打包和核对文件，可取消；不会改动原工程。")
            self._launch("export", lambda stop: export_project_archive(review, selected, target,
                                                       accept_warnings=bool(warnings), cancelled=stop))
        except ValueError as exc:
            self.status.setText(str(exc))
            self._controls()

    def _release(self):
        if self.lease is not None:
            self.lease.release()
            self.lease = None

    def _close(self):
        self._release()
        super().reject()

    def reject(self):
        self.closing = True
        self.cancel.set()
        if self.busy:
            self.status.setText("正在取消，等待当前文件处理结束…")
            self._controls()
        else:
            self._close()


def show_project_archive(window):
    app = QApplication.instance()
    previous = getattr(app, "_icstex_project_archive_dialog", None)
    if previous is not None and isValid(previous):
        previous.raise_()
        previous.activateWindow()
        return
    dialog = None
    try:
        dialog = ProjectArchiveDialog(window)
        app._icstex_project_archive_dialog = dialog
        dialog.exec()
    except (ValueError, OSError) as exc:
        QMessageBox.warning(window, "工程导出未开始", str(exc))
    finally:
        if dialog is not None:
            dialog._release()
            dialog.deleteLater()
        app._icstex_project_archive_dialog = None
