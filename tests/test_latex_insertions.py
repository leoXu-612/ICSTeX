from __future__ import annotations

from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from app.core.latex_insertions import (
    FIGURE_PACKAGES,
    FigureLayout,
    FigureLayoutItem,
    FigureLayoutSpec,
    FigureSpec,
    HyperlinkSpec,
    SideBySideFigureSpec,
    TableSpec,
    ensure_packages,
    export_template,
    existing_packages,
    figure_layout_snippet,
    figure_snippet,
    hyperlink_snippet,
    import_custom_template,
    latex_relative_path,
    parse_delimited,
    parse_tabular,
    save_custom_template,
    sanitize_asset_filename,
    side_by_side_figure_snippet,
    table_snippet,
    template_for_key,
    unique_asset_path,
)


TOOLCHAIN = detect_toolchain()


class ParseTabularTests(TestCase):
    def test_round_trips_booktabs_snippet(self) -> None:
        original = TableSpec(
            rows=2,
            columns=3,
            alignment="l",
            use_booktabs=True,
            caption="My table",
            label="tab:demo",
            placement="htbp",
            headers=("A", "B", "C"),
            cells=(("1", "2", "3"), ("4", "5", "6")),
        )
        parsed = parse_tabular(table_snippet(original))
        assert parsed is not None
        self.assertEqual(parsed.columns, 3)
        self.assertEqual(parsed.alignment, "l")
        self.assertTrue(parsed.use_booktabs)
        self.assertEqual(parsed.caption, "My table")
        self.assertEqual(parsed.label, "tab:demo")
        self.assertEqual(parsed.placement, "htbp")
        self.assertEqual(parsed.headers, ("A", "B", "C"))
        self.assertEqual(parsed.cells, (("1", "2", "3"), ("4", "5", "6")))

    def test_round_trips_hline_snippet(self) -> None:
        original = TableSpec(rows=1, columns=2, use_booktabs=False, headers=("h1", "h2"), cells=(("a", "b"),))
        parsed = parse_tabular(table_snippet(original))
        assert parsed is not None
        self.assertFalse(parsed.use_booktabs)
        self.assertEqual(parsed.headers, ("h1", "h2"))
        self.assertEqual(parsed.cells, (("a", "b"),))

    def test_parses_handwritten_tabular_without_table_wrapper(self) -> None:
        text = r"\begin{tabular}{|c|c|} \hline x & y \\ \hline 1 & 2 \\ \hline \end{tabular}"
        parsed = parse_tabular(text)
        assert parsed is not None
        self.assertEqual(parsed.columns, 2)
        self.assertEqual(parsed.headers, ("x", "y"))
        self.assertEqual(parsed.cells, (("1", "2"),))
        self.assertEqual(parsed.placement, "htbp")

    def test_handles_p_column_spec(self) -> None:
        text = r"\begin{tabular}{lp{3cm}r} a & b & c \\ \end{tabular}"
        parsed = parse_tabular(text)
        assert parsed is not None
        self.assertEqual(parsed.columns, 3)

    def test_returns_none_without_tabular(self) -> None:
        self.assertIsNone(parse_tabular("no table here"))


class ParseDelimitedTests(TestCase):
    def test_parses_excel_tab_separated(self) -> None:
        parsed = parse_delimited("Name\tScore\nAlice\t90\nBob\t85")
        assert parsed is not None
        self.assertEqual(parsed.columns, 2)
        self.assertEqual(parsed.headers, ("Name", "Score"))
        self.assertEqual(parsed.cells, (("Alice", "90"), ("Bob", "85")))

    def test_parses_csv_with_quoted_comma(self) -> None:
        parsed = parse_delimited('a,b\n"x, y",2')
        assert parsed is not None
        self.assertEqual(parsed.headers, ("a", "b"))
        self.assertEqual(parsed.cells, (("x, y", "2"),))

    def test_skips_blank_lines_and_pads_columns(self) -> None:
        parsed = parse_delimited("a,b,c\n\n1,2\n")
        assert parsed is not None
        self.assertEqual(parsed.columns, 3)
        self.assertEqual(parsed.cells, (("1", "2"),))

    def test_returns_none_for_empty(self) -> None:
        self.assertIsNone(parse_delimited("   \n  "))


class LatexInsertionsTests(TestCase):
    def test_sanitizes_asset_filename(self) -> None:
        self.assertEqual(sanitize_asset_filename("My Figure 1.PNG"), "My_Figure_1.png")
        self.assertEqual(sanitize_asset_filename("图片.jpeg"), "image.jpeg")

    def test_unique_asset_path_adds_suffix(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "plot.png").write_text("existing", encoding="utf-8")

            self.assertEqual(unique_asset_path(root, "plot.png").name, "plot_1.png")

    def test_latex_relative_path_uses_forward_slashes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tex = root / "main.tex"
            image = root / "figures" / "plot.png"

            self.assertEqual(latex_relative_path(tex, image), "figures/plot.png")

    def test_figure_snippet(self) -> None:
        snippet = figure_snippet(FigureSpec(image_path="figures/plot.png", caption="Plot", label="fig:plot"))

        self.assertIn("\\includegraphics[width=0.8\\textwidth]{figures/plot.png}", snippet)
        self.assertIn("\\caption{Plot}", snippet)
        self.assertIn("\\label{fig:plot}", snippet)

    def test_side_by_side_snippet(self) -> None:
        snippet = side_by_side_figure_snippet(
            SideBySideFigureSpec(
                left_image_path="figures/a.png",
                right_image_path="figures/b.png",
                left_caption="A",
                right_caption="B",
                caption="Both",
            )
        )

        self.assertIn("\\begin{subfigure}{0.48\\textwidth}", snippet)
        self.assertIn("\\includegraphics[width=\\linewidth]{figures/a.png}", snippet)
        self.assertIn("\\caption{Both}", snippet)

    def test_vertical_figure_layout_preserves_individual_widths(self) -> None:
        snippet = figure_layout_snippet(
            FigureLayoutSpec(
                layout=FigureLayout.VERTICAL,
                items=(
                    FigureLayoutItem("figures/a.png", 0.80, "Top"),
                    FigureLayoutItem("figures/b.png", 0.65, "Bottom"),
                ),
                caption="Vertical pair",
            )
        )

        self.assertIn("\\begin{subfigure}{0.8\\textwidth}", snippet)
        self.assertIn("\\begin{subfigure}{0.65\\textwidth}", snippet)
        self.assertIn("\\par\\medskip", snippet)
        self.assertNotIn("\\hfill", snippet)

    def test_grid_figure_layout_builds_two_rows_without_distortion(self) -> None:
        snippet = figure_layout_snippet(
            FigureLayoutSpec(
                layout=FigureLayout.GRID_2X2,
                items=tuple(
                    FigureLayoutItem(f"figures/{name}.png", width, name.upper())
                    for name, width in (("a", 0.55), ("b", 0.40), ("c", 0.45), ("d", 0.50))
                ),
                caption="Grid",
                label="fig:grid",
            )
        )

        self.assertEqual(snippet.count("\\begin{subfigure}"), 4)
        self.assertEqual(snippet.count("\\hfill"), 2)
        self.assertEqual(snippet.count("\\par\\medskip"), 1)
        self.assertEqual(snippet.count("\\includegraphics[width=\\linewidth]"), 4)
        self.assertNotIn("height=", snippet)
        self.assertIn("\\label{fig:grid}", snippet)

    def test_horizontal_and_grid_layout_reject_row_overflow(self) -> None:
        with self.assertRaisesRegex(ValueError, "宽度合计"):
            figure_layout_snippet(
                FigureLayoutSpec(
                    layout=FigureLayout.HORIZONTAL,
                    items=(
                        FigureLayoutItem("figures/a.png", 0.60),
                        FigureLayoutItem("figures/b.png", 0.50),
                    ),
                )
            )

    def test_figure_layout_requires_the_layout_image_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "4 张图片"):
            figure_layout_snippet(
                FigureLayoutSpec(
                    layout=FigureLayout.GRID_2X2,
                    items=(
                        FigureLayoutItem("figures/a.png"),
                        FigureLayoutItem("figures/b.png"),
                    ),
                )
            )

    def test_table_snippet_uses_booktabs(self) -> None:
        snippet = table_snippet(TableSpec(rows=2, columns=2, caption="Data", label="tab:data"))

        self.assertIn("\\toprule", snippet)
        self.assertIn("Header 1 & Header 2", snippet)
        self.assertIn("Cell 2-1 & Cell 2-2", snippet)
        self.assertIn("\\label{tab:data}", snippet)

    def test_table_snippet_uses_visual_editor_values(self) -> None:
        snippet = table_snippet(
            TableSpec(
                rows=2,
                columns=2,
                headers=("Mass", "Time"),
                cells=(("1 kg", "2 s"), ("3 kg", "4 s")),
            )
        )

        self.assertIn("Mass & Time", snippet)
        self.assertIn("1 kg & 2 s", snippet)
        self.assertIn("3 kg & 4 s", snippet)

    def test_hyperlink_snippet(self) -> None:
        self.assertEqual(
            hyperlink_snippet(HyperlinkSpec(text="OpenAI", url="https://openai.com")),
            "\\href{https://openai.com}{OpenAI}",
        )

    def test_ensure_packages_is_idempotent(self) -> None:
        text = "\\documentclass{article}\n\\usepackage{graphicx}\n\n\\begin{document}\nHi\n\\end{document}\n"

        updated_once = ensure_packages(text, FIGURE_PACKAGES)
        updated_twice = ensure_packages(updated_once, FIGURE_PACKAGES)

        self.assertEqual(updated_once, updated_twice)
        self.assertEqual(existing_packages(updated_once), {"graphicx"})

    def test_ensure_packages_inserts_after_documentclass(self) -> None:
        text = "\\documentclass{article}\n\n\\begin{document}\nHi\n\\end{document}\n"

        updated = ensure_packages(text, ("hyperref",))

        self.assertTrue(updated.startswith("\\documentclass{article}\n\\usepackage{hyperref}\n"))

    def test_template_contains_common_ia_structure(self) -> None:
        template = template_for_key("ib_ia_report")

        self.assertIn("\\usepackage{siunitx}", template.text)
        self.assertIn("\\section{Research Question}", template.text)
        self.assertEqual(template.filename, "IB_IA_Report.tex")

    def test_new_student_templates_are_available(self) -> None:
        self.assertIn("\\section{Uncertainty Analysis}", template_for_key("physics_ia").text)
        self.assertIn("% !TEX program = xelatex", template_for_key("chinese_xelatex_article").text)

    def test_custom_template_save_import_and_export(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = "\\documentclass{article}\n\\title{Demo Template}\n\\begin{document}\nHi\n\\end{document}\n"

            saved = save_custom_template("Demo Template", source, root)
            self.assertTrue(saved.key.startswith("custom:"))
            self.assertIn("Demo Template", template_for_key(saved.key, root).title)

            external = root / "external.tex"
            external.write_text("\\documentclass{article}\n\\title{External}\n", encoding="utf-8")
            imported = import_custom_template(external, directory=root)
            self.assertIn("External", imported.title)

            exported = export_template(saved.key, root / "shared-template", root)
            self.assertEqual(exported.suffix, ".tex")
            self.assertIn("\\documentclass{article}", exported.read_text(encoding="utf-8"))


@skipUnless(TOOLCHAIN.supports_engine(LaTeXEngine.XELATEX), "xelatex is not available")
class FigureLayoutCompileTests(TestCase):
    def test_adjustable_grid_compiles_with_subcaption(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            fixture = Path(__file__).parents[1] / "app" / "assets" / "icstex_cover.png"
            for name in ("a.png", "b.png", "c.png", "d.png"):
                shutil.copyfile(fixture, project / name)
            snippet = figure_layout_snippet(
                FigureLayoutSpec(
                    layout=FigureLayout.GRID_2X2,
                    items=tuple(
                        FigureLayoutItem(name, width, name[0].upper())
                        for name, width in zip(
                            ("a.png", "b.png", "c.png", "d.png"),
                            (0.55, 0.40, 0.45, 0.50),
                            strict=True,
                        )
                    ),
                    caption="Four panels",
                    label="fig:grid",
                )
            )
            main = project / "main.tex"
            main.write_text(
                "\\documentclass{article}\n"
                "\\usepackage{graphicx}\n"
                "\\usepackage{subcaption}\n"
                "\\begin{document}\n"
                f"{snippet}\n"
                "\\end{document}\n",
                encoding="utf-8",
            )

            result = CompileManager(
                main,
                toolchain=TOOLCHAIN,
                engine=LaTeXEngine.XELATEX,
            ).compile_now(BuildPurpose.FINAL, timeout_seconds=300)

            self.assertTrue(result.ok, result.combined_output)
