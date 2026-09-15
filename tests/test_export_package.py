from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import hashlib
import json

from app.core import project_checkpoint
from app.core import artifact_export
import importlib

package_module = importlib.import_module("app.core.blocks.export_package")

from app.core.blocks.export_package import export_package, safe_relative_path


class SafeRelativePathTests(TestCase):
    def test_rejects_unsafe_paths(self) -> None:
        for unsafe in ("../x", "/abs/x", "a/../b", "C:/x", "a\\b", "", "x\x00y", "./x"):
            self.assertIsNone(safe_relative_path(unsafe), unsafe)

    def test_accepts_normal_paths(self) -> None:
        self.assertEqual(safe_relative_path("blocks/blk_a.tex"), "blocks/blk_a.tex")
        self.assertEqual(safe_relative_path("assets/images/a.png"), "assets/images/a.png")


class ExportPackageTests(TestCase):
    def test_original_readme_manifest_and_non_utf8_bytes_are_preserved(self):
        with TemporaryDirectory() as directory:
            project, target = Path(directory) / "project", Path(directory) / "export"
            project.mkdir()
            originals = {"main.tex": b"source", "README.md": b"original readme\r\n",
                         "manifest.json": b'{"original":true}\r\n', "legacy.tex": b"% \x81\xff\r\n"}
            for name, payload in originals.items():
                (project / name).write_bytes(payload)
            result = export_package(project, target)
            for name, payload in originals.items():
                self.assertEqual((target / name).read_bytes(), payload)
            for entry in result.manifest["files"]:
                self.assertEqual(hashlib.sha256((target / entry["path"]).read_bytes()).hexdigest(), entry["sha256"])
            self.assertEqual(json.loads((target / ".icstex-package/manifest.json").read_bytes()), result.manifest)

    def test_private_names_and_virtual_environments_are_not_read_or_copied(self):
        with TemporaryDirectory() as directory:
            project, target = Path(directory) / "project", Path(directory) / "export"
            project.mkdir()
            (project / "main.tex").write_bytes(b"source")
            names = ("signing.pem", "id_ed25519", "tokens.json", ".venv/cache.txt", "venv/cache.txt")
            for name in names:
                path = project / name
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(b"SYNTHETIC NOT A REAL CREDENTIAL")
            observed = []
            original = artifact_export._read_file
            def read(scope, relative, *args, **kwargs):
                observed.append(relative)
                return original(scope, relative, *args, **kwargs)
            with patch.object(artifact_export, "_read_file", read):
                result = export_package(project, target)
            self.assertFalse(set(names) & set(result.files))
            self.assertFalse(set(names) & set(observed))
            for name in names:
                self.assertFalse((target / name).exists())

    def test_nonempty_target_never_changes(self):
        with TemporaryDirectory() as directory:
            project, target = Path(directory) / "project", Path(directory) / "export"
            project.mkdir()
            target.mkdir()
            (project / "main.tex").write_bytes(b"new source")
            (target / "main.tex").write_bytes(b"previous successful source")
            with self.assertRaises((OSError, ValueError)):
                export_package(project, target)
            self.assertEqual((target / "main.tex").read_bytes(), b"previous successful source")
            self.assertEqual(list(target.iterdir()), [target / "main.tex"])

    def test_existing_empty_stage_remains_supported(self):
        with TemporaryDirectory() as directory:
            project, stage = Path(directory) / "project", Path(directory) / "stage"
            project.mkdir()
            stage.mkdir()
            (project / "main.tex").write_bytes(b"source")
            result = export_package(project, stage)
            self.assertEqual(result.target_dir, stage.resolve())
            self.assertEqual((stage / "main.tex").read_bytes(), b"source")

    def test_changes_during_capture_or_staging_never_publish_mixed_source(self):
        for phase in ("capture", "staging"):
            for existing_empty in (False, True):
                with self.subTest(phase=phase, existing_empty=existing_empty), TemporaryDirectory() as directory:
                    base = Path(directory).resolve()
                    project, target = base / "project", base / "target"
                    project.mkdir()
                    if existing_empty:
                        target.mkdir()
                    for name in ("a.tex", "b.tex"):
                        (project / name).write_bytes(("old " + name).encode())
                    applied = False
                    def change():
                        nonlocal applied
                        if not applied:
                            applied = True
                            for name in ("a.tex", "b.tex"):
                                (project / name).write_bytes(("new " + name).encode())
                    original_read = artifact_export._read_file
                    def read(scope, relative, *args, **kwargs):
                        value = original_read(scope, relative, *args, **kwargs)
                        if scope == project and relative == "a.tex":
                            change()
                        return value
                    original_write = project_checkpoint._write_restored
                    def write(scope, relative, *args, **kwargs):
                        value = original_write(scope, relative, *args, **kwargs)
                        if relative == "a.tex":
                            change()
                        return value
                    seam = patch.object(artifact_export, "_read_file", read) if phase == "capture" else patch.object(
                        project_checkpoint, "_write_restored", write)
                    with seam, self.assertRaises((OSError, ValueError)):
                        export_package(project, target)
                    self.assertTrue(applied)
                    self.assertEqual((project / "a.tex").read_bytes(), b"new a.tex")
                    self.assertEqual(target.exists(), existing_empty)
                    if existing_empty:
                        self.assertEqual(list(target.iterdir()), [])
                    self.assertFalse(list(base.glob(".icstex-delivery.incomplete-*")))

    def test_new_input_or_journal_during_staging_refuses(self):
        for added in ("later.tex", ".icstex/block-write.pending"):
            with self.subTest(added=added), TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                project, target = base / "project", base / "target"
                project.mkdir()
                (project / "main.tex").write_bytes(b"source")
                original = project_checkpoint._write_restored
                def write(scope, relative, *args, **kwargs):
                    value = original(scope, relative, *args, **kwargs)
                    if relative == "main.tex":
                        path = project / added
                        path.parent.mkdir(exist_ok=True)
                        path.write_bytes(b"external new input or unresolved evidence")
                    return value
                with patch.object(project_checkpoint, "_write_restored", write), self.assertRaises((OSError, ValueError)):
                    export_package(project, target)
                self.assertFalse(target.exists())
                self.assertTrue((project / added).is_file())

    def test_late_empty_target_is_not_treated_as_a_supplied_stage(self):
        with TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, target = base / "project", base / "target"
            project.mkdir()
            (project / "main.tex").write_bytes(b"source")
            original = package_module._publish_payloads
            identity = []
            def publish(path, *args, **kwargs):
                target.mkdir()
                identity.append(target.stat().st_ino)
                return original(path, *args, **kwargs)
            with patch.object(package_module, "_publish_payloads", publish), self.assertRaises(FileExistsError):
                export_package(project, target)
            self.assertEqual(target.stat().st_ino, identity[0])
            self.assertEqual(list(target.iterdir()), [])

    def test_failed_empty_stage_replacement_restores_empty_directory(self):
        with TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, target = base / "project", base / "target"
            project.mkdir()
            target.mkdir()
            (project / "main.tex").write_bytes(b"source")
            with patch.object(project_checkpoint, "_write_restored", side_effect=OSError("synthetic disk full")), self.assertRaises(OSError):
                export_package(project, target)
            self.assertEqual(list(target.iterdir()), [])
            self.assertEqual(sorted(path.name for path in base.iterdir()), ["project", "target"])

    def test_incomplete_inventory_or_private_key_marker_refuses(self):
        with TemporaryDirectory() as directory:
            project, target = Path(directory) / "project", Path(directory) / "target"
            project.mkdir()
            (project / "main.tex").write_bytes(b"source")
            with patch.object(package_module, "checkpoint_candidates", return_value=(("main.tex",), ("bounded scan incomplete",))), self.assertRaises(ValueError):
                export_package(project, target)
            (project / "notes.txt").write_bytes(b"-----BEGIN PRIVATE KEY-----\nSYNTHETIC NOT A REAL KEY\n")
            with self.assertRaises(ValueError):
                export_package(project, target)
            self.assertFalse(target.exists())

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
