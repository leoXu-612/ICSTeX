"""Render a solved layout tree to stable, compilable LaTeX (Sprint 2).

Row/Grid cells become ``minipage`` units at ``\\linewidth`` ratios computed by
the solver (gaps already deducted, fixed precision). Nested containers
recursively render their solved children.
"""
from __future__ import annotations

from app.core.blocks.layout_solver import SolvedNode, SolvedSlot


def render_layout(node: SolvedNode, block_latex: dict[str, str]) -> str:
    return _render_node(node, block_latex).rstrip() + "\n"


def _render_node(node: SolvedNode, block_latex: dict[str, str]) -> str:
    header = f"% ICSTEX:layout={node.layoutId}"
    if node.kind == "row":
        cells = [_render_slot(child, block_latex) for child in node.children]
        return header + "\n\\noindent\n" + "\n\\hfill\n".join(cells)
    if node.kind == "grid":
        columns = max(1, node.columns or 1)
        rows: list[str] = []
        cells = [_render_slot(child, block_latex) for child in node.children]
        for index in range(0, len(cells), columns):
            rows.append("\n\\hfill\n".join(cells[index : index + columns]))
        return header + "\n\\noindent\n" + "\n\n".join(rows)
    if node.kind == "fullWidth":
        body = "\n\n".join(_render_child(child, block_latex) for child in node.children)
        return header + "\n\\noindent\n" + body
    # column: children flow naturally in document order.
    body = "\n\n".join(_render_child(child, block_latex) for child in node.children)
    return header + "\n" + body


def _render_child(child: object, block_latex: dict[str, str]) -> str:
    if isinstance(child, SolvedSlot):
        return _slot_content(child, block_latex)
    return _render_node(child, block_latex)


def _render_slot(slot: SolvedSlot, block_latex: dict[str, str]) -> str:
    return (
        f"\\begin{{minipage}}[t]{{{slot.ratio:.4f}\\linewidth}}\n"
        "  \\vspace{0pt}\n"
        f"  % ICSTEX:slot={slot.instanceId} block={slot.blockId}\n"
        + _indent(_slot_content(slot, block_latex))
        + "\\end{minipage}"
    )


def _slot_content(slot: SolvedSlot, block_latex: dict[str, str]) -> str:
    return block_latex.get(slot.blockId, f"% missing block: {slot.blockId}\n")


def _indent(text: str) -> str:
    return "".join(f"  {line}\n" if line else "\n" for line in text.splitlines())
