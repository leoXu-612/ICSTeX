from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.gui.update_backends import SparkleUpdater, WinSparkleUpdater
from tests.test_app_updates import update_config


class FakeFunction:
    def __init__(self, result=None):
        self.calls = []
        self.result = result

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


class FakeLibrary:
    def __init__(self):
        self.functions = {}

    def __getattr__(self, name):
        if name not in self.functions:
            result = 1 if name in ("icstex_update_init", "icstex_update_check", "win_sparkle_set_eddsa_public_key") else None
            self.functions[name] = FakeFunction(result)
        return self.functions[name]


class NativeUpdateBackendTests(unittest.TestCase):
    def test_sparkle_uses_build_identity_and_retains_callbacks(self):
        library = FakeLibrary()
        events = []
        exits = []
        adapter = SparkleUpdater(update_config(), Path("/fixture/bridge"), lambda: False,
                                 lambda: exits.append(True), events.append, loader=lambda _path: library)
        args = library.icstex_update_init.calls[0]
        self.assertEqual(args[2], b"101")
        self.assertEqual(args[3](), 0)
        args[4]()
        args[5](b"available")
        self.assertEqual(exits, [True])
        self.assertEqual(events, ["available"])
        adapter.check(user_initiated=True)
        adapter.check(user_initiated=False)
        self.assertEqual(library.icstex_update_check.calls, [(1,), (0,)])
        adapter.close()
        self.assertEqual(len(library.icstex_update_cleanup.calls), 1)

    def test_sparkle_start_error_and_busy_are_not_success(self):
        library = FakeLibrary()
        library.icstex_update_init.result = 0
        with self.assertRaises(RuntimeError):
            SparkleUpdater(update_config(), Path("/fixture"), lambda: True, lambda: None,
                           lambda _event: None, loader=lambda _path: library)
        library.icstex_update_init.result = 1
        adapter = SparkleUpdater(update_config(), Path("/fixture"), lambda: True, lambda: None,
                                 lambda _event: None, loader=lambda _path: library)
        library.icstex_update_check.result = 0
        with self.assertRaises(RuntimeError):
            adapter.check(user_initiated=True)

    def test_windows_sets_key_before_init_and_disables_native_scheduling(self):
        library = FakeLibrary()
        adapter = WinSparkleUpdater(update_config(platform="win32"), Path("/fixture/WinSparkle.dll"),
                                    lambda: False, lambda: None, lambda _event: None,
                                    loader=lambda _path: library)
        self.assertEqual(library.win_sparkle_set_automatic_check_for_updates.calls, [(0,)])
        self.assertEqual(library.win_sparkle_set_app_build_version.calls, [("101",)])
        self.assertEqual(library.win_sparkle_set_can_shutdown_callback.calls[0][0](), 0)
        adapter.check(user_initiated=True)
        adapter.check(user_initiated=False)
        self.assertEqual(len(library.win_sparkle_check_update_with_ui.calls), 1)
        self.assertEqual(len(library.win_sparkle_check_update_without_ui.calls), 1)
        self.assertNotIn("win_sparkle_check_update_with_ui_and_install", library.functions)
        adapter.close()

    def test_windows_bad_key_never_initializes_updater(self):
        library = FakeLibrary()
        library.win_sparkle_set_eddsa_public_key.result = 0
        with self.assertRaises(RuntimeError):
            WinSparkleUpdater(update_config(platform="win32"), Path("/fixture"), lambda: True,
                              lambda: None, lambda _event: None, loader=lambda _path: library)
        self.assertEqual(library.win_sparkle_init.calls, [])

    def test_windows_launches_only_approved_exe_without_remote_arguments(self):
        library = FakeLibrary()
        events, launches = [], []
        adapter = WinSparkleUpdater(update_config(platform="win32"), Path("/fixture"), lambda: True,
                                    lambda: None, events.append, loader=lambda _path: library,
                                    launcher=launches.append)
        run = library.win_sparkle_set_user_run_installer_callback.calls[0][0]
        approve = library.win_sparkle_set_can_shutdown_callback.calls[0][0]
        with TemporaryDirectory() as temporary:
            installer = Path(temporary) / "ICSTeX-Setup.exe"
            installer.write_bytes(b"synthetic signed-payload callback fixture")
            self.assertEqual(run(str(installer)), -1)
            self.assertFalse(launches)
            self.assertEqual(approve(), 1)
            self.assertEqual(run(str(installer)), 1)
            self.assertEqual(launches, [installer])
            self.assertEqual(events[-1], "installing")
            self.assertEqual(run(str(installer)), -1)  # One-use permission.
            approve()
            self.assertEqual(run(str(installer.with_suffix(".cmd"))), -1)
        adapter.close()

    def test_windows_launch_failure_does_not_fall_back_to_remote_parameters(self):
        library, events = FakeLibrary(), []
        def fail(_path):
            raise OSError("UAC cancelled")
        adapter = WinSparkleUpdater(update_config(platform="win32"), Path("/fixture"), lambda: True,
                                    lambda: None, events.append, loader=lambda _path: library, launcher=fail)
        with TemporaryDirectory() as temporary:
            installer = Path(temporary) / "ICSTeX-Setup.exe"
            installer.write_bytes(b"fixture")
            library.win_sparkle_set_can_shutdown_callback.calls[0][0]()
            self.assertEqual(library.win_sparkle_set_user_run_installer_callback.calls[0][0](str(installer)), -1)
        self.assertEqual(events, ["installing", "error"])
