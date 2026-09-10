from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt, qInstallMessageHandler
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox

from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.blocks.layout import LayoutNode, block_slot
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow
from app.gui.blocks.inspector import BlockInspector
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.workspace_widget import BlockWorkspaceWidget


class BlockEditorTargetTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-editor-targets-")
        self.addCleanup(self.temp.cleanup)
        registry = BlockRegistry()
        for name in ("alpha", "beta"):
            data = TableData(columns=[ColumnSpec(id="c1", name="Value")],
                rows=[TableRow(id="r1", cells={"c1": Cell("text", name)})], header_row_count=0)
            registry.create(CreateBlockInput(type="table", alias=name, content=data.to_content_dict()))
        self.first, self.second = registry.blocks()
        self.formula = registry.create(CreateBlockInput(type="formula", alias="formula",
            content=FormulaBlockAdapter().content_for("x+1")))
        layout = LayoutNode(id="tables", kind="column", children=tuple(block_slot(b.id) for b in registry.blocks()))
        self.session = ProjectSession(registry=registry, layout=layout, project_dir=Path(self.temp.name) / "project")
        self.session.save_now()
        self.assertTrue(self.session.last_save_ok, self.session.save_error)
        self.workspace = BlockWorkspaceWidget(self.session)
        self.inspector = BlockInspector(self.session)
        self.inspector.set_workspace(self.workspace)
        self.addCleanup(self.dispose)
        self.before = {p: p.read_bytes() for p in self.session.project_dir.rglob("*") if p.is_file()}

    def dispose(self):
        self.session.shutdown()
        for widget in (self.workspace, self.inspector):
            widget.close()
            widget.deleteLater()
        self.session.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def open_table(self, block):
        self.session.selection.select_block(block.id, source="test")
        self.inspector.table_button.click()

    def value(self, block):
        return self.session.registry.get(block.id).content["rows"][0]["cells"]["c1"]["value"]

    def choose_draft(self, key):
        box = self.inspector.draft_list
        index = next(i for i in range(box.count()) if box.itemData(i) == key)
        box.setCurrentIndex(index)
        box.activated.emit(index)
        self.inspector.refresh()
        self.assertEqual(box.currentData(), key)

    def test_inspector_opens_selected_second_table_without_model_or_disk_changes(self):
        before = [deepcopy(b.to_dict()) for b in self.session.registry.blocks()]
        self.open_table(self.second)
        self.assertEqual(self.workspace.table_editor.table.item(0, 0).text(), self.second.alias)
        self.assertEqual([b.to_dict() for b in self.session.registry.blocks()], before)
        self.assertFalse(self.session.has_unsaved_changes)
        self.assertIsNone(self.session.compile_manager)
        self.assertEqual({p: p.read_bytes() for p in self.before}, self.before)

    def test_table_edit_is_pending_and_direct_save_or_final_cannot_apply_it(self):
        self.open_table(self.second)
        self.workspace.table_editor.table.item(0, 0).setText("second draft")
        self.assertEqual(self.value(self.first), self.first.alias)
        self.assertEqual(self.value(self.second), self.second.alias)
        self.assertIn(("table", self.second.id), self.session.editor_drafts)
        self.assertFalse(self.session._save_timer.isActive())
        self.assertFalse(self.session._preview_timer.isActive())
        self.session.save_now()
        self.assertFalse(self.session.last_save_ok)
        self.assertIsNone(self.session.compile_final())
        self.assertIsNone(self.session.compile_manager)
        self.assertEqual({p: p.read_bytes() for p in self.before}, self.before)

    def test_switch_preserves_each_table_draft_and_local_undo(self):
        self.open_table(self.first)
        self.workspace.table_editor.table.item(0, 0).setText("first draft")
        first_model = self.workspace.table_editor.model
        self.open_table(self.second)
        self.workspace.table_editor.table.item(0, 0).setText("second draft")
        self.open_table(self.first)
        self.assertIs(self.workspace.table_editor.model, first_model)
        self.assertEqual(self.workspace.table_editor.table.item(0, 0).text(), "first draft")
        self.workspace.table_editor.undo()
        self.assertEqual(self.workspace.table_editor.table.item(0, 0).text(), self.first.alias)
        self.assertNotIn(("table", self.first.id), self.session.editor_drafts)
        self.assertIn(("table", self.second.id), self.session.editor_drafts)
        self.assertEqual(self.session.undo_stack.count(), 0)

    def test_apply_and_global_undo_stay_bound_after_selection_changes(self):
        self.open_table(self.second)
        self.workspace.table_editor.table.item(0, 0).setText("second applied")
        self.workspace.table_apply_button.click()
        self.assertEqual(self.value(self.second), "second applied")
        self.assertEqual(self.session.undo_stack.count(), 1)
        self.open_table(self.first)
        self.session.undo_stack.undo()
        self.assertEqual(self.value(self.second), self.second.alias)
        self.assertEqual(self.value(self.first), self.first.alias)
        self.session.undo_stack.redo()
        self.assertEqual(self.value(self.second), "second applied")
        self.assertEqual(self.value(self.first), self.first.alias)

    def test_changed_formula_target_is_not_overwritten_and_accepted_draft_is_retained(self):
        self.session.selection.select_block(self.formula.id, source="test")
        def accepted_after_change():
            self.session.registry.update(self.formula.id, {"content": FormulaBlockAdapter().content_for("x+7")})
            self.session.notify_model_changed("other-formula-editor")
            return QDialog.DialogCode.Accepted
        with patch("app.gui.formula_dialog.FormulaDialog") as dialog, \
             patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok):
            dialog.return_value.exec.side_effect = accepted_after_change
            dialog.return_value.plan.return_value = SimpleNamespace(text=r"\(x+2\)")
            self.inspector.formula_button.click()
        self.assertEqual(self.session.registry.get(self.formula.id).content["latexCache"], "x+7")
        draft = self.session.editor_drafts[("formula", self.formula.id)]
        self.assertEqual(draft.values["latexCache"], "x+2")
        self.assertEqual(self.session.undo_stack.count(), 0)

    def test_formula_cancel_changes_nothing(self):
        self.session.selection.select_block(self.formula.id, source="test")
        before = deepcopy(self.formula.to_dict())
        with patch("app.gui.formula_dialog.FormulaDialog") as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.inspector.formula_button.click()
        self.assertEqual(self.formula.to_dict(), before)
        self.assertFalse(self.session.editor_drafts)
        self.assertFalse(self.session.has_unsaved_changes)
        self.assertIsNone(self.session.compile_manager)

    def start_cell_input(self, text):
        self.workspace.show()
        self.workspace.activateWindow()
        self.open_table(self.second)
        self.app.processEvents()
        grid = self.workspace.table_editor.table
        grid.editItem(grid.item(0, 0))
        self.app.processEvents()
        editor = self.app.focusWidget()
        self.assertIsInstance(editor, QLineEdit)
        editor.selectAll()
        QTest.keyClicks(editor, text)
        return editor

    def test_live_cell_text_is_dirty_before_delegate_commit_and_switch_keeps_target(self):
        editor = self.start_cell_input("live cell draft")
        self.assertTrue(self.session.has_unsaved_changes)
        self.assertIn(("table_cell", self.second.id), self.session.editor_drafts)
        self.assertEqual(self.value(self.second), self.second.alias)
        self.assertEqual(editor.text(), "live cell draft")
        self.open_table(self.first)
        self.assertIn(("table", self.second.id), self.session.editor_drafts)
        self.assertNotIn(("table_cell", self.second.id), self.session.editor_drafts)
        self.assertEqual(self.workspace.table_editor.table.item(0, 0).text(), self.first.alias)
        self.open_table(self.second)
        self.assertEqual(self.workspace.table_editor.table.item(0, 0).text(), "live cell draft")
        self.assertEqual({p: p.read_bytes() for p in self.before}, self.before)

    def test_save_flushes_live_cell_to_its_draft_before_explicit_confirmation(self):
        from app.gui.blocks.close_guard import save_block_session
        from app.core.blocks.project_repository import load_project
        self.start_cell_input("saved live input")
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Save) as warning:
            self.assertTrue(save_block_session(self.workspace, self.session))
            self.assertEqual(warning.call_count, 1)
        loaded = load_project(self.session.project_dir)["registry"]
        self.assertEqual(loaded.get(self.second.id).content["rows"][0]["cells"]["c1"]["value"], "saved live input")
        self.assertEqual(loaded.get(self.first.id).content["rows"][0]["cells"]["c1"]["value"], self.first.alias)
        self.assertFalse(self.session.has_unsaved_changes)
        self.assertIsNone(self.session.compile_manager)

    def test_live_cell_escape_cancels_without_model_undo_or_io(self):
        editor = self.start_cell_input("cancel this cell")
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        self.app.processEvents()
        self.assertFalse(self.session.editor_drafts)
        self.assertFalse(self.session.has_unsaved_changes)
        self.assertEqual(self.value(self.second), self.second.alias)
        self.assertEqual(self.session.undo_stack.count(), 0)
        self.assertEqual({p: p.read_bytes() for p in self.before}, self.before)

    def test_enter_then_immediate_switch_has_no_stale_delegate_commit(self):
        editor = self.start_cell_input("enter then switch")
        warnings = []
        previous = qInstallMessageHandler(lambda _kind, _context, message: warnings.append(message))
        try:
            QTest.keyClick(editor, Qt.Key.Key_Return)
            self.open_table(self.first)
            self.app.processEvents()
        finally:
            qInstallMessageHandler(previous)
        self.assertFalse([text for text in warnings if "commitData called" in text], warnings)
        self.open_table(self.second)
        self.assertEqual(self.workspace.table_editor.table.item(0, 0).text(), "enter then switch")
        self.assertEqual(self.value(self.second), self.second.alias)

    def test_enter_then_immediate_save_has_no_stale_delegate_commit(self):
        from app.gui.blocks.close_guard import save_block_session
        editor = self.start_cell_input("enter then save")
        warnings = []
        previous = qInstallMessageHandler(lambda _kind, _context, message: warnings.append(message))
        try:
            QTest.keyClick(editor, Qt.Key.Key_Return)
            with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Save):
                self.assertTrue(save_block_session(self.workspace, self.session))
            self.app.processEvents()
        finally:
            qInstallMessageHandler(previous)
        self.assertFalse([text for text in warnings if "commitData called" in text], warnings)
        self.assertEqual(self.value(self.second), "enter then save")

    def test_live_cell_close_cancel_retains_input_and_external_model_conflict(self):
        from app.gui.blocks.close_guard import confirm_block_close
        self.start_cell_input("retained live input")
        content = deepcopy(self.second.content)
        content["rows"][0]["cells"]["c1"]["value"] = "changed model"
        self.session.registry.update(self.second.id, {"content": content})
        self.session.notify_model_changed("changed-table-target")
        self.assertEqual(self.workspace.table_editor.table.item(0, 0).text(), "retained live input")
        self.assertFalse(self.session.apply_editor_drafts())
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel):
            self.assertFalse(confirm_block_close(self.workspace, self.session))
        self.assertEqual(self.value(self.second), "changed model")
        self.assertIn(("table", self.second.id), self.session.editor_drafts)
        self.assertEqual({p: p.read_bytes() for p in self.before}, self.before)

    def test_deleted_table_draft_can_reopen_and_discard_without_first_table_fallback(self):
        self.open_table(self.second)
        self.workspace.table_editor.table.item(0, 0).setText("deleted target draft")
        self.session.registry.remove(self.second.id)
        self.session.notify_model_changed("deleted-table")
        self.open_table(self.first)
        self.choose_draft(("table", self.second.id))
        self.assertEqual(self.workspace.table_editor.table.item(0, 0).text(), "deleted target draft")
        self.assertFalse(self.session.apply_editor_drafts())
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel):
            self.workspace.table_discard_button.click()
        self.assertIn(("table", self.second.id), self.session.editor_drafts)
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Discard):
            self.workspace.table_discard_button.click()
        self.assertFalse(self.session.editor_drafts)
        self.assertFalse(self.workspace.table_editor.isEnabled())
        self.assertEqual(self.value(self.first), self.first.alias)

    def test_batch_table_and_alias_changes_preserve_opaque_fields_zero_false_and_one_undo(self):
        content = deepcopy(self.second.content)
        content["columns"][0]["opaque"] = {"preserve": True}
        content["columns"].append({"id": "c2", "name": "Flag", "dataType": "boolean"})
        content["rows"][0]["opaque"] = ["row metadata"]
        content["rows"][0]["cells"]["c1"]["opaque"] = "cell metadata"
        content["rows"][0]["cells"]["c2"] = {"kind": "boolean", "value": False}
        content["header"]["opaque"] = "header metadata"
        content["merges"] = [[0, 0, 0, 0]]
        self.session.registry.update(self.second.id, {"content": content})
        self.session.notify_model_changed("synthetic-opaque-table")
        self.session.save_now()
        self.assertTrue(self.session.last_save_ok, self.session.save_error)
        before = deepcopy(self.second.content)
        self.open_table(self.second)
        self.inspector.alias_edit.setText("renamed table")
        self.workspace.table_editor.table.item(0, 0).setText("0")
        self.assertTrue(self.session.apply_editor_drafts())
        applied = self.second.content
        self.assertEqual(applied["rows"][0]["cells"]["c1"], {"kind": "number", "value": 0, "opaque": "cell metadata"})
        self.assertIs(applied["rows"][0]["cells"]["c2"]["value"], False)
        self.assertEqual(applied["columns"][0]["opaque"], {"preserve": True})
        self.assertEqual(applied["rows"][0]["opaque"], ["row metadata"])
        self.assertEqual(applied["header"], before["header"])
        self.assertEqual(applied["merges"], before["merges"])
        self.assertEqual(self.second.alias, "renamed table")
        self.assertEqual(self.session.undo_stack.count(), 1)
        self.session.undo_stack.undo()
        self.assertEqual(self.second.content, before)
        self.assertNotEqual(self.second.alias, "renamed table")

    def test_invalid_table_edit_refuses_whole_batch_before_alias_or_other_table_change(self):
        content = deepcopy(self.second.content)
        content["columns"][0]["dataType"] = "number"
        content["rows"][0]["cells"]["c1"] = {"kind": "number", "value": 1}
        self.session.registry.update(self.second.id, {"content": content})
        self.session.notify_model_changed("numeric-table")
        self.open_table(self.first)
        self.workspace.table_editor.table.item(0, 0).setText("valid draft")
        self.open_table(self.second)
        self.inspector.alias_edit.setText("must not apply")
        self.workspace.table_editor.table.item(0, 0).setText("not a number")
        self.assertFalse(self.session.apply_editor_drafts())
        self.assertEqual(self.value(self.first), self.first.alias)
        self.assertEqual(self.value(self.second), 1)
        self.assertNotEqual(self.second.alias, "must not apply")
        self.assertEqual(self.session.undo_stack.count(), 0)
        self.assertEqual(len(self.session.editor_drafts), 3)

    def test_unsupported_table_shape_is_disabled_without_substitution(self):
        content = deepcopy(self.second.content)
        del content["rows"][0]["id"]
        self.session.registry.update(self.second.id, {"content": content})
        self.session.notify_model_changed("missing-row-id")
        before = deepcopy(self.second.to_dict())
        self.open_table(self.second)
        self.assertFalse(self.workspace.table_editor.isEnabled())
        self.assertEqual(self.second.to_dict(), before)
        self.assertEqual(self.value(self.first), self.first.alias)

    def test_read_only_input_never_projects_current_table_over_first_registry_table(self):
        import json
        from app.gui.submission_check_controller import SubmissionCheckController
        self.open_table(self.second)
        self.workspace.table_editor.table.item(0, 0).setText("unapplied second")
        payload = SubmissionCheckController._block_input(self.session)
        blocks = {block["id"]: block for block in json.loads(payload.blocks)["blocks"]}
        self.assertEqual(blocks[self.first.id]["content"]["rows"][0]["cells"]["c1"]["value"], self.first.alias)
        self.assertEqual(blocks[self.second.id]["content"]["rows"][0]["cells"]["c1"]["value"], self.second.alias)
        self.assertTrue(payload.pending_property_drafts)

    def test_formula_tab_and_inspector_share_one_captured_target_command(self):
        tab = self.workspace.formula_tab
        tab.block_list.setCurrentRow(0)
        with patch("app.gui.blocks.formula_tab.FormulaDialog") as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.plan.return_value = SimpleNamespace(text=r"\(x+3\)")
            tab.edit_button.click()
        self.assertEqual(self.formula.content["latexCache"], "x+3")
        self.assertEqual(self.session.undo_stack.count(), 1)
        self.session.undo_stack.undo()
        self.assertEqual(self.formula.content["latexCache"], "x+1")
        self.assertIn("x+1", tab.block_list.item(0).text())

    def test_formula_no_edit_preserves_opaque_ast_and_does_not_create_undo(self):
        content = deepcopy(self.formula.content)
        content["ast"]["opaque"] = {"preserve": True}
        self.session.registry.update(self.formula.id, {"content": content})
        self.session.notify_model_changed("opaque-formula")
        self.session.selection.select_block(self.formula.id, source="test")
        before = deepcopy(self.formula.to_dict())
        with patch("app.gui.formula_dialog.FormulaDialog") as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.plan.return_value = SimpleNamespace(text=r"\(x+1\)")
            self.inspector.formula_button.click()
        self.assertEqual(self.formula.to_dict(), before)
        self.assertEqual(self.session.undo_stack.count(), 0)

    def test_formula_deleted_target_retains_accepted_text_and_can_be_explicitly_discarded(self):
        self.session.selection.select_block(self.formula.id, source="test")
        def accept_after_delete():
            self.session.registry.remove(self.formula.id)
            self.session.notify_model_changed("deleted-formula")
            return QDialog.DialogCode.Accepted
        with patch("app.gui.formula_dialog.FormulaDialog") as dialog, patch.object(QMessageBox, "warning"):
            dialog.return_value.exec.side_effect = accept_after_delete
            dialog.return_value.plan.return_value = SimpleNamespace(text=r"\(x+9\)")
            self.inspector.formula_button.click()
        key = ("formula", self.formula.id)
        self.choose_draft(key)
        self.assertEqual(self.inspector.formula_info.text(), "x+9")
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel):
            self.inspector.pending_discard_button.click()
        self.assertIn(key, self.session.editor_drafts)
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Discard):
            self.inspector.pending_discard_button.click()
        self.assertNotIn(key, self.session.editor_drafts)
        self.assertIsNone(self.session.registry.get(self.formula.id))

    def test_late_formula_acceptance_after_shutdown_does_not_mutate_model(self):
        self.session.selection.select_block(self.formula.id, source="test")
        before = deepcopy(self.formula.to_dict())
        with patch("app.gui.formula_dialog.FormulaDialog") as dialog:
            dialog.return_value.exec.side_effect = lambda: (self.session.shutdown(), QDialog.DialogCode.Accepted)[1]
            dialog.return_value.plan.return_value = SimpleNamespace(text=r"\(x+9\)")
            self.inspector.formula_button.click()
        self.assertEqual(self.formula.to_dict(), before)
        self.assertFalse(self.session.editor_drafts)

    def test_image_target_changed_during_picker_is_rejected_before_copy(self):
        block = self.session.registry.create(CreateBlockInput(type="image", alias="image",
            content={"source": "assets/images/original.png"}))
        self.session.selection.select_block(block.id, source="test")
        def selected_after_change(*_args):
            self.session.registry.update(block.id, {"content": {"source": "assets/images/other.png"}})
            return "/synthetic/chosen.png", ""
        with patch("app.gui.blocks.inspector.QFileDialog.getOpenFileName", side_effect=selected_after_change), \
             patch("app.gui.blocks.inspector.import_image", return_value="assets/images/chosen.png") as copy, \
             patch.object(QMessageBox, "warning"):
            self.inspector.image_replace_button.click()
        copy.assert_not_called()
        self.assertEqual(block.content["source"], "assets/images/other.png")
        self.assertEqual(self.session.undo_stack.count(), 0)
