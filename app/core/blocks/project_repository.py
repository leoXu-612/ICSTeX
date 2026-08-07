"""Atomic Block project load/save shared by the console and the main window.

Kept in ``app/core`` so it can be tested without Qt.  Load/save never mutate
the in-memory models; ``save_project`` performs same-directory atomic writes
so a failed write cannot corrupt an existing project.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from app.core.blocks.layout import LayoutNode
from app.core.blocks.registry import BlockRegistry
from app.core.blocks.store import BlockStore
from app.core.blocks.source_registry import SourceRecord
from app.core.blocks.theme import DocumentTheme, theme_from_dict


def load_project(project_dir: Path) -> dict:
    """Load registry/layout/sources/document theme from a Block project dir."""
    project = Path(project_dir).expanduser().resolve()
    metadata = project / ".icstex"
    registry = (
        BlockStore(metadata / "blocks.json").load()
        if (metadata / "blocks.json").is_file()
        else BlockRegistry()
    )

    layout: LayoutNode | None = None
    layouts_path = metadata / "layouts.json"
    if layouts_path.is_file():
        try:
            payload = json.loads(layouts_path.read_text(encoding="utf-8"))
            layouts = payload.get("layouts", [])
            if layouts:
                layout = LayoutNode.from_dict(layouts[0])
        except (OSError, ValueError, KeyError, TypeError):
            layout = None

    sources: list[SourceRecord] = []
    sources_path = metadata / "sources.json"
    if sources_path.is_file():
        try:
            payload = json.loads(sources_path.read_text(encoding="utf-8"))
            sources = [SourceRecord.from_dict(item) for item in payload.get("sources", [])]
        except (OSError, ValueError, KeyError, TypeError):
            sources = []

    document_theme = DocumentTheme(id="doc_default", name="Default")
    theme_path = project / "styles" / "document-theme.json"
    if theme_path.is_file():
        try:
            loaded = theme_from_dict(json.loads(theme_path.read_text(encoding="utf-8")))
            if isinstance(loaded, DocumentTheme):
                document_theme = loaded
        except (OSError, ValueError, KeyError):
            pass

    return {
        "registry": registry,
        "layout": layout,
        "sources": sources,
        "theme": document_theme,
        "document_theme": document_theme,
        "project_dir": project,
    }


def save_project(
    project_dir: Path,
    *,
    registry: BlockRegistry,
    layout: LayoutNode | None,
    sources: list[SourceRecord] | tuple[SourceRecord, ...] = (),
    document_theme: DocumentTheme | None = None,
) -> list[Path]:
    """Atomically persist the whole project; returns the written paths."""
    project = Path(project_dir).expanduser().resolve()
    metadata = project / ".icstex"
    metadata.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    blocks_path = metadata / "blocks.json"
    BlockStore(blocks_path).save(registry)
    written.append(blocks_path)

    layouts_path = metadata / "layouts.json"
    _atomic_write_json(
        layouts_path,
        {
            "schemaVersion": "1.0.0",
            "layouts": [layout.to_dict()] if layout is not None else [],
        },
    )
    written.append(layouts_path)

    sources_path = metadata / "sources.json"
    _atomic_write_json(sources_path, {"sources": [record.to_dict() for record in sources]})
    written.append(sources_path)

    if document_theme is not None:
        theme_path = project / "styles" / "document-theme.json"
        theme_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(theme_path, document_theme.to_dict())
        written.append(theme_path)
    return written


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
