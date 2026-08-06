from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.latex_tools import LaTeXEngine
from app.core.magic_comments import magic_engine_for, magic_root_for, parse_magic_comments


class MagicCommentTests(TestCase):
    def test_parses_root_relative_to_source_directory(self) -> None:
        comments = parse_magic_comments(
            "% !TEX root = ../main.tex\n\\section{Intro}",
            base_dir=Path("/tmp/project/chapters"),
        )

        self.assertEqual(comments.root, Path("/tmp/project/chapters/../main.tex"))

    def test_parses_tex_program(self) -> None:
        comments = parse_magic_comments("% !TEX program = xelatex\n\\documentclass{article}")

        self.assertEqual(comments.program, LaTeXEngine.XELATEX)

    def test_parses_texshop_ts_program(self) -> None:
        comments = parse_magic_comments("% !TEX TS-program = lualatex\n")

        self.assertEqual(comments.program, LaTeXEngine.LUALATEX)

    def test_parses_first_line_percent_ampersand_program(self) -> None:
        comments = parse_magic_comments("%&pdflatex\n\\documentclass{article}")

        self.assertEqual(comments.program, LaTeXEngine.PDFLATEX)

    def test_reads_magic_root_only_when_target_exists_by_default(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            chapter = root / "chapter.tex"
            chapter.write_text("% !TEX root = main.tex\nBody", encoding="utf-8")

            self.assertIsNone(magic_root_for(chapter))

            main = root / "main.tex"
            main.write_text("\\documentclass{article}", encoding="utf-8")

            self.assertEqual(magic_root_for(chapter), main.resolve())

    def test_reads_magic_engine_from_file(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("% !TEX program = xelatex\n", encoding="utf-8")

            self.assertEqual(magic_engine_for(source), LaTeXEngine.XELATEX)
