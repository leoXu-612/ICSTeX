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
    target.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    hashes: dict[str, str] = {}
    for path in sorted(project.rglob("*")):
        if not path.is_file() or not _allowed(path):
            continue
        relative = path.relative_to(project).as_posix()
        if safe_relative_path(relative) is None:
            continue
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
