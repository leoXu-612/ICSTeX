from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.diagnostics import (
    SEVERITY_ERROR,
    analyze_project,
    apply_fix,
    explain_latex_error,
    image_diagnostics,
    package_diagnostics,
    structure_diagnostics,
)
from app.core.latex_insertions import existing_packages
from app.core.latex_tools import LaTeXToolchain
from app.core.log_parser import LaTeXError


class DiagnosticsTests(TestCase):
    def test_explains_undefined_control_sequence_with_package_fix(self) -> None:
        diagnostic = explain_latex_error(LaTeXError("Undefined control sequence. \\includegraphics", line=12))

        self.assertEqual(diagnostic.severity, SEVERITY_ERROR)
        self.assertIn("graphicx", diagnostic.message)
        self.assertIsNotNone(diagnostic.fix)
        assert diagnostic.fix is not None
        self.assertEqual(diagnostic.fix.packages, ("graphicx",))

    def test_package_diagnostics_detect_missing_package_and_fix_is_idempotent(self) -> None:
        text = "\\documentclass{article}\n\\begin{document}\n\\includegraphics{figures/a.png}\n\\end{document}\n"

        diagnostics = package_diagnostics(text)
        fixed = apply_fix(text, diagnostics[0].fix)  # type: ignore[arg-type]
        fixed_again = apply_fix(fixed, diagnostics[0].fix)  # type: ignore[arg-type]

        self.assertEqual(diagnostics[0].fix.packages, ("graphicx",))  # type: ignore[union-attr]
        self.assertIn("graphicx", existing_packages(fixed))
        self.assertEqual(fixed, fixed_again)

    def test_textcolor_diagnostic_offers_xcolor_fix(self) -> None:
        text = (
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\textcolor{red}{Result}\n"
            "\\end{document}\n"
        )

        diagnostics = package_diagnostics(text)

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].title, "缺少 xcolor")
        self.assertEqual(diagnostics[0].fix.packages, ("xcolor",))  # type: ignore[union-attr]

    def test_textcolor_diagnostic_accepts_existing_xcolor(self) -> None:
        text = (
            "\\documentclass{article}\n"
            "\\usepackage{xcolor}\n"
            "\\begin{document}\n"
            "\\textcolor{red}{Result}\n"
            "\\end{document}\n"
        )

        self.assertEqual(package_diagnostics(text), [])

    def test_math_text_diagnostic_offers_amsmath_fix(self) -> None:
        text = "\\documentclass{article}\n\\begin{document}\n$\\text{result}$\n\\end{document}\n"

        diagnostics = package_diagnostics(text)

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].fix.packages, ("amsmath",))  # type: ignore[union-attr]

    def test_image_diagnostics_detect_missing_relative_graphic(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tex = root / "main.tex"
            tex.write_text("", encoding="utf-8")

            diagnostics = image_diagnostics("\\includegraphics{figures/missing.png}", root_file=tex)

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].title, "找不到图片文件")

    def test_image_diagnostics_accept_extensionless_existing_graphic(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tex = root / "main.tex"
            figures = root / "figures"
            figures.mkdir()
            (figures / "plot.png").write_text("", encoding="utf-8")

            diagnostics = image_diagnostics("\\includegraphics{figures/plot}", root_file=tex)

        self.assertEqual(diagnostics, [])

    def test_analyze_project_collects_refs_cites_duplicates_and_toolchain(self) -> None:
        text = (
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\label{sec:intro}\n"
            "\\label{sec:intro}\n"
            "\\ref{fig:missing}\n"
            "\\cite{MissingKey}\n"
            "\\end{document}\n"
        )
        toolchain = LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None)

        diagnostics = analyze_project(text, root_file=Path("main.tex"), bib_text="", toolchain=toolchain)
        titles = {diagnostic.title for diagnostic in diagnostics}

        self.assertIn("未找到 LaTeX 编译器", titles)
        self.assertIn("重复 label", titles)
        self.assertIn("未定义 ref", titles)
        self.assertIn("未定义 citation", titles)

    def test_structure_diagnostics_detect_missing_document_and_unclosed_environment(self) -> None:
        diagnostics = structure_diagnostics("\\begin{itemize}\n\\item A\n")
        titles = {diagnostic.title for diagnostic in diagnostics}

        self.assertIn("缺少 documentclass", titles)
        self.assertIn("缺少正文开始标记", titles)
        self.assertIn("缺少正文结束标记", titles)
        self.assertIn("环境没有结束", titles)

    def test_structure_diagnostics_warns_when_citations_have_no_bibliography(self) -> None:
        diagnostics = structure_diagnostics(
            "\\documentclass{article}\n\\begin{document}\n\\cite{Storm2024}\n\\end{document}\n"
        )

        self.assertIn("引用可能不会输出", {diagnostic.title for diagnostic in diagnostics})

    def test_env_balance_ignores_begin_inside_verbatim(self) -> None:
        diagnostics = structure_diagnostics(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\begin{verbatim}\n"
            "\\begin{foo}\n"
            "this never matters\n"
            "\\end{verbatim}\n"
            "\\end{document}\n"
        )
        titles = {diagnostic.title for diagnostic in diagnostics}

        # No env-balance complaints at all (verbatim hides the fake \begin{foo})
        self.assertNotIn("环境没有结束", titles)
        self.assertNotIn("多余的 end 环境", titles)
        self.assertNotIn("环境嵌套不匹配", titles)

    def test_env_balance_detects_extra_end_environment(self) -> None:
        diagnostics = structure_diagnostics(
            "\\documentclass{article}\n\\begin{document}\n\\end{itemize}\n\\end{document}\n"
        )
        titles = {diagnostic.title for diagnostic in diagnostics}

        self.assertIn("多余的 end 环境", titles)

    def test_env_balance_detects_mismatched_pair(self) -> None:
        diagnostics = structure_diagnostics(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\begin{outer}\n"
            "\\begin{inner}\n"
            "\\end{outer}\n"
            "\\end{inner}\n"
            "\\end{document}\n"
        )
        titles = {diagnostic.title for diagnostic in diagnostics}

        self.assertIn("环境嵌套不匹配", titles)

    def test_env_balance_ignores_begin_inside_comment(self) -> None:
        diagnostics = structure_diagnostics(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "% \\begin{itemize}\n"
            "Hello.\n"
            "\\end{document}\n"
        )
        titles = {diagnostic.title for diagnostic in diagnostics}

        self.assertNotIn("环境没有结束", titles)
