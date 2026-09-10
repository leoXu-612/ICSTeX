"""Read-only comparison of a captured Block model and its saved project files."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from app.core.blocks.assembly import build_latex_files
from app.core.blocks.layout import LayoutNode
from app.core.blocks.model import Block
from app.core.blocks.registry import BlockRegistry
from app.core.blocks.theme import theme_from_dict
from app.core.project_dependencies import read_project_bytes


@dataclass(frozen=True)
class BlockCheckInput:
    # JSON strings freeze model values before work leaves the GUI thread.
    blocks: str
    layouts: str
    sources: str
    theme: str
    allow_trusted_raw_latex: bool = False
    pending_property_drafts: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlockDiskCheck:
    saved: bool | None
    generated: bool | None
    # (path, bytes, internal-metadata flag); unavailable bytes remain unknown.
    observations: tuple[tuple[Path, bytes | None, bool], ...]


def inspect_block_inputs(scope: Path, model: BlockCheckInput) -> BlockDiskCheck:
    expected = {
        scope / ".icstex" / "blocks.json": json.loads(model.blocks),
        scope / ".icstex" / "layouts.json": json.loads(model.layouts),
        scope / ".icstex" / "sources.json": json.loads(model.sources),
        scope / "styles" / "document-theme.json": json.loads(model.theme),
    }
    observations = []
    saved: bool | None = True
    for path, payload in expected.items():
        internal = path.parent.name == ".icstex"
        data = None
        try:
            data = read_project_bytes(path, scope, allow_internal=internal)
            same = json.loads(data.decode("utf-8")) == payload
        except FileNotFoundError:
            data, same = None, False
        except (OSError, ValueError, UnicodeError):
            same = None
        observations.append((path, data, internal))
        saved = False if saved is False or same is False else None if same is None or saved is None else True

    registry = BlockRegistry([Block.from_dict(value) for value in json.loads(model.blocks)["blocks"]])
    layouts = json.loads(model.layouts)["layouts"]
    generated = build_latex_files(
        scope, registry=registry, layout=LayoutNode.from_dict(layouts[0]) if layouts else None,
        document_theme=theme_from_dict(json.loads(model.theme)),
        allow_trusted_raw_latex=model.allow_trusted_raw_latex,
    )
    matches: bool | None = True
    for path, text in generated.items():
        try:
            data = read_project_bytes(path, scope)
            same = data == text.encode("utf-8")
        except FileNotFoundError:
            data, same = None, False
        except (OSError, ValueError):
            data, same = None, None
        observations.append((path, data, False))
        matches = False if matches is False or same is False else None if same is None or matches is None else True
    return BlockDiskCheck(saved, matches, tuple(observations))


def block_inputs_unchanged(scope: Path, check: BlockDiskCheck) -> bool:
    for path, data, internal in check.observations:
        try:
            current = read_project_bytes(path, scope, allow_internal=internal)
        except (OSError, ValueError):
            current = None
        if current != data:
            return False
    return True
