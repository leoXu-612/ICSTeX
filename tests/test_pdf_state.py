from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.compiler import CompileOutcome
from app.core.pdf_state import (
    FRESHNESS_LABELS,
    FRESHNESS_SEVERITY,
    PdfFreshness,
    PdfStateStore,
)


class PdfStateStoreTests(TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "main.tex"
        self.root.write_text("x", encoding="utf-8")
        self.pdf = Path(self._tmp.name) / "main.pdf"
        self.store = PdfStateStore()

    def _write_pdf(self) -> None:
        self.pdf.write_bytes(b"%PDF-1.4 fake")

    def test_open_root_without_build_is_uncompiled(self) -> None:
        record = self.store.record_for(self.root)
        self.assertEqual(record.freshness, PdfFreshness.UNCOMPILED)
        self.assertIsNone(record.last_successful_pdf)
        self.assertFalse(record.export_allowed)

    def test_records_are_keyed_by_normalized_root(self) -> None:
        alias = Path(self._tmp.name) / "sub" / ".." / "main.tex"
        self.assertIs(self.store.record_for(self.root), self.store.record_for(alias))

    def test_edit_marks_dirty_from_any_state(self) -> None:
        for prepare in (
            lambda: None,
            lambda: self.store.begin_build(self.root, 1),
            lambda: self.store.finish_build(self.root, 1, CompileOutcome.LATEX_ERROR),
        ):
            self.store = PdfStateStore()
            prepare()
            record = self.store.mark_edited(self.root)
            self.assertEqual(record.freshness, PdfFreshness.DIRTY)

    def test_edit_increments_source_revision(self) -> None:
        record = self.store.mark_edited(self.root)
        first = record.source_revision
        self.store.mark_edited(self.root)
        self.assertEqual(record.source_revision, first + 1)

    def test_compile_start_marks_compiling_and_captures_revision(self) -> None:
        self.store.mark_edited(self.root)
        record = self.store.begin_build(self.root, 1)
        self.assertEqual(record.freshness, PdfFreshness.COMPILING)
        self.assertEqual(record.compile_revision, record.source_revision)

    def test_success_without_edit_is_current(self) -> None:
        self._write_pdf()
        self.store.begin_build(self.root, 1)
        record = self.store.finish_build(
            self.root, 1, CompileOutcome.SUCCESS, pdf_file=self.pdf
        )
        assert record is not None
        self.assertEqual(record.freshness, PdfFreshness.CURRENT)
        self.assertEqual(record.last_successful_pdf, self.pdf.resolve())
        self.assertEqual(record.last_successful_revision, record.source_revision)
        self.assertTrue(record.export_allowed)
        self.assertFalse(record.export_needs_warning)

    def test_success_with_edit_during_build_is_dirty(self) -> None:
        self._write_pdf()
        self.store.begin_build(self.root, 1)
        self.store.mark_edited(self.root)
        record = self.store.finish_build(
            self.root, 1, CompileOutcome.SUCCESS, pdf_file=self.pdf
        )
        assert record is not None
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)
        # The successful PDF is still recorded even though it is already stale.
        self.assertEqual(record.last_successful_pdf, self.pdf.resolve())
        self.assertTrue(record.export_needs_warning)

    def test_failure_with_previous_pdf_is_failed_stale(self) -> None:
        self._write_pdf()
        self.store.begin_build(self.root, 1)
        self.store.finish_build(self.root, 1, CompileOutcome.SUCCESS, pdf_file=self.pdf)
        self.store.begin_build(self.root, 2)
        record = self.store.finish_build(self.root, 2, CompileOutcome.LATEX_ERROR)
        assert record is not None
        self.assertEqual(record.freshness, PdfFreshness.FAILED_STALE)
        self.assertEqual(record.last_successful_pdf, self.pdf.resolve())
        self.assertTrue(record.export_allowed)
        self.assertTrue(record.export_needs_warning)

    def test_stop_behaves_like_failure_for_freshness(self) -> None:
        self.store.begin_build(self.root, 1)
        record = self.store.finish_build(self.root, 1, CompileOutcome.STOPPED)
        assert record is not None
        self.assertEqual(record.freshness, PdfFreshness.FAILED_NO_PDF)

    def test_failure_without_previous_pdf_is_failed_no_pdf(self) -> None:
        self.store.begin_build(self.root, 1)
        record = self.store.finish_build(self.root, 1, CompileOutcome.LATEX_ERROR)
        assert record is not None
        self.assertEqual(record.freshness, PdfFreshness.FAILED_NO_PDF)
        self.assertFalse(record.export_allowed)

    def test_deleted_pdf_downgrades_failure_to_no_pdf(self) -> None:
        self._write_pdf()
        self.store.begin_build(self.root, 1)
        self.store.finish_build(self.root, 1, CompileOutcome.SUCCESS, pdf_file=self.pdf)
        self.pdf.unlink()
        self.store.begin_build(self.root, 2)
        record = self.store.finish_build(self.root, 2, CompileOutcome.LATEX_ERROR)
        assert record is not None
        self.assertEqual(record.freshness, PdfFreshness.FAILED_NO_PDF)

    def test_clean_build_output_resets_to_uncompiled(self) -> None:
        self._write_pdf()
        self.store.begin_build(self.root, 1)
        self.store.finish_build(self.root, 1, CompileOutcome.SUCCESS, pdf_file=self.pdf)
        record = self.store.clear_build_output(self.root)
        self.assertEqual(record.freshness, PdfFreshness.UNCOMPILED)
        self.assertIsNone(record.last_successful_pdf)
        self.assertIsNone(record.last_successful_revision)
        self.assertFalse(record.export_allowed)

    def test_late_older_result_cannot_replace_newer_state(self) -> None:
        self._write_pdf()
        old_pdf = Path(self._tmp.name) / "old.pdf"
        old_pdf.write_bytes(b"%PDF-1.4 older")
        self.store.begin_build(self.root, 1)
        self.store.begin_build(self.root, 2)
        applied = self.store.finish_build(
            self.root, 2, CompileOutcome.SUCCESS, pdf_file=self.pdf
        )
        self.assertIsNotNone(applied)
        stale = self.store.finish_build(
            self.root, 1, CompileOutcome.SUCCESS, pdf_file=old_pdf
        )
        self.assertIsNone(stale)
        record = self.store.record_for(self.root)
        self.assertEqual(record.freshness, PdfFreshness.CURRENT)
        self.assertEqual(record.last_successful_pdf, self.pdf.resolve())

    def test_stale_begin_build_does_not_regress_latest_build(self) -> None:
        self.store.begin_build(self.root, 5)
        record = self.store.begin_build(self.root, 3)
        self.assertEqual(record.latest_build_id, 5)

    def test_clean_cache_invalidates_in_flight_build_result(self) -> None:
        self.store.begin_build(self.root, 7)
        self.store.clear_build_output(self.root)
        late = self.store.finish_build(self.root, 7, CompileOutcome.STOPPED)
        self.assertIsNone(late)
        record = self.store.record_for(self.root)
        self.assertEqual(record.freshness, PdfFreshness.UNCOMPILED)
        # The next real build still applies normally.
        self.store.begin_build(self.root, 8)
        applied = self.store.finish_build(self.root, 8, CompileOutcome.LATEX_ERROR)
        self.assertIsNotNone(applied)
        self.assertEqual(record.freshness, PdfFreshness.FAILED_NO_PDF)

    def test_failed_attempt_without_build_updates_outcome_and_freshness(self) -> None:
        record = self.store.record_failed_attempt(self.root, CompileOutcome.TOOLCHAIN_MISSING)
        self.assertEqual(record.last_outcome, CompileOutcome.TOOLCHAIN_MISSING)
        self.assertEqual(record.freshness, PdfFreshness.FAILED_NO_PDF)

    def test_compiling_state_allows_export_with_warning_when_pdf_exists(self) -> None:
        self._write_pdf()
        self.store.begin_build(self.root, 1)
        self.store.finish_build(self.root, 1, CompileOutcome.SUCCESS, pdf_file=self.pdf)
        record = self.store.begin_build(self.root, 2)
        self.assertEqual(record.freshness, PdfFreshness.COMPILING)
        self.assertTrue(record.export_allowed)
        self.assertTrue(record.export_needs_warning)

    def test_every_freshness_state_has_label_and_severity(self) -> None:
        for freshness in PdfFreshness:
            self.assertIn(freshness, FRESHNESS_LABELS)
            self.assertIn(FRESHNESS_SEVERITY[freshness], {"neutral", "success", "warning", "error"})
