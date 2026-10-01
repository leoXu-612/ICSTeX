"""Synthetic build proofs test export orchestration; real LaTeX is checked separately."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import threading
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from app.core.build_evidence import capture_compile_inputs, finish_compile_inputs, final_build_evidence
from app.core.compiler import BuildPurpose, CompileJobKey, CompileOutcome, CompileResult
from app.core.pdf_state import PdfFreshness
from app.gui.main_window import MainWindow
from tests.test_gui_editor import isolated_settings


class PdfExportControllerTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.root = self.directory / "main.tex"
        self.root.write_text("\\documentclass{article}\n\\begin{document}Test\\end{document}\n")
        self.canonical_pdf = self.directory / ".latex_build/main.pdf"
        self.canonical_pdf.parent.mkdir()
        self.window = MainWindow(settings_store=isolated_settings())
        self.window.auto_compile_action.setChecked(False)
        self.window._watch_file = lambda _path: None
        self.window.project_files.set_project_root(self.directory)
        self.window.open_file(self.root)
        self.controller, self.store = self.window.pdf_export, self.window.pdf_state
        self.errors, self.statuses = [], []
        self.window.notify_pdf_export_error = self.errors.append
        self.window.notify_pdf_export_status = lambda message, _duration: self.statuses.append(message)
        self.compile_patch = patch.object(self.window.compile, "compile_current", return_value=True)
        self.compile = self.compile_patch.start()
        self.addCleanup(self.compile_patch.stop)
        self.addCleanup(self.dispose)
        self.wait(lambda: self.window.dependencies.memberships_current)

    def wait(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertTrue(predicate(), (self.errors, self.statuses))

    def dispose(self):
        self.controller.shutdown()
        self.wait(lambda: self.controller._publication is None)
        for tab in self.window.tabs.values():
            tab.modified = tab.dirty = False
            self.window.documents.cancel_save_timer(tab)
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def result(self, build_id, *, purpose=BuildPurpose.FINAL, outcome=CompileOutcome.SUCCESS):
        record = self.store.record_for(self.root)
        engine = self.window.compile._effective_engine_for(self.root, self.root)
        key = CompileJobKey(self.root, self.canonical_pdf.parent, purpose, engine,
                            self.window.toolchain, False, record.compile_revision or 0, 0)
        inputs = capture_compile_inputs(self.root, self.directory)
        evidence = finish_compile_inputs(inputs, self.root, self.directory, (), self.canonical_pdf)
        return CompileResult(self.root, self.canonical_pdf.parent, self.canonical_pdf,
            self.canonical_pdf.with_suffix(".log"), ["synthetic"], 0 if outcome is CompileOutcome.SUCCESS else 1,
            "", "", 0.01, outcome, build_id=build_id, purpose=purpose, job_key=key, input_evidence=evidence)

    def finish(self, build_id=1, payload=b"%PDF-1.4 synthetic fixture"):
        self.canonical_pdf.write_bytes(payload)
        result = self.result(build_id)
        record = self.store.finish_build(self.root, build_id, CompileOutcome.SUCCESS, pdf_file=self.canonical_pdf)
        self.window.compile._final_evidence[self.root] = final_build_evidence(result)
        return result, record

    def current(self):
        self.store.begin_build(self.root, 1)
        return self.finish()

    def test_current_exact_pdf_exports_without_compile_or_review(self):
        self.current()
        original = self.root.read_bytes()
        target = self.directory / "export.pdf"
        with patch.object(self.window, "prepare_submission", side_effect=AssertionError("not a submission review")):
            self.assertTrue(self.controller.request_export(self.root, target))
            self.wait(lambda: not self.controller._pending)
        self.assertEqual(target.read_bytes(), self.canonical_pdf.read_bytes())
        self.assertEqual(self.root.read_bytes(), original)
        self.compile.assert_not_called()
        self.assertEqual(self.errors, [])

    def export_once(self):
        self.current()
        target = self.directory / "export.pdf"
        self.assertTrue(self.controller.request_export(self.root, target))
        self.wait(lambda: not self.controller._pending)
        self.assertEqual(self.window.app_settings.pdf_export_target(self.root)[1].target, target)
        return target

    def compile_again(self, build_id=2, payload=b"%PDF-1.4 automatic update"):
        # Mirror the real compile entry's manager ownership; the engine result is synthetic.
        tab = self.window._tab_for_path(self.root)
        if tab.manager is None:
            tab.manager = self.window.create_compile_manager(self.root)
        self.store.mark_edited(self.root)
        self.store.begin_build(self.root, build_id)
        self.controller.handle_compile_started(self.root, build_id, BuildPurpose.FINAL)
        result, record = self.finish(build_id, payload)
        self.controller.handle_compile_result(result, record)
        return result, record

    def auto_idle(self):
        return not self.controller._automatic_results and not self.controller._pending

    def test_successive_final_builds_update_same_export_without_dialog_or_extra_compile(self):
        target = self.export_once()
        with patch("app.gui.pdf_export_controller.QFileDialog", side_effect=AssertionError("no picker")):
            for build_id in (2, 3):
                expected = f"%PDF-1.4 build {build_id}".encode()
                self.compile_again(build_id, expected)
                self.wait(self.auto_idle)
                self.assertEqual(target.read_bytes(), expected)
                self.assertEqual(self.window.app_settings.pdf_export_target(self.root)[1].target, target)
        self.compile.assert_not_called()
        self.assertEqual(self.errors, [])

    def test_preview_failure_and_stale_final_never_update_remembered_pdf(self):
        target = self.export_once()
        old = target.read_bytes()
        for purpose, outcome in ((BuildPurpose.PREVIEW, CompileOutcome.SUCCESS),
                                 (BuildPurpose.FINAL, CompileOutcome.LATEX_ERROR)):
            self.assertFalse(self.controller.handle_compile_result(
                self.result(1, purpose=purpose, outcome=outcome), self.store.record_for(self.root)))
        self.store.begin_build(self.root, 2)
        self.store.mark_edited(self.root)
        result, record = self.finish(2, b"%PDF-1.4 stale")
        self.assertFalse(self.controller.handle_compile_result(result, record))
        self.controller._poll()
        self.assertEqual(target.read_bytes(), old)
        self.assertTrue(self.auto_idle())

    def test_external_destination_change_is_kept_without_modal_error(self):
        target = self.export_once()
        target.write_bytes(b"Externally annotated PDF; keep this")
        self.compile_again()
        self.wait(self.auto_idle)
        self.assertEqual(target.read_bytes(), b"Externally annotated PDF; keep this")
        self.assertEqual(self.errors, [])
        self.assertIn("未更新 export.pdf", self.statuses[-1])

    def test_new_controller_loads_target_and_stop_action_disarms_it(self):
        from app.core.settings import AppSettings
        from app.gui.pdf_export_controller import PdfExportController
        from PySide6.QtCore import QSettings
        target = self.export_once()
        original_controller = self.controller
        original_controller.shutdown()
        self.window.app_settings = AppSettings(QSettings(
            self.window.app_settings.settings.fileName(), QSettings.Format.IniFormat))
        self.controller = self.window.pdf_export = PdfExportController(self.window)
        self.compile_again()
        self.wait(self.auto_idle)
        self.assertEqual(target.read_bytes(), self.canonical_pdf.read_bytes())
        self.assertTrue(self.window.stop_pdf_update_action.isEnabled())
        self.controller.stop_automatic()
        old = target.read_bytes()
        self.assertIsNone(self.window.app_settings.pdf_export_target(self.root))
        self.assertFalse(self.window.stop_pdf_update_action.isEnabled())
        self.compile_again(3, b"%PDF-1.4 not exported")
        self.controller._poll()
        self.assertEqual(target.read_bytes(), old)

    def test_exporting_to_new_location_moves_the_binding_only_after_success(self):
        first = self.export_once()
        second = self.directory / "another.pdf"
        self.controller.request_export(self.root, second)
        self.wait(lambda: not self.controller._pending)
        old = first.read_bytes()
        self.compile_again()
        self.wait(self.auto_idle)
        self.assertEqual(first.read_bytes(), old)
        self.assertEqual(second.read_bytes(), self.canonical_pdf.read_bytes())

    def test_background_root_updates_its_target_without_changing_active_tab(self):
        target = self.export_once()
        other = self.directory / "other.tex"
        other.write_text("\\documentclass{article}\\begin{document}Other\\end{document}")
        self.window.open_file(other)
        active = self.window.current_tab()
        self.wait(lambda: self.window.dependencies.memberships_current)
        statuses = list(self.statuses)
        self.compile_again()
        self.wait(self.auto_idle)
        self.assertIs(self.window.current_tab(), active)
        self.assertEqual(self.statuses, statuses)
        self.assertEqual(target.read_bytes(), self.canonical_pdf.read_bytes())
        self.assertIsNone(self.window.app_settings.pdf_export_target(other))

    def test_successor_build_replaces_queued_auto_update_and_rejects_old_callback(self):
        target = self.export_once()
        old, _ = self.compile_again(2)
        self.controller._queue_automatic()
        self.compile_again(3, b"%PDF-1.4 successor")
        self.controller.handle_compile_result(old, self.store.record_for(self.root))
        self.wait(self.auto_idle)
        self.assertEqual(target.read_bytes(), b"%PDF-1.4 successor")

    def test_manual_export_can_update_its_own_remembered_destination(self):
        target = self.export_once()
        self.store.begin_build(self.root, 2)
        self.finish(2, b"%PDF-1.4 manual update")
        self.assertTrue(self.controller.request_export(self.root, target))
        self.wait(lambda: not self.controller._pending)
        self.assertEqual(target.read_bytes(), b"%PDF-1.4 manual update")

    def test_auto_export_cancel_and_shutdown_keep_previous_output(self):
        target = self.export_once()
        old = target.read_bytes()
        self.compile_again()
        self.controller.cancel_root(self.root)
        self.controller._poll()
        self.assertEqual(target.read_bytes(), old)
        self.compile_again(3)
        self.controller.shutdown()
        self.controller._poll()
        self.assertEqual(target.read_bytes(), old)

    def test_stop_during_publication_does_not_rearm_after_late_success(self):
        from app.gui import pdf_export_controller as module
        target = self.export_once()
        entered, resume = threading.Event(), threading.Event()
        original = module.exported_pdf
        def paused(*args):
            receipt = original(*args)
            entered.set()  # Publication already succeeded; GUI callback has not arrived.
            resume.wait(3)
            return receipt
        with patch.object(module, "exported_pdf", side_effect=paused):
            try:
                self.compile_again()
                self.wait(entered.is_set)
                self.window.stop_pdf_update_action.trigger()
            finally:
                resume.set()
            self.wait(self.auto_idle)
        self.assertEqual(target.read_bytes(), self.canonical_pdf.read_bytes())
        self.assertIsNone(self.window.app_settings.pdf_export_target(self.root))
        self.assertIn("自动更新已停止", self.statuses[-1])

    def test_shared_settings_stop_is_not_undone_by_inflight_automatic_result(self):
        from app.gui import pdf_export_controller as module
        target = self.export_once()
        entered, resume = threading.Event(), threading.Event()
        original = module.exported_pdf
        def paused(*args):
            receipt = original(*args)
            entered.set()
            resume.wait(3)
            return receipt
        with patch.object(module, "exported_pdf", side_effect=paused):
            try:
                self.compile_again()
                self.wait(entered.is_set)
                # Other windows share this store but not the controller's local stop set.
                self.window.app_settings.forget_pdf_export(self.root)
            finally:
                resume.set()
            self.wait(self.auto_idle)
        self.assertEqual(target.read_bytes(), self.canonical_pdf.read_bytes())
        self.assertIsNone(self.window.app_settings.pdf_export_target(self.root))

    def test_picker_cancel_does_not_save_compile_or_export(self):
        self.current()
        tab = self.window.current_tab()
        tab.editor.insertPlainText("new")
        before = self.root.read_bytes()
        with patch("app.gui.pdf_export_controller.QFileDialog") as picker:
            picker.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.assertFalse(self.window.export_pdf())
        self.compile.assert_not_called()
        self.assertEqual(self.root.read_bytes(), before)
        self.assertTrue(tab.modified)
        self.assertFalse((self.directory / "main.pdf").exists())

    def test_one_picker_accepts_update_export_and_avoids_existing_default_name(self):
        self.current()
        existing = self.directory / "main.pdf"
        existing.write_bytes(b"keep previous export")
        target = self.directory / "main-2.pdf"
        with patch("app.gui.pdf_export_controller.QFileDialog") as picker:
            picker.return_value.exec.return_value = QDialog.DialogCode.Accepted
            picker.return_value.selectedFiles.return_value = [str(target)]
            self.assertTrue(self.window.export_pdf())
            self.assertEqual(picker.call_args.args[2], str(target))
            picker.return_value.setLabelText.assert_called_once_with(
                picker.DialogLabel.Accept, "更新并导出")
            self.wait(lambda: not self.controller._pending)
        self.assertEqual(existing.read_bytes(), b"keep previous export")
        self.assertEqual(target.read_bytes(), self.canonical_pdf.read_bytes())

    def test_dirty_final_queues_once_and_ignores_preview_and_old_final(self):
        self.current()
        self.store.mark_edited(self.root)
        self.store.begin_build(self.root, 2)  # Already running before the export request.
        target = self.directory / "export.pdf"
        self.assertTrue(self.controller.request_export(self.root, target))
        self.compile.assert_called_once()
        self.assertEqual(self.compile.call_args.kwargs["purpose"], BuildPurpose.FINAL)
        self.assertFalse(self.controller.handle_compile_result(self.result(2), self.store.record_for(self.root)))
        self.assertFalse(self.controller.handle_compile_started(self.root, 3, BuildPurpose.PREVIEW))
        self.assertFalse(self.controller.handle_compile_result(self.result(3, purpose=BuildPurpose.PREVIEW),
                                                               self.store.record_for(self.root)))
        self.assertFalse(target.exists())
        self.store.begin_build(self.root, 4)
        self.controller.handle_compile_started(self.root, 4, BuildPurpose.FINAL)
        result, record = self.finish(4, b"%PDF-1.4 newest")
        self.assertTrue(self.controller.handle_compile_result(result, record))
        self.wait(lambda: not self.controller._pending)
        self.assertEqual(target.read_bytes(), b"%PDF-1.4 newest")

    def test_edit_during_compile_requires_successor_and_never_exports_stale_result(self):
        self.current()
        self.store.mark_edited(self.root)
        target = self.directory / "export.pdf"
        self.controller.request_export(self.root, target)
        self.store.begin_build(self.root, 2)
        self.controller.handle_compile_started(self.root, 2, BuildPurpose.FINAL)
        self.store.mark_edited(self.root)
        result, record = self.finish(2, b"%PDF-1.4 stale")
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)
        self.controller.handle_compile_result(result, record)
        self.assertEqual(self.compile.call_count, 2)
        self.assertFalse(target.exists())
        self.store.begin_build(self.root, 3)
        self.controller.handle_compile_started(self.root, 3, BuildPurpose.FINAL)
        result, record = self.finish(3, b"%PDF-1.4 current")
        self.controller.handle_compile_result(result, record)
        self.wait(lambda: not self.controller._pending)
        self.assertEqual(target.read_bytes(), b"%PDF-1.4 current")

    def test_failed_update_exports_nothing_and_keeps_old_pdf(self):
        self.current()
        old = self.canonical_pdf.read_bytes()
        self.store.mark_edited(self.root)
        target = self.directory / "export.pdf"
        self.controller.request_export(self.root, target)
        self.controller.handle_compile_started(self.root, 2, BuildPurpose.FINAL)
        failed = self.result(2, outcome=CompileOutcome.LATEX_ERROR)
        self.controller.handle_compile_result(failed, self.store.record_for(self.root))
        self.assertFalse(target.exists())
        self.assertEqual(self.canonical_pdf.read_bytes(), old)
        self.assertFalse(self.controller._pending)
        self.assertIn("未导出旧版本", self.errors[-1])

    def test_nonempty_pdf_record_without_real_evidence_requires_update(self):
        self.current()
        self.window.compile._final_evidence.clear()
        target = self.directory / "export.pdf"
        self.assertTrue(self.controller.request_export(self.root, target))
        self.compile.assert_called_once()
        self.assertFalse(target.exists())

    def test_existing_destination_and_failed_compile_request_are_preserved(self):
        self.current()
        target = self.directory / "existing.pdf"
        target.write_bytes(b"original")
        self.assertFalse(self.controller.request_export(self.root, target))
        self.assertEqual(target.read_bytes(), b"original")
        self.store.mark_edited(self.root)
        self.compile.return_value = False
        self.assertFalse(self.controller.request_export(self.root, self.directory / "new.pdf"))
        self.assertFalse(self.controller._pending)

    def test_failed_deferred_compile_cancels_the_waiting_export(self):
        self.current()
        self.store.mark_edited(self.root)
        target = self.directory / "export.pdf"
        self.controller.request_export(self.root, target)
        tab = self.window.current_tab()
        self.window.compile._deferred_dependencies[self.root] = (
            id(tab.editor), self.window.selected_project_scope, BuildPurpose.FINAL,
            True, False, True, "test export", False)
        self.compile.return_value = False
        self.window.compile.resume_dependencies()
        self.assertFalse(self.controller._pending)
        self.assertFalse(target.exists())

    def test_changed_disk_pdf_or_source_refuses_publication(self):
        for changed in (self.root, self.canonical_pdf):
            with self.subTest(changed=changed):
                self.root.write_text("\\documentclass{article}\n\\begin{document}Test\\end{document}\n")
                self.current()
                changed.write_bytes(changed.read_bytes() + b" changed")
                target = self.directory / "export.pdf"
                self.assertTrue(self.controller.request_export(self.root, target))
                self.wait(lambda: not self.controller._pending)
                self.assertFalse(target.exists())

    def test_cancel_and_scope_switch_do_not_leave_an_export(self):
        self.current()
        self.store.mark_edited(self.root)
        target = self.directory / "export.pdf"
        self.controller.request_export(self.root, target)
        alias = self.directory / "subdir/../main.tex"
        self.assertTrue(self.controller.cancel_root(alias))
        self.assertFalse(self.controller.cancel_root(self.root))
        self.controller.request_export(self.root, target)
        context = self.window.readiness._context()
        with patch.object(self.window.readiness, "_context",
                          return_value=(*context[:2], self.directory / "other.tex", *context[3:])):
            self.controller._poll()
        self.assertFalse(target.exists())
        self.assertFalse(self.controller._pending)

    def test_exclusive_publication_failure_cleans_staging(self):
        self.current()
        target = self.directory / "export.pdf"
        with patch("app.core.project_checkpoint._OutputParent.publish_file", side_effect=OSError("test denied")):
            self.controller.request_export(self.root, target)
            self.wait(lambda: not self.controller._pending)
        self.assertFalse(target.exists())
        self.assertEqual(list(self.directory.glob(".icstex-export.incomplete-*")), [])
        self.assertTrue(self.errors)

    def test_cancel_during_worker_blocks_reentry_until_cleanup(self):
        from app.gui import pdf_export_controller as module
        self.current()
        entered, resume = threading.Event(), threading.Event()
        publish = module.publish_exact_file
        def paused(*args, **kwargs):
            entered.set()
            resume.wait(3)
            return publish(*args, **kwargs)
        target = self.directory / "export.pdf"
        with patch.object(module, "publish_exact_file", side_effect=paused):
            try:
                self.controller.request_export(self.root, target)
                self.wait(entered.is_set)
                self.controller.cancel_root(self.root)
                self.assertFalse(self.controller.request_export(self.root, self.directory / "second.pdf"))
            finally:
                resume.set()
            self.wait(lambda: self.controller._publication is None)
        self.assertFalse(target.exists())
        self.assertFalse(self.controller._pending)

    def test_another_windows_unsaved_draft_is_not_silently_saved_or_exported(self):
        self.current()
        other = MainWindow(settings_store=isolated_settings())
        other.auto_compile_action.setChecked(False)
        other.save_debounce_ms = 3600000
        other.open_file(self.root)
        tab = other.current_tab()
        tab.editor.insertPlainText("UNSAVED")
        original = self.root.read_bytes()
        try:
            target = self.directory / "export.pdf"
            self.controller.request_export(self.root, target)
            self.wait(lambda: not self.controller._pending)
            self.assertFalse(target.exists())
            self.assertEqual(self.root.read_bytes(), original)
            self.assertTrue(tab.modified)
        finally:
            other.documents.cancel_save_timer(tab)
            tab.dirty = tab.modified = False
            other.close()
            other.deleteLater()
