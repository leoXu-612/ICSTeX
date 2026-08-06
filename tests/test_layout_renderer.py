from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.blocks.block_renderer import escape_latex, render_block, required_packages_for_block
from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.blocks.layout import LayoutNode, Size, block_slot
from app.core.blocks.layout_renderer import render_layout
from app.core.blocks.layout_solver import solve_layout
from app.core.blocks.model import (
    Block,
    Caption,
    Semantic,
    content_for_raw_latex,
    content_for_text,
)
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import detect_toolchain
from app.core.latex_tools import LaTeXEngine


TOOLCHAIN = detect_toolchain()


class BlockRendererTests(TestCase):
    def test_escape_latex_special_characters(self) -> None:
        self.assertEqual(
            escape_latex(r"50% & _ {x} ~ ^ $"),
            r"50\% \& \_ \{x\} \textasciitilde{} \textasciicircum{} \$",
        )

    def test_render_block_types(self) -> None:
        text = Block(id="blk_text", type="text", alias="t", semantic=Semantic(role="text"), content=content_for_text("a & b"))
        self.assertIn(r"a \& b", render_block(text))
        self.assertIn("% ICSTEX:BEGIN block=blk_text", render_block(text))

        raw = Block(id="blk_raw", type="rawLatex", alias="r", semantic=Semantic(role="raw-latex"), content=content_for_raw_latex(r"\textbf{ok}"))
        self.assertIn(r"\textbf{ok}", render_block(raw))

        formula = Block(
            id="blk_f",
            type="formula",
            alias="eq",
            semantic=Semantic(role="equation", label="eq:x"),
            content=FormulaBlockAdapter().content_for(r"E=mc^2"),
        )
        rendered = render_block(formula)
        self.assertIn(r"\[", rendered)
        self.assertIn(r"\label{eq:x}", rendered)

    def test_render_is_deterministic(self) -> None:
        block = Block(id="blk_f", type="formula", alias="eq", semantic=Semantic(role="equation"), content=FormulaBlockAdapter().content_for(r"E=mc^2"))
        self.assertEqual(render_block(block), render_block(block))


class LayoutRendererTests(TestCase):
    def _block_latex(self) -> dict[str, str]:
        image = Block(
            id="blk_img",
            type="image",
            alias="img",
            semantic=Semantic(role="figure", label="fig:app", caption=Caption("装置")),
            content={"source": "figures/a.png"},
        )
        formula = Block(
            id="blk_eq",
            type="formula",
            alias="eq",
            semantic=Semantic(role="equation"),
            content=FormulaBlockAdapter().content_for(r"E=mc^2"),
        )
        return {"blk_img": render_block(image), "blk_eq": render_block(formula)}

    def test_row_renders_minipages_with_gap_ratios(self) -> None:
        layout = LayoutNode(
            id="lyt_summary",
            kind="row",
            gap=Size(value=8, unit="mm"),
            children=(block_slot("blk_img", weight=2, min_width_pt=120), block_slot("blk_eq", weight=3)),
        )
        solved = solve_layout(layout, 300.0)
        latex = render_layout(solved, self._block_latex())

        self.assertIn(r"% ICSTEX:layout=lyt_summary", latex)
        self.assertIn(r"\begin{minipage}[t]{0.3696\linewidth}", latex)
        self.assertIn(r"\hfill", latex)
        self.assertIn("\\includegraphics", latex)
        self.assertIn(r"\[", latex)

    def test_render_is_deterministic(self) -> None:
        layout = LayoutNode(id="lyt_row", kind="row", children=(block_slot("blk_img"), block_slot("blk_eq")))
        latex = render_layout(solve_layout(layout, 300.0), self._block_latex())
        self.assertEqual(latex, render_layout(solve_layout(layout, 300.0), self._block_latex()))


@skipUnless(TOOLCHAIN.is_compile_ready, "latexmk or pdflatex is not available")
class MixedGridCompileTests(TestCase):
    def test_four_mixed_blocks_in_2x2_grid_compile(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            figures = project / "figures"
            figures.mkdir()
            _write_tiny_png(figures / "a.png")
            blocks = {
                "blk_img": Block(
                    id="blk_img",
                    type="image",
                    alias="img",
                    semantic=Semantic(role="figure", caption=Caption("装置")),
                    content={"source": "figures/a.png"},
                ),
                "blk_tab": Block(
                    id="blk_tab",
                    type="table",
                    alias="tab",
                    semantic=Semantic(role="table"),
                    content={"tableVersion": "1.0.0", "columns": [], "rows": [], "header": {}, "merges": [], "notes": []},
                ),
                "blk_eq": Block(
                    id="blk_eq",
                    type="formula",
                    alias="eq",
                    semantic=Semantic(role="equation", label="eq:rate"),
                    content=FormulaBlockAdapter().content_for(r"r = k[A]"),
                ),
                "blk_txt": Block(
                    id="blk_txt",
                    type="text",
                    alias="txt",
                    semantic=Semantic(role="text"),
                    content=content_for_text("结果分析：温度升高，反应速率增大。"),
                ),
            }
            block_latex = {block_id: render_block(block, in_box=True) for block_id, block in blocks.items()}
            packages = sorted(
                {
                    package
                    for block in blocks.values()
                    for package in required_packages_for_block(block, in_box=True)
                }
            )
            layout = LayoutNode(
                id="lyt_demo",
                kind="grid",
                columns=2,
                gap=Size(value=8, unit="mm"),
                fallback={"strategy": "stackVertically"},
                children=tuple(block_slot(block_id, min_width_pt=120) for block_id in ("blk_img", "blk_tab", "blk_eq", "blk_txt")),
            )
            solved = solve_layout(layout, 426.0)
            rendered = render_layout(solved, block_latex)

            main = project / "main.tex"
            main.write_text(
                "\\documentclass{ctexart}\n"
                "\\usepackage{graphicx}\n"
                "\\usepackage{amsmath}\n"
                + "".join(f"\\usepackage{{{package}}}\n" for package in packages)
                + "\\usepackage{caption}\n"
                "\\graphicspath{{figures/}}\n"
                "\\begin{document}\n"
                f"{rendered}"
                "\\end{document}\n",
                encoding="utf-8",
            )
            manager = CompileManager(main, toolchain=TOOLCHAIN, engine=LaTeXEngine.XELATEX)
            result = manager.compile_now(BuildPurpose.FINAL)

            self.assertIsNotNone(result)
            assert result is not None
            self.assertTrue(result.ok, result.combined_output)
            self.assertTrue(result.pdf_file.exists())


def _write_tiny_png(path: Path) -> None:
    from PySide6.QtGui import QColor, QImage, QImageWriter

    image = QImage(4, 4, QImage.Format.Format_RGB32)
    image.fill(QColor(200, 200, 200))
    writer = QImageWriter(str(path), b"png")
    writer.write(image)
