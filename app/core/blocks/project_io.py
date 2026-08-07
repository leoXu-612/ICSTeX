"""Load a Block project (registry/layout/theme) from disk for the console."""
from __future__ import annotations

import json
from pathlib import Path

from app.core.blocks.layout import LayoutNode
from app.core.blocks.registry import BlockRegistry
from app.core.blocks.store import BlockStore
from app.core.blocks.theme import DocumentTheme, theme_from_dict


def load_block_project(project_dir: Path) -> dict:
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
    theme = DocumentTheme(id="doc_default", name="Default")
    theme_path = project / "styles" / "document-theme.json"
    if theme_path.is_file():
        try:
            loaded = theme_from_dict(json.loads(theme_path.read_text(encoding="utf-8")))
            if isinstance(loaded, DocumentTheme):
                theme = loaded
        except (OSError, ValueError, KeyError):
            pass
    return {
        "registry": registry,
        "layout": layout,
        "theme": theme,
        "document_theme": theme,
        "project_dir": project,
    }
