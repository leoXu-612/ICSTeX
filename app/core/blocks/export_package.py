"""Byte-consistent portable source copy; not a reviewed submission certificate.

Only bounded, supported source/material names are selected by this legacy API.
GUI submission provides explicit file review instead. Name filtering is not a
privacy or complete-dependency guarantee; external TeX/fonts are not bundled.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from app.core.artifact_export import (
    EXPORT_CONTEXT_PATHS, capture_export_inputs, recheck_export_inputs,
)
from app.core.project_checkpoint import (
    MAX_TOTAL_BYTES, _publish_payloads, _validate_paths, checkpoint_candidates,
)
from app.core.submission_delivery import _SOURCE_SUFFIXES, source_path_allowed


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


def _candidates(project):
    paths, warnings = checkpoint_candidates(project, extensions=_SOURCE_SUFFIXES, include_metadata=False)
    if warnings:
        raise ValueError("导出清单不完整或含符号链接；请先处理：" + " ".join(warnings))
    selected = tuple(path for path in paths if source_path_allowed(path)
                     and not path.startswith(".icstex/"))
    _validate_paths(selected)
    if not selected:
        raise ValueError("没有可导出的受支持源码或材料。")
    return selected


def export_package(project_dir: Path, target_dir: Path, *, check_target=None, allow_empty=True) -> ExportResult:
    """Preserve legacy root-level source files and optional empty-stage callers.

    Nonempty targets are always refused. Existing empty staging directories may
    be replaced, not preserved by inode; failure restores emptiness where still
    possible without replacing a late owner. Actual final publication is exclusive.
    """
    project = Path(project_dir).expanduser().resolve(strict=True)
    raw_target = Path(target_dir).expanduser().absolute()
    target = raw_target.parent.resolve(strict=False) / raw_target.name
    consume_empty = allow_empty and target.exists()
    if target.is_relative_to(project) or project.is_relative_to(target):
        raise ValueError("导出目标不能与项目目录重叠。")
    selected = _candidates(project)
    captured = capture_export_inputs(project, set(selected) | set(EXPORT_CONTEXT_PATHS))
    values = {entry.path: entry.payload for entry in captured.files}
    if any(values[path] is None for path in selected):
        raise OSError("选定导出文件已消失。")
    if any(b"PRIVATE KEY-----" in values[path] for path in selected):
        raise ValueError("选定文件含私钥标记，已拒绝导出。")
    manifest = {
        "format": "icstex-portable-package",
        "version": "1.0.0",
        "entry": "main.tex",
        "files": [{"path": path, "sha256": hashlib.sha256(values[path]).hexdigest()} for path in selected],
        "excluded": [".icstex", ".git", ".env", ".venv", "venv", "__pycache__", ".latex_build",
                     "hidden directories", "private names and key suffixes", "logs and unsupported suffixes"],
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    instructions = (
        "ICSTeX 可移植源码副本（不是 GUI 准备提交审阅或 FINAL 证明）\n\n"
        "原始文件保持相对路径、编码和换行。交付清单位于 .icstex-package/manifest.json；\n"
        "若原项目已有 README.md 或 manifest.json，它们不会被生成说明覆盖。\n"
        "此旧接口仅按保守文件规则纳入源码/材料，不提供逐文件审阅；需逐文件选择时使用 GUI 准备提交。\n"
        "动态/外部依赖及个人信息未获完整确认，文件名过滤不证明内容无隐私。\n"
        "请自备 TeX distribution、所需字体/宏包，并按项目真实引擎编译 main.tex；\n"
        "ICSTeX 生成的 Block 项目使用 XeLaTeX；普通项目以作者指定引擎为准。\n"
        "禁用项目钩子和 shell escape，例如 pdfLaTeX 项目：\n"
        "latexmk -norc -pdf -interaction=nonstopmode -halt-on-error -file-line-error -no-shell-escape main.tex\n"
        "此副本不包含个人历史或未保存草稿，也不保证跨环境排版字节相同。\n"
    ).encode("utf-8")
    payloads = [(path, values[path]) for path in selected]
    payloads.extend(((".icstex-package/manifest.json", manifest_bytes),
                     (".icstex-package/README.txt", instructions)))
    occupied = {path.split("/")[0].casefold() for path in selected}
    # Retain old aliases where free; never overwrite a source file or directory.
    if "manifest.json" not in occupied:
        payloads.append(("manifest.json", manifest_bytes))
    if "readme.md" not in occupied:
        payloads.append(("README.md", instructions))
    _validate_paths([path for path, _ in payloads])
    if sum(len(payload) for _, payload in payloads) > MAX_TOTAL_BYTES:
        raise ValueError("导出副本超过 256 MiB 上限。")

    def recheck():
        recheck_export_inputs(captured)
        if _candidates(project) != selected:
            raise OSError("导出文件清单发生变化。")
        if check_target is not None:
            check_target()

    recheck()
    target.parent.mkdir(parents=True, exist_ok=True)
    _publish_payloads(target, payloads, check_source=recheck,
        prefix=".icstex-delivery.incomplete-", allow_empty=consume_empty)
    return ExportResult(target_dir=target, files=selected, manifest=manifest)
