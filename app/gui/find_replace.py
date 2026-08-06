from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCursor, QTextFormat
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QWidget

from app.core.search import SearchMatch, SearchOptions, find_matches, replace_all
from app.gui.latex_editor import LaTeXEditor


class FindReplaceBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor: LaTeXEditor | None = None
        self.matches: list[SearchMatch] = []
        self.current_index = -1
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("查找")
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("替换为")
        self.status_label = QLabel("无匹配")
        self.case_check = QCheckBox("区分大小写")
        self.word_check = QCheckBox("全词")
        self.prev_button = QPushButton("上一个")
        self.next_button = QPushButton("下一个")
        self.replace_button = QPushButton("替换")
        self.replace_all_button = QPushButton("全部替换")
        self.close_button = QPushButton("关闭")
        self._build()
        self._connect()
        self.hide()

    def set_editor(self, editor: LaTeXEditor | None) -> None:
        if self.editor is not None:
            self.editor.set_search_selections([])
        self.editor = editor
        self.update_matches()

    def show_find(self) -> None:
        self._set_replace_visible(False)
        self.show()
        self.find_edit.setFocus()
        self.find_edit.selectAll()
        self.update_matches()

    def show_replace(self) -> None:
        self._set_replace_visible(True)
        self.show()
        self.find_edit.setFocus()
        self.find_edit.selectAll()
        self.update_matches()

    def update_matches(self) -> None:
        if self.editor is None:
            self.matches = []
            self.current_index = -1
            self.status_label.setText("无编辑器")
            return
        self.matches = find_matches(self.editor.toPlainText(), self.find_edit.text(), self._options())
        self.current_index = self._nearest_match_index()
        self._apply_highlights()
        self._update_status()

    def find_next(self) -> None:
        if not self.matches:
            self.update_matches()
            return
        self.current_index = 0 if self.current_index < 0 else (self.current_index + 1) % len(self.matches)
        self._select_current()

    def find_previous(self) -> None:
        if not self.matches:
            self.update_matches()
            return
        self.current_index = len(self.matches) - 1 if self.current_index < 0 else (self.current_index - 1) % len(self.matches)
        self._select_current()

    def replace_current(self) -> None:
        if self.editor is None:
            return
        self.update_matches()
        if self.current_index < 0:
            return
        match = self.matches[self.current_index]
        cursor = self.editor.textCursor()
        cursor.setPosition(match.start)
        cursor.setPosition(match.end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(self.replace_edit.text())
        self.editor.setTextCursor(cursor)
        self.update_matches()

    def replace_all_matches(self) -> None:
        if self.editor is None:
            return
        new_text, count = replace_all(self.editor.toPlainText(), self.find_edit.text(), self.replace_edit.text(), self._options())
        if count == 0:
            self.update_matches()
            return
        cursor_position = min(self.editor.textCursor().position(), len(new_text))
        self.editor.setPlainText(new_text)
        cursor = self.editor.textCursor()
        cursor.setPosition(cursor_position)
        self.editor.setTextCursor(cursor)
        self.update_matches()
        self.status_label.setText(f"已替换 {count} 处")

    def close_bar(self) -> None:
        if self.editor is not None:
            self.editor.set_search_selections([])
        self.hide()

    def keyPressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key() == Qt.Key.Key_Escape:
            self.close_bar()
            return
        super().keyPressEvent(event)

    def _build(self) -> None:
        self.setObjectName("findReplaceBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        layout.addWidget(QLabel("查找"))
        layout.addWidget(self.find_edit, 2)
        layout.addWidget(self.replace_edit, 2)
        layout.addWidget(self.case_check)
        layout.addWidget(self.word_check)
        layout.addWidget(self.prev_button)
        layout.addWidget(self.next_button)
        layout.addWidget(self.replace_button)
        layout.addWidget(self.replace_all_button)
        layout.addWidget(self.status_label)
        layout.addWidget(self.close_button)

    def _connect(self) -> None:
        self.find_edit.textChanged.connect(self.update_matches)
        self.case_check.toggled.connect(self.update_matches)
        self.word_check.toggled.connect(self.update_matches)
        self.prev_button.clicked.connect(self.find_previous)
        self.next_button.clicked.connect(self.find_next)
        self.replace_button.clicked.connect(self.replace_current)
        self.replace_all_button.clicked.connect(self.replace_all_matches)
        self.close_button.clicked.connect(self.close_bar)

    def _set_replace_visible(self, visible: bool) -> None:
        self.replace_edit.setVisible(visible)
        self.replace_button.setVisible(visible)
        self.replace_all_button.setVisible(visible)

    def _options(self) -> SearchOptions:
        return SearchOptions(case_sensitive=self.case_check.isChecked(), whole_word=self.word_check.isChecked())

    def _nearest_match_index(self) -> int:
        if self.editor is None or not self.matches:
            return -1
        position = self.editor.textCursor().position()
        for index, match in enumerate(self.matches):
            if match.start <= position <= match.end or match.start >= position:
                return index
        return 0

    def _select_current(self) -> None:
        if self.editor is None or self.current_index < 0:
            return
        match = self.matches[self.current_index]
        cursor = self.editor.textCursor()
        cursor.setPosition(match.start)
        cursor.setPosition(match.end, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()
        self._apply_highlights()
        self._update_status()

    def _apply_highlights(self) -> None:
        if self.editor is None:
            return
        selections: list[QTextEdit.ExtraSelection] = []
        for index, match in enumerate(self.matches):
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#d8c985" if index == self.current_index else "#eee3ad"))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, False)
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(match.start)
            cursor.setPosition(match.end, QTextCursor.MoveMode.KeepAnchor)
            selection.cursor = cursor
            selections.append(selection)
        self.editor.set_search_selections(selections)

    def _update_status(self) -> None:
        if not self.find_edit.text():
            self.status_label.setText("输入关键词")
        elif not self.matches:
            self.status_label.setText("无匹配")
        else:
            self.status_label.setText(f"第 {self.current_index + 1} / {len(self.matches)} 个匹配")
