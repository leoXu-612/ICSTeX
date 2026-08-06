from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

from app.gui.theme import (
    COLOR_SYNTAX_ARGUMENT,
    COLOR_SYNTAX_COMMAND,
    COLOR_SYNTAX_COMMENT,
    COLOR_SYNTAX_ENVIRONMENT,
    COLOR_SYNTAX_MATH,
    COLOR_SYNTAX_OPTION,
    COLOR_SYNTAX_REFERENCE,
)


@dataclass(frozen=True)
class HighlightRule:
    pattern: QRegularExpression
    style: QTextCharFormat


class LaTeXHighlighter(QSyntaxHighlighter):
    def __init__(self, document) -> None:  # type: ignore[no-untyped-def]
        super().__init__(document)
        self.rules = [
            HighlightRule(QRegularExpression(r"\\(?:label|ref|eqref|autoref|cite|parencite|textcite)\b"), _format(COLOR_SYNTAX_REFERENCE, bold=True)),
            HighlightRule(QRegularExpression(r"\\(?:begin|end)\s*\{[^{}]+\}"), _format(COLOR_SYNTAX_ENVIRONMENT, bold=True)),
            HighlightRule(QRegularExpression(r"\\[A-Za-z@]+\*?"), _format(COLOR_SYNTAX_COMMAND, bold=True)),
            HighlightRule(QRegularExpression(r"\\."), _format(COLOR_SYNTAX_COMMAND)),
            HighlightRule(QRegularExpression(r"\{[^{}]*\}"), _format(COLOR_SYNTAX_ARGUMENT)),
            HighlightRule(QRegularExpression(r"\[[^\[\]]*\]"), _format(COLOR_SYNTAX_OPTION)),
            HighlightRule(QRegularExpression(r"\$[^$]*\$|\$\$[^$]*\$\$|\\\[|\\\]|\\\(|\\\)"), _format(COLOR_SYNTAX_MATH)),
        ]
        self.comment_format = _format(COLOR_SYNTAX_COMMENT, italic=True)

    def highlightBlock(self, text: str) -> None:
        for rule in self.rules:
            iterator = rule.pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), rule.style)

        comment_start = _comment_start(text)
        if comment_start is not None:
            self.setFormat(comment_start, len(text) - comment_start, self.comment_format)


def _format(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


def _comment_start(text: str) -> int | None:
    escaped = False
    for index, char in enumerate(text):
        if char == "\\":
            escaped = not escaped
            continue
        if char == "%" and not escaped:
            return index
        escaped = False
    return None
