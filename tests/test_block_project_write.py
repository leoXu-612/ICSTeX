from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
from unittest import TestCase
from unittest.mock import patch

from app.core.blocks.assembly import build_latex_files
from app.core.blocks.project_repository import load_project, project_payloads
from app.core.blocks.project_write import BlockWriteGuard, BlockWriteConflict, PENDING_PATH
from tests.v1_fixtures import create_project


class BlockProjectWriteTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = create_project(Path(self.temp.name).resolve(), "block")
        self.root = self.fixture.root.parent
        self.loaded = load_project(self.root)
        self.metadata = project_payloads(self.root, **{key: self.loaded[key] for key in
            ("registry", "layout", "sources", "document_theme")})
        self.generated = {p: t.encode() for p, t in build_latex_files(self.root,
            **{key: self.loaded[key] for key in ("registry", "layout", "document_theme")}).items()}
        self.original = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def guard(self):
        return BlockWriteGuard(self.root, self.metadata, self.generated)

    def changed(self):
        path = self.root / ".icstex/sources.json"
        return {**self.metadata, path: b'{"sources": [], "test": true}'}

    def test_no_change_is_zero_write_and_changed_batch_verifies(self):
        guard = self.guard()
        self.assertEqual(guard.write(self.metadata), [])
        changed = self.changed()
        self.assertEqual(guard.write(changed), [self.root / ".icstex/sources.json"])
        self.assertEqual({p: p.read_bytes() for p in changed}, changed)
        self.assertFalse((self.root / PENDING_PATH).exists())
        self.assertEqual(guard.write(changed), [])

    def test_external_metadata_winner_is_not_overwritten(self):
        guard = self.guard()
        path = self.root / ".icstex/blocks.json"
        winner = self.original[path] + b" \n"
        path.write_bytes(winner)
        with self.assertRaises(BlockWriteConflict):
            guard.write(self.changed())
        self.assertEqual(path.read_bytes(), winner)
        self.assertEqual((self.root / ".icstex/sources.json").read_bytes(), self.original[self.root / ".icstex/sources.json"])
        self.assertFalse((self.root / PENDING_PATH).exists())

    def test_generated_edits_are_not_silently_reassembled(self):
        guard = self.guard()
        self.fixture.draft_path.write_bytes(b"Hand edited source")
        with self.assertRaises(BlockWriteConflict):
            guard.write({**self.metadata, **self.generated})
        self.assertEqual(self.fixture.draft_path.read_bytes(), b"Hand edited source")

    def test_unowned_generated_file_and_unknown_metadata_reject_writes(self):
        self.fixture.root.write_bytes(b"Hand written root")
        with self.assertRaises(BlockWriteConflict):
            self.guard()
        self.fixture.root.write_bytes(self.original[self.fixture.root])
        path = self.root / ".icstex/layouts.json"
        payload = json.loads(path.read_bytes())
        payload["schemaVersion"] = "999.0.0"
        path.write_text(json.dumps(payload))
        with self.assertRaises(BlockWriteConflict):
            self.guard()

    def test_new_generated_destination_must_be_absent(self):
        guard = self.guard()
        path = self.root / "blocks/new.tex"
        path.write_bytes(b"Someone else's file")
        with self.assertRaises(BlockWriteConflict):
            guard.write({path: b"New generated file"})
        self.assertEqual(path.read_bytes(), b"Someone else's file")

    def test_partial_write_failure_rolls_back_original_bytes(self):
        guard = self.guard()
        changed = {p: data + b" " for p, data in self.metadata.items()}
        real = guard._replace
        calls = []
        def fail_second(path, data, expected):
            if path in self.metadata:
                calls.append(path)
                if len(calls) == 2:
                    raise OSError("synthetic disk failure")
            return real(path, data, expected)
        with patch.object(guard, "_replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                guard.write(changed)
        self.assertEqual({p: p.read_bytes() for p in self.original}, self.original)
        self.assertFalse((self.root / PENDING_PATH).exists())

    def test_rollback_does_not_replace_external_winner_and_keeps_recovery_bytes(self):
        guard = self.guard()
        changed = {p: data + b" " for p, data in self.metadata.items()}
        real = guard._replace
        paths = list(changed)
        calls = []
        def race(path, data, expected):
            if path in self.metadata:
                calls.append(path)
                if len(calls) == 2:
                    paths[0].write_bytes(b"external winner during write")
                    raise OSError("synthetic disk failure")
            return real(path, data, expected)
        with patch.object(guard, "_replace", side_effect=race):
            with self.assertRaises(BlockWriteConflict):
                guard.write(changed)
        self.assertEqual(paths[0].read_bytes(), b"external winner during write")
        journal = self.root / PENDING_PATH
        self.assertTrue(journal.is_dir())
        self.assertEqual((journal / "before-0.bin").read_bytes(), self.original[paths[0]])
        self.assertEqual((journal / "after-0.bin").read_bytes(), changed[paths[0]])
        with self.assertRaises(BlockWriteConflict):
            self.guard()

    def test_symlink_substitution_and_pending_transaction_are_refused(self):
        guard = self.guard()
        target = self.root / ".icstex/sources.json"
        outside = Path(self.temp.name) / "outside.json"
        outside.write_bytes(b"original outside")
        target.unlink()
        target.symlink_to(outside)
        with self.assertRaises((BlockWriteConflict, OSError, ValueError)):
            guard.write(self.changed())
        self.assertEqual(outside.read_bytes(), b"original outside")

    def test_limits_fail_before_changing_project_files(self):
        guard = self.guard()
        with patch("app.core.blocks.project_write.MAX_BATCH_BYTES", 2):
            with self.assertRaises(ValueError):
                guard.write(self.changed())
        self.assertEqual({p: p.read_bytes() for p in self.original}, self.original)
        self.assertFalse((self.root / PENDING_PATH).exists())

    def test_failure_after_replacement_still_restores_the_original(self):
        guard = self.guard()
        changed = self.changed()
        path = self.root / ".icstex/sources.json"
        real = os.fsync
        failed = []
        def fail_after_replace(fd):
            if not failed and path.read_bytes() == changed[path]:
                failed.append(True)
                raise OSError("directory fsync failed after replace")
            return real(fd)
        with patch("app.core.blocks.project_write.os.fsync", side_effect=fail_after_replace):
            with self.assertRaises(OSError):
                guard.write(changed)
        self.assertTrue(failed)
        self.assertEqual({p: p.read_bytes() for p in self.original}, self.original)
        self.assertFalse((self.root / PENDING_PATH).exists())

    def test_change_while_staging_refuses_all_project_replacements(self):
        guard = self.guard()
        real = guard._journal
        path = self.root / ".icstex/blocks.json"
        def stage_then_change(*args):
            files = real(*args)
            path.write_bytes(b"external winner while staging")
            return files
        with patch.object(guard, "_journal", side_effect=stage_then_change):
            with self.assertRaises(BlockWriteConflict):
                guard.write(self.changed())
        self.assertEqual(path.read_bytes(), b"external winner while staging")
        self.assertEqual((self.root / ".icstex/sources.json").read_bytes(), self.original[self.root / ".icstex/sources.json"])
        self.assertFalse((self.root / PENDING_PATH).exists())

    def test_project_loader_does_not_follow_metadata_links(self):
        target = self.root / ".icstex/blocks.json"
        outside = Path(self.temp.name) / "outside.json"
        outside.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(outside)
        with patch("app.core.blocks.project_repository.BlockStore.from_bytes") as decode:
            with self.assertRaises((OSError, ValueError)):
                load_project(self.root)
            decode.assert_not_called()

    def test_journal_staging_failure_preserves_originals_and_blocks_retry(self):
        guard = self.guard()
        real = guard._replace
        def fail_after_evidence(path, data, expected):
            real(path, data, expected)
            if path.name == "before-0.bin":
                raise OSError("synthetic storage failure during staging")
        with patch.object(guard, "_replace", side_effect=fail_after_evidence):
            with self.assertRaises(OSError):
                guard.write(self.changed())
        self.assertEqual({p: p.read_bytes() for p in self.original}, self.original)
        journal = self.root / PENDING_PATH
        self.assertTrue((journal / "before-0.bin").is_file())
        with self.assertRaises(BlockWriteConflict):
            guard.write(self.changed())
        with self.assertRaises(BlockWriteConflict):
            self.guard()
