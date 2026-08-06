from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import TestCase

from app.core.paths import (
    built_pdf_for,
    find_root_tex,
    included_tex_files,
    latex_dependency_closure,
    preview_assets_dir_for,
    preview_build_dir_for,
    resolve_root_tex,
)


class PathTests(TestCase):
    def test_find_root_prefers_main_tex_with_documentclass(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "chapter.tex").write_text("Chapter text", encoding="utf-8")
            (root / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nHi\n\\end{document}", encoding="utf-8")

            self.assertEqual(find_root_tex(root), (root / "main.tex").resolve())

    def test_find_root_honors_magic_root_when_opening_subfile(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "main.tex"
            chapter = root / "chapters" / "intro.tex"
            chapter.parent.mkdir()
            main.write_text("\\documentclass{article}\n\\begin{document}\n\\input{chapters/intro}\n\\end{document}", encoding="utf-8")
            chapter.write_text("% !TEX root = ../main.tex\nChapter text", encoding="utf-8")

            self.assertEqual(find_root_tex(chapter), main.resolve())
            self.assertEqual(resolve_root_tex(chapter).source, "magic")

    def test_find_root_infers_parent_from_input_relationship(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "main.tex"
            chapter = root / "chapters" / "intro.tex"
            chapter.parent.mkdir()
            main.write_text("\\documentclass{article}\n\\begin{document}\n\\input{chapters/intro}\n\\end{document}", encoding="utf-8")
            chapter.write_text("Chapter text without magic comment", encoding="utf-8")

            self.assertEqual(find_root_tex(chapter), main.resolve())
            self.assertEqual(resolve_root_tex(chapter).source, "inferred")

    def test_real_multifile_project_resolves_root_from_intro_chapter(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            chapters = root / "chapters"
            chapters.mkdir()
            main = root / "main.tex"
            intro = chapters / "intro.tex"
            method = chapters / "method.tex"
            main.write_text(
                "\\documentclass{article}\n"
                "\\begin{document}\n"
                "\\input{chapters/intro}\n"
                "\\include{chapters/method}\n"
                "% \\input{chapters/ignored}\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            intro.write_text("Intro", encoding="utf-8")
            method.write_text("Method", encoding="utf-8")

            resolution = resolve_root_tex(intro)

            self.assertEqual(resolution.root, main.resolve())
            self.assertEqual(resolution.source, "inferred")
            self.assertNotIn((chapters / "ignored.tex").resolve(), included_tex_files(main))

    def test_subfiles_package_child_resolves_to_parent(self) -> None:
        # With the subfiles package, the child has its own \documentclass{subfiles}
        # so is_latex_root() is True for it too; resolution must still prefer the
        # parent that \subfile{}s it rather than treating the child as its own root.
        with TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "main.tex"
            chapter = root / "chapters" / "intro.tex"
            chapter.parent.mkdir()
            main.write_text(
                "\\documentclass{article}\n"
                "\\usepackage{subfiles}\n"
                "\\begin{document}\n"
                "\\subfile{chapters/intro}\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            chapter.write_text(
                "\\documentclass[../main.tex]{subfiles}\n\\begin{document}\nIntro\n\\end{document}\n",
                encoding="utf-8",
            )

            resolution = resolve_root_tex(chapter)

            self.assertEqual(resolution.root, main.resolve())
            self.assertEqual(resolution.source, "inferred")

    def test_find_root_prefers_candidate_that_includes_subfiles(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            standalone = root / "standalone.tex"
            thesis = root / "thesis.tex"
            chapter = root / "chapter.tex"
            standalone.write_text("\\documentclass{article}\n\\begin{document}\nStandalone\n\\end{document}", encoding="utf-8")
            thesis.write_text("\\documentclass{article}\n\\begin{document}\n\\include{chapter}\n\\end{document}", encoding="utf-8")
            chapter.write_text("Chapter", encoding="utf-8")

            self.assertEqual(find_root_tex(root), thesis.resolve())

    def test_included_tex_files_ignores_commented_input(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "main.tex"
            main.write_text(
                "\\documentclass{article}\n"
                "% \\input{ignored}\n"
                "\\input{chapters/real}\n"
                "\\include{appendix}\n"
                "\\subfile{sections/method.tex}\n",
                encoding="utf-8",
            )

            self.assertEqual(
                included_tex_files(main),
                (
                    (root / "chapters" / "real.tex").resolve(),
                    (root / "appendix.tex").resolve(),
                    (root / "sections" / "method.tex").resolve(),
                ),
            )

    def test_dependency_closure_is_recursive(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "chapters").mkdir()
            main = root / "main.tex"
            chapter = root / "chapters" / "ch1.tex"
            section = root / "chapters" / "sec1.tex"
            main.write_text("\\documentclass{article}\n\\input{chapters/ch1}", encoding="utf-8")
            chapter.write_text("\\input{sec1}", encoding="utf-8")
            section.write_text("deep text", encoding="utf-8")

            closure = latex_dependency_closure(main)

            self.assertIn(main.resolve(), closure)
            self.assertIn(chapter.resolve(), closure)
            self.assertIn(section.resolve(), closure)

    def test_dependency_closure_survives_include_cycles(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            a = root / "a.tex"
            b = root / "b.tex"
            a.write_text("\\input{b}", encoding="utf-8")
            b.write_text("\\input{a}", encoding="utf-8")

            closure = latex_dependency_closure(a)

            self.assertEqual(closure, frozenset({a.resolve(), b.resolve()}))

    def test_built_pdf_uses_latex_build_directory(self) -> None:
        pdf = built_pdf_for(Path("/tmp/project/main.tex"))

        self.assertEqual(pdf, Path("/tmp/project/.latex_build/main.pdf").resolve())

    def test_preview_paths_are_root_scoped_outside_canonical_build(self) -> None:
        main = Path("/tmp/project/main.tex")
        other = Path("/tmp/project/other.tex")

        main_build = preview_build_dir_for(main)
        other_build = preview_build_dir_for(other)

        self.assertEqual(main_build.parent.parent, Path("/tmp/project/.icstex/preview").resolve())
        self.assertEqual(preview_assets_dir_for(main).parent, main_build.parent)
        self.assertNotEqual(main_build, other_build)
        self.assertNotIn(".latex_build", main_build.parts)
