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
from PySide6.QtTest import QTest

from app.core.blocks.write_recovery import inspect_write_journal
from app.core.project_recovery import read_recovery_copy
from app.gui.block_write_recovery_dialog import BlockWriteRecoveryDialog
from app.gui.project_checkpoint_dialog import checkpoint_close_guard
from app.gui.main_window import MainWindow
from tests.test_block_write_recovery import interrupted_write
from tests.test_gui_editor import isolated_settings
from tests.v1_fixtures import create_project


class BlockWriteRecoveryGuiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-journal-gui-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.fixture = create_project(self.home, "block")
        self.project = self.fixture.root.parent
        interrupted_write(self.project, external=True)
        self.window = MainWindow(settings_store=isolated_settings())
        self.window.save_debounce_ms = 3600000
        self.window.project_files.set_project_root(self.project)
        self.window.open_file(self.fixture.root)
        self.window.current_tab().editor.appendPlainText("% Independent window draft")
        self.before = self.bytes()
        self.dialog = BlockWriteRecoveryDialog(self.window)
        self.addCleanup(self.dispose)

    def bytes(self):
        return {p.relative_to(self.project).as_posix(): p.read_bytes()
                for p in self.project.rglob("*") if p.is_file()}

    def wait(self, condition, seconds=6):
        end = time.monotonic() + seconds
        while not condition() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.003)
        self.assertTrue(condition())

    def dispose(self):
        self.app._icstex_write_recovery_dialog = None
        self.dialog.cancel.set()
        self.wait(lambda: not self.dialog.busy)
        self.dialog.reject()
        self.dialog.deleteLater()
        for tab in self.window.tabs.values():
            self.window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def load(self, side="after"):
        self.dialog.load_project(self.project)
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNotNone(self.dialog.review, self.dialog.status.text())
        for choice in self.dialog.choices.values():
            if side:
                choice.setCurrentIndex(choice.findData(side))
        self.dialog.target.setText(str(self.home / "recovered"))

    def test_large_font_version_picker_is_visible_and_return_does_not_publish(self):
        self.load(side=None)
        dialog = self.dialog
        font = dialog.font()
        font.setPointSize(18)
        dialog.setFont(font)
        dialog.resize(760, 620)
        dialog.show()
        dialog.activateWindow()
        path, choice = next(iter(dialog.choices.items()))
        item = next(dialog.tree.topLevelItem(i) for i in range(dialog.tree.topLevelItemCount())
                    if dialog.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) == path)
        dialog.tree.setCurrentItem(item, 2)
        dialog.tree.scrollToItem(item)
        dialog.scroller.ensureWidgetVisible(dialog.tree)
        choice.setFocus()
        self.app.processEvents()
        self.assertTrue(choice.visibleRegion().contains(choice.rect()))
        self.assertTrue(dialog.action_button.visibleRegion().contains(dialog.action_button.rect()))
        with patch.object(QMessageBox, "question") as question:
            QTest.keyClick(choice, Qt.Key.Key_Space)
            self.assertTrue(choice.view().isVisible())
            popup = self.app.focusWindow()
            self.assertIsNotNone(popup)
            QTest.keyClick(popup, Qt.Key.Key_Down)
            QTest.keyClick(popup, Qt.Key.Key_Return)
            self.assertEqual(choice.currentData(), "before")
            question.assert_not_called()
        self.assertIsNone(dialog.result)
        self.assertEqual(self.bytes(), self.before)

    def test_real_review_selection_cancel_confirm_and_separate_window_draft(self):
        self.load(side=None)
        with patch.object(QMessageBox, "question") as question:
            self.dialog.perform()
            question.assert_not_called()
        for choice in self.dialog.choices.values():
            choice.setCurrentIndex(choice.findData("after"))
        item = next(self.dialog.tree.topLevelItem(i) for i in range(self.dialog.tree.topLevelItemCount())
                    if self.dialog.tree.topLevelItem(i).text(1) == "外部版本 / 冲突")
        self.dialog.tree.setCurrentItem(item)
        self.assertIn("External manual winner.", self.dialog.preview.toPlainText())
        self.assertIn("Recovered interrupted", self.dialog.preview.toPlainText())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            self.dialog.perform()
        self.assertFalse((self.home / "recovered").exists())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.dialog.perform()
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNotNone(self.dialog.result, self.dialog.status.text())
        copy = read_recovery_copy(self.dialog.result.directory)
        self.assertIn(b"Independent window draft", next(iter(dict(copy.drafts).values())))
        QTest.qWait(800)
        self.assertEqual(self.bytes(), self.before)
        self.assertFalse(self.window.compile_authorized_roots)
        self.assertTrue(self.dialog.reveal_button.isHidden() is False)
        self.assertTrue(self.dialog.resume_button.isHidden() is False)
        self.assertFalse(self.dialog.action_button.isEnabled())

    def test_inconsistent_current_choices_keep_original_and_never_publish(self):
        self.load(side="current")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.dialog.perform()
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNone(self.dialog.result)
        self.assertIn("不一致", self.dialog.status.text())
        self.assertFalse((self.home / "recovered").exists())
        self.assertEqual(self.bytes(), self.before)

    def test_change_inside_confirmation_refuses_recovery(self):
        self.load()
        def mutate(*args):
            self.fixture.root.write_bytes(b"new external winner")
            return QMessageBox.StandardButton.Yes
        with patch.object(QMessageBox, "question", side_effect=mutate):
            self.dialog.perform()
        self.wait(lambda: not self.dialog.busy)
        self.assertIsNone(self.dialog.result)
        self.assertFalse((self.home / "recovered").exists())
        self.assertEqual(self.fixture.root.read_bytes(), b"new external winner")
        self.assertIn("Independent window draft", self.window.current_tab().editor.toPlainText())

    def test_owner_close_waits_for_active_reader_and_cancels_once(self):
        ready, release = threading.Event(), threading.Event()
        calls = []
        def read(*args, **kwargs):
            calls.append(True)
            ready.set()
            release.wait(5)
            return inspect_write_journal(*args, **kwargs)
        self.app._icstex_write_recovery_dialog = self.dialog
        with patch("app.gui.block_write_recovery_dialog.inspect_write_journal", side_effect=read):
            self.dialog.load_project(self.project)
            self.wait(ready.is_set)
            self.assertFalse(checkpoint_close_guard(self.window))
            self.dialog.load_project(self.project)
            self.assertEqual(len(calls), 1)
            release.set()
            self.wait(lambda: not self.dialog.busy)
        self.assertTrue(self.dialog.lease.released)
        self.assertIsNone(self.dialog.result)
        self.assertEqual(self.bytes(), self.before)

    def test_publication_winning_final_cancel_keeps_visible_result(self):
        self.load()
        from app.core import project_checkpoint
        real = project_checkpoint._rename_directory_exclusive
        ready, release = threading.Event(), threading.Event()
        def publish(*args):
            ready.set()
            release.wait(5)
            return real(*args)
        with patch.object(project_checkpoint, "_rename_directory_exclusive", side_effect=publish):
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                self.dialog.perform()
            self.wait(ready.is_set)
            self.dialog.reject()
            release.set()
            self.wait(lambda: not self.dialog.busy)
        self.assertIsNotNone(self.dialog.result, self.dialog.status.text())
        self.assertTrue((self.home / "recovered/project/main.tex").is_file())
        self.assertFalse(self.dialog.reveal_button.isHidden())
        self.assertIn("已生成", self.dialog.close_button.text())
        self.assertEqual(self.bytes(), self.before)
