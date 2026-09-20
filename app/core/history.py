"""Bounded source text history, not a raw-byte project checkpoint.

Manifest paths are assertions, never read/delete authority. Legacy buckets stay
readable but immutable; new writes use source-specific buckets.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

from app.core.project_dependencies import safe_project_input
from app.core.project_lock import project_write_lock

HISTORY_DIR = ".icstex/history"
MAX_SNAPSHOTS = 40
MAX_HISTORY_BYTES = 4 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_INDEX_ENTRIES = 1000
_ID = re.compile(r"[0-9]{8}T[0-9]{6}(?:[0-9]{6})?Z-[0-9a-f]{10}(?:-[0-9a-f]{12})?\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class HistoryError(ValueError):
    pass


@dataclass(frozen=True)
class HistorySnapshot:
    id: str
    source_path: Path
    snapshot_path: Path
    label: str
    created_at: datetime
    size: int
    sha256: str


def _source(path):
    raw = Path(path).expanduser().absolute()
    parent = raw.parent.resolve(strict=True)
    source = parent / raw.name
    if safe_project_input(parent, source, allow_internal=True) is None:
        raise HistoryError("History source path contains a link or is unavailable")
    return source


def _legacy_bucket_for(source_path: Path, project_dir: Path) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", source_path.name).strip("._")
    return value or source_path.stem or "document"


def _bucket_for(source_path: Path, project_dir: Path) -> str:
    label = re.sub(r"[^A-Za-z0-9._-]", "_", _legacy_bucket_for(source_path, project_dir))[:80]
    return label + "-" + hashlib.sha256(source_path.name.encode("utf-8")).hexdigest()[:16]


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


class _Bucket:
    def __init__(self, source, name, *, create=False):
        self.source = source
        self.root = source.parent
        self.path = self.root / HISTORY_DIR / name
        self.create = create
        self.fd = None
        info = self.root.stat()
        self.root_id = (info.st_dev, info.st_ino)

    def __enter__(self):
        if safe_project_input(self.root, self.path / "manifest.json", allow_internal=True) is None:
            raise HistoryError("History directory contains a link")
        try:
            if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                self.fd = os.open(self.root.anchor, flags)
                for part in self.root.parts[1:]:
                    child = os.open(part, flags, dir_fd=self.fd)
                    os.close(self.fd)
                    self.fd = child
                opened = os.fstat(self.fd)
                if (opened.st_dev, opened.st_ino) != self.root_id:
                    raise HistoryError("History source directory changed")
                for part in (".icstex", "history", self.path.name):
                    if self.create:
                        try:
                            os.mkdir(part, 0o700, dir_fd=self.fd)
                        except FileExistsError:
                            pass
                    child = os.open(part, flags, dir_fd=self.fd)
                    os.close(self.fd)
                    self.fd = child
                opened = os.fstat(self.fd)
            else:
                # Observed links/junctions are rejected on Windows. Native reparse
                # races remain separate platform acceptance, not a POSIX claim.
                if self.create:
                    current = self.root
                    for part in (".icstex", "history", self.path.name):
                        current /= part
                        if safe_project_input(self.root, current / "guard", allow_internal=True) is None:
                            raise HistoryError("History directory contains a link")
                        current.mkdir(mode=0o700, exist_ok=True)
                opened = self.path.lstat()
                if not stat.S_ISDIR(opened.st_mode):
                    raise HistoryError("History bucket is not a directory")
            self.identity = (opened.st_dev, opened.st_ino)
            self.check()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    @property
    def kwargs(self):
        return {"dir_fd": self.fd} if self.fd is not None else {}

    def name(self, name):
        if Path(name).name != name:
            raise HistoryError("Invalid history object name")
        return name if self.fd is not None else self.path / name

    def check(self):
        root, current = self.root.lstat(), self.path.lstat()
        if ((root.st_dev, root.st_ino) != self.root_id or not stat.S_ISDIR(root.st_mode)
                or (current.st_dev, current.st_ino) != self.identity or not stat.S_ISDIR(current.st_mode)
                or safe_project_input(self.root, self.path / "manifest.json", allow_internal=True) is None):
            raise HistoryError("History directory changed; original retained")

    def read(self, name, limit):
        self.check()
        if safe_project_input(self.root, self.path / name, allow_internal=True) is None:
            raise HistoryError("History object contains a link; no file was opened")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(self.name(name), flags, **self.kwargs)
        with os.fdopen(descriptor, "rb") as stream:
            initial = os.fstat(stream.fileno())
            if not stat.S_ISREG(initial.st_mode) or initial.st_size > limit:
                raise HistoryError("History object is not a bounded regular file")
            data = stream.read(limit + 1)
            if len(data) > limit or _signature(os.fstat(stream.fileno())) != _signature(initial):
                raise HistoryError("History object changed or exceeds its size limit")
        try:
            current = os.stat(self.name(name), follow_symlinks=False, **self.kwargs)
        except FileNotFoundError as exc:
            raise HistoryError("History object disappeared during reading") from exc
        if _signature(current) != _signature(initial):
            raise HistoryError("History object changed during reading")
        self.check()
        return data, _signature(initial)

    def manifest(self):
        try:
            return self.read("manifest.json", MAX_MANIFEST_BYTES)[0]
        except FileNotFoundError:
            return None

    def write_new(self, name, data):
        self.check()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(self.name(name), flags, 0o600, **self.kwargs)
        initial = os.fstat(descriptor)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
                return _signature(os.fstat(stream.fileno()))
        except BaseException:
            try:
                current = os.stat(self.name(name), follow_symlinks=False, **self.kwargs)
                if (current.st_dev, current.st_ino) == (initial.st_dev, initial.st_ino):
                    os.unlink(self.name(name), **self.kwargs)
            except FileNotFoundError:
                pass
            raise

    def unlink_owned(self, name, expected):
        # Cooperating writers share the lock. External changes cannot be locked
        # out of the final syscall; changed observed objects are retained.
        try:
            current = os.stat(self.name(name), follow_symlinks=False, **self.kwargs)
            if _signature(current) == expected and stat.S_ISREG(current.st_mode):
                os.unlink(self.name(name), **self.kwargs)
        except FileNotFoundError:
            pass

    def publish_manifest(self, entries, expected):
        data = json.dumps([_entry(record) for record in entries], ensure_ascii=False, indent=2).encode("utf-8")
        if len(data) > MAX_MANIFEST_BYTES:
            raise HistoryError("History index exceeds 1 MiB")
        name = f".manifest-{uuid.uuid4().hex}.tmp"
        owned = self.write_new(name, data)
        try:
            if self.manifest() != expected:
                raise HistoryError("History index changed; original retained")
            self.check()
            staged, observation = self.read(name, MAX_MANIFEST_BYTES)
            if observation != owned or staged != data:
                raise HistoryError("Staged history index changed")
            if self.fd is not None:
                os.replace(name, "manifest.json", src_dir_fd=self.fd, dst_dir_fd=self.fd)
            else:
                os.replace(self.path / name, self.path / "manifest.json")
        finally:
            self.unlink_owned(name, owned)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise HistoryError("Duplicate history index field")
        result[key] = value
    return result


def _records(data, source, bucket):
    if data is None:
        return []
    try:
        entries = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
        if not isinstance(entries, list) or len(entries) > MAX_INDEX_ENTRIES:
            raise HistoryError("Unknown or oversized history index")
        if bucket.name != _legacy_bucket_for(source, source.parent) and len(entries) > MAX_SNAPSHOTS:
            raise HistoryError("Current history index exceeds the bounded retention count")
        result = []
        for value in entries:
            if not isinstance(value, dict) or set(value) != {"id", "source_path", "snapshot_path", "label", "created_at", "size", "sha256"}:
                raise HistoryError("Unknown history entry fields; original retained")
            if (any(not isinstance(value[key], str) or len(value[key]) > 4096
                    for key in ("id", "source_path", "snapshot_path", "label", "created_at", "sha256"))
                    or not _ID.fullmatch(value["id"]) or not _SHA.fullmatch(value["sha256"])
                    or value["id"].split("-")[1] != value["sha256"][:10]
                    or type(value["size"]) is not int or not 0 <= value["size"] <= MAX_HISTORY_BYTES):
                raise HistoryError("Invalid history identity or size")
            owner = Path(value["source_path"])
            path = bucket / (value["id"] + ".tex")
            legacy = bucket.name == _legacy_bucket_for(source, source.parent)
            if (owner != source and not (legacy and owner.parent == source.parent
                    and _legacy_bucket_for(owner, owner.parent) == bucket.name)):
                raise HistoryError("History entry belongs to another source")
            if Path(value["snapshot_path"]) != path:
                raise HistoryError("History entry points outside its expected bucket")
            created = datetime.fromisoformat(value["created_at"])
            if created.tzinfo is None:
                raise HistoryError("History creation time is ambiguous")
            result.append(HistorySnapshot(value["id"], owner, path, value["label"], created,
                                          value["size"], value["sha256"]))
        return result
    except (TypeError, KeyError, RecursionError, OverflowError, UnicodeError, json.JSONDecodeError) as exc:
        raise HistoryError("History index is corrupt or unsupported; original retained") from exc


def _entry(snapshot):
    return {"id": snapshot.id, "source_path": str(snapshot.source_path), "snapshot_path": str(snapshot.snapshot_path),
            "label": snapshot.label, "created_at": snapshot.created_at.isoformat(), "size": snapshot.size,
            "sha256": snapshot.sha256}


def _read_record(bucket, snapshot):
    data, observation = bucket.read(snapshot.id + ".tex", MAX_HISTORY_BYTES)
    text = data.decode("utf-8", errors="strict")
    if len(data) != snapshot.size or hashlib.sha256(data).hexdigest() != snapshot.sha256:
        raise HistoryError("History content does not match its recorded digest; not restored or pruned")
    return text, observation


def create_snapshot(source_path: Path, content: str, label: str, *, max_snapshots: int = MAX_SNAPSHOTS) -> HistorySnapshot | None:
    source = _source(source_path)
    if not isinstance(content, str) or not isinstance(label, str):
        raise HistoryError("History content and label must be text")
    data = content.encode("utf-8")
    if len(data) > MAX_HISTORY_BYTES or len(label) > 4096 or type(max_snapshots) is not int:
        raise HistoryError("History text/label/retention exceeds its supported bounds")
    maximum = min(MAX_SNAPSHOTS, max(1, max_snapshots))
    digest = hashlib.sha256(data).hexdigest()
    with project_write_lock(source.parent, blocking=False):
        with _Bucket(source, _bucket_for(source, source.parent), create=True) as bucket:
            initial = bucket.manifest()
            records = _records(initial, source, bucket.path)
            if records and records[0].sha256 == digest and records[0].label == label:
                _read_record(bucket, records[0])
                return None
            now = datetime.now(timezone.utc)
            ident = now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + digest[:10] + "-" + uuid.uuid4().hex[:12]
            snapshot = HistorySnapshot(ident, source, bucket.path / (ident + ".tex"), label, now, len(data), digest)
            keep = [snapshot, *records][:maximum]
            kept_ids = {record.id for record in keep}
            remove = {record.id: record for record in records if record.id not in kept_ids}
            # Unknown/changed retention candidates are never deleted just to meet
            # a count; validate them before publishing the bounded new index.
            observations = {ident: _read_record(bucket, record)[1] for ident, record in remove.items()}
            owned = bucket.write_new(snapshot.id + ".tex", data)
            published = False
            try:
                _read_record(bucket, snapshot)
                bucket.publish_manifest(keep, initial)
                published = True
                for ident, observation in observations.items():
                    try:
                        bucket.check()
                        bucket.unlink_owned(ident + ".tex", observation)
                    except OSError:
                        # A failed cleanup may leave an unindexed old object; it
                        # does not invalidate the complete new recovery entry.
                        pass
                return snapshot
            finally:
                if not published:
                    bucket.unlink_owned(snapshot.id + ".tex", owned)


def list_snapshots(source_path: Path) -> list[HistorySnapshot]:
    source = _source(source_path)
    result = []
    for name in dict.fromkeys((_bucket_for(source, source.parent), _legacy_bucket_for(source, source.parent))):
        try:
            with _Bucket(source, name) as bucket:
                result.extend(record for record in _records(bucket.manifest(), source, bucket.path)
                              if record.source_path == source)
        except FileNotFoundError:
            continue
    return sorted(result, key=lambda record: record.created_at, reverse=True)


def read_snapshot(snapshot: HistorySnapshot, *, expected_source: Path | None = None) -> str:
    source = _source(expected_source if expected_source is not None else snapshot.source_path)
    if snapshot.source_path != source:
        raise HistoryError("History does not belong to the selected source")
    allowed = {_bucket_for(source, source.parent), _legacy_bucket_for(source, source.parent)}
    if snapshot.snapshot_path.parent not in {source.parent / HISTORY_DIR / name for name in allowed}:
        raise HistoryError("History path is outside its expected source bucket")
    with _Bucket(source, snapshot.snapshot_path.parent.name) as bucket:
        _records(json.dumps([_entry(snapshot)]).encode("utf-8"), source, bucket.path)
        current = _records(bucket.manifest(), source, bucket.path)
        if snapshot not in current:
            raise HistoryError("Selected history entry changed or was removed")
        return _read_record(bucket, snapshot)[0]
