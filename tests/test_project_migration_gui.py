"""Offscreen only: real migration workflow, guards and separate opening."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from shiboken6 import isValid

from app.core.blocks.migration import legacy_fixture
from app.core.project_migration import read_migration_copy, inspect_project_migration
from app.gui.main_window import MainWindow
from app.gui.project_checkpoint_dialog import checkpoint_close_guard
from app.gui.project_migration_dialog import ProjectMigrationDialog, show_project_migration
from tests.test_gui_editor import isolated_settings
from tests.v1_fixtures import _png, create_project


class ProjectMigrationGuiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-migration-gui-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.project = self.home / "legacy"
        (self.project / ".icstex").mkdir(parents=True)
        (self.project / "figures").mkdir()
        (self.project / ".icstex/blocks.json").write_text(json.dumps(legacy_fixture()))
        for name in ("a.png", "b.png"):
            (self.project / "figures" / name).write_bytes(_png())
        (self.project / "main.tex").write_bytes(b"% Manual old source\r\n")
        (self.project / "optional.bib").write_bytes(b"% optional\n")
        self.window = MainWindow(settings_store=isolated_settings())
        self.window.save_debounce_ms = 3600000
        self.window.project_files.set_project_root(self.project)
        self.window.open_file(self.project / "main.tex")
        self.window.current_tab().editor.appendPlainText("% Independent original draft")
        self.before = self.bytes()
        self.dialog = ProjectMigrationDialog(self.window)
        self.app._icstex_migration_dialog = self.dialog
        self.addCleanup(self.dispose)

    def bytes(self):
        return {p.relative_to(self.project).as_posix(): p.read_bytes()
                for p in self.project.rglob("*") if p.is_file()}

    def wait(self, condition, seconds=8):
        until = time.monotonic() + seconds
        while not condition() and time.monotonic() < until:
            self.app.processEvents()
            time.sleep(0.003)
        self.assertTrue(condition())

    def dispose(self):
        self.dialog.cancel.set()
        self.wait(lambda: not self.dialog.busy)
        if isValid(self.dialog):
            self.dialog.reject()
        self.app._icstex_migration_dialog = None
        if isValid(self.dialog):
            self.dialog.deleteLater()
        for window in (self.dialog.opened, self.window):
            if window is None:
                continue
            if window.block_session:
                window.block_session._dirty = False
                window.block_session.editor_drafts.clear()
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            window.close()
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def load(self):
        self.dialog.load_project(self.project)
        self.wait(lambda: not self.dialog.busy)
        self.assertEqual(self.dialog.files.topLevelItemCount(), 5, self.dialog.status.text())
        self.dialog.inspect_selection()
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNotNone(self.dialog.review, self.dialog.status.text())
        self.dialog.target.setText(str(self.home / "copy"))

    def publish(self):
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.dialog.perform()
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNotNone(self.dialog.result, self.dialog.status.text())

    def test_primary_actions_stay_fixed_before_and_after_publication(self):
        self.load()
        dialog = self.dialog
        frozen, lease = dialog.review, dialog.lease
        dialog.show()
        dialog.resize(760, 620)
        for _ in range(6):
            self.app.processEvents()
        dialog.scroller.verticalScrollBar().setValue(0)
        self.app.processEvents()
        self.assertFalse(dialog.scroller.isAncestorOf(dialog.action_button))
        self.assertTrue(dialog.action_button.visibleRegion().contains(dialog.action_button.rect()))
        self.assertTrue(dialog.open_button.isHidden())
        self.assertIs(dialog.review, frozen)
        self.assertIs(dialog.lease, lease)
        self.publish()
        self.assertFalse(dialog.scroller.isAncestorOf(dialog.open_button))
        self.assertTrue(dialog.action_button.isHidden())
        self.assertFalse(dialog.open_button.isHidden())
        self.assertEqual(self.bytes(), self.before)

    def test_actual_selection_preview_cancel_publish_and_separate_confirmed_open(self):
        self.load()
        item = next(self.dialog.output.topLevelItem(i) for i in range(self.dialog.output.topLevelItemCount())
                    if self.dialog.output.topLevelItem(i).text(0) == "main.tex")
        self.dialog.output.setCurrentItem(item)
        self.assertIn("Manual old source", self.dialog.preview.toPlainText())
        self.assertIn("documentclass", self.dialog.preview.toPlainText())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            self.dialog.perform()
        self.assertFalse((self.home / "copy").exists())
        self.publish()
        reviewed = read_migration_copy(self.dialog.result.directory)
        self.assertIn(b"Independent original draft", next(iter(dict(reviewed.copy.drafts).values())))
        self.assertIsNone(reviewed.copy.info.drafts[0].target)
        self.assertIsNone(self.dialog.opened)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            self.dialog.prepare_open()
            self.wait(lambda: not self.dialog.busy)
        self.assertIsNone(self.dialog.opened)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.dialog.prepare_open()
            self.wait(lambda: not self.dialog.busy)
        new = self.dialog.opened
        self.assertIsNotNone(new, self.dialog.status.text())
        self.assertEqual(new.block_session.project_dir, reviewed.copy.project)
        self.assertFalse(new.block_session._compile_authorized)
        self.assertFalse(new.block_session.has_unsaved_changes)
        self.assertFalse(new.compile_authorized_roots)
        QTest.qWait(700)
        self.assertEqual(self.bytes(), self.before)
        self.assertIn("Independent original draft", self.window.current_tab().editor.toPlainText())

    def test_modal_no_then_keyboard_yes_keeps_new_window_after_dialog_disposal(self):
        self.load()
        self.publish()
        self.window.show()
        state = {"phase": "start"}
        errors = []
        started = time.monotonic()

        def step():
            modal = self.app.activeModalWidget()
            try:
                self.assertLess(time.monotonic() - started, 10, state)
                phase = state["phase"]
                if isinstance(modal, QMessageBox):
                    no = modal.button(QMessageBox.StandardButton.No)
                    yes = modal.button(QMessageBox.StandardButton.Yes)
                    self.assertIs(modal.defaultButton(), no)
                    self.assertIs(modal.focusWidget(), no)
                    if phase == "no":
                        state["phase"] = "cancelled"
                        QTest.keyClick(no, Qt.Key.Key_Return)
                    elif phase == "yes":
                        state["phase"] = "opened"
                        QTest.keyClick(no, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
                        self.assertIs(modal.focusWidget(), yes)
                        QTest.keyClick(yes, Qt.Key.Key_Space)
                    else:
                        self.fail(str(state))
                elif modal is self.dialog and not self.dialog.busy:
                    if phase == "start":
                        state["phase"] = "no"
                        self.dialog.prepare_open()
                    elif phase == "cancelled":
                        self.assertIsNone(self.dialog.opened)
                        self.assertIn("已取消打开", self.dialog.status.text())
                        self.assertFalse(self.dialog.cancel.is_set())
                        state["phase"] = "yes"
                        self.dialog.prepare_open()
                    elif phase == "opened":
                        self.fail(self.dialog.status.text())
            except Exception as exc:
                errors.append(repr(exc))
                if isinstance(modal, QMessageBox):
                    modal.reject()
                self.dialog.reject()

        timer = QTimer()
        timer.timeout.connect(step)
        timer.start(10)
        activation = []
        original_raise = MainWindow.raise_
        original_activate = MainWindow.activateWindow

        def raise_window(window):
            activation.append((window, "raise", self.app.activeModalWidget()))
            original_raise(window)

        def activate_window(window):
            activation.append((window, "activate", self.app.activeModalWidget()))
            original_activate(window)

        self.app._icstex_migration_dialog = None
        try:
            with patch("app.gui.project_migration_dialog.ProjectMigrationDialog", return_value=self.dialog), \
                    patch.object(MainWindow, "raise_", new=raise_window), \
                    patch.object(MainWindow, "activateWindow", new=activate_window):
                show_project_migration(self.window)
        finally:
            timer.stop()
        self.assertEqual(errors, [])
        self.assertEqual(state["phase"], "opened")
        new = self.dialog.opened
        self.assertIsNotNone(new, self.dialog.status.text())
        self.assertTrue(new.isVisible())
        self.assertIn(new, self.app._icstex_windows)
        self.assertEqual(new.block_session.project_dir, self.dialog.result.project_dir)
        self.assertFalse(new.compile_authorized_roots)
        self.assertFalse(new.block_session._compile_authorized)
        self.assertFalse(new.block_session.has_unsaved_changes)
        self.assertEqual(activation, [(new, "raise", None), (new, "activate", None)])
        self.assertIsNone(self.app._icstex_migration_dialog)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(isValid(self.dialog))
        self.assertTrue(isValid(new))
        self.assertTrue(new.isVisible())
        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.bytes(), self.before)
        self.assertIn("Independent original draft", self.window.current_tab().editor.toPlainText())

    def test_cancelled_migration_does_not_request_window_activation(self):
        self.window.show()
        self.app._icstex_migration_dialog = None
        QTimer.singleShot(0, self.dialog.reject)
        with patch("app.gui.project_migration_dialog.ProjectMigrationDialog", return_value=self.dialog), \
                patch.object(MainWindow, "raise_") as raised, \
                patch.object(MainWindow, "activateWindow") as activated:
            show_project_migration(self.window)
        raised.assert_not_called()
        activated.assert_not_called()
        self.assertIsNone(self.dialog.opened)
        self.assertIsNone(self.app._icstex_migration_dialog)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(isValid(self.dialog))
        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.bytes(), self.before)
        self.assertIn("Independent original draft", self.window.current_tab().editor.toPlainText())

    def test_changed_selection_requires_new_preview_and_omitted_metadata_refuses(self):
        self.load()
        optional = next(self.dialog.files.topLevelItem(i) for i in range(self.dialog.files.topLevelItemCount())
                        if self.dialog.files.topLevelItem(i).text(0) == "optional.bib")
        optional.setCheckState(0, Qt.CheckState.Unchecked)
        self.assertIsNone(self.dialog.review)
        self.assertFalse(self.dialog.action_button.isEnabled())
        self.dialog.inspect_selection()
        self.wait(lambda: not self.dialog.busy)
        self.assertNotIn("optional.bib", dict(self.dialog.review.original))
        metadata = next(self.dialog.files.topLevelItem(i) for i in range(self.dialog.files.topLevelItemCount())
                        if self.dialog.files.topLevelItem(i).text(0) == ".icstex/blocks.json")
        metadata.setCheckState(0, Qt.CheckState.Unchecked)
        self.dialog.inspect_selection()
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNone(self.dialog.review)
        self.assertIn("元数据", self.dialog.status.text())
        self.assertEqual(self.bytes(), self.before)

    def test_ordinary_copy_opens_selected_source_without_applying_draft_or_compiling(self):
        fixture = create_project(self.home, "multi")
        self.window.project_files.set_project_root(fixture.root.parent)
        self.window.open_file(fixture.root)
        self.window.current_tab().editor.appendPlainText("% independent new source draft")
        self.dialog.load_project(fixture.root.parent)
        self.wait(lambda: not self.dialog.busy)
        self.dialog.inspect_selection()
        self.wait(lambda: not self.dialog.busy)
        self.dialog.target.setText(str(self.home / "ordinary-copy"))
        self.publish()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.dialog.prepare_open()
            self.wait(lambda: not self.dialog.busy)
        new = self.dialog.opened
        self.assertIsNotNone(new, self.dialog.status.text())
        self.assertEqual(new.current_tab().path, self.dialog.result.project_dir / "main.tex")
        self.assertFalse(new.compile_authorized_roots)
        self.assertNotIn("independent new source draft", new.current_tab().editor.toPlainText())
        self.assertIn("independent new source draft", self.window.current_tab().editor.toPlainText())

    def test_active_block_draft_is_captured_but_not_applied_to_saved_copy(self):
        from app.core.blocks.project_repository import load_project
        from app.core.blocks.model import content_for_text
        from app.gui.blocks.project_session import ProjectSession
        from app.gui.block_mode import _install_session, _set_block_mode
        fixture = create_project(self.home, "block")
        loaded = load_project(fixture.root.parent)
        session = ProjectSession(**{k: loaded[k] for k in ("registry", "layout", "sources", "document_theme", "project_dir")})
        self.assertTrue(_install_session(self.window, session))
        _set_block_mode(self.window, True)
        block = session.registry.blocks()[0]
        session.registry.update(block.id, {"content": content_for_text("Independent Block model draft")})
        session.notify_model_changed("synthetic draft")
        self.dialog.load_project(fixture.root.parent)
        self.wait(lambda: not self.dialog.busy)
        self.dialog.inspect_selection()
        self.wait(lambda: not self.dialog.busy)
        self.dialog.target.setText(str(self.home / "block-copy"))
        self.publish()
        copy = read_migration_copy(self.dialog.result.directory)
        self.assertTrue(any(b"Independent Block model draft" in b for _, b in copy.copy.drafts))
        self.assertEqual(load_project(copy.copy.project)["registry"].blocks()[0].content["text"], "Synthetic analysis.")
        self.assertTrue(session._checkpoint_paused)
        self.assertTrue(session.has_unsaved_changes)

    def test_original_edit_during_confirmation_preserves_new_winner_and_draft(self):
        self.load()
        def mutate(*args):
            (self.project / "main.tex").write_bytes(b"External winner")
            return QMessageBox.StandardButton.Yes
        with patch.object(QMessageBox, "question", side_effect=mutate):
            self.dialog.perform()
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNone(self.dialog.result)
        self.assertFalse((self.home / "copy").exists())
        self.assertEqual((self.project / "main.tex").read_bytes(), b"External winner")
        self.assertIn("Independent original draft", self.window.current_tab().editor.toPlainText())

    def test_copy_evidence_change_during_open_confirmation_prevents_new_window(self):
        self.load()
        self.publish()
        def tamper(*args):
            (self.dialog.result.directory / "recovery-evidence/original/main.tex").write_bytes(b"tampered")
            return QMessageBox.StandardButton.Yes
        with patch.object(QMessageBox, "question", side_effect=tamper):
            self.dialog.prepare_open()
            self.wait(lambda: not self.dialog.busy)
        self.assertIsNone(self.dialog.opened)
        self.assertIn("摘要", self.dialog.status.text())
        self.assertEqual(self.bytes(), self.before)

    def test_owner_close_cancels_active_worker_and_cannot_start_second_reader(self):
        self.dialog.load_project(self.project)
        self.wait(lambda: not self.dialog.busy)
        ready, release = threading.Event(), threading.Event()
        calls = []
        def blocked(*args, **kwargs):
            calls.append(True)
            ready.set()
            release.wait(5)
            return inspect_project_migration(*args, **kwargs)
        with patch("app.gui.project_migration_dialog.inspect_project_migration", side_effect=blocked):
            self.dialog.inspect_selection()
            self.wait(ready.is_set)
            self.assertFalse(checkpoint_close_guard(self.window))
            self.dialog.inspect_selection()
            self.assertEqual(calls, [True])
            release.set()
            self.wait(lambda: not self.dialog.busy)
        self.assertTrue(self.dialog.lease.released)
        self.assertEqual(self.bytes(), self.before)

    def test_success_winning_cancel_is_visible_and_not_republished(self):
        from app.core import project_checkpoint
        self.load()
        real_publish = project_checkpoint._rename_directory_exclusive
        ready, release = threading.Event(), threading.Event()
        def publish(*args):
            ready.set()
            release.wait(5)
            return real_publish(*args)
        with patch.object(project_checkpoint, "_rename_directory_exclusive", side_effect=publish):
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                self.dialog.perform()
            self.wait(ready.is_set)
            self.dialog.reject()
            release.set()
            self.wait(lambda: not self.dialog.busy)
        self.assertIsNotNone(self.dialog.result)
        self.assertIn("已生成", self.dialog.close_button.text())
        self.assertFalse(self.dialog.action_button.isEnabled())
        self.assertTrue((self.home / "copy/project/main.tex").is_file())
        self.assertEqual(self.bytes(), self.before)
