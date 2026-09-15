from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QAbstractButton, QWidget

from app.gui.theme import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_PRESSED,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
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
        self._refresh_size()

    def _scale(self):
        manager = getattr(QApplication.instance(), "ui_scale_manager", None)
        return manager.scale if manager is not None else 1.0

    def _refresh_size(self):
        self.setFixedHeight(round(32 * self._scale()))
        self.setMinimumWidth(self.sizeHint().width())
        self.updateGeometry()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._refresh_size()

    def sizeHint(self) -> QSize:
        scale = self._scale()
        return QSize(round(52 * scale) + self.fontMetrics().horizontalAdvance("自动编译"), round(32 * scale))

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = self._scale()
        painter.scale(scale, scale)

        track = QRectF(4, 8, 30, 16)
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
        painter.drawEllipse(QRectF(knob_x, 10, 12, 12))

        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(COLOR_ACCENT), 1))
            painter.drawRoundedRect(QRectF(1, 2, self.width() / scale - 2, 28), 5, 5)

        painter.resetTransform()
        painter.setFont(self.font())
        painter.setPen(QColor(COLOR_TEXT if self.isChecked() else COLOR_TEXT_MUTED))
        painter.drawText(
            QRectF(40 * scale, 0, self.width() - 40 * scale, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "自动编译",
        )
        painter.end()
