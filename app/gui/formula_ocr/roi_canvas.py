"""Draggable ROI selection canvas for multi-line formula images."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget


class RoiCanvas(QWidget):
    rois_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._rois: list[QRect] = []
        self._current: QRect | None = None
        self._drag_start: QPoint | None = None
        self.setMinimumSize(320, 200)
        self.setMouseTracking(True)

    def set_image(self, image: QImage) -> None:
        self._image = image
        self._rois = []
        self._current = None
        self.update()

    def set_rois(self, rois: list[QRect]) -> None:
        self._rois = list(rois)
        self.update()
        self.rois_changed.emit()

    def rois(self) -> list[QRect]:
        return list(self._rois)

    def add_rect(self, rect: QRect) -> None:
        if rect.width() < 8 or rect.height() < 8:
            return
        self._rois.append(rect)
        self.update()
        self.rois_changed.emit()

    def clear(self) -> None:
        self._rois = []
        self.update()
        self.rois_changed.emit()

    def _scale(self) -> float:
        if self._image is None or self._image.isNull():
            return 1.0
        return min(self.width() / self._image.width(), self.height() / self._image.height(), 3.0)

    def _image_origin(self) -> QPoint:
        if self._image is None:
            return QPoint(0, 0)
        scale = self._scale()
        x = (self.width() - int(self._image.width() * scale)) // 2
        y = (self.height() - int(self._image.height() * scale)) // 2
        return QPoint(max(0, x), max(0, y))

    def _to_image(self, point: QPoint) -> QPoint:
        scale = self._scale()
        origin = self._image_origin()
        return QPoint(int((point.x() - origin.x()) / scale), int((point.y() - origin.y()) / scale))

    def mousePressEvent(self, event) -> None:
        if self._image is None:
            return
        point = self._to_image(event.position().toPoint())
        for index, rect in enumerate(self._rois):
            if rect.contains(point):
                del self._rois[index]
                self.update()
                self.rois_changed.emit()
                return
        self._drag_start = point
        self._current = QRect(point, QSize(0, 0))

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None:
            return
        point = self._to_image(event.position().toPoint())
        self._current = QRect(self._drag_start, point).normalized()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_start is not None and self._current is not None:
            self.add_rect(self._current)
        self._drag_start = None
        self._current = None

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f4f4f2"))
        if self._image is None or self._image.isNull():
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "（无图片）")
            return
        scale = self._scale()
        origin = self._image_origin()
        painter.drawImage(QRect(origin, QSize(int(self._image.width() * scale), int(self._image.height() * scale))), self._image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for index, rect in enumerate(self._rois):
            widget_rect = QRect(
                origin.x() + int(rect.x() * scale),
                origin.y() + int(rect.y() * scale),
                int(rect.width() * scale),
                int(rect.height() * scale),
            )
            painter.setPen(QPen(QColor("#b45309"), 2))
            painter.drawRect(widget_rect)
            painter.setBrush(QColor("#b45309"))
            painter.drawText(widget_rect.topLeft() + QPoint(4, 14), str(index + 1))
        if self._current is not None:
            rect = self._current
            widget_rect = QRect(
                origin.x() + int(rect.x() * scale),
                origin.y() + int(rect.y() * scale),
                int(rect.width() * scale),
                int(rect.height() * scale),
            )
            painter.setPen(QPen(QColor("#3478c4"), 1, Qt.PenStyle.DashLine))
            painter.drawRect(widget_rect)
        painter.end()
