"""In-workspace editing of exact source ranges, not a second saved document."""
from __future__ import annotations

import html
from dataclasses import replace

from PySide6.QtCore import QEvent, QRegularExpression, QSignalBlocker, Qt
from PySide6.QtGui import QKeySequence, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSplitter, QStackedWidget,
    QStyledItemDelegate, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from app.core.document_structure import (
    SourceEdit, plain_fragment, plain_fragment_source, readable_text, table_cell_ranges,
)
from app.core.table_clipboard import parse_grid
from app.core.source_table import change_source_table, read_source_table
from app.core.blocks.latex_escape import escape_latex
from app.gui.latex_editor import LaTeXEditor
from app.gui.table_grid import TableGrid
from app.gui.table_options import TableOptions
from app.gui.theme import ui_font


class _CellDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            panel = self.parent()
            editor.installEventFilter(panel)
            row, column = index.row(), index.column()
            # Write on actual typing, not on focus loss: Save must see this edit.
            editor.textEdited.connect(lambda text: panel.edit_cell(row, column, text))
        return editor


class SourceBlockEditor(QScrollArea):
    """GUI-thread live adapter. Any unrelated source mutation ends the binding.

    Each accepted edit immediately enters the original document and undo stack.
    There is no unapplied draft for Save/Compile/Close to accidentally omit.
    """
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.key = None
        self.writing = False
        self.source = ""
        self.ranges = []
        self.plain = []
        self.setObjectName("localBlockEditor")
        # QStackedLayout includes hidden pages' minimum sizes. A native scroll
        # area keeps this form from limiting the source/console splitter, and
        # keeps its controls reachable when the user makes the workspace short.
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 8, 16, 12)
        row = QHBoxLayout()
        back = QPushButton("← 返回文稿")
        back.clicked.connect(controller.leave_local_editor)
        row.addWidget(back)
        for label, callback in (("撤销", controller.undo_source), ("重做", lambda: controller.undo_source(redo=True))):
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        row.addStretch()
        row.addWidget(QLabel("修改即时写入文稿 · 可撤销"))
        layout.addLayout(row)
        self.help = QLabel()
        self.help.setWordWrap(True)
        layout.addWidget(self.help)
        self.table_options = TableOptions(self)
        label_pattern = QRegularExpression(r"[\w:./-]*")
        label_pattern.setPatternOptions(QRegularExpression.PatternOption.UseUnicodePropertiesOption)
        self.table_options.label_edit.setValidator(QRegularExpressionValidator(label_pattern))
        self.table_options.changed.connect(self.change_specs)
        layout.addWidget(self.table_options)
        self.table_actions = QWidget()
        actions = QHBoxLayout(self.table_actions)
        actions.setContentsMargins(0, 0, 0, 0)
        for label, callback in (("清空所选", self.clear_cells),
                                ("粘贴数据", lambda: self.paste_cells(QApplication.clipboard().text()))):
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        actions.addStretch()
        layout.addWidget(self.table_actions)
        split = QSplitter(Qt.Orientation.Vertical)
        self.inputs = QStackedWidget()
        self.text = LaTeXEditor()
        self.text.setAccessibleName("当前块内容")
        self.text.sourceTextChanged.connect(self.edit_text)
        self.text.installEventFilter(self)
        self.table = TableGrid()
        self.table.setItemDelegate(_CellDelegate(self))
        self.table.itemChanged.connect(lambda item: self.edit_cell(item.row(), item.column(), item.text()))
        self.table.clearRequested.connect(self.clear_cells)
        self.table.pasteRequested.connect(self.paste_cells)
        self.table.undoRequested.connect(controller.undo_source)
        self.table.redoRequested.connect(lambda: controller.undo_source(redo=True))
        self.inputs.addWidget(self.text)
        self.inputs.addWidget(self.table)
        split.addWidget(self.inputs)
        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(0, 8, 0, 0)
        preview_layout.addWidget(QLabel("当前块内容示意 · 最终排版请看右侧 PDF"))
        self.preview = QTextBrowser()
        self.preview.setAccessibleName("当前块内容示意")
        self.preview.setOpenLinks(False)
        self.preview.setOpenExternalLinks(False)
        self.preview.setFont(ui_font(13))
        self.preview.setStyleSheet("QTextBrowser { background: #fffefa; border: 1px solid #d6dad6; padding: 14px; }")
        preview_layout.addWidget(self.preview)
        split.addWidget(preview)
        split.setSizes([360, 220])
        layout.addWidget(split, 1)

    def eventFilter(self, watched, event):
        if event.type() in {QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress}:
            undo = event.matches(QKeySequence.StandardKey.Undo)
            redo = event.matches(QKeySequence.StandardKey.Redo)
            if undo or redo:
                if event.type() == QEvent.Type.KeyPress:
                    self.controller.undo_source(redo=redo)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def bind(self, source, block, key, *, focus=True):
        self.block = block
        self.source, self.key = source, key
        cells = table_cell_ranges(source, block) if block.kind == "table" else ()
        self.is_table = bool(cells)
        self.table_actions.setVisible(self.is_table)
        self._table_model = read_source_table(source, block) if cells else None
        self.table_options.setVisible(self._table_model is not None)
        self.table_options.setEnabled(self._table_model is not None)
        if self._table_model:
            model = self._table_model
            caption = plain_fragment(model.spec.caption)
            self.table_options.load(replace(model.spec, caption=model.spec.caption if caption is None else caption))
            self.table_options.caption_edit.setReadOnly(caption is None)
            self.table_options.caption_edit.setToolTip("此题注含格式命令，请用编辑代码修改。" if caption is None else "直接输入题注文字，特殊字符自动处理。")
            for widget in (self.table_options.caption_edit, self.table_options.label_edit, self.table_options.placement_combo):
                widget.setEnabled(model.metadata_insert is not None)
            self.table_options.setToolTip("")
        elif cells:
            self.table_options.setToolTip("此表含复杂列、注释或行规则，或超出 40 行数据 / 12 列；保留单元格编辑，规格请用代码修改。")
        self.columns = len(cells[0]) if cells else 1
        if cells:
            self.ranges = [span for row in cells for span in row]
        else:
            start, end = block.argument or (block.start, block.end)
            fragment = source[start:end]
            # Whitespace surrounding a paragraph is document structure, not content.
            if block.kind == "text":
                start += len(fragment) - len(fragment.lstrip())
                end = max(start, end - len(fragment) + len(fragment.rstrip()))
            self.ranges = [(start, end)]
        values = [source[a:b] for a, b in self.ranges]
        decoded = [plain_fragment(value) for value in values]
        self.plain = [value is not None for value in decoded]
        values = [raw if value is None else value for raw, value in zip(values, decoded)]
        with QSignalBlocker(self.text), QSignalBlocker(self.table):
            if cells:
                current = self.table.currentRow(), self.table.currentColumn()
                if focus:
                    self.table.clear()
                self.table.setRowCount(len(cells))
                self.table.setColumnCount(self.columns)
                self.table.setHorizontalHeaderLabels([str(i + 1) for i in range(self.columns)])
                self.table.setVerticalHeaderLabels(["表头", *[str(i) for i in range(1, len(cells))]])
                for index, value in enumerate(values):
                    row, col = divmod(index, self.columns)
                    item = self.table.item(row, col)
                    if item is None:
                        item = QTableWidgetItem(value)
                        self.table.setItem(row, col, item)
                    elif item.text() != value:
                        item.setText(value)
                    item.setToolTip("直接输入文字" if self.plain[index] else "此格包含公式或格式命令；保留 LaTeX 写法。")
                if min(current) >= 0:
                    self.table.setCurrentCell(min(current[0], len(cells) - 1), min(current[1], self.columns - 1))
                self.inputs.setCurrentWidget(self.table)
                self.help.setText("双击单元格即可修改。普通文字自动处理特殊字符；带公式或格式的格子保留 LaTeX 写法。")
                if self._table_model is None:
                    self.help.setText("可直接改单元格。此表含特殊列、注释或行规则，或超出 40 行数据 / 12 列；规格请用“编辑代码”修改。")
            else:
                self.text.setPlainText(values[0])
                plain = self.plain[0]
                self.text.auto_pairs_enabled = self.text.auto_environment_enabled = not plain
                self.text.auto_item_enabled = self.text.snippets_enabled = not plain
                self.text.setFont(ui_font(14))
                self.inputs.setCurrentWidget(self.text)
                self.help.setText("直接写内容，Enter 换行，空一行另起一段。" if plain else
                                  "此块含 LaTeX 格式，保留原写法；换行请用 \\\\，空一行另起一段。")
                if block.kind == "table":
                    self.help.setText("此表包含合并单元格或复杂排版，暂用局部代码编辑；不会重排或丢弃原表。")
        self.refresh_preview()
        if focus:
            self.inputs.currentWidget().setFocus()

    def change_specs(self):
        """One original-source transaction, including any required local package."""
        if self.key is None or self._table_model is None:
            return
        try:
            # Re-read cell bytes after live typing, not the older options snapshot.
            model = read_source_table(self.source, self.block)
            if model is None:
                raise ValueError("当前表格结构已变化，请先补全代码后再调整规格。")
            changes = self.table_options.changes()
            changes["caption"] = (model.spec.caption if self.table_options.caption_edit.isReadOnly()
                                   else escape_latex(changes["caption"]))
            requested = replace(model.spec, **changes)
            removed = any(value for r, row in enumerate((model.spec.headers, *model.spec.cells))
                          for c, value in enumerate(row) if r > requested.rows or c >= requested.columns)
            if removed and QMessageBox.question(self, "缩小表格", "缩小后会移除范围外的数据；可以撤销。是否继续？",
                                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                self._reload_options()
                return
            edits = change_source_table(self.source, self.block, requested)
            if not edits:
                return
            self.writing = True
            self.controller.apply_local_edits(edits, source=self.source, key=self.key)
            start, end = self.block.start, self.block.end
            start += sum(len(e.text) - (e.end - e.start) for e in edits if e.end <= self.block.start)
            end += sum(len(e.text) - (e.end - e.start) for e in edits if e.start < self.block.end)
            self.controller._selection_offset = start
            self.bind(self.controller._editor.toPlainText(), replace(self.block, start=start, end=end),
                      self.controller._key(), focus=False)
        except ValueError as exc:
            self._reload_options()
            self.controller._notice(exc)
        finally:
            self.writing = False

    def _reload_options(self):
        if self.key is not None and self._table_model is not None:
            spec = self._table_model.spec
            caption = plain_fragment(spec.caption)
            self.table_options.load(replace(spec, caption=spec.caption if caption is None else caption))

    def edit_text(self):
        if self.key is not None and not self.is_table:
            self.write_values({0: self.text.toPlainText()})

    def edit_cell(self, row, column, text):
        if self.key is not None and self.is_table:
            self.write_values({row * self.columns + column: text})

    def write_values(self, values):
        if self.key is None:
            return
        edits = []
        for index, value in values.items():
            start, end = self.ranges[index]
            replacement = plain_fragment_source(value) if self.plain[index] else value
            if replacement != self.source[start:end]:
                edits.append(SourceEdit(start, end, replacement))
        if not edits:
            return
        self.writing = True
        try:
            self.controller.apply_local_edits(edits, source=self.source, key=self.key)
            for edit in sorted(edits, key=lambda edit: edit.start, reverse=True):
                delta = len(edit.text) - (edit.end - edit.start)
                self.ranges = [(a, a + len(edit.text)) if (a, b) == (edit.start, edit.end) else
                               (a + delta, b + delta) if a >= edit.end else (a, b)
                               for a, b in self.ranges]
                self.source = self.source[:edit.start] + edit.text + self.source[edit.end:]
                self.block = replace(self.block, end=self.block.end + delta)
            self.key = self.controller._key()
            if self.is_table:
                with QSignalBlocker(self.table):
                    for index, value in values.items():
                        self.table.item(index // self.columns, index % self.columns).setText(value)
            self.refresh_preview()
        except ValueError as exc:
            self.controller.leave_local_editor()
            self.controller._notice(exc)
        finally:
            self.writing = False

    def clear_cells(self):
        self.write_values({item.row() * self.columns + item.column(): "" for item in self.table.selectedItems()})

    def paste_cells(self, text):
        row, col = self.table.currentRow(), self.table.currentColumn()
        if row < 0 or col < 0:
            return
        try:
            rows = parse_grid(text, max_rows=self.table.rowCount() - row,
                              max_columns=self.columns - col)
            self.write_values({(row + r) * self.columns + col + c: value
                               for r, cells in enumerate(rows) for c, value in enumerate(cells)})
        except ValueError:
            self.controller._notice("粘贴范围超出当前表格；原内容未改动。")

    def refresh_preview(self):
        values = [html.escape(readable_text(self.source[a:b])).replace("\n", "<br>")
                  for a, b in self.ranges]
        if self.is_table:
            markup = '<table width="100%" cellpadding="7" border="1" cellspacing="0">'
            for start in range(0, min(len(values), self.columns * 12), self.columns):
                markup += "<tr>" + "".join("<td>" + value + "</td>" for value in values[start:start + self.columns]) + "</tr>"
            markup += "</table>"
            if self.table.rowCount() > 12:
                markup += "<p>仅示意前 12 行；上方表格可编辑全部内容。</p>"
        else:
            markup = '<div style="line-height:150%">' + values[0] + "</div>"
        self.preview.setHtml(markup)
