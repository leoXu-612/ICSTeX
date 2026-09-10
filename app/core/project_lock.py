"""The existing reentrant project lock, shared by bounded local writers.

This serializes cooperating ICSTeX writers, not external editors. Callers still
need content comparisons and must not treat the lock as frozen-input evidence.
"""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import tempfile
import threading

_LOCKS: dict[str, threading.RLock] = {}
_GUARD = threading.Lock()
_HELD = threading.local()


@contextmanager
def project_write_lock(root: Path, *, blocking: bool = True):
    key = str(root.resolve())
    held = getattr(_HELD, "roots", None)
    if held is None:
        held = set()
        _HELD.roots = held
    if key in held:
        yield
        return
    with _GUARD:
        thread_lock = _LOCKS.setdefault(key, threading.RLock())
    if not thread_lock.acquire(blocking=blocking):
        raise BlockingIOError("Project is busy; retry after the current operation")
    try:
        lock_dir = Path(tempfile.gettempdir()).resolve() / "icstex-agent-locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.lock"
        with lock_path.open("a+b") as handle:
            _lock_handle(handle, blocking=blocking)
            held.add(key)
            try:
                yield
            finally:
                held.remove(key)
                _unlock_handle(handle)
    finally:
        thread_lock.release()


def _lock_handle(handle, *, blocking=True):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        if handle.read(1) == b"":
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))


def _unlock_handle(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
