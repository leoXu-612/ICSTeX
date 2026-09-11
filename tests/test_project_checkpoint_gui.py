import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.project_checkpoint import create_checkpoint, restore_checkpoint, inspect_checkpoint
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.property_draft import PropertyDraft
from app.gui.blocks.project_session import ProjectSession
from app.gui.block_mode import _install_session
from app.gui.project_checkpoint_dialog import CaptureLease, ProjectCheckpointDialog, checkpoint_close_guard
from app.gui.main_window import MainWindow
from tests.test_gui_editor import isolated_settings


class ProjectCheckpointGuiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-checkpoint-gui-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.project = self.home / "项目"
        self.project.mkdir()
        self.source = self.project / "main.tex"
        self.original = b"\\documentclass{article}\r\n\\begin{document}Saved\\end{document}\r\n"
        self.source.write_bytes(self.original)
        self.window = MainWindow(settings_store=isolated_settings())
        self.window.save_debounce_ms = 3600000
        self.window.auto_compile_action.setChecked(False)
        self.window._watch_file = lambda _: None
        self.window.open_file(self.source)
        self.tab = self.window.current_tab()
        self.dialogs = []
        self.addCleanup(self.dispose)

    def wait(self, condition):
        until = time.monotonic() + 6
        while not condition() and time.monotonic() < until:
            self.app.processEvents()
            time.sleep(0.003)
        self.assertTrue(condition())

    def dialog(self, restore=False):
        dialog = ProjectCheckpointDialog(self.window, restore=restore)
        self.dialogs.append(dialog)
        self.wait(lambda: not dialog.busy)
        return dialog

    def dispose(self):
        self.app._icstex_checkpoint_dialog = None
        for dialog in self.dialogs:
            dialog.cancel.set()
            self.wait(lambda: not dialog.busy)
            dialog.reject()
            dialog.deleteLater()
        session = getattr(self.window, "block_session", None)
        if session:
            session._dirty = False
            session.editor_drafts.clear()
        for tab in self.window.tabs.values():
            self.window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_live_source_draft_and_raw_disk_bytes_are_independently_recovered(self):
        self.tab.editor.appendPlainText("未保存草稿")
        draft = self.tab.editor.toPlainText()
        self.assertTrue(self.tab.save_timer.isActive())
        dialog = self.dialog()
        self.assertFalse(self.tab.save_timer.isActive())
        self.assertFalse(self.window.documents.flush_pending_save(self.tab))
        path = self.home / "saved.icstex-checkpoint"
        dialog.target.setText(str(path))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.perform()
        self.wait(lambda: not dialog.busy)
        self.assertTrue(path.exists(), dialog.status.text())
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(self.tab.editor.toPlainText(), draft)
        self.assertFalse(self.window.compile_authorized_roots)
        info = inspect_checkpoint(path)
        self.assertEqual(len(info.drafts), 1)
        result = restore_checkpoint(path, self.home / "restored")
        self.assertEqual((result.project_dir / "main.tex").read_bytes(), self.original)
        self.assertEqual((result.drafts_dir / (info.drafts[0].id + ".txt")).read_text(), draft)
        dialog.reject()
        self.assertTrue(self.tab.save_timer.isActive())
        self.assertFalse(self.window.documents.checkpoint_tabs)

    def test_cancel_confirmation_and_changed_editor_leave_no_checkpoint(self):
        self.tab.editor.appendPlainText("draft")
        dialog = self.dialog()
        path = self.home / "cancelled.icstex-checkpoint"
        dialog.target.setText(str(path))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            dialog.perform()
        self.assertFalse(path.exists())
        self.tab.editor.appendPlainText("newer draft")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.perform()
        self.assertFalse(path.exists())
        self.assertEqual(self.source.read_bytes(), self.original)
        dialog.reject()
        self.assertFalse(self.tab.save_timer.isActive())
        self.assertIn("newer draft", self.tab.editor.toPlainText())

    def test_signal_blocked_external_reload_cancels_capture_and_stops_auto_compile(self):
        self.window.auto_compile_action.setChecked(True)
        self.window.compile_authorized_roots.add(self.source)
        self.tab.manager = self.window.create_compile_manager(self.source)
        dialog = self.dialog()
        self.source.write_bytes(self.original.replace(b"Saved", b"External"))
        with patch.object(self.tab.manager, "schedule_compile") as scheduled:
            self.window.documents.reload_external_change(str(self.source))
        self.assertTrue(dialog.cancel.is_set())
        self.assertEqual(scheduled.call_count, 0)

    def test_restore_ui_rejects_archive_changed_after_review_and_existing_target(self):
        path = self.home / "reviewed.icstex-checkpoint"
        create_checkpoint(self.project, ["main.tex"], path)
        dialog = self.dialog(restore=True)
        dialog.load_archive(path)
        self.wait(lambda: not dialog.busy)
        old_info = dialog.info
        path.unlink()
        self.source.write_bytes(b"newer external source")
        create_checkpoint(self.project, ["main.tex"], path)
        target = self.home / "not-restored"
        dialog.target.setText(str(target))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.perform()
        self.wait(lambda: not dialog.busy)
        self.assertFalse(target.exists())
        self.assertIn("changed since review", dialog.status.text())
        self.assertEqual(dialog.info, old_info)
        dialog.load_archive(path)
        self.wait(lambda: not dialog.busy)
        target.mkdir()
        (target / "sentinel").write_text("keep")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.perform()
        self.wait(lambda: not dialog.busy)
        self.assertEqual((target / "sentinel").read_text(), "keep")

    def test_actual_restore_dialog_preserves_current_project_and_reports_draft_location(self):
        path = self.home / "input.icstex-checkpoint"
        create_checkpoint(self.project, ["main.tex"], path)
        dialog = self.dialog(restore=True)
        dialog.load_archive(path)
        self.wait(lambda: not dialog.busy)
        target = self.home / "恢复目录"
        dialog.target.setText(str(target))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.perform()
        self.wait(lambda: not dialog.busy)
        self.assertEqual((target / "project/main.tex").read_bytes(), self.original)
        self.assertEqual(self.window.current_tab(), self.tab)
        self.assertEqual(self.tab.path, self.source)
        self.assertIn("drafts/", dialog.status.text())
        self.assertFalse(self.window.compile_authorized_roots)

    def test_block_model_and_unapplied_properties_are_captured_without_application(self):
        registry = BlockRegistry()
        block = registry.create(CreateBlockInput(type="text", alias="paragraph", content={"format": "plain", "text": "saved"}))
        block_project = self.home / "block-project"
        block_project.mkdir()
        session = ProjectSession(registry=registry, project_dir=block_project)
        session.save_now()
        self.assertTrue(session.last_save_ok, session.save_error)
        self.assertTrue(_install_session(self.window, session))
        initial = {"text": "saved"}
        draft = PropertyDraft("text", block.id, "paragraph", block.to_dict(), initial, {"text": "pending property"})
        session.set_editor_draft(draft)
        with patch.object(session, "save_now", wraps=session.save_now) as save:
            lease = CaptureLease(self.window, block_project)
            self.addCleanup(lease.release)
            payload = json.loads(next(d.payload for d in lease.drafts if d.kind == "block-state"))
            self.assertEqual(payload["model"]["blocks"][0]["content"]["text"], "saved")
            self.assertEqual(payload["unapplied"][0]["values"]["text"], "pending property")
            self.assertEqual(save.call_count, 0)
            self.assertIsNone(session.compile_final())
            self.assertFalse(session._compile_authorized)
            self.assertEqual(block.content["text"], "saved")

    def test_two_windows_keep_distinct_drafts_for_the_same_source(self):
        second = MainWindow(settings_store=isolated_settings())
        second.save_debounce_ms = 3600000
        second.auto_compile_action.setChecked(False)
        second._watch_file = lambda _: None
        second.open_file(self.source)
        other = second.current_tab()
        lease = None
        try:
            self.tab.editor.appendPlainText("first window")
            other.editor.appendPlainText("second window")
            lease = CaptureLease(self.window, self.project)
            payloads = [draft.payload.decode() for draft in lease.drafts]
            self.assertEqual(len(payloads), 2)
            self.assertTrue(any("first window" in payload for payload in payloads))
            self.assertTrue(any("second window" in payload for payload in payloads))
            self.assertFalse(self.tab.save_timer.isActive())
            self.assertFalse(other.save_timer.isActive())
            lease.release()
            self.assertTrue(self.tab.save_timer.isActive())
            self.assertTrue(other.save_timer.isActive())
        finally:
            if lease:
                lease.release()
            second.documents.cancel_save_timer(other)
            other.modified = other.dirty = False
            second.close()
            second.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_cancel_and_parent_close_wait_for_the_single_worker_before_resuming_writes(self):
        self.tab.editor.appendPlainText("pending")
        dialog = self.dialog()
        self.app._icstex_checkpoint_dialog = dialog
        entered, release = threading.Event(), threading.Event()
        def blocked(stop):
            entered.set()
            release.wait(3)
            if stop():
                from app.core.project_checkpoint import CheckpointCancelled
                raise CheckpointCancelled()
        dialog._launch("create", blocked)
        self.wait(entered.is_set)
        self.assertFalse(checkpoint_close_guard(self.window))
        self.assertTrue(dialog.busy)
        self.assertFalse(self.tab.save_timer.isActive())
        release.set()
        self.wait(lambda: not dialog.busy)
        self.assertFalse(self.window.documents.checkpoint_tabs)
        self.assertTrue(self.tab.save_timer.isActive())
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_publication_winning_cancel_race_keeps_its_result_visible(self):
        dialog = self.dialog()
        dialog.show()
        published, release = threading.Event(), threading.Event()
        target = self.home / "published-before-cancel.icstex-checkpoint"
        dialog.target.setText(str(target))
        def publish(*args, **kwargs):
            info = create_checkpoint(*args, **kwargs)
            published.set()
            release.wait(3)
            return info
        with patch("app.gui.project_checkpoint_dialog.create_checkpoint", side_effect=publish), \
             patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.perform()
            self.wait(published.is_set)
            dialog.reject()
            release.set()
            self.wait(lambda: not dialog.busy)
        self.assertTrue(target.exists())
        self.assertTrue(dialog.isVisible())
        self.assertIn(str(target), dialog.status.text())
        self.assertEqual(dialog.result_path, target)
        self.assertFalse(dialog.reveal_button.isHidden())
