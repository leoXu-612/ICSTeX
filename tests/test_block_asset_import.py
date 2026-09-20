"""Synthetic Block image import boundaries; never touch student projects."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import shutil
import os
import threading

from app.core.project_lock import project_write_lock

from app.core.blocks.asset_import import import_image


class BlockAssetImportTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-asset-import-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.outside = self.base / "outside"
        self.outside.mkdir()
        self.source = self.base / "source.png"
        self.data = b"\x89PNG\r\n\x1a\nSynthetic image bytes"
        self.source.write_bytes(self.data)

    def test_internal_parent_symlinks_refuse_without_outside_writes(self):
        for relative in ("assets", "assets/images"):
            with self.subTest(relative=relative):
                target = self.project / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(self.outside, target_is_directory=True)
                with self.assertRaises((OSError, ValueError)):
                    import_image(self.project, self.source)
                self.assertEqual(list(self.outside.iterdir()), [])
                self.assertEqual(self.source.read_bytes(), self.data)
                target.unlink()

    def test_dangling_destination_link_is_not_followed_or_overwritten(self):
        folder = self.project / "assets/images"
        folder.mkdir(parents=True)
        target = folder / self.source.name
        outside = self.outside / "must-not-exist.png"
        target.symlink_to(outside)
        relative = import_image(self.project, self.source)
        self.assertEqual(relative, "assets/images/source (1).png")
        self.assertTrue(target.is_symlink())
        self.assertFalse(outside.exists())
        self.assertEqual((self.project / relative).read_bytes(), self.data)

    def test_copy_failure_does_not_publish_partial_image_or_change_existing_file(self):
        folder = self.project / "assets/images"
        folder.mkdir(parents=True)
        existing = folder / "original.png"
        existing.write_bytes(b"original")
        def fail_path(_source, target, **_kwargs):
            Path(target).write_bytes(b"partial")
            raise OSError("Synthetic interrupted copy")
        def fail_stream(_source, target, *_args):
            target.write(b"partial")
            raise OSError("Synthetic interrupted copy")
        with patch("shutil.copy2", side_effect=fail_path), patch("shutil.copyfileobj", side_effect=fail_stream):
            with self.assertRaises(OSError):
                import_image(self.project, self.source)
        self.assertEqual(list(folder.iterdir()), [existing])
        self.assertEqual(existing.read_bytes(), b"original")
        self.assertEqual(self.source.read_bytes(), self.data)

    def test_destination_created_during_copy_is_preserved_and_new_name_is_used(self):
        folder = self.project / "assets/images"
        winner = folder / self.source.name
        copy_path, copy_stream = shutil.copy2, shutil.copyfileobj
        def race_path(source, target, **kwargs):
            winner.write_bytes(b"external winner")
            return copy_path(source, target, **kwargs)
        def race_stream(source, target, *args):
            winner.write_bytes(b"external winner")
            return copy_stream(source, target, *args)
        with patch("shutil.copy2", side_effect=race_path), patch("shutil.copyfileobj", side_effect=race_stream):
            relative = import_image(self.project, self.source)
        self.assertEqual(winner.read_bytes(), b"external winner")
        self.assertEqual(relative, "assets/images/source (1).png")
        self.assertEqual((self.project / relative).read_bytes(), self.data)

    def test_source_changed_during_copy_is_not_published_as_success(self):
        copy_path, copy_stream = shutil.copy2, shutil.copyfileobj
        def changed_path(source, target, **kwargs):
            result = copy_path(source, target, **kwargs)
            self.source.write_bytes(b"changed source version")
            return result
        def changed_stream(source, target, *args):
            result = copy_stream(source, target, *args)
            self.source.write_bytes(b"changed source version")
            return result
        with patch("shutil.copy2", side_effect=changed_path), patch("shutil.copyfileobj", side_effect=changed_stream):
            with self.assertRaises(OSError):
                import_image(self.project, self.source)
        self.assertEqual(self.source.read_bytes(), b"changed source version")
        self.assertEqual(list((self.project / "assets/images").iterdir()), [])

    def test_invalid_source_does_not_create_asset_directories(self):
        missing = self.base / "missing.png"
        text = self.base / "not-an-image.txt"
        text.write_text("synthetic")
        for source in (missing, text, self.outside):
            with self.subTest(source=source):
                with self.assertRaises((OSError, ValueError)):
                    import_image(self.project, source)
                self.assertFalse((self.project / "assets").exists())

    def test_directory_swapped_for_link_during_copy_refuses_and_cleans_owned_stage(self):
        if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
            self.skipTest("Anchored directory-race case requires POSIX openat")
        folder = self.project / "assets/images"
        retained = self.project / "assets/retained-images"
        copy_stream = shutil.copyfileobj
        def swapped(source, target, *args):
            folder.rename(retained)
            folder.symlink_to(self.outside, target_is_directory=True)
            return copy_stream(source, target, *args)
        with patch("shutil.copyfileobj", side_effect=swapped):
            with self.assertRaises(OSError):
                import_image(self.project, self.source)
        self.assertEqual(list(self.outside.iterdir()), [])
        self.assertEqual(list(retained.iterdir()), [])
        self.assertTrue(folder.is_symlink())
        self.assertEqual(self.source.read_bytes(), self.data)

    def test_publication_failure_keeps_originals_and_removes_only_owned_stage(self):
        with patch("app.core.blocks.asset_import.os.link", side_effect=OSError("Synthetic publication failure")), \
             patch("app.core.blocks.asset_import.os.rename", side_effect=OSError("Synthetic publication failure")):
            with self.assertRaises(OSError):
                import_image(self.project, self.source)
        self.assertEqual(list((self.project / "assets/images").iterdir()), [])
        self.assertEqual(self.source.read_bytes(), self.data)

    def test_busy_project_refuses_without_creating_assets(self):
        entered, release = threading.Event(), threading.Event()
        def owner():
            with project_write_lock(self.project):
                entered.set()
                release.wait(5)
        thread = threading.Thread(target=owner)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaises(BlockingIOError):
                import_image(self.project, self.source)
            self.assertFalse((self.project / "assets").exists())
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
