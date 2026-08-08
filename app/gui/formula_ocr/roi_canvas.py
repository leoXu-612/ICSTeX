"""Draggable ROI canvas: borders only, Shift+drag to create, drag to move,
corner handles to resize, Delete to remove, click to select."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


_HANDLE = 7


class RoiCanvas(QWidget):
    rois_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._rois: list[QRect] = []
        self._selected: int | None = None
        self._drag: dict | None = None
        self.setMinimumSize(320, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # --- public API ------------------------------------------------------
    def set_image(self, image: QImage) -> None:
        self._image = image
        self._rois = []
        self._selected = None
        self._drag = None
        self.update()

    def set_rois(self, rois: list[QRect]) -> None:
        self._rois = list(rois)
        self._selected = None
        self.update()
        self.rois_changed.emit()

    def rois(self) -> list[QRect]:
        return list(self._rois)

    def add_rect(self, rect: QRect) -> None:
        if rect.width() < 8 or rect.height() < 8:
            return
        self._rois.append(rect)
        self._selected = len(self._rois) - 1
        self.update()
        self.rois_changed.emit()

    def select_roi(self, index: int) -> None:
        if 0 <= index < len(self._rois):
            self._selected = index
            self.update()

    def selected_index(self) -> int | None:
        """Public accessor for the selected ROI index (None when none)."""

        return self._selected

    def delete_selected(self) -> None:
        if self._selected is None:
            return
        del self._rois[self._selected]
        self._selected = None
        self.update()
        self.rois_changed.emit()

    def clear(self) -> None:
        self._rois = []
        self._selected = None
        self.update()
        self.rois_changed.emit()

    # --- geometry --------------------------------------------------------
    def _scale(self) -> float:
        if self._image is None or self._image.isNull():
            return 1.0
        return min(self.width() / self._image.width(), self.height() / self._image.height(), 3.0)

    def _origin(self) -> QPoint:
        if self._image is None:
            return QPoint(0, 0)
        scale = self._scale()
        return QPoint(max(0, (self.width() - int(self._image.width() * scale)) // 2), max(0, (self.height() - int(self._image.height() * scale)) // 2))

    def _to_image(self, point: QPoint) -> QPoint:
        scale = self._scale()
        origin = self._origin()
        return QPoint(int((point.x() - origin.x()) / scale), int((point.y() - origin.y()) / scale))

    def _to_widget(self, rect: QRect) -> QRect:
        scale = self._scale()
        origin = self._origin()
        return QRect(
            origin.x() + int(rect.x() * scale),
            origin.y() + int(rect.y() * scale),
            int(rect.width() * scale),
            int(rect.height() * scale),
        )

    def _hit_roi(self, point: QPoint) -> int:
        for index in range(len(self._rois) - 1, -1, -1):
            if self._rois[index].contains(point):
                return index
        return -1

    def _handle_at(self, point: QPoint) -> str | None:
        if self._selected is None:
            return None
        rect = self._rois[self._selected]
        scale = self._scale()
        half = max(2, int(_HANDLE / 2))
        origin = self._origin()
        handles = {
            "tl": (rect.left(), rect.top()),
            "tr": (rect.right(), rect.top()),
            "bl": (rect.left(), rect.bottom()),
            "br": (rect.right(), rect.bottom()),
            "t": (rect.center().x(), rect.top()),
            "b": (rect.center().x(), rect.bottom()),
            "l": (rect.left(), rect.center().y()),
            "r": (rect.right(), rect.center().y()),
        }
        for handle, (x, y) in handles.items():
            widget = QPoint(origin.x() + int(x * scale), origin.y() + int(y * scale))
            if abs(point.x() - widget.x()) <= half and abs(point.y() - widget.y()) <= half:
                return handle
        return None

    # --- interaction -----------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._image is None:
            return
        point = self._to_image(event.position().toPoint())
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._drag = {"mode": "draw", "start": point, "current": QRect(point, QSize(0, 0))}
            return
        handle = self._handle_at(event.position().toPoint())
        index = self._hit_roi(point)
        if index >= 0:
            self._selected = index
            if handle:
                self._drag = {"mode": "resize", "index": index, "handle": handle, "start_rect": self._rois[index]}
            else:
                self._drag = {"mode": "move", "index": index, "start": point, "start_rect": self._rois[index]}
            self.update()
            return
        self._selected = None
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag is None:
            return
        point = self._to_image(event.position().toPoint())
        drag = self._drag
        if drag["mode"] == "draw":
            drag["current"] = QRect(drag["start"], point).normalized()
        elif drag["mode"] == "move":
            delta = point - drag["start"]
            drag["current"] = drag["start_rect"].translated(delta)
        elif drag["mode"] == "resize":
            rect = QRect(drag["start_rect"])
            handle = drag["handle"]
            if "l" in handle:
                rect.setLeft(point.x())
            if "r" in handle:
                rect.setRight(point.x())
            if "t" in handle:
                rect.setTop(point.y())
            if "b" in handle:
                rect.setBottom(point.y())
            drag["current"] = rect.normalized()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag is None:
            return
        drag = self._drag
        self._drag = None
        if drag["mode"] == "draw":
            self.add_rect(drag["current"])
        elif drag["mode"] in ("move", "resize"):
            index = drag["index"]
            if 0 <= index < len(self._rois):
                updated = drag.get("current", drag.get("start_rect"))
                if updated != self._rois[index]:
                    self._rois[index] = updated
                    self.rois_changed.emit()
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
            event.accept()
            return
        super().keyPressEvent(event)

    # --- paint -----------------------------------------------------------
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f4f4f2"))
        if self._image is None or self._image.isNull():
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "（无图片）")
            return
        scale = self._scale()
        origin = self._origin()
        painter.drawImage(
            QRect(origin, QSize(int(self._image.width() * scale), int(self._image.height() * scale))),
            self._image,
        )
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for index, rect in enumerate(self._rois):
            widget_rect = self._to_widget(rect)
            selected = index == self._selected
            painter.setPen(QPen(QColor("#b45309") if selected else QColor("#7a7a74"), 2 if selected else 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(widget_rect)
            painter.setPen(QPen(QColor("#b45309"), 1))
            painter.drawText(widget_rect.topLeft() + QPoint(4, -4), str(index + 1))
            if selected:
                painter.setPen(QPen(QColor("#b45309"), 1))
                painter.setBrush(QColor("#b45309"))
                handles = {
                    "tl": (widget_rect.left(), widget_rect.top()),
                    "tr": (widget_rect.right(), widget_rect.top()),
                    "bl": (widget_rect.left(), widget_rect.bottom()),
                    "br": (widget_rect.right(), widget_rect.bottom()),
                    "t": (widget_rect.center().x(), widget_rect.top()),
                    "b": (widget_rect.center().x(), widget_rect.bottom()),
                    "l": (widget_rect.left(), widget_rect.center().y()),
                    "r": (widget_rect.right(), widget_rect.center().y()),
                }
                for x, y in handles.values():
                    painter.drawRect(QRect(x - _HANDLE // 2, y - _HANDLE // 2, _HANDLE, _HANDLE))
        drag = self._drag
        if drag is not None and "current" in drag:
            widget_rect = self._to_widget(drag["current"])
            painter.setPen(QPen(QColor("#3478c4"), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(widget_rect)
        painter.end()
