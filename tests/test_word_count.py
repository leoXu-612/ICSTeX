from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.core.latex_tools import LaTeXToolchain
from app.core.word_count import count_project, count_text, count_words


class WordCountTests(TestCase):
    def test_fallback_counts_text_and_ignores_comments_and_commands(self) -> None:
        with TemporaryDirectory() as directory:
            tex = Path(directory) / "main.tex"
            tex.write_text(
                "\\section{Introduction}\n"
                "Hello world from LaTeX. % hidden words here\n"
                "$x + y$\n"
                "中文\n",
                encoding="utf-8",
            )

            result = count_words(
                tex,
                LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
            )

        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.words, 7)
        self.assertEqual(result.effective_words, 6)
        self.assertEqual(result.header_words, 1)
        self.assertEqual(result.formulas, 1)

    def test_fallback_breaks_down_headers_captions_math_and_numbers(self) -> None:
        text = (
            "\\documentclass{article}\n"
            "\\title{My IA 2024}\n"
            "\\begin{document}\n"
            "\\maketitle\n"
            "\\section{Research Question}\n"
            "The cart moved 12.8 cm in 3 trials.\n"
            "\\begin{equation}F=ma\\end{equation}\n"
            "\\begin{figure}\n"
            "\\includegraphics{figures/trial.png}\n"
            "\\caption{Trial graph 2024}\n"
            "\\end{figure}\n"
            "\\end{document}\n"
        )

        result = count_text(
            text,
            toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
        )

        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.effective_words, 6)
        self.assertEqual(result.header_words, 4)
        self.assertEqual(result.caption_words, 2)
        self.assertEqual(result.numbers, 4)
        self.assertEqual(result.math_display, 1)
        self.assertEqual(result.formulas, 1)
        self.assertEqual(result.total_words, 16)

    def test_count_text_handles_unsaved_editor_content(self) -> None:
        result = count_text(
            "\\begin{document}Hello 42 world.\\end{document}",
            toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
        )

        self.assertEqual(result.effective_words, 2)
        self.assertEqual(result.numbers, 1)
        self.assertEqual(result.total_words, 3)
        self.assertIn("未找到 texcount", " ".join(result.warnings))

    def test_fallback_counts_unicode_words_and_cjk_characters(self) -> None:
        result = count_text(
            "\\begin{document}Résumé naïve student's teacher’s 中文\\end{document}",
            toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
        )

        self.assertEqual(result.effective_words, 6)
        preview = "".join(segment.text for segment in result.visual_segments)
        self.assertIn("Résumé", preview)
        self.assertIn("teacher’s", preview)

    def test_count_text_warns_when_texcount_fails(self) -> None:
        result = count_text(
            "\\begin{document}Hello world.\\end{document}",
            toolchain=LaTeXToolchain(
                latexmk="/bin/latexmk",
                pdflatex="/bin/pdflatex",
                texcount="/missing/texcount",
                synctex=None,
            ),
        )

        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.effective_words, 2)
        self.assertIn("texcount 调用失败", " ".join(result.warnings))

    def test_fallback_ignores_words_inside_verbatim(self) -> None:
        text = (
            "\\begin{document}\n"
            "Hello world.\n"
            "\\begin{verbatim}\n"
            "secret hidden token inside verbatim block\n"
            "\\end{verbatim}\n"
            "After.\n"
            "\\end{document}\n"
        )

        result = count_text(
            text,
            toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
        )

        self.assertEqual(result.source, "fallback")
        # body should only include "Hello world." and "After.", not verbatim content
        self.assertEqual(result.effective_words, 3)

    def test_fallback_ignores_words_inside_lstlisting(self) -> None:
        text = (
            "\\begin{document}\n"
            "Code below.\n"
            "\\begin{lstlisting}\n"
            "int main() { return 0; }\n"
            "\\end{lstlisting}\n"
            "Done.\n"
            "\\end{document}\n"
        )

        result = count_text(
            text,
            toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
        )

        self.assertEqual(result.effective_words, 3)

    def test_fallback_ignores_words_inside_thebibliography(self) -> None:
        text = (
            "\\begin{document}\n"
            "Hello world.\n"
            "\\begin{thebibliography}{9}\n"
            "\\bibitem{a} Some Author Name, A Very Long Reference Title About Things.\n"
            "\\end{thebibliography}\n"
            "\\end{document}\n"
        )

        result = count_text(
            text,
            toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
        )

        self.assertEqual(result.source, "fallback")
        # body should only include "Hello world.", not the bibliography entry
        self.assertEqual(result.effective_words, 2)

    def test_fallback_href_only_counts_display_text(self) -> None:
        result = count_text(
            "\\begin{document}\\href{https://example.com}{Click me}\\end{document}",
            toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
        )

        # Only the visible "Click me" counts; the URL does not.
        self.assertEqual(result.effective_words, 2)

    def test_visual_segments_explain_counted_categories(self) -> None:
        result = count_text(
            "\\begin{document}\n"
            "\\section{Research 2026}\n"
            "Body text 42.\n"
            "$x+y$\n"
            "\\begin{figure}\\caption{Trial graph}\\end{figure}\n"
            "\\end{document}",
            toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
        )

        categories = {segment.category for segment in result.visual_segments}
        self.assertIn("headers", categories)
        self.assertIn("effective", categories)
        self.assertIn("numbers", categories)
        self.assertIn("math_inline", categories)
        self.assertIn("captions", categories)
        preview_text = "".join(segment.text for segment in result.visual_segments)
        self.assertIn("Research", preview_text)
        self.assertIn("Body text", preview_text)
        self.assertNotIn("includegraphics", preview_text)

    def test_project_preview_includes_root_and_child_with_texcount_total(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            child = Path(directory) / "child.tex"
            root.write_text(
                "\\documentclass{article}\n\\begin{document}\n"
                "Root text here.\\input{child}\n\\end{document}\n",
                encoding="utf-8",
            )
            child.write_text("Child content has five visible words.\n", encoding="utf-8")
            completed = type("Result", (), {
                "returncode": 0,
                "stdout": "ICSTEX_WORDCOUNT\t9\t0\t0\t0\t0\t0\t0\t9\n",
                "stderr": "",
            })()

            with patch("app.core.word_count.subprocess.run", return_value=completed):
                result = count_project(
                    root,
                    {root: root.read_text(encoding="utf-8")},
                    LaTeXToolchain(latexmk=None, pdflatex=None, texcount="texcount", synctex=None),
                )

        self.assertEqual(result.effective_words, 9)
        by_source = {
            source: "".join(segment.text for segment in result.visual_segments if segment.source == source)
            for source in {segment.source for segment in result.visual_segments}
        }
        self.assertIn("Root text here", by_source["main.tex"])
        self.assertIn("Child content has five visible words", by_source["child.tex"])

    def test_project_nested_include_order_and_cycle_are_stable(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            first = Path(directory) / "first.tex"
            second = Path(directory) / "second.tex"
            root.write_text("\\begin{document}Root.\\input{first}\\end{document}", encoding="utf-8")
            first.write_text("First.\\input{second}", encoding="utf-8")
            second.write_text("Second.\\input{first}", encoding="utf-8")

            result = count_project(
                root,
                toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
            )

        sources = list(dict.fromkeys(segment.source for segment in result.visual_segments))
        self.assertEqual(sources, ["main.tex", "first.tex", "second.tex"])
        self.assertEqual(result.effective_words, 3)

    def test_project_missing_child_warns_and_keeps_root_text(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            root.write_text(
                "\\begin{document}Visible root words.\\input{missing}\\end{document}",
                encoding="utf-8",
            )

            result = count_project(
                root,
                toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
            )

        self.assertEqual(result.effective_words, 3)
        self.assertIn("无法读取引用文件：missing.tex", " ".join(result.warnings))

    def test_project_uses_unsaved_child_override_without_touching_disk(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            child = Path(directory) / "child.tex"
            root.write_text("\\begin{document}Root.\\input{child}\\end{document}", encoding="utf-8")
            child.write_text("Old disk text.", encoding="utf-8")

            result = count_project(
                root,
                {child: "Unsaved child buffer has five words."},
                LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
            )

            self.assertEqual(child.read_text(encoding="utf-8"), "Old disk text.")
        preview = "".join(segment.text for segment in result.visual_segments)
        self.assertIn("Unsaved child buffer has five words", preview)
        self.assertNotIn("Old disk text", preview)
        self.assertEqual(result.effective_words, 7)

    def test_shadow_project_rewrites_absolute_include_to_unsaved_copy(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            child = Path(directory) / "child.tex"
            child.write_text("Old disk text.", encoding="utf-8")
            root.write_text(
                "\\begin{document}Root.\\input{" + str(child) + "}\\end{document}",
                encoding="utf-8",
            )
            shadow_paths: list[Path] = []

            def fake_run(command, **_kwargs):
                shadow_root = Path(command[-1])
                shadow_paths.append(shadow_root)
                shadow_text = shadow_root.read_text(encoding="utf-8")
                shadow_child = Path(shadow_text.split("\\input{", 1)[1].split("}", 1)[0])
                self.assertNotEqual(shadow_child, child)
                self.assertEqual(
                    shadow_child.read_text(encoding="utf-8"),
                    "Unsaved replacement has four words.",
                )
                return type("Result", (), {
                    "returncode": 0,
                    "stdout": "ICSTEX_WORDCOUNT\t6\t0\t0\t0\t0\t0\t0\t6\n",
                    "stderr": "",
                })()

            with patch("app.core.word_count.subprocess.run", side_effect=fake_run), patch(
                "app.core.word_count.os.path.commonpath",
                side_effect=ValueError("different drives"),
            ):
                result = count_project(
                    root,
                    {child: "Unsaved replacement has four words."},
                    LaTeXToolchain(latexmk=None, pdflatex=None, texcount="texcount", synctex=None),
                )

            self.assertEqual(child.read_text(encoding="utf-8"), "Old disk text.")
            self.assertEqual(len(shadow_paths), 1)
            self.assertFalse(shadow_paths[0].exists())
        self.assertEqual(result.effective_words, 6)

    def test_shadow_project_is_removed_when_texcount_cannot_start(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            root.write_text("\\begin{document}Fallback words.\\end{document}", encoding="utf-8")
            shadow_paths: list[Path] = []

            def fail_run(command, **_kwargs):
                shadow_paths.append(Path(command[-1]))
                raise OSError("cannot start")

            with patch("app.core.word_count.subprocess.run", side_effect=fail_run):
                result = count_project(
                    root,
                    {root: root.read_text(encoding="utf-8")},
                    LaTeXToolchain(latexmk=None, pdflatex=None, texcount="texcount", synctex=None),
                )

            self.assertEqual(len(shadow_paths), 1)
            self.assertFalse(shadow_paths[0].exists())
        self.assertEqual(result.source, "fallback")
        self.assertIn("texcount 调用失败", " ".join(result.warnings))

    def test_project_does_not_count_preamble_include_as_body(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            preamble = Path(directory) / "preamble.tex"
            body = Path(directory) / "body.tex"
            root.write_text(
                "\\documentclass{article}\n"
                "\\input{preamble}\n"
                "\\begin{document}\n"
                "\\input{body}\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            preamble.write_text(
                "\\newcommand{\\hidden}{These definition words are not body}\n"
                "\\title{Visible Title}\n",
                encoding="utf-8",
            )
            body.write_text("Actual body words.\n", encoding="utf-8")

            result = count_project(
                root,
                toolchain=LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
            )

        self.assertEqual(result.effective_words, 3)
        self.assertEqual(result.header_words, 2)
        preview = "".join(segment.text for segment in result.visual_segments)
        self.assertIn("Visible Title", preview)
        self.assertIn("Actual body words", preview)
        self.assertNotIn("definition words", preview)

    def test_project_decodes_declared_cp1252_child_without_replacement(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            child = Path(directory) / "child.tex"
            root.write_text("\\begin{document}Root.\\input{child}\\end{document}", encoding="utf-8")
            child.write_bytes(
                "% !TEX encoding = Windows Latin 1\nRésumé body.\n".encode("cp1252")
            )

            result = count_project(
                root,
                {root: root.read_text(encoding="utf-8")},
                LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
            )

        preview = "".join(segment.text for segment in result.visual_segments)
        self.assertIn("Résumé body", preview)
        self.assertNotIn("�", preview)
        self.assertNotIn("无法按", " ".join(result.warnings))

    def test_declared_cp1252_child_uses_utf8_shadow_even_without_overrides(self) -> None:
        # texcount runs with -utf8; feeding it raw CP1252 disk bytes splits
        # accented words and inflates totals versus the (correct) preview.
        # Non-UTF-8 projects must therefore go through the UTF-8 shadow tree
        # even when no unsaved override exists.
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            child = Path(directory) / "child.tex"
            root.write_text("\\begin{document}Root.\\input{child}\\end{document}", encoding="utf-8")
            child_bytes = "% !TEX encoding = Windows Latin 1\nRésumé body text.\n".encode("cp1252")
            child.write_bytes(child_bytes)
            invoked_roots: list[Path] = []

            def fake_run(command, **_kwargs):
                shadow_root = Path(command[-1])
                invoked_roots.append(shadow_root)
                shadow_text = shadow_root.read_text(encoding="utf-8")
                target = Path(shadow_text.split("\\input{", 1)[1].split("}", 1)[0])
                if target.suffix == "":
                    target = target.with_suffix(".tex")
                # Shadow child must be valid UTF-8 with the accent intact.
                self.assertIn("Résumé body text", target.read_text(encoding="utf-8"))
                return type("Result", (), {
                    "returncode": 0,
                    "stdout": "ICSTEX_WORDCOUNT\t4\t0\t0\t0\t0\t0\t0\t4\n",
                    "stderr": "",
                })()

            with patch("app.core.word_count.subprocess.run", side_effect=fake_run):
                result = count_project(
                    root,
                    {},
                    LaTeXToolchain(latexmk=None, pdflatex=None, texcount="texcount", synctex=None),
                )

            self.assertEqual(len(invoked_roots), 1)
            self.assertNotEqual(invoked_roots[0], root)  # shadow, not the raw project
            self.assertEqual(child.read_bytes(), child_bytes)  # disk untouched
        self.assertEqual(result.source, "texcount")
        self.assertEqual(result.effective_words, 4)

    def test_undecodable_child_is_skipped_by_texcount_without_overrides(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            child = Path(directory) / "child.tex"
            child_bytes = b"\x81 invalid encoding words"
            child.write_bytes(child_bytes)
            root.write_text(
                "\\begin{document}Visible root.\\input{" + str(child) + "}\\end{document}",
                encoding="utf-8",
            )
            shadow_paths: list[Path] = []

            def fake_run(command, **_kwargs):
                shadow_root = Path(command[-1])
                shadow_paths.append(shadow_root)
                self.assertNotEqual(shadow_root, root)
                shadow_text = shadow_root.read_text(encoding="utf-8")
                shadow_child = Path(shadow_text.split("\\input{", 1)[1].split("}", 1)[0])
                self.assertNotEqual(shadow_child, child)
                self.assertEqual(shadow_child.read_text(encoding="utf-8"), "")
                return type("Result", (), {
                    "returncode": 0,
                    "stdout": "ICSTEX_WORDCOUNT\t2\t0\t0\t0\t0\t0\t0\t2\n",
                    "stderr": "",
                })()

            with patch("app.core.word_count.subprocess.run", side_effect=fake_run):
                result = count_project(
                    root,
                    {},
                    LaTeXToolchain(latexmk=None, pdflatex=None, texcount="texcount", synctex=None),
                )

            self.assertEqual(len(shadow_paths), 1)
            self.assertFalse(shadow_paths[0].exists())
            self.assertEqual(child.read_bytes(), child_bytes)
        self.assertEqual(result.source, "texcount")
        self.assertEqual(result.effective_words, 2)
        self.assertIn("无法按 utf-8 解码引用文件：child.tex", " ".join(result.warnings))

    def test_project_warns_instead_of_replacing_unknown_child_encoding(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            child = Path(directory) / "child.tex"
            root.write_text("\\begin{document}Visible root.\\input{child}\\end{document}", encoding="utf-8")
            child.write_bytes(b"\x81 invalid encoding")

            result = count_project(
                root,
                {root: root.read_text(encoding="utf-8")},
                LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None),
            )

        preview = "".join(segment.text for segment in result.visual_segments)
        self.assertIn("Visible root", preview)
        self.assertNotIn("invalid encoding", preview)
        self.assertIn("无法按 utf-8 解码引用文件：child.tex", " ".join(result.warnings))
