"""Explicit byte checkpoints and verified restore to a NEW directory.

This is selected-file recovery, not a filesystem snapshot, cloud backup, source
format migration or permission to apply drafts. No source file is ever written.
The caller owns GUI draft capture and pauses its cooperating write entrances.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import ctypes
import hashlib
from itertools import islice
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import unicodedata
import uuid
import zipfile

from app.core.project_dependencies import _open_safe_input, safe_project_input


MAX_FILES = 2000
MAX_DRAFTS = 200
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_DRAFT_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
_FORMAT = "icstex-project-checkpoint"
_METADATA = frozenset({".icstex/blocks.json", ".icstex/layouts.json",
                       ".icstex/sources.json", ".icstex/project-profile.json"})
_INTERNAL = frozenset({".git", ".hg", ".svn", ".venv", "venv", "__pycache__",
                       ".latex_build", ".icstex"})
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_DRAFT_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
_DEVICE = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)
_DRAFT_SUFFIX = {"source-text": ".txt", "block-state": ".json"}


class CheckpointCancelled(OSError):
    pass


@dataclass(frozen=True)
class DraftInput:
    id: str
    kind: str
    target: str | None
    payload: bytes


@dataclass(frozen=True)
class FileEntry:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class DraftEntry:
    id: str
    kind: str
    target: str | None
    sha256: str
    size: int


@dataclass(frozen=True)
class CheckpointInfo:
    created_at: str
    files: tuple[FileEntry, ...]
    drafts: tuple[DraftEntry, ...]

    def manifest(self) -> bytes:
        return _json_bytes({"format": _FORMAT, "version": 1,
                            "consistency": "selected-files-two-pass-byte-check",
                            "created_at": self.created_at,
                            "files": [asdict(entry) for entry in self.files],
                            "drafts": [asdict(entry) for entry in self.drafts]})


@dataclass(frozen=True)
class RestoreResult:
    directory: Path
    info: CheckpointInfo

    @property
    def project_dir(self) -> Path:
        return self.directory / "project"

    @property
    def drafts_dir(self) -> Path:
        return self.directory / "drafts"


def _cancel(cancelled):
    if cancelled is not None and cancelled():
        raise CheckpointCancelled("Checkpoint operation cancelled; original preserved")


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def _relative(value):
    if (not isinstance(value, str) or not value or len(value.encode("utf-8")) > 4096
            or "\\" in value or ":" in value or any(ord(c) < 32 for c in value)):
        raise ValueError("Invalid portable project-relative path")
    parts = value.split("/")
    if len(parts) > 32 or any(not p or p in {".", ".."} or p[-1] in " ." or _DEVICE.match(p) for p in parts):
        raise ValueError("Unsafe or nonportable project-relative path")
    if value not in _METADATA and any(part.casefold() in _INTERNAL for part in parts):
        raise ValueError("Private history, caches and repository internals are excluded")
    return value


def _validate_paths(paths):
    """Reject aliases of files AND implicit directories on portable restores."""
    seen = {}
    files = set()
    for raw in paths:
        path = _relative(raw)
        parts = PurePosixPath(path).parts
        for index in range(1, len(parts) + 1):
            prefix = "/".join(parts[:index])
            key = unicodedata.normalize("NFC", prefix).casefold()
            if key in seen and seen[key] != prefix:
                raise ValueError("Case or Unicode path collision; restore would be ambiguous")
            if key in files:
                raise ValueError("Duplicate or file/directory path collision")
            if index == len(parts) and key in seen:
                raise ValueError("File conflicts with an existing directory")
            seen[key] = prefix
        files.add(key)


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _check_signature(project, relative, expected):
    with _open_safe_input(project, project / relative, allow_internal=True) as stream:
        if _signature(os.fstat(stream.fileno())) != expected:
            raise OSError(f"Selected file changed: {relative}")


def _read_file(project, relative, cancelled=None):
    """Bounded original bytes with before/after descriptor and path identity."""
    _cancel(cancelled)
    with _open_safe_input(project, project / relative, allow_internal=True) as stream:
        initial = _signature(os.fstat(stream.fileno()))
        if initial[2] > MAX_FILE_BYTES:
            raise ValueError(f"Selected file exceeds 64 MiB: {relative}")
        chunks = []
        size = 0
        while True:
            _cancel(cancelled)
            chunk = stream.read(min(1024 * 1024, MAX_FILE_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                raise ValueError(f"Selected file exceeds 64 MiB: {relative}")
        if _signature(os.fstat(stream.fileno())) != initial:
            raise OSError(f"Selected file changed while reading: {relative}")
    _check_signature(project, relative, initial)
    return b"".join(chunks), initial


class _OutputParent:
    """Anchor one explicit existing output parent; never create its ancestors."""

    def __init__(self, target):
        raw = Path(target).expanduser().absolute()
        self.path = raw.parent.resolve(strict=True)
        self.target = self.path / raw.name
        if raw.name in {"", ".", ".."}:
            raise ValueError("Choose a new output name")
        self.fd = None
        self.identity = None

    def __enter__(self):
        info = self.path.stat()
        if not stat.S_ISDIR(info.st_mode):
            raise NotADirectoryError(self.path)
        self.identity = (info.st_dev, info.st_ino)
        if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
            self.fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            self.check()
            self.absent()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    @property
    def kwargs(self):
        return {"dir_fd": self.fd} if self.fd is not None else {}

    def name(self, name):
        return name if self.fd is not None else self.path / name

    def check(self):
        info = self.path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != self.identity
                or (hasattr(self.path, "is_junction") and self.path.is_junction())):
            raise OSError("Output parent changed; publication refused")
        if self.fd is not None:
            opened = os.fstat(self.fd)
            if (opened.st_dev, opened.st_ino) != self.identity:
                raise OSError("Output parent identity changed")

    def absent(self):
        try:
            os.stat(self.name(self.target.name), follow_symlinks=False, **self.kwargs)
        except FileNotFoundError:
            return
        raise FileExistsError(f"Output already exists; never overwritten: {self.target}")

    def create_file(self, name):
        self.check()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        return os.open(self.name(name), flags, 0o600, **self.kwargs)

    def remove_file(self, name, owned):
        try:
            info = os.stat(self.name(name), follow_symlinks=False, **self.kwargs)
            if (info.st_dev, info.st_ino) == owned:
                os.unlink(self.name(name), **self.kwargs)
        except FileNotFoundError:
            pass

    def check_owned(self, name, expected):
        info = os.stat(self.name(name), follow_symlinks=False, **self.kwargs)
        if _signature(info) != expected:
            raise OSError("Owned staging file changed; publication refused")

    def publish_file(self, name, expected):
        self.check()
        self.absent()
        self.check_owned(name, expected)
        if os.name == "nt":
            os.rename(self.path / name, self.target)
        else:
            kwargs = {"src_dir_fd": self.fd, "dst_dir_fd": self.fd} if self.fd is not None else {}
            os.link(self.name(name), self.name(self.target.name), follow_symlinks=False, **kwargs)
        published = os.stat(self.name(self.target.name), follow_symlinks=False, **self.kwargs)
        # link/rename may change ctime. Verify the actual published object's identity.
        if (published.st_dev, published.st_ino, published.st_size, published.st_mtime_ns) != expected[:4]:
            raise OSError("Published checkpoint changed; do not accept this output")


def _rename_directory_exclusive(parent, source):
    """Same-parent atomic publication; never emulate no-replace with a check."""
    parent.check()
    parent.absent()
    if os.name == "nt":
        os.rename(parent.path / source, parent.target)
        return
    if parent.fd is None:
        raise OSError("This platform cannot publish a restore directory exclusively")
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        function = getattr(libc, "renameatx_np", None)
        flags = 0x00000004  # RENAME_EXCL, macOS SDK sys/stdio.h.
    elif sys.platform.startswith("linux"):
        function = getattr(libc, "renameat2", None)
        flags = 1  # RENAME_NOREPLACE; unsupported libc/filesystems fail closed.
    else:
        function = None
        flags = 0
    if function is None:
        raise OSError("Exclusive directory rename is unavailable on this platform")
    function.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    function.restype = ctypes.c_int
    if function(parent.fd, os.fsencode(source), parent.fd, os.fsencode(parent.target.name), flags):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(parent.target))


def _draft_entries(drafts):
    result = []
    ids = set()
    for draft in drafts:
        if (not isinstance(draft, DraftInput) or not isinstance(draft.id, str)
                or not _DRAFT_ID.fullmatch(draft.id) or draft.id in ids
                or draft.kind not in _DRAFT_SUFFIX or type(draft.payload) is not bytes):
            raise ValueError("Invalid or duplicate checkpoint draft")
        if draft.target is not None:
            _relative(draft.target)
        if len(draft.payload) > MAX_DRAFT_BYTES:
            raise ValueError("Draft exceeds 16 MiB")
        draft.payload.decode("utf-8", errors="strict")
        ids.add(draft.id)
        result.append(DraftEntry(draft.id, draft.kind, draft.target,
                                 hashlib.sha256(draft.payload).hexdigest(), len(draft.payload)))
    return tuple(result)


def create_checkpoint(project, paths, target, *, drafts=(), cancelled=None) -> CheckpointInfo:
    """Capture a frozen, explicit file selection and separately supplied drafts.

    Two full byte passes plus final identity checks detect observed instability.
    No promise is made about files outside the selection or edits after capture.
    One explicit output is retained; no hidden history, pruning or background work.
    """
    project = Path(project).expanduser().resolve(strict=True)
    initial_root = project.stat()
    paths = tuple(islice(paths, MAX_FILES + 1))
    drafts = tuple(islice(drafts, MAX_DRAFTS + 1))
    if not 1 <= len(paths) <= MAX_FILES or len(drafts) > MAX_DRAFTS:
        raise ValueError("Choose 1-2000 disk files and at most 200 drafts")
    _validate_paths(paths)
    paths = tuple(sorted(paths))
    draft_entries = _draft_entries(drafts)
    total = sum(entry.size for entry in draft_entries)
    if total > MAX_TOTAL_BYTES:
        raise ValueError("Checkpoint drafts exceed 256 MiB")
    _cancel(cancelled)
    with _OutputParent(target) as parent:
        name = f".icstex-checkpoint.incomplete-{uuid.uuid4().hex}"
        descriptor = parent.create_file(name)
        owned_info = os.fstat(descriptor)
        owned = (owned_info.st_dev, owned_info.st_ino)
        observations = {}
        entries = []
        objects = set()
        try:
            with os.fdopen(descriptor, "wb") as stream:
                with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
                    for path in paths:
                        payload, observation = _read_file(project, path, cancelled)
                        total += len(payload)
                        if total > MAX_TOTAL_BYTES:
                            raise ValueError("Checkpoint selection exceeds 256 MiB")
                        digest = hashlib.sha256(payload).hexdigest()
                        entries.append(FileEntry(path, digest, len(payload)))
                        observations[path] = observation
                        if digest not in objects:
                            archive.writestr("objects/" + digest, payload)
                            objects.add(digest)
                    for draft, entry in zip(drafts, draft_entries):
                        _cancel(cancelled)
                        if entry.sha256 not in objects:
                            archive.writestr("objects/" + entry.sha256, draft.payload)
                            objects.add(entry.sha256)
                    info = CheckpointInfo(datetime.now(timezone.utc).isoformat(), tuple(entries), draft_entries)
                    manifest = info.manifest()
                    if len(manifest) > MAX_MANIFEST_BYTES:
                        raise ValueError("Checkpoint manifest exceeds 4 MiB")
                    archive.writestr("manifest.json", manifest)
                stream.flush()
                os.fsync(stream.fileno())
                staged_signature = _signature(os.fstat(stream.fileno()))
            for entry in entries:
                payload, observation = _read_file(project, entry.path, cancelled)
                if (observation != observations[entry.path]
                        or hashlib.sha256(payload).hexdigest() != entry.sha256):
                    raise OSError(f"Selected file changed between capture passes: {entry.path}")
            parent.check()
            if inspect_checkpoint(parent.path / name, cancelled=cancelled, _expected_signature=staged_signature) != info:
                raise OSError("Staged checkpoint verification failed")
            for path, observation in observations.items():
                _cancel(cancelled)
                _check_signature(project, path, observation)
            current = project.lstat()
            if (not stat.S_ISDIR(current.st_mode)
                    or (current.st_dev, current.st_ino) != (initial_root.st_dev, initial_root.st_ino)):
                raise OSError("Project directory changed during capture")
            _cancel(cancelled)
            parent.publish_file(name, staged_signature)
            return info
        finally:
            parent.remove_file(name, owned)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate checkpoint manifest field")
        result[key] = value
    return result


def _parse_manifest(payload):
    if len(payload) > MAX_MANIFEST_BYTES:
        raise ValueError("Checkpoint manifest exceeds 4 MiB")
    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
        if (not isinstance(value, dict) or set(value) != {"format", "version", "consistency", "created_at", "files", "drafts"}
                or value["format"] != _FORMAT or type(value["version"]) is not int or value["version"] != 1
                or value["consistency"] != "selected-files-two-pass-byte-check"):
            raise ValueError("Unknown checkpoint format/version; no migration or restore performed")
        if not isinstance(value["created_at"], str) or datetime.fromisoformat(value["created_at"]).tzinfo is None:
            raise ValueError("Invalid checkpoint creation time")
        if (not isinstance(value["files"], list) or not 1 <= len(value["files"]) <= MAX_FILES
                or not isinstance(value["drafts"], list) or len(value["drafts"]) > MAX_DRAFTS):
            raise ValueError("Invalid checkpoint entry count")
        files = tuple(FileEntry(**item) for item in value["files"])
        drafts = tuple(DraftEntry(**item) for item in value["drafts"])
        _validate_paths(entry.path for entry in files)
        ids = set()
        for entry in drafts:
            if (not isinstance(entry.id, str) or not _DRAFT_ID.fullmatch(entry.id)
                    or entry.id in ids or entry.kind not in _DRAFT_SUFFIX):
                raise ValueError("Unknown or duplicate draft")
            if entry.target is not None:
                _relative(entry.target)
            ids.add(entry.id)
        for entry in (*files, *drafts):
            limit = MAX_DRAFT_BYTES if isinstance(entry, DraftEntry) else MAX_FILE_BYTES
            if (type(entry.size) is not int or not 0 <= entry.size <= limit
                    or not isinstance(entry.sha256, str) or not _DIGEST.fullmatch(entry.sha256)):
                raise ValueError("Invalid checkpoint digest or bounded size")
        if sum(entry.size for entry in (*files, *drafts)) > MAX_TOTAL_BYTES:
            raise ValueError("Checkpoint expands beyond 256 MiB")
        return CheckpointInfo(value["created_at"], files, drafts)
    except (TypeError, KeyError, RecursionError, OverflowError) as exc:
        raise ValueError("Invalid checkpoint manifest") from exc


def _object_bytes(archive, digest, size, cancelled):
    _cancel(cancelled)
    member = archive.getinfo("objects/" + digest)
    if member.file_size != size:
        raise ValueError("Checkpoint object size mismatch")
    data = bytearray()
    with archive.open(member) as stream:
        while len(data) <= size:
            _cancel(cancelled)
            chunk = stream.read(min(1024 * 1024, size + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Checkpoint object digest mismatch")
    return bytes(data)


@contextmanager
def _verified_archive(path, cancelled=None, expected_signature=None):
    raw = Path(path).expanduser().absolute()
    parent = raw.parent.resolve(strict=True)
    path = parent / raw.name
    with _open_safe_input(parent, path, allow_internal=True) as stream:
        observed = _signature(os.fstat(stream.fileno()))
        if expected_signature is not None and observed != expected_signature:
            raise OSError("Staged archive identity changed before verification")
        if observed[2] > MAX_TOTAL_BYTES + MAX_MANIFEST_BYTES + 2 * 1024 * 1024:
            raise ValueError("Checkpoint archive exceeds its bounded size")
        with zipfile.ZipFile(stream, "r") as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if (len(names) > MAX_FILES + MAX_DRAFTS + 1 or len(set(names)) != len(names)
                    or "manifest.json" not in names or any(member.compress_type != zipfile.ZIP_STORED
                    or member.flag_bits & 1 or member.file_size < 0 for member in members)):
                raise ValueError("Unknown, compressed, encrypted or duplicate archive members")
            manifest_member = archive.getinfo("manifest.json")
            if manifest_member.file_size > MAX_MANIFEST_BYTES:
                raise ValueError("Checkpoint manifest exceeds 4 MiB")
            info = _parse_manifest(archive.read(manifest_member))
            expected = {"manifest.json", *("objects/" + entry.sha256 for entry in (*info.files, *info.drafts))}
            if set(names) != expected:
                raise ValueError("Missing or unrecognized checkpoint object")
            verified = set()
            for entry in (*info.files, *info.drafts):
                key = (entry.sha256, entry.size)
                if key not in verified:
                    _object_bytes(archive, *key, cancelled)
                    verified.add(key)
                if isinstance(entry, DraftEntry):
                    # The same object may also be a disk file; drafts are explicit UTF-8.
                    _object_bytes(archive, *key, cancelled).decode("utf-8", errors="strict")

            def check():
                _cancel(cancelled)
                if _signature(os.fstat(stream.fileno())) != observed:
                    raise OSError("Checkpoint archive changed while reading")
                _check_signature(parent, path.name, observed)

            check()
            yield archive, info, check


def inspect_checkpoint(path, *, cancelled=None, _expected_signature=None) -> CheckpointInfo:
    """Validate the complete archive, not merely its declared manifest."""
    try:
        with _verified_archive(path, cancelled, _expected_signature) as (_, info, _):
            return info
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("Checkpoint archive is corrupt or incomplete") from exc


@contextmanager
def _candidate_directory(project, directory):
    """Anchor name enumeration; discovered names never grant content access."""
    if safe_project_input(project, directory / "guard", allow_internal=True) is None:
        raise OSError("Linked candidate directory refused")
    initial = directory.lstat()
    descriptor = None
    try:
        if os.scandir in os.supports_fd and hasattr(os, "O_NOFOLLOW"):
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (initial.st_dev, initial.st_ino):
                raise OSError("Candidate directory changed before enumeration")
        if safe_project_input(project, directory / "guard", allow_internal=True) is None:
            raise OSError("Linked candidate parent refused")
        with os.scandir(descriptor if descriptor is not None else directory) as entries:
            yield entries
    finally:
        if descriptor is not None:
            os.close(descriptor)


def checkpoint_candidates(project, *, cancelled=None):
    """Bounded local name inventory, not dependency or cloud-availability proof."""
    project = Path(project).expanduser().resolve(strict=True)
    extensions = {".tex", ".ltx", ".bib", ".sty", ".cls", ".bst", ".png", ".jpg",
                  ".jpeg", ".svg", ".pdf", ".eps", ".csv", ".xlsx"}
    paths, warnings, pending = [], [], [(project, 0)]
    visited = 0
    while pending:
        directory, depth = pending.pop()
        _cancel(cancelled)
        try:
            with _candidate_directory(project, directory) as entries:
                for entry in entries:
                    _cancel(cancelled)
                    visited += 1
                    if visited > 10000 or len(paths) >= MAX_FILES - len(_METADATA):
                        return tuple(sorted(paths)), ("目录清单达到上限；未列出的文件不在检查点内。",)
                    path = directory / entry.name
                    if entry.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                        warnings.append("有链接被排除；清单不是完整项目备份。")
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.casefold() not in _INTERNAL and not entry.name.startswith("."):
                            if depth < 31:
                                pending.append((path, depth + 1))
                            else:
                                warnings.append("目录深度超限；清单不完整。")
                    elif entry.is_file(follow_symlinks=False):
                        relative = path.relative_to(project).as_posix()
                        if Path(relative).suffix.lower() in extensions or relative == "styles/document-theme.json":
                            _relative(relative)
                            paths.append(relative)
        except CheckpointCancelled:
            raise
        except (OSError, ValueError):
            warnings.append("部分本地目录不可读或路径不兼容；可用性未知。")
    for relative in sorted(_METADATA):
        path = project / relative
        # Actual opening, link refusal and availability are verified at capture.
        if path.exists() or path.is_symlink():
            paths.append(relative)
    return tuple(sorted(paths)), tuple(dict.fromkeys(warnings))


def checkpoint_review(path, *, cancelled=None):
    """Validate all bytes and return bounded, explicitly truncated draft previews."""
    try:
        with _verified_archive(path, cancelled) as (archive, info, check):
            previews = {}
            for entry in info.drafts:
                value = _object_bytes(archive, entry.sha256, entry.size, cancelled).decode("utf-8")
                previews[entry.id] = value[:64000] + ("\n[预览截断；完整草稿将在独立 drafts 目录恢复。]" if len(value) > 64000 else "")
            check()
            return info, previews
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("Checkpoint archive is corrupt or incomplete") from exc


def _write_restored(directory, relative, payload, *, directory_fd=None):
    """Exclusive file creation in an owned staging directory; no extractall."""
    parts = PurePosixPath(relative).parts
    handles = []
    try:
        if directory_fd is not None:
            parent = directory_fd
            for part in parts[:-1]:
                try:
                    os.mkdir(part, 0o700, dir_fd=parent)
                except FileExistsError:
                    pass
                parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                handles.append(parent)
            descriptor = os.open(parts[-1], os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        else:
            path = directory / relative
            # Windows fallback: reject observed reparse points; native races remain
            # a separate platform acceptance item, not a POSIX-equivalent claim.
            current = directory
            for part in parts[:-1]:
                current /= part
                current.mkdir(mode=0o700, exist_ok=True)
                if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
                    raise OSError("Restore staging contains a link")
            descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        with os.fdopen(descriptor, "w+b") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            stream.seek(0)
            if hashlib.sha256(stream.read(len(payload) + 1)).digest() != hashlib.sha256(payload).digest():
                raise OSError("Restored file readback failed")
            return _signature(os.fstat(stream.fileno()))
    finally:
        for handle in reversed(handles):
            os.close(handle)


def _verify_restored_tree(directory, expected_files, directory_fd):
    """Reject extra files/directories, links and missing entries before publish."""
    expected_dirs = {""}
    for relative in expected_files:
        parts = PurePosixPath(relative).parts
        expected_dirs.update("/".join(parts[:i]) for i in range(1, len(parts)))
    found_files, found_dirs = set(), set()

    def visit(relative, descriptor):
        found_dirs.add(relative)
        current = directory / relative
        with os.scandir(descriptor if descriptor is not None else current) as entries:
            for entry in entries:
                name = (relative + "/" if relative else "") + entry.name
                value = entry.stat(follow_symlinks=False)
                if stat.S_ISREG(value.st_mode) and name in expected_files:
                    found_files.add(name)
                elif stat.S_ISDIR(value.st_mode) and name in expected_dirs:
                    if descriptor is not None:
                        child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                        try:
                            visit(name, child)
                        finally:
                            os.close(child)
                    else:
                        if (current / entry.name).is_symlink() or (hasattr(current / entry.name, "is_junction")
                                and (current / entry.name).is_junction()):
                            raise OSError("Restore staging contains a link")
                        visit(name, None)
                else:
                    raise OSError("Restore staging contains an unlisted entry or link")
    visit("", directory_fd)
    if found_files != set(expected_files) or found_dirs != expected_dirs:
        raise OSError("Restore staging is incomplete")


def restore_checkpoint(path, target, *, cancelled=None, expected_info=None) -> RestoreResult:
    """Restore bytes under NEW target/project, drafts under target/drafts.

    Unsupported platforms/filesystems fail closed before directory publication.
    Interrupted staging names explicitly say incomplete; never open them as a
    successful restored project. A successful restore does not switch projects.
    """
    try:
        with _verified_archive(path, cancelled) as (archive, info, check_archive):
            if expected_info is not None and info != expected_info:
                raise ValueError("Checkpoint changed since review; no restore performed")
            with _OutputParent(target) as parent:
                name = f".icstex-restore.incomplete-{uuid.uuid4().hex}"
                os.mkdir(parent.name(name), mode=0o700, **parent.kwargs)
                directory = parent.path / name
                owned_info = os.stat(parent.name(name), follow_symlinks=False, **parent.kwargs)
                owned = (owned_info.st_dev, owned_info.st_ino)
                directory_fd = None
                try:
                    if parent.fd is not None:
                        directory_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent.fd)
                        opened = os.fstat(directory_fd)
                        if (opened.st_dev, opened.st_ino) != owned:
                            raise OSError("Restore staging directory changed")
                    written = {}
                    def write(relative, payload):
                        observation = _write_restored(directory, relative, payload, directory_fd=directory_fd)
                        written[relative] = (hashlib.sha256(payload).hexdigest(), observation)

                    for entry in info.files:
                        payload = _object_bytes(archive, entry.sha256, entry.size, cancelled)
                        write("project/" + entry.path, payload)
                    for entry in info.drafts:
                        payload = _object_bytes(archive, entry.sha256, entry.size, cancelled)
                        write("drafts/" + entry.id + _DRAFT_SUFFIX[entry.kind], payload)
                    write("manifest.json", info.manifest())
                    write("README.txt", (
                        "Selected-file recovery copy. A directory named .icstex-restore.incomplete-*\n"
                        "is NOT a published or accepted restore, even if it contains this file.\n"
                        "Only after successful final publication, open project/ explicitly.\n"
                        "Drafts in drafts/ are separate UTF-8 recovery copies; never applied automatically.\n"
                        "Only manifest-listed files are covered. No permissions, timestamps, external\n"
                        "dependencies or independent/cloud backup are implied. Original project unchanged.\n"
                    ).encode("utf-8"))
                    parent.check()
                    current = directory.lstat()
                    if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != owned:
                        raise OSError("Restore staging directory changed")
                    for relative, (digest, observation) in written.items():
                        payload, current = _read_file(directory, relative, cancelled)
                        if current != observation or hashlib.sha256(payload).hexdigest() != digest:
                            raise OSError("Restored file changed before final publication")
                    for relative, (_, observation) in written.items():
                        _cancel(cancelled)
                        _check_signature(directory, relative, observation)
                    _verify_restored_tree(directory, written, directory_fd)
                    check_archive()
                    current = os.stat(parent.name(name), follow_symlinks=False, **parent.kwargs)
                    if (current.st_dev, current.st_ino) != owned:
                        raise OSError("Restore staging directory changed before publication")
                    _cancel(cancelled)
                    _rename_directory_exclusive(parent, name)
                    return RestoreResult(parent.target, info)
                finally:
                    if directory_fd is not None:
                        os.close(directory_fd)
                    # Do not recursively delete a path substituted by another writer.
                    # fd-safe cleanup only; on other platforms leave an explicitly
                    # incomplete directory for manual inspection after failure.
                    if parent.fd is not None and shutil.rmtree.avoids_symlink_attacks:
                        try:
                            current = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
                            if (current.st_dev, current.st_ino) == owned:
                                shutil.rmtree(name, dir_fd=parent.fd)
                        except FileNotFoundError:
                            pass
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("Checkpoint archive is corrupt or incomplete") from exc
