"""Widget/ownership checks with synthetic build evidence; real FINAL is a separate probe."""
from dataclasses import replace
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
import time
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.latex_tools import LaTeXToolchain
from app.core.pdf_state import PdfBuildRecord, PdfFreshness
from app.gui.main_window import MainWindow
from app.gui.project_checkpoint_dialog import checkpoint_close_guard
from app.gui.submission_delivery_dialog import SubmissionDeliveryDialog
from tests.test_gui_editor import isolated_settings
from tests.test_submission_check import request_for
from tests.v1_fixtures import create_project


class SubmissionDeliveryGuiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-delivery-gui-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.sample = create_project(self.home)
        self.project = self.sample.root.parent
        self.pdf = self.project / ".latex_build/main.pdf"
        self.pdf.parent.mkdir()
        self.pdf.write_bytes(b"%PDF-1.4 synthetic unit evidence")
        record = PdfBuildRecord(self.sample.root, PdfFreshness.CURRENT, self.pdf, 4, 4, 4, 7)
        request = request_for(self.sample, final=record)
        tools = LaTeXToolchain(None, sys.executable)
        self.request = replace(request, tools=tools,
            build_evidence=replace(request.build_evidence, job_key=replace(request.build_evidence.job_key, toolchain=tools)))
        self.window = MainWindow(settings_store=isolated_settings())
        self.window.save_debounce_ms = 3600000
        self.window.project_files.set_project_root(self.project)
        self.window.open_file(self.sample.root)
        self.windows = [self.window]
        self.block_windows = []
        # Only tests supply synthetic evidence. Product probes use the actual
        # controller capture and real asynchronous FINAL, not this seam.
        self.capture = patch.object(self.window.readiness, "capture_request", side_effect=lambda:
            replace(self.request, key=self.window.readiness._context()[0]))
        self.capture.start()
        self.dialog = SubmissionDeliveryDialog(self.window)
        self.app._icstex_delivery_dialog = self.dialog
        self.addCleanup(self.dispose)

    def wait(self, condition, seconds=10):
        until = time.monotonic() + seconds
        while not condition() and time.monotonic() < until:
            self.app.processEvents()
            time.sleep(0.003)
        self.assertTrue(condition(), self.dialog.status.text())

    def dispose(self):
        self.dialog.cancel.set()
        self.wait(lambda: not self.dialog.busy)
        self.dialog.reject()
        self.app._icstex_delivery_dialog = None
        self.dialog.deleteLater()
        self.capture.stop()
        for window in self.windows:
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            window.close()
            window.deleteLater()
        for window in self.block_windows:
            window.session.editor_drafts.clear()
            window.session._dirty = False
            window.close()
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def review(self):
        self.dialog.inspect()
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNotNone(self.dialog.prepared, self.dialog.status.text())
        self.dialog.target.setText(str(self.home / "delivered"))

    def publish(self):
        self.dialog.acknowledge.setChecked(True)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.dialog.perform()
        self.wait(lambda: not self.dialog.busy)

    def test_stage_navigation_preserves_frozen_authority_and_unknown_gate(self):
        dialog = self.dialog
        dialog.show()
        self.assertIs(dialog.pages.currentWidget(), dialog.prepare_page)
        self.assertTrue(dialog.review_button.isVisible())
        self.assertFalse(dialog.target.isVisible())
        self.assertFalse(dialog.action_button.isVisible())
        self.review()
        frozen, lease = dialog.prepared, dialog.lease
        self.assertIs(dialog.pages.currentWidget(), dialog.review_page)
        self.assertFalse(dialog.save_button.isVisible())
        self.assertFalse(dialog.continue_button.isEnabled())
        dialog.continue_to_target()
        self.assertIs(dialog.pages.currentWidget(), dialog.review_page)
        dialog.acknowledge.setChecked(True)
        dialog.continue_button.click()
        self.assertIs(dialog.pages.currentWidget(), dialog.target_page)
        self.assertTrue(dialog.action_button.isVisible())
        self.assertFalse(dialog.review_button.isVisible())
        dialog.back_button.click()
        self.assertIs(dialog.prepared, frozen)
        self.assertIs(dialog.lease, lease)
        self.assertTrue(dialog.acknowledge.isChecked())
        dialog.back_button.click()
        self.assertIs(dialog.pages.currentWidget(), dialog.prepare_page)
        dialog.pdf_name.setText("changed.pdf")
        self.assertIsNone(dialog.prepared)
        self.assertIsNone(dialog.lease)
        self.assertIn("内容尚未固定", dialog.status.text())

    def test_source_clear_is_only_shown_for_source_preparation(self):
        dialog = self.dialog
        dialog.show()
        self.assertFalse(dialog.clear_button.isVisible())
        dialog.include_source.setChecked(True)
        self.wait(lambda: not dialog.busy)
        self.assertTrue(dialog.clear_button.isVisible())
        dialog.select_button.click()
        self.assertTrue(dialog.options().source_paths)
        dialog.clear_button.click()
        self.assertEqual(dialog.options().source_paths, ())
        dialog.select_button.click()
        self.review()
        self.assertFalse(dialog.clear_button.isVisible())

    def test_technical_details_keep_full_identity_and_pdf_preview_is_not_live(self):
        import hashlib
        self.review()
        dialog = self.dialog
        dialog.outputs.setCurrentItem(dialog.outputs.topLevelItem(0))
        details = dialog.technical.toPlainText()
        self.assertIn(dialog.report.input_id, details)
        self.assertIn(str(self.project), details)
        self.assertIn(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), details)
        self.assertNotIn("主窗口", dialog.preview.toPlainText())
        self.assertIn("不预览版面", dialog.preview.toPlainText())

    def test_success_uses_actual_directory_and_open_is_explicit(self):
        from PySide6.QtGui import QDesktopServices
        self.review()
        with patch.object(QDesktopServices, "openUrl", return_value=True) as opened:
            self.publish()
            dialog = self.dialog
            self.assertIs(dialog.pages.currentWidget(), dialog.success_page)
            self.assertIn(str(dialog.result), dialog.success_details.toPlainText())
            self.assertIn("main.pdf", dialog.success_details.toPlainText())
            opened.assert_not_called()
            dialog.open_button.click()
            opened.assert_called_once()
            self.assertEqual(opened.call_args.args[0].toLocalFile(), str(dialog.result))
            with patch("app.gui.submission_delivery_dialog.publish_submission") as publish:
                dialog.perform()
                publish.assert_not_called()

    def test_navigation_and_technical_expansion_do_not_rehash_payloads(self):
        self.review()
        dialog = self.dialog
        with patch("app.gui.submission_delivery_dialog.hashlib.sha256", side_effect=AssertionError("Unexpected rehash")):
            dialog.technical_button.click()
            dialog.technical_button.click()
            dialog.previous_stage()
            dialog.show_technical(True)
        self.assertIsNotNone(dialog.prepared)

    def test_repeated_publish_clicks_start_only_one_existing_transaction(self):
        from app.gui import submission_delivery_dialog as module
        self.review()
        self.dialog.acknowledge.setChecked(True)
        self.dialog.continue_button.click()
        entered, finish = threading.Event(), threading.Event()
        original = module.publish_submission

        def held(*args, **kwargs):
            entered.set()
            finish.wait(5)
            return original(*args, **kwargs)

        try:
            with patch.object(module, "publish_submission", side_effect=held) as publish, \
                    patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                self.dialog.action_button.click()
                self.wait(entered.is_set)
                self.dialog.action_button.click()
                self.dialog.perform()
                self.assertEqual(publish.call_count, 1)
                self.assertFalse(self.dialog.back_button.isEnabled())
                finish.set()
                self.wait(lambda: not self.dialog.busy)
            self.assertIsNotNone(self.dialog.result, self.dialog.status.text())
        finally:
            finish.set()

    def test_open_and_review_do_not_save_or_compile_default_only_pdf(self):
        self.assertFalse(self.dialog.include_source.isChecked())
        self.assertFalse(self.dialog.include_report.isChecked())
        with patch.object(self.window.documents, "flush_root_documents") as save, patch.object(
                self.window.compile_action, "trigger") as compile:
            self.review()
            save.assert_not_called()
            compile.assert_not_called()
        self.assertTrue(self.dialog.lease)
        self.assertFalse(self.dialog.action_button.isEnabled())
        self.assertEqual([p for p, _ in self.dialog.payloads], ["main.pdf"])
        self.publish()
        self.assertEqual(self.dialog.result, self.home / "delivered", self.dialog.status.text())
        self.assertEqual([p.name for p in self.dialog.result.iterdir()], ["main.pdf"])
        self.assertEqual((self.dialog.result / "main.pdf").read_bytes(), self.pdf.read_bytes())
        self.assertIsNone(self.dialog.lease)

    def test_probe_waits_for_confirmation_call_return_before_publish_assertion(self):
        from PySide6.QtTest import QTest
        from tools.probe_submission_delivery_gui import drive

        output = self.home / "probe-evidence"
        output.mkdir()
        target = self.home / "probe-delivery"
        question = QMessageBox.question

        def delayed_return(*args, **kwargs):
            answer = question(*args, **kwargs)
            # Fault injection: native nested-loop events can run after the
            # message box hides but before the action handler receives Yes.
            # The probe must not assert publication at this intermediate point.
            QTest.qWait(75)
            return answer

        def new_proof():
            self.request = replace(self.request, build_evidence=replace(self.request.build_evidence))

        with patch.object(self.window.prepare_submission_action, "trigger", side_effect=self.dialog.exec), \
             patch.object(self.window.compile_action, "trigger", side_effect=new_proof), \
             patch.object(self.window.compile, "final_evidence_for", side_effect=lambda _root: self.request.build_evidence), \
             patch.object(QMessageBox, "question", side_effect=delayed_return):
            result = drive(self.window, target, output, "confirmation-return")
        self.assertEqual(result["files"], 1)
        self.assertEqual((target / "main.pdf").read_bytes(), self.pdf.read_bytes())

    def test_sources_explicit_preview_bytes_match_publication_including_original_readme(self):
        (self.project / "README.md").write_bytes(b"Original user instructions\r\n")
        (self.project / "encoded.tex").write_bytes(b"% \x81\xff\r\n")
        self.dialog.include_source.setChecked(True)
        self.wait(lambda: not self.dialog.busy)
        self.assertTrue(self.dialog.inventory_loaded)
        self.assertEqual(self.dialog.options().source_paths, ())
        self.dialog.select_all()
        self.dialog.include_report.setChecked(True)
        self.review()
        outputs = dict(self.dialog.payloads)
        self.assertIn("source/README.md", outputs)
        self.assertEqual(outputs["source/README.md"], b"Original user instructions\r\n")
        item = next(self.dialog.outputs.topLevelItem(i) for i in range(self.dialog.outputs.topLevelItemCount())
                    if self.dialog.outputs.topLevelItem(i).text(0) == "source/encoded.tex")
        self.dialog.outputs.setCurrentItem(item)
        self.assertIn("81 ff", self.dialog.preview.toPlainText())
        self.assertNotIn(str(self.home).encode(), outputs["submission-report.json"])
        self.publish()
        self.assertIsNotNone(self.dialog.result, self.dialog.status.text())
        for path, raw in outputs.items():
            self.assertEqual((self.dialog.result / path).read_bytes(), raw)

    def test_confirmation_defaults_no_cancel_and_changed_target_never_publish(self):
        self.review()
        self.dialog.acknowledge.setChecked(True)
        def no(*args):
            self.assertEqual(args[-1], QMessageBox.StandardButton.No)
            return QMessageBox.StandardButton.No
        with patch.object(QMessageBox, "question", side_effect=no):
            self.dialog.perform()
        self.assertIsNone(self.dialog.result)
        self.assertFalse((self.home / "delivered").exists())
        def change(*args):
            self.dialog.target.setText(str(self.home / "changed-target"))
            return QMessageBox.StandardButton.Yes
        with patch.object(QMessageBox, "question", side_effect=change):
            self.dialog.perform()
        self.assertIn("选择变化", self.dialog.status.text())
        self.assertFalse((self.home / "changed-target").exists())

    def test_dirty_current_or_other_project_window_buffer_refuses_without_saving(self):
        other = MainWindow(settings_store=isolated_settings())
        self.windows.append(other)
        other.save_debounce_ms = 3600000
        other.project_files.set_project_root(self.project)
        other.open_file(self.sample.draft_path)
        before = self.sample.draft_path.read_bytes()
        other.current_tab().editor.appendPlainText("% unsaved competing window")
        self.dialog.inspect()
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNone(self.dialog.prepared)
        self.assertIn("尚不能交付", self.dialog.status.text())
        self.assertEqual(self.sample.draft_path.read_bytes(), before)
        self.assertIn("unsaved competing", other.current_tab().editor.toPlainText())

    def test_change_after_review_invalidates_lease_and_requires_new_capture(self):
        self.review()
        self.window.current_tab().editor.appendPlainText("% newer unsaved input")
        self.dialog.poll()
        self.assertIsNone(self.dialog.prepared)
        self.assertIsNone(self.dialog.lease)
        self.assertFalse(self.dialog.action_button.isEnabled())
        self.assertNotIn(b"newer unsaved", self.sample.root.read_bytes())

    def test_pdf_option_change_discards_review_and_releases_save_hold(self):
        self.review()
        self.assertTrue(self.window.documents.checkpoint_tabs)
        self.dialog.include_report.setChecked(True)
        self.assertIsNone(self.dialog.prepared)
        self.assertFalse(self.window.documents.checkpoint_tabs)
        self.assertFalse(self.dialog.action_button.isEnabled())

    def test_actual_snapshot_without_final_evidence_never_accepts_cached_pdf_record(self):
        self.capture.stop()
        self.window.pdf_state.begin_build(self.sample.root, 1)
        self.window.pdf_state.finish_build(self.sample.root, 1, self.request.build_evidence.outcome, pdf_file=self.pdf)
        self.dialog.inspect()
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNone(self.dialog.prepared)
        self.assertFalse(self.dialog.action_button.isEnabled())
        self.assertTrue(self.dialog.report)
        self.assertFalse((self.home / "delivered").exists())

    def test_actual_publication_disk_failure_preserves_old_delivery_and_requires_new_review(self):
        from app.core import project_checkpoint
        self.review()
        old = self.home / "older-delivery"
        old.mkdir()
        (old / "main.pdf").write_bytes(b"Previous success")
        with patch.object(project_checkpoint, "_write_restored", side_effect=OSError("disk full")):
            self.publish()
        self.assertIsNone(self.dialog.result)
        self.assertIsNone(self.dialog.prepared)
        self.assertIsNone(self.dialog.lease)
        self.assertFalse(self.dialog.action_button.isEnabled())
        self.assertFalse((self.home / "delivered").exists())
        self.assertEqual((old / "main.pdf").read_bytes(), b"Previous success")

    def test_same_mtime_external_child_change_during_confirmation_refuses_actual_publish(self):
        self.review()
        self.dialog.acknowledge.setChecked(True)
        def change(*args):
            stat = self.sample.draft_path.stat()
            self.sample.draft_path.write_bytes(b"External winner\r\n")
            os.utime(self.sample.draft_path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            return QMessageBox.StandardButton.Yes
        with patch.object(QMessageBox, "question", side_effect=change):
            self.dialog.perform()
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNone(self.dialog.result)
        self.assertFalse((self.home / "delivered").exists())
        self.assertEqual(self.sample.draft_path.read_bytes(), b"External winner\r\n")

    def test_new_final_or_changed_root_invalidates_review(self):
        self.review()
        other = create_project(self.home / "second", "single")
        self.window.project_files.set_project_root(other.root.parent)
        self.window.open_file(other.root)
        self.dialog.poll()
        self.assertIsNone(self.dialog.prepared)
        with patch.object(self.window.documents, "flush_root_documents") as save:
            self.dialog.save_inputs()
            save.assert_not_called()

    def test_save_compile_are_explicit_use_existing_actions_and_release_hold(self):
        self.review()
        def saved(root):
            self.assertFalse(self.window.documents.checkpoint_tabs)
            self.assertEqual(root, self.sample.root)
            return True
        with patch.object(self.window.documents, "flush_root_documents", side_effect=saved) as save:
            self.dialog.save_inputs()
            self.wait(lambda: save.called)
            save.assert_called_once()
        self.assertIsNone(self.dialog.prepared)
        with patch.object(self.window.compile_action, "trigger") as compile:
            self.dialog.compile_final()
            compile.assert_called_once()
        self.assertIsNone(self.dialog.prepared)

    def test_cancel_dialog_cancels_save_waiting_for_membership(self):
        from app.gui import dependency_controller
        original = dependency_controller.calculate_memberships
        entered, release = threading.Event(), threading.Event()
        raw = self.sample.root.read_bytes()
        tab = self.window.current_tab()
        tab.editor.insertPlainText("% unsaved test draft\n")

        def held(*args, **kwargs):
            entered.set()
            release.wait(3)
            return original(*args, **kwargs)

        try:
            with patch.object(dependency_controller, "calculate_memberships", side_effect=held):
                self.dialog.save_inputs()
                self.wait(entered.is_set)
                self.assertTrue(self.window.documents.root_save_pending)
                self.dialog.reject()
                release.set()
                self.wait(lambda: not self.window.dependencies.is_busy)
                self.app.processEvents()
            self.assertEqual(self.sample.root.read_bytes(), raw)
            self.assertTrue(tab.modified)
        finally:
            release.set()

    def test_owner_close_cancels_worker_and_no_second_worker_can_start(self):
        entered, finish = threading.Event(), threading.Event()
        from app.gui import submission_delivery_dialog as module
        real = module._prepare
        def held(*args):
            entered.set()
            finish.wait(5)
            return real(*args)
        with patch.object(module, "_prepare", side_effect=held) as work:
            self.dialog.inspect()
            self.wait(entered.is_set)
            self.dialog.inspect()
            self.assertEqual(work.call_count, 1)
            self.assertFalse(checkpoint_close_guard(self.window))
            self.assertTrue(self.dialog.closing)
            finish.set()
            self.wait(lambda: not self.dialog.busy)
        self.assertIsNone(self.dialog.lease)
        self.assertFalse((self.home / "delivered").exists())

    def test_publication_winning_cancel_is_reported_and_not_republished(self):
        from app.core import project_checkpoint
        self.review()
        original = project_checkpoint._rename_directory_exclusive
        def publish(*args):
            original(*args)
            self.dialog.cancel.set()
        with patch.object(project_checkpoint, "_rename_directory_exclusive", side_effect=publish):
            self.publish()
        self.assertIsNotNone(self.dialog.result, self.dialog.status.text())
        self.assertIn("已生成交付", self.dialog.status.text())
        self.assertFalse(self.dialog.action_button.isEnabled())

    def test_file_and_pdf_entrypoints_use_same_review_not_legacy_copy(self):
        from app.gui import submission_delivery_dialog
        with patch.object(submission_delivery_dialog, "show_submission_delivery", return_value=self.home / "out") as show:
            self.window.prepare_submission_action.trigger()
            self.window.pdf_state.begin_build(self.sample.root, 1)
            self.window.pdf_state.finish_build(self.sample.root, 1, self.request.build_evidence.outcome, pdf_file=self.pdf)
            self.assertTrue(self.window.export_pdf())
            self.assertEqual(show.call_count, 2)
        self.assertFalse((self.home / "out").exists())

    def standalone(self):
        from app.core.blocks.project_repository import load_project
        from app.gui.blocks.project_dialog import BlockProjectDialog
        sample = create_project(self.home, "block")
        loaded = load_project(sample.root.parent)
        owner = BlockProjectDialog(registry=loaded["registry"], layout=loaded["layout"],
            document_theme=loaded["document_theme"], project_dir=loaded["project_dir"])
        self.block_windows.append(owner)
        self.dialog.reject()
        self.dialog.deleteLater()
        self.dialog = SubmissionDeliveryDialog(owner, session=owner.session)
        self.app._icstex_delivery_dialog = self.dialog
        return owner

    def test_standalone_block_has_real_snapshot_and_protected_explicit_actions(self):
        from app.gui import submission_delivery_dialog as module
        owner = self.standalone()
        snapshot = self.dialog._snapshot()
        self.assertEqual(snapshot.scope, owner.session.project_dir)
        self.assertIsNotNone(snapshot.block)
        self.assertIsNone(snapshot.build_evidence)
        with patch.object(module, "save_block_session") as save, patch.object(module, "compile_block_session") as compile:
            self.dialog.save_inputs()
            self.dialog.compile_final()
            save.assert_called_once_with(self.dialog, owner.session)
            compile.assert_called_once_with(self.dialog, owner.session)
        self.dialog.inspect()
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNone(self.dialog.prepared, "No actual FINAL must not become a valid delivery")
        self.assertFalse(owner.session._compile_authorized)
        with patch.object(module, "show_submission_delivery") as show:
            owner.workspace.delivery_button.click()
            show.assert_called_once_with(owner, session=owner.session)

    def test_standalone_close_waits_for_cancelled_worker_and_releases_shared_pause(self):
        from app.gui import submission_delivery_dialog as module
        owner = self.standalone()
        entered, finish = threading.Event(), threading.Event()
        def held(*args):
            entered.set()
            finish.wait(5)
            raise OSError("Cancelled synthetic read")
        with patch.object(module, "_prepare", side_effect=held):
            self.dialog.inspect()
            self.wait(entered.is_set)
            self.assertTrue(owner.session._checkpoint_paused)
            owner.reject()
            self.assertFalse(owner.session._closed)
            self.assertTrue(self.dialog.cancel.is_set())
            finish.set()
            self.wait(lambda: not self.dialog.busy)
        self.assertFalse(owner.session._checkpoint_paused)
        self.assertFalse(owner.session._closed)
