from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.blocks.export_package import export_package, safe_relative_path


class SafeRelativePathTests(TestCase):
    def test_rejects_unsafe_paths(self) -> None:
        for unsafe in ("../x", "/abs/x", "a/../b", "C:/x", "a\\b", "", "x\x00y", "./x"):
            self.assertIsNone(safe_relative_path(unsafe), unsafe)

    def test_accepts_normal_paths(self) -> None:
        self.assertEqual(safe_relative_path("blocks/blk_a.tex"), "blocks/blk_a.tex")
        self.assertEqual(safe_relative_path("assets/images/a.png"), "assets/images/a.png")


class ExportPackageTests(TestCase):
    def test_export_excludes_caches_and_secrets(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            (project / "blocks").mkdir(parents=True)
            (project / ".icstex" / "cache").mkdir(parents=True)
            (project / "main.tex").write_text("\\documentclass{article}\n", encoding="utf-8")
            (project / "blocks" / "blk_a.tex").write_text("text", encoding="utf-8")
            (project / ".env").write_text("API_KEY=secret", encoding="utf-8")
            (project / ".icstex" / "cache" / "tmp.pdf").write_bytes(b"x")
            (project / "notes.log").write_text("log", encoding="utf-8")
            target = Path(directory) / "export"

            result = export_package(project, target)

            self.assertIn("main.tex", result.files)
            self.assertIn("blocks/blk_a.tex", result.files)
            self.assertNotIn(".env", result.files)
            self.assertNotIn(".icstex/cache/tmp.pdf", result.files)
            self.assertNotIn("notes.log", result.files)
            self.assertFalse((target / ".env").exists())
            self.assertFalse((target / ".icstex").exists())
            manifest = result.manifest
            self.assertEqual(manifest["format"], "icstex-portable-package")
            self.assertTrue(all(file["sha256"] for file in manifest["files"]))
            self.assertEqual(len(manifest["files"]), len(result.files))

    def test_export_rejects_symlink_without_partial_output(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            (project / "main.tex").write_text("safe", encoding="utf-8")
            secret = root / "secret.txt"
            secret.write_text("secret", encoding="utf-8")
            (project / "notes.txt").symlink_to(secret)
            target = root / "export"

            with self.assertRaisesRegex(ValueError, "符号链接"):
                export_package(project, target)

            self.assertFalse(target.exists())
