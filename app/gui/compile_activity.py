"""Indeterminate compile activity. It never estimates a completion percentage."""
import ctypes
from functools import lru_cache
import sys

from PySide6.QtCore import QElapsedTimer, QEvent, QRectF, QSize, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QApplication, QProgressBar

from app.gui.theme import COLOR_ACCENT, COLOR_HOVER


@lru_cache(maxsize=1)
def _workspace_reader():
    """Bind the documented AppKit accessibility preference, without changing it."""
    try:
        ctypes.CDLL('/System/Library/Frameworks/AppKit.framework/AppKit')
        objc = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(('objc_msgSend', objc))
        read = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(('objc_msgSend', objc))
        workspace = send(objc.objc_getClass(b'NSWorkspace'), objc.sel_registerName(b'sharedWorkspace'))
        selector = objc.sel_registerName(b'accessibilityDisplayShouldReduceMotion')
        return objc, read, workspace, selector
    except (OSError, AttributeError):
        return None


def system_reduces_motion() -> bool:
    if sys.platform != 'darwin' or QApplication.instance().platformName() != 'cocoa':
        return False
    reader = _workspace_reader()
    if reader is None:
        return True  # Prefer a static indicator if the native preference is unreadable.
    _runtime, read, workspace, selector = reader
    return not workspace or bool(read(workspace, selector))


class CompileActivityBar(QProgressBar):
    """A small flowing highlight; visibility remains owned by compile controllers."""
    def __init__(self, window):
        super().__init__(window)
        self.setObjectName('compileProgress')
        self.setRange(0, 0)
        self.setTextVisible(False)
        self.setAccessibleName('编译进行中')
        self.setAccessibleDescription('显示活动状态，不表示完成百分比。')
        self.setFixedWidth(112)
        self._window = window
        window.installEventFilter(self)
        self._motion_override = None
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)

    def sizeHint(self):
        return QSize(112, 12)

    def set_reduced_motion(self, reduce: bool | None):
        self._motion_override = reduce
        self._sync_animation()

    def _sync_animation(self):
        reduce = system_reduces_motion() if self._motion_override is None else self._motion_override
        animate = self.isVisible() and not self._window.isMinimized() and not reduce
        if animate and not self._timer.isActive():
            self._clock.start()
            self._timer.start()
        elif not animate:
            self._timer.stop()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_animation()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if event.type() in {QEvent.Type.WindowStateChange, QEvent.Type.WindowActivate}:
            self._sync_animation()
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(1, (self.height() - 7) / 2, self.width() - 2, 7)
        painter.setPen(QColor(COLOR_HOVER))
        painter.setBrush(QColor(COLOR_HOVER))
        painter.drawRoundedRect(track, 3.5, 3.5)
        phase = (self._clock.elapsed() % 1400) / 1400 if self._timer.isActive() else .5
        width = track.width() * .42
        x = track.left() - width + (track.width() + width) * phase
        gradient = QLinearGradient(x, 0, x + width, 0)
        for position, alpha in ((0, 0), (.35, 150), (.65, 255), (1, 0)):
            color = QColor(COLOR_ACCENT)
            color.setAlpha(alpha)
            gradient.setColorAt(position, color)
        painter.setClipRect(track)
        painter.fillRect(QRectF(x, track.top(), width, track.height()), gradient)
