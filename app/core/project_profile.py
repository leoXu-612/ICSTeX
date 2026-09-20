"""Optional, versioned local preferences; never source authority or executable code."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import uuid

from app.core.latex_tools import LaTeXEngine
from app.core.file_observation import file_signature
from app.core.project_dependencies import read_project_bytes, safe_project_input
from app.core.project_lock import project_write_lock

PROFILE_PATH = Path(".icstex/project-profile.json")
MAX_PROFILE_BYTES = 64 * 1024


@dataclass(frozen=True)
class ProjectProfile:
    enabled: bool = True
    template: str = ""
    engine: str = ""
    directories: tuple[str, ...] = ("figures", "tables", "bib")
    word_min: int | None = None
    word_max: int | None = None
    check_resources: bool = True
    check_references: bool = True

    @property
    def word_target(self):
        return (self.word_min, self.word_max) if self.enabled and (
            self.word_min is not None or self.word_max is not None) else None


@dataclass(frozen=True)
class ProfileSnapshot:
    path: Path
    profile: ProjectProfile | None
    digest: str | None
    error: str = ""
    stable: bool = True


class ProfileConflict(ValueError):
    pass


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate profile field")
        result[key] = value
    return result


def parse_profile(data: bytes) -> ProjectProfile:
    if len(data) > MAX_PROFILE_BYTES:
        raise ValueError("Profile exceeds 64 KiB")
    value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    keys = {"format", "version", *ProjectProfile.__dataclass_fields__}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("Unknown or missing profile fields; original preserved")
    if value.pop("format") != "icstex-project-profile" or type(value.get("version")) is not int or value.pop("version") != 1:
        raise ValueError("Unsupported profile format/version; original preserved")
    for key in ("enabled", "check_resources", "check_references"):
        if type(value[key]) is not bool:
            raise ValueError(f"{key} must be boolean")
    template = value["template"]
    if not isinstance(template, str) or len(template) > 160 or any(ord(c) < 32 for c in template):
        raise ValueError("Invalid template key")
    if value["engine"] not in ("", *(engine.value for engine in LaTeXEngine)):
        raise ValueError("Unknown engine")
    dirs = value["directories"]
    if not isinstance(dirs, list) or len(dirs) > 16:
        raise ValueError("At most 16 directory suggestions are allowed")
    for entry in dirs:
        if not isinstance(entry, str) or not entry or len(entry) > 160:
            raise ValueError("Invalid directory suggestion")
        path = PurePosixPath(entry)
        if not path.parts or path.is_absolute() or str(path) != entry or any(
                part in {".", "..", ".icstex", ".git", ".latex_build"} or part.endswith((".", " "))
                for part in path.parts) or any(c in '<>:"\\|?*' or ord(c) < 32 for c in entry):
            raise ValueError("Directory suggestions must be safe project-relative paths")
    if len(set(dirs)) != len(dirs):
        raise ValueError("Duplicate directory suggestion")
    for key in ("word_min", "word_max"):
        if value[key] is not None and (type(value[key]) is not int or not 0 <= value[key] <= 10_000_000):
            raise ValueError("Word target must be an integer from 0 to 10000000 or unset")
    if value["word_min"] is not None and value["word_max"] is not None and value["word_min"] > value["word_max"]:
        raise ValueError("Minimum word target exceeds maximum")
    value["directories"] = tuple(dirs)
    return ProjectProfile(**value)


def profile_bytes(profile: ProjectProfile) -> bytes:
    data = (json.dumps({"format": "icstex-project-profile", "version": 1,
                       **asdict(profile)}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    parse_profile(data)
    return data


def load_profile(root: Path) -> ProfileSnapshot:
    root = root.resolve()
    path = root / PROFILE_PATH
    if not root.is_dir() or safe_project_input(root, path, allow_internal=True) is None:
        return ProfileSnapshot(path, None, None, "Unsafe or unavailable profile path")
    before = file_signature(path)
    try:
        data = read_project_bytes(path, root, allow_internal=True, max_bytes=MAX_PROFILE_BYTES)
    except FileNotFoundError:
        after = file_signature(path)
        return ProfileSnapshot(path, None, "missing", stable=before == after)
    except (OSError, ValueError) as exc:
        return ProfileSnapshot(path, None, None, str(exc))
    digest = hashlib.sha256(data).hexdigest()
    try:
        confirmed = read_project_bytes(path, root, allow_internal=True, max_bytes=MAX_PROFILE_BYTES)
    except (OSError, ValueError) as exc:
        return ProfileSnapshot(path, None, digest, str(exc), False)
    stable = before == file_signature(path) and data == confirmed
    try:
        profile = parse_profile(data)
        return ProfileSnapshot(path, profile, digest, stable=stable)
    except (UnicodeError, ValueError, RecursionError) as exc:
        return ProfileSnapshot(path, None, digest, str(exc), stable)


def save_profile(root: Path, profile: ProjectProfile, *, expected: ProfileSnapshot) -> ProfileSnapshot:
    """Explicit single-file CAS. No template, engine, source or directory action.

    Recheck external changes immediately before replacement. Like existing CAS
    writers, this cannot lock arbitrary external programs out of the final syscall.
    POSIX replacement is anchored to the opened non-symlink metadata directory.
    """
    data = profile_bytes(profile)
    root = root.resolve(strict=True)
    path = root / PROFILE_PATH
    if expected.path != path or not expected.stable or expected.error:
        raise ProfileConflict("Profile cannot be safely edited; reload it first")
    with project_write_lock(root, blocking=False):
        if load_profile(root) != expected:
            raise ProfileConflict("Profile changed externally; original and draft preserved")
        path.parent.mkdir(exist_ok=True)
        if safe_project_input(root, path, allow_internal=True) is None:
            raise ProfileConflict("Profile path changed")
        directory = None
        temporary = None
        try:
            if os.rename in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
                directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
            if directory is not None:
                name = f".project-profile-{uuid.uuid4().hex}.tmp"
                fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
                temporary = path.parent / name
                handle = os.fdopen(fd, "wb")
            else:
                handle = tempfile.NamedTemporaryFile(dir=path.parent, prefix=".project-profile-", suffix=".tmp", delete=False)
                temporary = Path(handle.name)
            with handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
                if hasattr(os, "fchmod"):
                    os.fchmod(handle.fileno(), mode)
            if load_profile(root) != expected:
                raise ProfileConflict("Profile changed while saving; draft preserved")
            if directory is not None:
                opened, current = os.fstat(directory), path.parent.stat()
                if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                    raise ProfileConflict("Profile directory changed while saving")
                os.replace(temporary.name, path.name, src_dir_fd=directory, dst_dir_fd=directory)
            else:
                os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                if directory is not None:
                    os.unlink(temporary.name, dir_fd=directory)
                else:
                    temporary.unlink(missing_ok=True)
            if directory is not None:
                os.close(directory)
    result = load_profile(root)
    if result.digest != hashlib.sha256(data).hexdigest() or not result.stable:
        raise ProfileConflict("Profile changed after save; reload before continuing")
    return result
