from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import tempfile

from app.core.project_scan import iter_project_files

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg"}
IGNORED_DIRS = {".latex_build", ".icstex", "__pycache__"}
GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}")


@dataclass(frozen=True)
class ImageAsset:
    path: Path
    relative_path: str
    used_count: int


def copy_image_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def scan_image_assets(project_dir: Path, *, current_text: str = "") -> list[ImageAsset]:
    root = project_dir.expanduser().resolve()
    references = _graphics_references(root, current_text=current_text)
    assets: list[ImageAsset] = []
    for path in _iter_image_files(root):
        rel = path.relative_to(root).as_posix()
        used_count = _usage_count(rel, references)
        assets.append(ImageAsset(path=path, relative_path=rel, used_count=used_count))
    return sorted(assets, key=lambda asset: (asset.used_count == 0, asset.relative_path.lower()))


def _graphics_references(root: Path, *, current_text: str) -> list[str]:
    references: list[str] = []
    references.extend(_graphics_in_text(current_text))
    for path in iter_project_files(root, ignored_dirs=IGNORED_DIRS):
        if path.suffix.lower() != ".tex":
            continue
        try:
            references.extend(_graphics_in_text(path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return references


def _graphics_in_text(text: str) -> list[str]:
    return [match.group(1).strip().replace("\\", "/") for match in GRAPHICS_RE.finditer(text)]


def _usage_count(relative_path: str, references: list[str]) -> int:
    rel_no_suffix = str(Path(relative_path).with_suffix("")).replace("\\", "/")
    count = 0
    for reference in references:
        ref_no_suffix = str(Path(reference).with_suffix("")).replace("\\", "/")
        if reference == relative_path or ref_no_suffix == rel_no_suffix:
            count += 1
    return count


def _iter_image_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in iter_project_files(root, ignored_dirs=IGNORED_DIRS):
        if path.suffix.lower() in IMAGE_SUFFIXES:
            files.append(path)
    return files
