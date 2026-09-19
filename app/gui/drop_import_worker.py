"""Background image copy for drag-and-drop import (phase 3).

Copying large (or not-yet-downloaded iCloud) images must not block the
PySide6 main thread. The worker copies each asset to a temporary file and
atomically renames it, then emits one result list for the whole drop.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading

from PySide6.QtCore import QThread, Signal

from app.core.image_assets import IMAGE_SUFFIXES, copy_image_atomic
from app.core.latex_insertions import (
    latex_relative_path,
    sanitize_asset_filename,
    unique_asset_path,
)


@dataclass
class DropCopyResult:
    source: Path
    destination: Path | None
    relative_path: str | None
    error: str | None


class DropCopyWorker(QThread):
    completed = Signal(list)

    def __init__(
        self,
        project_dir: Path,
        tex_path: Path,
        sources: list[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._project_dir = Path(project_dir).expanduser().resolve()
        self._tex_path = Path(tex_path)
        self._sources = [Path(source) for source in sources]
        self.thread_id: int | None = None

    def run(self) -> None:
        self.thread_id = threading.get_ident()
        figures = self._project_dir / "figures"
        results: list[DropCopyResult] = []
        for source in self._sources:
            results.append(self._copy_one(source, figures))
        self.completed.emit(results)

    def _copy_one(self, source: Path, figures: Path) -> DropCopyResult:
        if source.suffix.lower() not in IMAGE_SUFFIXES:
            return DropCopyResult(source, None, None, f"不支持的图片格式：{source.suffix or '未知'}")
        if not source.is_file():
            return DropCopyResult(source, None, None, "找不到图片文件。")

        try:
            if source.expanduser().resolve().is_relative_to(self._project_dir):
                # Already inside the project: reuse the existing relative path.
                relative = source.expanduser().resolve().relative_to(self._project_dir).as_posix()
                return DropCopyResult(source, source, relative, None)
            destination = unique_asset_path(figures, sanitize_asset_filename(source.name))
            copy_image_atomic(source, destination)
            relative = latex_relative_path(self._tex_path.resolve(), destination)
            return DropCopyResult(source, destination, relative, None)
        except OSError as exc:
            return DropCopyResult(
                source,
                None,
                None,
                f"复制失败（文件可能未从 iCloud 下载完成）：{exc}",
            )
