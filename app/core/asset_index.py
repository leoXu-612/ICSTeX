"""Incremental asset index for project images (phase 2).

Unlike a full re-scan that re-extracts metadata on every refresh, the index
caches ``AssetRecord`` entries keyed by relative path and reuses them while
size/mtime are unchanged. New and modified files are the only ones that need
metadata extraction. The index persists atomically to
``.icstex/asset-index.json`` and is written once per refresh that changed it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Callable

from app.core.image_assets import (
    IGNORED_DIRS,
    IMAGE_SUFFIXES,
    ImageAsset,
    _graphics_references,
    _usage_count,
)


@dataclass
class AssetRecord:
    """One indexed image asset."""

    asset_id: str
    filename: str
    media_type: str
    size: int
    modified_time_ns: int
    width: int | None = None
    height: int | None = None


MetadataReader = Callable[[Path], tuple[int | None, int | None]]


class AssetIndex:
    """Size/mtime-keyed cache with diff tracking and atomic persistence."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir.expanduser().resolve()
        self._records: dict[str, AssetRecord] = {}
        self.last_diff: dict[str, list[str]] = {"added": [], "removed": [], "modified": []}
        self._dirty = False
        self._loaded = False
        self._index_path = self.project_dir / ".icstex" / "asset-index.json"

    def load(self) -> None:
        try:
            payload = json.loads(self._index_path.read_text(encoding="utf-8"))
            for raw in payload.get("records", []):
                record = AssetRecord(
                    asset_id=raw["asset_id"],
                    filename=raw["filename"],
                    media_type=raw["media_type"],
                    size=raw["size"],
                    modified_time_ns=raw["modified_time_ns"],
                    width=raw.get("width"),
                    height=raw.get("height"),
                )
                self._records[record.asset_id] = record
        except (OSError, ValueError, KeyError, TypeError):
            self._records.clear()
        self._loaded = True

    def save(self) -> None:
        """Atomic single-write persistence; no-op when nothing changed."""

        if not self._dirty or not self._records:
            return
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "project": str(self.project_dir),
            "records": [asdict(record) for record in sorted(self._records.values(), key=lambda r: r.asset_id)],
        }
        temporary = self._index_path.with_name(self._index_path.name + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self._index_path)
        self._dirty = False

    def scan(self, *, read_metadata: MetadataReader | None = None) -> dict[str, list[str]]:
        """Incremental scan; unchanged files reuse cached records.

        Returns the diff of added/removed/modified relative paths. Metadata
        extraction runs only for new or modified files.
        """

        seen: set[str] = set()
        added: list[str] = []
        removed: list[str] = []
        modified: list[str] = []
        for path in self.project_dir.rglob("*"):
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            if not (path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES):
                continue
            relative = path.relative_to(self.project_dir).as_posix()
            seen.add(relative)
            try:
                stat = path.stat()
            except OSError:
                continue
            cached = self._records.get(relative)
            if (
                cached is not None
                and cached.size == stat.st_size
                and cached.modified_time_ns == stat.st_mtime_ns
            ):
                continue
            record = AssetRecord(
                asset_id=relative,
                filename=path.name,
                media_type=path.suffix.lower(),
                size=stat.st_size,
                modified_time_ns=stat.st_mtime_ns,
            )
            if read_metadata is not None:
                record.width, record.height = read_metadata(path)
            self._records[relative] = record
            self._dirty = True
            if cached is None:
                added.append(relative)
            else:
                modified.append(relative)
        for relative in list(self._records):
            if relative not in seen:
                del self._records[relative]
                removed.append(relative)
                self._dirty = True
        self.last_diff = {"added": added, "removed": removed, "modified": modified}
        return self.last_diff

    def add_many(self, records: list[AssetRecord]) -> None:
        for record in records:
            self._records[record.asset_id] = record
        self._dirty = True

    def remove(self, asset_ids: list[str]) -> None:
        for asset_id in asset_ids:
            self._records.pop(asset_id, None)
        self._dirty = True

    def image_assets(self, *, current_text: str = "") -> list[ImageAsset]:
        references = _graphics_references(self.project_dir, current_text=current_text)
        assets = [
            ImageAsset(
                path=self.project_dir / record.asset_id,
                relative_path=record.asset_id,
                used_count=_usage_count(record.asset_id, references),
            )
            for record in self._records.values()
        ]
        return sorted(assets, key=lambda asset: (asset.used_count == 0, asset.relative_path.lower()))

    @property
    def was_cached(self) -> bool:
        """True when a persisted index existed and was loaded."""

        return self._loaded and bool(self._records)
