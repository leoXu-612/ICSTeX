"""Synthetic, disposable projects shared by V1 tests and native QA probes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import zlib

from app.core.blocks.assembly import build_latex_files
from app.core.blocks.layout import LayoutNode, block_slot
from app.core.blocks.model import content_for_text
from app.core.blocks.project_repository import save_project
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.theme import DocumentTheme


@dataclass(frozen=True)
class ProjectFixture:
    root: Path
    draft_path: Path
    draft_text: str
    conflict_text: str


def _png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0\x33\x66\x99\x66\x99\xcc" * 2))
            + chunk(b"IEND", b""))


def create_project(base: Path, kind: str = "multi", *, missing: bool = False) -> ProjectFixture:
    """Refuse an existing target; never open or alter a student's project."""
    project = base / {"single": "single", "multi": "多文件 项目", "block": "block"}[kind]
    project.mkdir(parents=True, exist_ok=False)
    root = project / "main.tex"
    if kind == "block":
        registry = BlockRegistry()
        block = registry.create(CreateBlockInput(type="text", alias="analysis",
                                                content=content_for_text("Synthetic analysis.")))
        layout = LayoutNode(id="qa_layout", kind="column", children=(block_slot(block.id),))
        theme = DocumentTheme(id="qa_theme", name="Synthetic QA")
        save_project(project, registry=registry, layout=layout, document_theme=theme)
        for path, text in build_latex_files(project, registry=registry, layout=layout,
                                           document_theme=theme).items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        draft = project / "blocks" / f"{block.id}.tex"
    else:
        text = "\\documentclass{article}\n\\usepackage{graphicx}\n"
        text += "\\newcommand{\\localterm}[1]{#1}\n\\begin{document}\n"
        text += "\\section{Synthetic sample}\\label{sec:intro}\n"
        text += "A local document with \\localterm{an unknown-to-the-editor macro}.\n"
        if kind == "multi":
            (project / "chapters").mkdir()
            draft = project / "chapters" / "analysis.tex"
            draft.write_text("% !TEX root = ../main.tex\n"
                             "See Section \\ref{sec:intro} and \\cite{sample}.\n"
                             "\\begin{tabular}{lr}Sample & Value\\\\ A & 0\\\\\\end{tabular}\n",
                             encoding="utf-8")
            text += "\\input{chapters/analysis}\n\\includegraphics{figures/plot}\n"
            text += "\\bibliographystyle{plain}\n\\bibliography{refs}\n"
            (project / "figures").mkdir()
            if not missing:
                (project / "figures" / "plot.png").write_bytes(_png())
            (project / "refs.bib").write_text(
                "@misc{sample,author={Synthetic Author},title={QA Reference},year={2026}}\n",
                encoding="utf-8")
        else:
            draft = root
        root.write_text(text + "\\end{document}\n", encoding="utf-8")
    original = draft.read_text(encoding="utf-8")
    return ProjectFixture(root, draft, original + "\nUnsaved synthetic draft.\n",
                          original + "\nDifferent external edit.\n")
