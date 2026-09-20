"""Render a Block to stable LaTeX (Sprint 2).

Deterministic output: fixed indentation, no timestamps, no absolute paths,
and all user text escaped unless it is explicitly trusted LaTeX. Table
rendering arrives with the Sprint 4 strategy selector; until then tables
emit an explicit placeholder comment.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re

from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.formula.sanitizer import sanitize_formula_latex
from app.core.blocks.model import Block
from app.core.blocks.latex_escape import escape_latex
from app.core.blocks.table_model import TableData
from app.core.blocks.table_renderer import render_table, required_packages


_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,127}$")


@dataclass(frozen=True)
class RenderPolicy:
    allow_trusted_raw_latex: bool = False
    project_root: Path | None = None


def render_block(block: Block, *, in_box: bool = False, policy: RenderPolicy | None = None) -> str:
    """Render a Block to LaTeX.

    ``in_box`` marks placement inside a Row/Grid minipage: floats and
    sections are not allowed in boxes, so images fall back to non-floating
    ``\\captionof`` and headings to bold text.
    """

    policy = policy or RenderPolicy()
    block_type = block.type
    if block_type == "text":
        latex = escape_latex(str(block.content.get("text", ""))) + "\n"
    elif block_type == "heading":
        level = max(1, min(6, int(block.content.get("level", 1))))
        command = ["section", "subsection", "subsubsection", "paragraph", "subparagraph", "subparagraph"][level - 1]
        if in_box:
            latex = "\\textbf{" + escape_latex(str(block.content.get("text", ""))) + "}\n"
        else:
            latex = f"\\{command}{{{escape_latex(str(block.content.get('text', '')))}}}\n"
    elif block_type == "quote":
        latex = "\\begin{quote}\n" + escape_latex(str(block.content.get("text", ""))) + "\n\\end{quote}\n"
    elif block_type == "list":
        environment = "enumerate" if block.content.get("ordered") else "itemize"
        items = "\n".join(f"  \\item {escape_latex(str(item))}" for item in block.content.get("items", []))
        latex = f"\\begin{{{environment}}}\n{items}\n\\end{{{environment}}}\n"
    elif block_type == "rawLatex":
        trusted = bool(block.content.get("trusted"))
        if trusted and policy.allow_trusted_raw_latex:
            latex = f"% ICSTEX:raw-latex trusted=true\n{block.content.get('latex', '')}\n"
        else:
            latex = "% ICSTEX:raw-latex blocked (requires explicit session trust)\n"
    elif block_type == "formula":
        try:
            latex = FormulaBlockAdapter().render_latex(block.content["ast"])
        except (KeyError, TypeError, ValueError):
            latex = "% ICSTEX:formula blocked (invalid managed AST)"
        else:
            sanitized = sanitize_formula_latex(latex)
            if not sanitized.ok:
                latex = "% ICSTEX:formula blocked (unsafe managed AST)"
            else:
                latex = sanitized.text
        label = _safe_label(block.semantic.label)
        role = block.semantic.role
        if role == "inline":
            latex = f"\\({latex}\\)\n"
        else:
            body = latex
            if label:
                body = latex + f"\n  \\label{{{label}}}"
            latex = f"\\[\n  {body}\n\\]\n"
    elif block_type == "image":
        latex = _render_image(block, in_box=in_box, policy=policy)
    elif block_type == "table":
        try:
            table = TableData.from_content_dict(block.content)
        except (KeyError, TypeError, ValueError):
            latex = f"% ICSTEX:table block={block.id} 无法解析表格内容\n"
        else:
            latex = render_table(
                table,
                caption=block.semantic.caption.text if block.semantic.caption else None,
                label=block.semantic.label,
                in_box=in_box,
                block_id=block.id,
            )
    else:
        latex = f"% ICSTEX:unknown-block-type {block_type}\n"
    return _wrap_block(block.id, latex)


def _wrap_block(block_id: str, latex: str) -> str:
    return f"% ICSTEX:BEGIN block={block_id}\n{latex}% ICSTEX:END block={block_id}\n"


def required_packages_for_block(block: Block, *, in_box: bool = False) -> tuple[str, ...]:
    """Packages required to compile this Block's rendered LaTeX."""

    if block.type == "table":
        try:
            table = TableData.from_content_dict(block.content)
        except (KeyError, TypeError, ValueError):
            return ()
        return required_packages(table, in_box=in_box)
    if block.type == "image" and in_box:
        return ("graphicx", "caption")
    if block.type == "image":
        return ("graphicx",)
    if block.type == "formula":
        return ("amsmath",)
    return ()


def _render_image(block: Block, *, in_box: bool, policy: RenderPolicy) -> str:
    source = _safe_image_source(str(block.content.get("source", "")), policy.project_root)
    if source is None:
        return f"% ICSTEX:image block={block.id} blocked (unsafe source)\n"
    caption = block.semantic.caption.text if block.semantic.caption else ""
    label = _safe_label(block.semantic.label) or ""
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


def _safe_label(label: str | None) -> str | None:
    value = str(label or "")
    return value if _LABEL_RE.fullmatch(value) else None


def _safe_image_source(source: str, project_root: Path | None) -> str | None:
    if not source or "\\" in source or "\x00" in source or "://" in source:
        return None
    candidate = PurePosixPath(source)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        return None
    if len(candidate.parts[0]) == 2 and candidate.parts[0][1] == ":":
        return None
    if project_root is not None:
        root = Path(project_root).expanduser().resolve()
        lexical = root.joinpath(*candidate.parts)
        if any(part.is_symlink() for part in (lexical, *lexical.parents) if part != root.parent):
            return None
        try:
            if not lexical.resolve(strict=True).is_relative_to(root):
                return None
        except OSError:
            return None
    return candidate.as_posix()
