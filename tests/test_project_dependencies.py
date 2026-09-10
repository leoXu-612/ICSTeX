from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.project_dependencies import (
    observe_input, recorder_dependencies, safe_project_input, static_dependencies,
)


class ProjectDependencyTests(TestCase):
    def test_pdf_svg_and_rejected_image_candidates_are_exposed(self) -> None:
        with TemporaryDirectory() as directory:
            scope = Path(directory).resolve()
            root = scope / "main.tex"
            (scope / "plot.png").symlink_to(scope / "elsewhere.png")
            result = static_dependencies(root, scope, {root: r"\includesvg{diagram}\includepdf{appendix}\includegraphics{plot}"})
            self.assertIn(scope / "diagram.svg", result.paths)
            self.assertIn(scope / "appendix.pdf", result.paths)
            graphic = next(ref for ref in result.references if ref.command == "includegraphics")
            self.assertTrue(graphic.rejected_candidates)
            self.assertNotIn(scope / "plot.png", graphic.candidates)

    def test_custom_reader_preserves_buffers_and_bounds_reference_expansion(self) -> None:
        with TemporaryDirectory() as directory:
            scope = Path(directory).resolve()
            root, child = scope / "main.tex", scope / "child.tex"
            calls = []

            def reader(path):
                calls.append(path)
                if path == child:
                    return r"\bibliography{catalog,more,extra}"
                raise FileNotFoundError(path)

            result = static_dependencies(root, scope, {root: r"\input{child}"},
                                         source_reader=reader, max_references=2)
            self.assertFalse(result.complete)
            self.assertEqual(len(result.references), 2)
            self.assertNotIn(root, calls)
            self.assertIn(child, calls)
            self.assertNotIn(scope / "extra.bib", result.paths)

    def test_reference_limit_counts_unparsed_commands(self) -> None:
        with TemporaryDirectory() as directory:
            scope = Path(directory).resolve()
            root = scope / "main.tex"
            result = static_dependencies(root, scope, {root: r"\input\a\input\b\input\c"},
                                         max_references=1)
            self.assertFalse(result.complete)
            self.assertEqual(len(result.references), 1)
            self.assertTrue(result.references[0].unresolved)

    def test_static_inputs_include_unopened_missing_bib_styles_and_graphics(self) -> None:
        with TemporaryDirectory() as directory:
            scope = Path(directory).resolve()
            root = scope / "main.tex"
            root.write_text(
                "\\documentclass{local}\n\\usepackage{mystyle,graphicx}\n"
                "\\graphicspath{{figures/}}\n\\input{chapters/child}\n"
                "\\bibliography{refs,other}\n% \\input{commented}\n",
            )
            (scope / "chapters").mkdir()
            (scope / "chapters" / "child.tex").write_text(
                "\\includegraphics{plot}\n\\addbibresource{more.bib}\n\\input missing\n",
            )
            (scope / "mystyle.sty").write_text(r"\input{settings}")
            snapshot = static_dependencies(root, scope)
            self.assertTrue(snapshot.complete)
            for relative in (
                "main.tex", "chapters/child.tex", "refs.bib", "other.bib", "more.bib",
                "missing.tex", "local.cls", "mystyle.sty", "settings.tex", "figures/plot.png",
            ):
                self.assertIn(scope / relative, snapshot.paths)
            self.assertNotIn(scope / "commented.tex", snapshot.paths)

    def test_static_buffers_cycle_and_bounded_expansion(self) -> None:
        with TemporaryDirectory() as directory:
            scope = Path(directory).resolve()
            root = scope / "main.tex"
            child = scope / "child.tex"
            root.write_text(r"\input{old}")
            child.write_text(r"\input{main}")
            snapshot = static_dependencies(root, scope, {root: r"\input{child}"})
            self.assertIn(child, snapshot.paths)
            self.assertNotIn(scope / "old.tex", snapshot.paths)
            bounded = static_dependencies(root, scope, {root: r"\bibliography{a,b,c,d}"}, max_inputs=3)
            self.assertFalse(bounded.complete)
            self.assertEqual(len(bounded.paths), 3)

    def test_unsafe_static_and_recorder_inputs_do_not_expand_scope(self) -> None:
        with TemporaryDirectory() as directory, TemporaryDirectory() as external:
            scope = Path(directory).resolve()
            outside = Path(external).resolve()
            root = scope / "main.tex"
            (outside / "secret.tex").write_text("secret")
            (scope / "link").symlink_to(outside, target_is_directory=True)
            (scope / "linked.tex").symlink_to(outside / "secret.tex")
            root.write_text(
                "\\input{../outside}\n\\input{link/secret}\n\\input{linked}\n"
                "\\input{.icstex/generated}\n\\input{.latex_build/generated}\n"
                "\\input{\\dynamic}\n",
            )
            snapshot = static_dependencies(root, scope)
            self.assertFalse(any(path.name == "secret.tex" for path in snapshot.paths))
            self.assertNotIn(scope / "linked.tex", snapshot.paths)
            self.assertIsNone(safe_project_input(scope, scope / "link" / ".." / "main.tex"))
            text = (
                "PWD /untrusted\nINPUT ./main.tex\nINPUT data values.csv\n"
                "INPUT generated.pdf\nOUTPUT generated.pdf\nINPUT .latex_build/main.aux\n"
                f"INPUT {outside / 'secret.tex'}\nINPUT link/secret.tex\nINPUT linked.tex\n"
                "INPUT ../escape.tex\nINPUT .icstex/preview/proxy.png\n"
            )
            recorded = recorder_dependencies(text, root=root, scope=scope)
            self.assertEqual(recorded.paths, frozenset({root, scope / "data values.csv"}))

    def test_observations_distinguish_same_bytes_changes_missing_and_symlinks(self) -> None:
        with TemporaryDirectory() as directory:
            scope = Path(directory).resolve()
            path = scope / "child.tex"
            path.write_text("first")
            first = observe_input(path, scope)
            path.write_text("first")
            self.assertEqual(observe_input(path, scope), first)
            path.write_text("other")
            self.assertNotEqual(observe_input(path, scope).digest, first.digest)
            path.unlink()
            self.assertIsNone(observe_input(path, scope).digest)
            target = scope / "target.tex"
            target.write_text("target")
            path.symlink_to(target)
            self.assertFalse(observe_input(path, scope).readable)
