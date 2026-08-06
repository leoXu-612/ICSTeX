from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.preview_state import (
    FRESHNESS_LABELS,
    FRESHNESS_SEVERITY,
    PreviewFreshness,
    PreviewStateStore,
)


class PreviewStateStoreTests(TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "main.tex"
        self.root.write_text("source", encoding="utf-8")
        self.pdf = Path(self._tmp.name) / "preview.pdf"
        self.store = PreviewStateStore()

    def _write_pdf(self, path: Path | None = None) -> Path:
        target = path or self.pdf
        target.write_bytes(b"preview output")
        return target

    def _finish_success(self, build_id: int = 1, **kwargs: object):
        self.store.begin_build(self.root, build_id)
        return self.store.finish_build(
            self.root,
            build_id,
            success=True,
            pdf_file=self._write_pdf(),
            **kwargs,
        )

    def test_new_root_is_uncompiled(self) -> None:
        record = self.store.record_for(self.root)
        self.assertEqual(record.freshness, PreviewFreshness.UNCOMPILED)
        self.assertIsNone(record.last_successful_revision)
        self.assertFalse(record.has_valid_pdf)

    def test_records_are_isolated_by_normalized_root(self) -> None:
        alias = self.root.parent / "sub" / ".." / self.root.name
        other = self.root.with_name("other.tex")
        self.assertIs(self.store.record_for(self.root), self.store.record_for(alias))
        self.assertIsNot(self.store.record_for(self.root), self.store.record_for(other))

    def test_edit_increments_source_revision_and_marks_dirty(self) -> None:
        record = self.store.mark_edited(self.root)
        self.store.mark_edited(self.root)
        self.assertEqual(record.source_revision, 2)
        self.assertEqual(record.freshness, PreviewFreshness.DIRTY)

    def test_begin_build_captures_source_revision(self) -> None:
        self.store.mark_edited(self.root)
        record = self.store.begin_build(self.root, 4)
        self.assertEqual(record.build_revision, 1)
        self.assertEqual(record.active_build_id, 4)
        self.assertEqual(record.freshness, PreviewFreshness.COMPILING)

    def test_success_records_current_revision_and_metadata(self) -> None:
        self.store.mark_edited(self.root)
        record = self._finish_success(
            duration_seconds=0.25,
            engine="xelatex",
            fidelity="proxy",
            manifest_digest="abc123",
        )
        assert record is not None
        self.assertEqual(record.freshness, PreviewFreshness.CURRENT)
        self.assertEqual(record.last_successful_revision, 1)
        self.assertEqual(record.last_successful_pdf, self.pdf.resolve())
        self.assertEqual(record.last_duration_seconds, 0.25)
        self.assertEqual(record.last_engine, "xelatex")
        self.assertEqual(record.fidelity, "proxy")
        self.assertEqual(record.manifest_digest, "abc123")
        self.assertTrue(record.has_valid_pdf)

    def test_edit_during_build_keeps_successful_preview_dirty(self) -> None:
        self.store.mark_edited(self.root)
        self.store.begin_build(self.root, 1)
        self.store.mark_edited(self.root)
        record = self.store.finish_build(
            self.root,
            1,
            success=True,
            pdf_file=self._write_pdf(),
        )
        assert record is not None
        self.assertEqual(record.freshness, PreviewFreshness.DIRTY)
        self.assertEqual(record.last_successful_revision, 1)
        self.assertEqual(record.source_revision, 2)

    def test_failure_with_previous_pdf_is_failed_stale(self) -> None:
        self._finish_success()
        self.store.begin_build(self.root, 2)
        record = self.store.finish_build(self.root, 2, success=False)
        assert record is not None
        self.assertEqual(record.freshness, PreviewFreshness.FAILED_STALE)
        self.assertEqual(record.last_successful_revision, 0)
        self.assertTrue(record.has_valid_pdf)

    def test_failure_without_previous_pdf_is_failed_no_pdf(self) -> None:
        self.store.begin_build(self.root, 1)
        record = self.store.finish_build(self.root, 1, success=False)
        assert record is not None
        self.assertEqual(record.freshness, PreviewFreshness.FAILED_NO_PDF)
        self.assertFalse(record.has_valid_pdf)

    def test_success_requires_existing_nonempty_pdf(self) -> None:
        missing = self.pdf.with_name("missing.pdf")
        self.store.begin_build(self.root, 1)
        missing_result = self.store.finish_build(
            self.root,
            1,
            success=True,
            pdf_file=missing,
        )
        assert missing_result is not None
        self.assertEqual(missing_result.freshness, PreviewFreshness.FAILED_NO_PDF)

        self.pdf.write_bytes(b"")
        self.store.begin_build(self.root, 2)
        empty_result = self.store.finish_build(
            self.root,
            2,
            success=True,
            pdf_file=self.pdf,
        )
        assert empty_result is not None
        self.assertEqual(empty_result.freshness, PreviewFreshness.FAILED_NO_PDF)

    def test_deleted_previous_pdf_does_not_count_as_stale_output(self) -> None:
        self._finish_success()
        self.pdf.unlink()
        self.store.begin_build(self.root, 2)
        record = self.store.finish_build(self.root, 2, success=False)
        assert record is not None
        self.assertEqual(record.freshness, PreviewFreshness.FAILED_NO_PDF)

    def test_older_and_duplicate_results_are_rejected(self) -> None:
        old_pdf = self._write_pdf(self.pdf.with_name("old.pdf"))
        new_pdf = self._write_pdf(self.pdf.with_name("new.pdf"))
        self.store.begin_build(self.root, 1)
        self.store.begin_build(self.root, 2)
        self.assertIsNone(
            self.store.finish_build(
                self.root,
                1,
                success=True,
                pdf_file=old_pdf,
            )
        )
        applied = self.store.finish_build(
            self.root,
            2,
            success=True,
            pdf_file=new_pdf,
        )
        self.assertIsNotNone(applied)
        self.assertIsNone(self.store.finish_build(self.root, 2, success=False))
        self.assertEqual(
            self.store.record_for(self.root).last_successful_pdf,
            new_pdf.resolve(),
        )

    def test_stale_begin_does_not_replace_active_build(self) -> None:
        record = self.store.begin_build(self.root, 5)
        same = self.store.begin_build(self.root, 3)
        self.assertIs(record, same)
        self.assertEqual(record.active_build_id, 5)
        self.assertEqual(record.latest_build_id, 5)

    def test_clear_invalidates_in_flight_result(self) -> None:
        self.store.mark_edited(self.root)
        self.store.begin_build(self.root, 7)
        record = self.store.clear(self.root)
        self.assertEqual(record.freshness, PreviewFreshness.UNCOMPILED)
        self.assertEqual(record.source_revision, 1)
        self.assertIsNone(record.last_successful_revision)
        self.assertIsNone(record.active_build_id)

        late = self.store.finish_build(
            self.root,
            7,
            success=True,
            pdf_file=self._write_pdf(),
        )
        self.assertIsNone(late)
        self.assertEqual(record.freshness, PreviewFreshness.UNCOMPILED)

        self.store.begin_build(self.root, 8)
        applied = self.store.finish_build(
            self.root,
            8,
            success=True,
            pdf_file=self.pdf,
        )
        self.assertIsNotNone(applied)
        self.assertEqual(record.freshness, PreviewFreshness.CURRENT)

    def test_clear_removes_success_metadata(self) -> None:
        self._finish_success(
            duration_seconds=0.5,
            engine="pdflatex",
            fidelity="proxy",
            manifest_digest="digest",
        )
        record = self.store.clear_build_output(self.root)
        self.assertEqual(record.freshness, PreviewFreshness.UNCOMPILED)
        self.assertIsNone(record.last_successful_pdf)
        self.assertIsNone(record.last_successful_revision)
        self.assertIsNone(record.last_duration_seconds)
        self.assertIsNone(record.last_engine)
        self.assertIsNone(record.fidelity)
        self.assertIsNone(record.manifest_digest)

    def test_failed_attempt_uses_available_preview(self) -> None:
        self._finish_success()
        record = self.store.record_failed_attempt(self.root, engine="xelatex")
        self.assertEqual(record.freshness, PreviewFreshness.FAILED_STALE)
        self.assertEqual(record.last_engine, "xelatex")

    def test_every_state_has_label_and_severity(self) -> None:
        for freshness in PreviewFreshness:
            self.assertIn(freshness, FRESHNESS_LABELS)
            self.assertIn(
                FRESHNESS_SEVERITY[freshness],
                {"neutral", "success", "warning", "error"},
            )
