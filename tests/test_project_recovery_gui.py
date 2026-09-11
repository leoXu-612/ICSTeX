import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import threading
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest

from app.core.project_checkpoint import create_checkpoint, restore_checkpoint, checkpoint_candidates
from app.core.project_recovery import read_recovery_copy
from app.core.blocks.project_repository import load_project
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow
from app.core.blocks.layout import LayoutNode, block_slot
from app.gui.project_checkpoint_dialog import CaptureLease
from app.gui.project_checkpoint_dialog import checkpoint_close_guard
from app.gui.project_recovery_dialog import RecoveryDraftDialog, open_recovered_drafts
from app.gui.main_window import MainWindow
from app.gui.block_mode import _install_session, _set_block_mode
from app.gui.blocks.project_session import ProjectSession
from tests.test_gui_editor import isolated_settings
from tests.v1_fixtures import create_project


class ProjectRecoveryGuiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-recovery-gui-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.fixture = create_project(self.home, "multi")
        self.project = self.fixture.root.parent
        self.window = MainWindow(settings_store=isolated_settings())
        self.window.save_debounce_ms = 3600000
        self.window.project_files.set_project_root(self.project)
        self.window.open_file(self.fixture.root)
        self.window.open_file(self.fixture.draft_path)
        self.original = self.fixture.draft_path.read_bytes()
        self.tab = self.window.current_tab()
        self.tab.editor.appendPlainText("Actual recovered source draft")
        self.draft = self.tab.editor.toPlainText()
        self.windows = [self.window]
        self.dialogs = []
        self.addCleanup(self.dispose)

    def wait(self, condition, timeout=6):
        end = time.monotonic() + timeout
        while not condition() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.003)
        self.assertTrue(condition())

    def dispose(self):
        self.app._icstex_recovery_dialog = None
        for dialog in self.dialogs:
            dialog.cancel.set()
            self.wait(lambda: not dialog.busy)
            if dialog.opened_window and dialog.opened_window not in self.windows:
                self.windows.append(dialog.opened_window)
            dialog.reject()
            dialog.deleteLater()
        for window in self.windows[::-1]:
            if window.block_session:
                window.block_session.editor_drafts.clear()
                window.block_session._dirty = False
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            window.close()
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def capture(self, project=None):
        project = project or self.project
        lease = CaptureLease(self.window, project)
        try:
            path = self.home / "saved.icstex-checkpoint"
            files, _ = checkpoint_candidates(project)
            create_checkpoint(project, files, path, drafts=lease.drafts)
        finally:
            lease.release()
        return restore_checkpoint(path, self.home / "recovered")

    def dialog(self, directory):
        dialog = RecoveryDraftDialog(self.window, directory)
        self.dialogs.append(dialog)
        self.wait(lambda: not dialog.busy)
        return dialog

    def test_actual_review_cancel_load_undo_no_autosave_and_explicit_save(self):
        restored = self.capture()
        dialog = self.dialog(restored.directory)
        self.assertIsNotNone(dialog.copy, dialog.status.text())
        dialog.tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Checked)
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0))
        self.assertIn("Actual recovered", dialog.preview.toPlainText())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            dialog.perform()
        self.assertIsNone(dialog.opened_window)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.perform()
        self.wait(lambda: not dialog.busy)
        new = dialog.opened_window
        self.assertIsNotNone(new, dialog.status.text())
        tab = new.current_tab()
        self.assertEqual(tab.editor.toPlainText(), self.draft)
        self.assertTrue(tab.recovery_pending)
        self.assertFalse(tab.save_timer and tab.save_timer.isActive())
        self.assertFalse(new.compile_authorized_roots)
        tab.editor.undo()
        self.assertEqual(tab.editor.toPlainText(), self.original.decode())
        tab.editor.redo()
        self.assertEqual(tab.editor.toPlainText(), self.draft)
        QTest.qWait(800)
        target = restored.project_dir / "chapters/analysis.tex"
        self.assertEqual(target.read_bytes(), self.original)
        self.assertTrue(new.save_current())
        self.assertFalse(tab.recovery_pending)
        self.assertEqual(target.read_text(), self.draft)
        self.assertEqual(self.fixture.draft_path.read_bytes(), self.original)
        self.assertEqual(self.tab.editor.toPlainText(), self.draft)

    def test_changed_copy_during_confirmation_is_refused(self):
        restored = self.capture()
        dialog = self.dialog(restored.directory)
        dialog.tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Checked)
        def change(*args):
            (restored.project_dir / "refs.bib").write_bytes(b"external winner")
            return QMessageBox.StandardButton.Yes
        with patch.object(QMessageBox, "question", side_effect=change):
            dialog.perform()
        self.wait(lambda: not dialog.busy)
        self.assertIsNone(dialog.opened_window)
        self.assertIn("摘要", dialog.status.text())

    def test_existing_window_and_later_external_write_are_preserved(self):
        restored = self.capture()
        copy = read_recovery_copy(restored.directory)
        ids = (copy.info.drafts[0].id,)
        new = open_recovered_drafts(self.window, copy, ids)
        self.windows.append(new)
        with self.assertRaises(ValueError):
            open_recovered_drafts(self.window, copy, ids)
        target = new.current_tab().path
        target.write_bytes(b"external winner")
        self.assertFalse(new.save_current())
        self.assertEqual(target.read_bytes(), b"external winner")
        self.assertEqual(new.current_tab().editor.toPlainText(), self.draft)

    def test_real_block_model_and_inspector_draft_resume_without_implicit_apply(self):
        fixture = create_project(self.home, "block")
        project = fixture.root.parent
        loaded = load_project(project)
        session = ProjectSession(**{key: loaded[key] for key in
            ("registry", "layout", "sources", "document_theme", "project_dir")})
        _install_session(self.window, session)
        _set_block_mode(self.window, True)
        block = session.registry.blocks()[0]
        session.selection.select_block(block.id, source="test")
        field = self.window.block_inspector.alias_edit
        field.selectAll()
        QTest.keyClicks(field, "recovered-alias")
        self.assertTrue(session.editor_drafts)
        original = (project / ".icstex/blocks.json").read_bytes()
        restored = self.capture(project)
        copy = read_recovery_copy(restored.directory)
        ids = tuple(entry.id for entry in copy.info.drafts if entry.kind == "block-state")
        new = open_recovered_drafts(self.window, copy, ids)
        self.windows.append(new)
        recovered = new.block_session
        self.assertEqual(new.block_inspector.alias_edit.text(), "recovered-alias")
        self.assertEqual(recovered.registry.get(block.id).alias, block.alias)
        self.assertTrue(recovered.recovery_pending)
        QTest.qWait(800)
        self.assertEqual((restored.project_dir / ".icstex/blocks.json").read_bytes(), original)
        self.assertTrue(recovered.apply_editor_drafts())
        self.assertEqual(recovered.registry.get(block.id).alias, "recovered-alias")
        QTest.qWait(800)
        self.assertEqual((restored.project_dir / ".icstex/blocks.json").read_bytes(), original)
        recovered.undo_stack.undo()
        self.assertEqual(recovered.registry.get(block.id).alias, block.alias)
        recovered.undo_stack.redo()
        recovered.save_now()
        self.assertTrue(recovered.last_save_ok, recovered.save_error)
        self.assertFalse(recovered.recovery_pending)
        self.assertEqual(load_project(restored.project_dir)["registry"].get(block.id).alias, "recovered-alias")
        self.assertEqual((project / ".icstex/blocks.json").read_bytes(), original)
        self.assertFalse(recovered._compile_authorized)

    def test_actual_live_table_cell_is_reopened_then_explicitly_applied(self):
        registry = BlockRegistry()
        data = TableData(columns=[ColumnSpec(id="c1", name="Value")],
            rows=[TableRow(id="r1", cells={"c1": Cell("text", "saved cell")})], header_row_count=0)
        block = registry.create(CreateBlockInput(type="table", alias="table", content=data.to_content_dict()))
        session = ProjectSession(registry=registry,
            layout=LayoutNode(id="tables", kind="column", children=(block_slot(block.id),)),
            project_dir=self.home / "tables")
        session.save_now()
        self.assertTrue(session.last_save_ok, session.save_error)
        _install_session(self.window, session)
        _set_block_mode(self.window, True)
        self.window.show()
        self.window.block_workspace.open_table(block.id)
        grid = self.window.block_workspace.table_editor.table
        grid.editItem(grid.item(0, 0))
        editor = self.window.block_workspace.table_editor._cell_editor
        self.assertIsNotNone(editor)
        editor.selectAll()
        QTest.keyClicks(editor, "recovered live cell")
        self.assertIn(("table_cell", block.id), session.editor_drafts)
        original = (session.project_dir / ".icstex/blocks.json").read_bytes()
        restored = self.capture(session.project_dir)
        copy = read_recovery_copy(restored.directory)
        new = open_recovered_drafts(self.window, copy,
            tuple(entry.id for entry in copy.info.drafts if entry.kind == "block-state"))
        self.windows.append(new)
        recovered = new.block_session
        self.assertIn(("table_cell", block.id), recovered.editor_drafts)
        box = new.block_inspector.draft_list
        index = next(i for i in range(box.count()) if box.itemData(i) == ("table_cell", block.id))
        box.setCurrentIndex(index)
        box.activated.emit(index)
        table = new.block_workspace.table_editor
        self.assertIsNotNone(table._cell_editor)
        self.assertEqual(table._cell_editor.text(), "recovered live cell")
        self.assertEqual(table.model.data.rows[0].cells["c1"].value, "saved cell")
        table.commit_pending_edit()
        self.assertNotIn(("table_cell", block.id), recovered.editor_drafts)
        self.assertTrue(recovered.apply_editor_drafts())
        self.assertEqual(recovered.registry.get(block.id).content["rows"][0]["cells"]["c1"]["value"], "recovered live cell")
        QTest.qWait(700)
        self.assertEqual((restored.project_dir / ".icstex/blocks.json").read_bytes(), original)
        recovered.save_now()
        self.assertTrue(recovered.last_save_ok, recovered.save_error)
        self.assertEqual((session.project_dir / ".icstex/blocks.json").read_bytes(), original)

    def test_close_during_background_review_waits_and_never_opens(self):
        restored = self.capture()
        ready, release = threading.Event(), threading.Event()
        def read(*args, **kwargs):
            ready.set()
            release.wait(5)
            return read_recovery_copy(*args, **kwargs)
        with patch("app.gui.project_recovery_dialog.read_recovery_copy", side_effect=read):
            dialog = RecoveryDraftDialog(self.window, restored.directory)
            self.dialogs.append(dialog)
            self.app._icstex_recovery_dialog = dialog
            self.wait(ready.is_set)
            self.assertFalse(checkpoint_close_guard(self.window))
            self.assertTrue(dialog.busy)
            release.set()
            self.wait(lambda: not dialog.busy)
        self.assertIsNone(dialog.opened_window)
