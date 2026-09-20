from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import hashlib
import os

from app.core.blocks import source_registry

from app.core.blocks.source_registry import (
    SourceRecord,
    check_source,
    hash_file,
)
from app.core.blocks.schema import validate_source


class SourceRegistryTests(TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name)

    def _record(self, relative: str, content: bytes) -> SourceRecord:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return SourceRecord(sourceId="src_1", kind="xlsx", relativePath=relative, baseSha256=hash_file(path))

    def test_unchanged_is_ok(self) -> None:
        record = self._record("data/results.xlsx", b"snapshot")
        status = check_source(self.project, record)
        self.assertEqual(status.state, "ok")

    def test_changed_content_detected(self) -> None:
        record = self._record("data/results.xlsx", b"snapshot")
        (self.project / "data" / "results.xlsx").write_bytes(b"new-content")
        status = check_source(self.project, record)
        self.assertEqual(status.state, "changed")

    def test_missing_source(self) -> None:
        record = self._record("data/results.xlsx", b"snapshot")
        (self.project / "data" / "results.xlsx").unlink()
        status = check_source(self.project, record)
        self.assertEqual(status.state, "missing")

    def test_moved_source_found_by_hash(self) -> None:
        record = self._record("data/results.xlsx", b"snapshot")
        (self.project / "data" / "results.xlsx").unlink()
        archive = self.project / "archive"
        archive.mkdir(exist_ok=True)
        (archive / "results-copy.xlsx").write_bytes(b"snapshot")
        status = check_source(self.project, record)
        self.assertEqual(status.state, "moved")
        self.assertEqual(status.relativePath, "archive/results-copy.xlsx")

    def test_path_escape_is_unsafe(self) -> None:
        record = SourceRecord(
            sourceId="src_2",
            kind="csv",
            relativePath="../../etc/passwd",
            baseSha256="x",
        )
        status = check_source(self.project, record)
        self.assertEqual(status.state, "unsafe")

    def test_recorded_link_and_internal_paths_are_unsafe_without_reading(self):
        record = self._record("data/results.xlsx", b"snapshot")
        (self.project / "linked.xlsx").symlink_to(self.project / record.relativePath)
        (self.project / ".git").mkdir()
        (self.project / ".git" / "config").write_bytes(b"snapshot")
        for relative in ("linked.xlsx", ".git/config", str(self.project / record.relativePath)):
            with self.subTest(relative=relative):
                candidate = SourceRecord("src_2", "xlsx", relative, record.baseSha256)
                with patch.object(source_registry, "hash_file", side_effect=AssertionError("unsafe read")):
                    self.assertEqual(check_source(self.project, candidate).state, "unsafe")

    def test_missing_lookup_skips_links_internal_files_and_other_formats(self):
        record = self._record("data/results.xlsx", b"snapshot")
        (self.project / record.relativePath).unlink()
        with TemporaryDirectory() as outside:
            external = Path(outside) / "outside.xlsx"
            external.write_bytes(b"snapshot")
            (self.project / "linked.xlsx").symlink_to(external)
            (self.project / "linked-directory").symlink_to(outside, target_is_directory=True)
            for directory in (".git", ".icstex", ".venv", "node_modules", "__pycache__"):
                folder = self.project / directory
                folder.mkdir()
                (folder / "candidate.xlsx").write_bytes(b"snapshot")
            (self.project / "notes.txt").write_bytes(b"snapshot")
            self.assertEqual(check_source(self.project, record).state, "missing")

    def test_identical_candidates_do_not_claim_a_unique_move(self):
        record = self._record("data/results.xlsx", b"snapshot")
        (self.project / record.relativePath).unlink()
        for name in ("one.xlsx", "two.xlsx"):
            (self.project / name).write_bytes(b"snapshot")
        status = check_source(self.project, record)
        self.assertEqual(status.state, "unknown")
        self.assertIsNone(status.currentSha256)

    def test_unreadable_input_is_unknown_not_missing_or_an_exception(self):
        record = self._record("data/results.xlsx", b"snapshot")
        with patch.object(source_registry, "hash_file", side_effect=PermissionError("synthetic denied")):
            self.assertEqual(check_source(self.project, record).state, "unknown")

    def test_invalid_baseline_is_unknown(self):
        self._record("data/results.xlsx", b"snapshot")
        record = SourceRecord("src_2", "xlsx", "data/results.xlsx", "not-a-hash")
        self.assertEqual(check_source(self.project, record).state, "unknown")

    def test_file_and_batch_read_limits_produce_unknown(self):
        first = self._record("data/a.xlsx", b"12345")
        second = self._record("data/b.xlsx", b"67890")
        limits = source_registry.SourceCheckLimits(max_file_bytes=4)
        self.assertEqual(check_source(self.project, first, limits=limits).state, "unknown")
        limits = source_registry.SourceCheckLimits(max_total_bytes=8)
        results = source_registry.check_sources(self.project, (first, second), limits=limits)
        self.assertEqual([result.state for result in results], ["ok", "unknown"])

    def test_entry_limit_and_unreadable_search_do_not_claim_missing(self):
        record = SourceRecord("src_1", "xlsx", "gone.xlsx", hashlib.sha256(b"snapshot").hexdigest())
        for index in range(3):
            (self.project / f"{index}.txt").write_bytes(b"unrelated")
        status = check_source(self.project, record, limits=source_registry.SourceCheckLimits(max_entries=2))
        self.assertEqual(status.state, "unknown")
        with patch.object(source_registry.os, "scandir", side_effect=PermissionError("synthetic denied")):
            self.assertEqual(check_source(self.project, record).state, "unknown")

    def test_cancelled_check_raises_before_reading(self):
        record = self._record("data/results.xlsx", b"snapshot")
        with patch.object(source_registry, "hash_file", side_effect=AssertionError("unexpected read")):
            with self.assertRaises(source_registry.SourceCheckCancelled):
                check_source(self.project, record, cancelled=lambda: True)

    def test_file_replacement_during_hash_is_unknown(self):
        from contextlib import contextmanager

        record = self._record("data/results.xlsx", b"snapshot")
        path = self.project / record.relativePath
        original_open = source_registry._open_safe_input

        @contextmanager
        def replaced_after_open(*args, **kwargs):
            with original_open(*args, **kwargs) as stream:
                replacement = path.with_name("replacement.xlsx")
                replacement.write_bytes(b"snapshot")
                os.replace(replacement, path)
                yield stream

        with patch.object(source_registry, "_open_safe_input", replaced_after_open):
            self.assertEqual(check_source(self.project, record).state, "unknown")

    def test_missing_lookup_is_shared_by_the_batch(self):
        one = SourceRecord("src_1", "xlsx", "gone.xlsx", hashlib.sha256(b"one").hexdigest())
        two = SourceRecord("src_2", "xlsx", "also-gone.xlsx", hashlib.sha256(b"two").hexdigest())
        (self.project / "one.xlsx").write_bytes(b"one")
        (self.project / "two.xlsx").write_bytes(b"two")
        with patch.object(source_registry, "hash_file", wraps=source_registry.hash_file) as hashing:
            results = source_registry.check_sources(self.project, (one, two))
        self.assertEqual([result.state for result in results], ["moved", "moved"])
        # Two failed recorded-path opens plus one read of each candidate, not
        # one full project search per source record.
        self.assertEqual(hashing.call_count, 4)

    def test_disappearing_after_hash_does_not_become_a_missing_candidate(self):
        from contextlib import contextmanager

        record = self._record("data/results.xlsx", b"snapshot")
        path = (self.project / record.relativePath).resolve()
        (self.project / "duplicate.xlsx").write_bytes(b"snapshot")
        original_open = source_registry._open_safe_input

        @contextmanager
        def vanishing_stream(*args, **kwargs):
            with original_open(*args, **kwargs) as stream:
                class Reader:
                    def fileno(self):
                        return stream.fileno()

                    def read(self, size):
                        result = stream.read(size)
                        if not result and args[1] == path:
                            path.unlink()
                        return result
                yield Reader()

        with patch.object(source_registry, "_open_safe_input", vanishing_stream):
            self.assertEqual(check_source(self.project, record).state, "unknown")

    def test_lookup_does_not_accept_a_reappeared_original_as_moved(self):
        record = SourceRecord("src_1", "xlsx", "gone.xlsx", hashlib.sha256(b"snapshot").hexdigest())
        original_scan = source_registry._candidate_files

        def reappeared(*args):
            (self.project / record.relativePath).write_bytes(b"snapshot")
            yield from original_scan(*args)

        with patch.object(source_registry, "_candidate_files", reappeared):
            self.assertEqual(check_source(self.project, record).state, "unknown")

    def test_scan_directory_replacement_cannot_follow_an_outside_link(self):
        if os.open not in os.supports_dir_fd:
            self.skipTest("POSIX directory descriptor acceptance only")
        record = SourceRecord("src_1", "xlsx", "gone.xlsx", hashlib.sha256(b"snapshot").hexdigest())
        directory = self.project / "subdir"
        directory.mkdir()
        original_scan = source_registry._scan_directory
        with TemporaryDirectory() as outside:
            (Path(outside) / "candidate.xlsx").write_bytes(b"snapshot")

            def replaced(project, target):
                if target.name == "subdir":
                    directory.rmdir()
                    directory.symlink_to(outside, target_is_directory=True)
                return original_scan(project, target)

            with patch.object(source_registry, "_scan_directory", replaced):
                self.assertEqual(check_source(self.project, record).state, "unknown")

    def test_cancel_is_checked_between_stream_chunks(self):
        from contextlib import contextmanager
        import threading

        record = self._record("data/results.xlsx", b"snapshot")
        cancelled = threading.Event()
        original_open = source_registry._open_safe_input

        @contextmanager
        def cancelling_stream(*args, **kwargs):
            with original_open(*args, **kwargs) as stream:
                class Reader:
                    def fileno(self):
                        return stream.fileno()

                    def read(self, size):
                        result = stream.read(size)
                        cancelled.set()
                        return result
                yield Reader()

        with patch.object(source_registry, "_open_safe_input", cancelling_stream):
            with self.assertRaises(source_registry.SourceCheckCancelled):
                check_source(self.project, record, cancelled=cancelled.is_set)

    def test_non_regular_source_never_blocks_or_passes(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO fixture requires POSIX")
        os.mkfifo(self.project / "pipe.csv")
        record = SourceRecord("src_1", "csv", "pipe.csv", hashlib.sha256(b"").hexdigest())
        self.assertEqual(check_source(self.project, record).state, "unknown")

    def test_limits_apply_to_records_and_incomplete_search_candidates(self):
        one = self._record("one.csv", b"one")
        two = self._record("two.csv", b"two")
        with patch.object(source_registry, "hash_file", side_effect=AssertionError("too many records")):
            results = source_registry.check_sources(self.project, (one, two),
                                                   limits=source_registry.SourceCheckLimits(max_records=1))
        self.assertEqual([result.state for result in results], ["unknown", "unknown"])
        (self.project / "one.csv").unlink()
        (self.project / "copy.csv").write_bytes(b"one")
        (self.project / "large.csv").write_bytes(b"oversize")
        self.assertEqual(check_source(self.project, one,
                                     limits=source_registry.SourceCheckLimits(max_file_bytes=4)).state, "unknown")

    def test_unsearched_format_stays_unknown(self):
        record = SourceRecord("src_1", "linked", "gone.bin", hashlib.sha256(b"snapshot").hexdigest())
        self.assertEqual(check_source(self.project, record).state, "unknown")

    def test_source_schema_validation(self) -> None:
        valid = {
            "sourceId": "src_1",
            "kind": "xlsx",
            "relativePath": "data/results.xlsx",
            "baseSha256": "a" * 64,
        }
        self.assertEqual(validate_source(valid), [])

        missing = dict(valid)
        del missing["baseSha256"]
        self.assertTrue(validate_source(missing))

        bad_kind = dict(valid, kind="exe")
        self.assertTrue(validate_source(bad_kind))

        bad_hash = dict(valid, baseSha256="not-a-sha")
        self.assertTrue(validate_source(bad_hash))
