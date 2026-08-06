from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.core.compiler import BuildPurpose, CompileOutcome, CompileResult
from app.core.pdf_state import PdfFreshness, PdfStateStore
from app.gui.pdf_export_controller import PdfExportController


class _Documents:
    def __init__(self) -> None:
        self.flush_results: list[bool] = []
        self.flushed: list[Path] = []

    def flush_root_documents(self, root: Path) -> bool:
        self.flushed.append(root)
        return self.flush_results.pop(0) if self.flush_results else True


class _Manager:
    def __init__(self) -> None:
        self.purposes: list[BuildPurpose] = []

    def compile_async(self, purpose: BuildPurpose) -> None:
        self.purposes.append(purpose)


class PdfExportControllerTests(TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)
        self.root = self.directory / "main.tex"
        self.root.write_text("source", encoding="utf-8")
        self.canonical_pdf = self.directory / ".latex_build" / "main.pdf"
        self.canonical_pdf.parent.mkdir()
        self.store = PdfStateStore()
        self.documents = _Documents()
        self.manager = _Manager()
        self.errors: list[str] = []
        self.statuses: list[tuple[str, int]] = []
        self.window = SimpleNamespace(
            documents=self.documents,
            pdf_state=self.store,
            compile_managers={self.root.resolve(): self.manager},
            notify_pdf_export_error=self.errors.append,
            notify_pdf_export_status=lambda message, duration: self.statuses.append(
                (message, duration)
            ),
        )
        self.controller = PdfExportController(self.window)

    def _result(
        self,
        build_id: int,
        *,
        purpose: BuildPurpose = BuildPurpose.FINAL,
        outcome: CompileOutcome = CompileOutcome.SUCCESS,
    ) -> CompileResult:
        return CompileResult(
            root_file=self.root,
            output_dir=self.canonical_pdf.parent,
            pdf_file=self.canonical_pdf,
            log_file=self.canonical_pdf.with_suffix(".log"),
            command=["latexmk"],
            returncode=0 if outcome is CompileOutcome.SUCCESS else 1,
            stdout="",
            stderr="",
            duration_seconds=0.1,
            outcome=outcome,
            build_id=build_id,
            purpose=purpose,
        )

    def _finish_current(self, build_id: int = 1):
        self.canonical_pdf.write_bytes(b"%PDF-1.4 canonical")
        self.store.begin_build(self.root, build_id)
        record = self.store.finish_build(
            self.root,
            build_id,
            CompileOutcome.SUCCESS,
            pdf_file=self.canonical_pdf,
        )
        assert record is not None
        return record

    def test_current_canonical_pdf_exports_immediately_and_atomically(self) -> None:
        self._finish_current()
        target = self.directory / "submission.pdf"

        self.assertTrue(self.controller.request_export(self.root, target))

        self.assertEqual(target.read_bytes(), b"%PDF-1.4 canonical")
        self.assertEqual(self.manager.purposes, [])
        self.assertEqual(self.documents.flushed, [self.root.resolve()])
        self.assertIsNone(self.controller.pending_for(self.root))

    def test_dirty_canonical_queues_final_and_preview_result_is_ignored(self) -> None:
        self._finish_current()
        self.store.mark_edited(self.root)
        target = self.directory / "submission.pdf"

        self.assertTrue(self.controller.request_export(self.root, target))
        self.assertEqual(self.manager.purposes, [BuildPurpose.FINAL])
        self.assertFalse(target.exists())

        preview = self.directory / ".icstex" / "preview" / "main.pdf"
        preview.parent.mkdir(parents=True)
        preview.write_bytes(b"%PDF-1.4 preview")
        result = self._result(2, purpose=BuildPurpose.PREVIEW)
        result = CompileResult(**{**result.__dict__, "pdf_file": preview})

        self.assertFalse(
            self.controller.handle_compile_result(
                result,
                self.store.record_for(self.root),
            )
        )
        self.assertFalse(target.exists())
        self.assertIsNotNone(self.controller.pending_for(self.root))

    def test_edit_during_final_build_flushes_and_queues_another_final(self) -> None:
        self.store.mark_edited(self.root)
        target = self.directory / "submission.pdf"
        self.assertTrue(self.controller.request_export(self.root, target))

        self.store.begin_build(self.root, 1)
        self.assertTrue(
            self.controller.handle_compile_started(self.root, 1, BuildPurpose.FINAL)
        )
        self.store.mark_edited(self.root)
        self.canonical_pdf.write_bytes(b"%PDF-1.4 stale-final")
        stale = self.store.finish_build(
            self.root,
            1,
            CompileOutcome.SUCCESS,
            pdf_file=self.canonical_pdf,
        )
        assert stale is not None
        self.assertEqual(stale.freshness, PdfFreshness.DIRTY)

        self.assertTrue(self.controller.handle_compile_result(self._result(1), stale))
        self.assertFalse(target.exists())
        self.assertEqual(
            self.manager.purposes,
            [BuildPurpose.FINAL, BuildPurpose.FINAL],
        )
        self.assertEqual(len(self.documents.flushed), 2)

        self.store.begin_build(self.root, 2)
        self.assertTrue(
            self.controller.handle_compile_started(self.root, 2, BuildPurpose.FINAL)
        )
        self.canonical_pdf.write_bytes(b"%PDF-1.4 current-final")
        current = self.store.finish_build(
            self.root,
            2,
            CompileOutcome.SUCCESS,
            pdf_file=self.canonical_pdf,
        )
        assert current is not None
        self.assertTrue(self.controller.handle_compile_result(self._result(2), current))
        self.assertEqual(target.read_bytes(), b"%PDF-1.4 current-final")
        self.assertIsNone(self.controller.pending_for(self.root))

    def test_failed_final_cancels_without_copying_old_or_preview_pdf(self) -> None:
        self._finish_current()
        self.store.mark_edited(self.root)
        target = self.directory / "submission.pdf"
        self.assertTrue(self.controller.request_export(self.root, target))
        self.assertTrue(
            self.controller.handle_compile_started(self.root, 2, BuildPurpose.FINAL)
        )

        record = self.store.record_for(self.root)
        self.assertTrue(
            self.controller.handle_compile_result(
                self._result(2, outcome=CompileOutcome.LATEX_ERROR),
                record,
            )
        )

        self.assertFalse(target.exists())
        self.assertIsNone(self.controller.pending_for(self.root))
        self.assertIn("未导出任何预览或旧版本", self.errors[-1])

    def test_failure_from_final_already_running_before_request_keeps_successor_pending(self) -> None:
        self._finish_current()
        self.store.mark_edited(self.root)
        self.store.begin_build(self.root, 2)
        target = self.directory / "submission.pdf"

        # Build 2 started before the request, so the export queues a successor
        # FINAL and intentionally remains unbound until that successor starts.
        self.assertTrue(self.controller.request_export(self.root, target))
        pending = self.controller.pending_for(self.root)
        self.assertIsNotNone(pending)
        assert pending is not None
        self.assertIsNone(pending.bound_build_id)

        failed = self.store.finish_build(
            self.root,
            2,
            CompileOutcome.LATEX_ERROR,
        )
        assert failed is not None
        self.assertFalse(
            self.controller.handle_compile_result(
                self._result(2, outcome=CompileOutcome.LATEX_ERROR),
                failed,
            )
        )
        self.assertIsNotNone(self.controller.pending_for(self.root))
        self.assertFalse(target.exists())

        self.store.begin_build(self.root, 3)
        self.assertTrue(
            self.controller.handle_compile_started(self.root, 3, BuildPurpose.FINAL)
        )
        self.canonical_pdf.write_bytes(b"%PDF-1.4 successor-final")
        current = self.store.finish_build(
            self.root,
            3,
            CompileOutcome.SUCCESS,
            pdf_file=self.canonical_pdf,
        )
        assert current is not None

        self.assertTrue(self.controller.handle_compile_result(self._result(3), current))
        self.assertEqual(target.read_bytes(), b"%PDF-1.4 successor-final")
        self.assertIsNone(self.controller.pending_for(self.root))

    def test_atomic_replace_failure_removes_staged_file(self) -> None:
        self._finish_current()
        target = self.directory / "submission.pdf"

        with patch(
            "app.gui.pdf_export_controller.os.replace",
            side_effect=OSError("replace denied"),
        ):
            self.assertFalse(self.controller.request_export(self.root, target))

        self.assertFalse(target.exists())
        self.assertEqual(list(self.directory.glob(".submission.pdf.*.part")), [])
        self.assertIn("replace denied", self.errors[-1])

    def test_failed_flush_or_missing_manager_does_not_leave_pending_request(self) -> None:
        self.documents.flush_results.append(False)
        target = self.directory / "submission.pdf"
        self.assertFalse(self.controller.request_export(self.root, target))
        self.assertIsNone(self.controller.pending_for(self.root))

        self.window.compile_managers.clear()
        self.assertFalse(self.controller.request_export(self.root, target))
        self.assertIsNone(self.controller.pending_for(self.root))

    def test_cancel_root_is_normalized_and_idempotent(self) -> None:
        self.store.mark_edited(self.root)
        self.assertTrue(
            self.controller.request_export(self.root, self.directory / "submission.pdf")
        )
        alias = self.directory / "subdir" / ".." / self.root.name
        self.assertTrue(self.controller.cancel_root(alias))
        self.assertFalse(self.controller.cancel_root(self.root))
