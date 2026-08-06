from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

from app.core.compiler import CompileManager
from app.core.latex_tools import detect_toolchain


TOOLCHAIN = detect_toolchain()


@skipUnless(TOOLCHAIN.is_compile_ready, "latexmk or pdflatex is not available")
class CompileIntegrationTests(TestCase):
    def test_simple_document_compiles_into_build_directory(self) -> None:
        with TemporaryDirectory() as directory:
            tex = Path(directory) / "main.tex"
            tex.write_text(
                "\\documentclass{article}\n"
                "\\begin{document}\n"
                "Hello integration test.\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            manager = CompileManager(tex, toolchain=TOOLCHAIN)

            result = manager.compile_now()

            self.assertIsNotNone(result)
            assert result is not None
            self.assertTrue(result.ok, result.combined_output)
            self.assertEqual(result.pdf_file.parent, Path(directory).resolve() / ".latex_build")
            self.assertTrue(result.pdf_file.exists())

    def test_visual_formula_write_back_compiles(self) -> None:
        with TemporaryDirectory() as directory:
            tex = Path(directory) / "main.tex"
            tex.write_text(
                "\\documentclass{article}\n"
                "\\usepackage{amsmath}\n"
                "\\begin{document}\n"
                "The result is \\(\\frac{a}{b}\\) under this condition.\n"
                "Inline: $E=\\gamma mc^2$ and $x^2+\\frac{x^2+1}{\\sqrt{y_1+y_2}}$.\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            manager = CompileManager(tex, toolchain=TOOLCHAIN)

            result = manager.compile_now()

            self.assertIsNotNone(result)
            assert result is not None
            self.assertTrue(result.ok, result.combined_output)
            self.assertTrue(result.pdf_file.exists())
