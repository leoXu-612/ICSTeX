"""macOS installation leases, shared by every entry into an installed bundle.

The native, short-lived guard retains the same kernel locks after Python exits.
It observes Sparkle's actual installer exit; elapsed time never releases a lock.
The small journal makes a killed guard fail closed instead of admitting a writer.
This is cooperative exclusion, not a security boundary against a local attacker.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
import time


class UpdateInProgress(RuntimeError):
    pass


def _open_lock(path: Path) -> int:
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o666)
    except FileExistsError:
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    else:
        os.fchmod(fd, 0o666)  # Same installation, including other login sessions.
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        raise UpdateInProgress("Invalid installation lock")
    os.set_inheritable(fd, False)
    return fd


def _boot_id() -> str:
    return subprocess.run(["/usr/sbin/sysctl", "-n", "kern.bootsessionuuid"],
                          check=True, capture_output=True, text=True, timeout=5).stdout.strip()


class InstallationLease:
    def __init__(self, bundle: Path, *, directory: Path = Path("/Users/Shared"),
                 helper: Path | None = None, boot_id: str | None = None) -> None:
        import fcntl
        self.bundle = bundle.resolve()
        self.helper = helper or self.bundle / "Contents/Helpers/ICSTeXInstallGuard"
        self.boot_id = _boot_id() if boot_id is None else boot_id
        identity = hashlib.sha256(os.fsencode(self.bundle)).hexdigest()
        self.gate = _open_lock(directory / f".icstex-{identity}.gate")
        try:
            self.use = _open_lock(directory / f".icstex-{identity}.use")
            self.channel = _open_lock(directory / ".icstex-com.icstex.app.update")
        except Exception:
            os.close(self.gate)
            if hasattr(self, "use"):
                os.close(self.use)
            raise
        self.process: subprocess.Popen | None = None
        self.updating = False
        self.tracking = False
        self._finish_sent = False
        self.closed = False
        self._fcntl = fcntl

    def _lock(self, fd: int, mode: int) -> None:
        try:
            self._fcntl.flock(fd, mode | self._fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise UpdateInProgress("ICSTeX is updating or another instance is running") from exc

    def enter(self) -> None:
        # The gate makes lease acquisition and upgrade atomic with respect to
        # other entrants/upgraders; flock conversion alone does not do that.
        self._lock(self.gate, self._fcntl.LOCK_EX)
        try:
            if os.fstat(self.gate).st_size:
                self._recover()
            self._lock(self.use, self._fcntl.LOCK_SH)
        finally:
            self._fcntl.flock(self.gate, self._fcntl.LOCK_UN)

    def _recover(self) -> None:
        record = os.pread(self.gate, 4096, 0).splitlines()
        try:
            header = json.loads(record[0])
            if header["schema"] != 1:
                raise ValueError("journal schema")
            safe = header["phase"] == "checking" or header["boot"] != self.boot_id
            if not safe and len(record) == 2:
                fields = record[1].decode("ascii").split()
                if len(fields) == 4 and fields[0] == "TRACKING":
                    result = subprocess.run([str(self.helper), "--alive", *fields[1:]], timeout=5)
                    safe = result.returncode == 1  # Gone, not merely unqueryable.
            if not safe:
                raise UpdateInProgress("上次更新尚未确认结束。请等待安装器退出后重试；若更新被强制中断且仍无法打开，请重新启动 Mac 后重试。")
            subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(self.bundle)],
                           check=True, capture_output=True, timeout=30)
        except UpdateInProgress:
            raise
        except Exception as exc:
            raise UpdateInProgress("更新后应用完整性尚未确认。请保留文稿，使用官网可信安装包恢复应用。") from exc
        self._clear()

    def _record(self, phase: str) -> None:
        data = (json.dumps({"schema": 1, "boot": self.boot_id, "phase": phase}) + "\n").encode("ascii")
        os.ftruncate(self.gate, 0)
        os.pwrite(self.gate, data, 0)
        os.fsync(self.gate)

    def _clear(self) -> None:
        os.ftruncate(self.gate, 0)
        os.fsync(self.gate)

    def begin(self) -> None:
        if self.updating:
            if self.process is not None and not os.fstat(self.gate).st_size:
                self.process.wait(timeout=5)
            if self.process is not None and self.process.poll() is not None:
                self.finish()
            else:
                return
        # Sparkle's launchd installer is keyed by bundle ID, not install path.
        # Serialize update sessions across copies as well as login sessions.
        self._lock(self.channel, self._fcntl.LOCK_EX)
        try:
            self._lock(self.gate, self._fcntl.LOCK_EX)
            # A previous guard may have died while this GUI remained alive.
            if os.fstat(self.gate).st_size:
                self._recover()
            if subprocess.run([str(self.helper), "--idle"], timeout=5).returncode != 0:
                raise UpdateInProgress("A Sparkle installer is already active")
            self._fcntl.flock(self.use, self._fcntl.LOCK_UN)
            try:
                self._lock(self.use, self._fcntl.LOCK_EX)
            except Exception:
                self._fcntl.flock(self.use, self._fcntl.LOCK_SH)
                raise
            self._record("checking")
            self.updating = True
        except Exception:
            self._fcntl.flock(self.use, self._fcntl.LOCK_SH)
            self._fcntl.flock(self.gate, self._fcntl.LOCK_UN)
            self._fcntl.flock(self.channel, self._fcntl.LOCK_UN)
            raise

    def extracting(self) -> None:
        if not self.updating:
            raise UpdateInProgress("Missing installation lease")
        if self.process is not None:
            return
        self._record("extracting")
        self._finish_sent = False
        # Only this signed, build-bound helper is run; no Python or libraries
        # from the old application are needed after bundle replacement.
        self.process = subprocess.Popen(
            [str(self.helper), str(self.gate), str(self.use), str(self.channel), str(self.bundle)],
            pass_fds=(self.gate, self.use, self.channel), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, start_new_session=True)
        assert self.process.stdout is not None
        readable, _, _ = select.select([self.process.stdout], [], [], 5)
        if not readable or self.process.stdout.readline() != b"READY\n":
            raise UpdateInProgress("Installation guard did not start")

    def ready(self, timeout: float = 5.0) -> bool:
        if self.tracking:
            return self.process is not None and self.process.poll() is None
        if self.process is None or self.process.stdout is None:
            return False
        readable, _, _ = select.select([self.process.stdout], [], [], timeout)
        if readable:
            self.tracking = self.process.stdout.readline() == b"TRACKING\n"
        return self.tracking and self.process.poll() is None

    def finish(self) -> None:
        if not self.updating:
            return
        if self.process is not None:
            if self.process.poll() is None:
                # A completed UI cycle can leave an install-on-quit pending.
                # Tell the helper discovery is finished, but never unlock here.
                if self.process.stdin is not None and not self._finish_sent:
                    try:
                        self.process.stdin.write(b"FINISH\n")
                        self.process.stdin.flush()
                        self._finish_sent = True
                    except (BrokenPipeError, OSError):
                        pass
                return
            for stream in (self.process.stdin, self.process.stdout):
                if stream is not None:
                    stream.close()
            self.process = None
            self.tracking = False
            # Helper downgrades the shared open-file description only after
            # installer exit and signature verification. Recheck the journal.
            if os.fstat(self.gate).st_size:
                self._recover()
        else:
            self._clear()  # No extraction/installer was ever started.
        self._fcntl.flock(self.use, self._fcntl.LOCK_SH)
        self._fcntl.flock(self.gate, self._fcntl.LOCK_UN)
        self._fcntl.flock(self.channel, self._fcntl.LOCK_UN)
        self.updating = False

    def close(self) -> None:
        if not self.closed:
            # close, NOT LOCK_UN: the native guard inherits these descriptions.
            os.close(self.use)
            os.close(self.gate)
            os.close(self.channel)
            self.closed = True


_installed_lease: InstallationLease | None = None


def installed_lease() -> InstallationLease | None:
    return _installed_lease


def enter_installed_application() -> None:
    """Called by the PyInstaller runtime hook, before GUI/MCP entry imports."""
    global _installed_lease
    if sys.platform != "darwin" or not getattr(sys, "frozen", False) or _installed_lease is not None:
        return
    bundle = Path(sys.executable).resolve().parents[2]
    helper = bundle / "Contents/Helpers/ICSTeXInstallGuard"
    if not helper.is_file():
        return  # Ordinary source/manual builds do not acquire update locks.
    lease = InstallationLease(bundle, helper=helper)
    deadline = time.monotonic() + 15
    while True:
        try:
            lease.enter()
            break
        except UpdateInProgress:
            # Sparkle can relaunch just before Autoupdate finishes cleanup.
            # A timeout refuses launch; it NEVER declares the install finished.
            if time.monotonic() >= deadline:
                lease.close()
                raise
            time.sleep(0.1)
    _installed_lease = lease
