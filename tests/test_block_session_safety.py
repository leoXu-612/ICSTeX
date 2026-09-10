from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.blocks.model import content_for_text
from app.core.blocks.project_repository import load_project
from app.gui.blocks.close_guard import confirm_block_close
from app.gui.blocks.project_session import ProjectSession
from tests.v1_fixtures import create_project


class BlockSessionSafetyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.sample = create_project(Path(self.temp.name).resolve(), "block")
        self.root = self.sample.root.parent
        state = load_project(self.root)
        self.session = ProjectSession(**{key: state[key] for key in
            ("registry", "layout", "sources", "document_theme", "project_dir")})
        self.addCleanup(self.session.shutdown)
        self.originals = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.block = self.session.registry.blocks()[0]

    def edit(self):
        self.session.registry.update(self.block.id, {"content": content_for_text("Unsaved model draft")})
        self.session.notify_model_changed("synthetic edit")

    def test_first_edit_saves_model_and_generated_source_without_authorizing_compile(self):
        self.edit()
        self.assertTrue(self.session.has_unsaved_changes)
        self.assertTrue(self.session._save_timer.isActive())
        self.assertFalse(self.session._preview_timer.isActive())
        self.assertIsNone(self.session.compile_manager)
        self.session.save_now()
        self.assertTrue(self.session.last_save_ok, self.session.save_error)
        self.assertFalse(self.session.has_unsaved_changes)
        self.assertIn(b"Unsaved model draft", self.sample.draft_path.read_bytes())
        self.assertIn(b"Unsaved model draft", (self.root / ".icstex/blocks.json").read_bytes())

    def test_metadata_conflict_preserves_external_winner_and_pauses_auto_writes(self):
        self.edit()
        path = self.root / ".icstex/blocks.json"
        winner = self.originals[path] + b" \n"
        path.write_bytes(winner)
        self.session.save_now()
        self.assertFalse(self.session.last_save_ok)
        self.assertTrue(self.session.has_unsaved_changes)
        self.assertIn("内存草稿", self.session.save_error)
        self.assertEqual(path.read_bytes(), winner)
        self.assertIn("Unsaved model draft", str(self.block.content))
        self.session.request_save("later edit")
        self.session.request_preview("later edit")
        self.assertFalse(self.session._save_timer.isActive())
        self.assertFalse(self.session._preview_timer.isActive())

    def test_saved_model_reopens_with_owned_generated_source_and_can_compile(self):
        self.edit()
        self.session.save_now()
        self.assertTrue(self.session.last_save_ok, self.session.save_error)
        self.session.shutdown()
        state = load_project(self.root)
        reopened = ProjectSession(**{key: state[key] for key in
            ("registry", "layout", "sources", "document_theme", "project_dir")})
        self.addCleanup(reopened.shutdown)
        self.assertFalse(reopened.save_error, reopened.save_error)
        self.assertIsNone(reopened.compile_manager)
        self.assertIsNotNone(reopened.assemble_latex())
        self.assertIn(b"Unsaved model draft", self.sample.draft_path.read_bytes())

    def test_manual_generated_edit_blocks_final_without_creating_compiler(self):
        self.sample.draft_path.write_bytes(b"manually edited TeX")
        self.assertIsNone(self.session.compile_final())
        self.assertIsNone(self.session.compile_manager)
        self.assertEqual(self.sample.draft_path.read_bytes(), b"manually edited TeX")

    def test_cancel_close_keeps_draft_and_resumes_pending_save(self):
        self.edit()
        def cancel(*_args):
            self.assertFalse(self.session._save_timer.isActive())
            self.assertFalse(self.session._preview_timer.isActive())
            return QMessageBox.StandardButton.Cancel
        with patch("app.gui.blocks.close_guard.QMessageBox.warning", side_effect=cancel):
            self.assertFalse(confirm_block_close(None, self.session))
        self.assertFalse(self.session._closed)
        self.assertTrue(self.session._save_timer.isActive())
        self.assertTrue(self.session.has_unsaved_changes)
        self.assertEqual({p: p.read_bytes() for p in self.originals}, self.originals)

    def test_save_close_persists_model_without_compiling(self):
        self.edit()
        with patch("app.gui.blocks.close_guard.QMessageBox.warning", return_value=QMessageBox.StandardButton.Save):
            self.assertTrue(confirm_block_close(None, self.session))
        self.assertTrue(self.session.last_save_ok, self.session.save_error)
        self.assertFalse(self.session.has_unsaved_changes)
        self.assertFalse(self.session._save_timer.isActive())
        self.assertIsNone(self.session.compile_manager)
        restored = load_project(self.root)["registry"].get(self.block.id)
        self.assertEqual(restored.content, self.block.content)

    def test_failed_save_refuses_close_and_retains_both_sides(self):
        self.edit()
        path = self.root / ".icstex/sources.json"
        path.write_bytes(b'{"sources":[], "external":true}')
        with patch("app.gui.blocks.close_guard.QMessageBox.warning",
                   side_effect=[QMessageBox.StandardButton.Save, QMessageBox.StandardButton.Ok]):
            self.assertFalse(confirm_block_close(None, self.session))
        self.assertTrue(self.session.has_unsaved_changes)
        self.assertFalse(self.session._closed)
        self.assertEqual(path.read_bytes(), b'{"sources":[], "external":true}')

    def test_confirmed_discard_and_shutdown_prevent_late_save_callbacks(self):
        self.edit()
        with patch("app.gui.blocks.close_guard.QMessageBox.warning", return_value=QMessageBox.StandardButton.Discard):
            self.assertTrue(confirm_block_close(None, self.session))
        self.session.shutdown()
        self.session.save_now()
        self.session.request_save("late")
        self.session._fire_preview()
        self.assertFalse(self.session._save_timer.isActive())
        self.assertFalse(self.session._preview_timer.isActive())
        self.assertEqual({p: p.read_bytes() for p in self.originals}, self.originals)

    def test_stopping_compile_does_not_discard_or_close_the_session(self):
        self.edit()
        self.session.stop_compile()
        self.assertFalse(self.session._closed)
        self.assertTrue(self.session.has_unsaved_changes)
        self.assertTrue(self.session._save_timer.isActive())

    def test_unknown_table_draft_is_not_replaced_by_an_empty_table(self):
        from app.core.blocks.registry import BlockRegistry, CreateBlockInput
        registry = BlockRegistry()
        block = registry.create(CreateBlockInput(type="table", alias="legacy", content={"text": "Legacy table bytes"}))
        original = dict(block.content)
        session = ProjectSession(registry=registry, project_dir=Path(self.temp.name) / "new-project")
        self.addCleanup(session.shutdown)
        session.save_now()
        self.assertFalse(session.last_save_ok)
        self.assertEqual(block.content, original)
        self.assertFalse((Path(self.temp.name) / "new-project").exists())

    def test_visible_final_request_uses_background_manager(self):
        from app.core.compiler import CompileManager, BuildPurpose
        with patch.object(CompileManager, "compile_async") as async_, \
             patch.object(CompileManager, "compile_now") as sync:
            self.session.request_final()
            async_.assert_called_once_with(BuildPurpose.FINAL)
            sync.assert_not_called()
        self.assertTrue(self.session._compile_authorized)
