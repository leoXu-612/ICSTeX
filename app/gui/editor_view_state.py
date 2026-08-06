"""Pure helpers for capturing/restoring editor cursor & scroll state and jumping to lines."""
from __future__ import annotations

from PySide6.QtGui import QTextCursor

from app.gui.latex_editor import LaTeXEditor
from app.gui.main_window_support import EditorViewState


def capture(editor: LaTeXEditor) -> EditorViewState:
    return EditorViewState(
        cursor_position=editor.textCursor().position(),
        horizontal=editor.horizontalScrollBar().value(),
        vertical=editor.verticalScrollBar().value(),
    )


def restore(editor: LaTeXEditor, state: EditorViewState) -> None:
    cursor = editor.textCursor()
    cursor.setPosition(min(state.cursor_position, len(editor.toPlainText())))
    editor.setTextCursor(cursor)
    editor.horizontalScrollBar().setValue(state.horizontal)
    editor.verticalScrollBar().setValue(state.vertical)


def jump_to_line(editor: LaTeXEditor, line: int) -> None:
    cursor = QTextCursor(editor.document().findBlockByNumber(max(line - 1, 0)))
    editor.setTextCursor(cursor)
    editor.setFocus()


def jump_to_position(editor: LaTeXEditor, line: int, column: int) -> None:
    block = editor.document().findBlockByNumber(max(line - 1, 0))
    position = block.position() + max(column - 1, 0)
    cursor = QTextCursor(block)
    cursor.setPosition(min(position, block.position() + len(block.text())))
    editor.setTextCursor(cursor)
    editor.setFocus()
