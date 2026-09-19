"""Linked external data source registry (Sprint 3).

Source records keep a project-relative path plus a SHA-256 snapshot of the
last synced content. Refresh detects ok/missing/moved/changed states without
ever overwriting local edits; path resolution rejects escapes from the
project directory.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True)
class SourceRecord:
    sourceId: str
    kind: str
    relativePath: str
    baseSha256: str
    createdAt: str | None = None


@dataclass(frozen=True)
class SourceStatus:
    state: str  # "ok" | "missing" | "moved" | "changed" | "unsafe"
    relativePath: str
    currentSha256: str | None = None
    message: str = ""


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_source_path(project_dir: Path, record: SourceRecord) -> Path:
    project = project_dir.expanduser().resolve()
    candidate = (project / record.relativePath).resolve()
    if not candidate.is_relative_to(project):
        raise ValueError(f"数据源路径越出项目目录：{record.relativePath}")
    return candidate


def check_source(project_dir: Path, record: SourceRecord) -> SourceStatus:
    project = project_dir.expanduser().resolve()
    try:
        path = resolve_source_path(project, record)
    except ValueError as exc:
        return SourceStatus(state="unsafe", relativePath=record.relativePath, message=str(exc))
    if not path.is_file():
        located = _locate_by_hash(project, record.baseSha256, exclude=path)
        if located is not None:
            relative = located.relative_to(project).as_posix()
            return SourceStatus(
                state="moved",
                relativePath=relative,
                currentSha256=record.baseSha256,
                message=f"源文件已移动到 {relative}",
            )
        return SourceStatus(state="missing", relativePath=record.relativePath, message="源文件不存在")
    current = hash_file(path)
    if current == record.baseSha256:
        return SourceStatus(state="ok", relativePath=record.relativePath, currentSha256=current)
    return SourceStatus(
        state="changed",
        relativePath=record.relativePath,
        currentSha256=current,
        message="外部源内容已变化",
    )


def _locate_by_hash(project: Path, target: str, *, exclude: Path) -> Path | None:
    for path in project.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == exclude.resolve():
            continue
        try:
            if hash_file(path) == target:
                return path
        except OSError:
            continue
    return None
