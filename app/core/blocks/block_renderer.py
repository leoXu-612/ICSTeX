"""Render a Block to stable LaTeX (Sprint 2).

Deterministic output: fixed indentation, no timestamps, no absolute paths,
and all user text escaped unless it is explicitly trusted LaTeX. Table
rendering arrives with the Sprint 4 strategy selector; until then tables
emit an explicit placeholder comment.
"""
from __future__ import annotations

from app.core.blocks.model import Block


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in user text (backslash first)."""

    escaped = (
        text.replace("\\", r"\textbackslash{}")
        .replace("#", r"\#")
        .replace("$", r"\$")
        .replace("%", r"\%")
        .replace("&", r"\&")
        .replace("_", r"\_")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("~", r"\textasciitilde{}")
        .replace("^", r"\textasciicircum{}")
    )
    return escaped


def render_block(block: Block, *, in_box: bool = False) -> str:
    """Render a Block to LaTeX.

    ``in_box`` marks placement inside a Row/Grid minipage: floats and
    sections are not allowed in boxes, so images fall back to non-floating
    ``\\captionof`` and headings to bold text.
    """

    block_type = block.type
    if block_type == "text":
        return escape_latex(str(block.content.get("text", ""))) + "\n"
    if block_type == "heading":
        level = max(1, min(6, int(block.content.get("level", 1))))
        command = ["section", "subsection", "subsubsection", "paragraph", "subparagraph", "subparagraph"][level - 1]
        if in_box:
            return "\\textbf{" + escape_latex(str(block.content.get("text", ""))) + "}\n"
        return f"\\{command}{{{escape_latex(str(block.content.get('text', '')))}}}\n"
    if block_type == "quote":
        return "\\begin{quote}\n" + escape_latex(str(block.content.get("text", ""))) + "\n\\end{quote}\n"
    if block_type == "list":
        environment = "enumerate" if block.content.get("ordered") else "itemize"
        items = "\n".join(f"  \\item {escape_latex(str(item))}" for item in block.content.get("items", []))
        return f"\\begin{{{environment}}}\n{items}\n\\end{{{environment}}}\n"
    if block_type == "rawLatex":
        trusted = bool(block.content.get("trusted"))
        return f"% ICSTEX:raw-latex trusted={str(trusted).lower()}\n{block.content.get('latex', '')}\n"
    if block_type == "formula":
        latex = str(block.content.get("latexCache", ""))
        label = block.semantic.label
        role = block.semantic.role
        if role == "inline":
            return f"\\({latex}\\)\n"
        body = latex
        if label:
            body = latex + f"\n  \\label{{{label}}}"
        return f"\\[\n  {body}\n\\]\n"
    if block_type == "image":
        return _render_image(block, in_box=in_box)
    if block_type == "table":
        return f"% ICSTEX:table block={block.id} rendering in Sprint 4\n"
    return f"% ICSTEX:unknown-block-type {block_type}\n"


def _render_image(block: Block, *, in_box: bool) -> str:
    source = str(block.content.get("source", ""))
    caption = block.semantic.caption.text if block.semantic.caption else ""
    label = block.semantic.label or ""
    if in_box:
        lines = [f"\\includegraphics[width=\\linewidth]{{{source}}}"]
        if caption:
            lines.append(f"\\captionof{{figure}}{{{escape_latex(caption)}}}")
        if label:
            lines.append(f"\\label{{{label}}}")
        return "\n".join(lines) + "\n"
    lines = ["\\begin{figure}[htbp]", "  \\centering", f"  \\includegraphics[width=0.8\\linewidth]{{{source}}}"]
    if caption:
        lines.append(f"  \\caption{{{escape_latex(caption)}}}")
    if label:
        lines.append(f"  \\label{{{label}}}")
    lines.append("\\end{figure}")
    return "\n".join(lines) + "\n"
