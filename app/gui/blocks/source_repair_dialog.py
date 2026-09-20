"""Explicit source-to-table repair, with bounded worker reads and one final Undo."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from app.core.blocks.source_merge import MergeResult, TableConflict, merge_three_way
from app.core.blocks.source_repair import (
    ColumnMapping, ImportOptions, capture_source, map_source_tables, parse_source, verify_capture,
)
from app.gui.blocks.merge_dialog import MergeDialog, _preview_json
from app.gui.blocks.source_repair_session import SourceRepairSnapshot


class _ReadSignals(QObject):
    finished = Signal(object, str)


def _read_worker(work, cancel, active, signals):
    result, error = None, ""
    try:
        result = work(cancel.is_set)
    except Exception as exc:
        error = f"读取/校验未完成：{exc}"
    finally:
        active.clear()
    if not cancel.is_set():
        try:
            signals.finished.emit(result, error)
        except RuntimeError:
            pass  # Dialog/application was destroyed; worker owns no widget.


def _read_in_background(parent, session, work):
    """One worker per modal step, no pending queue; cancellation never applies."""
    if session._closed:
        return None
    previous = getattr(session, "_source_repair_reader", None)
    if previous is not None and previous.is_set():
        raise ValueError("上一次来源读取/解析尚未结束，请稍后重试；没有启动第二个工作线程。")
    active = threading.Event()
    active.set()
    session._source_repair_reader = active
    dialog = QDialog(parent)
    dialog.setWindowTitle("读取与复核来源（不修改文件）")
    layout = QVBoxLayout(dialog)
    message = QLabel("正在读取本地来源。可取消；原始数据与表格尚未修改。")
    message.setWordWrap(True)
    layout.addWidget(message)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    cancel = threading.Event()
    signals = _ReadSignals()
    values = []

    def finished(result, error):
        if cancel.is_set() or session._closed:
            dialog.reject()
            return
        values.append((result, error))
        dialog.accept()

    def lifecycle():
        if session._closed:
            dialog.reject()

    signals.finished.connect(finished, Qt.ConnectionType.QueuedConnection)
    session.compile_state_changed.connect(lifecycle)
    dialog.finished.connect(lambda _result: cancel.set())
    threading.Thread(target=_read_worker, args=(work, cancel, active, signals),
                     name="icstex-source-repair", daemon=True).start()
    try:
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
    finally:
        cancel.set()
        session.compile_state_changed.disconnect(lifecycle)
        signals.finished.disconnect(finished)
        dialog.deleteLater()
    if not accepted or not values or session._closed:
        return None
    result, error = values[0]
    if error:
        raise ValueError(error)
    return result


def _buttons(dialog, layout, label):
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText(label)
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消全部修复")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    return buttons


class SourceVersionDialog(QDialog):
    def __init__(self, snapshot, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择来源原始版本")
        self.resize(700, 360)
        self.snapshot = snapshot
        layout = QVBoxLayout(self)
        text = QLabel(f"来源：{snapshot.record.relativePath}\n基线 SHA-256：{snapshot.record.baseSha256}\n"
                      f"须逐一确认全部 {len(snapshot.blocks)} 个关联表格，最后统一应用。\n"
                      "请选择项目内、摘要匹配的原始 CSV/XLSX。不能用当前表格替代原始版本。\n"
                      "修复不会改写原始数据，也不创建项目级备份；请自行保留原始和当前数据版本。")
        text.setTextFormat(Qt.TextFormat.PlainText)
        text.setWordWrap(True)
        layout.addWidget(text)
        self.baseline_path = QLineEdit()
        self.baseline_path.setPlaceholderText("项目相对路径，例如 data/original.csv")
        layout.addWidget(self.baseline_path)
        choose = QPushButton("选择原始版本…")
        choose.clicked.connect(self._choose)
        layout.addWidget(choose)
        _buttons(self, layout, "读取两份来源")

    def _choose(self):
        name, _filter = QFileDialog.getOpenFileName(self, "选择项目内原始版本", str(self.snapshot.project),
                                                  "表格来源 (*.csv *.xlsx)")
        if name:
            try:
                self.baseline_path.setText(Path(name).relative_to(self.snapshot.project).as_posix())
            except ValueError:
                QMessageBox.warning(self, "未读取项目外文件", "请选择当前项目内的原始版本；本流程不会自动复制或读取项目外文件。")


class SourceTableMappingDialog(QDialog):
    def __init__(self, session, snapshot, block_id, baseline, remote, parent=None):
        super().__init__(parent)
        self.session, self.snapshot, self.block_id = session, snapshot, block_id
        self.baseline, self.remote = baseline, remote
        self.local = deepcopy(snapshot.local_tables[block_id])
        self.parsed = None
        self._parse_revision = 0
        self.candidate = None
        self.setWindowTitle(f"来源修复 · {snapshot.blocks[block_id]['alias']}")
        self.resize(780, 720)
        layout = QVBoxLayout(self)
        self.status = QLabel("选择真实导入选项，再核对列映射与唯一行键。XLSX 只读缓存，不执行公式；缓存新鲜度未验证。")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        self.encoding = QComboBox()
        self.encoding.addItems(["utf-8-sig", "gbk", "latin-1"])
        self.header = QCheckBox("两份来源首行为表头")
        self.header.setChecked(True)
        self.base_sheet, self.remote_sheet = QLineEdit(), QLineEdit()
        self.base_range, self.remote_range = QLineEdit(), QLineEdit()
        form.addRow("CSV 编码（严格解码）", self.encoding)
        form.addRow(self.header)
        for label, widget in (("原始 XLSX 工作表", self.base_sheet), ("原始范围（空白为全表）", self.base_range),
                              ("当前 XLSX 工作表", self.remote_sheet), ("当前范围（空白为全表）", self.remote_range)):
            form.addRow(label, widget)
        self.load_button = QPushButton("读取选定表格（只读）")
        form.addRow(self.load_button)
        self.load_button.clicked.connect(self._load)
        self.mode = QComboBox()
        self.mode.addItems(["按唯一行键合并数据，保留本地列格式", "整表比较：明确保留本地或采用外部全部内容"])
        form.addRow("比较方式", self.mode)
        self.key_column = QComboBox()
        for column in self.local.columns:
            self.key_column.addItem(f"{column.name} · {column.dataType}", column.id)
        form.addRow("唯一行键（不可为空或重复）", self.key_column)
        self.mapping = QTableWidget(0, 3)
        self.mapping.setHorizontalHeaderLabels(["本地列 / 类型", "原始版本列", "当前版本列"])
        self.mapping.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mapping.setMinimumHeight(150)
        form.addRow(self.mapping)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_widget)
        layout.addWidget(scroll, 2)
        self.inputs = QTabWidget()
        layout.addWidget(self.inputs, 2)
        self.preview_button = QPushButton("查看差异并选择合并候选…")
        self.preview_button.setEnabled(False)
        self.preview_button.clicked.connect(self._preview)
        layout.addWidget(self.preview_button)
        cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel.button(QDialogButtonBox.StandardButton.Cancel).setText("取消全部修复")
        cancel.rejected.connect(self.reject)
        layout.addWidget(cancel)
        for widget in (self.encoding, self.header, self.base_sheet, self.remote_sheet, self.base_range, self.remote_range):
            signal = (widget.currentTextChanged if isinstance(widget, QComboBox) else
                      widget.toggled if isinstance(widget, QCheckBox) else widget.textChanged)
            signal.connect(self._invalidate)

    def _invalidate(self, *_args):
        self._parse_revision += 1
        self.parsed = None
        self.preview_button.setEnabled(False)
        self.status.setText("读取选项已变化，请重新读取；没有应用任何候选。")

    def _load(self):
        try:
            self.snapshot.validate(self.session)
            options = ImportOptions(self.encoding.currentText(), self.header.isChecked(), self.base_sheet.text(), self.base_range.text())
            remote_options = replace(options, sheet=self.remote_sheet.text(), cell_range=self.remote_range.text())
            baseline, remote = self.baseline, self.remote
            parse_revision = self._parse_revision

            def read(cancelled):
                if cancelled():
                    return None
                base_table = parse_source(baseline, options)
                if cancelled():
                    return None
                return base_table, parse_source(remote, remote_options)

            parsed = _read_in_background(self, self.session, read)
            if parsed is None:
                return
            self.snapshot.validate(self.session)
            if parse_revision != self._parse_revision:
                return
            self.parsed = parsed
            while self.inputs.count():
                widget = self.inputs.widget(0)
                self.inputs.removeTab(0)
                widget.deleteLater()
            complete = True
            for title, data in (("原始数据", parsed[0]), ("当前来源", parsed[1]), ("本地表格（含草稿）", self.local)):
                editor = QPlainTextEdit()
                editor.setReadOnly(True)
                text, ok = _preview_json(data.to_content_dict())
                complete &= ok
                editor.setPlainText(text)
                self.inputs.addTab(editor, title)
            self.mapping.setRowCount(len(self.local.columns))
            for row, column in enumerate(self.local.columns):
                item = QTableWidgetItem(f"{column.name} · {column.dataType}")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.mapping.setItem(row, 0, item)
                for side, table in enumerate(parsed, 1):
                    combo = QComboBox()
                    combo.addItem("请选择对应列", None)
                    for imported in table.columns:
                        combo.addItem(f"{imported.name} · {imported.id}", imported.id)
                    self.mapping.setCellWidget(row, side, combo)
                self.mapping.setRowHeight(row, max(self.mapping.cellWidget(row, side).sizeHint().height()
                                                    for side in (1, 2)) + 4)
            self.preview_button.setEnabled(complete)
            self.status.setText("请明确选择全部列映射和行键。数值/日期/布尔列按目标类型转换；文本不去空白。"
                                if complete else "完整输入预览超过显示上限，未开放应用；原内容保留。")
        except (ValueError, OSError) as exc:
            self._invalidate()
            self.status.setText(str(exc))

    def _preview(self):
        if self.parsed is None:
            return
        try:
            self.snapshot.validate(self.session)
            base, remote = self.parsed
            if self.mode.currentIndex() == 0:
                mapping = tuple(ColumnMapping(column.id, self.mapping.cellWidget(i, 1).currentData(),
                                              self.mapping.cellWidget(i, 2).currentData())
                                for i, column in enumerate(self.local.columns))
                base, remote = map_source_tables(base, remote, self.local, mapping,
                                                 key_column=self.key_column.currentData())
                result = merge_three_way(base, remote, self.local)
            else:
                # New identities prevent accidental preservation of opaque cell
                # attributes based on coincidentally equal importer row numbers.
                remote = deepcopy(remote)
                prefix = "source_" + self.remote.sha256[:16] + "_"
                remote.columns = [replace(c, id=prefix + c.id) for c in remote.columns]
                remote.rows = [replace(row, id=prefix + row.id,
                                      cells={prefix + key: value for key, value in row.cells.items()}) for row in remote.rows]
                result = MergeResult(deepcopy(self.local), table_conflict=TableConflict(base, remote, self.local))
            dialog = MergeDialog(result, self)
            try:
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self.snapshot.validate(self.session)
                    self.candidate = deepcopy(dialog.result.data)
                    self.accept()
            finally:
                dialog.deleteLater()
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))


def _confirm_transaction(parent, snapshot, candidates, remote):
    patches = snapshot.patches(candidates)
    dialog = QDialog(parent)
    dialog.setWindowTitle("最终确认：应用全部表格及来源基线")
    dialog.resize(800, 650)
    layout = QVBoxLayout(dialog)
    message = QLabel(f"本次统一应用 {len(patches)} 个表格并推进来源摘要。一次全局 Undo 可撤销。\n"
                     f"新基线 SHA-256：{remote.sha256}\n"
                     "原始数据文件不改写；确认后按现有自动保存策略保存项目。\n"
                     "下列预览包含将保留或删除的未建模字段；整表替换可能删除原行/列附加字段。")
    message.setTextFormat(Qt.TextFormat.PlainText)
    message.setWordWrap(True)
    layout.addWidget(message)
    tabs = QTabWidget()
    complete = True
    for title, contents in (("原项目内容", {k: v["content"] for k, v in snapshot.blocks.items()}),
                            ("将应用的完整内容", patches)):
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        text, ok = _preview_json(contents)
        complete &= ok
        editor.setPlainText(text)
        tabs.addTab(editor, title)
    layout.addWidget(tabs)
    buttons = _buttons(dialog, layout, "确认应用到项目（一次 Undo）")
    buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(complete)
    try:
        return dialog.exec() == QDialog.DialogCode.Accepted
    finally:
        dialog.deleteLater()


def run_source_repair(parent, session, source_id):
    pending = session.pause_writes()
    applied = False
    try:
        snapshot = SourceRepairSnapshot.capture(session, source_id)
        chooser = SourceVersionDialog(snapshot, parent)
        try:
            if chooser.exec() != QDialog.DialogCode.Accepted:
                return False
            relative = chooser.baseline_path.text()
        finally:
            chooser.deleteLater()
        snapshot.validate(session)

        def capture(cancelled):
            baseline = capture_source(snapshot.project, relative, expected_sha=snapshot.record.baseSha256, cancelled=cancelled)
            remote = capture_source(snapshot.project, snapshot.record.relativePath, cancelled=cancelled)
            return baseline, remote

        captured = _read_in_background(parent, session, capture)
        if captured is None:
            return False
        baseline, remote = captured
        candidates = {}
        for block_id in snapshot.blocks:
            snapshot.validate(session)
            dialog = SourceTableMappingDialog(session, snapshot, block_id, baseline, remote, parent)
            try:
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return False
                candidates[block_id] = deepcopy(dialog.candidate)
            finally:
                dialog.deleteLater()
        if not _confirm_transaction(parent, snapshot, candidates, remote):
            return False
        snapshot.validate(session)
        guard = session._write_guard

        def verify(cancelled):
            if not verify_capture(baseline, cancelled=cancelled) or not verify_capture(remote, cancelled=cancelled):
                raise ValueError("来源或原始版本已变化，请重新比较。")
            if guard is not None:
                guard.check_current()
            return True

        if not _read_in_background(parent, session, verify):
            return False
        applied = snapshot.apply_verified(session, candidates, baseline, remote)
        return applied
    except (ValueError, OSError) as exc:
        if not session._closed:
            QMessageBox.warning(parent, "来源修复未应用", str(exc))
        return False
    finally:
        session.resume_writes((pending[0] or applied, pending[1] or (applied and session._compile_authorized)))
