from pathlib import Path
from dataclasses import replace
import hashlib
import json
import os
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core import history
from app.core.history import create_snapshot, list_snapshots, read_snapshot


class HistoryTests(TestCase):
    def test_create_list_and_read_snapshot(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("A", encoding="utf-8")

            first = create_snapshot(source, "A", "保存")
            duplicate = create_snapshot(source, "A", "保存")
            second = create_snapshot(source, "B", "编译成功")

            snapshots = list_snapshots(source)

            self.assertIsNotNone(first)
            self.assertIsNone(duplicate)
            self.assertIsNotNone(second)
            self.assertEqual([snapshot.label for snapshot in snapshots], ["编译成功", "保存"])
            self.assertEqual(read_snapshot(snapshots[0]), "B")

    def test_corrupt_snapshot_is_not_decoded_with_replacement_characters(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("Original", encoding="utf-8")
            snapshot = create_snapshot(source, "Original", "保存")
            assert snapshot is not None
            snapshot.snapshot_path.write_bytes(b"Corrupt \xff")

            with self.assertRaises(UnicodeDecodeError):
                read_snapshot(snapshot)

    def test_changed_valid_utf8_is_not_returned_under_old_digest(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("original")
            snapshot = create_snapshot(source, "original", "saved")
            snapshot.snapshot_path.write_text("modified")
            with self.assertRaises((OSError, ValueError)):
                read_snapshot(snapshot)

    def test_forged_manifest_never_reads_or_deletes_outside_project(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / "project"
            project.mkdir()
            source = project / "main.tex"
            source.write_text("original")
            snapshot = create_snapshot(source, "original", "saved")
            sentinel = root / "outside.tex"
            sentinel.write_text("original")
            manifest_path = snapshot.snapshot_path.parent / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest[0]["snapshot_path"] = str(sentinel)
            manifest[0]["sha256"] = hashlib.sha256(sentinel.read_bytes()).hexdigest()
            before = json.dumps(manifest).encode()
            manifest_path.write_bytes(before)
            with self.assertRaisesRegex((OSError, ValueError), "expected bucket"):
                list_snapshots(source)
            with self.assertRaisesRegex((OSError, ValueError), "expected bucket"):
                create_snapshot(source, "newer", "saved", max_snapshots=1)
            self.assertEqual(sentinel.read_text(), "original")
            self.assertEqual(manifest_path.read_bytes(), before)
            self.assertEqual(source.read_text(), "original")

    def test_direct_snapshot_read_is_bound_to_the_expected_source(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "main.tex"
            source.write_text("original")
            snapshot = create_snapshot(source, "original", "saved")
            with self.assertRaises((OSError, ValueError)):
                read_snapshot(replace(snapshot, snapshot_path=source))
            with self.assertRaises((OSError, ValueError)):
                read_snapshot(snapshot, expected_source=root / "other.tex")

    def test_known_links_are_never_used_for_history_writes_or_reads(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / "project"
            project.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (project / ".icstex").symlink_to(outside, target_is_directory=True)
            source = project / "main.tex"
            source.write_text("original")
            with self.assertRaises((OSError, ValueError)):
                create_snapshot(source, "original", "saved")
            self.assertEqual(list(outside.iterdir()), [])

    def test_unique_ids_do_not_delete_a_kept_snapshot_when_labels_differ(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("same")
            first = create_snapshot(source, "same", "saved", max_snapshots=1)
            second = create_snapshot(source, "same", "compiled", max_snapshots=1)
            self.assertNotEqual(first.id, second.id)
            self.assertEqual(read_snapshot(second), "same")
            self.assertEqual(list_snapshots(source), [second])

    def test_legacy_bucket_is_read_without_migration_or_deletion(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "main.tex"
            source.write_text("original")
            bucket = root / ".icstex/history/main.tex"
            bucket.mkdir(parents=True)
            payload = b"old valid bytes\r\n"
            digest = hashlib.sha256(payload).hexdigest()
            ident = "20260910T120000Z-" + digest[:10]
            path = bucket / (ident + ".tex")
            path.write_bytes(payload)
            entry = {"id": ident, "source_path": str(source), "snapshot_path": str(path),
                     "label": "legacy", "created_at": "2026-09-10T12:00:00+00:00",
                     "size": len(payload), "sha256": digest}
            manifest = bucket / "manifest.json"
            original = json.dumps([entry]).encode()
            manifest.write_bytes(original)
            self.assertEqual(read_snapshot(list_snapshots(source)[0]), payload.decode())
            new = create_snapshot(source, "new", "saved", max_snapshots=1)
            self.assertNotEqual(new.snapshot_path.parent, bucket)
            self.assertEqual(manifest.read_bytes(), original)
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(len(list_snapshots(source)), 2)

    def test_chinese_and_sanitized_name_collisions_get_separate_buckets(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            snapshots = []
            for name in ("第一篇.tex", "第二篇.tex", "a b.tex", "a_b.tex"):
                source = root / name
                source.write_text(name)
                snapshots.append(create_snapshot(source, name, "saved"))
            self.assertEqual(len({item.snapshot_path.parent for item in snapshots}), 4)
            for item in snapshots:
                self.assertEqual(list_snapshots(item.source_path), [item])

    def test_malformed_manifest_is_preserved_instead_of_replaced_with_empty_history(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("original")
            snapshot = create_snapshot(source, "original", "saved")
            manifest = snapshot.snapshot_path.parent / "manifest.json"
            manifest.write_bytes(b"malformed JSON")
            with self.assertRaises((OSError, ValueError)):
                create_snapshot(source, "new", "saved")
            self.assertEqual(manifest.read_bytes(), b"malformed JSON")

    def test_manifest_publication_failure_keeps_previous_record_and_bytes(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("original")
            first = create_snapshot(source, "old", "saved", max_snapshots=1)
            manifest = first.snapshot_path.parent / "manifest.json"
            before = manifest.read_bytes()
            with patch.object(history.os, "replace", side_effect=OSError("write failed")):
                with self.assertRaises(OSError):
                    create_snapshot(source, "new", "saved", max_snapshots=1)
            self.assertEqual(manifest.read_bytes(), before)
            self.assertEqual(read_snapshot(first), "old")

    def test_object_or_manifest_links_are_refused_without_touching_their_targets(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "main.tex"
            source.write_text("source")
            snapshot = create_snapshot(source, "original", "saved")
            outside = root / "outside.tex"
            outside.write_text("original")
            snapshot.snapshot_path.unlink()
            snapshot.snapshot_path.symlink_to(outside)
            with self.assertRaises((OSError, ValueError)):
                read_snapshot(snapshot)
            with self.assertRaises((OSError, ValueError)):
                create_snapshot(source, "new", "saved", max_snapshots=1)
            self.assertEqual(outside.read_text(), "original")
            manifest = snapshot.snapshot_path.parent / "manifest.json"
            external_index = root / "outside.json"
            external_index.write_bytes(manifest.read_bytes())
            manifest.unlink()
            manifest.symlink_to(external_index)
            with self.assertRaises((OSError, ValueError)):
                list_snapshots(source)

    def test_changed_retention_candidate_is_not_deleted_to_meet_the_limit(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("source")
            first = create_snapshot(source, "old", "saved")
            manifest = first.snapshot_path.parent / "manifest.json"
            index = manifest.read_bytes()
            first.snapshot_path.write_text("externally changed history")
            with self.assertRaises((OSError, ValueError)):
                create_snapshot(source, "new", "saved", max_snapshots=1)
            self.assertEqual(manifest.read_bytes(), index)
            self.assertEqual(first.snapshot_path.read_text(), "externally changed history")

    def test_fsync_failure_removes_only_the_new_partial_object(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("source")
            first = create_snapshot(source, "old", "saved")
            before = {p.name: p.read_bytes() for p in first.snapshot_path.parent.iterdir()}
            with patch.object(history.os, "fsync", side_effect=OSError("No space left")):
                with self.assertRaises(OSError):
                    create_snapshot(source, "new", "saved")
            self.assertEqual({p.name: p.read_bytes() for p in first.snapshot_path.parent.iterdir()}, before)

    def test_changed_manifest_during_staging_is_not_replaced(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("source")
            first = create_snapshot(source, "old", "saved")
            manifest = first.snapshot_path.parent / "manifest.json"
            original = history._Bucket.write_new
            def write(bucket, name, data):
                result = original(bucket, name, data)
                if name.startswith(".manifest-"):
                    manifest.write_bytes(b"external index change")
                return result
            with patch.object(history._Bucket, "write_new", write), self.assertRaises((OSError, ValueError)):
                create_snapshot(source, "new", "saved", max_snapshots=1)
            self.assertEqual(manifest.read_bytes(), b"external index change")
            self.assertEqual(first.snapshot_path.read_text(), "old")

    def test_replaced_bucket_is_never_used_for_new_writes_or_cleanup(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "main.tex"
            source.write_text("source")
            first = create_snapshot(source, "old", "saved")
            bucket_path = first.snapshot_path.parent
            original = history._Bucket.write_new
            def write(bucket, name, data):
                result = original(bucket, name, data)
                if name.endswith(".tex"):
                    bucket.path.rename(root / "moved-history")
                    bucket.path.mkdir()
                    (bucket.path / "foreign.txt").write_bytes(b"preserve foreign")
                return result
            with patch.object(history._Bucket, "write_new", write), self.assertRaises((OSError, ValueError)):
                create_snapshot(source, "new", "saved", max_snapshots=1)
            self.assertEqual((bucket_path / "foreign.txt").read_bytes(), b"preserve foreign")
            self.assertEqual(list(bucket_path.iterdir()), [bucket_path / "foreign.txt"])
            self.assertEqual((root / "moved-history" / first.snapshot_path.name).read_text(), "old")

    def test_index_limits_duplicate_fields_and_future_fields_fail_closed(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("source")
            first = create_snapshot(source, "old", "saved")
            manifest = first.snapshot_path.parent / "manifest.json"
            record = json.loads(manifest.read_text())[0]
            variants = (json.dumps([record] * 41).encode(),
                        json.dumps([{**record, "future": True}]).encode(),
                        json.dumps([record]).encode().replace(b'"label": "saved"', b'"label":"saved", "label":"changed"'))
            for payload in variants:
                manifest.write_bytes(payload)
                with self.subTest(payload=payload[:80]), self.assertRaises((OSError, ValueError)):
                    create_snapshot(source, "new", "saved")
                self.assertEqual(manifest.read_bytes(), payload)

    def test_retention_is_bounded_and_only_current_bucket_objects_are_pruned(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("source")
            for index in range(45):
                create_snapshot(source, str(index), "saved", max_snapshots=10000)
            snapshots = list_snapshots(source)
            self.assertEqual(len(snapshots), 40)
            self.assertEqual(len(list(snapshots[0].snapshot_path.parent.glob("*.tex"))), 40)
            self.assertEqual(read_snapshot(snapshots[0]), "44")
            self.assertEqual(read_snapshot(snapshots[-1]), "5")

    def test_linked_snapshot_is_rejected_before_any_leaf_open(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "main.tex"
            source.write_text("source")
            snapshot = create_snapshot(source, "original", "saved")
            outside = root / "outside.tex"
            outside.write_text("original")
            snapshot.snapshot_path.unlink()
            snapshot.snapshot_path.symlink_to(outside)
            original_open = history.os.open
            def guarded_open(path, *args, **kwargs):
                if Path(path).name == snapshot.snapshot_path.name:
                    self.fail("An observed snapshot link reached os.open")
                return original_open(path, *args, **kwargs)
            with patch.object(history.os, "open", side_effect=guarded_open):
                with self.assertRaises(history.HistoryError):
                    read_snapshot(snapshot)
