from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.blocks.source_registry import (
    SourceRecord,
    check_source,
    hash_file,
)


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
