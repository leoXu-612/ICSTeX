"""Read-only, bounded observations of recorded project data sources.

A matching digest describes file content, not provenance or data authenticity.
Missing-source lookup covers only same-extension CSV/XLSX files, not arbitrary
project content. No observation changes a record's baseline or imports data.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
from typing import Callable, Iterable

from app.core.project_dependencies import (
    GENERATED_SUFFIXES, INTERNAL_DIRS, _open_safe_input, safe_project_input,
)


@dataclass(frozen=True)
class SourceCheckLimits:
    max_file_bytes: int = 64 * 1024 * 1024
    max_total_bytes: int = 256 * 1024 * 1024
    max_entries: int = 2000
    max_records: int = 2000


class SourceCheckCancelled(Exception):
    pass


@dataclass
class _Budget:
    limits: SourceCheckLimits
    cancelled: Callable[[], bool]
    read_bytes: int = 0
    entries: int = 0

    def check(self):
        if self.cancelled():
            raise SourceCheckCancelled()


_EXCLUDED = INTERNAL_DIRS | {"node_modules", "venv", "build", "dist"}
_LOOKUP_SUFFIXES = {".csv", ".xlsx"}


def _excluded(parts):
    return any(part.startswith(".") or part.casefold() in _EXCLUDED for part in parts)


@dataclass(frozen=True)
class SourceRecord:
    sourceId: str
    kind: str
    relativePath: str
    baseSha256: str
    createdAt: str | None = None

    def to_dict(self) -> dict:
        result = {
            "sourceId": self.sourceId,
            "kind": self.kind,
            "relativePath": self.relativePath,
            "baseSha256": self.baseSha256,
        }
        if self.createdAt is not None:
            result["createdAt"] = self.createdAt
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "SourceRecord":
        return cls(
            sourceId=data["sourceId"],
            kind=data.get("kind", ""),
            relativePath=data.get("relativePath", ""),
            baseSha256=data.get("baseSha256", ""),
            createdAt=data.get("createdAt"),
        )


@dataclass(frozen=True)
class SourceStatus:
    state: str  # "ok" | "missing" | "moved" | "changed" | "unsafe" | "unknown"
    relativePath: str
    currentSha256: str | None = None
    message: str = ""


def _signature(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def hash_file(path: Path, *, project_dir: Path | None = None, _budget: _Budget | None = None) -> str:
    """Hash a regular, link-safe file; reject oversized or changed observations.

    The optional project boundary is used for every source check. Legacy fixture
    callers select the parent directory but still cannot follow a leaf link.
    Cancellation is cooperative between reads, not an OS I/O deadline.
    """
    budget = _budget or _Budget(SourceCheckLimits(), lambda: False)
    budget.check()
    if project_dir is None:
        project_dir = path.parent.resolve()
        path = project_dir / path.name
    digest = hashlib.sha256()
    with _open_safe_input(project_dir, path) as handle:
        before = os.fstat(handle.fileno())
        if before.st_size > budget.limits.max_file_bytes:
            raise OSError("源文件超过单文件读取上限")
        if before.st_size > budget.limits.max_total_bytes - budget.read_bytes:
            raise OSError("本次检查超过累计读取上限")
        consumed = 0
        while True:
            budget.check()
            # The extra byte detects growth; it is never accepted as a digest.
            remaining = min(budget.limits.max_file_bytes - consumed,
                            budget.limits.max_total_bytes - budget.read_bytes)
            chunk = handle.read(min(1024 * 1024, remaining + 1))
            if not chunk:
                break
            consumed += len(chunk)
            budget.read_bytes += len(chunk)
            if (consumed > budget.limits.max_file_bytes
                    or budget.read_bytes > budget.limits.max_total_bytes):
                raise OSError("源文件读取期间超过大小限制")
            digest.update(chunk)
        after = os.fstat(handle.fileno())
        try:
            current_path = path.stat(follow_symlinks=False)
        except OSError as exc:
            # An opened source disappearing is an unstable read, not an
            # initially absent source eligible for a moved-file search.
            raise OSError("读取后无法复核源路径，结果未知") from exc
        if (consumed != before.st_size or _signature(before) != _signature(after)
                or safe_project_input(project_dir, path) is None
                or _signature(before) != _signature(current_path)):
            raise OSError("源文件在读取期间变化；未接受摘要")
    budget.check()
    return digest.hexdigest()


def resolve_source_path(project_dir: Path, record: SourceRecord) -> Path:
    project = project_dir.expanduser().resolve()
    relative = Path(record.relativePath)
    if (not record.relativePath or "\x00" in record.relativePath or "\\" in record.relativePath
            or relative.is_absolute() or _excluded(relative.parts)):
        raise ValueError("来源必须是项目内的非隐藏相对文件路径")
    candidate = safe_project_input(project, relative)
    if candidate is None:
        raise ValueError("来源路径越界、为链接或属于内部/生成文件")
    return candidate


def check_source(project_dir: Path, record: SourceRecord, *, limits: SourceCheckLimits | None = None,
                 cancelled: Callable[[], bool] = lambda: False) -> SourceStatus:
    return check_sources(project_dir, (record,), limits=limits, cancelled=cancelled)[0]


def check_sources(project_dir: Path, records: Iterable[SourceRecord], *,
                  limits: SourceCheckLimits | None = None,
                  cancelled: Callable[[], bool] = lambda: False) -> tuple[SourceStatus, ...]:
    """One bounded batch, with one shared search for missing CSV/XLSX sources."""
    records = tuple(records)
    budget = _Budget(limits or SourceCheckLimits(), cancelled)
    budget.check()
    if len(records) > budget.limits.max_records:
        return tuple(SourceStatus("unknown", r.relativePath, message="来源数量超过本次检查上限")
                     for r in records)
    project = project_dir.expanduser().resolve()
    results: list[SourceStatus] = []
    missing: dict[int, tuple[str, str]] = {}
    for record in records:
        budget.check()
        try:
            path = resolve_source_path(project, record)
        except (ValueError, OSError) as exc:
            results.append(SourceStatus("unsafe", record.relativePath, message=str(exc)))
            continue
        if not re.fullmatch(r"[0-9a-fA-F]{64}", record.baseSha256):
            results.append(SourceStatus("unknown", record.relativePath, message="来源基线摘要无效"))
            continue
        baseline = record.baseSha256.lower()
        try:
            current = hash_file(path, project_dir=project, _budget=budget)
        except FileNotFoundError:
            suffix = path.suffix.lower()
            if suffix in _LOOKUP_SUFFIXES:
                missing[len(results)] = (baseline, suffix)
            results.append(SourceStatus("unknown", record.relativePath,
                                        message="原路径不存在；候选查找仅支持同扩展名 CSV/XLSX"))
            continue
        except OSError as exc:
            results.append(SourceStatus("unknown", record.relativePath, message=f"未完成读取：{exc}"))
            continue
        results.append(SourceStatus("ok" if current == baseline else "changed", record.relativePath,
                                    current, "与记录基线相同" if current == baseline else "源内容与记录基线不同"))
    if missing:
        matches: dict[tuple[str, str], list[Path]] = {key: [] for key in missing.values()}
        incomplete = ""
        try:
            for path in _candidate_files(project, budget, {key[1] for key in matches}):
                current = hash_file(path, project_dir=project, _budget=budget)
                key = (current, path.suffix.lower())
                if key in matches:
                    matches[key].append(path)
        except OSError as exc:
            incomplete = f"原路径不存在，候选查找未完成：{exc}"
        for index, key in missing.items():
            budget.check()
            record = records[index]
            candidates = matches[key]
            original_changed = ""
            try:
                resolve_source_path(project, record).lstat()
            except FileNotFoundError:
                pass
            except (OSError, ValueError):
                original_changed = "查找后无法复核原路径，结果未知"
            else:
                original_changed = "原路径在查找期间重新出现，结果未知；请刷新"
            if original_changed or incomplete or len(candidates) > 1:
                results[index] = SourceStatus("unknown", record.relativePath,
                                              message=original_changed or incomplete or "找到多个同内容候选，无法确定是否移动")
            elif candidates:
                relative = candidates[0].relative_to(project).as_posix()
                results[index] = SourceStatus("moved", relative, key[0],
                                              "找到一个同内容候选（可能移动）；未更新路径或基线")
            else:
                results[index] = SourceStatus("missing", record.relativePath,
                                              message="原路径不存在；限定范围内未找到同内容候选")
    budget.check()
    return tuple(results)


@contextmanager
def _scan_directory(project: Path, directory: Path):
    """Anchor POSIX enumeration too; a raced directory link is not traversed."""
    if directory != project and safe_project_input(project, directory) is None:
        raise PermissionError("候选目录不再是安全的项目路径")
    handle = None
    try:
        if os.scandir in os.supports_fd and os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            handle = os.open(directory.anchor, flags)
            for part in directory.parts[1:]:
                child = os.open(part, flags, dir_fd=handle)
                os.close(handle)
                handle = child
            with os.scandir(handle) as entries:
                yield entries
        else:
            # As in safe input opening, known links are refused; native Windows
            # reparse replacement races still need platform acceptance.
            with os.scandir(directory) as entries:
                yield entries
    finally:
        if handle is not None:
            os.close(handle)


def _candidate_files(project: Path, budget: _Budget, suffixes: set[str]):
    pending = [project]
    while pending:
        budget.check()
        directory = pending.pop()
        with _scan_directory(project, directory) as entries:
            for entry in entries:
                budget.check()
                budget.entries += 1
                if budget.entries > budget.limits.max_entries:
                    raise OSError("目录条目超过候选查找上限")
                if _excluded((entry.name,)) or entry.is_symlink():
                    continue
                path = directory / entry.name
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                elif (path.suffix.lower() in suffixes and path.suffix.lower() not in GENERATED_SUFFIXES
                      and entry.is_file(follow_symlinks=False)):
                    yield path
