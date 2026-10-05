from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QAbstractButton, QWidget

from app.gui.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRESSED,
    COLOR_BORDER,
    COLOR_BORDER_SOFT,
    COLOR_PRESSED,
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_TEXT,
    COLOR_TEXT_FAINT,
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
        self.setText("自动编译")
        self._refresh_size()

    def set_mode_text(self, text: str) -> None:
        if self.text() != text:
            self.setText(text)
            self.setAccessibleName(text)
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

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def sizeHint(self) -> QSize:
        scale = self._scale()
        return QSize(round(52 * scale) + self.fontMetrics().horizontalAdvance(self.text()), round(32 * scale))

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = self._scale()
        painter.scale(scale, scale)

        track = QRectF(4, 8, 30, 16)
        if not self.isEnabled():
            track_top, track_bottom = COLOR_SURFACE_ALT, COLOR_BORDER_SOFT
            edge = COLOR_BORDER
        elif self.isChecked():
            track_top = COLOR_ACCENT_HOVER if self.underMouse() else COLOR_ACCENT
            track_bottom = COLOR_ACCENT_PRESSED if self.isDown() else COLOR_ACCENT_HOVER
            edge = COLOR_ACCENT_PRESSED if self.isDown() else COLOR_ACCENT_HOVER
        elif self.underMouse():
            track_top, track_bottom = COLOR_BORDER_SOFT, COLOR_BORDER
            edge = COLOR_TEXT_FAINT if self.isDown() else COLOR_BORDER
        else:
            track_top, track_bottom = COLOR_SURFACE_ALT, COLOR_PRESSED
            edge = COLOR_BORDER
        if self.isEnabled() and self.isDown():
            track_top = track_bottom
        track_fill = QLinearGradient(track.topLeft(), track.bottomLeft())
        track_fill.setColorAt(0, QColor(track_top))
        track_fill.setColorAt(1, QColor(track_bottom))
        painter.setPen(QPen(QColor(edge), 1))
        painter.setBrush(track_fill)
        painter.drawRoundedRect(track, 8, 8)

        knob_x = 20 if self.isChecked() else 6
        knob_fill = QLinearGradient(knob_x, 10, knob_x, 22)
        knob_fill.setColorAt(0, QColor(COLOR_SURFACE))
        knob_fill.setColorAt(1, QColor(COLOR_SURFACE_ALT if self.isEnabled() else COLOR_BORDER_SOFT))
        painter.setBrush(knob_fill)
        painter.setPen(QPen(QColor(COLOR_BORDER_SOFT), 0.6))
        painter.drawEllipse(QRectF(knob_x, 10, 12, 12))

        if self.isEnabled() and self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(COLOR_ACCENT), 1))
            painter.drawRoundedRect(QRectF(1, 2, self.width() / scale - 2, 28), 5, 5)

        painter.resetTransform()
        painter.setFont(self.font())
        text_color = COLOR_TEXT if self.isChecked() else COLOR_TEXT_MUTED
        painter.setPen(QColor(text_color if self.isEnabled() else COLOR_TEXT_FAINT))
        painter.drawText(
            QRectF(40 * scale, 0, self.width() - 40 * scale, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.text(),
        )
        painter.end()
