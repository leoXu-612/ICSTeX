from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
from unittest import TestCase
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtWidgets import QApplication

from app.core.latex_tools import LaTeXToolchain
from app.core.settings import AppSettings
from app.core.submission_check import CheckStatus, check_submission
from app.gui.main_window import MainWindow
from tests.v1_fixtures import create_project


def wait_until(predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return
        time.sleep(0.002)
    raise AssertionError("Timed out waiting for submission check")


class SubmissionCheckGuiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.sample = create_project(self.base)
        settings = AppSettings(QSettings(str(self.base / "qa.ini"), QSettings.Format.IniFormat))
        self.window = MainWindow(settings_store=settings)
        self.window.auto_compile_action.setChecked(False)
        self.window.toolchain = LaTeXToolchain(None, None)
        self.window.project_files.set_project_root(self.sample.root.parent)
        self.window.open_file(self.sample.root)
        wait_until(lambda: not self.window.dependencies.is_busy and not self.window.word_counts.is_busy)
        self.controller = self.window.readiness
        self.panel = self.window.submission_panel

    def tearDown(self):
        if self.window.block_session is not None:
            self.window.block_session.shutdown()  # Explicitly discard synthetic drafts during cleanup.
        for tab in self.window.tabs.values():
            self.window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        self.window.close()
        self.app.processEvents()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.temp.cleanup()

    def check(self):
        self.controller.show()
        wait_until(lambda: not self.controller.is_busy)
        self.assertIsNotNone(self.panel.report, self.panel.summary.text())
        return self.panel.report

    def test_refresh_has_no_save_compile_or_network_and_displays_actual_evidence(self):
        before = {p: p.read_bytes() for p in self.sample.root.parent.rglob("*") if p.is_file()}
        with patch.object(self.window.documents, "flush_root_documents") as save, \
             patch.object(self.window, "compile_current") as compile_, \
             patch("urllib.request.urlopen") as network:
            report = self.check()
            save.assert_not_called()
            compile_.assert_not_called()
            network.assert_not_called()
        self.assertEqual(self.panel.tree.topLevelItemCount(), len(report.items))
        self.assertIn(report.input_id, self.panel.detail.toPlainText())
        self.assertEqual(before, {p: p.read_bytes() for p in self.sample.root.parent.rglob("*") if p.is_file()})

    def test_profile_edit_is_explicit_and_updates_word_target_without_source_writes(self):
        from app.gui.project_profile_dialog import ProjectProfileDialog
        from app.core.project_profile import PROFILE_PATH, load_profile
        root = self.sample.root.parent
        before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        with patch.object(self.window, "compile_current") as compile_, \
             patch.object(self.window.documents, "flush_root_documents") as save, \
             patch("urllib.request.urlopen") as network:
            cancelled = ProjectProfileDialog(root, self.window)
            cancelled.word_max.setText("3")
            cancelled.reject()
            self.assertFalse((root / PROFILE_PATH).exists())
            dialog = ProjectProfileDialog(root, self.window)
            dialog.word_max.setText("0")
            dialog.resources.setChecked(False)
            dialog.accept()
            self.assertIsNotNone(dialog.saved_snapshot, dialog.error.text())
            compile_.assert_not_called()
            save.assert_not_called()
            network.assert_not_called()
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        report = self.check()
        rules = {item.rule_id: item for item in report.items}
        self.assertEqual(rules["word_target"].status, CheckStatus.FAIL)
        self.assertEqual(rules["resources"].status, CheckStatus.NOT_APPLICABLE)
        self.assertEqual(rules["final_build"].status, CheckStatus.UNKNOWN)
        self.assertIn("输入与 FINAL", rules["resources"].reason)
        disabled = ProjectProfileDialog(root, self.window)
        disabled.enabled.setChecked(False)
        disabled.accept()
        self.assertEqual(load_profile(root).profile.word_max, 0)
        self.controller.external_changed(str(root / PROFILE_PATH))
        report = self.check()
        self.assertEqual(next(i for i in report.items if i.rule_id == "word_target").status, CheckStatus.NOT_APPLICABLE)
        self.assertEqual(next(i for i in report.items if i.rule_id == "resources").status, CheckStatus.PASS)

    def test_profile_dialog_preserves_conflicting_draft_and_invalid_format(self):
        from app.gui.project_profile_dialog import ProjectProfileDialog
        from app.core.project_profile import PROFILE_PATH, ProjectProfile, load_profile, save_profile
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        root = self.sample.root.parent
        dialog = ProjectProfileDialog(root, self.window)
        dialog.word_max.setText("999")
        winner = save_profile(root, ProjectProfile(word_max=42), expected=load_profile(root))
        dialog.accept()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertEqual(dialog.word_max.text(), "999")
        self.assertIn("未保存", dialog.error.text())
        self.assertEqual(load_profile(root), winner)
        (root / PROFILE_PATH).write_bytes(b'{"version":999}')
        invalid = ProjectProfileDialog(root, self.window)
        self.assertFalse(invalid.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled())
        self.assertTrue(invalid.error.text())
        report = self.check()
        for rule in ("project_profile", "word_target"):
            self.assertEqual(next(i for i in report.items if i.rule_id == rule).status, CheckStatus.UNKNOWN)

    def test_actual_profile_creation_event_invalidates_existing_report(self):
        from app.core.project_profile import PROFILE_PATH, ProjectProfile, load_profile, save_profile
        self.check()
        root = self.sample.root.parent
        self.assertIn(root / PROFILE_PATH, self.window.file_watcher._files)
        save_profile(root, ProjectProfile(word_max=99), expected=load_profile(root))
        wait_until(lambda: self.panel.report is None)

    def test_profile_action_targets_visible_block_instead_of_hidden_source(self):
        from app.gui.project_profile_dialog import show_project_profile
        sample, _ = self.install_block()
        with patch("app.gui.project_profile_dialog.ProjectProfileDialog") as dialog:
            show_project_profile(self.window)
        self.assertEqual(dialog.call_args.args[0], sample.root.parent)

    def test_profile_shortcut_is_available_from_check_evidence(self):
        report = self.check()
        index = next(n for n, item in enumerate(report.items) if item.rule_id == "project_profile")
        self.panel.tree.setCurrentItem(self.panel.tree.topLevelItem(index))
        self.assertEqual(self.panel.action_button.text(), "项目配置")
        self.assertTrue(self.panel.action_button.isEnabled())
        with patch("app.gui.main_window_signals.show_project_profile") as show:
            self.panel.action_button.click()
        show.assert_called_once_with(self.window)

    def test_edit_invalidates_immediately_without_rechecking_or_scanning(self):
        self.check()
        with patch.object(self.window.documents, "schedule_save"), \
             patch("app.gui.submission_check_controller.check_submission") as analyze:
            self.window.current_tab().editor.insertPlainText("draft")
            self.assertIsNone(self.panel.report)
            self.assertIn("待重新检查", self.panel.summary.text())
            analyze.assert_not_called()

    def test_reconciliation_does_not_resolve_roots_or_read_source_files(self):
        self.check()
        with patch.object(self.window, "_compile_root_for_tab", side_effect=AssertionError("disk resolution")):
            self.controller.reconcile()
        self.assertIsNotNone(self.panel.report)

    def test_external_event_and_root_switch_clear_previous_report(self):
        first = self.check()
        self.controller.external_changed(str(self.sample.draft_path))
        self.assertIsNone(self.panel.report)
        self.check()
        other = create_project(self.base, "single")
        self.window.project_files.set_project_root(other.root.parent)
        self.window.open_file(other.root)
        self.assertIsNone(self.panel.report)
        wait_until(lambda: not self.window.dependencies.is_busy and not self.window.word_counts.is_busy)
        second = self.check()
        self.assertNotEqual(first.input_id, second.input_id)
        self.assertTrue(all(item.scope == str(other.root) for item in second.items))

    def test_late_callback_after_edit_or_cancel_is_not_published(self):
        entered, release, done = threading.Event(), threading.Event(), threading.Event()
        def delayed(request, cancelled):
            entered.set()
            release.wait(5)
            try:
                return check_submission(request, cancelled)
            finally:
                done.set()
        with patch("app.gui.submission_check_controller.check_submission", side_effect=delayed):
            self.controller.request()
            wait_until(entered.is_set)
            self.controller.cancel()
            release.set()
            wait_until(lambda: done.is_set() and not self.controller.is_busy)
        self.assertIsNone(self.panel.report)

    def test_worker_failure_is_unknown_and_refresh_recovers(self):
        with self.assertLogs("app.gui.submission_check_controller", level="ERROR"), \
             patch("app.gui.submission_check_controller.check_submission", side_effect=ValueError("fixture")):
            self.controller.request()
            wait_until(lambda: not self.controller.is_busy)
        self.assertIsNone(self.panel.report)
        self.assertIn("未知", self.panel.summary.text())
        self.check()

    def test_navigation_uses_child_location_and_stale_actions_do_nothing(self):
        child = self.sample.draft_path
        generation = self.window.dependencies.generation_for(self.sample.root)
        child.write_text(child.read_text() + "\\cite{missing}\n")
        # Await the actual polling event, not an extra synthetic duplicate event.
        wait_until(lambda: self.window.dependencies.generation_for(self.sample.root) > generation)
        wait_until(lambda: not self.window.dependencies.is_busy and not self.window.word_counts.is_busy)
        report = self.check()
        index = next(i for i, item in enumerate(report.items) if item.rule_id == "citation_missing")
        self.controller.act(index)
        self.assertEqual(self.window.current_tab().path, child)
        self.assertEqual(self.window.current_tab().editor.textCursor().blockNumber(), 3)
        with patch.object(self.window, "open_file") as open_file:
            self.controller.act(index)
            open_file.assert_not_called()

    def test_close_cancels_worker_and_does_not_receive_a_late_result(self):
        entered, release, done = threading.Event(), threading.Event(), threading.Event()
        def delayed(request, cancelled):
            entered.set()
            release.wait(5)
            try:
                return check_submission(request, cancelled)
            finally:
                done.set()
        with patch("app.gui.submission_check_controller.check_submission", side_effect=delayed):
            self.controller.request()
            wait_until(entered.is_set)
            self.window.close()
            self.assertTrue(self.controller._closed)
            release.set()
            wait_until(done.is_set)
        self.assertIsNone(self.panel.report)

    def install_block(self):
        from app.core.blocks.project_repository import load_project
        from app.gui.blocks.project_session import ProjectSession
        from app.gui.block_mode import _install_session, _set_block_mode
        sample = create_project(self.base, "block")
        loaded = load_project(sample.root.parent)
        session = ProjectSession(**{key: loaded[key] for key in
                                 ("registry", "layout", "sources", "document_theme", "project_dir")})
        _install_session(self.window, session)
        _set_block_mode(self.window, True)
        return sample, session

    def test_block_check_binds_visible_project_and_never_compiles_or_saves(self):
        sample, session = self.install_block()
        before = {p: p.read_bytes() for p in sample.root.parent.rglob("*") if p.is_file()}
        with patch.object(session, "save_now") as save, patch.object(session, "compile_final") as compile_:
            report = self.check()
            save.assert_not_called()
            compile_.assert_not_called()
        self.assertTrue(all(item.scope == str(sample.root) for item in report.items))
        self.assertTrue(self.window.block_mode_action.isChecked())
        self.assertIs(self.controller._block_dock.widget(), self.panel)
        self.assertEqual(self.window.bottom_tabs.indexOf(self.panel), -1)
        rules = {item.rule_id: item for item in report.items}
        self.assertEqual(rules["saved"].status, CheckStatus.PASS)
        self.assertEqual(rules["block_generated"].status, CheckStatus.PASS)
        self.assertEqual(rules["final_build"].status, CheckStatus.UNKNOWN)
        self.assertIn("XeLaTeX", rules["toolchain"].reason)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_pending_property_drafts_invalidate_checks_and_cannot_pass_saved_state(self):
        sample, session = self.install_block()
        block = session.registry.blocks()[0]
        session.selection.select_block(block.id, source="test")
        self.check()
        key = self.controller._key()
        before = {p: p.read_bytes() for p in sample.root.parent.rglob("*") if p.is_file()}
        self.window.block_inspector.content_edit.setPlainText("unapplied property text")
        self.assertNotEqual(key, self.controller._key())
        self.assertIsNone(self.panel.report)
        with patch.object(session, "save_now") as save, patch.object(session, "request_final") as compile_:
            report = self.check()
            save.assert_not_called()
            compile_.assert_not_called()
        rules = {item.rule_id: item for item in report.items}
        self.assertEqual(rules["saved"].status, CheckStatus.FAIL)
        self.assertIn("尚未应用", rules["saved"].reason)
        self.assertNotEqual(rules["pdf_current"].status, CheckStatus.PASS)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        session.discard_editor_draft(("block", block.id))
        self.assertEqual(self.window.block_inspector.content_edit.toPlainText(), block.content["text"])
        self.assertIsNone(self.panel.report)
        rules = {item.rule_id: item for item in self.check().items}
        self.assertEqual(rules["saved"].status, CheckStatus.PASS)

    def test_workspace_block_header_and_actions_do_not_borrow_hidden_source(self):
        from app.gui.block_mode import _set_block_mode
        sample, session = self.install_block()
        with patch.object(session, "save_now") as save, patch.object(session, "compile_final") as compile_:
            self.window.workspace.refresh()
            save.assert_not_called()
            compile_.assert_not_called()
        self.assertIn(sample.root.parent.name, self.window.workspace.title.full_text)
        self.assertIn("XeLaTeX", self.window.workspace.details.full_text)
        self.assertTrue(self.window.engine_selector.isHidden())
        self.assertFalse(self.window.compile_action.isEnabled())
        self.assertFalse(self.window.save_action.isEnabled())
        self.assertIs(self.window.workspace.next_button.defaultAction(), self.window.block_compile_action)
        self.window.workspace._block_navigation(2)
        self.assertEqual(self.window.block_nav.tabs.currentIndex(), 2)
        self.window.show()
        for width in (1080, 1200, 1120):
            self.window.resize(width, 800)
            self.app.processEvents()
            self.assertFalse(self.window.engine_toolbar_action.isVisible())
            self.assertFalse(self.window.auto_compile_toolbar_action.isVisible())
            self.assertFalse(self.window.engine_selector.isVisible())
            self.assertFalse(self.window.auto_compile_toggle.isVisible())
        _set_block_mode(self.window, False)
        self.app.processEvents()
        self.assertFalse(self.window.engine_selector.isHidden())
        self.assertTrue(self.window.compile_action.isEnabled())
        self.assertTrue(self.window.save_action.isEnabled())

    def test_closing_block_project_restores_source_controls_and_context(self):
        from app.gui.block_mode import _close_block_project
        _sample, session = self.install_block()
        _close_block_project(self.window)
        self.window.show()
        self.app.processEvents()
        self.assertIsNone(self.window.block_session)
        self.assertFalse(self.window.block_mode_action.isChecked())
        self.assertFalse(self.window.engine_selector.isHidden())
        self.assertFalse(self.window.auto_compile_toggle.isHidden())
        self.assertTrue(self.window.auto_compile_action.isEnabled())
        self.assertTrue(self.window.save_action.isEnabled())
        self.assertTrue(self.window.compile_action.isEnabled())
        self.assertIn(self.sample.root.parent.name, self.window.workspace.title.full_text)
        self.assertFalse(session._save_timer.isActive())

    def test_block_model_and_save_state_use_content_not_pending_reason(self):
        from app.core.blocks.model import content_for_text
        sample, session = self.install_block()
        self.check()
        with patch.object(session, "request_save"), patch.object(session, "request_preview"):
            session.registry.update(session.registry.blocks()[0].id, {"content": content_for_text("New draft")})
            session.notify_model_changed("qa")
        self.assertIsNone(self.panel.report)
        report = self.check()
        self.assertEqual(next(i for i in report.items if i.rule_id == "saved").status, CheckStatus.FAIL)
        # Guarded save keeps metadata/generated source together, without compiling.
        session._pending_save_reason = "old-reason-retained-by-existing-session"
        session.save_now()
        report = self.check()
        self.assertTrue(session._pending_save_reason)
        self.assertEqual(next(i for i in report.items if i.rule_id == "saved").status, CheckStatus.PASS)
        self.assertEqual(next(i for i in report.items if i.rule_id == "block_generated").status, CheckStatus.PASS)
        self.assertIn("New draft", sample.draft_path.read_text())
        self.assertIsNone(session.compile_manager)
        self.assertNotEqual(next(i for i in report.items if i.rule_id == "final_build").status, CheckStatus.PASS)

    def test_block_metadata_external_event_invalidates_and_mode_restores_same_panel(self):
        from app.gui.block_mode import _close_block_project, _set_block_mode
        sample, session = self.install_block()
        self.check()
        metadata = sample.root.parent / ".icstex/sources.json"
        self.assertIn(metadata, self.window.file_watcher._files)
        metadata.write_bytes(metadata.read_bytes() + b" ")
        wait_until(lambda: self.panel.report is None)
        self.check()
        _set_block_mode(self.window, False)
        self.assertIsNone(self.panel.report)
        self.assertGreaterEqual(self.window.bottom_tabs.indexOf(self.panel), 0)
        report = self.check()
        self.assertTrue(all(item.scope == str(self.sample.root) for item in report.items))
        _close_block_project(self.window)
        self.assertNotIn(metadata, self.window.file_watcher._files)

    def test_block_late_result_after_mode_switch_is_discarded(self):
        from app.gui.block_mode import _set_block_mode
        self.install_block()
        entered, release = threading.Event(), threading.Event()
        def delayed(request, cancelled):
            entered.set()
            release.wait(5)
            return check_submission(request, cancelled)
        with patch("app.gui.submission_check_controller.check_submission", side_effect=delayed):
            self.controller.request()
            wait_until(entered.is_set)
            _set_block_mode(self.window, False)
            release.set()
            wait_until(lambda: not self.controller.is_busy)
        self.assertIsNone(self.panel.report)

    def test_block_check_ignores_unrelated_hidden_source_revision(self):
        self.install_block()
        self.check()
        before = self.controller._key()
        tab = self.window.current_tab()
        with patch.object(self.window.documents, "schedule_save"):
            tab.editor.blockSignals(True)
            try:
                tab.editor.insertPlainText("Unrelated hidden source")
            finally:
                tab.editor.blockSignals(False)
        self.assertEqual(before, self.controller._key())
        self.controller.reconcile()
        self.assertIsNotNone(self.panel.report)

    def fake_block_compile(self, session, purpose=None, outcome=None):
        from app.core.compiler import BuildPurpose, CompileOutcome
        purpose = purpose or BuildPurpose.FINAL
        outcome = outcome or CompileOutcome.SUCCESS
        session._ensure_compile_manager(session.project_dir / "main.tex")
        manager = session.compile_manager
        def run(build_id, selected, **_kwargs):
            output = manager.output_dir_for(selected)
            output.mkdir(parents=True, exist_ok=True)
            manager.pdf_file_for(selected).write_bytes(b"%PDF-1.4 synthetic unit fixture")
            return manager._simple_result(build_id, outcome, purpose=selected,
                                          returncode=0 if outcome is CompileOutcome.SUCCESS else 1, stderr="")
        with patch.object(manager, "_run_compile", side_effect=run), \
             patch.object(self.window.pdf_panel, "load_pdf"):
            if purpose is BuildPurpose.FINAL:
                return session.compile_final()
            manager.set_input_revision(session._revision)
            return manager.compile_now(purpose)

    def test_block_final_is_bound_to_actual_job_once_and_preview_does_not_replace_it(self):
        from app.core.compiler import BuildPurpose
        sample, session = self.install_block()
        finished = []
        session.compile_finished.connect(finished.append)
        result = self.fake_block_compile(session)
        self.assertEqual(len(finished), 1)
        self.assertEqual(result.job_key.source_revision, session._revision)
        self.assertEqual(session.final_evidence.build_id, result.build_id)
        self.assertTrue(result.input_evidence.stable)
        report = self.check()
        for rule in ("saved", "block_generated", "final_build", "pdf_current"):
            self.assertEqual(next(i for i in report.items if i.rule_id == rule).status, CheckStatus.PASS, rule)
        self.fake_block_compile(session, purpose=BuildPurpose.PREVIEW)
        self.assertEqual(session.final_evidence.build_id, result.build_id)
        self.assertFalse(session.final_is_running)
        self.assertEqual(self.window.pdf_state.record_for(sample.root).latest_build_id, None)

    def test_block_changed_revision_failed_final_and_late_closed_result_cannot_pass(self):
        from app.core.compiler import CompileOutcome
        _, session = self.install_block()
        result = self.fake_block_compile(session)
        with patch.object(session, "request_save"), patch.object(session, "request_preview"):
            session.notify_model_changed("new model revision")
        self.assertIsNone(self.window.pdf_panel.current_pdf)
        report = self.check()
        self.assertEqual(next(i for i in report.items if i.rule_id == "final_build").status, CheckStatus.FAIL)
        self.fake_block_compile(session, outcome=CompileOutcome.LATEX_ERROR)
        report = self.check()
        self.assertEqual(next(i for i in report.items if i.rule_id == "final_build").status, CheckStatus.FAIL)
        current = session.final_evidence
        session._on_compile_finished(result)
        self.assertEqual(session.final_evidence, current, "older callback cannot replace latest failed evidence")
        finished = []
        session.compile_finished.connect(finished.append)
        from dataclasses import replace
        late = replace(result, build_id=session._latest_build_id + 1)
        session._accept_compile_started(late.job_key, late.build_id)
        session.shutdown()
        session._on_compile_finished(late)
        self.assertFalse(finished)

    def test_background_block_compile_cannot_replace_source_pdf_or_enable_wrong_export(self):
        from app.gui.block_mode import _set_block_mode
        self.check()
        old_path = self.window.pdf_panel.current_pdf
        _, session = self.install_block()
        self.assertIsNone(self.window.pdf_panel.current_pdf, "entering Block must clear unrelated source PDF")
        self.assertFalse(self.window.export_pdf_action.isEnabled())
        _set_block_mode(self.window, False)
        self.fake_block_compile(session)
        self.assertEqual(self.window.pdf_panel.current_pdf, old_path)
        self.assertFalse(self.window.block_mode_action.isChecked())

    def test_separate_windows_do_not_publish_checks_into_each_other(self):
        other = create_project(self.base, "single")
        settings = AppSettings(QSettings(str(self.base / "peer.ini"), QSettings.Format.IniFormat))
        peer = MainWindow(settings_store=settings)
        peer.auto_compile_action.setChecked(False)
        peer.toolchain = LaTeXToolchain(None, None)
        try:
            peer.project_files.set_project_root(other.root.parent)
            peer.open_file(other.root)
            wait_until(lambda: not peer.dependencies.is_busy and not peer.word_counts.is_busy)
            report = self.check()
            peer.readiness.show()
            wait_until(lambda: not peer.readiness.is_busy)
            self.assertIs(self.panel.report, report)
            self.assertTrue(all(item.scope == str(other.root) for item in peer.submission_panel.report.items))
            peer.readiness.cancel()
            self.assertIs(self.panel.report, report)
        finally:
            peer.close()
