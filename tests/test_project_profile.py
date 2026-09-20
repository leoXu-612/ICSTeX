from dataclasses import replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
from unittest import TestCase
from unittest.mock import patch

from app.core.project_profile import (PROFILE_PATH, ProfileConflict, ProjectProfile,
                                     load_profile, parse_profile, profile_bytes, save_profile)


class ProjectProfileTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "\u4e2d\u6587\u9879\u76ee"
        self.root.mkdir()
        self.source = self.root / "main.tex"
        self.source.write_bytes(b"student source\r\n")

    def test_absent_load_is_read_only_and_defaults_have_no_course_limits(self):
        before = set(self.root.rglob("*"))
        snapshot = load_profile(self.root)
        self.assertEqual(snapshot.digest, "missing")
        self.assertTrue(snapshot.stable)
        self.assertIsNone(snapshot.profile)
        self.assertIsNone(ProjectProfile().word_target)
        self.assertEqual(set(self.root.rglob("*")), before)

    def test_roundtrip_edit_disable_preserves_source_and_does_not_create_suggestions(self):
        profile = ProjectProfile(engine="xelatex", word_max=300, directories=("\u56fe\u7247", "data/tables"))
        first = save_profile(self.root, profile, expected=load_profile(self.root))
        self.assertEqual(first.profile, profile)
        self.assertEqual(first.profile.word_target, (None, 300))
        disabled = save_profile(self.root, replace(profile, enabled=False), expected=first)
        self.assertIsNone(disabled.profile.word_target)
        self.assertEqual(disabled.profile.word_max, 300)
        self.assertFalse((self.root / "data").exists())
        self.assertEqual(self.source.read_bytes(), b"student source\r\n")

    def test_unknown_fields_versions_types_paths_and_executable_hooks_are_rejected(self):
        base = json.loads(profile_bytes(ProjectProfile()))
        bad = [{**base, "version": 2}, {**base, "version": True}, {**base, "hook": "rm -rf x"},
               {**base, "enabled": 1}, {**base, "word_min": -1}, {**base, "word_max": False},
               {**base, "word_min": 20, "word_max": 10}, {**base, "engine": "shell"}]
        bad += [{**base, "directories": [entry]} for entry in (".", "../secret", "/tmp", "a/../b", ".git", "a\\b", "a//b", "a/./b")]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_profile(json.dumps(value).encode())
        with self.assertRaises(ValueError):
            parse_profile(b'{"version":1,"version":2}')

    def test_invalid_existing_profile_cannot_be_overwritten(self):
        path = self.root / PROFILE_PATH
        path.parent.mkdir()
        path.write_bytes(b'{"format":"future"}')
        snapshot = load_profile(self.root)
        self.assertTrue(snapshot.error)
        with self.assertRaises(ProfileConflict):
            save_profile(self.root, ProjectProfile(), expected=snapshot)
        self.assertEqual(path.read_bytes(), b'{"format":"future"}')

    def test_oversize_profile_is_bounded_and_not_editable(self):
        path = self.root / PROFILE_PATH
        path.parent.mkdir()
        path.write_bytes(b" " * (64 * 1024 + 1))
        snapshot = load_profile(self.root)
        self.assertTrue(snapshot.error)
        self.assertIsNone(snapshot.profile)
        with self.assertRaises(ProfileConflict):
            save_profile(self.root, ProjectProfile(), expected=snapshot)

    def test_external_change_and_two_window_cas_preserve_winner(self):
        first = save_profile(self.root, ProjectProfile(), expected=load_profile(self.root))
        winner = save_profile(self.root, ProjectProfile(word_max=42), expected=first)
        with self.assertRaises(ProfileConflict):
            save_profile(self.root, ProjectProfile(word_max=99), expected=first)
        self.assertEqual(load_profile(self.root), winner)

    def test_concurrent_creation_only_one_writer_wins(self):
        before = load_profile(self.root)
        barrier = threading.Barrier(2)
        results = []
        def save(n):
            barrier.wait()
            try:
                save_profile(self.root, ProjectProfile(word_max=n), expected=before)
                results.append("saved")
            except (ProfileConflict, BlockingIOError):
                results.append("conflict")
        threads = [threading.Thread(target=save, args=(n,)) for n in (10, 20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertCountEqual(results, ["saved", "conflict"])

    def test_symlink_metadata_or_leaf_never_writes_outside(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        metadata = self.root / ".icstex"
        metadata.symlink_to(outside, target_is_directory=True)
        self.assertTrue(load_profile(self.root).error)
        with self.assertRaises(ProfileConflict):
            save_profile(self.root, ProjectProfile(), expected=load_profile(self.root))
        self.assertEqual(list(outside.iterdir()), [])
        metadata.unlink()
        metadata.mkdir()
        target = outside / "profile.json"
        target.write_bytes(b"keep")
        (self.root / PROFILE_PATH).symlink_to(target)
        self.assertTrue(load_profile(self.root).error)
        self.assertEqual(target.read_bytes(), b"keep")

    def test_replace_failure_preserves_original_and_cleans_temporary(self):
        before = save_profile(self.root, ProjectProfile(), expected=load_profile(self.root))
        original = before.path.read_bytes()
        with patch("app.core.project_profile.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                save_profile(self.root, ProjectProfile(word_max=3), expected=before)
        self.assertEqual(before.path.read_bytes(), original)
        self.assertEqual(list(before.path.parent.iterdir()), [before.path])

    def test_external_change_during_temp_write_is_not_overwritten(self):
        before = save_profile(self.root, ProjectProfile(), expected=load_profile(self.root))
        changed = profile_bytes(ProjectProfile(word_max=17))
        real_fsync = os.fsync
        def mutate(fd):
            before.path.write_bytes(changed)
            real_fsync(fd)
        with patch("app.core.project_profile.os.fsync", side_effect=mutate):
            with self.assertRaises(ProfileConflict):
                save_profile(self.root, ProjectProfile(word_max=3), expected=before)
        self.assertEqual(before.path.read_bytes(), changed)

    def test_busy_project_does_not_block_gui_writer(self):
        from app.core.project_lock import project_write_lock
        entered, release = threading.Event(), threading.Event()
        def hold():
            with project_write_lock(self.root):
                entered.set()
                release.wait(3)
        worker = threading.Thread(target=hold)
        worker.start()
        self.assertTrue(entered.wait(2))
        try:
            with self.assertRaises(BlockingIOError):
                save_profile(self.root, ProjectProfile(), expected=load_profile(self.root))
        finally:
            release.set()
            worker.join(3)
