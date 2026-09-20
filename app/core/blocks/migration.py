"""Pure deterministic conversion of the known legacy Block document.

No filesystem writes or compilation authority. Publishing and separately opening
a verified copy are caller actions; the original bytes accompany the candidate.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from app.core.blocks.ids import _encode
from app.core.blocks.layout import BlockSlot, LayoutNode, Size
from app.core.blocks.model import Block
from app.core.blocks.project_write import _json, _preserves
from app.core.blocks.schema import validate_block, validate_layout
from app.core.blocks.theme import DocumentTheme
from app.core.project_checkpoint import _relative
from app.core.project_recovery import parse_block_model


class MigrationError(ValueError):
    pass


@dataclass(frozen=True)
class LegacyConversion:
    original: bytes
    model: dict
    unmapped_keys: tuple[str, ...]


def _identity(prefix, entry, index, role):
    # Unknown creation time; deterministic 80-bit suffix in the existing ID form.
    seed = json.dumps([entry, index, role], sort_keys=True, ensure_ascii=False, allow_nan=False)
    digest = int.from_bytes(hashlib.sha256(seed.encode()).digest()[:10], "big")
    return prefix + "_" + "0" * 10 + _encode(digest, 16)


def _entries(data, key):
    value = data.get(key, [])
    if not isinstance(value, list) or len(value) > 2000 or any(not isinstance(e, dict) for e in value):
        raise MigrationError(f"旧格式 {key} 必须是有界对象列表。")
    return value


def _text(entry, key, default=None):
    value = entry.get(key, default)
    if not isinstance(value, str):
        raise MigrationError(f"旧格式 {key} 必须是文本，不能自动转换类型。")
    return value


def _completed(data, marker, expected):
    if len({alias for alias, _ in expected}) != len(expected):
        raise MigrationError("旧条目的迁移别名重复，无法确定逐项对应关系。")
    flag = data.get(marker, False)
    if type(flag) is not bool:
        raise MigrationError("旧迁移标记不是布尔值。")
    if flag:
        blocks = _entries(data, "blocks")
        for alias, kind in expected:
            matches = [b for b in blocks if b.get("alias") == alias and b.get("type") == kind]
            if len(matches) != 1:
                raise MigrationError("旧迁移完成标记与现有 Block 不一致；拒绝遗漏内容。")
    return flag


def _new_block(entry, index, role, kind, alias, content, semantic, extensions):
    return Block.from_dict({
        "id": _identity("blk", entry, index, role), "type": kind, "alias": alias,
        "content": content, "semantic": semantic, "provenance": {"kind": "imported"},
        "extensions": {**extensions, "legacyInput": deepcopy(entry)},
    }).to_dict()


def _layout_preserves(original, projected):
    # LayoutNode normalizes schema-validated sizes/weights from int to float.
    if isinstance(original, dict):
        return isinstance(projected, dict) and all(
            k in projected and _layout_preserves(v, projected[k]) for k, v in original.items())
    if isinstance(original, list):
        return isinstance(projected, list) and len(original) == len(projected) and all(
            _layout_preserves(a, b) for a, b in zip(original, projected))
    if type(original) in (int, float) and type(projected) in (int, float):
        return original == projected
    return type(original) is type(projected) and original == projected


@dataclass(frozen=True)
class MigrationPlan:
    version: int
    description: str

    def apply(self, data: dict) -> dict:
        raise NotImplementedError


class SideBySideFigureMigration(MigrationPlan):
    """Two image Blocks and one existing Row layout per legacy pair."""

    def __init__(self):
        super().__init__(version=1, description="并排图片迁移为两个 Image Block + Row 布局")

    def apply(self, data):
        result = deepcopy(data)
        legacy = _entries(result, "legacySideBySideFigures")
        expected = [(f"side-by-side-{i}-{side}", "image")
                    for i in range(len(legacy)) for side in ("left", "right")]
        if _completed(result, "legacySideBySideFiguresMigrated", expected) or not legacy:
            return result
        blocks = _entries(result, "blocks")
        layouts = _entries(result, "layouts")
        for index, entry in enumerate(legacy):
            children = []
            for side in ("left", "right"):
                source = _relative(_text(entry, side + "Image"))
                label = entry.get("label") if side == "right" else None
                if label is not None and not isinstance(label, str):
                    raise MigrationError("图片 label 必须是文本或 null。")
                block = _new_block(entry, index, side, "image", f"side-by-side-{index}-{side}",
                    {"source": source, "width": None},
                    {"role": "figure", "label": label, "caption": {"text": _text(entry, side + "Caption", "")}},
                    {"legacyPlacement": entry.get("placement")})
                blocks.append(block)
                children.append(BlockSlot(_identity("ins", entry, index, side), block["id"], minWidthPt=120))
            layouts.append(LayoutNode(id=_identity("lyt", entry, index, "row"), kind="row",
                gap=Size(8, "mm"), fallback={"strategy": "stackVertically"}, children=tuple(children)).to_dict())
        result.update(blocks=blocks, layouts=layouts, legacySideBySideFiguresMigrated=True)
        return result


class RawLatexMigration(MigrationPlan):
    """Keep snippet text verbatim; persisted trust never grants compilation."""

    def __init__(self):
        super().__init__(version=1, description="旧 LaTeX 片段迁移为 RawLatexBlock")

    def apply(self, data):
        result = deepcopy(data)
        legacy = _entries(result, "legacyLatexSnippets")
        aliases = [_text(entry, "alias", f"legacy-latex-{i}") for i, entry in enumerate(legacy)]
        if _completed(result, "legacyLatexSnippetsMigrated", [(a, "rawLatex") for a in aliases]) or not legacy:
            return result
        blocks = _entries(result, "blocks")
        for index, (entry, alias) in enumerate(zip(legacy, aliases)):
            blocks.append(_new_block(entry, index, "raw", "rawLatex", alias,
                {"latex": _text(entry, "latex"), "trusted": False},
                {"role": "raw-latex", "numbering": "none"}, {}))
        result.update(blocks=blocks, legacyLatexSnippetsMigrated=True)
        return result


def _convert(raw):
    if not isinstance(raw, bytes) or len(raw) > 4 * 1024 * 1024:
        raise MigrationError("旧格式元数据必须是原始字节，且不能超过 4 MiB。")
    data = _json(raw)
    # JSON exponent overflow (for example 1e999) is not parse_constant's input.
    json.dumps(data, allow_nan=False)
    if (not isinstance(data, dict) or data.get("format") != "icstex-legacy-project"
            or data.get("schemaVersion", "1.0.0") != "1.0.0"
            or type(data.get("migrationVersion", 0)) is not int
            or data.get("migrationVersion", 0) not in (0, 1)):
        raise MigrationError("未知项目格式或更新的迁移版本；原件保留。")
    known = {"format", "schemaVersion", "migrationVersion", "blocks", "layouts", "sources", "document_theme",
             "legacySideBySideFigures", "legacyLatexSnippets", "legacySideBySideFiguresMigrated",
             "legacyLatexSnippetsMigrated"}
    # The historical plans share version 1. Each marker is checked separately.
    working = RawLatexMigration().apply(SideBySideFigureMigration().apply(data))
    blocks = _entries(working, "blocks")
    layouts = _entries(working, "layouts")
    if len(blocks) + len(layouts) > 2000:
        raise MigrationError("转换对象超过 2000 项上限。")
    canonical_blocks = []
    for block in blocks:
        if validate_block(block):
            raise MigrationError("现有 Block 含未知字段或无效内容。")
        canonical = Block.from_dict(block).to_dict()
        if not _preserves(block, canonical):
            raise MigrationError("现有 Block 无法无损载入。")
        if canonical["type"] == "image":
            _relative(canonical["content"]["source"])
        canonical_blocks.append(canonical)
    ids = {b["id"] for b in canonical_blocks}
    used, instances, layout_ids = set(), set(), set()
    count = 0
    def visit(node, depth=0):
        nonlocal count
        count += 1
        if count > 2000 or depth > 32:
            raise MigrationError("布局节点或嵌套超过上限。")
        if isinstance(node, BlockSlot):
            if node.blockId not in ids or node.instanceId in instances:
                raise MigrationError("布局引用缺失或实例身份重复。")
            used.add(node.blockId)
            instances.add(node.instanceId)
        else:
            if node.id in layout_ids:
                raise MigrationError("布局身份重复。")
            layout_ids.add(node.id)
            for child in node.children:
                visit(child, depth + 1)
    children = []
    for layout in layouts:
        if validate_layout(layout):
            raise MigrationError("旧布局格式未知或无效。")
        node = LayoutNode.from_dict(layout)
        if not _layout_preserves(layout, node.to_dict()):
            raise MigrationError("旧布局无法无损载入。")
        visit(node)
        children.append(node)
    for block in canonical_blocks:
        if block["id"] not in used:
            node = BlockSlot(_identity("ins", block["id"], 0, "unplaced"), block["id"])
            visit(node)
            children.append(node)
    root = LayoutNode(id=_identity("lyt", [c.to_dict() for c in children], 0, "root"),
                      kind="column", children=tuple(children))
    if root.id in layout_ids:
        raise MigrationError("转换根布局身份冲突。")
    model = {"blocks": sorted(canonical_blocks, key=lambda b: b["id"]), "layout": root.to_dict(),
             "sources": working.get("sources", []),
             "document_theme": working.get("document_theme", DocumentTheme(id="doc_default", name="Default").to_dict())}
    loaded = parse_block_model(model)
    if loaded["registry"].validate_all():
        raise MigrationError("转换后的 Block 标签或引用不一致。")
    return LegacyConversion(raw, model, tuple(sorted(set(data) - known)))


def convert_legacy_document(raw: bytes) -> LegacyConversion:
    """Validate and project only the known envelope, without touching disk."""
    try:
        return _convert(raw)
    except MigrationError:
        raise
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        raise MigrationError(f"旧格式无法安全转换：{exc}") from exc


class MigrationRunner:
    """Retired in-place API. Use a reviewed new-copy migration instead."""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)

    def run(self, plans: list[MigrationPlan]):
        raise MigrationError("原地迁移已停用；请审阅后迁移到原项目之外的新副本。")


def legacy_fixture() -> dict:
    """A deterministic synthetic document; not evidence of student content."""
    return {
        "format": "icstex-legacy-project",
        "legacySideBySideFigures": [{"leftImage": "figures/a.png", "rightImage": "figures/b.png",
            "leftCaption": "A", "rightCaption": "B", "label": "fig:ab", "placement": "htbp"}],
        "legacyLatexSnippets": [{"alias": "old-formula", "latex": "E=mc^2"}],
    }
