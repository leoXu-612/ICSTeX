"""Content-guarded Block writes with bounded in-flight recovery evidence.

Only cooperating ICSTeX writers share the lock. Rechecking immediately before
replace is not an OS compare-and-swap against arbitrary external editors. A
pending journal is never called a completed checkpoint or automatically restored.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

from app.core.blocks.model import SCHEMA_VERSION
from app.core.project_dependencies import MAX_SOURCE_BYTES, read_project_bytes, safe_project_input
from app.core.project_lock import project_write_lock

PENDING_PATH = Path(".icstex/block-write.pending")
MAX_BATCH_BYTES = 64 * 1024 * 1024
MAX_FILES = 2000
_METADATA = frozenset({".icstex/blocks.json", ".icstex/layouts.json", ".icstex/sources.json",
                       "styles/document-theme.json"})


class BlockWriteConflict(OSError):
    pass


def _json(data):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate metadata field")
            value[key] = item
        return value
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def _preserves(original, serialized):
    # Known optional defaults may be added; no original field/value may disappear.
    if isinstance(original, dict):
        return isinstance(serialized, dict) and all(
            key in serialized and _preserves(value, serialized[key]) for key, value in original.items())
    if isinstance(original, list):
        return isinstance(serialized, list) and len(original) == len(serialized) and all(
            _preserves(a, b) for a, b in zip(original, serialized))
    return type(original) is type(serialized) and original == serialized


class BlockWriteGuard:
    def __init__(self, root: Path, metadata: dict[Path, bytes], generated: dict[Path, bytes],
                 *, generated_alternative: dict[Path, bytes] | None = None):
        self.root = root.resolve(strict=True)
        info = self.root.lstat()
        self._identity = (info.st_dev, info.st_ino)
        self.expected: dict[Path, bytes | None] = {}
        with project_write_lock(self.root, blocking=False):
            self._no_pending()
            self._limit({**metadata, **generated})
            for path, encoded in {**metadata, **generated}.items():
                self._relative(path)
                current = self._read(path)
                if current is not None:
                    if path in metadata:
                        try:
                            value = _json(current)
                            if not isinstance(value, dict) or value.get("schemaVersion", SCHEMA_VERSION) != SCHEMA_VERSION:
                                raise ValueError("Unsupported metadata version")
                            if not _preserves(value, _json(encoded)):
                                raise ValueError("Metadata cannot round-trip without loss")
                        except (ValueError, UnicodeError, RecursionError) as exc:
                            raise BlockWriteConflict(f"Unsupported or changed Block metadata: {path.name}") from exc
                    elif current not in (encoded, (generated_alternative or {}).get(path)):
                        raise BlockWriteConflict(f"Generated source has manual or external changes: {path.name}")
                self.expected[path] = current
            self._check(self.expected)

    def check_current(self) -> None:
        """Read-only observation before an explicit model transaction.

        This does not reserve external files; write() repeats its own checks.
        The owning session must pause its own writers while this is called.
        """
        self._root_check()
        self._no_pending()
        self._check(self.expected)

    def _relative(self, path):
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise BlockWriteConflict("Path is outside this Block project") from exc
        if not relative.parts or any(part in {".", ".."} for part in relative.parts):
            raise BlockWriteConflict("Invalid Block project path")
        return relative

    def _root_check(self):
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != self._identity:
            raise BlockWriteConflict("Block project directory changed")

    def _read(self, path):
        self._root_check()
        try:
            return read_project_bytes(path, self.root, allow_internal=True)
        except FileNotFoundError:
            return None

    def _no_pending(self):
        self._root_check()
        path = self.root / PENDING_PATH
        if path.exists() or path.is_symlink():
            raise BlockWriteConflict("Unresolved Block write evidence: .icstex/block-write.pending; originals retained")

    def _check(self, expected):
        for path, data in expected.items():
            if self._read(path) != data:
                raise BlockWriteConflict(f"Block file changed externally; draft retained: {self._relative(path)}")

    def _limit(self, files):
        if len(files) > MAX_FILES or any(len(data) > MAX_SOURCE_BYTES for data in files.values() if data is not None):
            raise ValueError("Block write exceeds file/count limit")
        if sum(len(data) for data in files.values() if data is not None) > MAX_BATCH_BYTES:
            raise ValueError("Block write exceeds 64 MiB limit")

    @contextmanager
    def _parent(self, path, *, create=False):
        """POSIX ancestor walk anchored to the original project, without links."""
        relative = self._relative(path)
        self._root_check()
        if safe_project_input(self.root, path, allow_internal=True) is None:
            raise BlockWriteConflict("Unsafe Block write path")
        fd = None
        try:
            if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                fd = os.open(self.root, flags)
                info = os.fstat(fd)
                if (info.st_dev, info.st_ino) != self._identity:
                    raise BlockWriteConflict("Block project directory changed")
                for part in relative.parts[:-1]:
                    if create:
                        try:
                            os.mkdir(part, 0o700, dir_fd=fd)
                            os.fsync(fd)
                        except FileExistsError:
                            pass
                    child = os.open(part, flags, dir_fd=fd)
                    os.close(fd)
                    fd = child
            elif create:
                path.parent.mkdir(parents=True, exist_ok=True)
                if safe_project_input(self.root, path, allow_internal=True) is None:
                    raise BlockWriteConflict("Unsafe Block write directory")
            yield fd
        finally:
            if fd is not None:
                os.close(fd)

    def _replace(self, path, data, expected):
        with self._parent(path, create=data is not None) as parent:
            self._check({path: expected})
            if data is None:
                if parent is not None:
                    os.unlink(path.name, dir_fd=parent)
                    os.fsync(parent)
                else:
                    path.unlink()
                return
            temporary = path.with_name(f".block-write-{uuid.uuid4().hex}.tmp")
            mode = stat.S_IMODE(path.lstat().st_mode) if expected is not None else 0o600
            try:
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
                fd = os.open(temporary.name if parent is not None else temporary, flags, 0o600,
                             **({"dir_fd": parent} if parent is not None else {}))
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                    if hasattr(os, "fchmod"):
                        os.fchmod(handle.fileno(), mode)
                self._check({path: expected})
                if parent is not None:
                    info, current = os.fstat(parent), path.parent.stat()
                    if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
                        raise BlockWriteConflict("Block parent directory changed")
                    os.replace(temporary.name, path.name, src_dir_fd=parent, dst_dir_fd=parent)
                    os.fsync(parent)
                else:
                    os.replace(temporary, path)
            finally:
                try:
                    if parent is not None:
                        os.unlink(temporary.name, dir_fd=parent)
                    else:
                        temporary.unlink(missing_ok=True)
                except FileNotFoundError:
                    pass

    def _journal(self, changed, before):
        directory = self.root / PENDING_PATH
        with self._parent(directory, create=True) as parent:
            if parent is not None:
                os.mkdir(directory.name, 0o700, dir_fd=parent)
                os.fsync(parent)
            else:
                directory.mkdir(mode=0o700)
        files = {}
        entries = []
        for index, (path, data) in enumerate(changed.items()):
            old = before[path]
            entries.append({"path": self._relative(path).as_posix(), "index": index,
                            "before": hashlib.sha256(old).hexdigest() if old is not None else None,
                            "after": hashlib.sha256(data).hexdigest()})
            if old is not None:
                files[directory / f"before-{index}.bin"] = old
            files[directory / f"after-{index}.bin"] = data
        files[directory / "manifest.json"] = json.dumps({"format": "icstex-block-write", "version": 1,
            "state": "pending", "entries": entries}, indent=2).encode()
        # Use the same anchored primitive, not an unprotected journal writer.
        for path, data in files.items():
            self._replace(path, data, None)
        self._check(files)
        return files

    def _clean_journal(self, files):
        self._check(files)
        for path, data in files.items():
            self._replace(path, None, data)
        directory = self.root / PENDING_PATH
        with self._parent(directory) as parent:
            if parent is not None:
                os.rmdir(directory.name, dir_fd=parent)
                os.fsync(parent)
            else:
                directory.rmdir()

    def write(self, payloads: dict[Path, bytes]) -> list[Path]:
        self._limit(payloads)
        for path in payloads:
            relative = self._relative(path)
            if (relative.as_posix() not in _METADATA | {"main.tex", "styles/icstex-generated.sty"}
                    and not (len(relative.parts) == 2 and relative.parts[0] == "blocks" and relative.suffix == ".tex")):
                raise BlockWriteConflict("Not a Block-owned destination")
        with project_write_lock(self.root, blocking=False):
            self._no_pending()
            expected = {**self.expected, **{path: self.expected.get(path) for path in payloads}}
            self._limit(expected)
            self._check(expected)
            changed = {path: data for path, data in payloads.items() if data != expected[path]}
            if not changed:
                return []
            if sum(len(data) + len(expected[path] or b"") for path, data in changed.items()) > MAX_BATCH_BYTES:
                raise ValueError("Block before/after evidence exceeds 64 MiB limit")
            # All before/after bytes are durable before the first project replacement.
            journal = self._journal(changed, expected)
            written = []
            try:
                self._check(expected)
                for path, data in changed.items():
                    written.append(path)
                    self._replace(path, data, expected[path])
                after = {**expected, **changed}
                self._check(after)
            except BaseException as original:
                failures = []
                for path in reversed(written):
                    try:
                        if self._read(path) != expected[path]:
                            self._replace(path, expected[path], changed[path])
                    except (OSError, ValueError) as exc:
                        failures.append(f"{self._relative(path)}: {exc}")
                if failures:
                    raise BlockWriteConflict("Block write incomplete; external winner and recovery bytes retained: "
                                             + "; ".join(failures)) from original
                self._clean_journal(journal)
                raise
            self._clean_journal(journal)
            self.expected = after
            return list(changed)
