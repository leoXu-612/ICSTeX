"""Table LaTeX strategy selector (Sprint 4).

Automatic choice between ``tabular``+booktabs, ``tabularx``, ``longtable``,
and ``siunitx`` S columns, per the task list rules. A table that needs page
breaks inside a Row/Grid box is reported as a blocking issue so the layout
solver can reject it before compilation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.blocks.table_model import Cell, TableData


AVG_CHAR_WIDTH_PT = 5.0
ROW_HEIGHT_PT = 14.0
LONG_TEXT_LENGTH = 40
PAGE_HEIGHT_LIMIT_PT = 500.0


@dataclass(frozen=True)
class ColumnLayout:
    column_id: str
    mode: str  # "content" | "flex" | "siunitx" | "p"
    format: str | None = None
    width_pt: float | None = None


@dataclass(frozen=True)
class TableStrategy:
    strategy: str  # "tabular" | "tabularx" | "longtable"
    column_layouts: list[ColumnLayout] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    needs_siunitx: bool = False
    needs_booktabs: bool = True


def select_strategy(
    table: TableData,
    *,
    allow_page_break: bool = False,
    in_box: bool = False,
    available_width_pt: float | None = None,
    style: dict | None = None,
) -> TableStrategy:
    style = style or {}
    column_sizing = style.get("columnSizing", {}) or {}
    issues: list[str] = []
    layouts: list[ColumnLayout] = []
    needs_siunitx = False
    has_flex = False
    has_long_text = False

    for column in table.columns:
        sizing = column_sizing.get(column.id, {}) or {}
        mode = sizing.get("mode")
        values = [table.cell(row.id, column.id) for row in table.rows]
        if column.dataType == "number" or column.unit:
            needs_siunitx = True
            layouts.append(
                ColumnLayout(
                    column_id=column.id,
                    mode="siunitx",
                    format=_siunitx_format(values),
                )
            )
        elif mode == "flex" or _is_long_text(values):
            has_flex = True
            has_long_text = has_long_text or _is_long_text(values)
            layouts.append(ColumnLayout(column_id=column.id, mode="flex"))
        else:
            layouts.append(ColumnLayout(column_id=column.id, mode="content"))

    estimated_width = _estimated_width_pt(table, layouts)
    if available_width_pt is not None and estimated_width > available_width_pt:
        issues.append(
            "ICSTEX_TABLE_WIDE: 表格估算宽度超过可用宽度，建议换行、减少非必要列或使用全宽"
        )

    if allow_page_break or estimated_height_pt(table) > PAGE_HEIGHT_LIMIT_PT:
        strategy = "longtable"
        if in_box:
            issues.append(
                "ICSTEX_TABLE_LONGTABLE_BOXED: 需要跨页的长表格不能放入不可分页的左右/网格容器"
            )
        if has_long_text:
            # longtable with long text: computed p{width} instead of tabularx.
            layouts = [
                ColumnLayout(
                    column_id=layout.column_id,
                    mode="p" if layout.mode == "flex" else layout.mode,
                    format=layout.format,
                    width_pt=120.0 if layout.mode == "flex" else None,
                )
                for layout in layouts
            ]
    elif has_flex:
        strategy = "tabularx"
    else:
        strategy = "tabular"

    return TableStrategy(
        strategy=strategy,
        column_layouts=layouts,
        issues=issues,
        needs_siunitx=needs_siunitx,
    )


def estimated_height_pt(table: TableData) -> float:
    return max(1, len(table.rows)) * ROW_HEIGHT_PT + table.header_row_count * ROW_HEIGHT_PT


def _is_long_text(cells: list[Cell]) -> bool:
    return any(
        cell.kind == "text" and len(str(cell.value or "")) > LONG_TEXT_LENGTH
        for cell in cells
    )


def _estimated_width_pt(table: TableData, layouts: list[ColumnLayout]) -> float:
    total = 0.0
    for column, layout in zip(table.columns, layouts):
        if layout.mode == "flex":
            total += 180.0
            continue
        longest = max(
            (len(str(table.cell(row.id, column.id).value or "")) for row in table.rows),
            default=len(column.name),
        )
        total += max(longest, len(column.name)) * AVG_CHAR_WIDTH_PT + 12.0
    return total


def _siunitx_format(cells: list[Cell]) -> str:
    integers = 1
    decimals = 0
    for cell in cells:
        if cell.kind != "number":
            continue
        text = str(cell.value)
        if "." in text:
            integer_part, decimal_part = text.split(".", 1)
            integers = max(integers, len(integer_part.strip("-")))
            decimals = max(decimals, len(decimal_part.rstrip("0")))
        else:
            integers = max(integers, len(text.strip("-")))
    return f"{integers}.{decimals}"
