from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.project_search import search_project


class ProjectSearchTests(TestCase):
    def test_search_project_finds_tex_and_bib_but_ignores_build_dir(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.tex").write_text("Alpha beta\nNeedle here\n", encoding="utf-8")
            (root / "refs.bib").write_text("@article{Needle2024, title={A}}\n", encoding="utf-8")
            (root / ".latex_build").mkdir()
            (root / ".latex_build" / "main.tex").write_text("Needle hidden\n", encoding="utf-8")

            results = search_project(root, "Needle")

            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].line, 2)
            self.assertTrue(all(".latex_build" not in str(result.file) for result in results))
