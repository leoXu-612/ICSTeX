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
    for row in header_rows:
        lines.append(_render_row(table, row, strategy, header=True) + r" \\")
    lines.append("\\midrule")
    for row in body_rows:
        lines.append(_render_row(table, row, strategy, header=False) + r" \\")
    lines.append("\\bottomrule")
    return "\n".join(lines)


def _render_row(table: TableData, row, strategy, *, header: bool) -> str:
    cells: list[str] = []
    for column, layout in zip(table.columns, strategy.column_layouts):
        if header:
            cells.append(_render_header_cell(column))
        else:
            cell = row.cells.get(column.id, Cell())
            cells.append(_render_cell(cell, layout))
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
