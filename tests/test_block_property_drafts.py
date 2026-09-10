from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox
from app.core.blocks.property_draft import PropertyDraft, prepare_drafts
from app.core.blocks.project_repository import load_project
from app.gui.blocks.inspector import BlockInspector
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.close_guard import compile_block_session, confirm_block_close, save_block_session
from tests.v1_fixtures import create_project


class PropertyDraftTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-property-drafts-")
        self.addCleanup(self.temp.cleanup)
        fixture = create_project(Path(self.temp.name), "block")
        self.root = fixture.root.parent
        loaded = load_project(self.root)
        self.session = ProjectSession(**{key: loaded[key] for key in
            ("registry", "layout", "sources", "document_theme", "project_dir")})
        self.inspector = BlockInspector(self.session)
        self.addCleanup(self.dispose)
        self.block = self.session.registry.blocks()[0]
        self.session.selection.select_block(self.block.id, source="test")
        self.before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def dispose(self):
        from PySide6.QtCore import QCoreApplication, QEvent
        self.session.shutdown()
        self.inspector.close()
        self.inspector.deleteLater()
        self.session.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def enter(self, text="Unapplied text"):
        self.inspector.content_edit.setPlainText(text)

    def test_refresh_preserves_unapplied_text_and_counts_it_without_model_or_io(self):
        before = deepcopy(self.block.to_dict())
        self.enter()
        self.assertTrue(self.session.has_unsaved_changes)
        self.assertEqual(len(self.session.editor_drafts), 1)
        self.inspector.refresh()
        self.assertEqual(self.inspector.content_edit.toPlainText(), "Unapplied text")
        self.assertEqual(self.block.to_dict(), before)
        self.assertEqual(self.session.undo_stack.count(), 0)
        self.assertFalse(self.session._save_timer.isActive())
        self.assertFalse(self.session._preview_timer.isActive())
        self.assertIsNone(self.session.compile_manager)
        self.assertEqual({p: p.read_bytes() for p in self.before}, self.before)

    def test_switch_back_retains_document_undo_and_unrelated_model_change(self):
        from app.core.blocks.registry import CreateBlockInput
        other = self.session.registry.create(CreateBlockInput(type="text", alias="other", content={"text": "other"}))
        self.inspector.content_edit.insertPlainText("draft ")
        document = self.inspector.content_edit.document()
        text = self.inspector.content_edit.toPlainText()
        self.session.selection.select_block(other.id, source="test")
        self.session.registry.rename_alias(other.id, "changed elsewhere")
        self.session.notify_model_changed("unrelated")
        self.session.selection.select_block(self.block.id, source="test")
        self.assertIs(self.inspector.content_edit.document(), document)
        self.assertEqual(self.inspector.content_edit.toPlainText(), text)
        self.inspector.content_edit.undo()
        self.assertEqual(self.inspector.content_edit.toPlainText(), self.block.content["text"])

    def test_apply_is_one_command_and_undo_does_not_recreate_pending_draft(self):
        original = self.block.content["text"]
        self.enter()
        self.inspector.apply_button.click()
        self.assertEqual(self.block.content["text"], "Unapplied text")
        self.assertEqual(self.session.undo_stack.count(), 1)
        self.assertFalse(self.session.editor_drafts)
        self.session.undo_stack.undo()
        self.assertEqual(self.block.content["text"], original)
        self.assertFalse(self.session.editor_drafts)
        self.assertEqual(self.inspector.content_edit.toPlainText(), original)

    def test_changed_target_refuses_apply_and_keeps_both_versions(self):
        self.enter()
        self.session.registry.update(self.block.id, {"content": {"text": "new model"}})
        self.session.notify_model_changed("other-editor")
        self.assertEqual(self.inspector.content_edit.toPlainText(), "Unapplied text")
        self.assertFalse(self.session.apply_editor_drafts())
        self.assertEqual(self.block.content["text"], "new model")
        self.assertEqual(len(self.session.editor_drafts), 1)
        self.assertEqual(self.session.undo_stack.count(), 0)

    def test_direct_save_and_final_do_not_apply_or_write_pending_drafts(self):
        self.enter()
        self.session.save_now()
        self.assertFalse(self.session.last_save_ok)
        self.assertIsNone(self.session.compile_final())
        self.assertIsNone(self.session.compile_manager)
        self.assertTrue(self.session.editor_drafts)
        self.assertEqual({p: p.read_bytes() for p in self.before}, self.before)

    def test_close_cancel_retains_draft_and_save_explicitly_applies_it(self):
        self.enter()
        with patch("app.gui.blocks.close_guard.QMessageBox.warning", return_value=QMessageBox.StandardButton.Cancel):
            self.assertFalse(confirm_block_close(None, self.session))
        self.assertEqual(self.inspector.content_edit.toPlainText(), "Unapplied text")
        with patch("app.gui.blocks.close_guard.QMessageBox.warning", return_value=QMessageBox.StandardButton.Save):
            self.assertTrue(confirm_block_close(None, self.session))
        self.assertEqual(load_project(self.root)["registry"].get(self.block.id).content["text"], "Unapplied text")
        self.assertFalse(self.session.has_unsaved_changes)
        self.assertIsNone(self.session.compile_manager)

    def test_batch_prechecks_all_bases_before_any_patch(self):
        base = deepcopy(self.block.to_dict())
        good = PropertyDraft("block", self.block.id, "text", base, {"text": "old"}, {"text": "new"})
        bad = replace(good, target_id="missing")
        with self.assertRaises(ValueError):
            prepare_drafts((good, bad), self.session.registry, self.session.layout)
        self.assertEqual(self.block.to_dict(), base)

    def test_heading_alias_and_level_apply_together_while_preserving_unknown_content(self):
        from app.core.blocks.registry import CreateBlockInput
        block = self.session.registry.create(CreateBlockInput(type="heading", alias="heading",
            content={"text": "original", "level": 2, "custom": {"keep": True}}))
        self.session.selection.select_block(block.id, source="test")
        self.inspector.alias_edit.setText("new heading")
        self.inspector.heading_level.setCurrentText("3")
        self.inspector.refresh()
        self.assertEqual(self.inspector.alias_edit.text(), "new heading")
        self.assertEqual(self.inspector.heading_level.currentText(), "3")
        self.assertEqual(block.alias, "heading")
        self.inspector.apply_button.click()
        self.assertEqual(block.alias, "new heading")
        self.assertEqual(block.content, {"text": "original", "level": 3, "custom": {"keep": True}})
        self.assertEqual(self.session.undo_stack.count(), 1)
        self.session.undo_stack.undo()
        self.assertEqual(block.alias, "heading")
        self.assertEqual(block.content["level"], 2)

    def test_alias_only_does_not_round_or_rewrite_image_content(self):
        from app.core.blocks.registry import CreateBlockInput
        original = {"source": "image.png", "widthMm": 12.3456, "heightMm": None,
                    "caption": "  caption  ", "custom": False}
        block = self.session.registry.create(CreateBlockInput(type="image", alias="figure", content=deepcopy(original)))
        self.session.selection.select_block(block.id, source="test")
        self.inspector.alias_edit.setText("renamed")
        self.inspector.refresh()
        self.inspector.apply_button.click()
        self.assertEqual(block.content, original)
        self.inspector.image_height.setValue(33.5)
        self.inspector.caption_edit.setText("  new caption  ")
        self.session.selection.select_block(self.block.id, source="test")
        self.session.selection.select_block(block.id, source="test")
        self.assertEqual(self.inspector.image_height.value(), 33.5)
        self.inspector.apply_button.click()
        self.assertEqual(block.content["widthMm"], 12.3456)
        self.assertEqual(block.content["heightMm"], 33.5)
        self.assertEqual(block.content["caption"], "  new caption  ")
        self.assertFalse(block.content["custom"])

    def test_deleted_target_is_recoverable_from_pending_list_and_discard_is_explicit(self):
        self.enter()
        self.session.registry.remove(self.block.id)
        self.session.selection.clear(source="test")
        self.session.notify_model_changed("deleted")
        self.assertEqual(len(self.session.editor_drafts), 1)
        self.inspector._choose_draft(1)
        self.assertEqual(self.inspector.content_edit.toPlainText(), "Unapplied text")
        self.assertIn("变化或删除", self.inspector.draft_status.text())
        self.assertFalse(self.session.apply_editor_drafts())
        with patch("app.gui.blocks.inspector.QMessageBox.warning", return_value=QMessageBox.StandardButton.Cancel):
            self.inspector.discard_button.click()
        self.assertTrue(self.session.editor_drafts)
        with patch("app.gui.blocks.inspector.QMessageBox.warning", return_value=QMessageBox.StandardButton.Discard):
            self.inspector.discard_button.click()
        self.assertFalse(self.session.editor_drafts)
        self.assertIsNone(self.session.registry.get(self.block.id))

    def test_nested_layout_draft_targets_selected_container_and_updates_panel_once(self):
        from app.core.blocks.layout import LayoutNode, Size, block_slot
        from app.gui.blocks.workspace_widget import BlockWorkspaceWidget
        child = LayoutNode(id="nested", kind="row", gap=Size(4), alignment="middle",
                           fallback={"strategy": "error", "custom": "keep"}, children=(block_slot(self.block.id),))
        outer = LayoutNode(id="outer", kind="column", gap=Size(11), children=(child,))
        self.session.layout = outer
        workspace = BlockWorkspaceWidget(self.session)
        self.addCleanup(workspace.close)
        self.session.selection.select_layout_node("nested", source="test")
        self.assertEqual(self.inspector.layout_gap.value(), 4)
        self.assertEqual(self.inspector.layout_alignment.currentText(), "middle")
        self.inspector.layout_gap.setValue(9)
        self.inspector.refresh()
        self.session.selection.select_layout_node("outer", source="test")
        self.assertEqual(self.inspector.layout_gap.value(), 11)
        self.session.selection.select_slot(child.children[0].instanceId, source="test")
        self.assertEqual(self.inspector.layout_gap.value(), 9)
        self.inspector.layout_apply.click()
        self.assertEqual(self.session.layout.gap, Size(11))
        self.assertEqual(self.session.layout.children[0].gap, Size(9))
        self.assertEqual(self.session.layout.children[0].fallback, child.fallback)
        self.assertEqual(workspace.layout_panel.layout, self.session.layout)
        self.assertEqual(self.session.undo_stack.count(), 1)
        self.session.undo_stack.undo()
        self.assertEqual(self.session.layout, outer)
        self.assertEqual(workspace.layout_panel.layout, outer)

    def test_blank_alias_refuses_apply_without_losing_other_draft_fields(self):
        self.enter()
        self.inspector.alias_edit.clear()
        before = deepcopy(self.block.to_dict())
        self.assertFalse(self.session.apply_editor_drafts())
        self.assertEqual(self.block.to_dict(), before)
        self.assertEqual(self.inspector.content_edit.toPlainText(), "Unapplied text")
        self.assertEqual(self.inspector.alias_edit.text(), "")
        self.assertEqual(self.session.undo_stack.count(), 0)

    def test_save_conflict_keeps_applied_draft_and_external_bytes(self):
        self.enter()
        path = self.root / ".icstex/blocks.json"
        winner = path.read_bytes() + b" \n"
        path.write_bytes(winner)
        with patch("app.gui.blocks.close_guard.QMessageBox.warning", return_value=QMessageBox.StandardButton.Save):
            self.assertFalse(save_block_session(None, self.session))
        self.assertEqual(path.read_bytes(), winner)
        self.assertEqual(self.block.content["text"], "Unapplied text")
        self.assertEqual(self.inspector.content_edit.toPlainText(), "Unapplied text")
        self.assertTrue(self.session.has_unsaved_changes)

    def test_save_and_final_cancel_do_not_apply_or_write(self):
        self.enter()
        original = deepcopy(self.block.to_dict())
        with patch("app.gui.blocks.close_guard.QMessageBox.warning", return_value=QMessageBox.StandardButton.Cancel):
            self.assertFalse(save_block_session(None, self.session))
            compile_block_session(None, self.session)
        self.assertEqual(self.block.to_dict(), original)
        self.assertIsNone(self.session.compile_manager)
        self.assertEqual({p: p.read_bytes() for p in self.before}, self.before)

    def test_confirmation_does_not_apply_newer_unreviewed_input(self):
        self.enter()
        original = deepcopy(self.block.to_dict())
        def choose(*_args):
            self.inspector.content_edit.setPlainText("newer input")
            return QMessageBox.StandardButton.Save
        with patch("app.gui.blocks.close_guard.QMessageBox.warning", side_effect=choose):
            self.assertFalse(save_block_session(None, self.session))
        self.assertEqual(self.block.to_dict(), original)
        self.assertEqual(self.inspector.content_edit.toPlainText(), "newer input")

    def test_late_edit_after_shutdown_is_ignored(self):
        self.enter()
        original = dict(self.session.editor_drafts)
        self.session.shutdown()
        self.inspector.content_edit.setPlainText("late input")
        self.assertEqual(self.session.editor_drafts, original)
        self.assertFalse(self.session.apply_editor_drafts())
        self.assertEqual({p: p.read_bytes() for p in self.before}, self.before)

    def test_apply_retains_reentrant_newer_input_instead_of_clearing_it(self):
        self.enter()
        def edit_again(_reason):
            self.session.model_changed.disconnect(edit_again)
            self.inspector.content_edit.setPlainText("newer reentrant draft")
        self.session.model_changed.connect(edit_again)
        self.assertTrue(self.session.apply_editor_drafts())
        self.assertEqual(self.block.content["text"], "Unapplied text")
        self.assertEqual(self.inspector.content_edit.toPlainText(), "newer reentrant draft")
        self.assertTrue(self.session.editor_drafts)
        self.assertFalse(self.session._save_timer.isActive())

    def test_two_valid_drafts_apply_and_undo_as_one_explicit_batch(self):
        from app.core.blocks.model import content_for_text
        from app.core.blocks.registry import CreateBlockInput
        other = self.session.registry.create(CreateBlockInput(type="text", alias="other", content=content_for_text("other")))
        first_text = self.block.content["text"]
        self.enter("first changed")
        self.session.selection.select_block(other.id, source="test")
        self.enter("second changed")
        self.assertEqual(len(self.session.editor_drafts), 2)
        self.assertTrue(self.session.apply_editor_drafts())
        self.assertEqual(self.session.undo_stack.count(), 1)
        self.assertEqual(self.block.content["text"], "first changed")
        self.assertEqual(other.content["text"], "second changed")
        self.session.undo_stack.undo()
        self.assertEqual(self.block.content["text"], first_text)
        self.assertEqual(other.content["text"], "other")
        self.assertFalse(self.session.editor_drafts)

    def test_batch_conflict_leaves_valid_other_draft_unapplied(self):
        from app.core.blocks.model import content_for_text
        from app.core.blocks.registry import CreateBlockInput
        other = self.session.registry.create(CreateBlockInput(type="text", alias="other", content=content_for_text("other")))
        first = deepcopy(self.block.to_dict())
        self.enter("first changed")
        self.session.selection.select_block(other.id, source="test")
        self.enter("second changed")
        self.session.registry.rename_alias(other.id, "external change")
        self.assertFalse(self.session.apply_editor_drafts())
        self.assertEqual(self.block.to_dict(), first)
        self.assertEqual(other.content["text"], "other")
        self.assertEqual(len(self.session.editor_drafts), 2)
        self.assertEqual(self.session.undo_stack.count(), 0)

    def test_layout_pt_gap_is_displayed_in_mm_and_not_rewritten_by_alignment(self):
        from app.core.blocks.layout import LayoutNode, Size
        node = LayoutNode(id="pt", gap=Size(72.27, "pt"), fallback={"strategy": "error", "custom": "keep"})
        self.session.layout = node
        self.session.selection.select_layout_node(node.id, source="test")
        self.assertEqual(self.inspector.layout_gap.value(), 25.4)
        self.inspector.layout_alignment.setCurrentText("bottom")
        self.inspector.layout_apply.click()
        self.assertEqual(self.session.layout.gap, node.gap)
        self.assertEqual(self.session.layout.fallback, node.fallback)

    def test_layout_panel_alignment_preserves_pt_gap(self):
        from app.core.blocks.layout import LayoutNode, Size
        from app.gui.blocks.layout_panel import BlockLayoutPanel
        node = LayoutNode(id="pt", gap=Size(72.27, "pt"))
        panel = BlockLayoutPanel(self.session.registry, node)
        self.addCleanup(panel.deleteLater)
        self.assertEqual(panel.gap_spin.value(), 25.4)
        panel.alignment_combo.setCurrentText("bottom")
        self.assertEqual(panel.layout.gap, node.gap)
