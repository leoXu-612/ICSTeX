from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.blocks.model import Block, Caption, Semantic
from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow
from app.core.blocks.table_renderer import render_table
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain


TOOLCHAIN = detect_toolchain()


def sample_table() -> TableData:
    return TableData(
        columns=[
            ColumnSpec(id="col_t", name="温度", dataType="number", unit=r"\celsius", alignment="decimal"),
            ColumnSpec(id="col_n", name="备注", dataType="text"),
        ],
        rows=[
            TableRow(id="row_000", cells={"col_t": Cell(kind="text", value="温度"), "col_n": Cell(kind="text", value="备注")}),
            TableRow(id="row_001", cells={"col_t": Cell(kind="number", value=20), "col_n": Cell(kind="text", value="基准组")}),
            TableRow(id="row_002", cells={"col_t": Cell(kind="number", value=30.5), "col_n": Cell(kind="text", value="重复测量")}),
        ],
        header_row_count=1,
    )


class TableRendererTests(TestCase):
    def test_golden_booktabs_output(self) -> None:
        latex = render_table(sample_table(), caption="温度表", label="tab:temp")
        expected = (
            "% ICSTEX:table block= strategy=tabular\n"
            "\\begin{table}[htbp]\n"
            "  \\centering\n"
            "  \\begin{tabular}{S[table-format=2.1]l}\n"
            "    \\toprule\n"
            "    {\\textbf{温度} / \\unit{\\celsius}} & {\\textbf{备注}} \\\\\n"
            "    \\midrule\n"
            "    20.0 & 基准组 \\\\\n"
            "    30.5 & 重复测量 \\\\\n"
            "    \\bottomrule\n"
            "  \\end{tabular}\n"
            "  \\caption{温度表}\n"
            "  \\label{tab:temp}\n"
            "\\end{table}\n"
        )
        self.assertEqual(latex, expected)

    def test_special_characters_are_escaped(self) -> None:
        table = TableData(
            columns=[ColumnSpec(id="c", name="注记", dataType="text")],
            rows=[TableRow(id="r1", cells={"c": Cell(kind="text", value="50% & _ {x} $")})],
            header_row_count=0,
        )
        latex = render_table(table)
        self.assertIn(r"50\% \& \_ \{x\} \$", latex)

    def test_deterministic_output(self) -> None:
        first = render_table(sample_table(), caption="t")
        second = render_table(sample_table(), caption="t")
        self.assertEqual(first, second)

    def test_longtable_repeats_header(self) -> None:
        table = sample_table()
        table.repeat_header = True
        latex = render_table(table, style={"allowPageBreak": True})
        self.assertIn("\\begin{longtable}", latex)
        self.assertIn("\\endfirsthead", latex)
        self.assertIn("\\endhead", latex)


@skipUnless(TOOLCHAIN.is_compile_ready, "latexmk or pdflatex is not available")
class TableCompileTests(TestCase):
    def test_table_block_compiles_with_xelatex(self) -> None:
        from app.core.blocks.block_renderer import render_block, required_packages_for_block

        with TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            table_block = Block(
                id="blk_tab",
                type="table",
                alias="results",
                semantic=Semantic(role="table", label="tab:results", caption=Caption("不同温度下的反应速率")),
                content=sample_table().to_content_dict(),
            )
            packages = "\n".join(
                f"\\usepackage{{{package}}}" for package in required_packages_for_block(table_block, in_box=True)
            )
            main = project / "main.tex"
            main.write_text(
                "\\documentclass{ctexart}\n"
                f"{packages}\n"
                "\\usepackage{amsmath}\n"
                "\\begin{document}\n"
                f"{render_block(table_block, in_box=True)}"
                "\\end{document}\n",
                encoding="utf-8",
            )
            result = CompileManager(main, toolchain=TOOLCHAIN, engine=LaTeXEngine.XELATEX).compile_now(
                BuildPurpose.FINAL
            )
            self.assertTrue(result.ok, result.combined_output)
