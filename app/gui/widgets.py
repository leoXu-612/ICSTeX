from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from app.gui.theme import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_PRESSED,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    ui_font,
)


class AutoCompileToggle(QAbstractButton):
    """Small accessible switch that avoids platform-native checkbox skins."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("autoCompileToggle")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("自动编译")
        self.setMinimumWidth(78)
        self.setFixedHeight(30)

    def sizeHint(self) -> QSize:
        return QSize(82, 30)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = QRectF(4, 7, 30, 16)
        if self.isChecked():
            track_color = QColor(COLOR_ACCENT)
        elif self.underMouse():
            track_color = QColor(COLOR_BORDER).darker(108)
        else:
            track_color = QColor(COLOR_PRESSED)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 8, 8)

        knob_x = 20 if self.isChecked() else 6
        painter.setBrush(QColor(COLOR_SURFACE))
        painter.drawEllipse(QRectF(knob_x, 9, 12, 12))

        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(COLOR_ACCENT), 1))
            painter.drawRoundedRect(QRectF(1, 2, self.width() - 2, self.height() - 4), 5, 5)

        painter.setFont(ui_font(11))
        painter.setPen(QColor(COLOR_TEXT if self.isChecked() else COLOR_TEXT_MUTED))
        painter.drawText(
            QRectF(40, 0, self.width() - 40, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "自动" if self.isChecked() else "手动",
        )
        painter.end()
