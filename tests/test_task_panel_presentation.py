"""D3 presentation must preserve underlying identities, drafts and commands."""
import os
from types import SimpleNamespace
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QInputMethodEvent, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.blocks.layout import LayoutNode, block_slot
from app.core.compiler import BuildPurpose, CompileOutcome
from app.core.latex_outline import scan_outline
from app.gui.blocks.diagnostics_dock import BlockDiagnostics
from app.gui.blocks.navigation_dock import BlockNavigationWidget
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.workspace_widget import BlockWorkspaceWidget
from app.gui.formula_dialog import FormulaDialog
from app.gui.project_panels import OutlinePanel
from app.gui.theme import apply_theme
from app.gui.theme.ui_scale_manager import UiScaleManager
from tests.test_blocks_gui import registry_with_blocks


class TaskPanelPresentationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        apply_theme(cls.app)
        if not hasattr(cls.app, "ui_scale_manager"):
            cls.app.ui_scale_manager = UiScaleManager(cls.app)

    def setUp(self):
        self.widgets = []
        self.registry = registry_with_blocks()
        block = self.registry.blocks()[0]
        self.layout = LayoutNode(id="lyt_test", kind="row", children=(block_slot(block.id), block_slot(block.id)))
        self.session = ProjectSession(registry=self.registry, layout=self.layout)
        self.previous_scale = self.app.ui_scale_manager.scale

    def tearDown(self):
        for widget in self.widgets:
            widget.close()
            widget.deleteLater()
        self.session.shutdown()
        self.session.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.ui_scale_manager.apply_scale(self.previous_scale)

    def test_outline_title_gets_space_and_refresh_keeps_selection_and_jump(self):
        panel = OutlinePanel()
        self.widgets.append(panel)
        items = scan_outline("\\section{Research question}\n\\subsubsection{Evidence and uncertainty}")
        panel.set_outline(items)
        panel.resize(440, 400)
        panel.show()
        self.app.processEvents()
        self.assertGreater(panel.table.columnWidth(0), 220)
        panel.table.setCurrentCell(1, 0)
        panel.set_outline(items)
        self.assertEqual(panel.table.currentRow(), 1)
        jumped = []
        panel.jumpRequested.connect(jumped.append)
        panel._emit_jump(1)
        self.assertEqual(jumped, [2])
        self.assertNotEqual(panel.table.item(1, 1).text(), "subsubsection")

    def test_number_pad_toggle_keeps_same_draft_preedit_and_undo(self):
        dialog = FormulaDialog(None, "$x+1$", 0, 5)
        self.widgets.append(dialog)
        dialog.show()
        editor = dialog.visual_edit
        editor.insert_text("y")
        latex, history = editor.latex(), len(editor._undo)
        actions = []
        dialog.keyboard.actionRequested.connect(actions.append)
        QApplication.sendEvent(editor, QInputMethodEvent("zhong", []))
        for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
            self.app.ui_scale_manager.apply_scale(scale)
            dialog.keyboard.numbers_button.setChecked(False)
            self.assertFalse(dialog.keyboard.number_pad.isVisible())
            self.assertEqual(editor.latex(), latex)
            self.assertTrue(editor.has_preedit)
            self.assertEqual(len(editor._undo), history)
            dialog.keyboard.numbers_button.setChecked(True)
            self.assertTrue(dialog.keyboard.number_pad.isVisible())
        self.assertEqual(actions, [])
        QApplication.sendEvent(editor, QInputMethodEvent())
        editor.undo()
        self.assertEqual(editor.latex(), "x+1")
        self.assertIsNone(dialog._accepted_plan)

    def test_navigation_shows_layout_and_copies_full_identity_without_model_change(self):
        nav = BlockNavigationWidget(self.session)
        self.widgets.append(nav)
        self.assertEqual(nav.layout_tree.topLevelItemCount(), 1)
        root = nav.layout_tree.topLevelItem(0)
        self.assertEqual(root.data(0, Qt.ItemDataRole.UserRole), ("node", self.layout.id))
        self.assertNotIn(self.layout.id, root.text(0))
        child = root.child(0)
        self.assertEqual(child.data(0, Qt.ItemDataRole.UserRole), ("slot", self.layout.children[0].instanceId))
        self.assertNotIn("blk_", child.text(0))
        self.assertIn(self.layout.children[0].blockId, child.toolTip(0))
        nav.layout_tree.setCurrentItem(child)
        nav.layout_tree.actions()[0].trigger()
        self.assertIn(self.layout.children[0].instanceId, self.app.clipboard().text())
        self.assertIn(self.layout.children[0].blockId, self.app.clipboard().text())
        nav._refresh_layout()
        self.assertEqual(nav.layout_tree.currentItem().data(0, Qt.ItemDataRole.UserRole),
                         ("slot", self.layout.children[0].instanceId))
        self.assertIs(self.session.layout, self.layout)
        self.assertEqual(self.session.undo_stack.count(), 0)

    def test_identity_copy_shortcut_and_numeric_toggle_are_keyboard_reachable(self):
        nav = BlockNavigationWidget(self.session)
        self.widgets.append(nav)
        nav.show()
        nav.activateWindow()
        nav.block_list.setCurrentRow(0)
        nav.block_list.setFocus()
        self.app.processEvents()
        QTest.keySequence(nav.block_list, QKeySequence.StandardKey.Copy)
        self.assertIn(nav.block_list.currentItem().data(Qt.ItemDataRole.UserRole), self.app.clipboard().text())
        nav.hide()
        dialog = FormulaDialog(None, "$x+1$", 0, 5)
        self.widgets.append(dialog)
        dialog.show()
        dialog.activateWindow()
        button = dialog.keyboard.numbers_button
        button.setFocus()
        self.app.processEvents()
        QTest.keyClick(button, Qt.Key.Key_Space)
        self.assertFalse(dialog.keyboard.number_pad.isVisible())
        self.assertIs(self.app.focusWidget(), button)
        QTest.keyClick(button, Qt.Key.Key_Space)
        self.assertTrue(dialog.keyboard.number_pad.isVisible())
        self.assertEqual(dialog.visual_edit.latex(), "x+1")

    def test_layout_selection_and_reorder_use_item_identity_not_display_text(self):
        workspace = BlockWorkspaceWidget(self.session)
        self.widgets.append(workspace)
        # Match the main-window assembly; standalone panels retain local undo.
        workspace.layout_panel.command_stack = self.session.undo_stack
        slots = workspace.layout_panel.slot_list
        selected = []
        workspace.layout_selected.connect(selected.append)
        slots.item(0).setText("Same friendly title")
        slots.item(1).setText("Same friendly title")
        slots.setCurrentRow(1)
        self.assertEqual(selected[-1], self.layout.children[1].instanceId)
        item = slots.takeItem(1)
        slots.insertItem(0, item)
        workspace.layout_panel._on_slots_moved()
        self.assertEqual(workspace.layout_panel.layout.children,
                         (self.layout.children[1], self.layout.children[0]))
        self.session.undo_stack.undo()
        self.assertEqual(self.session.layout, self.layout)

    def test_compile_labels_distinguish_every_outcome_and_do_not_claim_render(self):
        panel = BlockDiagnostics(self.session)
        self.widgets.append(panel)
        for outcome in CompileOutcome:
            panel._on_finished(SimpleNamespace(purpose=BuildPurpose.FINAL, outcome=outcome,
                duration_seconds=1.25, ok=outcome is CompileOutcome.SUCCESS))
            self.assertIn("正式编译", panel.status_label.text())
            self.assertNotIn("BuildPurpose", panel.status_label.text())
            self.assertNotIn(outcome.value, panel.status_label.text())
            self.assertNotIn("PDF 已刷新", panel.log_view.toPlainText())
        self.session._compile_authorized = True
        panel._on_requested("block_updated:blk_synthetic")
        self.assertNotIn("blk_", panel.status_label.text())
        self.assertIn("blk_synthetic", panel.status_label.toolTip())
        self.assertIsNone(self.session.compile_manager)

    def test_copying_inspector_identity_preserves_unapplied_draft(self):
        from app.gui.blocks.inspector import BlockInspector
        inspector = BlockInspector(self.session)
        self.widgets.append(inspector)
        self.assertFalse(inspector.copy_identity_button.isEnabled())
        block = next(block for block in self.registry.blocks() if block.type == "text")
        before = block.to_dict()
        self.session.selection.select_block(block.id, source="test")
        inspector.content_edit.insertPlainText("Unapplied synthetic draft ")
        draft = self.session.editor_drafts[("block", block.id)]
        inspector.copy_identity_button.click()
        self.assertIn(block.id, self.app.clipboard().text())
        self.assertIs(self.session.editor_drafts[("block", block.id)], draft)
        self.assertEqual(block.to_dict(), before)
        self.assertEqual(self.session.undo_stack.count(), 0)
