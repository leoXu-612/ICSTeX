"""Cheap invalidation observations; these do not authorize file access."""
from __future__ import annotations

from pathlib import Path


FileSignature = tuple[int, int, int, int, int] | None


def file_signature(path: Path) -> FileSignature:
    try:
        value = path.stat()
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    except OSError:
        return None
