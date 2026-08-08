"""Portable project export (Sprint 6).

The exported package must compile away from ICSTeX, must not contain caches,
secrets, or absolute external paths, and must never write outside the target
directory. The manifest is deterministic (sorted files, stable format).
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat


EXCLUDED_DIRS = {".icstex", ".git", "__pycache__", ".latex_build"}
EXCLUDED_SUFFIXES = {
    ".log",
    ".aux",
    ".out",
    ".toc",
    ".fls",
    ".fdb_latexmk",
    ".synctex.gz",
    ".bbl",
    ".bcf",
    ".blg",
    ".run.xml",
    ".tmp",
    ".importing",
}
EXCLUDED_PREFIXES = (".env",)


@dataclass(frozen=True)
class ExportResult:
    target_dir: Path
    files: tuple[str, ...]
    manifest: dict


def safe_relative_path(relative: str) -> str | None:
    """Normalize and validate a project-relative path; None when unsafe."""

    candidate = relative.strip()
    if "\\" in candidate:
        return None
    if not candidate or candidate.startswith("/") or "\x00" in candidate:
        return None
    parts = candidate.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    if len(parts) > 1 and len(parts[0]) == 2 and parts[0][1] == ":":
        return None  # Windows drive letter
    return candidate


def _allowed(path: Path) -> bool:
    if any(part in EXCLUDED_DIRS for part in path.parts):
        return False
    name = path.name
    if name.startswith(EXCLUDED_PREFIXES):
        return False
    suffix = name.lower()
    for excluded in EXCLUDED_SUFFIXES:
        if suffix.endswith(excluded):
            return False
    return True


def export_package(project_dir: Path, target_dir: Path) -> ExportResult:
    project = project_dir.expanduser().resolve()
    target = target_dir.expanduser().resolve()
    candidates: list[tuple[Path, str]] = []
    for path in sorted(project.rglob("*")):
        relative = path.relative_to(project).as_posix()
        if path.is_symlink():
            raise ValueError(f"项目包含符号链接，已拒绝导出：{relative}")
        try:
            mode = path.stat(follow_symlinks=False).st_mode
        except OSError as exc:
            raise ValueError(f"无法安全检查导出源：{relative}") from exc
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(f"项目包含非普通文件，已拒绝导出：{relative}")
        canonical = path.resolve(strict=True)
        if not canonical.is_relative_to(project):
            raise ValueError(f"导出源越界：{relative}")
        if _allowed(path) and safe_relative_path(relative) is not None:
            candidates.append((path, relative))

    target.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    hashes: dict[str, str] = {}
    for path, relative in candidates:
        destination = target / relative
        if not destination.resolve().is_relative_to(target):
            raise ValueError(f"导出路径越界：{relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        hashes[relative] = _sha256(destination)
        copied.append(relative)

    manifest = {
        "format": "icstex-portable-package",
        "version": "1.0.0",
        "entry": "main.tex",
        "files": [{"path": relative, "sha256": hashes[relative]} for relative in copied],
        "excluded": [".icstex/cache", ".icstex/build", ".icstex/backups", ".env"],
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target / "README.md").write_text(
        "ICSTeX 可移植项目包\n\n本目录脱离 ICSTeX 后可直接用 latexmk 编译：\n"
        "```bash\nlatexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error main.tex\n```\n",
        encoding="utf-8",
    )
    return ExportResult(target_dir=target, files=tuple(copied), manifest=manifest)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
