from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from app.core import project_checkpoint as checkpoint


class ProjectCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.project = self.home / "original"
        self.project.mkdir()
        self.original = b"% GBK and CRLF\r\n" + "中文".encode("gbk") + b"\r\n"
        (self.project / "main.tex").write_bytes(self.original)
        (self.project / "refs.bib").write_bytes(b"@book{x, title={X}}\r\n")
        self.path = self.home / "saved.icstex-checkpoint"

    def create(self, **kwargs):
        return checkpoint.create_checkpoint(self.project, ("main.tex", "refs.bib"), self.path, **kwargs)

    def test_bytes_and_drafts_restore_separately_without_changing_original(self):
        draft = checkpoint.DraftInput("source-1", "source-text", "main.tex", "未保存\n".encode())
        info = self.create(drafts=(draft,))
        result = checkpoint.restore_checkpoint(self.path, self.home / "restored")
        self.assertEqual((result.project_dir / "main.tex").read_bytes(), self.original)
        self.assertEqual((result.drafts_dir / "source-1.txt").read_text(), "未保存\n")
        self.assertEqual((self.project / "main.tex").read_bytes(), self.original)
        self.assertEqual(info.files[0].sha256, hashlib.sha256(self.original).hexdigest())
        self.assertEqual(info, checkpoint.inspect_checkpoint(self.path))
        self.assertFalse(any(self.home.glob("*.incomplete-*")))

    def test_changed_file_during_second_pass_never_publishes(self):
        original = checkpoint._read_file
        calls = []
        def read(project, relative, *args, **kwargs):
            calls.append(relative)
            if len(calls) == 3:
                (self.project / "main.tex").write_bytes(b"external change")
            return original(project, relative, *args, **kwargs)
        with patch.object(checkpoint, "_read_file", side_effect=read):
            with self.assertRaises(OSError):
                self.create()
        self.assertFalse(self.path.exists())
        self.assertEqual((self.project / "main.tex").read_bytes(), b"external change")

    def test_existing_checkpoint_and_restore_destinations_are_never_replaced(self):
        self.create()
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.create()
        self.assertEqual(self.path.read_bytes(), before)
        target = self.home / "restored"
        target.mkdir()
        with self.assertRaises(FileExistsError):
            checkpoint.restore_checkpoint(self.path, target)
        self.assertEqual(list(target.iterdir()), [])

    def test_restore_is_bound_to_the_fully_reviewed_manifest(self):
        reviewed = self.create()
        self.path.unlink()
        (self.project / "main.tex").write_bytes(b"new unrelated valid checkpoint")
        self.create()
        target = self.home / "restore-after-review"
        with self.assertRaisesRegex(ValueError, "changed since review"):
            checkpoint.restore_checkpoint(self.path, target, expected_info=reviewed)
        self.assertFalse(target.exists())

    def test_review_verifies_all_bytes_and_bounds_only_the_display_preview(self):
        text = "draft" * 15000
        self.create(drafts=(checkpoint.DraftInput("source", "source-text", "main.tex", text.encode()),))
        info, previews = checkpoint.checkpoint_review(self.path)
        self.assertIn("source", previews)
        self.assertLess(len(previews["source"]), len(text))
        result = checkpoint.restore_checkpoint(self.path, self.home / "full-draft", expected_info=info)
        self.assertEqual((result.drafts_dir / "source.txt").read_text(), text)

    def test_candidate_names_exclude_links_secrets_and_private_history(self):
        (self.project / "private.pem").write_text("synthetic private placeholder")
        (self.project / "linked.tex").symlink_to(self.home / "outside.tex")
        internal = self.project / ".icstex"
        (internal / "history").mkdir(parents=True)
        (internal / "history" / "old.tex").write_text("private history")
        (internal / "blocks.json").write_text("{}")
        paths, warnings = checkpoint.checkpoint_candidates(self.project)
        self.assertEqual(set(paths), {"main.tex", "refs.bib", ".icstex/blocks.json"})
        self.assertTrue(warnings)

    def test_cancel_and_disk_full_leave_no_final_target(self):
        with self.assertRaises(checkpoint.CheckpointCancelled):
            self.create(cancelled=lambda: True)
        self.assertFalse(self.path.exists())
        self.create()
        with patch.object(checkpoint, "_write_restored", side_effect=OSError("No space left")):
            with self.assertRaises(OSError):
                checkpoint.restore_checkpoint(self.path, self.home / "restored")
        self.assertFalse((self.home / "restored").exists())

    def test_links_internal_history_and_portability_collisions_are_refused(self):
        (self.project / "linked.tex").symlink_to(self.home / "outside.tex")
        (self.home / "outside.tex").write_text("outside")
        for paths in (("linked.tex",), ("../outside.tex",), (".git/config",),
                      (".icstex/history/a.tex",), ("main.tex", "MAIN.tex"),
                      ("CON.tex",), ("a/b.tex", "A/c.tex")):
            with self.subTest(paths=paths), self.assertRaises((OSError, ValueError)):
                checkpoint.create_checkpoint(self.project, paths, self.path)
            self.assertFalse(self.path.exists())

    def test_unknown_version_missing_or_corrupt_objects_refuse_restore(self):
        self.create()
        with zipfile.ZipFile(self.path) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        object_name = next(name for name in members if name.startswith("objects/"))
        manifest = json.loads(members["manifest.json"])
        variants = []
        future = dict(members)
        future["manifest.json"] = json.dumps({**manifest, "version": 999}).encode()
        variants.append(future)
        variants.append({key: value for key, value in members.items() if key != object_name})
        variants.append({**members, object_name: b"corrupt"})
        for index, variant in enumerate(variants):
            bad = self.home / f"bad-{index}.icstex-checkpoint"
            with zipfile.ZipFile(bad, "w") as archive:
                for name, data in variant.items():
                    archive.writestr(name, data)
            with self.subTest(index=index), self.assertRaises((OSError, ValueError)):
                checkpoint.restore_checkpoint(bad, self.home / f"bad-restore-{index}")
            self.assertFalse((self.home / f"bad-restore-{index}").exists())

    def test_restore_rechecks_earlier_files_before_final_publication(self):
        self.create()
        original = checkpoint._write_restored
        def write(directory, relative, *args, **kwargs):
            result = original(directory, relative, *args, **kwargs)
            if relative == "README.txt":
                (directory / "project/main.tex").write_bytes(b"changed during restore")
            return result
        with patch.object(checkpoint, "_write_restored", side_effect=write):
            with self.assertRaises(OSError):
                checkpoint.restore_checkpoint(self.path, self.home / "restored")
        self.assertFalse((self.home / "restored").exists())

    def test_replaced_staging_directory_is_not_published_or_deleted(self):
        self.create()
        original = checkpoint._write_restored
        def write(directory, relative, *args, **kwargs):
            result = original(directory, relative, *args, **kwargs)
            if relative == "README.txt":
                directory.rename(directory.parent / "moved-owned-staging")
                directory.mkdir()
                (directory / "other-user-data.txt").write_bytes(b"preserve me")
            return result
        with patch.object(checkpoint, "_write_restored", side_effect=write):
            with self.assertRaises(OSError):
                checkpoint.restore_checkpoint(self.path, self.home / "restored")
        foreign = list(self.home.glob(".icstex-restore.incomplete-*/other-user-data.txt"))
        self.assertEqual(len(foreign), 1)
        self.assertEqual(foreign[0].read_bytes(), b"preserve me")
        self.assertFalse((self.home / "restored").exists())

    def test_replaced_staged_archive_is_not_published_or_deleted(self):
        original = checkpoint.inspect_checkpoint
        def inspect(path, **kwargs):
            result = original(path, **kwargs)
            Path(path).rename(self.home / "owned-archive-moved")
            Path(path).write_bytes(b"foreign data")
            return result
        with patch.object(checkpoint, "inspect_checkpoint", side_effect=inspect):
            with self.assertRaises(OSError):
                self.create()
        self.assertFalse(self.path.exists())
        self.assertEqual(next(self.home.glob(".icstex-checkpoint.incomplete-*")).read_bytes(), b"foreign data")

    def test_unlisted_file_in_restore_staging_is_rejected(self):
        self.create()
        original = checkpoint._write_restored
        def write(directory, relative, *args, **kwargs):
            result = original(directory, relative, *args, **kwargs)
            if relative == "README.txt":
                (directory / "project/unselected.tex").write_bytes(b"unselected")
            return result
        with patch.object(checkpoint, "_write_restored", side_effect=write), self.assertRaises(OSError):
            checkpoint.restore_checkpoint(self.path, self.home / "restored")
        self.assertFalse((self.home / "restored").exists())

    def test_publication_race_does_not_replace_even_an_empty_directory(self):
        self.create()
        target = self.home / "restored"
        original = checkpoint._OutputParent.absent
        calls = []
        def absent(parent):
            original(parent)
            calls.append(True)
            if len(calls) == 2:
                target.mkdir()
        with patch.object(checkpoint._OutputParent, "absent", absent):
            with self.assertRaises(FileExistsError):
                checkpoint.restore_checkpoint(self.path, target)
        self.assertEqual(list(target.iterdir()), [])

    def test_capture_publication_race_preserves_new_existing_file(self):
        original = checkpoint._OutputParent.absent
        calls = []
        def absent(parent):
            original(parent)
            calls.append(True)
            if len(calls) == 2:
                self.path.write_bytes(b"other checkpoint")
        with patch.object(checkpoint._OutputParent, "absent", absent):
            with self.assertRaises(FileExistsError):
                self.create()
        self.assertEqual(self.path.read_bytes(), b"other checkpoint")

    def test_metadata_is_byte_exact_but_personal_history_is_not_captured(self):
        metadata = self.project / ".icstex"
        metadata.mkdir()
        original = b'{"format":"newer-unknown-blocks", "unknown":true}\r\n'
        (metadata / "blocks.json").write_bytes(original)
        info = checkpoint.create_checkpoint(self.project, ("main.tex", ".icstex/blocks.json"), self.path)
        result = checkpoint.restore_checkpoint(self.path, self.home / "restored")
        self.assertEqual((result.project_dir / ".icstex/blocks.json").read_bytes(), original)
        self.assertEqual(len(info.files), 2)
        self.assertFalse((result.project_dir / ".icstex/history").exists())

    def test_limits_and_invalid_drafts_fail_without_publication(self):
        for draft in (checkpoint.DraftInput("../bad", "source-text", None, b"x"),
                      checkpoint.DraftInput("ok", "future-draft", None, b"x"),
                      checkpoint.DraftInput("ok", "source-text", "/outside", b"x"),
                      checkpoint.DraftInput("ok", "source-text", None, b"\xff")):
            with self.subTest(draft=draft), self.assertRaises(ValueError):
                self.create(drafts=(draft,))
        with patch.object(checkpoint, "MAX_FILE_BYTES", 2), self.assertRaises(ValueError):
            self.create()
        with patch.object(checkpoint, "MAX_TOTAL_BYTES", 2), self.assertRaises(ValueError):
            self.create()
        self.assertFalse(self.path.exists())

    def test_mid_capture_and_restore_cancellation_clean_up_owned_staging(self):
        count = 0
        def cancelled():
            nonlocal count
            count += 1
            return count >= 5
        with self.assertRaises(checkpoint.CheckpointCancelled):
            self.create(cancelled=cancelled)
        self.assertFalse(self.path.exists())
        self.create()
        original = checkpoint._write_restored
        cancel = False
        def write(*args, **kwargs):
            nonlocal cancel
            value = original(*args, **kwargs)
            cancel = True
            return value
        with patch.object(checkpoint, "_write_restored", side_effect=write):
            with self.assertRaises(checkpoint.CheckpointCancelled):
                checkpoint.restore_checkpoint(self.path, self.home / "restored", cancelled=lambda: cancel)
        self.assertFalse((self.home / "restored").exists())
        if os.name == "posix" and checkpoint.shutil.rmtree.avoids_symlink_attacks:
            self.assertFalse(list(self.home.glob("*.incomplete-*")))

    @unittest.skipUnless(os.name == "posix", "POSIX hard termination fixture")
    def test_hard_process_interruption_leaves_only_explicitly_incomplete_staging(self):
        self.create()
        script = '''
import os, signal, sys
from app.core import project_checkpoint as cp
original = cp._write_restored
def stop_after_first_file(*args, **kwargs):
    result = original(*args, **kwargs)
    os.kill(os.getpid(), signal.SIGKILL)
    return result
cp._write_restored = stop_after_first_file
cp.restore_checkpoint(sys.argv[1], sys.argv[2])
'''
        target = self.home / "interrupted"
        process = subprocess.run([sys.executable, "-c", script, str(self.path), str(target)],
                                 cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=20)
        self.assertEqual(process.returncode, -signal.SIGKILL, process.stderr)
        self.assertFalse(target.exists())
        staging = list(self.home.glob(".icstex-restore.incomplete-*"))
        self.assertEqual(len(staging), 1)
        self.assertFalse((staging[0] / "manifest.json").exists())
        self.assertEqual((self.project / "main.tex").read_bytes(), self.original)

    def test_archive_changes_during_restore_are_rejected(self):
        self.create()
        original = checkpoint._write_restored
        def write(directory, relative, *args, **kwargs):
            result = original(directory, relative, *args, **kwargs)
            if relative == "README.txt":
                with self.path.open("ab") as stream:
                    stream.write(b"changed")
            return result
        with patch.object(checkpoint, "_write_restored", side_effect=write), self.assertRaises(OSError):
            checkpoint.restore_checkpoint(self.path, self.home / "restored")
        self.assertFalse((self.home / "restored").exists())

    def test_capture_write_failure_preserves_original_and_existing_files(self):
        with patch.object(zipfile.ZipFile, "writestr", side_effect=OSError("No space left")):
            with self.assertRaises(OSError):
                self.create()
        self.assertFalse(self.path.exists())
        self.assertEqual((self.project / "main.tex").read_bytes(), self.original)

    def test_manifest_paths_duplicate_keys_and_zip_members_are_not_trusted(self):
        self.create()
        with zipfile.ZipFile(self.path) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        original = json.loads(members["manifest.json"])
        for index, path in enumerate(("../escape.tex", "/absolute.tex", "C:/escape.tex", ".git/config")):
            manifest = json.loads(json.dumps(original))
            manifest["files"][0]["path"] = path
            bad = self.home / f"unsafe-{index}"
            with zipfile.ZipFile(bad, "w") as archive:
                for name, data in members.items():
                    archive.writestr(name, json.dumps(manifest).encode() if name == "manifest.json" else data)
            with self.subTest(path=path), self.assertRaises(ValueError):
                checkpoint.restore_checkpoint(bad, self.home / f"unsafe-out-{index}")
        payload = members["manifest.json"].replace(b'"version": 1,', b'"version": 1, "version": 1,')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            checkpoint._parse_manifest(payload)

    def test_second_pass_checks_bytes_even_when_observation_signature_is_same(self):
        original = checkpoint._read_file
        calls = []
        def read(project, relative, *args, **kwargs):
            data, observation = original(project, relative, *args, **kwargs)
            calls.append(relative)
            return (b"different bytes", observation) if len(calls) == 3 else (data, observation)
        with patch.object(checkpoint, "_read_file", side_effect=read), self.assertRaises(OSError):
            self.create()
        self.assertFalse(self.path.exists())

    def test_file_links_and_parent_links_are_refused_on_restore(self):
        self.create()
        link = self.home / "linked-checkpoint"
        link.symlink_to(self.path)
        with self.assertRaises(OSError):
            checkpoint.restore_checkpoint(link, self.home / "restored")
        target = self.home / "existing-link"
        target.symlink_to(self.home / "missing-target")
        with self.assertRaises(FileExistsError):
            checkpoint.restore_checkpoint(self.path, target)
        self.assertTrue(target.is_symlink())

    def test_parent_replacement_refuses_output_in_replacement_directory(self):
        folder = self.home / "destination"
        folder.mkdir()
        target = folder / self.path.name
        original = checkpoint._read_file
        calls = []
        def read(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(True)
            if len(calls) == 2:
                folder.rename(self.home / "moved-parent")
                folder.mkdir()
                (folder / "unrelated.txt").write_bytes(b"preserve")
            return result
        with patch.object(checkpoint, "_read_file", side_effect=read), self.assertRaises(OSError):
            checkpoint.create_checkpoint(self.project, ("main.tex", "refs.bib"), target)
        self.assertFalse(target.exists())
        self.assertEqual((folder / "unrelated.txt").read_bytes(), b"preserve")

    def test_shared_objects_unicode_names_and_empty_files_roundtrip(self):
        (self.project / "中文 名称.tex").write_bytes(self.original)
        (self.project / "empty.bib").write_bytes(b"")
        paths = ("main.tex", "中文 名称.tex", "empty.bib")
        info = checkpoint.create_checkpoint(self.project, paths, self.path)
        with zipfile.ZipFile(self.path) as archive:
            self.assertEqual(len(archive.namelist()), 3)  # manifest + two unique objects
        result = checkpoint.restore_checkpoint(self.path, self.home / "restored")
        for entry in info.files:
            self.assertEqual((result.project_dir / entry.path).read_bytes(), (self.project / entry.path).read_bytes())

    @unittest.skipUnless(os.name == "posix", "POSIX exclusive rename availability")
    def test_unsupported_exclusive_directory_publication_never_uses_replace(self):
        self.create()
        with patch.object(checkpoint.ctypes, "CDLL", return_value=object()):
            with self.assertRaises(OSError):
                checkpoint.restore_checkpoint(self.path, self.home / "restored")
        self.assertFalse((self.home / "restored").exists())

    def test_duplicate_and_compressed_archive_members_are_refused(self):
        self.create()
        with zipfile.ZipFile(self.path) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        for variant in ("duplicate", "compressed"):
            bad = self.home / variant
            compression = zipfile.ZIP_DEFLATED if variant == "compressed" else zipfile.ZIP_STORED
            with zipfile.ZipFile(bad, "w", compression=compression) as archive:
                for name, data in members.items():
                    archive.writestr(name, data)
                if variant == "duplicate":
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        archive.writestr("manifest.json", members["manifest.json"])
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                checkpoint.restore_checkpoint(bad, self.home / (variant + "-out"))
            self.assertFalse((self.home / (variant + "-out")).exists())


if __name__ == "__main__":
    unittest.main()
