from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QStringListModel, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDragMoveEvent, QDropEvent, QKeyEvent, QPainter, QTextCursor, QTextFormat, QTextOption
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QWidget

from app.core.latex_completion import CompletionCandidate, completion_context
from app.core.editor_assist import (
    enter_assist,
    environment_completion_for_line,
    snippet_for_trigger,
    trigger_before_cursor,
)
from app.gui.latex_highlighter import LaTeXHighlighter
from app.gui.theme import COLOR_CURRENT_LINE, COLOR_GUTTER, COLOR_TEXT, COLOR_TEXT_FAINT


PAIR_CHARS = {
    "{": "}",
    "[": "]",
    "(": ")",
    "$": "$",
}
CLOSING_CHARS = set(PAIR_CHARS.values())
IMAGE_DROP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg"}


class LineNumberArea(QWidget):
    def __init__(self, editor: "LaTeXEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.editor.line_number_area_paint_event(event)


class LaTeXEditor(QPlainTextEdit):
    imageDropped = Signal(list)

    def __init__(self, text: str = "") -> None:
        super().__init__()
        self.auto_item_enabled = True
        self.auto_environment_enabled = True
        self.auto_pairs_enabled = True
        self.snippets_enabled = True
        self.soft_wrap_enabled = True
        self._current_line_selection: QTextEdit.ExtraSelection | None = None
        self._search_selections: list[QTextEdit.ExtraSelection] = []
        self._completion_labels: list[str] = []
        self._completion_citations: list[str] = []
        self._completion_candidates: dict[str, CompletionCandidate] = {}
        self._completion_replacement_length = 0

        self.setAcceptDrops(True)
        self.set_soft_wrap_enabled(True)
        self.line_number_area = LineNumberArea(self)
        self.highlighter = LaTeXHighlighter(self.document())
        self._completion_model = QStringListModel(self)
        self._completer = QCompleter(self._completion_model, self)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        self._completer.activated[str].connect(self._insert_completion)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()
        if text:
            self.setPlainText(text)

    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 18 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _new_block_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        contents = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(contents.left(), contents.top(), self.line_number_area_width(), contents.height())
        )

    def line_number_area_paint_event(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(COLOR_GUTTER))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        current_block = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor(COLOR_TEXT if block_number == current_block else COLOR_TEXT_FAINT))
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self) -> None:
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(COLOR_CURRENT_LINE))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self._current_line_selection = selection
        self._refresh_extra_selections()

    def set_search_selections(self, selections: list[QTextEdit.ExtraSelection]) -> None:
        self._search_selections = selections
        self._refresh_extra_selections()

    def set_completion_context(self, *, labels: list[str], citations: list[str]) -> None:
        self._completion_labels = labels
        self._completion_citations = citations

    def _refresh_extra_selections(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        if self._current_line_selection is not None:
            selections.append(self._current_line_selection)
        selections.extend(self._search_selections)
        self.setExtraSelections(selections)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._completer.popup().isVisible():
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                completion = self._selected_completion()
                if completion:
                    self._insert_completion(completion)
                self._completer.popup().hide()
                return
            if event.key() == Qt.Key.Key_Escape:
                self._completer.popup().hide()
                return

        if event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        ):
            super().keyPressEvent(event)
            return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._handle_enter():
            self._completer.popup().hide()
            return

        if event.key() == Qt.Key.Key_Tab and self._handle_tab():
            self._completer.popup().hide()
            return

        text = event.text()
        if self.auto_pairs_enabled and text:
            if text in CLOSING_CHARS and self._handle_closing_pair(text):
                if text == "}" and self.auto_environment_enabled:
                    self._complete_environment_if_needed()
                self._show_completion_if_available()
                return
            if text in PAIR_CHARS and self._handle_open_pair(text):
                self._show_completion_if_available()
                return

        super().keyPressEvent(event)

        if text == "}" and self.auto_environment_enabled:
            self._complete_environment_if_needed()
        self._show_completion_if_available()

    def insert_latex_snippet(self, text: str, cursor_offset: int | None = None) -> None:
        cursor = self.textCursor()
        start_position = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        cursor.insertText(text)
        if cursor_offset is not None:
            cursor.setPosition(start_position + cursor_offset)
        self.setTextCursor(cursor)

    def set_soft_wrap_enabled(self, enabled: bool) -> None:
        self.soft_wrap_enabled = enabled
        if enabled:
            # QPlainTextEdit can retain a stale horizontal layout after
            # setPlainText(), which insertion tools use while adding packages.
            # Toggle the mode to force Qt to recompute wrapping immediately.
            self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.horizontalScrollBar().setValue(0)
            self.viewport().update()
        else:
            self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._image_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._image_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        image_paths = self._image_paths_from_mime(event.mimeData())
        if image_paths:
            self.imageDropped.emit(image_paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def _image_paths_from_mime(self, mime_data) -> list[str]:  # type: ignore[no-untyped-def]
        paths: list[str] = []
        if not mime_data.hasUrls():
            return paths
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() in IMAGE_DROP_EXTENSIONS:
                paths.append(str(path))
        return paths

    def _handle_enter(self) -> bool:
        if not self.auto_item_enabled:
            return False
        cursor = self.textCursor()
        assist = enter_assist(self._text_before_cursor())
        if assist is None:
            return False

        cursor.beginEditBlock()
        if assist.replace_current_line:
            block = cursor.block()
            cursor.setPosition(block.position())
            cursor.setPosition(block.position() + len(block.text()), QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(assist.replacement)
        else:
            cursor.insertText(assist.replacement)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        return True

    def _handle_tab(self) -> bool:
        if not self.snippets_enabled:
            return False

        cursor = self.textCursor()
        trigger = trigger_before_cursor(self._text_before_cursor())
        if not trigger:
            return False

        snippet = snippet_for_trigger(trigger)
        if snippet is None:
            return False

        start = cursor.position() - len(trigger)
        cursor.beginEditBlock()
        cursor.setPosition(start)
        cursor.setPosition(start + len(trigger), QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(snippet.text)
        cursor.setPosition(start + snippet.cursor_offset)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        return True

    def _handle_open_pair(self, opener: str) -> bool:
        closer = PAIR_CHARS[opener]
        cursor = self.textCursor()
        if cursor.hasSelection():
            selected = cursor.selectedText()
            cursor.insertText(f"{opener}{selected}{closer}")
            self.setTextCursor(cursor)
            return True

        cursor.insertText(opener + closer)
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        self.setTextCursor(cursor)
        return True

    def _handle_closing_pair(self, closer: str) -> bool:
        cursor = self.textCursor()
        plain = self.toPlainText()
        if cursor.position() < len(plain) and plain[cursor.position()] == closer:
            cursor.movePosition(QTextCursor.MoveOperation.Right)
            self.setTextCursor(cursor)
            return True
        return False

    def _complete_environment_if_needed(self) -> None:
        cursor = self.textCursor()
        block = cursor.block()
        line_to_cursor = block.text()[: cursor.position() - block.position()]
        if line_to_cursor != block.text():
            return

        completion = environment_completion_for_line(line_to_cursor)
        if completion is None:
            return

        start = cursor.position()
        cursor.insertText(completion.insertion)
        cursor.setPosition(start + completion.cursor_offset)
        self.setTextCursor(cursor)

    def _text_before_cursor(self) -> str:
        cursor = self.textCursor()
        return self.toPlainText()[: cursor.position()]

    def _show_completion_if_available(self) -> None:
        context = completion_context(
            self._text_before_cursor(),
            labels=self._completion_labels,
            citations=self._completion_citations,
        )
        if context is None:
            self._completer.popup().hide()
            return

        self._completion_replacement_length = context.replacement_length
        self._completion_candidates = {candidate.display: candidate for candidate in context.candidates}
        self._completion_model.setStringList(list(self._completion_candidates))
        cursor_rect = self.cursorRect()
        cursor_rect.setWidth(max(260, self._completer.popup().sizeHintForColumn(0) + 20))
        self._completer.complete(cursor_rect)

    def _selected_completion(self) -> str:
        """Return the row highlighted in the popup, not QCompleter's stale row."""
        index = self._completer.popup().currentIndex()
        if index.isValid():
            selected = index.data(Qt.ItemDataRole.DisplayRole)
            if isinstance(selected, str) and selected:
                return selected
        return self._completer.currentCompletion()

    def _insert_completion(self, display: str) -> None:
        candidate = self._completion_candidates.get(display)
        if candidate is None:
            return
        cursor = self.textCursor()
        start = max(0, cursor.position() - self._completion_replacement_length)
        cursor.beginEditBlock()
        cursor.setPosition(start)
        cursor.setPosition(start + self._completion_replacement_length, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(candidate.insertion)
        cursor.setPosition(start + candidate.cursor_offset)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
