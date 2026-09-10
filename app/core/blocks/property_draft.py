"""Explicit, base-checked property drafts; no Qt, I/O or automatic application."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace

from app.core.blocks.layout import BlockSlot, LayoutNode, Size
from app.core.blocks.layout_solver import MM_PER_INCH, PT_PER_INCH, size_to_pt
from app.core.blocks.table_model import DATA_TYPES, TableData


def table_projection(content: dict) -> dict:
    """Validate the editable table shape; do not normalize the original bytes."""
    if content.get("tableVersion") != "1.0.0":
        raise ValueError("未知表格版本，原内容保留。")
    for key in ("columns", "rows"):
        items = content.get(key)
        if (not isinstance(items, list) or any(not isinstance(item, dict)
                or not isinstance(item.get("id"), str) or not item["id"] for item in items)):
            raise ValueError("表格缺少明确的行列 ID，不能安全绑定单元格。")
    header = content.get("header", {})
    if (not isinstance(header, dict) or type(header.get("rowCount", 1)) is not int
            or header.get("rowCount", 1) < 0 or type(header.get("repeatOnPageBreak", True)) is not bool):
        raise ValueError("表头字段格式未知，原内容保留。")
    data = TableData.from_content_dict(content)
    columns = [column.id for column in data.columns]
    rows = [row.id for row in data.rows]
    if (any(not isinstance(value, str) or not value for value in columns + rows)
            or len(set(columns)) != len(columns) or len(set(rows)) != len(rows)):
        raise ValueError("表格行列 ID 无效或重复，不能安全绑定单元格。")
    if len(columns) > 200 or len(rows) > 5000 or len(columns) * len(rows) > 100000:
        raise ValueError("表格超过本地编辑器的行列或单元格限制。")
    if (any(column.dataType not in DATA_TYPES for column in data.columns)
            or any(cell.kind not in DATA_TYPES for row in data.rows for cell in row.cells.values())):
        raise ValueError("未知表格单元格类型，原内容保留。")
    issues = data.validate()
    if issues:
        raise ValueError(issues[0])
    return data.to_content_dict()


def apply_table_projection(original: dict, before: dict, after: dict) -> dict:
    """Apply local projection differences, preserving unedited opaque fields.

    The caller checks the exact captured Block first. This is not an external
    three-way merge: stable row/column IDs only preserve fields the editor does
    not model while applying deliberate edits/deletions to the captured object.
    """
    result = deepcopy(original)
    for key in before.keys() - after.keys():
        result.pop(key, None)
    for key, value in after.items():
        if key in before and value == before[key]:
            continue
        if key in ("rows", "columns") and key in before:
            old = {item["id"]: item for item in result.get(key, [])}
            projected = {item["id"]: item for item in before[key]}
            result[key] = [apply_table_projection(old[item["id"]], projected[item["id"]], item)
                           if item["id"] in old and item["id"] in projected else deepcopy(item)
                           for item in value]
        elif isinstance(value, dict) and isinstance(before.get(key), dict) and isinstance(result.get(key), dict):
            result[key] = apply_table_projection(result[key], before[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def layout_gap_mm(layout: LayoutNode) -> float:
    return size_to_pt(layout.gap) * MM_PER_INCH / PT_PER_INCH


@dataclass(frozen=True)
class PropertyDraft:
    kind: str
    target_id: str
    label: str
    base: dict
    initial: dict
    values: dict

    @property
    def key(self) -> tuple[str, str]:
        return self.kind, self.target_id

    @property
    def changed(self) -> dict:
        return {key: deepcopy(value) for key, value in self.values.items()
                if value != self.initial.get(key)}


def find_layout(layout: LayoutNode | None, node_id: str | None = None,
                slot_id: str | None = None) -> LayoutNode | None:
    if layout is None:
        return None
    if node_id == layout.id or any(isinstance(c, BlockSlot) and c.instanceId == slot_id
                                   for c in layout.children):
        return layout
    for child in layout.children:
        if isinstance(child, LayoutNode):
            found = find_layout(child, node_id, slot_id)
            if found is not None:
                return found
    return None


def draft_conflict(draft: PropertyDraft, registry, layout) -> str:
    target = (registry.get(draft.target_id) if draft.kind in ("block", "table", "table_cell", "formula")
              else find_layout(layout, draft.target_id))
    if target is None or target.to_dict() != draft.base:
        return f"{draft.label} 的原对象已变化或删除；草稿保留，请比较内容后重新编辑。"
    return ""


def prepare_drafts(drafts, registry, layout):
    """Validate every base before computing any applied patch (no mutations)."""
    block_patches = {}
    layout_patches = {}
    for draft in drafts:
        if draft.kind == "table_cell":
            raise ValueError("请先结束表格单元格编辑；输入仍保留。")
        conflict = draft_conflict(draft, registry, layout)
        if conflict:
            raise ValueError(conflict)
        changed = draft.changed
        if draft.kind in ("block", "table", "formula"):
            block = registry.get(draft.target_id)
            patch = block_patches.get(block.id, {})
            if "alias" in changed:
                alias = str(changed.pop("alias")).strip()
                if not alias:
                    raise ValueError("别名不能为空；草稿仍保留。")
                patch["alias"] = alias
            if changed:
                content = deepcopy(patch.get("content", block.content))
                if draft.kind == "table":
                    try:
                        table_projection(draft.values)
                        content = apply_table_projection(content, draft.initial, draft.values)
                    except (KeyError, TypeError, IndexError, OverflowError) as exc:
                        raise ValueError("表格草稿格式无效，尚未应用。") from exc
                else:
                    content.update(changed)
                patch["content"] = content
            patch = {key: value for key, value in patch.items() if value != getattr(block, key)}
            if patch:
                block_patches[block.id] = patch
        elif draft.kind == "layout":
            layout_patches[draft.target_id] = changed
        else:
            raise ValueError("Unknown property draft kind")

    def update(node):
        if not isinstance(node, LayoutNode):
            return node
        changes = layout_patches.get(node.id, {})
        values = {"children": tuple(update(c) for c in node.children)}
        if "gap" in changes:
            values["gap"] = Size(changes["gap"], "mm")
        if "alignment" in changes:
            values["alignment"] = changes["alignment"]
        if "strategy" in changes:
            values["fallback"] = {**node.fallback, "strategy": changes["strategy"]}
        return replace(node, **values)

    return block_patches, update(layout)
