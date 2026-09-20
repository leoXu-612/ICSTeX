"""Version/ABI boundaries without changing this process's Objective-C runtime."""
import ctypes
from contextlib import ExitStack
from unittest import TestCase
from unittest.mock import Mock, patch

from app.gui import macos_accessibility as guard


class MacAccessibilityGuardTests(TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name in ("_callback", "_original", "_runtime"):
            self.stack.enter_context(patch.object(guard, name, None))
        self.app = Mock()
        self.thread = object()
        self.app.thread.return_value = self.thread
        self.app.platformName.return_value = "cocoa"
        self.stack.enter_context(patch.object(guard.QApplication, "instance", return_value=self.app))
        self.stack.enter_context(patch.object(guard.QThread, "currentThread", return_value=self.thread))
        self.objc = Mock()
        self.objc.objc_getClass.return_value = 10
        self.objc.sel_registerName.return_value = 20
        self.objc.class_getInstanceMethod.return_value = 30
        self.objc.method_getTypeEncoding.return_value = b"@16@0:8"
        self.objc.method_setImplementation.return_value = 40
        self.library = self.stack.enter_context(patch.object(guard.ctypes, "CDLL", return_value=self.objc))

    def test_only_verified_runtime_is_affected(self):
        cases = [
            ("darwin", "26.6.1", "arm64", "6.11.1", "cocoa", True),
            ("darwin", "25.1", "arm64", "6.11.1", "cocoa", False),
            ("darwin", "27.0", "arm64", "6.11.1", "cocoa", False),
            ("darwin", "26.6.1", "x86_64", "6.11.1", "cocoa", False),
            ("darwin", "26.6.1", "arm64", "6.11.2", "cocoa", False),
            ("darwin", "26.6.1", "arm64", "6.11.1", "offscreen", False),
            ("win32", "", "arm64", "6.11.1", "windows", False),
        ]
        for system, mac, machine, qt, backend, expected in cases:
            with self.subTest(system=system, mac=mac, machine=machine, qt=qt, backend=backend):
                self.app.platformName.return_value = backend
                with patch.object(guard.sys, "platform", system), \
                     patch.object(guard.platform, "mac_ver", return_value=(mac, (), "")), \
                     patch.object(guard.platform, "machine", return_value=machine), \
                     patch.object(guard, "qVersion", return_value=qt):
                    self.assertEqual(guard._affected_runtime(self.app), expected)
        self.library.assert_not_called()

    def test_unaffected_or_no_application_does_not_load_runtime(self):
        with patch.object(guard, "_affected_runtime", return_value=False):
            self.assertFalse(guard.install_selected_children_guard())
        with patch.object(guard.QApplication, "instance", return_value=None):
            self.assertFalse(guard.install_selected_children_guard())
        self.library.assert_not_called()

    def test_gui_thread_required_before_runtime_mutation(self):
        with patch.object(guard, "_affected_runtime", return_value=True), \
             patch.object(guard.QThread, "currentThread", return_value=object()):
            with self.assertRaises(RuntimeError):
                guard.install_selected_children_guard()
        self.library.assert_not_called()

    def test_missing_class_method_or_unknown_abi_never_patches(self):
        for name, value in (("objc_getClass", None), ("class_getInstanceMethod", None),
                            ("method_getTypeEncoding", b"v16@0:8")):
            with self.subTest(name=name), patch.object(guard, "_affected_runtime", return_value=True), \
                 patch.object(getattr(self.objc, name), "return_value", value), \
                 self.assertLogs(guard._log, level="WARNING"):
                self.assertFalse(guard.install_selected_children_guard())
        self.objc.method_setImplementation.assert_not_called()
        self.app.setProperty.assert_not_called()

    def test_only_one_selector_replaced_once_and_callback_retained(self):
        with patch.object(guard, "_affected_runtime", return_value=True), \
             self.assertLogs(guard._log, level="WARNING"):
            self.assertTrue(guard.install_selected_children_guard())
            self.assertTrue(guard.install_selected_children_guard())
        self.objc.sel_registerName.assert_called_once_with(b"accessibilitySelectedChildren")
        self.objc.method_setImplementation.assert_called_once()
        method, pointer = self.objc.method_setImplementation.call_args.args
        self.assertEqual(method, 30)
        self.assertEqual(pointer.value, ctypes.cast(guard._callback, ctypes.c_void_p).value)
        self.assertIsNone(guard._callback(None, None))
        self.assertEqual(guard._original, 40)
        self.assertIs(guard._runtime, self.objc)
        self.app.setProperty.assert_called_once_with("icstex_ax_selected_children_guard", True)

    def test_runtime_load_failure_is_visible_without_claiming_install(self):
        with patch.object(guard, "_affected_runtime", return_value=True), \
             patch.object(guard.ctypes, "CDLL", side_effect=OSError("missing runtime")), \
             self.assertLogs(guard._log, level="ERROR"):
            self.assertFalse(guard.install_selected_children_guard())
        self.assertIsNone(guard._callback)
        self.app.setProperty.assert_not_called()
