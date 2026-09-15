from __future__ import annotations

import os
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt, QEvent
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QToolBar

from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.theme import (
    CJK_SANS_FONT_CANDIDATES,
    CJK_SERIF_FONT_CANDIDATES,
    COLOR_EDITOR,
    COLOR_SYNTAX_COMMENT,
    COLOR_SYNTAX_OPTION,
    COLOR_TEXT_FAINT,
    LATIN_MONO_FONT_CANDIDATES,
    UI_LATIN_SANS_FONT_CANDIDATES,
    apply_theme,
    editor_font,
    heading_font,
    stylesheet,
    ui_font,
)


_TEMP = TemporaryDirectory()
_COUNTER = count()


def _app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
        apply_theme(instance)
    return instance


class ModalWorkflowKeyboardTests(TestCase):
    """Actual focus traversal; synthetic FINAL evidence is used only for layout."""

    def setUp(self):
        from tests.test_gui_editor import isolated_settings
        from tests.v1_fixtures import create_project
        self.application = _app()
        self.temp = TemporaryDirectory(prefix="icstex-modal-keyboard-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.sample = create_project(self.home)
        self.window = MainWindow(settings_store=isolated_settings())
        self.previous_scale = self.application.ui_scale_manager.scale
        self.window.save_debounce_ms = 3600000
        self.window.auto_compile_action.setChecked(False)
        self.window.project_files.set_project_root(self.sample.root.parent)
        self.window.open_file(self.sample.root)
        self.dialogs = []
        self.addCleanup(self.dispose)

    def wait(self, predicate):
        import time
        deadline = time.monotonic() + 8
        while not predicate() and time.monotonic() < deadline:
            self.application.processEvents()
            # Match the worker-backed workflow tests: let Python I/O workers
            # progress as well as delivering their queued Qt result signals.
            time.sleep(0.003)
        self.assertTrue(predicate())

    def dispose(self):
        for dialog in self.dialogs:
            if hasattr(dialog, "cancel"):
                dialog.cancel.set()
                self.wait(lambda: not dialog.busy)
            dialog.reject()
            dialog.deleteLater()
        for tab in self.window.tabs.values():
            self.window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        self.window.close()
        self.window.deleteLater()
        self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.application.ui_scale_manager.apply_scale(self.previous_scale)

    def traverse(self, dialog, targets):
        from PySide6.QtCore import QPoint, QRect
        from PySide6.QtWidgets import QAbstractItemView, QPlainTextEdit, QTextEdit
        from PySide6.QtGui import QTextCursor
        dialog.show()
        for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
            with self.subTest(dialog=type(dialog).__name__, scale=scale):
                self.application.ui_scale_manager.apply_scale(scale)
                dialog.resize(900, 640)
                QTest.qWait(30)
                self.assertLessEqual(dialog.height(), 640)
                self.assertLessEqual(dialog.width(), 900)
                text_before = {w: w.toPlainText() for w in dialog.findChildren(QPlainTextEdit)
                               if not w.isReadOnly()}
                targets[0].setFocus(Qt.FocusReason.TabFocusReason)
                QTest.qWait(10)
                for key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                    visited = set()
                    trace = []
                    for _ in range(80):
                        current = self.application.focusWidget()
                        self.assertIsNotNone(current)
                        trace.append(type(current).__name__ + ":" + current.accessibleName())
                        if current in targets:
                            visited.add(current)
                            surface, rect = current, current.rect()
                            if isinstance(current, QAbstractItemView):
                                surface = current.viewport()
                                rect = current.visualRect(current.currentIndex()) if current.currentIndex().isValid() else QRect(0, 0, 16, 16)
                            elif isinstance(current, (QPlainTextEdit, QTextEdit)):
                                surface = current.viewport()
                                cursor = current.textCursor()
                                rect = current.cursorRect(cursor)
                            self.assertTrue(surface.visibleRegion().contains(rect), (key, trace, rect))
                            bounds = QRect(surface.mapTo(dialog, rect.topLeft()), rect.size())
                            self.assertTrue(dialog.rect().contains(bounds), (key, trace, bounds))
                        if visited == set(targets):
                            break
                        QTest.keyClick(current, key)
                        QTest.qWait(5)
                        self.assertEqual(text_before, {w: w.toPlainText() for w in text_before},
                                         "Tab traversal must not edit a form field")
                    self.assertEqual(visited, set(targets), (key, trace))
                self.assertEqual(text_before, {w: w.toPlainText() for w in text_before})

    def test_profile_fields_and_actions_are_reachable_without_inserting_tabs(self):
        from PySide6.QtWidgets import QDialogButtonBox
        from app.gui.project_profile_dialog import ProjectProfileDialog
        dialog = ProjectProfileDialog(self.sample.root.parent, self.window)
        self.dialogs.append(dialog)
        self.traverse(dialog, [dialog.enabled, dialog.template, dialog.engine, dialog.directories,
            dialog.word_min, dialog.word_max, dialog.resources, dialog.references,
            dialog.buttons.button(QDialogButtonBox.StandardButton.Save),
            dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)])

    def test_task_primary_button_rendering_states_are_visible_without_triggering_actions(self):
        import json
        from PySide6.QtTest import QSignalSpy
        from PySide6.QtWidgets import QPushButton
        from app.core.environment_doctor import EnvironmentReport
        from app.gui.submission_check_panel import SubmissionCheckPanel
        from app.gui.submission_delivery_dialog import SubmissionDeliveryDialog
        from app.gui.project_checkpoint_dialog import ProjectCheckpointDialog
        from app.gui.project_recovery_dialog import RecoveryDraftDialog
        from app.gui.project_migration_dialog import ProjectMigrationDialog
        from app.gui.block_write_recovery_dialog import BlockWriteRecoveryDialog
        from app.gui.blocks.project_session import ProjectSession
        from app.gui.blocks.workspace_widget import BlockWorkspaceWidget
        from app.gui.project_panels import ReferencesPanel, HistoryPanel, ImagesPanel
        from app.gui.insert_panel import TemplatesPanel, TableDialog
        from app.gui.diagnostics_panel import DiagnosticsPanel
        from app.gui.environment_doctor_dialog import EnvironmentDoctorDialog
        session = ProjectSession()
        self.addCleanup(session.shutdown)
        self.addCleanup(session.deleteLater)
        surfaces = [
            ("submission", SubmissionCheckPanel(), "action_button"),
            ("delivery", SubmissionDeliveryDialog(self.window), "review_button"),
            ("checkpoint", ProjectCheckpointDialog(self.window, restore=True), "action_button"),
            ("recovery", RecoveryDraftDialog(self.window), "apply_button"),
            ("migration", ProjectMigrationDialog(self.window), "action_button"),
            ("write-recovery", BlockWriteRecoveryDialog(self.window), "action_button"),
            ("block", BlockWorkspaceWidget(session), "preview_button"),
            ("references", ReferencesPanel(), "insert_button"),
            ("history", HistoryPanel(), "restore_button"),
            ("images", ImagesPanel(), "insert_button"),
            ("templates", TemplatesPanel(), None),
            ("table", TableDialog(self.window), None),
            ("diagnostics", DiagnosticsPanel(), "fix_button"),
            ("environment", EnvironmentDoctorDialog(
                EnvironmentReport("ICSTeX", "synthetic", "Test system", "Test Python", (), ()), self.window), "copy_button"),
        ]
        original = self.sample.root.read_bytes()
        rows = []
        for _, owner, _ in surfaces:
            self.addCleanup(owner.deleteLater)
            self.addCleanup(owner.close)
        for scale in (.9, 1., 1.1, 1.25, 1.5):
            self.application.ui_scale_manager.apply_scale(scale)
            for name, owner, attribute in surfaces:
                button = getattr(owner, attribute) if attribute else owner.findChild(QPushButton, "primaryButton")
                self.assertIsNotNone(button, name)
                owner.setWindowTitle(f"ICSTeX - BUTTON RENDER TEST - {name}")
                owner.resize(980, 720)
                owner.show()
                owner.activateWindow()
                if self.application.platformName() == "cocoa":
                    self.wait(lambda: owner.isActiveWindow() and owner.windowHandle() is not None
                              and owner.windowHandle().isExposed())
                for _ in range(6):
                    self.application.processEvents()
                enabled = button.isEnabled()
                clicked = QSignalSpy(button.clicked)
                # Appearance-only state simulation; never execute a gated action or
                # treat this as proof of readiness, publication or restored content.
                button.setEnabled(True)
                button.clearFocus()
                for _ in range(6):
                    self.application.processEvents()
                geometry = button.geometry()
                normal = button.grab().toImage()
                capture = os.environ.get("ICSTEX_TASK_BUTTON_CAPTURE")
                if capture:
                    directory = Path(capture)
                    directory.mkdir(parents=True, exist_ok=True)
                    owner.grab().save(str(directory / f"{scale:g}-{name}-render-normal.png"))
                button.setFocus(Qt.FocusReason.TabFocusReason)
                self.application.processEvents()
                focused = button.grab().toImage()
                focus_owned = button.hasFocus()
                button.clearFocus()
                button.setDown(True)
                self.application.processEvents()
                pressed = button.grab().toImage()
                button.setDown(False)
                button.setEnabled(False)
                self.application.processEvents()
                disabled = button.grab().toImage()
                rows.append({"name": name, "scale": scale, "window_active": owner.isActiveWindow(),
                             "focus_owned": focus_owned,
                             "focus": normal != focused, "pressed": normal != pressed,
                             "disabled": normal != disabled, "geometry_retained": geometry == button.geometry(),
                             "actions_triggered": clicked.count()})
                if capture:
                    for state, pixels in (("normal", normal), ("focus", focused), ("pressed", pressed), ("disabled", disabled)):
                        pixels.save(str(directory / f"{scale:g}-{name}-{state}.png"))
                button.setEnabled(enabled)
                owner.hide()
        self.assertEqual(self.sample.root.read_bytes(), original)
        self.assertIsNone(session.compile_manager)
        self.assertEqual(session.undo_stack.count(), 0)
        if os.environ.get("ICSTEX_TASK_BUTTON_CAPTURE"):
            from tools.bench_pdf_pipeline import source_digest
            (Path(os.environ["ICSTEX_TASK_BUTTON_CAPTURE"]) / "states.json").write_text(
                json.dumps({"app_sha256": source_digest(),
                            "limits": "Appearance-only state simulation, not workflow readiness", "states": rows}, indent=2))
        self.assertTrue(all(all(row[key] for key in ("focus_owned", "focus", "pressed", "disabled", "geometry_retained"))
                            and row["actions_triggered"] == 0 for row in rows), rows)

    def test_modal_comboboxes_remain_reachable_with_text_list_tab_policy(self):
        from app.gui.project_panels import ProjectWizardDialog
        from app.gui.project_profile_dialog import ProjectProfileDialog
        from app.gui.project_migration_dialog import ProjectMigrationDialog
        hints = self.application.styleHints()
        previous = hints.tabFocusBehavior()
        # Process-local simulation of the observed Cocoa policy, not an OS
        # keyboard preference change or a production override of that policy.
        hints.setTabFocusBehavior(Qt.TabFocusBehavior(
            Qt.TabFocusBehavior.TabFocusTextControls.value |
            Qt.TabFocusBehavior.TabFocusListControls.value))
        try:
            wizard = ProjectWizardDialog(self.window)
            profile = ProjectProfileDialog(self.sample.root.parent, self.window)
            migration = ProjectMigrationDialog(self.window)
            self.dialogs.extend((wizard, profile, migration))
            for dialog, before, first, second in (
                    (wizard, wizard.name_edit, wizard.template_combo, wizard.engine_combo),
                    (profile, profile.enabled, profile.template, profile.engine)):
                with self.subTest(dialog=type(dialog).__name__):
                    dialog.show()
                    before.setFocus()
                    QTest.qWait(20)
                    QTest.keyClick(before, Qt.Key.Key_Tab)
                    self.assertIs(self.application.focusWidget(), first)
                    QTest.keyClick(first, Qt.Key.Key_Tab)
                    self.assertIs(self.application.focusWidget(), second)
                    QTest.keyClick(second, Qt.Key.Key_Backtab)
                    self.assertIs(self.application.focusWidget(), first)
                    dialog.hide()
            # This selector is disabled until a real copy exists. Its actual
            # publication/open workflow is separately tested; check its policy
            # here without manufacturing a successful migration state.
            self.assertEqual(migration.source.focusPolicy() & Qt.FocusPolicy.StrongFocus,
                             Qt.FocusPolicy.StrongFocus)
        finally:
            hints.setTabFocusBehavior(previous)

    def test_creation_fields_preview_and_actions_are_reachable(self):
        from PySide6.QtWidgets import QDialogButtonBox
        from app.gui.project_panels import ProjectWizardDialog
        dialog = ProjectWizardDialog(self.window)
        self.dialogs.append(dialog)
        dialog.parent_edit.setText(str(self.home))
        self.traverse(dialog, [dialog.parent_edit, dialog.name_edit, dialog.template_combo,
            dialog.engine_combo, dialog.profile_enabled, dialog.open_new_window, dialog.preview,
            dialog.buttons.button(QDialogButtonBox.StandardButton.Ok),
            dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)])

    def test_combobox_return_never_confirms_creation_or_profile_save(self):
        from app.core.project_profile import PROFILE_PATH
        from app.gui.project_panels import ProjectWizardDialog
        from app.gui.project_profile_dialog import ProjectProfileDialog
        profile_path = self.sample.root.parent / PROFILE_PATH
        original = profile_path.read_bytes() if profile_path.exists() else None
        for kind in ("creation", "profile"):
            for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                with self.subTest(kind=kind, key=key):
                    if kind == "creation":
                        dialog = ProjectWizardDialog(self.window)
                        dialog.parent_edit.setText(str(self.home))
                        dialog.name_edit.setText(f"no-implicit-create-{key.value}")
                        combos = (dialog.template_combo, dialog.engine_combo)
                    else:
                        dialog = ProjectProfileDialog(self.sample.root.parent, self.window)
                        dialog.word_min.setText("20")
                        combos = (dialog.template, dialog.engine)
                    self.dialogs.append(dialog)
                    dialog.show()
                    QTest.qWait(20)
                    for combo in combos:
                        combo.setFocus()
                        QTest.keyClick(combo, key)
                        self.assertTrue(dialog.isVisible(), "Selecting a field must not confirm the dialog")
                        self.assertIsNone(getattr(dialog, "created_project", None))
                        self.assertIsNone(getattr(dialog, "saved_snapshot", None))
                        self.assertEqual(profile_path.read_bytes() if profile_path.exists() else None, original)
                        previous_index = combo.currentIndex()
                        QTest.keyClick(combo, Qt.Key.Key_Space)
                        self.assertTrue(combo.view().isVisible())
                        popup_window = self.application.focusWindow()
                        self.assertIsNotNone(popup_window)
                        QTest.keyClick(popup_window, Qt.Key.Key_Down)
                        QTest.keyClick(popup_window, key)
                        self.assertEqual(combo.currentIndex(), previous_index + 1)
                        self.assertFalse(combo.view().isVisible())
                        self.assertTrue(dialog.isVisible())
                        self.assertIsNone(getattr(dialog, "created_project", None))
                        self.assertIsNone(getattr(dialog, "saved_snapshot", None))
                        self.assertEqual(profile_path.read_bytes() if profile_path.exists() else None, original)
                    dialog.reject()

    def test_modal_tab_pages_are_reachable_with_text_list_tab_policy(self):
        from app.gui.project_migration_dialog import ProjectMigrationDialog
        from app.gui.submission_delivery_dialog import SubmissionDeliveryDialog
        hints = self.application.styleHints()
        previous = hints.tabFocusBehavior()
        hints.setTabFocusBehavior(Qt.TabFocusBehavior(
            Qt.TabFocusBehavior.TabFocusTextControls.value |
            Qt.TabFocusBehavior.TabFocusListControls.value))
        try:
            for dialog in (SubmissionDeliveryDialog(self.window), ProjectMigrationDialog(self.window)):
                self.dialogs.append(dialog)
                if isinstance(dialog, SubmissionDeliveryDialog):
                    dialog.inspect()
                    self.wait(lambda: not dialog.busy)
                    self.assertIs(dialog.pages.currentWidget(), dialog.review_page)
                dialog.show()
                start = dialog.close_button if isinstance(dialog, SubmissionDeliveryDialog) else dialog.choose_button
                for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                    with self.subTest(dialog=type(dialog).__name__, scale=scale):
                        self.application.ui_scale_manager.apply_scale(scale)
                        dialog.resize(900, 640)
                        start.setFocus()
                        QTest.qWait(20)
                        for _ in range(40):
                            current = self.application.focusWidget()
                            self.assertIsNotNone(current)
                            if current is dialog.tabs.tabBar():
                                break
                            QTest.keyClick(current, Qt.Key.Key_Tab)
                        self.assertIs(self.application.focusWidget(), dialog.tabs.tabBar())
                        self.assertTrue(dialog.tabs.tabBar().visibleRegion().contains(dialog.tabs.tabBar().rect()))
                        dialog.tabs.setCurrentIndex(0)
                        QTest.keyClick(dialog.tabs.tabBar(), Qt.Key.Key_Right)
                        self.assertEqual(dialog.tabs.currentIndex(), 1)
                        QTest.keyClick(dialog.tabs.tabBar(), Qt.Key.Key_Left)
                        self.assertEqual(dialog.tabs.currentIndex(), 0)
                dialog.hide()
        finally:
            hints.setTabFocusBehavior(previous)

    def test_standalone_block_delivery_entry_is_keyboard_reachable_at_all_scales(self):
        from app.core.blocks.project_repository import load_project
        from app.gui.blocks.project_dialog import BlockProjectDialog
        from tests.v1_fixtures import create_project
        fixture = create_project(self.home, "block")
        saved = {p: p.read_bytes() for p in fixture.root.parent.rglob("*") if p.is_file()}
        loaded = load_project(fixture.root.parent)
        dialog = BlockProjectDialog(registry=loaded["registry"], layout=loaded["layout"],
                                    document_theme=loaded["document_theme"],
                                    project_dir=fixture.root.parent)
        hints = self.application.styleHints()
        previous = hints.tabFocusBehavior()
        hints.setTabFocusBehavior(Qt.TabFocusBehavior(
            Qt.TabFocusBehavior.TabFocusTextControls.value |
            Qt.TabFocusBehavior.TabFocusListControls.value))
        try:
            dialog.show()
            workspace = dialog.workspace
            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                with self.subTest(scale=scale):
                    self.application.ui_scale_manager.apply_scale(scale)
                    dialog.resize(900, 640)
                    workspace.tabs.setCurrentIndex(0)
                    workspace.preview_button.setFocus()
                    QTest.qWait(20)
                    for _ in range(40):
                        focus = self.application.focusWidget()
                        self.assertIsNotNone(focus)
                        if focus is workspace.tabs.tabBar():
                            break
                        QTest.keyClick(focus, Qt.Key.Key_Tab)
                    self.assertIs(self.application.focusWidget(), workspace.tabs.tabBar())
                    for _ in range(workspace.tabs.count() - 1):
                        QTest.keyClick(workspace.tabs.tabBar(), Qt.Key.Key_Right)
                    self.assertEqual(workspace.tabs.currentIndex(), workspace.tabs.count() - 1)
                    for _ in range(10):
                        focus = self.application.focusWidget()
                        if focus is workspace.delivery_button:
                            break
                        self.assertIsNotNone(focus)
                        QTest.keyClick(focus, Qt.Key.Key_Tab)
                    self.assertIs(self.application.focusWidget(), workspace.delivery_button)
                    self.assertTrue(workspace.delivery_button.visibleRegion().contains(workspace.delivery_button.rect()))
                    with patch("app.gui.submission_delivery_dialog.show_submission_delivery") as opened:
                        QTest.keyClick(workspace.delivery_button, Qt.Key.Key_Space)
                    opened.assert_called_once_with(dialog, session=dialog.session)
                    QTest.keyClick(workspace.delivery_button, Qt.Key.Key_Backtab)
                    self.assertIs(self.application.focusWidget(), workspace.tabs.tabBar())
            self.assertFalse(dialog.session._compile_authorized)
            self.assertEqual({p: p.read_bytes() for p in saved}, saved)
        finally:
            hints.setTabFocusBehavior(previous)
            dialog.session._dirty = False
            dialog.session.editor_drafts.clear()
            dialog.close()
            dialog.deleteLater()

    def test_profile_keyboard_multiline_undo_cancel_and_save_preserve_source(self):
        from app.core.project_profile import PROFILE_PATH, load_profile
        from app.gui.project_profile_dialog import ProjectProfileDialog
        from PySide6.QtWidgets import QDialogButtonBox
        original = self.sample.root.read_bytes()
        profile_path = self.sample.root.parent / PROFILE_PATH
        previous = profile_path.read_bytes() if profile_path.exists() else None
        for save in (False, True):
            dialog = ProjectProfileDialog(self.sample.root.parent, self.window)
            self.dialogs.append(dialog)
            dialog.show()
            dialog.directories.setFocus()
            QTest.qWait(10)
            dialog.directories.selectAll()
            QTest.keyClicks(dialog.directories, "figures")
            QTest.keyClick(dialog.directories, Qt.Key.Key_Return)
            QTest.keyClicks(dialog.directories, "chapters")
            self.assertEqual(dialog.directories.toPlainText(), "figures\nchapters")
            QTest.keyClicks(dialog.directories, "x")
            from PySide6.QtGui import QKeySequence
            QTest.keySequence(dialog.directories, QKeySequence.StandardKey.Undo)
            # Qt may merge the last word into the same typing transaction;
            # redo must restore exactly the draft, without changing disk.
            QTest.keySequence(dialog.directories, QKeySequence.StandardKey.Redo)
            self.assertEqual(dialog.directories.toPlainText(), "figures\nchaptersx")
            QTest.keyClick(dialog.directories, Qt.Key.Key_Backspace)
            QTest.keyClick(dialog.directories, Qt.Key.Key_Tab)
            self.assertIs(self.application.focusWidget(), dialog.word_min)
            QTest.keyClick(dialog.word_min, Qt.Key.Key_Backtab)
            self.assertIs(self.application.focusWidget(), dialog.directories)
            button = dialog.buttons.button(QDialogButtonBox.StandardButton.Save if save
                                           else QDialogButtonBox.StandardButton.Cancel)
            for _ in range(20):
                focused = self.application.focusWidget()
                if focused is button:
                    break
                self.assertIsNotNone(focused)
                QTest.keyClick(focused, Qt.Key.Key_Tab)
            self.assertIs(self.application.focusWidget(), button)
            QTest.keyClick(button, Qt.Key.Key_Space)
            self.assertFalse(dialog.isVisible())
            self.assertEqual(self.sample.root.read_bytes(), original)
            if save:
                self.assertEqual(load_profile(self.sample.root.parent).profile.directories,
                                 ("figures", "chapters"))
            else:
                self.assertEqual(profile_path.read_bytes() if profile_path.exists() else None, previous)

    def test_checkpoint_selection_preview_and_actions_are_reachable(self):
        from app.gui.project_checkpoint_dialog import ProjectCheckpointDialog
        dialog = ProjectCheckpointDialog(self.window)
        self.dialogs.append(dialog)
        self.wait(lambda: not dialog.busy)
        dialog.target.setText(str(self.home / "checkpoint.zip"))
        self.traverse(dialog, [dialog.open_button, dialog.select_button, dialog.clear_button,
            dialog.tree, dialog.preview, dialog.target, dialog.target_button,
            dialog.action_button, dialog.close_button])

    def test_migration_review_preview_and_actions_are_reachable(self):
        from app.gui.project_migration_dialog import ProjectMigrationDialog
        dialog = ProjectMigrationDialog(self.window)
        self.dialogs.append(dialog)
        dialog.load_project(self.sample.root.parent)
        self.wait(lambda: not dialog.busy)
        dialog.inspect_selection()
        self.wait(lambda: not dialog.busy)
        self.assertIsNotNone(dialog.review, dialog.status.text())
        dialog.target.setText(str(self.home / "migration"))
        self.traverse(dialog, [dialog.choose_button, dialog.tabs.tabBar(), dialog.output, dialog.review_button,
            dialog.preview, dialog.target, dialog.target_button, dialog.action_button,
            dialog.close_button])

    def test_restore_review_and_actions_are_reachable(self):
        from app.core.project_checkpoint import create_checkpoint, DraftInput
        from app.gui.project_checkpoint_dialog import ProjectCheckpointDialog
        archive = self.home / "original.icstex-checkpoint"
        create_checkpoint(self.sample.root.parent, (self.sample.root.name,), archive,
                          drafts=(DraftInput("source", "source-text", self.sample.root.name,
                                             b"Independent synthetic draft"),))
        dialog = ProjectCheckpointDialog(self.window, restore=True)
        self.dialogs.append(dialog)
        dialog.load_archive(archive)
        self.wait(lambda: not dialog.busy)
        self.assertIsNotNone(dialog.info, dialog.status.text())
        dialog.target.setText(str(self.home / "restored"))
        self.traverse(dialog, [dialog.open_button, dialog.tree, dialog.preview, dialog.target,
            dialog.target_button, dialog.action_button, dialog.close_button])

    def test_migration_published_source_selection_does_not_confirm_open(self):
        from PySide6.QtWidgets import QMessageBox
        from app.gui.project_migration_dialog import ProjectMigrationDialog
        original = {p: p.read_bytes() for p in self.sample.root.parent.rglob("*") if p.is_file()}
        dialog = ProjectMigrationDialog(self.window)
        self.dialogs.append(dialog)
        dialog.load_project(self.sample.root.parent)
        self.wait(lambda: not dialog.busy)
        dialog.inspect_selection()
        self.wait(lambda: not dialog.busy)
        self.assertIsNotNone(dialog.review, dialog.status.text())
        dialog.target.setText(str(self.home / "keyboard-migration"))
        # Real publication establishes the enabled post-copy controls. Its
        # native confirmation and picker remain separate acceptance evidence.
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.perform()
        self.wait(lambda: not dialog.busy)
        self.assertIsNotNone(dialog.result, dialog.status.text())
        copied = {p: p.read_bytes() for p in dialog.result.directory.rglob("*") if p.is_file()}
        hints = self.application.styleHints()
        previous = hints.tabFocusBehavior()
        hints.setTabFocusBehavior(Qt.TabFocusBehavior(
            Qt.TabFocusBehavior.TabFocusTextControls.value |
            Qt.TabFocusBehavior.TabFocusListControls.value))
        try:
            self.traverse(dialog, [dialog.tabs.tabBar(), dialog.output, dialog.preview,
                                  dialog.source, dialog.open_button, dialog.close_button])
            self.assertGreater(dialog.source.count(), 1)
            dialog.open_button.setFocus()
            QTest.keyClick(dialog.open_button, Qt.Key.Key_Backtab)
            self.assertIs(self.application.focusWidget(), dialog.source)
            QTest.keyClick(dialog.source, Qt.Key.Key_Space)
            self.assertTrue(dialog.source.view().isVisible())
            popup = self.application.focusWindow()
            self.assertIsNotNone(popup)
            QTest.keyClick(popup, Qt.Key.Key_Home)
            QTest.keyClick(popup, Qt.Key.Key_Down)
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as confirm:
                QTest.keyClick(popup, Qt.Key.Key_Return)
                QTest.qWait(50)
                self.assertEqual(confirm.call_count, 0, "Source selection must not request opening")
            self.assertEqual(dialog.source.currentIndex(), 1)
            self.assertFalse(dialog.source.view().isVisible())
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog.busy)
            self.assertIsNone(dialog.opened)
        finally:
            hints.setTabFocusBehavior(previous)
        self.assertEqual({p: p.read_bytes() for p in original}, original)
        self.assertEqual({p: p.read_bytes() for p in copied}, copied)
        self.assertFalse(self.window.compile_authorized_roots)

    def test_recovery_draft_selection_preview_and_actions_are_reachable(self):
        from app.core.project_checkpoint import create_checkpoint, restore_checkpoint, DraftInput
        from app.gui.project_recovery_dialog import RecoveryDraftDialog
        archive = self.home / "draft.icstex-checkpoint"
        draft = b"Independent keyboard recovery draft"
        original = self.sample.root.read_bytes()
        create_checkpoint(self.sample.root.parent, (self.sample.root.name,), archive,
                          drafts=(DraftInput("source", "source-text", self.sample.root.name, draft),))
        restored = restore_checkpoint(archive, self.home / "draft-copy")
        dialog = RecoveryDraftDialog(self.window, restored.directory)
        self.dialogs.append(dialog)
        self.wait(lambda: not dialog.busy)
        self.assertIsNotNone(dialog.copy, dialog.status.text())
        self.assertTrue(dialog.apply_button.isEnabled())
        dialog.show()
        dialog.tree.setFocus()
        QTest.qWait(20)
        QTest.keyClick(dialog.tree, Qt.Key.Key_Home)
        QTest.keyClick(dialog.tree, Qt.Key.Key_Space)
        self.assertEqual(dialog.tree.topLevelItem(0).checkState(0), Qt.CheckState.Checked)
        self.assertEqual(dialog.preview.toPlainText(), draft.decode())
        hints = self.application.styleHints()
        previous = hints.tabFocusBehavior()
        hints.setTabFocusBehavior(Qt.TabFocusBehavior(
            Qt.TabFocusBehavior.TabFocusTextControls.value |
            Qt.TabFocusBehavior.TabFocusListControls.value))
        try:
            self.traverse(dialog, [dialog.choose_button, dialog.tree, dialog.preview,
                                  dialog.apply_button, dialog.close_button])
        finally:
            hints.setTabFocusBehavior(previous)
        self.assertIsNone(dialog.opened_window)
        self.assertFalse(self.window.compile_authorized_roots)
        dialog.close_button.setFocus()
        QTest.keyClick(dialog.close_button, Qt.Key.Key_Space)
        self.assertFalse(dialog.isVisible())
        self.assertEqual(self.sample.root.read_bytes(), original)
        self.assertEqual((restored.project_dir / self.sample.root.name).read_bytes(), original)
        self.assertEqual((restored.drafts_dir / "source.txt").read_bytes(), draft)

    def test_delivery_review_preview_and_actions_are_reachable(self):
        from dataclasses import replace
        import sys
        from app.core.latex_tools import LaTeXToolchain
        from app.core.pdf_state import PdfBuildRecord, PdfFreshness
        from app.gui.submission_delivery_dialog import SubmissionDeliveryDialog
        from tests.test_submission_check import request_for
        pdf = self.sample.root.parent / ".latex_build/main.pdf"
        pdf.parent.mkdir()
        pdf.write_bytes(b"%PDF-1.4 synthetic layout evidence only")
        record = PdfBuildRecord(self.sample.root, PdfFreshness.CURRENT, pdf, 4, 4, 4, 7)
        request = request_for(self.sample, final=record)
        tools = LaTeXToolchain(None, sys.executable)
        request = replace(request, tools=tools, build_evidence=replace(request.build_evidence,
            job_key=replace(request.build_evidence.job_key, toolchain=tools)))
        with patch.object(self.window.readiness, "capture_request", side_effect=lambda:
                          replace(request, key=self.window.readiness._context()[0])):
            dialog = SubmissionDeliveryDialog(self.window)
            self.dialogs.append(dialog)
            original = self.sample.root.read_bytes()
            self.traverse(dialog, [dialog.save_button, dialog.compile_button, dialog.review_button,
                dialog.include_source, dialog.include_report, dialog.pdf_name, dialog.close_button])
            dialog.include_source.setChecked(True)
            self.wait(lambda: not dialog.busy)
            self.traverse(dialog, [dialog.files, dialog.select_button, dialog.clear_button,
                dialog.inventory_button, dialog.review_button, dialog.close_button])
            dialog.include_source.setChecked(False)
            dialog.inspect()
            self.wait(lambda: not dialog.busy)
            self.assertIsNotNone(dialog.prepared, dialog.status.text())
            dialog.acknowledge.setChecked(True)
            dialog.target.setText(str(self.home / "delivery"))
            frozen, lease = dialog.prepared, dialog.lease
            self.traverse(dialog, [dialog.tabs.tabBar(), dialog.outputs, dialog.preview,
                dialog.acknowledge, dialog.continue_button, dialog.back_button, dialog.technical_button,
                dialog.close_button])
            dialog.technical_button.click()
            self.traverse(dialog, [dialog.technical, dialog.technical_button, dialog.continue_button,
                dialog.back_button, dialog.close_button])
            dialog.technical_button.click()
            dialog.continue_button.click()
            self.traverse(dialog, [dialog.target, dialog.target_button, dialog.target_summary,
                dialog.action_button, dialog.back_button, dialog.close_button])
            self.assertIs(dialog.prepared, frozen)
            self.assertIs(dialog.lease, lease)
            self.assertEqual(self.sample.root.read_bytes(), original)
            self.assertFalse((self.home / "delivery").exists())


class WritingWorkspaceLayoutTests(TestCase):
    """C slice: real Qt geometry and persistent editor state, no compiler."""

    def setUp(self):
        from tests.test_gui_editor import isolated_settings
        self.application = _app()
        self.settings = isolated_settings()
        self.window = MainWindow(settings_store=self.settings)
        self.previous_scale = self.application.ui_scale_manager.scale
        if os.environ.get("ICSTEX_WELCOME_CAPTURE"):
            self.window.setWindowTitle("ICSTeX - WELCOME UI TEST")
        self.window.set_ui_scale(1.0)
        self.window.auto_compile_action.setChecked(False)
        self.window.show()
        self.window.activateWindow()
        self.addCleanup(self.dispose)

    def settle(self):
        for _ in range(6):
            self.application.processEvents()

    def dispose(self):
        for tab in self.window.tabs.values():
            self.window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        self.window.close()
        self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.application.ui_scale_manager.apply_scale(self.previous_scale)

    def test_welcome_uses_main_workspace_without_empty_pdf_console_or_header(self):
        self.settle()
        self.assertTrue(self.window.welcome_page.isVisible())
        self.assertFalse(self.window.pdf_panel_wrapper.isVisible())
        self.assertFalse(self.window.bottom_panel.isVisible())
        self.assertFalse(self.window.workspace.toolbar.isVisible())
        self.assertGreater(self.window.welcome_page.width(), self.window.width() * 0.95)

    def test_restored_toolbox_waits_for_project_and_survives_welcome_restart(self):
        self.window.resize(1440, 900)
        self.window.new_document()
        self.window.set_toolbox_visible(True)
        self.settle()
        self.assertTrue(self.window.toolbox_dock.isVisible())
        self.settings.settings.setValue("window/block_console_state", self.window.saveState())
        for cycle in range(2):
            fresh = MainWindow(settings_store=self.settings)
            try:
                fresh.setWindowTitle("ICSTeX - WELCOME RESTORE TEST")
                fresh.resize(1440, 900)
                fresh.show()
                self.settle()
                capture = os.environ.get("ICSTEX_WELCOME_CAPTURE")
                if capture:
                    directory = Path(capture)
                    directory.mkdir(parents=True, exist_ok=True)
                    fresh.grab().save(str(directory / f"welcome-{cycle}.png"))
                self.assertFalse(fresh.toolbox_dock.isVisible())
                self.assertGreater(fresh.welcome_page.width(), fresh.width() * 0.95)
                if cycle == 1:
                    fresh.new_document()
                    self.settle()
                    self.assertTrue(fresh.toolbox_dock.isVisible())
                    self.assertTrue(fresh.toolbox_action.isChecked())
            finally:
                for tab in fresh.tabs.values():
                    tab.modified = tab.dirty = False
                fresh.close()
                self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_welcome_allows_explicit_toolbox_and_selected_folder_navigation(self):
        from tempfile import TemporaryDirectory
        self.window.resize(1440, 900)
        self.window.new_document()
        self.window.set_toolbox_visible(True)
        self.window.close_tab(0)
        self.settle()
        self.assertFalse(self.window.toolbox_dock.isVisible())
        self.window.set_toolbox_visible(True)
        self.settle()
        self.assertTrue(self.window.toolbox_dock.isVisible())
        self.window.set_toolbox_visible(False)
        self.window.update_document_view_state()
        with TemporaryDirectory() as directory:
            self.window.project_files.set_project_root(directory)
            self.window.set_toolbox_visible(True)
            self.settle()
            self.assertTrue(self.window.toolbox_dock.isVisible())
            self.assertEqual(self.window.selected_project_scope, Path(directory).resolve())

    def test_welcome_primary_feedback_and_actions_fit_all_scale_tiers(self):
        from PySide6.QtCore import QPoint, QRect
        apply_theme(self.application)
        page = self.window.welcome_page
        button = page.new_project_button
        for scale in (.9, 1., 1.1, 1.25, 1.5):
            self.window.set_ui_scale(scale)
            for width, height in ((1080, 720), (1440, 900)):
                self.window.resize(width, height)
                self.window.activateWindow()
                button.setEnabled(True)
                button.clearFocus()
                self.settle()
                self.assertLessEqual(self.window.width(), width)
                self.assertLessEqual(self.window.height(), height)
                self.assertGreater(page.width(), self.window.width() * .95)
                for action in page._action_buttons:
                    area = QRect(action.mapTo(page.scroll.viewport(), QPoint()), action.size())
                    self.assertTrue(page.scroll.viewport().rect().contains(area), (scale, width, action.text()))
                first_row = [page.action_grid.itemAt(i).widget() for i in range(page.action_grid.count())
                             if page.action_grid.getItemPosition(i)[0] == 0]
                self.assertGreater(max(action.mapTo(page, QPoint()).x() + action.width()
                                       for action in first_row), page.width() * .9, (scale, width))
                geometry = button.geometry()
                normal = button.grab().toImage()
                button.setFocus(Qt.FocusReason.TabFocusReason)
                self.settle()
                self.assertTrue(button.hasFocus())
                self.assertNotEqual(normal, button.grab().toImage(), ("focus", scale, width))
                button.clearFocus()
                button.setDown(True)
                self.settle()
                self.assertNotEqual(normal, button.grab().toImage(), ("pressed", scale, width))
                button.setDown(False)
                button.setEnabled(False)
                self.settle()
                self.assertNotEqual(normal, button.grab().toImage(), ("disabled", scale, width))
                self.assertEqual(button.geometry(), geometry)
                button.setEnabled(True)
                self.settle()
                capture = os.environ.get("ICSTEX_WELCOME_CAPTURE")
                if capture:
                    directory = Path(capture)
                    directory.mkdir(parents=True, exist_ok=True)
                    self.window.grab().save(str(directory / f"welcome-{scale:g}-{width}.png"))
        self.assertFalse(self.window.tabs)
        self.assertFalse(self.window.compile_authorized_roots)

    def test_default_writing_has_600px_editor_and_truthful_compile_action(self):
        self.window.new_document()
        self.window.resize(1440, 900)
        self.settle()
        self.assertTrue(self.window.bottom_tabs.isHidden())
        editor = self.window.current_tab().editor
        self.assertGreaterEqual(editor.viewport().height(), 600)
        self.assertEqual(self.window.compile_action.text(), "正式编译")
        labels = [label.text() for label in self.window.findChildren(QLabel)]
        self.assertNotIn("实时编译", labels)
        self.assertFalse(self.window.compile_authorized_roots)

    def test_primary_keyboard_focus_changes_pixels_without_changing_geometry(self):
        from PySide6.QtCore import QPoint, QRect
        from app.gui.formula_dialog import FormulaDialog
        apply_theme(self.application)
        self.window.new_document()
        self.window.resize(1440, 900)
        button = self.window.findChild(QToolBar, "mainToolbar").widgetForAction(self.window.compile_action)
        block_button = self.window.findChild(QToolBar, "mainToolbar").widgetForAction(self.window.block_compile_action)
        self.assertTrue(button.styleSheet())
        self.assertEqual(block_button.styleSheet(), button.styleSheet())
        dialog = FormulaDialog(self.window, "$x+1$", 0, 5)
        try:
            for scale in (.9, 1., 1.1, 1.25, 1.5):
                self.window.set_ui_scale(scale)
                for owner, action in ((self.window, button), (dialog, dialog._ok_button)):
                    owner.show()
                    owner.activateWindow()
                    action.clearFocus()
                    self.settle()
                    area = QRect(action.mapTo(owner, QPoint()), action.size()).adjusted(-4, -4, 4, 4)
                    geometry = action.geometry()
                    normal = owner.grab(area).toImage()
                    action.setFocus(Qt.FocusReason.TabFocusReason)
                    self.settle()
                    self.assertTrue(action.hasFocus())
                    self.assertEqual(action.geometry(), geometry)
                    self.assertNotEqual(normal, owner.grab(area).toImage(), (scale, action.objectName()))
            self.assertEqual(dialog.visual_edit.latex(), "x+1")
            self.assertIsNone(dialog._accepted_plan)
            self.assertFalse(self.window.compile_authorized_roots)
        finally:
            dialog.reject()
            dialog.deleteLater()
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_primary_press_stays_distinct_when_pointer_is_already_hovering(self):
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtWidgets import QStyle, QStyleOptionButton, QStyleOptionToolButton
        apply_theme(self.application)
        self.window.new_document()
        toolbar = self.window.findChild(QToolBar, "mainToolbar")
        targets = (self.window.welcome_page.new_project_button,
                   toolbar.widgetForAction(self.window.compile_action))
        for button in targets:
            option = QStyleOptionButton() if button is targets[0] else QStyleOptionToolButton()
            button.initStyleOption(option)
            base = option.state & ~(QStyle.StateFlag.State_MouseOver | QStyle.StateFlag.State_Sunken |
                                    QStyle.StateFlag.State_HasFocus)
            images = []
            for extra in (QStyle.StateFlag.State_None, QStyle.StateFlag.State_MouseOver,
                          QStyle.StateFlag.State_MouseOver | QStyle.StateFlag.State_Sunken):
                option.state = base | extra
                pixels = QImage(button.size(), QImage.Format.Format_ARGB32_Premultiplied)
                pixels.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixels)
                if button is targets[0]:
                    button.style().drawControl(QStyle.ControlElement.CE_PushButton, option, painter, button)
                else:
                    button.style().drawComplexControl(QStyle.ComplexControl.CC_ToolButton, option, painter, button)
                painter.end()
                images.append(pixels)
            self.assertNotEqual(images[0], images[1], (button.objectName(), "hover"))
            self.assertNotEqual(images[1], images[2], (button.objectName(), "hover+pressed"))
        self.assertFalse(self.window.compile_authorized_roots)

    def test_formula_disabled_primary_has_distinct_pixels_and_keeps_its_draft(self):
        from app.gui.formula_dialog import FormulaDialog
        apply_theme(self.application)
        dialog = FormulaDialog(self.window, "$x+1$", 0, 5)
        try:
            dialog.show()
            dialog.activateWindow()
            for scale in (.9, 1., 1.1, 1.25, 1.5):
                self.window.set_ui_scale(scale)
                button = dialog._ok_button
                button.setEnabled(True)
                button.clearFocus()
                self.settle()
                geometry = button.geometry()
                enabled = button.grab().toImage()
                button.setDown(True)
                self.settle()
                self.assertNotEqual(enabled, button.grab().toImage(), ("pressed", scale))
                button.setDown(False)
                button.setEnabled(False)
                self.settle()
                self.assertFalse(button.isEnabled())
                self.assertEqual(button.geometry(), geometry)
                self.assertNotEqual(enabled, button.grab().toImage(), scale)
            self.assertEqual(dialog.visual_edit.latex(), "x+1")
            self.assertIsNone(dialog._accepted_plan)
        finally:
            dialog.reject()
            dialog.deleteLater()
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_console_expansion_is_explicit_and_retained_on_document_changes(self):
        self.window.new_document()
        self.settle()
        self.assertTrue(self.window.bottom_tabs.isHidden())
        self.window.bottom_collapse_button.click()
        self.settle()
        self.assertFalse(self.window.bottom_tabs.isHidden())
        self.assertFalse(self.settings.settings.value("window/console_collapsed", True, type=bool))
        self.window.update_document_view_state()
        self.settle()
        self.assertFalse(self.window.bottom_tabs.isHidden())
        self.window.bottom_collapse_button.click()
        self.window.update_document_view_state()
        self.assertTrue(self.window.bottom_tabs.isHidden())

    def test_explicit_console_preference_survives_a_new_window(self):
        self.settings.settings.setValue("window/console_collapsed", False)
        other = MainWindow(settings_store=self.settings)
        try:
            other.new_document()
            other.show()
            self.settle()
            self.assertFalse(other.bottom_tabs.isHidden())
            self.assertGreater(other.vertical_splitter.sizes()[1], 100)
        finally:
            other.close()
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_requested_checks_expand_without_focus_or_preference_changes(self):
        self.window.new_document()
        editor = self.window.current_tab().editor
        editor.setFocus()
        self.settle()
        self.window.run_project_check(switch_to_panel=True)
        self.settle()
        self.assertFalse(self.window.bottom_tabs.isHidden())
        self.assertIs(self.application.focusWidget(), editor)
        self.assertTrue(self.settings.settings.value("window/console_collapsed", True, type=bool))
        self.window.bottom_collapse_button.click()
        self.window.run_project_check(switch_to_panel=True)
        self.assertFalse(self.window.bottom_tabs.isHidden())

    def test_pdf_search_reveals_compact_pane_and_escape_returns_to_source(self):
        from PySide6.QtGui import QPainter, QPdfWriter
        from tests.test_gui_editor import wait_until
        self.window.new_document()
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        editor = self.window.current_tab().editor
        with TemporaryDirectory() as directory:
            path = Path(directory) / "search.pdf"
            writer = QPdfWriter(str(path))
            painter = QPainter(writer)
            painter.drawText(100, 100, "search needle")
            painter.end()
            del writer
            panel = self.window.pdf_panel
            panel.load_pdf(path)
            self.assertTrue(wait_until(lambda: panel._document.pageCount() == 1))
            self.window.resize(1080, 720)
            self.window.set_toolbox_visible(True)
            self.window.source_preview_area.select_pdf(False)
            editor.setFocus()
            self.settle()
            self.assertFalse(panel.isVisible())
            QTest.keyClick(editor, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
            self.settle()
            self.assertTrue(panel.isVisible())
            self.assertIs(self.application.focusWidget(), panel.pdf_search_edit)
            QTest.keyClick(panel.pdf_search_edit, Qt.Key.Key_Escape)
            self.settle()
            self.assertTrue(editor.isVisible())
            self.assertIs(self.application.focusWidget(), editor)
            panel.clear_pdf()

    def test_narrow_pair_preserves_widgets_selection_scroll_undo_and_wide_split(self):
        from PySide6.QtGui import QTextCursor
        self.window.new_document()
        editor = self.window.current_tab().editor
        editor.setPlainText("line\n" * 300)
        editor.moveCursor(QTextCursor.MoveOperation.End)
        editor.insertPlainText("one edit")
        cursor = editor.textCursor()
        cursor.setPosition(120)
        cursor.setPosition(140, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        self.settle()
        editor.verticalScrollBar().setValue(80)
        editor.setFocus()
        area = self.window.source_preview_area
        # Exercise the same signal as a user moving the splitter handle.
        area.splitter.moveSplitter(850, 1)
        self.settle()
        widths = area.splitter.sizes()
        state = (cursor.position(), cursor.anchor(), editor.verticalScrollBar().value())
        for scale in (1.0, 1.5):
            self.window.set_ui_scale(scale)
            self.window.resize(1080, 720)
            self.window.set_toolbox_visible(True)
            self.settle()
            self.assertTrue(area._compact)
            self.assertTrue(editor.isVisible())
            self.assertFalse(area.pdf.isVisible())
            area.select_pdf(True)
            self.settle()
            self.assertTrue(area.pdf.isVisible())
            self.assertFalse(editor.isVisible())
            area.select_pdf(False)
            self.assertIs(self.window.current_tab().editor, editor)
            self.assertTrue(editor.document().isUndoAvailable())
        self.window.set_toolbox_visible(False)
        self.window.set_ui_scale(1.0)
        self.window.resize(1440, 900)
        self.settle()
        self.assertFalse(area._compact)
        self.assertEqual(area.splitter.sizes(), widths)
        self.assertEqual((editor.textCursor().position(), editor.textCursor().anchor(),
                          editor.verticalScrollBar().value()), state)
        editor.undo()
        self.assertEqual(editor.toPlainText(), "line\n" * 300)

    def test_temporary_pdf_minimum_does_not_replace_wide_split_preference(self):
        # A wider PDF toolbar at another font must not become a new user ratio.
        self.window.source_preview_area.pdf.setMinimumWidth(480)
        self.test_narrow_pair_preserves_widgets_selection_scroll_undo_and_wide_split()

    def test_default_split_ratio_survives_minimum_constrained_compact_mode(self):
        self.window.new_document()
        area = self.window.source_preview_area
        area.pdf.setMinimumWidth(480)
        self.settle()
        widths = area.splitter.sizes()
        self.window.resize(1080, 720)
        self.window.set_toolbox_visible(True)
        self.settle()
        self.assertTrue(area._compact)
        self.window.set_toolbox_visible(False)
        self.window.resize(1440, 900)
        self.settle()
        self.assertEqual(area.splitter.sizes(), widths)


class SourceWorkspacePanelTests(TestCase):
    setUp = WritingWorkspaceLayoutTests.setUp
    settle = WritingWorkspaceLayoutTests.settle
    dispose = WritingWorkspaceLayoutTests.dispose

    def test_widening_keeps_the_requested_console_open(self):
        from app.gui.main_window_layout import show_console
        self.window.new_document()
        self.window.resize(1080, 720)
        self.settle()
        show_console(self.window, self.window.submission_panel)
        self.window.resize(1440, 900)
        self.settle()
        self.assertTrue(self.window.submission_panel.isVisible())


    def test_narrow_source_switches_auxiliary_without_replacing_widgets(self):
        from app.gui.main_window_layout import show_console
        self.window.new_document()
        self.window.resize(1080, 720)
        self.settle()
        tree = self.window.tree
        checks = self.window.submission_panel
        self.window.set_toolbox_visible(True)
        show_console(self.window, checks)
        self.settle()
        self.assertFalse(self.window.toolbox_dock.isVisible())
        self.assertTrue(self.window.bottom_tabs.isVisible())
        self.window.set_toolbox_visible(True)
        self.settle()
        self.assertTrue(self.window.toolbox_dock.isVisible())
        self.assertTrue(self.window.bottom_tabs.isHidden())
        self.assertIs(self.window.tree, tree)
        self.assertIs(self.window.submission_panel, checks)

    def test_wide_auxiliary_choices_and_dimensions_return_after_narrow_mode(self):
        from app.gui.main_window_layout import show_console
        self.window.new_document()
        self.window.set_toolbox_visible(True)
        show_console(self.window)
        self.window.resizeDocks([self.window.toolbox_dock], [355], Qt.Orientation.Horizontal)
        self.window.vertical_splitter.setSizes([440, 250])
        self.window.current_tab().editor.setFocus()
        self.settle()
        width = self.window.toolbox_dock.width()
        height = self.window.vertical_splitter.sizes()[1]
        self.window.resize(1080, 720)
        self.settle()
        self.assertFalse(self.window.toolbox_dock.isVisible() and self.window.bottom_tabs.isVisible())
        self.window.resize(1440, 900)
        self.settle()
        self.assertTrue(self.window.toolbox_dock.isVisible())
        self.assertTrue(self.window.bottom_tabs.isVisible())
        self.assertAlmostEqual(self.window.toolbox_dock.width(), width, delta=2)
        self.assertAlmostEqual(self.window.vertical_splitter.sizes()[1], height, delta=2)

    def test_automatic_error_does_not_hide_focused_search_preedit(self):
        from PySide6.QtGui import QInputMethodEvent
        from app.gui.main_window_layout import show_console
        self.window.new_document()
        self.window.resize(1080, 720)
        self.window.set_toolbox_visible(True)
        self.window.sidebar_tabs.setCurrentIndex(2)
        editor = self.window.search_panel.findChild(QLineEdit)
        editor.setText("query")
        editor.setFocus()
        self.settle()
        QApplication.sendEvent(editor, QInputMethodEvent("zhong", []))
        show_console(self.window, self.window.diagnostic_panel, error_notice=True)
        self.settle()
        self.assertTrue(editor.isVisible())
        self.assertIs(self.application.focusWidget(), editor)
        self.assertTrue(self.window.bottom_tabs.isHidden())
        self.assertIn("控制台", self.window.statusBar().currentMessage())
        QApplication.sendEvent(editor, QInputMethodEvent("", []))
        show_console(self.window, self.window.diagnostic_panel)
        self.settle()
        self.assertFalse(self.window.toolbox_dock.isVisible())
        self.assertTrue(self.window.bottom_tabs.isVisible())
        self.assertEqual(editor.text(), "query")

    def test_expanded_status_is_complete_copyable_read_only_and_height_bounded(self):
        from PySide6.QtWidgets import QPlainTextEdit
        self.window.new_document()
        self.window.set_ui_scale(1.5)
        self.window.resize(1080, 720)
        self.window.workspace.refresh()
        self.window.workspace._timer.stop()
        details = self.window.workspace.details
        self.assertIsInstance(details, QPlainTextEdit)
        text = "入口：" + "中文目录/" * 80 + "main.tex\n保存：尚未保存\nPDF：未编译\n提交检查：未知"
        details.describe(text)
        details.show()
        self.settle()
        self.assertTrue(details.isReadOnly())
        self.assertEqual(details.toPlainText(), text)
        details.selectAll()
        self.assertEqual(details.textCursor().selectedText().replace("\u2029", "\n"), text)
        self.assertLessEqual(details.height(), 150)
        self.assertGreater(details.verticalScrollBar().maximum(), 0)
        before = self.window.current_tab().editor.toPlainText()
        QTest.keyClick(details, Qt.Key.Key_X)
        self.assertEqual(details.toPlainText(), text)
        self.assertEqual(self.window.current_tab().editor.toPlainText(), before)
        selected = details.textCursor().selectedText()
        details.describe(text + "\n检查仍只读")
        self.assertEqual(details.textCursor().selectedText(), selected)


class BlockWorkspacePanelTests(TestCase):
    def setUp(self):
        from app.core.blocks.project_repository import load_project
        from app.gui.block_mode import _install_session, _set_block_mode
        from app.gui.blocks.project_session import ProjectSession
        from tests.test_gui_editor import isolated_settings
        from tests.v1_fixtures import create_project
        self.application = _app()
        self.temp = TemporaryDirectory(prefix="icstex-block-panels-")
        self.addCleanup(self.temp.cleanup)
        self.fixture = create_project(Path(self.temp.name), "block")
        self.originals = {p: p.read_bytes() for p in self.fixture.root.parent.rglob("*") if p.is_file()}
        self.window = MainWindow(settings_store=isolated_settings())
        self.previous_scale = self.application.ui_scale_manager.scale
        self.window.set_ui_scale(1.0)
        loaded = load_project(self.fixture.root.parent)
        self.session = ProjectSession(**{key: loaded[key] for key in
            ("registry", "layout", "sources", "document_theme", "project_dir")})
        self.assertTrue(_install_session(self.window, self.session))
        _set_block_mode(self.window, True)
        self.window.show()
        self.window.activateWindow()
        self.addCleanup(self.dispose)
        self.settle()

    def settle(self):
        for _ in range(8):
            self.application.processEvents()

    def dispose(self):
        self.assertEqual({p: p.read_bytes() for p in self.originals}, self.originals)
        self.assertIsNone(self.session.compile_manager)
        self.session.editor_drafts.clear()
        self.session._dirty = False
        self.window.close()
        self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.application.ui_scale_manager.apply_scale(self.previous_scale)

    def test_default_small_block_workspace_keeps_auxiliaries_collapsed(self):
        for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
            self.window.block_workspace.tabs.tabBar().setFocus()
            self.window.set_ui_scale(scale)
            self.window.resize(1080, 720)
            self.settle()
            self.assertFalse(self.window.block_diagnostics_dock.isVisible())
            self.assertFalse(self.window.block_inspector_dock.isVisible())
            self.assertGreaterEqual(self.window.block_preview_area.width(), 720)
            self.assertGreaterEqual(self.window.block_workspace.height(), 420)
            self.assertFalse(self.window.workspace.next_button.isVisible())

    def test_compact_requests_show_only_one_auxiliary_without_recreating_widgets(self):
        self.window.resize(1080, 720)
        self.settle()
        panels = self.window.block_panels
        widgets = {key: dock.widget() for key, dock in panels.docks.items()}
        for name in ("navigation", "inspector", "diagnostics", "navigation"):
            panels.docks[name].toggleViewAction().trigger()
            self.settle()
            self.assertEqual([key for key, dock in panels.docks.items() if dock.isVisible()], [name])
            self.assertEqual({key: dock.widget() for key, dock in panels.docks.items()}, widgets)

    def test_wide_visibility_and_width_survive_compact_and_mode_switch(self):
        from app.gui.block_mode import _set_block_mode
        panels = self.window.block_panels
        panels.request("inspector")
        self.window.resizeDocks([self.window.block_inspector_dock], [345], Qt.Orientation.Horizontal)
        self.window.block_nav_dock.hide()
        self.window.block_workspace.tabs.tabBar().setFocus()
        self.settle()
        width = self.window.block_inspector_dock.width()
        self.window.resize(1080, 720)
        self.settle()
        self.assertFalse(self.window.block_inspector_dock.isVisible())
        self.window.resize(1440, 900)
        self.settle()
        self.assertFalse(self.window.block_nav_dock.isVisible())
        self.assertTrue(self.window.block_inspector_dock.isVisible())
        self.assertAlmostEqual(self.window.block_inspector_dock.width(), width, delta=2)
        _set_block_mode(self.window, False)
        _set_block_mode(self.window, True)
        self.settle()
        self.assertFalse(self.window.block_nav_dock.isVisible())
        self.assertTrue(self.window.block_inspector_dock.isVisible())

    def test_focused_property_preedit_draft_and_undo_survive_resize_and_error_notice(self):
        from PySide6.QtGui import QInputMethodEvent, QTextCursor
        panels = self.window.block_panels
        block = self.session.registry.blocks()[0]
        self.session.selection.select_block(block.id, source="test")
        panels.request("inspector")
        editor = self.window.block_inspector.content_edit
        original = editor.toPlainText()
        editor.moveCursor(QTextCursor.MoveOperation.End)
        editor.insertPlainText(" unapplied")
        editor.setFocus()
        self.settle()
        QApplication.sendEvent(editor, QInputMethodEvent("zhong", []))
        self.window.resize(1080, 720)
        self.settle()
        self.assertIs(self.application.focusWidget(), editor)
        self.assertTrue(editor.isVisible())
        self.assertEqual(editor.toPlainText(), original + " unapplied")
        self.window.block_diagnostics.error_seen.emit()
        self.settle()
        self.assertIs(self.application.focusWidget(), editor)
        self.assertTrue(editor.isVisible())
        self.assertFalse(self.window.block_diagnostics_dock.isVisible())
        self.assertIn("诊断", self.window.statusBar().currentMessage())
        QApplication.sendEvent(editor, QInputMethodEvent("", []))
        editor.undo()
        self.assertEqual(editor.toPlainText(), original)
        self.assertFalse(self.session.editor_drafts)
        self.window.block_workspace.tabs.tabBar().setFocus()
        self.window.block_diagnostics.error_seen.emit()
        self.settle()
        self.assertTrue(self.window.block_diagnostics_dock.isVisible())
        self.assertIs(self.application.focusWidget(), self.window.block_workspace.tabs.tabBar())

    def test_submission_check_replaces_other_compact_auxiliary(self):
        from app.gui.block_mode import _set_block_mode
        self.window.resize(1080, 720)
        self.settle()
        self.window.block_panels.request("inspector")
        with patch.object(self.window.readiness, "request") as request:
            self.window.readiness.show()
            self.settle()
            request.assert_called_once()
        self.assertTrue(self.window.readiness._block_dock.isVisible())
        self.assertFalse(self.window.block_inspector_dock.isVisible())
        self.assertFalse(self.window.block_nav_dock.isVisible())
        self.window.resize(1440, 900)
        self.settle()
        self.assertTrue(self.window.readiness._block_dock.isVisible())
        _set_block_mode(self.window, False)
        _set_block_mode(self.window, True)
        self.settle()
        self.assertTrue(self.window.readiness._block_dock.isVisible())

    def test_error_expansion_does_not_become_a_saved_layout_preference(self):
        panels = self.window.block_panels
        self.window.block_workspace.tabs.tabBar().setFocus()
        self.window.block_diagnostics.error_seen.emit()
        self.settle()
        self.assertTrue(self.window.block_diagnostics_dock.isVisible())
        panels.save_preferences()
        saved = self.window.app_settings.settings.value("window/block_panel_visibility")
        self.assertFalse(saved["diagnostics"])
        self.window.resize(1080, 720)
        self.settle()
        self.window.block_diagnostics.error_seen.emit()
        panels.save_preferences()
        self.assertEqual(self.window.app_settings.settings.value("window/block_compact_panel"), "")

    def test_explicit_text_edit_reveals_existing_inspector_and_preferences_reload(self):
        from app.gui.block_mode import _install_session, _set_block_mode
        from app.gui.blocks.project_session import ProjectSession
        self.window.resize(1080, 720)
        self.settle()
        editor = self.window.block_inspector.content_edit
        self.window.block_nav.block_edit_requested.emit(self.session.registry.blocks()[0].id)
        self.settle()
        self.assertIs(self.application.focusWidget(), editor)
        self.assertTrue(editor.isVisible())
        self.window.block_panels.save_preferences()
        other = MainWindow(settings_store=self.window.app_settings)
        try:
            other.resize(1080, 720)
            self.assertTrue(_install_session(other, ProjectSession()))
            _set_block_mode(other, True)
            other.show()
            self.settle()
            self.assertTrue(other.block_inspector_dock.isVisible())
            self.assertFalse(other.block_nav_dock.isVisible())
            self.assertFalse(other.block_diagnostics_dock.isVisible())
        finally:
            other.close()
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_failure_without_tex_line_is_visible_but_user_stop_does_not_expand(self):
        from types import SimpleNamespace
        from app.core.compiler import BuildPurpose, CompileOutcome
        self.window.resize(1080, 720)
        self.window.block_workspace.tabs.tabBar().setFocus()
        self.settle()
        result = SimpleNamespace(ok=False, outcome=CompileOutcome.TOOLCHAIN_MISSING,
            purpose=BuildPurpose.FINAL, duration_seconds=0, stdout="", stderr="Missing synthetic engine")
        self.window.block_diagnostics._on_finished(result)
        self.settle()
        self.assertTrue(self.window.block_diagnostics_dock.isVisible())
        self.assertEqual(self.window.block_diagnostics.log_view.toPlainText(), result.stderr)
        self.assertFalse(self.window.block_diagnostics.locate_button.isEnabled())
        self.window.block_diagnostics_dock.hide()
        result.outcome = CompileOutcome.STOPPED
        self.window.block_diagnostics._on_finished(result)
        self.settle()
        self.assertFalse(self.window.block_diagnostics_dock.isVisible())

    def test_block_indicators_do_not_reuse_hidden_source_duration_or_timer(self):
        from types import SimpleNamespace
        import time
        from app.core.compiler import BuildPurpose
        from app.gui.block_mode import _set_block_mode, sync_block_pdf
        self.window.compile_time_label.setText("上次编译 123.45s")
        self.window.compile_started_at = time.perf_counter()
        self.window.compile_timer.start()
        self.session.last_result = SimpleNamespace(job_key=None, ok=True,
            purpose=BuildPurpose.FINAL, duration_seconds=1.23)
        sync_block_pdf(self.window)
        self.assertIn("Block", self.window.compile_time_label.text())
        self.assertIn("1.23s", self.window.compile_time_label.text())
        self.assertFalse(self.window.compile_timer.isActive())
        self.assertTrue(self.window.status_auto_label.isHidden())
        with patch.object(self.window, "_compile_root_for_tab", return_value=self.fixture.root):
            self.assertFalse(self.window.compile._is_active_root(self.fixture.root))
        self.window.compile.update_timer()
        self.assertIn("1.23s", self.window.compile_time_label.text())
        _set_block_mode(self.window, False)
        self.assertFalse(self.window.status_auto_label.isHidden())
        self.assertNotIn("Block", self.window.compile_time_label.text())


class WorkbenchVisualSmokeTests(TestCase):
    def test_source_and_pdf_panes_do_not_overlap_at_supported_small_window(self):
        from PySide6.QtCore import QPoint, QRect
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        previous = application.ui_scale_manager.scale
        try:
            window.auto_compile_action.setChecked(False)
            window.new_document()
            window.show()
            window.set_toolbox_visible(True)
            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                with self.subTest(scale=scale):
                    window.set_ui_scale(scale)
                    window.resize(1080, 720)
                    for _ in range(5):
                        application.processEvents()
                    splitter = window.main_splitter
                    source, pdf = splitter.widget(0), splitter.widget(1)
                    area = window.source_preview_area
                    if area._compact:
                        area.select_pdf(False)
                        application.processEvents()
                        self.assertTrue(source.isVisible())
                        self.assertFalse(pdf.isVisible())
                        self.assertTrue(splitter.rect().contains(source.geometry()))
                        area.select_pdf(True)
                        application.processEvents()
                        self.assertFalse(source.isVisible())
                    else:
                        self.assertFalse(source.geometry().intersects(pdf.geometry()),
                                         (scale, source.geometry(), pdf.geometry()))
                    self.assertTrue(pdf.isVisible())
                    self.assertTrue(splitter.rect().contains(pdf.geometry()))
                    for control in (window.pdf_panel.page_spin, window.pdf_panel.zoom_out_button,
                                    window.pdf_panel.zoom_in_button, window.pdf_panel.fit_width_button,
                                    window.pdf_panel._more_button):
                        bounds = QRect(control.mapTo(splitter, QPoint()), control.size())
                        self.assertTrue(pdf.geometry().contains(bounds), (scale, control, bounds))
                        if source.isVisible():
                            self.assertFalse(source.geometry().intersects(bounds))
                        ancestor = control.parentWidget()
                        while ancestor is not None:
                            self.assertTrue(ancestor.rect().contains(QRect(
                                control.mapTo(ancestor, QPoint()), control.size())), (scale, control, ancestor))
                            ancestor = ancestor.parentWidget()
        finally:
            window.close()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            application.ui_scale_manager.apply_scale(previous)

    def test_pdf_core_keyboard_controls_are_visible_and_operate_at_all_scales(self):
        from PySide6.QtGui import QPainter, QPdfWriter
        from PySide6.QtPdfWidgets import QPdfView
        from tests.test_gui_editor import isolated_settings
        from tests.test_gui_submission_check import wait_until
        application = _app()
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "synthetic-navigation.pdf"
            writer = QPdfWriter(str(pdf))
            painter = QPainter(writer)
            for page in range(3):
                if page:
                    writer.newPage()
                painter.drawText(100, 100, f"Synthetic PDF keyboard page {page + 1}")
            painter.end()
            del writer
            original = pdf.read_bytes()
            window = MainWindow(settings_store=isolated_settings())
            previous = application.ui_scale_manager.scale
            try:
                window.auto_compile_action.setChecked(False)
                window.new_document()
                source_before = window.current_tab().editor.toPlainText()
                window.show()
                window.set_toolbox_visible(True)
                window.activateWindow()
                # This fixture loads a standalone renderer PDF, not a build
                # record. Let the initial async document routing finish first.
                wait_until(lambda: not window.dependencies.is_busy)
                panel = window.pdf_panel
                panel.load_pdf(pdf)
                wait_until(lambda: panel._document.pageCount() == 3)
                for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                    with self.subTest(scale=scale):
                        window.set_ui_scale(scale)
                        window.resize(1080, 720)
                        window.source_preview_area.select_pdf(True)
                        panel.page_spin.setFocus()
                        for _ in range(5):
                            application.processEvents()
                        self.assertTrue(panel.page_spin.visibleRegion().contains(panel.page_spin.rect()), scale)
                        panel.jump_to_page(1)
                        QTest.keyClick(panel.page_spin, Qt.Key.Key_Up)
                        self.assertEqual(panel.current_page(), 2)
                        QTest.keyClick(panel.page_spin, Qt.Key.Key_Down)
                        self.assertEqual(panel.current_page(), 1)
                        for button in (panel.zoom_out_button, panel.zoom_in_button, panel.fit_width_button):
                            QTest.keyClick(application.focusWidget(), Qt.Key.Key_Tab)
                            self.assertIs(application.focusWidget(), button)
                            self.assertTrue(button.visibleRegion().contains(button.rect()), (scale, button.accessibleName()))
                            zoom = panel._effective_zoom(panel.current_page() - 1)
                            QTest.keyClick(button, Qt.Key.Key_Space)
                            if button is panel.fit_width_button:
                                self.assertEqual(panel._view.zoomMode(), QPdfView.ZoomMode.FitToWidth)
                            else:
                                factor = 1.15 if button is panel.zoom_in_button else 1 / 1.15
                                self.assertAlmostEqual(panel._effective_zoom(panel.current_page() - 1), zoom * factor)
                        QTest.keyClick(panel.fit_width_button, Qt.Key.Key_Tab)
                        self.assertIs(application.focusWidget(), panel.pdf_search_button)
                        self.assertTrue(panel.pdf_search_button.visibleRegion().contains(panel.pdf_search_button.rect()), scale)
                        QTest.keyClick(panel.pdf_search_button, Qt.Key.Key_Tab)
                        # Compact workspace gives PDF the whole main area;
                        # its own toolbar may therefore expose page buttons.
                        next_control = (panel._more_button if panel._more_button.isVisible()
                                        else panel.next_page_button)
                        self.assertIs(application.focusWidget(), next_control)
                        self.assertTrue(next_control.visibleRegion().contains(next_control.rect()), scale)
                        for button in (panel.pdf_search_button, panel.fit_width_button, panel.zoom_in_button,
                                       panel.zoom_out_button, panel.page_spin):
                            QTest.keyClick(application.focusWidget(), Qt.Key.Key_Backtab)
                            self.assertIs(application.focusWidget(), button)
                            self.assertTrue(button.visibleRegion().contains(button.rect()), scale)
                self.assertEqual(pdf.read_bytes(), original)
                self.assertFalse(window.compile_authorized_roots)
                self.assertEqual(window.current_tab().editor.toPlainText(), source_before)
            finally:
                window.close()
                application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                application.ui_scale_manager.apply_scale(previous)

    def test_word_count_keyboard_targets_remain_visible_in_small_console(self):
        from app.core.latex_tools import LaTeXToolchain
        from PySide6.QtGui import QTextCursor
        from tests.test_gui_editor import isolated_settings
        from tests.test_gui_submission_check import wait_until
        from tests.v1_fixtures import create_project
        application = _app()
        with TemporaryDirectory() as directory:
            sample = create_project(Path(directory))
            source = sample.root.read_text(encoding="utf-8")
            source = source.replace("\\end{document}", "\n\n".join(
                f"Synthetic reading paragraph {index}." for index in range(40)) + "\n\\end{document}")
            sample.root.write_text(source, encoding="utf-8")
            before = {p: p.read_bytes() for p in sample.root.parent.rglob("*") if p.is_file()}
            window = MainWindow(settings_store=isolated_settings())
            previous = application.ui_scale_manager.scale
            try:
                window.auto_compile_action.setChecked(False)
                window.toolchain = LaTeXToolchain(None, None)
                window.project_files.set_project_root(sample.root.parent)
                window.open_file(sample.root)
                window.show()
                window.set_toolbox_visible(True)
                window.activateWindow()
                wait_until(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
                view = window.word_count_view
                with patch.object(window.documents, "flush_root_documents") as save, \
                     patch.object(window, "compile_current") as compile_, \
                     patch("urllib.request.urlopen") as network:
                    for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                        with self.subTest(scale=scale):
                            window.set_ui_scale(scale)
                            window.resize(1080, 720)
                            window.bottom_tabs.setCurrentIndex(0)
                            application.processEvents()
                            total = sum(window.vertical_splitter.sizes())
                            window.vertical_splitter.setSizes([total - 110, 110])
                            window.bottom_tabs.setCurrentIndex(2)
                            view.refresh_button.setFocus()
                            for _ in range(5):
                                application.processEvents()
                            self.assertTrue(view.refresh_button.visibleRegion().contains(view.refresh_button.rect()))
                            editor = window.current_tab().editor
                            source_position = (editor.textCursor().position(), editor.verticalScrollBar().value())
                            QTest.keyClick(view.refresh_button, Qt.Key.Key_Space)
                            wait_until(lambda: not window.word_counts.is_busy)
                            self.assertTrue(view.last_mode_label)
                            self.assertIn(view.last_mode_label, view.meta_label.text())
                            QTest.keyClick(view.refresh_button, Qt.Key.Key_Tab)
                            for _ in range(5):
                                application.processEvents()
                            self.assertIs(application.focusWidget(), view.preview_browser)
                            for key, position in ((Qt.Key.Key_Home, QTextCursor.MoveOperation.Start),
                                                  (Qt.Key.Key_End, QTextCursor.MoveOperation.End)):
                                QTest.keyClick(view.preview_browser, key)
                                for _ in range(5):
                                    application.processEvents()
                                bar = view.preview_browser.verticalScrollBar()
                                self.assertGreater(bar.maximum(), 0)
                                self.assertEqual(bar.value(), 0 if key == Qt.Key.Key_Home else bar.maximum())
                                cursor = QTextCursor(view.preview_browser.document())
                                cursor.movePosition(position)
                                self.assertTrue(view.preview_browser.viewport().visibleRegion().contains(
                                    view.preview_browser.cursorRect(cursor)), (scale, key))
                            window.bottom_tabs.setCurrentIndex(0)
                            application.processEvents()
                            window.bottom_tabs.setCurrentIndex(2)
                            view.refresh_button.setFocus()
                            for _ in range(5):
                                application.processEvents()
                            self.assertTrue(view.refresh_button.visibleRegion().contains(view.refresh_button.rect()))
                            QTest.keyClick(view.refresh_button, Qt.Key.Key_Tab)
                            QTest.keyClick(view.preview_browser, Qt.Key.Key_Backtab)
                            for _ in range(5):
                                application.processEvents()
                            self.assertIs(application.focusWidget(), view.refresh_button)
                            self.assertTrue(view.refresh_button.visibleRegion().contains(view.refresh_button.rect()))
                            self.assertEqual((editor.textCursor().position(), editor.verticalScrollBar().value()), source_position)
                    save.assert_not_called()
                    compile_.assert_not_called()
                    network.assert_not_called()
                self.assertFalse(window.compile_authorized_roots)
                self.assertEqual(before, {p: p.read_bytes() for p in before})
                self.assertEqual(window.current_tab().editor.toPlainText(), sample.root.read_text(encoding="utf-8"))
            finally:
                window.close()
                application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                application.ui_scale_manager.apply_scale(previous)

    def test_submission_check_keyboard_results_and_details_remain_visible_in_small_console(self):
        from app.core.latex_tools import LaTeXToolchain
        from PySide6.QtGui import QTextCursor
        from PySide6.QtTest import QSignalSpy
        from tests.test_gui_editor import isolated_settings
        from tests.test_gui_submission_check import wait_until
        from tests.v1_fixtures import create_project
        application = _app()
        with TemporaryDirectory() as directory:
            sample = create_project(Path(directory))
            before = {p: p.read_bytes() for p in sample.root.parent.rglob("*") if p.is_file()}
            window = MainWindow(settings_store=isolated_settings())
            previous = application.ui_scale_manager.scale
            try:
                window.auto_compile_action.setChecked(False)
                window.toolchain = LaTeXToolchain(None, None)
                window.project_files.set_project_root(sample.root.parent)
                window.open_file(sample.root)
                window.show()
                window.set_toolbox_visible(True)
                window.activateWindow()
                wait_until(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
                panel = window.submission_panel
                actions = QSignalSpy(panel.actionRequested)
                with patch.object(window.documents, "flush_root_documents") as save, \
                     patch.object(window, "compile_current") as compile_, \
                     patch("urllib.request.urlopen") as network:
                    window.readiness.show()
                    wait_until(lambda: not window.readiness.is_busy)
                    self.assertIsNotNone(panel.report)
                    for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                        with self.subTest(scale=scale):
                            window.set_ui_scale(scale)
                            window.resize(1080, 720)
                            window.bottom_tabs.setCurrentIndex(0)
                            application.processEvents()
                            total = sum(window.vertical_splitter.sizes())
                            window.vertical_splitter.setSizes([total - 110, 110])
                            window.bottom_tabs.setCurrentIndex(4)
                            panel.refresh_button.setFocus()
                            for _ in range(5):
                                application.processEvents()
                            self.assertTrue(panel.refresh_button.visibleRegion().contains(panel.refresh_button.rect()))
                            editor = window.current_tab().editor
                            source_position = (editor.textCursor().position(), editor.verticalScrollBar().value())
                            QTest.keyClick(panel.refresh_button, Qt.Key.Key_Space)
                            wait_until(lambda: not window.readiness.is_busy)
                            self.assertEqual(panel.tree.topLevelItemCount(), len(panel.report.items))
                            QTest.keyClick(panel.refresh_button, Qt.Key.Key_Tab)
                            if application.focusWidget() is panel.action_button:
                                self.assertTrue(panel.action_button.visibleRegion().contains(panel.action_button.rect()))
                                QTest.keyClick(panel.action_button, Qt.Key.Key_Tab)
                            self.assertIs(application.focusWidget(), panel.tree)
                            for index in range(panel.tree.topLevelItemCount()):
                                if index:
                                    QTest.keyClick(panel.tree, Qt.Key.Key_Down)
                                for _ in range(5):
                                    application.processEvents()
                                item = panel.tree.currentItem()
                                self.assertIs(item, panel.tree.topLevelItem(index))
                                rect = panel.tree.visualItemRect(item)
                                self.assertTrue(panel.tree.viewport().visibleRegion().contains(rect), (scale, index, rect))
                                original_index = item.data(0, Qt.ItemDataRole.UserRole)
                                checked = panel.report.items[original_index]
                                self.assertIn(checked.reason, panel.detail.toPlainText())
                                self.assertIn(checked.input_id, panel.technical_detail.toPlainText())
                            QTest.keyClick(panel.tree, Qt.Key.Key_Tab)
                            self.assertIs(application.focusWidget(), panel.detail)
                            for key, position in ((Qt.Key.Key_Home, QTextCursor.MoveOperation.Start),
                                                  (Qt.Key.Key_End, QTextCursor.MoveOperation.End)):
                                QTest.keyClick(panel.detail, key)
                                for _ in range(5):
                                    application.processEvents()
                                bar = panel.detail.verticalScrollBar()
                                self.assertEqual(bar.value(), 0 if key == Qt.Key.Key_Home else bar.maximum())
                                cursor = QTextCursor(panel.detail.document())
                                cursor.movePosition(position)
                                self.assertTrue(panel.detail.viewport().visibleRegion().contains(panel.detail.cursorRect(cursor)),
                                                (scale, key, panel.detail.cursorRect(cursor)))
                            QTest.keyClick(panel.detail, Qt.Key.Key_Backtab)
                            self.assertIs(application.focusWidget(), panel.tree)
                            QTest.keyClick(panel.tree, Qt.Key.Key_Backtab)
                            if application.focusWidget() is panel.action_button:
                                QTest.keyClick(panel.action_button, Qt.Key.Key_Backtab)
                            for _ in range(5):
                                application.processEvents()
                            self.assertIs(application.focusWidget(), panel.refresh_button)
                            self.assertTrue(panel.refresh_button.visibleRegion().contains(panel.refresh_button.rect()))
                            self.assertEqual((editor.textCursor().position(), editor.verticalScrollBar().value()), source_position)
                    save.assert_not_called()
                    compile_.assert_not_called()
                    network.assert_not_called()
                self.assertEqual(actions.count(), 0)
                self.assertFalse(window.compile_authorized_roots)
                self.assertEqual(before, {p: p.read_bytes() for p in before})
                self.assertEqual(window.current_tab().editor.toPlainText(), sample.root.read_text(encoding="utf-8"))
            finally:
                window.close()
                application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                application.ui_scale_manager.apply_scale(previous)

    def test_small_console_keeps_diagnostic_keyboard_targets_visible_at_all_scales(self):
        from app.core.diagnostics import Diagnostic
        from tests.test_gui_editor import isolated_settings
        application = _app()
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            original = "\n".join(f"Synthetic line {index}" for index in range(200)) + "\n"
            root.write_text(original, encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            previous = application.ui_scale_manager.scale
            try:
                window.auto_compile_action.setChecked(False)
                window.open_file(root)
                window.show()
                window.activateWindow()
                panel = window.diagnostic_panel
                panel.set_diagnostics([
                    Diagnostic("info", "A", "Synthetic navigation fixture", root, 3),
                    Diagnostic("info", "B", "Synthetic navigation fixture", root, 80),
                ])
                for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                    with self.subTest(scale=scale):
                        window.set_ui_scale(scale)
                        window.resize(1080, 720)
                        window.bottom_tabs.setCurrentIndex(0)
                        application.processEvents()
                        total = sum(window.vertical_splitter.sizes())
                        window.vertical_splitter.setSizes([total - 110, 110])
                        editor = window.current_tab().editor
                        cursor = editor.textCursor()
                        cursor.setPosition(editor.document().findBlockByNumber(80).position())
                        editor.setTextCursor(cursor)
                        editor.verticalScrollBar().setValue(60)
                        before = (editor.textCursor().position(), editor.verticalScrollBar().value())
                        window.bottom_tabs.setCurrentIndex(3)
                        panel.refresh_button.setFocus()
                        for _ in range(5):
                            application.processEvents()
                        self.assertTrue(panel.refresh_button.visibleRegion().contains(panel.refresh_button.rect()))
                        QTest.keyClick(panel.refresh_button, Qt.Key.Key_Tab)
                        for _ in range(5):
                            application.processEvents()
                        self.assertIs(application.focusWidget(), panel.table)
                        panel.table.setCurrentCell(0, 0)
                        QTest.keyClick(panel.table, Qt.Key.Key_Down)
                        for _ in range(5):
                            application.processEvents()
                        row = panel.table.visualItemRect(panel.table.item(1, 0))
                        self.assertTrue(panel.table.viewport().visibleRegion().contains(row),
                                        (scale, row, panel.table.viewport().visibleRegion()))
                        mapped = row.translated(panel.table.viewport().mapTo(window, row.topLeft()) - row.topLeft())
                        self.assertTrue(window.rect().contains(mapped), (scale, mapped))
                        QTest.keyClick(panel.table, Qt.Key.Key_Backtab)
                        for _ in range(5):
                            application.processEvents()
                        self.assertIs(application.focusWidget(), panel.refresh_button)
                        self.assertTrue(panel.refresh_button.visibleRegion().contains(panel.refresh_button.rect()))
                        self.assertEqual((editor.textCursor().position(), editor.verticalScrollBar().value()), before)
                        self.assertEqual(editor.toPlainText(), original)
                        self.assertEqual(root.read_text(encoding="utf-8"), original)
                        self.assertFalse(window.compile_authorized_roots)
            finally:
                window.close()
                application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                application.ui_scale_manager.apply_scale(previous)

    def test_console_collapse_keeps_header_and_restores_diagnostic_focus_at_all_scales(self):
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        previous = application.ui_scale_manager.scale
        try:
            window.new_document()
            window.show()
            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                with self.subTest(scale=scale):
                    window.set_ui_scale(scale)
                    window.resize(1080, 720)
                    window.bottom_tabs.setCurrentIndex(3)
                    for _ in range(5):
                        application.processEvents()
                    window.bottom_collapse_button.click()
                    for _ in range(5):
                        application.processEvents()
                    self.assertTrue(window.bottom_tabs.isHidden())
                    button = window.bottom_collapse_button
                    self.assertTrue(button.visibleRegion().contains(button.rect()))
                    self.assertEqual(button.toolTip(), "展开控制台：日志、错误、字数和检查")
                    window.resize(1100, 740)
                    application.processEvents()
                    self.assertTrue(window.bottom_tabs.isHidden())
                    button.click()
                    window.diagnostic_panel.refresh_button.setFocus()
                    for _ in range(5):
                        application.processEvents()
                    self.assertFalse(window.bottom_tabs.isHidden())
                    target = window.diagnostic_panel.refresh_button
                    self.assertTrue(target.visibleRegion().contains(target.rect()))
            self.assertFalse(window.compile_authorized_roots)
        finally:
            window.close()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            application.ui_scale_manager.apply_scale(previous)

    def test_tool_rail_precedes_its_panel_in_the_main_window_focus_chain(self):
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        try:
            window.new_document()
            window.show()
            window.activateWindow()
            window.set_toolbox_visible(True)
            navigation = window.toolbox_navigation
            navigation.setCurrentIndex(7)
            panel = window.references_panel
            panel.reference_tabs.setCurrentIndex(1)
            navigation.setFocus()
            application.processEvents()
            button = navigation.navigationButton(7)
            self.assertIs(application.focusWidget(), button)
            QTest.keyClick(button, Qt.Key.Key_Tab)
            application.processEvents()
            self.assertTrue(panel.isAncestorOf(application.focusWidget()))
            QTest.keyClick(application.focusWidget(), Qt.Key.Key_Backtab)
            self.assertIs(application.focusWidget(), button)
            QTest.keyClick(button, Qt.Key.Key_Backtab)
            previous = application.focusWidget()
            self.assertIsNotNone(previous)
            self.assertFalse(navigation.isAncestorOf(previous))
            QTest.keyClick(previous, Qt.Key.Key_Tab)
            self.assertIs(application.focusWidget(), button)
        finally:
            window.close()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_tool_rail_accepts_tab_entry_and_reverse_exit(self):
        from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget
        from app.gui.toolbox_navigation import ToolboxNavigation
        application = _app()
        window = QWidget()
        layout = QVBoxLayout(window)
        before = QPushButton("Before")
        navigation = ToolboxNavigation()
        after = QPushButton("After")
        layout.addWidget(before)
        layout.addWidget(navigation)
        layout.addWidget(after)
        for index in range(9):
            navigation.addTab(QWidget(), str(index), "file")
        navigation.finish()
        navigation.setCurrentIndex(7)
        try:
            window.show()
            window.activateWindow()
            for selected in (7, 0, 8, 3):
                navigation.setCurrentIndex(selected)
                for index in range(navigation.count()):
                    self.assertEqual(navigation.navigationButton(index).focusPolicy(),
                                     Qt.FocusPolicy.StrongFocus if index == selected else Qt.FocusPolicy.ClickFocus)
                before.setFocus()
                application.processEvents()
                self.assertIs(application.focusWidget(), before)
                QTest.keyClick(before, Qt.Key.Key_Tab)
                application.processEvents()
                self.assertIs(application.focusWidget(), navigation.navigationButton(selected))
                QTest.keyClick(application.focusWidget(), Qt.Key.Key_Backtab)
                self.assertIs(application.focusWidget(), before)
                QTest.keyClick(before, Qt.Key.Key_Tab)
                QTest.keyClick(application.focusWidget(), Qt.Key.Key_Tab)
                self.assertIs(application.focusWidget(), after)
        finally:
            window.close()
            window.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_focus_scroll_timer_is_destroyed_with_its_container(self):
        from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget
        from shiboken6 import isValid
        from app.gui.insert_panel import scrollable_panel
        application = _app()
        content = QWidget()
        layout = QVBoxLayout(content)
        button = QPushButton("Target")
        layout.addWidget(button)
        area = scrollable_panel(content)
        timer = area._focus_timer
        area.show()
        area.activateWindow()
        button.setFocus()
        application.processEvents()
        timer.start(0)
        area.deleteLater()
        application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(isValid(area))
        self.assertFalse(isValid(timer))
        application.processEvents()

    def test_external_reverse_tab_reveals_scrolled_citation_action_at_all_scales(self):
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        previous = application.ui_scale_manager.scale
        try:
            window.new_document()
            window.show()
            window.activateWindow()
            window.set_toolbox_visible(True)
            window.sidebar_tabs.setCurrentIndex(7)
            panel = window.references_panel
            panel.reference_tabs.setCurrentIndex(1)
            panel.check_locate_button.setEnabled(True)
            scroll = window.sidebar_tabs.widget(7)
            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                with self.subTest(scale=scale):
                    window.set_ui_scale(scale)
                    window.resize(1080, 720)
                    application.processEvents()
                    scroll.verticalScrollBar().setValue(0)
                    window.log_view.setFocus()
                    application.processEvents()
                    button = panel.check_locate_button
                    for _ in range(6):
                        self.assertIsNotNone(application.focusWidget())
                        QTest.keyClick(application.focusWidget(), Qt.Key.Key_Backtab)
                        application.processEvents()
                        if application.focusWidget() is button:
                            break
                    self.assertIs(application.focusWidget(), button)
                    rect = button.rect()
                    rect.moveTopLeft(button.mapTo(window, rect.topLeft()))
                    self.assertTrue(window.rect().contains(rect), rect)
                    self.assertTrue(button.visibleRegion().contains(button.rect()))
            self.assertFalse(window.compile_authorized_roots)
        finally:
            window.close()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            application.ui_scale_manager.apply_scale(previous)

    def test_read_only_workbench_tables_release_tab_focus_at_all_scales(self):
        from PySide6.QtWidgets import QAbstractItemView, QTableWidgetItem
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        previous = application.ui_scale_manager.scale
        cases = (
            ("outline", window.outline_panel.table, 1, None, None),
            ("search", window.search_panel.table, 2, None, None),
            ("images", window.images_panel.table, 3, window.images_panel.material_tabs, 0),
            ("materials", window.images_panel.health_table, 3, window.images_panel.material_tabs, 1),
            ("history", window.history_panel.table, 4, None, None),
            ("references", window.references_panel.table, 7, window.references_panel.reference_tabs, 0),
            ("citations", window.references_panel.health_table, 7, window.references_panel.reference_tabs, 1),
            ("labels", window.labels_panel.table, 8, None, None),
            ("errors", window.error_table, None, window.bottom_tabs, 1),
            ("diagnostics", window.diagnostic_panel.table, None, window.bottom_tabs, 3),
        )
        try:
            window.show()
            window.activateWindow()
            window.set_toolbox_visible(True)
            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                window.set_ui_scale(scale)
                window.resize(1080, 720)
                for name, table, tool, tabs, tab_index in cases:
                    if tool is not None:
                        window.sidebar_tabs.setCurrentIndex(tool)
                    if tabs is not None:
                        tabs.setCurrentIndex(tab_index)
                    table.setRowCount(2)
                    for row in range(2):
                        for column in range(table.columnCount()):
                            table.setItem(row, column, QTableWidgetItem(f"synthetic-{row}-{column}"))
                    self.assertEqual(table.editTriggers(), QAbstractItemView.EditTrigger.NoEditTriggers)
                    table.setCurrentCell(0, 0)
                    table.setFocus()
                    application.processEvents()
                    self.assertIs(application.focusWidget(), table, (scale, name))
                    QTest.keyClick(table, Qt.Key.Key_Down)
                    self.assertEqual(table.currentRow(), 1, (scale, name))
                    QTest.keyClick(table, Qt.Key.Key_Up)
                    self.assertEqual(table.currentRow(), 0, (scale, name))
                    for key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                        with self.subTest(scale=scale, table=name, key=key):
                            table.setFocus()
                            QTest.keyClick(table, key)
                            application.processEvents()
                            focus = application.focusWidget()
                            self.assertIsNot(focus, table)
                            self.assertIsNotNone(focus)
                            self.assertTrue(window.isAncestorOf(focus))
                            self.assertEqual(table.item(0, 0).text(), "synthetic-0-0")
            self.assertFalse(window.compile_authorized_roots)
        finally:
            window.close()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            application.ui_scale_manager.apply_scale(previous)

    def test_small_window_navigation_scrolls_focused_keyboard_target_into_view(self):
        from tests.test_gui_editor import isolated_settings, wait_until
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        previous = application.ui_scale_manager.scale
        try:
            window.show()
            window.activateWindow()
            window.set_toolbox_visible(True)
            window.set_ui_scale(1.5)
            window.resize(1080, 720)
            navigation = window.toolbox_navigation
            # C's compact layout can now fit all items. Force actual overflow
            # so this still tests scrolling rather than only focus traversal.
            navigation.rail_scroll.setFixedHeight(260)
            application.processEvents()
            self.assertGreater(navigation.rail_scroll.verticalScrollBar().maximum(), 0)
            first = navigation.navigationButton(0)
            first.setFocus()
            self.assertTrue(wait_until(first.hasFocus))
            for index in range(1, navigation.count()):
                QTest.keyClick(application.focusWidget(), Qt.Key.Key_Down)
                application.processEvents()
                target = navigation.navigationButton(index)
                self.assertIs(application.focusWidget(), target)
                self.assertEqual(navigation.currentIndex(), index)
                self.assertTrue(target.visibleRegion().contains(target.rect()), index)
            self.assertGreater(navigation.rail_scroll.verticalScrollBar().value(), 0)
            for index in reversed(range(navigation.count() - 1)):
                QTest.keyClick(application.focusWidget(), Qt.Key.Key_Up)
                application.processEvents()
                target = navigation.navigationButton(index)
                self.assertIs(application.focusWidget(), target)
                self.assertTrue(target.visibleRegion().contains(target.rect()), index)
            self.assertFalse(window.compile_authorized_roots)
        finally:
            window.close()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            application.ui_scale_manager.apply_scale(previous)

    def test_citation_panel_fits_side_dock_and_exposes_full_issue_text_at_all_scales(self):
        from app.core.citation_health import CitationItem, CitationLocation, CitationReport
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        previous = application.ui_scale_manager.scale
        scope = Path("/synthetic-citation-layout")
        location = CitationLocation(scope / "chapters/long-source-directory/child.tex", 27)
        key = "LongMissingCitationIdentifier2026"
        report = CitationReport(None, "synthetic-input", (
            CitationItem("citation_missing", "fail", key, "No matching entry", (location,)),
            CitationItem("entry_unused", "suggestion", "Unused", "Keep author choice", (location,)),
        ), frozenset(), True, True, ())
        panel = window.references_panel
        try:
            window.show()
            window.set_toolbox_visible(True)
            window.sidebar_tabs.setCurrentIndex(7)
            scroll = window.sidebar_tabs.widget(7)
            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                window.set_ui_scale(scale)
                window.resize(1080, 720)
                panel.set_citation_report(report, scope, "2026-09-11T19:00:00+08:00 · main.tex")
                for tab_index in (0, 1):
                    with self.subTest(scale=scale, tab=tab_index):
                        panel.reference_tabs.setCurrentIndex(tab_index)
                        application.processEvents()
                        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
                        controls = ((panel.add_button, panel.import_button, panel.refresh_button,
                                     panel.insert_button, panel.check_button) if tab_index == 0 else
                                    (panel.check_refresh_button, panel.check_cancel_button, panel.check_locate_button))
                        for control in controls:
                            scroll.ensureWidgetVisible(control)
                            application.processEvents()
                            rect = control.rect()
                            rect.moveTopLeft(control.mapTo(scroll.viewport(), rect.topLeft()))
                            self.assertTrue(scroll.viewport().rect().contains(rect), (scale, control.text(), rect))
                            self.assertTrue(control.visibleRegion().contains(control.rect()),
                                            (scale, control.text(), control.visibleRegion().boundingRect()))
                            self.assertGreaterEqual(control.width(), control.sizeHint().width())
                with self.subTest(scale=scale, detail=True):
                    self.assertIn(key, panel.check_detail.toPlainText())
                    self.assertIn("2026-09-11T19:00:00+08:00 · main.tex", panel.check_detail.toPlainText())
                    self.assertEqual(panel.health_table.item(0, 2).toolTip(), key)
                    self.assertEqual(panel.check_locations.item(0).toolTip(), panel.check_locations.item(0).text())
                    self.assertGreaterEqual(panel.health_table.rowHeight(0), panel.health_table.fontMetrics().height() + 4)
                for index in range(window.sidebar_tabs.count()):
                    button = window.sidebar_tabs.navigationButton(index)
                    window.sidebar_tabs.rail_scroll.ensureWidgetVisible(button)
                    application.processEvents()
                    self.assertTrue(button.visibleRegion().contains(button.rect()), (scale, index))
            self.assertIs(panel.citation_report, report)
            self.assertFalse(window.compile_authorized_roots)
        finally:
            window.close()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            application.ui_scale_manager.apply_scale(previous)

    def test_submission_delivery_controls_are_scroll_reachable_at_large_font(self):
        from app.gui.submission_delivery_dialog import SubmissionDeliveryDialog
        from tests.test_gui_editor import isolated_settings
        from tests.v1_fixtures import create_project
        application = _app()
        with TemporaryDirectory() as temp:
            sample = create_project(Path(temp).resolve(), "single")
            window = MainWindow(settings_store=isolated_settings())
            window.project_files.set_project_root(sample.root.parent)
            window.open_file(sample.root)
            dialog = SubmissionDeliveryDialog(window)
            try:
                for size in (12, 18):
                    font = dialog.font()
                    font.setPointSize(size)
                    dialog.setFont(font)
                    dialog.resize(760, 620)
                    dialog.show()
                    application.processEvents()
                    for control in (dialog.save_button, dialog.compile_button, dialog.review_button,
                            dialog.include_source, dialog.include_report, dialog.pdf_name,
                            dialog.technical_button, dialog.close_button):
                        if dialog.scroller.isAncestorOf(control):
                            dialog.scroller.ensureWidgetVisible(control)
                            application.processEvents()
                        self.assertTrue(control.visibleRegion().contains(control.rect()))
                        self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().topLeft())))
                        self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().bottomRight())))
                    self.assertTrue(dialog.preview.isReadOnly())
                    self.assertFalse(dialog.action_button.isEnabled())
                    self.assertFalse(window.compile_authorized_roots)
            finally:
                dialog.reject()
                dialog.deleteLater()
                window.close()
                window.deleteLater()
                application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_migration_review_and_open_controls_fit_large_font(self):
        from app.gui.project_migration_dialog import ProjectMigrationDialog
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        dialog = ProjectMigrationDialog(window)
        try:
            for size in (12, 18):
                font = dialog.font()
                font.setPointSize(size)
                dialog.setFont(font)
                dialog.resize(760, 620)
                dialog.show()
                application.processEvents()
                for control in (dialog.choose_button, dialog.review_button, dialog.target_button,
                                dialog.action_button, dialog.close_button):
                    if dialog.scroller.isAncestorOf(control):
                        dialog.scroller.ensureWidgetVisible(control)
                        application.processEvents()
                    self.assertTrue(control.visibleRegion().contains(control.rect()))
                    self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().topLeft())))
                    self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().bottomRight())))
                self.assertTrue(dialog.preview.isReadOnly())
                self.assertFalse(dialog.action_button.isEnabled())
                self.assertFalse(dialog.open_button.isEnabled())
                self.assertTrue(dialog.open_button.isHidden())
        finally:
            dialog.reject()
            dialog.deleteLater()
            window.close()
            window.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)


    def test_cocoa_guard_precedes_editor_ui_construction(self):
        from app.gui import main_window, macos_accessibility
        from tests.test_gui_editor import isolated_settings
        application = _app()
        build = main_window.build_ui
        with patch.object(macos_accessibility, "install_selected_children_guard") as install:
            def checked_build(window):
                install.assert_called_once_with()
                return build(window)
            with patch.object(main_window, "build_ui", side_effect=checked_build):
                window = MainWindow(settings_store=isolated_settings())
            window.close()
            window.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_interrupted_write_review_actions_fit_large_font(self):
        from app.gui.block_write_recovery_dialog import BlockWriteRecoveryDialog
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        dialog = BlockWriteRecoveryDialog(window)
        try:
            for size in (12, 18):
                font = dialog.font()
                font.setPointSize(size)
                dialog.setFont(font)
                dialog.resize(760, 600)
                dialog.show()
                application.processEvents()
                for control in (dialog.choose_button, dialog.target_button, dialog.action_button, dialog.close_button):
                    self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().topLeft())))
                    self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().bottomRight())))
                self.assertTrue(dialog.preview.isReadOnly())
                self.assertFalse(dialog.action_button.isEnabled())
        finally:
            dialog.reject()
            dialog.deleteLater()
            window.close()
            window.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_recovery_draft_review_buttons_fit_large_font(self):
        from app.gui.project_recovery_dialog import RecoveryDraftDialog
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        dialog = RecoveryDraftDialog(window)
        try:
            for size in (12, 18):
                font = dialog.font()
                font.setPointSize(size)
                dialog.setFont(font)
                dialog.resize(760, 560)
                dialog.show()
                application.processEvents()
                for control in (dialog.choose_button, dialog.apply_button, dialog.close_button):
                    if dialog.scroller.isAncestorOf(control):
                        dialog.scroller.ensureWidgetVisible(control)
                        application.processEvents()
                    self.assertTrue(control.visibleRegion().contains(control.rect()))
                    self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().topLeft())))
                    self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().bottomRight())))
                self.assertTrue(dialog.preview.isReadOnly())
                self.assertFalse(dialog.apply_button.isEnabled())
        finally:
            dialog.reject()
            dialog.deleteLater()
            window.close()
            window.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_checkpoint_review_actions_and_close_fit_with_large_font(self):
        from app.gui.project_checkpoint_dialog import ProjectCheckpointDialog
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        dialog = ProjectCheckpointDialog(window, restore=True)
        try:
            dialog.status.setText("已验证合成检查点；请审阅相对路径和独立草稿，再选择新目录。")
            for size in (12, 18):
                font = dialog.font()
                font.setPointSize(size)
                dialog.setFont(font)
                dialog.resize(760, 560)
                dialog.show()
                application.processEvents()
                for control in (dialog.open_button, dialog.target_button, dialog.action_button, dialog.close_button):
                    if dialog.scroller.isAncestorOf(control):
                        dialog.scroller.ensureWidgetVisible(control)
                        application.processEvents()
                    self.assertTrue(control.visibleRegion().contains(control.rect()))
                    self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().topLeft())))
                    self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().bottomRight())))
                self.assertTrue(dialog.preview.isReadOnly())
                self.assertFalse(dialog.action_button.isEnabled())
        finally:
            dialog.reject()
            dialog.deleteLater()
            window.close()
            window.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_review_dialogs_keep_first_file_row_and_fixed_actions_at_large_scale(self):
        from app.gui.project_checkpoint_dialog import ProjectCheckpointDialog
        from app.gui.project_recovery_dialog import RecoveryDraftDialog
        from app.gui.block_write_recovery_dialog import BlockWriteRecoveryDialog
        from PySide6.QtWidgets import QTreeWidgetItem, QComboBox
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        dialogs = [ProjectCheckpointDialog(window, restore=True), RecoveryDraftDialog(window),
                   BlockWriteRecoveryDialog(window)]
        try:
            for dialog in dialogs:
                font = dialog.font()
                font.setPointSize(18)
                dialog.setFont(font)
                item = QTreeWidgetItem(["Synthetic file", "Current input", "SHA-256"])
                item.setData(0, Qt.ItemDataRole.UserRole, ("file", "Synthetic file"))
                dialog.tree.addTopLevelItem(item)
                if isinstance(dialog, BlockWriteRecoveryDialog):
                    choice = QComboBox()
                    choice.addItems(["请选择版本", "写入前", "写入后"])
                    dialog.tree.setItemWidget(item, 2, choice)
                dialog.resize(760, 620)
                dialog.show()
                application.processEvents()
                dialog.tree.setCurrentItem(item)
                dialog.scroller.ensureWidgetVisible(dialog.tree)
                application.processEvents()
                self.assertTrue(dialog.tree.viewport().visibleRegion().contains(dialog.tree.visualItemRect(item)))
                primary = getattr(dialog, "action_button", None) or dialog.apply_button
                self.assertFalse(dialog.scroller.isAncestorOf(primary))
                for button in (primary, dialog.close_button):
                    self.assertTrue(button.visibleRegion().contains(button.rect()))
                self.assertLessEqual(dialog.height(), 620)
                dialog.hide()
        finally:
            for dialog in dialogs:
                dialog.reject()
                dialog.deleteLater()
            window.close()
            window.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_source_repair_mapping_controls_and_cancel_remain_reachable(self):
        from types import SimpleNamespace
        from app.core.blocks.table_import import read_csv_text
        from app.gui.blocks.source_repair_dialog import SourceTableMappingDialog
        from PySide6.QtWidgets import QDialogButtonBox, QScrollArea
        application = _app()
        local = read_csv_text("Key,Value\nA,10\n")
        snapshot = SimpleNamespace(local_tables={"t": local}, blocks={"t": {"alias": "合成来源表格"}})
        dialog = SourceTableMappingDialog(None, snapshot, "t", None, None)
        try:
            for size in (12, 18):
                font = dialog.font()
                font.setPointSize(size)
                dialog.setFont(font)
                dialog.resize(760, 600)
                dialog.show()
                application.processEvents()
                scroll = dialog.findChild(QScrollArea)
                scroll.ensureWidgetVisible(dialog.load_button)
                application.processEvents()
                self.assertTrue(scroll.viewport().rect().contains(
                    dialog.load_button.mapTo(scroll.viewport(), dialog.load_button.rect().center())))
                self.assertTrue(dialog.rect().contains(dialog.preview_button.mapTo(dialog, dialog.preview_button.rect().center())))
                cancel = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel)
                self.assertTrue(dialog.rect().contains(cancel.mapTo(dialog, cancel.rect().center())))
            self.assertFalse(dialog.preview_button.isEnabled())
            dialog.encoding.setCurrentIndex(1)
            self.assertIsNone(dialog.parsed)
            self.assertIsNone(dialog.candidate)
        finally:
            dialog.close()
            dialog.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_merge_preview_controls_are_reachable_and_changes_require_a_fresh_preview(self):
        from app.core.blocks.source_merge import merge_three_way
        from app.gui.blocks.merge_dialog import MergeDialog
        from tests.test_source_merge import table
        from PySide6.QtWidgets import QDialogButtonBox
        application = _app()
        result = merge_three_way(table({"r1": {"a": "base", "b": "keep"}}),
                                 table({"r1": {"a": "remote", "b": "keep"}}),
                                 table({"r1": {"a": "local", "b": "keep"}}))
        before = result.data.to_content_dict()
        dialog = MergeDialog(result)
        try:
            for point_size in (12, 18):
                font = dialog.font()
                font.setPointSize(point_size)
                dialog.setFont(font)
                dialog.resize(760, 640)
                dialog.show()
                application.processEvents()
                for button in (dialog.preview_button, dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)):
                    self.assertTrue(dialog.rect().contains(button.mapTo(dialog, button.rect().center())))
                self.assertTrue(dialog.preview.isReadOnly())
            dialog._manual_buttons[0].setChecked(True)
            self.assertFalse(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
            dialog.preview_button.click()
            self.assertIn('"value": ""', dialog.preview.toPlainText())
            dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
            self.assertEqual(dialog.result.data.cell("r1", "a").value, "")
            self.assertEqual(dialog.result.data.cell("r1", "b").value, "keep")
            self.assertEqual(result.data.to_content_dict(), before)
        finally:
            dialog.close()
            dialog.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_table_draft_controls_are_reachable_in_a_narrow_large_font_workspace(self):
        from app.core.blocks.registry import BlockRegistry, CreateBlockInput
        from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow
        from app.gui.blocks.project_session import ProjectSession
        from app.gui.blocks.workspace_widget import BlockWorkspaceWidget
        application = _app()
        registry = BlockRegistry()
        block = registry.create(CreateBlockInput(type="table", alias="合成的长名称表格",
            content=TableData(columns=[ColumnSpec("c1", "Value")],
                rows=[TableRow("r1", {"c1": Cell("text", "before")})]).to_content_dict()))
        session = ProjectSession(registry=registry)
        workspace = BlockWorkspaceWidget(session)
        try:
            font = workspace.font()
            font.setPointSizeF(18)
            workspace.setFont(font)
            workspace.resize(300, 380)
            workspace.show()
            workspace.open_table(block.id)
            workspace.table_editor.table.item(0, 0).setText("unapplied")
            application.processEvents()
            scroll = workspace.tabs.widget(1)
            for button in (workspace.table_apply_button, workspace.table_discard_button):
                scroll.ensureWidgetVisible(button)
                QTest.qWait(20)
                rect = button.rect()
                rect.moveTopLeft(button.mapTo(scroll.viewport(), rect.topLeft()))
                self.assertTrue(scroll.viewport().rect().contains(rect), (rect, scroll.viewport().rect()))
            self.assertEqual(block.content["rows"][0]["cells"]["c1"]["value"], "before")
            self.assertEqual(session.undo_stack.count(), 0)
            self.assertIsNone(session.compile_manager)
        finally:
            session.shutdown()
            workspace.close()
            workspace.deleteLater()
            session.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_button_flow_wraps_whole_buttons_without_overlap(self):
        from app.gui.responsive.helpers import ButtonFlowLayout
        from PySide6.QtWidgets import QPushButton, QWidget
        application = _app()
        widget = QWidget()
        flow = ButtonFlowLayout(widget)
        buttons = [QPushButton(text) for text in ("组合为 Row", "组合为 Grid", "取消组合", "撤销")]
        for button in buttons:
            flow.addWidget(button)
        try:
            widget.show()
            for width in (260, 640, 280):
                widget.resize(width, 400)
                application.processEvents()
                for index, button in enumerate(buttons):
                    self.assertTrue(widget.rect().contains(button.geometry()))
                    self.assertGreaterEqual(button.width(), button.sizeHint().width())
                    for other in buttons[index + 1:]:
                        self.assertFalse(button.geometry().intersects(other.geometry()))
                if width == 260:
                    self.assertGreater(buttons[-1].y(), buttons[0].y())
        finally:
            widget.close()
            widget.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_block_preview_switch_preserves_widgets_and_focused_editor(self):
        from app.gui.blocks.workspace_widget import BlockPreviewArea
        from PySide6.QtWidgets import QLineEdit, QWidget, QVBoxLayout
        application = _app()
        editor, pdf = QWidget(), QWidget()
        edit = QLineEdit()
        QVBoxLayout(editor).addWidget(edit)
        area = BlockPreviewArea(editor, pdf)
        parents = editor.parentWidget(), pdf.parentWidget()
        try:
            area.resize(600, 500)
            area.show()
            application.processEvents()
            area.pdf_button.click()
            self.assertTrue(editor.isHidden())
            area.resize(1400, 500)
            application.processEvents()
            self.assertFalse(editor.isHidden())
            edit.setFocus()
            QTest.keyClicks(edit, "pending draft")
            area.resize(600, 500)
            application.processEvents()
            self.assertFalse(editor.isHidden())
            self.assertTrue(pdf.isHidden())
            self.assertIs(application.focusWidget(), edit)
            self.assertEqual(edit.text(), "pending draft")
            self.assertEqual((editor.parentWidget(), pdf.parentWidget()), parents)
        finally:
            area.close()
            area.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_first_window_registers_with_new_scale_manager(self):
        application = _app()
        previous = getattr(application, "ui_scale_manager", None)
        if previous is not None:
            del application.ui_scale_manager
        window = None
        try:
            window = MainWindow(settings_store=AppSettings(QSettings(
                str(Path(_TEMP.name) / f"first-scale-{next(_COUNTER)}.ini"), QSettings.Format.IniFormat)))
            self.assertIn(window, application.ui_scale_manager._windows)
        finally:
            if window is not None:
                window.close()
                window.deleteLater()
                application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            if previous is not None:
                application.ui_scale_manager = previous

    def test_block_layout_and_inspector_fit_narrow_scroll_containers(self):
        from app.gui.blocks.project_session import ProjectSession
        from app.gui.blocks.workspace_widget import BlockWorkspaceWidget
        from app.gui.blocks.inspector import BlockInspector
        application = _app()
        session = ProjectSession()
        workspace = BlockWorkspaceWidget(session)
        inspector = BlockInspector(session)
        try:
            for widget in (workspace, inspector):
                widget.resize(280, 300)
                widget.show()
                application.processEvents()
                self.assertLessEqual(widget.width(), 280)
                self.assertLessEqual(widget.height(), 300)
            self.assertIsNone(session.compile_manager)
        finally:
            session.shutdown()
            for widget in (workspace, inspector):
                widget.close()
                widget.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_profile_dialog_keyboard_and_scroll_access_at_all_scales(self):
        from app.gui.project_profile_dialog import ProjectProfileDialog
        from app.gui.theme.ui_scale_manager import UiScaleManager
        from PySide6.QtWidgets import QDialogButtonBox
        application = _app()
        manager = getattr(application, "ui_scale_manager", None)
        if manager is None:
            manager = UiScaleManager(application)
            application.ui_scale_manager = manager
        previous = manager.scale
        with TemporaryDirectory() as directory:
            dialog = ProjectProfileDialog(Path(directory).resolve())
            try:
                dialog.resize(520, 480)
                dialog.show()
                for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                    manager.apply_scale(scale)
                    application.processEvents()
                    dialog.word_max.setFocus()
                    dialog.word_max.selectAll()
                    QTest.keyClicks(dialog.word_max, "234")
                    QTest.keyClick(dialog.word_max, Qt.Key.Key_Tab)
                    application.processEvents()
                    self.assertEqual(dialog.word_max.text(), "234")
                    self.assertIsNotNone(application.focusWidget())
                    for kind in (QDialogButtonBox.StandardButton.Save, QDialogButtonBox.StandardButton.Cancel):
                        button = dialog.buttons.button(kind)
                        self.assertTrue(button.isVisible())
                        self.assertTrue(dialog.rect().contains(button.mapTo(dialog, button.rect().center())))
                QTest.keyClick(dialog, Qt.Key.Key_Escape)
                self.assertFalse((Path(directory) / ".icstex").exists())
            finally:
                dialog.close()
                manager.apply_scale(previous)

    def test_destroyed_welcome_page_is_disconnected_from_scale_manager(self) -> None:
        import sys
        from unittest.mock import patch
        from PySide6.QtCore import QCoreApplication
        from shiboken6 import isValid
        from app.gui.theme.ui_scale_manager import UiScaleManager
        from app.gui.welcome_page import WelcomePage

        application = _app()
        if not hasattr(application, "ui_scale_manager"):
            application.ui_scale_manager = UiScaleManager(application)
        with patch.object(sys, "excepthook") as errors:
            for _ in range(5):
                page = WelcomePage()
                page.show()
                application.processEvents()
                page.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                self.assertFalse(isValid(page))
                application.ui_scale_manager.scale_changed.emit(1.25)
                application.processEvents()
            errors.assert_not_called()

    def test_formula_and_table_editor_layout_and_keyboard_flow(self) -> None:
        from app.gui.formula_dialog import FormulaDialog
        from app.gui.insert_panel import TableDialog
        from app.gui.math_keyboard import MathKeyButton

        application = _app()
        formula = FormulaDialog(None, "", 0, 0, seed_text=r"\(x=\)")
        table = TableDialog()
        try:
            for width, height in ((920, 720), (800, 720), (1040, 720), (920, 720)):
                formula.resize(width, height)
                formula.show()
                application.processEvents()
                self.assertEqual(formula.size().width(), width)
                self.assertLessEqual(formula.size().height(), height)
                self.assertTrue(formula._ok_button.isVisible())
                self.assertGreater(formula.keyboard.stack.width(), 100)
                self.assertIsNotNone(formula.keyboard.stack.parentWidget())
                self.assertFalse(formula.grab().isNull())
            actions = {button.action: button for button in formula.keyboard.findChildren(MathKeyButton)}
            self.assertNotIn("apply", actions)
            self.assertTrue(all(button.accessibleName() for button in actions.values()))
            formula.keyboard._emit("toggle:abc")
            application.processEvents()
            self.assertLessEqual(formula.width(), 920)
            self.assertLessEqual(formula.height(), 720)
            self.assertEqual(formula.keyboard.stack.currentWidget(), formula.keyboard.letters_row)
            formula.keyboard._emit("toggle:abc")
            self.assertEqual(formula.keyboard.stack.currentWidget(), formula.keyboard._base_page)
            actions["structure:fraction"].click()
            QTest.keyClicks(formula.visual_edit, "a")
            QTest.keyClick(formula.visual_edit, Qt.Key.Key_Tab)
            QTest.keyClicks(formula.visual_edit, "b")
            QTest.keyClick(formula.visual_edit, Qt.Key.Key_Return)
            self.assertEqual(formula.preview_edit.toPlainText(), r"\(x=\frac{a}{b}\)")
            self.assertIsNone(formula.plan())
            formula.source_mode_check.setChecked(True)
            self.assertFalse(formula.keyboard.isVisible())
            formula.source_mode_check.setChecked(False)

            table.resize(840, 660)
            table.show()
            table.paste_clipboard_text("Name\tValue\nA\t0\nB\t1")
            application.processEvents()
            self.assertLessEqual(table.height(), 660)
            self.assertEqual(table._cell_text(1, 1), "0")
            self.assertFalse(table.grab().isNull())
        finally:
            formula.close()
            table.close()
            formula.deleteLater()
            table.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_formula_draft_and_fixed_actions_fit_full_size_scale_matrix(self):
        from app.gui.formula_dialog import FormulaDialog
        from app.gui.theme.ui_scale_manager import UiScaleManager
        from PySide6.QtWidgets import QDialogButtonBox
        from PySide6.QtGui import QInputMethodEvent, QTextCursor
        application = _app()
        if not hasattr(application, "ui_scale_manager"):
            application.ui_scale_manager = UiScaleManager(application)
        manager = application.ui_scale_manager
        previous = manager.scale
        try:
            for source_mode in (False, True):
                dialog = FormulaDialog(None, "$x+1$", 0, 5)
                try:
                    dialog.source_mode_check.setChecked(source_mode)
                    active = dialog._active_editor()
                    initial = active.toPlainText() if source_mode else active.latex()
                    if source_mode:
                        cursor = active.textCursor()
                        cursor.movePosition(QTextCursor.MoveOperation.End)
                        cursor.movePosition(QTextCursor.MoveOperation.Left)
                        cursor.insertText("y")
                    else:
                        active.insert_text("y")
                    draft = active.toPlainText() if source_mode else active.latex()
                    dialog.show()
                    active.setFocus()
                    if not source_mode:
                        QApplication.sendEvent(active, QInputMethodEvent("zhong", []))
                    for scale in (.9, 1., 1.1, 1.25, 1.5):
                        manager.apply_scale(scale)
                        for width, height in ((1080, 720), (1366, 768), (1440, 900), (1920, 1080)):
                            with self.subTest(source=source_mode, scale=scale, size=(width, height)):
                                dialog.resize(width, height)
                                application.processEvents()
                                self.assertLessEqual(dialog.width(), width)
                                self.assertLessEqual(dialog.height(), height)
                                box = dialog.findChild(QDialogButtonBox)
                                for kind in (QDialogButtonBox.StandardButton.Ok, QDialogButtonBox.StandardButton.Cancel):
                                    button = box.button(kind)
                                    self.assertTrue(button.visibleRegion().contains(button.rect()))
                                self.assertEqual(active.toPlainText() if source_mode else active.latex(), draft)
                                if not source_mode:
                                    self.assertTrue(active.has_preedit)
                                self.assertIsNone(dialog._accepted_plan)
                    if not source_mode:
                        QApplication.sendEvent(active, QInputMethodEvent())
                    active.undo()
                    self.assertEqual(active.toPlainText() if source_mode else active.latex(), initial)
                finally:
                    dialog.reject()
                    dialog.deleteLater()
                    application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        finally:
            manager.apply_scale(previous)

    def test_formula_control_tab_leaves_editor_without_applying_or_losing_draft(self):
        import sys
        from app.gui.formula_dialog import FormulaDialog
        from PySide6.QtTest import QSignalSpy
        application = _app()
        dialog = FormulaDialog(None, "$x+1$", 0, 5)
        spies = [QSignalSpy(shortcut.activated) for shortcut in dialog._editor_focus_shortcuts]
        control = Qt.KeyboardModifier.MetaModifier if sys.platform == "darwin" else Qt.KeyboardModifier.ControlModifier
        try:
            dialog.resize(900, 640)
            dialog.show()
            dialog.activateWindow()
            for source_mode in (False, True):
                dialog.source_mode_check.setChecked(source_mode)
                active = dialog._active_editor()
                before = active.toPlainText() if source_mode else active.latex()
                active.setFocus()
                application.processEvents()
                self.assertIs(application.focusWidget(), active)
                QTest.keyClick(dialog.windowHandle(), Qt.Key.Key_Tab, control)
                application.processEvents()
                target = dialog.preview_edit if source_mode else dialog.keyboard.category_group.checkedButton()
                self.assertIs(application.focusWidget(), target)
                self.assertTrue(target.visibleRegion().contains(target.rect()))
                active.setFocus()
                QTest.keyClick(dialog.windowHandle(), Qt.Key.Key_Tab, control | Qt.KeyboardModifier.ShiftModifier)
                application.processEvents()
                self.assertIs(application.focusWidget(), dialog.source_mode_check)
                self.assertEqual(active.toPlainText() if source_mode else active.latex(), before)
                self.assertIsNone(dialog._accepted_plan)
                counts = [spy.count() for spy in spies]
                QTest.keyClick(dialog.windowHandle(), Qt.Key.Key_Tab, control)
                self.assertEqual([spy.count() for spy in spies], counts, "Focus escape is editor-scoped")
        finally:
            dialog.reject()
            dialog.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_font_roles_resolve_expected_latin_and_chinese_families(self) -> None:
        _app()
        available = set(QFontDatabase.families())
        expected_ui_latin = next(
            (family for family in UI_LATIN_SANS_FONT_CANDIDATES if family in available),
            None,
        )
        expected_mono_latin = next(
            (family for family in LATIN_MONO_FONT_CANDIDATES if family in available),
            None,
        )
        expected_sans_cjk = next(
            (family for family in CJK_SANS_FONT_CANDIDATES if family in available),
            None,
        )
        expected_serif_cjk = next(
            (family for family in CJK_SERIF_FONT_CANDIDATES if family in available),
            None,
        )

        expected_roles = (
            (ui_font(), expected_ui_latin, expected_sans_cjk),
            (editor_font(), expected_mono_latin, expected_serif_cjk),
            (heading_font(), expected_ui_latin, expected_serif_cjk),
        )
        for font, expected_latin, expected_cjk in expected_roles:
            families = font.families()
            if expected_latin is not None:
                self.assertEqual(families[0], expected_latin)
            if expected_cjk is not None:
                self.assertIn(expected_cjk, families)
                if expected_latin is not None:
                    self.assertGreater(families.index(expected_cjk), families.index(expected_latin))

        qss = stylesheet()
        for family in (expected_ui_latin, expected_mono_latin, expected_sans_cjk, expected_serif_cjk):
            if family is not None:
                self.assertIn(f'"{family}"', qss)

    def test_small_text_theme_colors_meet_aa_contrast(self) -> None:
        for color in (COLOR_TEXT_FAINT, COLOR_SYNTAX_OPTION, COLOR_SYNTAX_COMMENT):
            self.assertGreaterEqual(_contrast_ratio(color, COLOR_EDITOR), 4.5)

    def test_supported_window_sizes_render_without_black_toolbar_or_overlap(self) -> None:
        application = _app()
        for width, height in ((1440, 900), (1280, 720), (1100, 720)):
            settings = AppSettings(
                QSettings(
                    str(Path(_TEMP.name) / f"visual-{next(_COUNTER)}.ini"),
                    QSettings.Format.IniFormat,
                )
            )
            window = MainWindow(settings_store=settings)
            window.resize(width, height)
            window.show()
            application.processEvents()

            toolbar = window.findChild(QToolBar, "mainToolbar")
            self.assertIsNotNone(toolbar)
            assert toolbar is not None
            self.assertGreater(toolbar.height(), 0)
            self.assertGreaterEqual(window.main_splitter.widget(0).width(), 430)
            self.assertFalse(window.pdf_panel.isVisible(), "Welcome state has no active document PDF")
            window.new_document()
            application.processEvents()
            area = window.source_preview_area
            if area._compact:
                area.select_pdf(True)
                application.processEvents()
                self.assertTrue(window.pdf_panel.isVisible())
                self.assertFalse(area.editor.isVisible())
                self.assertTrue(area.editor_button.visibleRegion().contains(area.editor_button.rect()))
                area.select_pdf(False)
            else:
                # Empty previews are now intentionally narrow. Keep the actual
                # action visibility/overlap checks, not the former 360px budget.
                self.assertFalse(area._preview_available)
                self.assertGreater(area.editor.width(), area.pdf.width())
                self.assertLessEqual(area.pdf.width(), area.pdf.maximumWidth())
                button = window.pdf_panel.empty_compile_button
                self.assertTrue(button.visibleRegion().contains(button.rect()))
                self.assertTrue(window.pdf_panel._toolbar.isHidden())

            compile_button = toolbar.widgetForAction(window.compile_action)
            self.assertIsNotNone(compile_button)
            assert compile_button is not None
            image = compile_button.grab().toImage()
            self.assertFalse(image.isNull())
            dark_pixels = 0
            sampled = 0
            for x in range(0, image.width(), 3):
                for y in range(0, image.height(), 3):
                    color = image.pixelColor(x, y)
                    sampled += 1
                    if color.red() < 20 and color.green() < 20 and color.blue() < 20:
                        dark_pixels += 1
            self.assertLess(dark_pixels, max(1, sampled // 3))

            frame = window.grab()
            self.assertFalse(frame.isNull())
            self.assertEqual(frame.size().width(), width)
            self.assertEqual(frame.size().height(), height)
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            window.close()


def _contrast_ratio(foreground: str, background: str) -> float:
    light, dark = sorted((_relative_luminance(foreground), _relative_luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


class AppUpdateVisualTests(TestCase):
    def test_update_dialog_chinese_content_and_actions_fit(self) -> None:
        from app.gui.update_dialog import AppUpdateDialog
        application = _app()
        dialog = AppUpdateDialog()
        try:
            self.assertIn("启动时自动检查", dialog.automatic.text())
            self.assertIn("每天复查", dialog.automatic.text())
            self.assertIn("30 秒", dialog.automatic.toolTip())
            self.assertIn("5 分钟", dialog.automatic.toolTip())
            self.assertIn("编译或导出期间暂缓", dialog.automatic.toolTip())
            dialog.set_state(available=False, automatic=False,
                             message="当前是源码开发模式，未启用应用内更新。请在带更新器的正式安装包中使用。")
            for width in (480, 600):
                dialog.resize(width, 360)
                dialog.show()
                application.processEvents()
                self.assertEqual(dialog.width(), width)
                self.assertTrue(dialog.rect().contains(dialog.check_button.geometry()))
                self.assertTrue(dialog.rect().contains(dialog.automatic.geometry()))
                self.assertFalse(dialog.check_button.isEnabled())
                self.assertFalse(dialog.automatic.isChecked())
                self.assertFalse(dialog.grab().isNull())
            dialog.set_state(available=True, automatic=True, message="发现可用更新，请在原生更新窗口查看并确认下载。",
                             source="更新源：updates.example.org", channel="Beta 通道")
            self.assertTrue(dialog.check_button.isEnabled())
            self.assertTrue(dialog.automatic.isChecked())
            dialog.set_state(available=True, automatic=False, message="更新正在进行。", checking=True)
            application.processEvents()
            self.assertEqual(dialog.check_button.text(), "查看更新进度")
            self.assertTrue(dialog.rect().contains(dialog.check_button.geometry()))
        finally:
            dialog.close()
            dialog.deleteLater()
