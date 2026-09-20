"""Reviewed, byte-preserving project ZIPs; no compilation or outside-scope reads."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import uuid
import zipfile

from app.core.artifact_export import EXPORT_CONTEXT_PATHS, ExportInputs, capture_export_inputs, recheck_export_inputs
from app.core.image_assets import IMAGE_SUFFIXES
from app.core.project_checkpoint import (
    _OutputParent, _cancel, _signature, _validate_paths, checkpoint_candidates,
)
from app.core.project_dependencies import (
    MAX_SOURCE_BYTES, _open_safe_input, safe_project_input, static_dependencies,
)
from app.core.submission_delivery import _SOURCE_SUFFIXES, source_path_allowed
from app.core.text_encoding import decode_latex_bytes

ARCHIVE_SUFFIXES = _SOURCE_SUFFIXES | IMAGE_SUFFIXES | {".dat", ".data", ".def", ".cfg", ".bbx", ".cbx", ".lbx",
                                      ".webp", ".bmp", ".tif", ".tiff", ".xls", ".ods"}
_SYSTEM_REFERENCES = {"documentclass", "LoadClass", "usepackage", "RequirePackage", "bibliographystyle"}


@dataclass(frozen=True)
class ProjectArchiveReview:
    inputs: ExportInputs
    root: str
    required: frozenset[str]
    warnings: tuple[str, ...]

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(entry.path for entry in self.inputs.files if entry.payload is not None)


def review_project_archive(project: Path, root: Path, *, cancelled=None) -> ProjectArchiveReview:
    """Worker-only local snapshot. Candidates are not a dependency-completeness claim."""
    project, root = Path(project), Path(root)
    if (project != project.resolve(strict=True) or project.is_symlink()
            or safe_project_input(project, root) != root or root.suffix.lower() not in {".tex", ".ltx"}):
        raise ValueError("请打开本地项目，并选择项目内的 LaTeX 主文件。")
    paths, warnings = checkpoint_candidates(project, cancelled=cancelled, extensions=ARCHIVE_SUFFIXES)
    paths = tuple(path for path in paths if source_path_allowed(path, suffixes=ARCHIVE_SUFFIXES))
    _validate_paths(paths)
    captured = capture_export_inputs(project, paths, cancelled=cancelled)
    values = {entry.path: entry.payload for entry in captured.files}
    relative = root.relative_to(project).as_posix()
    if values.get(relative) is None:
        raise ValueError("主文件尚未保存或无法读取，请先保存再导出。")
    if any(payload is None for payload in values.values()):
        raise OSError("清单中的文件已消失，请重新打开导出窗口。")

    def source_reader(path):
        _cancel(cancelled)
        payload = values.get(path.relative_to(project).as_posix())
        if payload is None:
            raise FileNotFoundError(path.name)
        if len(payload) > MAX_SOURCE_BYTES:
            raise OSError("源码超过依赖检查上限。")
        return decode_latex_bytes(payload).text

    dependencies = static_dependencies(root, project, source_reader=source_reader, max_references=2000)
    warnings = list(warnings)
    if not dependencies.complete:
        warnings.append("部分源码无法完整检查；不能确认是否还需要其他文件。")
    required = {relative, *(path for path in EXPORT_CONTEXT_PATHS if values.get(path) is not None)}
    for ref in dependencies.references:
        existing = {p.relative_to(project).as_posix() for p in ref.candidates
                    if values.get(p.relative_to(project).as_posix()) is not None}
        required.update(existing)
        location = f"{ref.source.relative_to(project).as_posix()}:{ref.line}"
        if Path(ref.value).is_absolute() or (len(ref.value) > 1 and ref.value[1] == ":"):
            warnings.append(f"{location} 使用绝对路径；换设备后需改成项目内的相对路径。")
        elif not existing:
            if ref.command in _SYSTEM_REFERENCES and not ref.unresolved and not ref.rejected_candidates:
                continue  # Installed TeX packages are provided by the destination's toolchain.
            detail = "项目外路径或链接未纳入" if ref.rejected_candidates else "文件缺失或动态引用无法确认"
            warnings.append(f"{location}：{detail}（{ref.command}）。")
    recheck_export_inputs(captured, cancelled=cancelled)
    return ProjectArchiveReview(captured, relative, frozenset(required), tuple(dict.fromkeys(warnings)))


def archive_selection_warnings(review: ProjectArchiveReview, paths: tuple[str, ...]) -> tuple[str, ...]:
    missing = review.required - set(paths)
    return (*review.warnings, *(f"未选中已识别的依赖：{path}" for path in sorted(missing)))


def export_project_archive(review: ProjectArchiveReview, paths: tuple[str, ...], target: Path,
                           *, accept_warnings=False, cancelled=None) -> Path:
    """Worker-only ZIP publication. Preserve originals and refuse existing output names."""
    _cancel(cancelled)
    _validate_paths(paths)
    if not paths or not set(paths) <= set(review.paths) or review.root not in paths:
        raise ValueError("请选择清单内的文件，并保留主文件。")
    if archive_selection_warnings(review, paths) and not accept_warnings:
        raise ValueError("工程存在未确认项，请先阅读提示再决定是否导出现有文件。")
    target = Path(target)
    if target.suffix.lower() != ".zip":
        raise ValueError("工程文件使用 .zip 后缀。")
    values = {entry.path: entry.payload for entry in review.inputs.files}
    payloads = [("project/" + path, values[path]) for path in sorted(paths)]
    if any(b"PRIVATE KEY-----" in payload for _, payload in payloads):
        raise ValueError("所选文件包含私钥标记，已取消导出。")
    notes = (
        "ICSTeX 工程文件\n\n解压后，用 ICSTeX 打开 project 文件夹，再打开主文件：" + review.root +
        "\n源码、图片和表格保留原始相对路径、编码与内容；未修改原工程。\n"
        "本包不是已验证的提交 PDF；不包含未保存草稿、个人历史、编译缓存或系统 TeX 环境。\n"
        "另一台电脑仍需安装 LaTeX 环境和原项目使用的字体。不会自动运行编译或安装软件。\n"
        "未改写绝对路径；动态引用和表格数据等额外文件请按导出清单核对。\n\n" +
        "\n".join(archive_selection_warnings(review, paths))
    ).encode("utf-8")
    manifest = {"entry": "project/" + review.root,
                "files": [{"path": path, "sha256": hashlib.sha256(payload).hexdigest()}
                          for path, payload in payloads]}
    payloads += [("README.txt", notes), ("files.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode())]
    with _OutputParent(target) as parent:
        name = ".icstex-archive.incomplete-" + uuid.uuid4().hex
        descriptor = parent.create_file(name)
        initial = os.fstat(descriptor)
        owned = initial.st_dev, initial.st_ino
        try:
            with os.fdopen(descriptor, "wb") as stream:
                with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                    for path, payload in payloads:
                        _cancel(cancelled)
                        archive.writestr(path, payload)
                stream.flush()
                os.fsync(stream.fileno())
                signature = _signature(os.fstat(stream.fileno()))
            # Read back staged members before making the new ZIP visible.
            with _open_safe_input(parent.path, parent.path / name, allow_internal=True) as stream:
                with zipfile.ZipFile(stream) as archive:
                    if archive.namelist() != [path for path, _ in payloads]:
                        raise OSError("工程包清单校验失败，未输出成品。")
                    for path, payload in payloads:
                        _cancel(cancelled)
                        if archive.read(path) != payload:
                            raise OSError("工程包内容校验失败，未输出成品。")
            recheck_export_inputs(review.inputs, cancelled=cancelled)
            _cancel(cancelled)
            parent.publish_file(name, signature)
            return parent.target
        finally:
            parent.remove_file(name, owned)
