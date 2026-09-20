"""Cheap invalidation observations; these do not authorize file access."""
from __future__ import annotations

from pathlib import Path
from stat import S_ISREG


FileSignature = tuple[int, int, int, int, int] | None


def is_nonempty_file(path: Path | None) -> bool:
    """One stat: a nonempty regular-file target, not content or access evidence.

    Like Path.is_file(), follows links. Callers retain their separate scope/link
    protections and must recheck at the actual export or submission boundary.
    """
    if path is None:
        return False
    try:
        value = path.stat()
        return S_ISREG(value.st_mode) and value.st_size > 0
    except OSError:
        return False


def file_signature(path: Path) -> FileSignature:
    try:
        value = path.stat()
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    except OSError:
        return None
