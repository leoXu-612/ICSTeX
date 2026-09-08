"""Narrow native update adapters. Upstream libraries own networking and install."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Callable, Protocol

from app.core.app_updates import UpdateConfiguration


CanShutdown = Callable[[], bool]
Notification = Callable[[str], None]


class NativeUpdater(Protocol):
    def check(self, *, user_initiated: bool) -> None: ...
    def close(self) -> None: ...


class SparkleUpdater:
    def __init__(self, config: UpdateConfiguration, library: Path,
                 can_shutdown: CanShutdown, shutdown: Callable[[], None],
                 notify: Notification, *, loader=ctypes.CDLL) -> None:
        self._library = loader(str(library))
        can_type = ctypes.CFUNCTYPE(ctypes.c_int)
        shutdown_type = ctypes.CFUNCTYPE(None)
        event_type = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
        self._callbacks = (
            can_type(lambda: int(can_shutdown())),
            shutdown_type(shutdown),
            event_type(lambda value: notify((value or b"error").decode("ascii", errors="replace"))),
        )
        initialize = self._library.icstex_update_init
        initialize.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
                               can_type, shutdown_type, event_type]
        initialize.restype = ctypes.c_int
        self._library.icstex_update_check.argtypes = [ctypes.c_int]
        self._library.icstex_update_check.restype = ctypes.c_int
        self._library.icstex_update_cleanup.argtypes = []
        self._library.icstex_update_cleanup.restype = None
        result = initialize(config.feed_url.encode("utf-8"), config.public_key.encode("ascii"),
                            str(config.release_sequence).encode("ascii"), *self._callbacks)
        if result != 1:
            raise RuntimeError("Sparkle configuration or native startup failed")

    def check(self, *, user_initiated: bool) -> None:
        if not self._library.icstex_update_check(int(user_initiated)):
            raise RuntimeError("An update operation is already in progress")

    def close(self) -> None:
        self._library.icstex_update_cleanup()


class WinSparkleUpdater:
    def __init__(self, config: UpdateConfiguration, library: Path,
                 can_shutdown: CanShutdown, shutdown: Callable[[], None],
                 notify: Notification, *, loader=ctypes.CDLL, launcher=None) -> None:
        # WinSparkle exports __cdecl APIs, including on 32-bit Windows.
        # CDLL's default Windows load flags do not search the working directory.
        self._library = loader(str(library))
        self._callbacks: list = []
        self._install_authorized = False
        self._notify = notify
        self._launcher = launcher or self._launch_installer
        self._bind("win_sparkle_set_app_details", [ctypes.c_wchar_p] * 3)
        self._bind("win_sparkle_set_app_build_version", [ctypes.c_wchar_p])
        for name in ("win_sparkle_set_appcast_url", "win_sparkle_set_registry_path", "win_sparkle_set_lang"):
            self._bind(name, [ctypes.c_char_p])
        self._bind("win_sparkle_set_eddsa_public_key", [ctypes.c_char_p], ctypes.c_int)
        self._bind("win_sparkle_set_automatic_check_for_updates", [ctypes.c_int])
        for name in ("win_sparkle_init", "win_sparkle_cleanup", "win_sparkle_check_update_with_ui",
                     "win_sparkle_check_update_without_ui"):
            self._bind(name, [])
        lib = self._library
        lib.win_sparkle_set_app_details("ICSTeX", "ICSTeX", config.version)
        lib.win_sparkle_set_app_build_version(str(config.release_sequence))
        lib.win_sparkle_set_registry_path(
            f"Software\\ICSTeX\\ICSTeX\\NativeUpdates\\{config.channel}-{config.architecture}".encode("ascii"))
        lib.win_sparkle_set_lang(b"zh_CN")
        lib.win_sparkle_set_appcast_url(config.feed_url.encode("utf-8"))
        if not lib.win_sparkle_set_eddsa_public_key(config.public_key.encode("ascii")):
            raise RuntimeError("WinSparkle rejected the Ed25519 public key")
        # Scheduling belongs to the opt-in Qt controller, never native defaults.
        lib.win_sparkle_set_automatic_check_for_updates(0)
        def authorize() -> int:
            self._install_authorized = bool(can_shutdown())
            return int(self._install_authorized)
        self._callback("win_sparkle_set_can_shutdown_callback", authorize, ctypes.c_int)
        self._callback("win_sparkle_set_shutdown_request_callback", shutdown)
        run_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_wchar_p)
        run_callback = run_type(self._run_installer)
        self._callbacks.append(run_callback)
        self._bind("win_sparkle_set_user_run_installer_callback", [run_type])
        lib.win_sparkle_set_user_run_installer_callback(run_callback)
        for api, event in (
            ("win_sparkle_set_error_callback", "error"),
            ("win_sparkle_set_did_find_update_callback", "available"),
            ("win_sparkle_set_did_not_find_update_callback", "no_update"),
            ("win_sparkle_set_update_cancelled_callback", "cancelled"),
            ("win_sparkle_set_update_dismissed_callback", "finished"),
        ):
            self._callback(api, lambda event=event: notify(event))
        lib.win_sparkle_init()

    @staticmethod
    def _launch_installer(path: Path) -> None:
        # WinSparkle has already verified the payload's Ed25519 signature.
        # Never forward remote appcast installerArguments. ShellExecute retains
        # normal UAC behavior for the verified EXE without invoking a command shell.
        os.startfile(str(path), "open", arguments="", cwd=str(path.parent))

    def _run_installer(self, file_name: str) -> int:
        try:
            if not self._install_authorized:
                raise RuntimeError("Installation was not approved by the application")
            self._install_authorized = False
            path = Path(file_name)
            if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.suffix.lower() != ".exe":
                raise RuntimeError("Only a verified local EXE installer is supported")
            self._notify("installing")
            self._launcher(path)
            return 1
        except Exception:
            self._notify("error")
            return -1  # WINSPARKLE_RETURN_ERROR: never fall back to remote arguments.

    def _bind(self, name: str, arguments: list, result=None) -> None:
        function = getattr(self._library, name)
        function.argtypes = arguments
        function.restype = result

    def _callback(self, name: str, function: Callable, result=None) -> None:
        callback_type = ctypes.CFUNCTYPE(result)
        callback = callback_type(function)
        self._callbacks.append(callback)  # Keep native function pointers alive.
        self._bind(name, [callback_type])
        getattr(self._library, name)(callback)

    def check(self, *, user_initiated: bool) -> None:
        if user_initiated:
            self._library.win_sparkle_check_update_with_ui()
        else:
            self._library.win_sparkle_check_update_without_ui()

    def close(self) -> None:
        self._library.win_sparkle_cleanup()


def create_native_updater(config: UpdateConfiguration, library: Path,
                          can_shutdown: CanShutdown, shutdown: Callable[[], None],
                          notify: Notification) -> NativeUpdater:
    updater = SparkleUpdater if config.target_platform == "darwin" else WinSparkleUpdater
    return updater(config, library, can_shutdown, shutdown, notify)
