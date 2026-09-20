"""Pure, deterministic Block-project to LaTeX assembly."""
from __future__ import annotations

from pathlib import Path

from app.core.blocks.block_renderer import RenderPolicy, render_block, required_packages_for_block
from app.core.blocks.layout import LayoutNode
from app.core.blocks.layout_renderer import render_layout
from app.core.blocks.layout_solver import solve_layout
from app.core.blocks.registry import BlockRegistry
from app.core.blocks.theme import DocumentTheme
from app.core.blocks.theme_renderer import render_document_theme_sty


def build_latex_files(
    project_dir: Path,
    *,
    registry: BlockRegistry,
    layout: LayoutNode | None,
    document_theme: DocumentTheme,
    allow_trusted_raw_latex: bool = False,
) -> dict[Path, str]:
    """Return every generated file without touching disk."""

    project = Path(project_dir).expanduser().resolve()
    files: dict[Path, str] = {}
    block_latex: dict[str, str] = {}
    for block in registry.blocks():
        files[project / "blocks" / f"{block.id}.tex"] = render_block(
            block,
            in_box=True,
            policy=RenderPolicy(
                allow_trusted_raw_latex=allow_trusted_raw_latex,
                project_root=project,
            ),
        )
        block_latex[block.id] = f"\\input{{blocks/{block.id}.tex}}\n"

    body = render_layout(solve_layout(layout, 426.0), block_latex) if layout is not None else ""
    packages = sorted(
        {"graphicx"}
        | {
            package
            for block in registry.blocks()
            for package in required_packages_for_block(block, in_box=True)
        }
    )
    files[project / "styles" / "icstex-generated.sty"] = render_document_theme_sty(document_theme)
    files[project / "main.tex"] = (
        "\\documentclass{ctexart}\n"
        + "".join(f"\\usepackage{{{package}}}\n" for package in packages)
        + "\\input{styles/icstex-generated.sty}\n"
        + "\\graphicspath{{assets/images/}}\n"
        + "\\begin{document}\n"
        + body
        + "\\end{document}\n"
    )
    return files
