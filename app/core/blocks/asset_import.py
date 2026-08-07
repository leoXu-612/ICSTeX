"""Unified image asset import for Block projects (copy into the project,
never move or reference outside the project)."""
from __future__ import annotations

from pathlib import Path
import shutil


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".svg", ".bmp", ".tif", ".tiff"}


def is_image_path(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def import_image(project_dir: Path, source_path: Path) -> str:
    """Copy ``source_path`` into ``<project>/assets/images`` and return the
    project-relative path (posix).  The source file is never moved."""
    project = Path(project_dir).expanduser().resolve()
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"图片文件不存在：{source}")
    if not is_image_path(source):
        raise ValueError(f"不支持的图片类型：{source.suffix}")
    target_dir = project / "assets" / "images"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    stem = source.stem
    suffix = source.suffix
    index = 1
    while target.exists():
        target = target_dir / f"{stem} ({index}){suffix}"
        index += 1
    shutil.copy2(source, target)
    return target.relative_to(project).as_posix()
