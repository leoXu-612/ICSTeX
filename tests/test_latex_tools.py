from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.core.latex_tools import LaTeXEngine, LaTeXToolchain, detect_toolchain


class LaTeXToolchainTests(TestCase):
    def test_prefers_latexmk_over_pdflatex(self) -> None:
        tools = LaTeXToolchain(
            latexmk="/bin/latexmk",
            pdflatex="/bin/pdflatex",
            xelatex="/bin/xelatex",
            lualatex="/bin/lualatex",
            texcount=None,
            synctex=None,
        )

        command = tools.compile_command(Path("main.tex"), Path("build"))

        self.assertEqual(command[0], "/bin/latexmk")
        self.assertIn("-pdf", command)
        self.assertIn("-norc", command)
        self.assertIn("-no-shell-escape", command)
        self.assertIn("-synctex=1", command)
        self.assertIn("-outdir=build", command)

    def test_latexmk_xelatex_engine_flag(self) -> None:
        tools = LaTeXToolchain(
            latexmk="/bin/latexmk",
            pdflatex="/bin/pdflatex",
            xelatex="/bin/xelatex",
            lualatex="/bin/lualatex",
            texcount=None,
            synctex=None,
        )

        command = tools.compile_command(Path("main.tex"), Path("build"), LaTeXEngine.XELATEX)

        self.assertEqual(command[0], "/bin/latexmk")
        self.assertIn("-xelatex", command)
        self.assertNotIn("-pdf", command)

    def test_latexmk_lualatex_engine_flag(self) -> None:
        tools = LaTeXToolchain(
            latexmk="/bin/latexmk",
            pdflatex="/bin/pdflatex",
            xelatex="/bin/xelatex",
            lualatex="/bin/lualatex",
            texcount=None,
            synctex=None,
        )

        command = tools.compile_command(Path("main.tex"), Path("build"), LaTeXEngine.LUALATEX)

        self.assertEqual(command[0], "/bin/latexmk")
        self.assertIn("-lualatex", command)

    def test_falls_back_to_pdflatex(self) -> None:
        tools = LaTeXToolchain(
            latexmk=None,
            pdflatex="/bin/pdflatex",
            xelatex="/bin/xelatex",
            lualatex="/bin/lualatex",
            texcount=None,
            synctex=None,
        )

        command = tools.compile_command(Path("main.tex"), Path("build"))

        self.assertEqual(command[0], "/bin/pdflatex")
        self.assertIn("-no-shell-escape", command)
        self.assertIn("-output-directory=build", command)

    def test_direct_xelatex_without_latexmk(self) -> None:
        tools = LaTeXToolchain(
            latexmk=None,
            pdflatex="/bin/pdflatex",
            xelatex="/bin/xelatex",
            lualatex="/bin/lualatex",
            texcount=None,
            synctex=None,
        )

        command = tools.compile_command(Path("main.tex"), Path("build"), LaTeXEngine.XELATEX)

        self.assertEqual(command[0], "/bin/xelatex")

    def test_missing_compiler_is_not_ready(self) -> None:
        tools = LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None)

        self.assertFalse(tools.is_compile_ready)
        with self.assertRaises(RuntimeError):
            tools.compile_command(Path("main.tex"), Path("build"))

    def test_supports_engine_requires_engine_binary(self) -> None:
        tools = LaTeXToolchain(latexmk="/bin/latexmk", pdflatex="/bin/pdflatex")

        self.assertTrue(tools.supports_engine(LaTeXEngine.PDFLATEX))
        self.assertFalse(tools.supports_engine(LaTeXEngine.XELATEX))

    def test_detect_toolchain_uses_runtime_path_helper(self) -> None:
        found = {
            "latexmk": "/Library/TeX/texbin/latexmk",
            "pdflatex": "/Library/TeX/texbin/pdflatex",
        }

        with patch("app.core.latex_tools.which_tool", side_effect=lambda name: found.get(name)):
            tools = detect_toolchain()

        self.assertEqual(tools.latexmk, "/Library/TeX/texbin/latexmk")
        self.assertEqual(tools.pdflatex, "/Library/TeX/texbin/pdflatex")
