"""Temporary, version-scoped protection for the verified Qt Cocoa AX crash.

Only the selected-children attribute is unavailable under this mitigation. This
is NOT full accessibility acceptance or a repair of Qt's stale interface cache.
Other AX attributes/actions remain installed. Reassess when changing Qt/macOS.
"""
from __future__ import annotations

import ctypes
import logging
import platform
import sys

from PySide6.QtCore import QThread, qVersion
from PySide6.QtWidgets import QApplication

_log = logging.getLogger(__name__)
_callback = None
_original = None
_runtime = None


def _affected_runtime(app):
    return (sys.platform == "darwin" and platform.mac_ver()[0].split(".")[0] == "26"
            and platform.machine() == "arm64" and qVersion() == "6.11.1"
            and app.platformName() == "cocoa")


def install_selected_children_guard():
    """Call on the GUI thread after QApplication, before creating editor UI.

    Local crash: libqcocoa + 0x87794 inside accessibilitySelectedChildren
    (method starts at 0x876bc), following a stale selectedChild->isValid call.
    No binary, system setting or other process is changed.
    """
    global _callback, _original, _runtime
    app = QApplication.instance()
    if app is None or not _affected_runtime(app):
        return False
    if QThread.currentThread() != app.thread():
        raise RuntimeError("Cocoa accessibility protection requires the GUI thread")
    if _callback is not None:
        return True
    try:
        objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.class_getInstanceMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        objc.class_getInstanceMethod.restype = ctypes.c_void_p
        objc.method_getTypeEncoding.argtypes = [ctypes.c_void_p]
        objc.method_getTypeEncoding.restype = ctypes.c_char_p
        objc.method_setImplementation.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        objc.method_setImplementation.restype = ctypes.c_void_p
        cls = objc.objc_getClass(b"QMacAccessibilityElement")
        selector = objc.sel_registerName(b"accessibilitySelectedChildren")
        method = objc.class_getInstanceMethod(cls, selector) if cls else None
        if not method or objc.method_getTypeEncoding(method) != b"@16@0:8":
            _log.warning("Qt selected-children AX guard unavailable: unknown method or ABI")
            return False
        callback_type = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        callback = callback_type(lambda _object, _selector: None)
        original = objc.method_setImplementation(method, ctypes.cast(callback, ctypes.c_void_p))
        # The callback must outlive every Cocoa access, including application
        # shutdown. Keep it even if the runtime returned an unexpected old IMP.
        _callback, _original, _runtime = callback, original, objc
        app.setProperty("icstex_ax_selected_children_guard", True)
        _log.warning("Qt Cocoa AX selected-children crash mitigation active; selection enumeration unavailable")
        return True
    except (OSError, AttributeError, TypeError, ValueError):
        _log.exception("Unable to install the version-scoped Qt Cocoa AX guard")
        return False
