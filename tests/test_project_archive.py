import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import zipfile

from app.core.project_archive import (
    archive_selection_warnings, export_project_archive, review_project_archive,
)
from app.core.project_checkpoint import CheckpointCancelled
from app.core.submission_delivery import source_path_allowed


class ProjectArchiveTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.project = self.home / "原工程"
        self.project.mkdir()
        self.root = self.project / "论文.tex"
        self.originals = {
            "论文.tex": b"\\documentclass{article}\r\n\\usepackage{graphicx}\r\n"
                b"\\input{chapters/body}\r\n\\bibliography{refs}\r\n",
            "chapters/body.tex": b"\\includegraphics{images/plot.png}\n",
            "images/plot.png": b"PNG placeholder for archive byte verification",
            "refs.bib": b"@book{sample,title={Sample}}\r\n",
            "data/table.csv": b"x,y\r\n1,2\r\n",
            "data/table.dat": b"1 2\n3 4\n",
            "data/source.xlsx": b"Spreadsheet bytes are copied, not parsed",
            "local.sty": b"% Local package\n",
            ".icstex/project-profile.json": b"{}",
        }
        for path, payload in self.originals.items():
            self.write(path, payload)

    def write(self, name, payload):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def test_zip_restores_paths_bytes_tables_and_entry_without_compilation(self):
        for name in (".env", "secret.json", ".git/config", ".latex_build/main.pdf", "run.py", "old.zip"):
            self.write(name, b"must not travel")
        review = review_project_archive(self.project, self.root)
        self.assertEqual(set(review.paths), set(self.originals))
        self.assertEqual(review.warnings, ())
        target = export_project_archive(review, review.paths, self.home / "工程.zip")
        moved = self.home / "另一台电脑"
        with zipfile.ZipFile(target) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(json.loads(archive.read("files.json"))["entry"], "project/论文.tex")
            archive.extractall(moved)
        for path, payload in self.originals.items():
            self.assertEqual((moved / "project" / path).read_bytes(), payload)
            self.assertEqual((self.project / path).read_bytes(), payload)
        self.assertTrue((moved / "README.txt").is_file())
        # Extending engineering-table support did not relax submission defaults.
        self.assertFalse(source_path_allowed("data/table.dat"))

    def test_missing_dynamic_absolute_and_external_references_need_confirmation(self):
        outside = self.home / "outside.tex"
        outside.write_text("private outside bytes")
        self.root.write_text("\\input{../outside}\n\\includegraphics{gone}\n"
                             "\\input{\\chosen}\n\\input{" + str(outside) + "}\n")
        review = review_project_archive(self.project, self.root)
        self.assertGreaterEqual(len(review.warnings), 4)
        self.assertFalse(any("outside.tex" == p for p in review.paths))
        target = self.home / "partial.zip"
        with self.assertRaises(ValueError):
            export_project_archive(review, review.paths, target)
        self.assertFalse(target.exists())
        export_project_archive(review, review.paths, target, accept_warnings=True)
        with zipfile.ZipFile(target) as archive:
            self.assertIn("绝对路径", archive.read("README.txt").decode())
            self.assertFalse(any(archive.read(p) == b"private outside bytes" for p in archive.namelist()))

    def test_unchecking_dependency_warns_and_main_is_required(self):
        review = review_project_archive(self.project, self.root)
        chosen = tuple(p for p in review.paths if p != "images/plot.png")
        self.assertTrue(any("images/plot.png" in warning for warning in archive_selection_warnings(review, chosen)))
        with self.assertRaises(ValueError):
            export_project_archive(review, chosen, self.home / "x.zip")
        with self.assertRaises(ValueError):
            export_project_archive(review, ("refs.bib",), self.home / "x.zip", accept_warnings=True)
        without_profile = tuple(p for p in review.paths if p != ".icstex/project-profile.json")
        self.assertTrue(any("project-profile.json" in warning for warning in archive_selection_warnings(review, without_profile)))

    def test_changed_inputs_and_existing_targets_never_publish_or_overwrite(self):
        review = review_project_archive(self.project, self.root)
        target = self.home / "new.zip"
        self.write("data/table.csv", b"new")
        with self.assertRaises(OSError):
            export_project_archive(review, review.paths, target)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.home.glob(".icstex-archive.incomplete-*")))
        target.write_bytes(b"keep existing")
        with self.assertRaises(FileExistsError):
            export_project_archive(review, review.paths, target)
        self.assertEqual(target.read_bytes(), b"keep existing")

    def test_links_cancel_collisions_and_private_keys_are_refused(self):
        linked = self.project / "linked.tex"
        linked.symlink_to(self.root)
        review = review_project_archive(self.project, self.root)
        self.assertNotIn("linked.tex", review.paths)
        self.assertTrue(review.warnings)
        with self.assertRaises(CheckpointCancelled):
            export_project_archive(review, review.paths, self.home / "x.zip", cancelled=lambda: True)
        linked.unlink()
        self.write("secret-copy.txt", b"-----BEGIN PRIVATE KEY-----\nnot a real key")
        review = review_project_archive(self.project, self.root)
        with self.assertRaises(ValueError):
            export_project_archive(review, review.paths, self.home / "x.zip")
        # Simulate a case-sensitive source on a case-insensitive Mac volume.
        with patch("app.core.project_archive.checkpoint_candidates", return_value=(("local.sty", "LOCAL.sty"), ())):
            with self.assertRaises(ValueError):
                review_project_archive(self.project, self.root)

    def test_cancellation_during_zip_cleans_stage_and_late_target_wins(self):
        review = review_project_archive(self.project, self.root)
        target = self.home / "x.zip"
        with patch("app.core.project_archive.recheck_export_inputs", side_effect=CheckpointCancelled()):
            with self.assertRaises(CheckpointCancelled):
                export_project_archive(review, review.paths, target)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.home.glob(".icstex-archive.incomplete-*")))
        with patch("app.core.project_archive.recheck_export_inputs", side_effect=lambda *_a, **_kw: target.write_bytes(b"late owner")):
            with self.assertRaises(FileExistsError):
                export_project_archive(review, review.paths, target)
        self.assertEqual(target.read_bytes(), b"late owner")
        self.assertFalse(list(self.home.glob(".icstex-archive.incomplete-*")))
