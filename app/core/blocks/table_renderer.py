"""Stable LaTeX table generator (Sprint 4).

Deterministic output: fixed column order, fixed number formatting, escaped
user text, and explicit strategy selection. Only ``kind: latex`` cells may
carry raw LaTeX. Horizontal merges become ``\\multicolumn``; vertical merges
emit a comment until a ``multirow`` strategy is added.
"""
from __future__ import annotations

from app.core.blocks.latex_escape import escape_latex
from app.core.blocks.table_model import Cell, TableData
from app.core.blocks.table_strategy import ColumnLayout, select_strategy


def required_packages(table: TableData, *, style: dict | None = None, in_box: bool = False) -> tuple[str, ...]:
    """Packages needed to compile the generated table LaTeX."""

    strategy = select_strategy(
        table,
        allow_page_break=bool((style or {}).get("allowPageBreak")),
        in_box=in_box,
        style=style,
    )
    packages = ["booktabs"]
    if strategy.needs_siunitx:
        packages.append("siunitx")
    if strategy.strategy == "tabularx":
        packages.append("tabularx")
    if strategy.strategy == "longtable":
        packages.append("longtable")
    if _has_vertical_merges(table.merges):
        packages.append("multirow")
    if in_box:
        packages.append("caption")
    return tuple(dict.fromkeys(packages))


def render_table(
    table: TableData,
    *,
    caption: str | None = None,
    label: str | None = None,
    style: dict | None = None,
    available_width_pt: float | None = None,
    in_box: bool = False,
    block_id: str = "",
) -> str:
    if not table.columns:
        return f"% ICSTEX:table block={block_id} empty\n"
    strategy = select_strategy(
        table,
        allow_page_break=bool((style or {}).get("allowPageBreak")),
        in_box=in_box,
        available_width_pt=available_width_pt,
        style=style,
    )
    header = f"% ICSTEX:table block={block_id} strategy={strategy.strategy}"
    body = _render_body(table, strategy)
    if strategy.strategy == "longtable":
        return header + "\n" + _render_longtable(table, caption, label, body)
    return header + "\n" + _render_float(table, strategy, caption, label, body, in_box=in_box)


def _render_float(
    table: TableData,
    strategy,
    caption: str | None,
    label: str | None,
    body: str,
    *,
    in_box: bool,
) -> str:
    lines = ["\\begin{table}[htbp]", "  \\centering"]
    if in_box:
        lines = []
    if strategy.strategy == "tabularx":
        lines.append(f"  \\begin{{tabularx}}{{\\linewidth}}{{{_column_spec(table, strategy)}}}")
    else:
        lines.append(f"  \\begin{{tabular}}{{{_column_spec(table, strategy)}}}")
    lines.extend(f"    {line}" for line in body.splitlines())
    lines.append(f"  \\end{{{_environment_name(strategy)}}}")
    if caption:
        lines.append(f"  \\captionof{{table}}{{{escape_latex(caption)}}}" if in_box else f"  \\caption{{{escape_latex(caption)}}}")
    if label:
        lines.append(f"  \\label{{{label}}}")
    if not in_box:
        lines.append("\\end{table}")
    return "\n".join(lines) + "\n"


def _render_longtable(table: TableData, caption: str | None, label: str | None, body: str) -> str:
    lines = [f"\\begin{{longtable}}{{{_column_spec(table, None)}}}"]
    if caption:
        lines.append(f"  \\caption{{{escape_latex(caption)}}} \\\\")
    if label:
        lines.append(f"  \\label{{{label}}} \\\\")
    if table.repeat_header:
        lines.append("  \\endfirsthead")
        lines.append("  \\endhead")
    lines.extend(f"  {line}" for line in body.splitlines())
    lines.append("\\end{longtable}")
    return "\n".join(lines) + "\n"


def _environment_name(strategy) -> str:
    return "tabularx" if strategy.strategy == "tabularx" else "tabular"


def _column_spec(table: TableData, strategy) -> str:
    layouts = strategy.column_layouts if strategy is not None else [
        ColumnLayout(column_id=column.id, mode="content") for column in table.columns
    ]
    parts: list[str] = []
    for column, layout in zip(table.columns, layouts):
        if layout.mode == "siunitx":
            parts.append(f"S[table-format={layout.format or '1.0'}]")
        elif layout.mode == "flex":
            parts.append("X")
        elif layout.mode == "p":
            parts.append(f"p{{{layout.width_pt or 120.0:.0f}pt}}")
        else:
            parts.append({"left": "l", "right": "r", "center": "c", "decimal": "l"}.get(column.alignment, "l"))
    return "".join(parts)


def _render_body(table: TableData, strategy) -> str:
    lines: list[str] = ["\\toprule"]
    header_rows = table.rows[: table.header_row_count]
    body_rows = table.rows[table.header_row_count :]
    origin, covered = _merged_map(table)
    for row_index, row in enumerate(header_rows):
        lines.append(_render_row(table, row_index, row, strategy, origin, covered, header=True) + r" \\")
    lines.append("\\midrule")
    for row_index, row in enumerate(body_rows, start=len(header_rows)):
        lines.append(_render_row(table, row_index, row, strategy, origin, covered, header=False) + r" \\")
    lines.append("\\bottomrule")
    return "\n".join(lines)


def _render_row(
    table: TableData,
    row_index: int,
    row,
    strategy,
    origin: dict,
    covered: set,
    *,
    header: bool,
) -> str:
    cells: list[str] = []
    skip_until = -1
    for column_index, (column, layout) in enumerate(zip(table.columns, strategy.column_layouts)):
        if column_index <= skip_until:
            continue
        if (row_index, column_index) in covered:
            if column_index <= skip_until:
                continue
            cells.append("")
            continue
        merge = origin.get((row_index, column_index))
        if header:
            content = _render_header_cell(column)
        else:
            cell = row.cells.get(column.id, Cell())
            content = _render_cell(cell, layout)
        if merge is not None:
            r1, r2, c1, c2 = merge
            span = c2 - c1 + 1
            rows = r2 - r1 + 1
            if rows > 1:
                content = f"\\multirow{{{rows}}}{{*}}{{{content}}}"
            if span > 1:
                content = f"\\multicolumn{{{span}}}{{c}}{{{content}}}"
                skip_until = c2
        cells.append(content)
    if not cells:
        cells = [""] * len(table.columns)
    return " & ".join(cells)


def _render_header_cell(column) -> str:
    text = escape_latex(column.name)
    if column.unit:
        return f"{{\\textbf{{{text}}} / \\unit{{{column.unit}}}}}"
    return "{\\textbf{" + text + "}}"


def _render_cell(cell: Cell, layout: ColumnLayout) -> str:
    if cell.kind == "latex":
        return str(cell.value or "")
    if cell.kind == "number" and layout.mode == "siunitx":
        decimals = int(layout.format.split(".")[1]) if layout.format and "." in layout.format else 0
        return f"{float(cell.value):.{decimals}f}"
    if cell.kind == "empty":
        return ""
    if cell.kind == "boolean":
        return escape_latex(str(cell.value).lower())
    return escape_latex(str(cell.value or ""))


def _merged_map(table: TableData) -> tuple[dict, set]:
    """Return (origin per top-left cell, covered cells) from table.merges."""

    origin: dict = {}
    covered: set = set()
    for merge in table.merges:
        r1, r2, c1, c2 = merge
        for row in range(r1, r2 + 1):
            for column in range(c1, c2 + 1):
                if (row, column) == (r1, c1):
                    origin[(r1, c1)] = merge
                else:
                    covered.add((row, column))
    return origin, covered


def _has_vertical_merges(merges: list[list[int]]) -> bool:
    return any(r1 != r2 for r1, r2, _c1, _c2 in merges)
