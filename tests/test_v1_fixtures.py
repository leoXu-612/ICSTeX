from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.blocks.project_repository import load_project
from app.core.project_dependencies import static_dependencies
from tests.v1_fixtures import create_project


class V1FixtureTests(TestCase):
    def test_three_workflows_are_real_local_files_and_drafts_stay_separate(self):
        with TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            for kind in ("single", "multi", "block"):
                sample = create_project(base, kind)
                self.assertTrue(sample.root.is_file())
                self.assertNotEqual(sample.draft_path.read_text(), sample.draft_text)
                self.assertNotEqual(sample.draft_text, sample.conflict_text)
                self.assertFalse((sample.root.parent / ".latex_build").exists())
                if kind == "block":
                    self.assertEqual(len(load_project(sample.root.parent)["registry"].blocks()), 1)
                with self.assertRaises(FileExistsError):
                    create_project(base, kind)

    def test_missing_resource_is_not_a_placeholder_file(self):
        with TemporaryDirectory() as directory:
            sample = create_project(Path(directory).resolve(), missing=True)
            missing = sample.root.parent / "figures" / "plot.png"
            self.assertFalse(missing.exists())
            self.assertIn(missing, static_dependencies(sample.root, sample.root.parent).paths)
