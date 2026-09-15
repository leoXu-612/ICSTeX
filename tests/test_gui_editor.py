from __future__ import annotations

from dataclasses import replace
import os
import time
from itertools import count
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QMimeData, QPointF, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDropEvent, QInputMethodEvent, QKeyEvent, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
)

from app.core.compiler import BuildPurpose, CompileManager, CompileOutcome, CompileResult
from app.core.formula_input import (
    FormulaDraft,
    FormulaMode,
    apply_formula_template,
    final_edit_plan,
    parse_document_selection,
)
from app.core.log_parser import LaTeXError
from app.core.history import create_snapshot
from app.core.pdf_state import PdfFreshness
from app.core.preview_state import PreviewFreshness
from app.core.settings import AppSettings
from app.core.latex_tools import LaTeXEngine, LaTeXToolchain
from app.core.latex_insertions import (
    HYPERLINK_PACKAGES,
    FigureLayout,
    FigureLayoutItem,
    FigureLayoutSpec,
)
from app.gui.diagnostics_panel import DiagnosticsPanel
from app.gui.environment_doctor_dialog import EnvironmentDoctorDialog
from app.gui.find_replace import FindReplaceBar
from app.gui.formula_dialog import FormulaDialog
from app.gui.insert_panel import FigureDialog, FigureLayoutDialog, HyperlinkDialog, TableDialog
from app.gui.latex_editor import LaTeXEditor
from app.gui.main_window import EditorTab, MainWindow
from app.gui.project_panels import BibEntryDialog, BibImportDialog, ProjectWizardDialog
from app.gui.settings_dialog import SettingsDialog
from app.gui.theme import apply_theme
from app.gui.toolbox_navigation import ToolboxNavigation
from app.gui.welcome_page import WelcomePage
from app.gui.widgets import AutoCompileToggle

_SETTINGS_TEMP = TemporaryDirectory()
_SETTINGS_COUNTER = count()


def app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
        apply_theme(instance)
    return instance


def isolated_settings() -> AppSettings:
    settings_file = Path(_SETTINGS_TEMP.name) / f"settings-{next(_SETTINGS_COUNTER)}.ini"
    return AppSettings(QSettings(str(settings_file), QSettings.Format.IniFormat))


def wait_until(predicate, timeout_s: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return predicate()


class SourceIdleCompositionTests(TestCase):
    """Real default save timers and Qt IME events; not physical IME evidence."""

    def setUp(self):
        self.application = app()
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.source = self.root / "main.tex"
        self.original = "\\documentclass{article}\n\\begin{document}\nbase \n\\end{document}\n"
        self.source.write_text(self.original, encoding="utf-8")
        self.window = MainWindow(settings_store=isolated_settings())
        self.addCleanup(self.dispose)
        self.window.auto_compile_action.setChecked(False)
        self.window.project_files.set_project_root(self.root)
        self.window.open_file(self.source)
        self.tab = self.window.current_tab()
        self.editor = self.tab.editor
        cursor = self.editor.textCursor()
        self.position = self.original.index("base ") + len("base ")
        cursor.setPosition(self.position)
        self.editor.setTextCursor(cursor)
        self.assertEqual(self.window.save_debounce_ms, 800)

    def dispose(self):
        for tab in self.window.tabs.values():
            self.window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        self.window.close()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def input(self, preedit="", commit=""):
        event = QInputMethodEvent(preedit, [])
        event.setCommitString(commit)
        QApplication.sendEvent(self.editor, event)

    def preedit(self):
        return self.editor.textCursor().block().layout().preeditAreaText()

    def wait_for_idle(self):
        from PySide6.QtTest import QTest
        QTest.qWait(self.window.save_debounce_ms + 200)

    def wait_for_save(self):
        from PySide6.QtTest import QSignalSpy
        timer = self.tab.save_timer
        self.assertEqual(timer.interval(), 800)
        observed = QSignalSpy(timer.timeout)
        expected = self.editor.toPlainText()
        # qWait can return with a due timer still queued after other callbacks.
        # Observe its actual delivery and bytes, without flushing it manually
        # or changing the production debounce to fit the test's wall clock.
        self.assertTrue(wait_until(lambda: observed.count() == 1 and not self.tab.dirty
                                   and self.source.read_text() == expected), {
            "timeouts": observed.count(), "timer_active": timer.isActive(),
            "remaining_ms": timer.remainingTime(), "conflict": self.tab.external_conflict,
        })

    def test_candidate_and_cancel_do_not_write_compile_or_invalidate_source(self):
        from app.core.text_encoding import write_latex_text_atomic
        self.window.auto_compile_action.setChecked(True)
        self.tab.manager = self.window.create_compile_manager(self.source)
        self.window.compile_authorized_roots.add(self.tab.manager.root_file)
        before = self.window.pdf_state.record_for(self.source).source_revision
        undo_steps = self.editor.document().availableUndoSteps()
        with patch("app.gui.document_lifecycle.write_latex_text_atomic", wraps=write_latex_text_atomic) as write, \
                patch.object(self.tab.manager, "compile_async") as compile_async, \
                patch.object(self.window.readiness, "invalidate") as invalidate:
            self.input("zhong")
            self.wait_for_idle()
            self.assertEqual(self.preedit(), "zhong")
            self.input("zhongwen")
            self.input()  # cancel without committing
            self.wait_for_idle()
            write.assert_not_called()
            compile_async.assert_not_called()
            invalidate.assert_not_called()
        self.assertEqual(self.source.read_text(), self.original)
        self.assertEqual(self.editor.toPlainText(), self.original)
        self.assertFalse(self.tab.modified or self.tab.dirty)
        self.assertEqual(self.editor.document().availableUndoSteps(), undo_steps)
        self.assertEqual(self.window.pdf_state.record_for(self.source).source_revision, before)

    def test_partial_commit_saves_only_committed_text_and_preserves_candidate_and_undo(self):
        from app.core.text_encoding import write_latex_text_atomic
        expected = self.original[:self.position] + "\u4e2d" + self.original[self.position:]
        with patch("app.gui.document_lifecycle.write_latex_text_atomic", wraps=write_latex_text_atomic) as write:
            self.input("zhongwen")
            self.input("wen", "\u4e2d")
            before_view = (self.editor.textCursor().position(), self.editor.verticalScrollBar().value())
            self.wait_for_save()
            self.assertEqual(self.source.read_text(), expected)
            self.assertEqual(self.preedit(), "wen")
            self.assertEqual((self.editor.textCursor().position(), self.editor.verticalScrollBar().value()), before_view)
            self.assertEqual(write.call_count, 1)
            self.assertFalse(self.tab.modified or self.tab.dirty)
            # Explicitly deliver our own watcher echo while the candidate lives.
            self.window.reload_external_change(str(self.source))
            self.assertEqual(self.preedit(), "wen")
            revision = self.window.pdf_state.record_for(self.source).source_revision
            self.input()  # cancel only the remaining candidate
            self.wait_for_idle()
            self.assertEqual(write.call_count, 1)
            self.assertEqual(self.window.pdf_state.record_for(self.source).source_revision, revision)
            self.editor.undo()
            self.assertEqual(self.editor.toPlainText(), self.original)
            self.editor.redo()
            self.assertEqual(self.editor.toPlainText(), expected)

    def test_cancel_does_not_rearm_an_existing_committed_save_timer(self):
        self.input(commit="\u4e2d")
        timer_id = self.tab.save_timer.timerId()
        self.input("wen")
        self.input()
        self.assertTrue(self.tab.save_timer.isActive())
        self.assertEqual(self.tab.save_timer.timerId(), timer_id)
        self.wait_for_save()
        self.assertEqual(self.source.read_text(), self.editor.toPlainText())

    def test_external_edit_after_idle_save_preserves_active_candidate_as_conflict(self):
        self.input("wen", "\u4e2d")
        self.wait_for_save()
        committed = self.editor.toPlainText()
        self.assertFalse(self.tab.modified or self.tab.dirty)
        external = self.original.replace("base ", "external ")
        self.source.write_text(external, encoding="utf-8")
        self.window.reload_external_change(str(self.source))
        self.assertTrue(self.tab.external_conflict)
        self.assertEqual(self.editor.toPlainText(), committed)
        self.assertEqual(self.preedit(), "wen")
        self.input(commit="\u6587")
        self.wait_for_idle()
        self.assertEqual(self.source.read_text(), external)
        self.assertTrue(self.tab.modified and self.tab.dirty)
        self.assertFalse(self.tab.save_timer.isActive())

    def test_inactive_source_commit_keeps_tab_save_and_revision_ownership(self):
        other = self.root / "other.tex"
        other.write_text("other", encoding="utf-8")
        self.window.open_file(other)
        active = self.window.current_tab()
        before = self.window.pdf_state.record_for(other).source_revision
        self.input("zhong")
        self.assertFalse(self.tab.modified or active.modified)
        self.input(commit="\u4e2d")
        self.assertTrue(self.tab.modified)
        self.assertFalse(active.modified)
        self.wait_for_save()
        self.assertEqual(self.source.read_text(), self.editor.toPlainText())
        self.assertEqual(other.read_text(), "other")
        self.assertIs(self.window.current_tab(), active)
        self.assertEqual(self.window.pdf_state.record_for(other).source_revision, before)

    def test_preedit_keeps_word_count_and_panel_cache_identity_without_reading_text(self):
        self.window.project_panels._refresh_domains({"outline"})
        word_key = self.window.word_counts._key()
        panel_key = self.window.project_panels._source_key
        self.input("zhong")
        with patch.object(self.editor, "toPlainText", side_effect=AssertionError("cached identity must be cheap")):
            self.assertEqual(self.window.word_counts._key(), word_key)
            self.window.project_panels._refresh_domains({"outline"})
        self.assertEqual(self.window.project_panels._source_key, panel_key)
        self.input()
        self.assertEqual(self.window.word_counts._key(), word_key)
        self.input(commit="\u4e2d")
        self.assertNotEqual(self.window.word_counts._key(), word_key)

    def test_reader_keys_reject_blocked_reload_and_undo_on_inactive_related_tab(self):
        other = self.root / "child.tex"
        other.write_text("% !TeX root = main.tex\nother", encoding="utf-8")
        self.original = self.original.replace("base \n", "base \\input{child}\n")
        self.source.write_text(self.original, encoding="utf-8")
        self.window.reload_external_change(str(self.source))
        self.window.open_file(other)
        active = self.window.current_tab()
        self.assertEqual(self.window._compile_root_for_tab(active), self.source)

        def keys():
            return (self.window.citations._key(), self.window.materials._key(),
                    self.window.readiness._quick_key(self.source), self.window.word_counts._key())

        before = keys()
        self.input("zhong")
        self.input()
        self.assertEqual(keys(), before)
        self.editor.blockSignals(True)
        try:
            self.editor.insertPlainText("changed ")
            changed = keys()
            self.editor.undo()
            undone = keys()
            self.editor.setPlainText("external")
            reloaded = keys()
        finally:
            self.editor.blockSignals(False)
        for old, new in ((before, changed), (changed, undone), (undone, reloaded), (before, undone)):
            for name, a, b in zip(("citation", "material", "submission", "word_count"), old, new):
                self.assertNotEqual(a, b, name)
        self.assertIs(self.window.current_tab(), active)
        self.assertFalse(self.tab.modified or self.tab.dirty or active.modified or active.dirty)
        self.assertEqual(self.source.read_text(), self.original)
        self.assertEqual(other.read_text(), "% !TeX root = main.tex\nother")

    def test_word_count_late_preedit_result_and_cache_survive_but_edit_undo_is_stale(self):
        from app.core.word_count import count_project_snapshot
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy
                                   and not self.window.word_counts.is_busy))
        controller = self.window.word_counts
        for action in ("preedit", "edit_undo"):
            with self.subTest(action=action):
                entered, release = threading.Event(), threading.Event()

                def delayed(*args, **kwargs):
                    result = count_project_snapshot(*args, **kwargs)
                    entered.set()
                    release.wait(3)
                    return result

                with patch("app.gui.word_count_controller.count_project_snapshot", delayed), \
                        patch.object(controller, "_show", wraps=controller._show) as show:
                    try:
                        controller.request(force=True)
                        self.assertTrue(wait_until(entered.is_set))
                        key = controller._active.key
                        if action == "preedit":
                            self.input("zhong")
                        else:
                            self.editor.blockSignals(True)
                            try:
                                self.editor.insertPlainText("changed ")
                                self.editor.undo()
                            finally:
                                self.editor.blockSignals(False)
                        release.set()
                        self.assertTrue(wait_until(lambda: not controller.is_busy))
                        self.assertEqual(show.call_count, 1 if action == "preedit" else 0)
                    finally:
                        release.set()
                if action == "preedit":
                    self.assertEqual(controller._displayed_key, key)
                    with patch.object(controller, "_launch", side_effect=AssertionError("reuse cache")), \
                            patch.object(self.editor, "toPlainText", side_effect=AssertionError("reuse snapshot")):
                        controller.request()
                    self.input()
        self.assertEqual(self.source.read_text(), self.original)


class ReadOnlyNavigationShortcutTests(TestCase):
    def setUp(self):
        self.application = app()
        self.directory = TemporaryDirectory(prefix="icstex-keyboard-navigation-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.main = self.root / "main.tex"
        self.child = self.root / "child.tex"
        self.main.write_text("\\documentclass{article}\n\\begin{document}\n"
                             "\\section{First}\ntext\n\\section{Second}\n"
                             "\\input{child}\n\\end{document}\n")
        self.child.write_text("% !TeX root = main.tex\nfirst\nnavigationneedle\nfourth\n")
        self.originals = {path: path.read_bytes() for path in (self.main, self.child)}
        self.window = MainWindow(settings_store=isolated_settings())
        self.window.auto_compile_action.setChecked(False)
        self.window.save_debounce_ms = 3600000
        self.window.project_files.set_project_root(self.root)
        self.window.open_file(self.main)
        self.window.show()
        self.window.activateWindow()
        self.window.set_toolbox_visible(True)
        self.addCleanup(self.dispose)

    def dispose(self):
        for tab in self.window.tabs.values():
            self.window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        self.window.close()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def select_surface(self, name):
        from app.core.diagnostics import Diagnostic
        from app.core.latex_outline import scan_outline
        self.window.open_file(self.main, 1)
        if name == "outline":
            self.window.sidebar_tabs.setCurrentIndex(1)
            panel = self.window.outline_panel
            panel.set_outline(scan_outline(self.main.read_text()))
            table, row, target, line = panel.table, 1, self.main, 5
        elif name == "search":
            self.window.sidebar_tabs.setCurrentIndex(2)
            self.window.run_project_search("navigationneedle", False, False)
            table, row, target, line = self.window.search_panel.table, 0, self.child, 3
        elif name == "diagnostics":
            self.window.bottom_tabs.setCurrentWidget(self.window.diagnostic_panel)
            self.window.diagnostic_panel.set_diagnostics([
                Diagnostic("info", "First", "Synthetic", self.main, 3),
                Diagnostic("info", "Second", "Synthetic", self.child, 3),
            ])
            table, row, target, line = self.window.diagnostic_panel.table, 1, self.child, 3
        else:
            self.window.bottom_tabs.setCurrentWidget(self.window.error_table)
            self.window.compile.show_errors(CompileResult(
                root_file=self.main, output_dir=self.root / "not-built",
                pdf_file=self.root / "not-built/main.pdf", log_file=self.root / "not-built/main.log",
                command=[], returncode=1, stdout="", stderr="", duration_seconds=0,
                outcome=CompileOutcome.LATEX_ERROR,
                errors=[LaTeXError("Synthetic", self.main, 3), LaTeXError("Synthetic", self.child, 3)],
            ))
            table, row, target, line = self.window.error_table, 1, self.child, 3
        table.setCurrentCell(row, 0)
        table.setFocus()
        self.application.processEvents()
        self.assertIs(self.application.focusWidget(), table)
        return table, target, line

    def test_return_and_enter_navigate_once_through_existing_read_only_routes(self):
        from PySide6.QtTest import QSignalSpy, QTest
        with patch.object(self.window, "save_current", side_effect=AssertionError("no save")), \
                patch.object(self.window, "compile_current", side_effect=AssertionError("no compile")):
            for name in ("outline", "search", "errors", "diagnostics"):
                for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    with self.subTest(surface=name, key=key):
                        table, target, line = self.select_surface(name)
                        activated = QSignalSpy(table.cellActivated)
                        QTest.keyClick(table, key)
                        self.application.processEvents()
                        self.assertEqual(activated.count(), 1)
                        tab = self.window.current_tab()
                        self.assertEqual(tab.path, target)
                        self.assertEqual(tab.editor.textCursor().blockNumber() + 1, line)
                        self.assertEqual({path: path.read_bytes() for path in self.originals}, self.originals)
                        self.assertFalse(self.window.compile_authorized_roots)
                        self.assertFalse(any(item.dirty or item.modified for item in self.window.tabs.values()))

    def test_navigation_keys_ignore_other_focus_empty_selection_and_repeat(self):
        from PySide6.QtTest import QSignalSpy, QTest
        for name in ("outline", "search", "errors", "diagnostics"):
            with self.subTest(surface=name):
                table, _target, _line = self.select_surface(name)
                activated = QSignalSpy(table.cellActivated)
                table.clearSelection()
                QTest.keyClick(table, Qt.Key.Key_Return)
                self.assertEqual(activated.count(), 0)
                table.selectRow(0)
                QApplication.sendEvent(table, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return,
                                                       Qt.KeyboardModifier.NoModifier, "", True))
                self.assertEqual(activated.count(), 0)
                self.window.auto_compile_toggle.setFocus()
                QTest.keyClick(self.window.auto_compile_toggle, Qt.Key.Key_Return)
                self.assertEqual(activated.count(), 0)
                self.assertFalse(self.window.auto_compile_action.isChecked())
                table.setRowCount(0)
                table.setFocus()
                QTest.keyClick(table, Qt.Key.Key_Return)
                self.assertEqual(activated.count(), 0)
                self.assertEqual(self.window.current_tab().path, self.main)
                self.assertEqual({path: path.read_bytes() for path in self.originals}, self.originals)

    def test_single_search_result_can_be_selected_with_space_before_return(self):
        from PySide6.QtTest import QSignalSpy, QTest
        table, target, line = self.select_surface("search")
        self.assertEqual(table.rowCount(), 1)
        table.clearSelection()
        activated = QSignalSpy(table.cellActivated)
        QTest.keyClick(table, Qt.Key.Key_Return)
        self.assertEqual(activated.count(), 0)
        QTest.keyClick(table, Qt.Key.Key_Space)
        self.assertTrue(table.selectionModel().isSelected(table.currentIndex()))
        QTest.keyClick(table, Qt.Key.Key_Return)
        self.assertEqual(activated.count(), 1)
        self.assertEqual(self.window.current_tab().path, target)
        self.assertEqual(self.window.current_tab().editor.textCursor().blockNumber() + 1, line)
        self.assertEqual({path: path.read_bytes() for path in self.originals}, self.originals)
        self.assertFalse(self.window.compile_authorized_roots)
        for table in (self.window.outline_panel.table, self.window.search_panel.table,
                      self.window.error_table, self.window.diagnostic_panel.table):
            with self.subTest(table=table.parentWidget().objectName()):
                self.assertIn("空格", table.toolTip())


class WorkbenchShortcutTests(TestCase):
    def setUp(self):
        self.application = app()

    def test_inspector_focus_shortcuts_preserve_draft_and_are_widget_scoped(self):
        import sys
        from PySide6.QtTest import QSignalSpy, QTest
        from app.core.blocks.project_repository import load_project
        from app.gui.block_mode import _install_session, _set_block_mode
        from app.gui.blocks.project_session import ProjectSession
        from tests.v1_fixtures import create_project

        with TemporaryDirectory() as directory:
            sample = create_project(Path(directory), "block")
            loaded = load_project(sample.root.parent)
            session = ProjectSession(**{key: loaded[key] for key in
                                     ("registry", "layout", "sources", "document_theme", "project_dir")})
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            manager = self.application.ui_scale_manager
            old_scale = manager.scale
            try:
                window.open_file(sample.root)
                self.assertTrue(_install_session(window, session))
                _set_block_mode(window, True)
                block = next(block for block in session.registry.blocks() if block.type == "text")
                session.selection.select_block(block.id, source="focus-test")
                window.resize(1080, 720)
                window.show()
                window.activateWindow()
                self.application.processEvents()
                inspector = window.block_inspector
                window.block_panels.request("inspector")
                self.application.processEvents()
                editor = inspector.content_edit
                self.assertTrue(editor.isVisible())
                editor.setFocus()
                editor.moveCursor(QTextCursor.MoveOperation.End)
                QTest.keyClicks(editor, " draft")
                expected = editor.toPlainText()
                before_model = block.to_dict()
                before_files = {path: path.read_bytes() for path in sample.root.parent.rglob("*") if path.is_file()}
                QTest.keyClick(editor, Qt.Key.Key_Tab)
                self.assertEqual(editor.toPlainText(), expected + "\t")
                QTest.keySequence(editor, QKeySequence(QKeySequence.StandardKey.Undo))
                self.assertEqual(editor.toPlainText(), before_model["content"]["text"])
                QTest.keySequence(editor, QKeySequence(QKeySequence.StandardKey.Redo))
                self.assertEqual(editor.toPlainText(), expected + "\t")
                QTest.keyClick(editor, Qt.Key.Key_Backspace)
                self.assertEqual(editor.toPlainText(), expected)
                forward = QSignalSpy(inspector._focus_apply_shortcut.activated)
                backward = QSignalSpy(inspector._focus_alias_shortcut.activated)
                control = Qt.KeyboardModifier.MetaModifier if sys.platform == "darwin" else Qt.KeyboardModifier.ControlModifier
                for scale in (1.0, 1.5):
                    manager.apply_scale(scale)
                    self.application.processEvents()
                    for modifiers, target in (
                        (control | Qt.KeyboardModifier.ShiftModifier, inspector.alias_edit),
                        (control, inspector.apply_button),
                    ):
                        editor.setFocus()
                        QTest.keyClick(window.windowHandle(), Qt.Key.Key_Tab, modifiers)
                        self.application.processEvents()
                        self.assertIs(self.application.focusWidget(), target)
                        self.assertFalse(target.visibleRegion().isEmpty())
                        self.assertEqual(editor.toPlainText(), expected)
                        self.assertEqual(block.to_dict(), before_model)
                        self.assertEqual(session.undo_stack.count(), 0)
                        self.assertEqual({path: path.read_bytes() for path in before_files}, before_files)
                        self.assertIsNone(session.compile_manager)
                self.assertEqual((forward.count(), backward.count()), (2, 2))
                inspector.alias_edit.setFocus()
                QTest.keyClick(window.windowHandle(), Qt.Key.Key_Tab, control)
                self.assertEqual((forward.count(), backward.count()), (2, 2))
                _set_block_mode(window, False)
                window.current_tab().editor.setFocus()
                QTest.keyClick(window.windowHandle(), Qt.Key.Key_Tab, control)
                self.assertEqual((forward.count(), backward.count()), (2, 2))
            finally:
                session.editor_drafts.clear()
                session._dirty = False
                for tab in window.tabs.values():
                    window.documents.cancel_save_timer(tab)
                    tab.modified = tab.dirty = False
                window.close()
                window.deleteLater()
                self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                manager.apply_scale(old_scale)

    def test_standard_save_shortcut_targets_only_the_visible_mode(self):
        from PySide6.QtTest import QTest
        from app.core.blocks.project_repository import load_project
        from app.gui.block_mode import _install_session, _set_block_mode
        from app.gui.blocks.project_session import ProjectSession
        from tests.v1_fixtures import create_project

        with TemporaryDirectory() as directory:
            sample = create_project(Path(directory), "block")
            loaded = load_project(sample.root.parent)
            session = ProjectSession(**{key: loaded[key] for key in
                                     ("registry", "layout", "sources", "document_theme", "project_dir")})
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            try:
                window.open_file(sample.root)
                self.assertTrue(_install_session(window, session))
                _set_block_mode(window, True)
                window.show()
                window.activateWindow()
                self.application.processEvents()
                window.block_inspector.alias_edit.setFocus()
                actions = []
                window.save_action.triggered.connect(lambda: actions.append("source"))
                window.block_save_action.triggered.connect(lambda: actions.append("block"))
                QTest.keySequence(window.block_inspector.alias_edit, QKeySequence(QKeySequence.StandardKey.Save))
                self.application.processEvents()
                self.assertEqual(actions, ["block"])
                self.assertTrue(session.last_save_ok)
                _set_block_mode(window, False)
                window.current_tab().editor.setFocus()
                QTest.keySequence(window.current_tab().editor, QKeySequence(QKeySequence.StandardKey.Save))
                self.application.processEvents()
                self.assertEqual(actions, ["block", "source"])
            finally:
                window.close()
                window.deleteLater()
                self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_standard_save_shortcut_writes_source_without_moving_editor_or_compiling(self):
        from PySide6.QtTest import QTest

        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("\\documentclass{article}\n\\begin{document}\n"
                              + "Line of synthetic text.\n" * 100 + "\\end{document}\n", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window.save_debounce_ms = 3600000
            try:
                window.open_file(source)
                window.show()
                window.activateWindow()
                self.application.processEvents()
                editor = window.current_tab().editor
                editor.setFocus()
                editor.moveCursor(QTextCursor.MoveOperation.End)
                editor.insertPlainText("% saved by keyboard\n")
                editor.verticalScrollBar().setValue(editor.verticalScrollBar().maximum() // 2)
                before = (editor.textCursor().position(), editor.verticalScrollBar().value())
                saves = []
                window.save_action.triggered.connect(lambda: saves.append(True))
                QTest.keySequence(editor, QKeySequence(QKeySequence.StandardKey.Save))
                self.application.processEvents()
                self.assertEqual(saves, [True])
                self.assertEqual(source.read_text(encoding="utf-8"), editor.toPlainText())
                self.assertFalse(window.current_tab().dirty)
                self.assertEqual((editor.textCursor().position(), editor.verticalScrollBar().value()), before)
                self.assertEqual(window.compile_authorized_roots, set())
            finally:
                for tab in window.tabs.values():
                    window.documents.cancel_save_timer(tab)
                    tab.modified = tab.dirty = False
                window.close()
                window.deleteLater()
                self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class TableDialogLifetimeTests(TestCase):
    def setUp(self):
        self.application = app()
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "main.tex"
        self.original = b"\\documentclass{article}\r\n\\begin{document}\r\nBody\r\n\\end{document}\r\n"
        self.path.write_bytes(self.original)
        self.window = MainWindow(settings_store=isolated_settings())
        self.addCleanup(self.dispose)
        self.window.auto_compile_action.setChecked(False)
        self.window.save_debounce_ms = 60_000
        self.window.open_file(self.path)
        self.editor = self.window.current_tab().editor
        cursor = self.editor.textCursor()
        cursor.setPosition(self.editor.toPlainText().index("\\end{document}"))
        self.editor.setTextCursor(cursor)
        self.before = self.editor.toPlainText()
        self.created = []

    def dispose(self):
        from shiboken6 import isValid
        if isValid(self.window):
            for tab in self.window.tabs.values():
                self.window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            self.window.close()
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def driven_dialog(self, outcome, failure=None, mutation=None, observed=None):
        created = self.created
        window = self.window

        class DrivenDialog(TableDialog):
            def __init__(self, parent, **kwargs):
                self.finished_exec = False
                super().__init__(parent, **kwargs)
                self.preview_table.item(0, 0).setText("Value")
                self.preview_table.item(1, 0).setText("0")
                self.caption_edit.setText("Measured values")
                self.label_edit.setText("tab:measured")
                created.append(self)

            def exec(self):
                if failure == "exec":
                    raise RuntimeError("Synthetic exec failure")
                if mutation is not None:
                    def change_then_accept():
                        from shiboken6 import isValid
                        try:
                            mutation()
                            target = window.current_tab()
                            before = target.editor.toPlainText() if target else None
                            draft = self.values()
                            self.accept()
                            observed.update(open=self.isVisible(), draft_preserved=self.values() == draft,
                                            preview_visible=self.source_preview.isVisible())
                            observed["source_unchanged"] = target is None or target.editor.toPlainText() == before
                        except Exception as exc:
                            observed["error"] = exc
                        finally:
                            if isValid(self):
                                self.reject()
                    QTimer.singleShot(0, self, change_then_accept)
                elif outcome == "parent-destroyed":
                    QTimer.singleShot(0, window, window.close)
                else:
                    QTimer.singleShot(0, self, self.accept if outcome == "accept" else self.reject)
                result = super().exec()
                self.finished_exec = True
                return result

            def values(self):
                if failure == "values" and self.finished_exec:
                    raise RuntimeError("Synthetic values failure")
                return super().values()

        return DrivenDialog

    def assert_disposed(self):
        from shiboken6 import isValid
        self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertTrue(self.created)
        self.assertTrue(all(not isValid(dialog) for dialog in self.created))
        if isValid(self.window):
            self.assertEqual(self.window.findChildren(TableDialog), [])

    def test_repeated_modal_cancel_releases_dialog_and_preserves_source(self):
        before_view = (self.editor.textCursor().position(), self.editor.verticalScrollBar().value())
        before_undo = self.editor.document().availableUndoSteps()
        with patch("app.gui.insertion_actions.TableDialog", self.driven_dialog("cancel")):
            for _ in range(6):
                self.window.insert_table()
                self.assert_disposed()
        self.assertEqual(self.editor.toPlainText(), self.before)
        self.assertEqual((self.editor.textCursor().position(), self.editor.verticalScrollBar().value()), before_view)
        self.assertEqual(self.editor.document().availableUndoSteps(), before_undo)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(self.window.compile_authorized_roots, set())

    def test_modal_accept_copies_values_before_disposal_and_keeps_one_undo(self):
        with patch("app.gui.insertion_actions.TableDialog", self.driven_dialog("accept")):
            self.window.insert_table()
        self.assert_disposed()
        after = self.editor.toPlainText()
        self.assertIn(r"\usepackage{booktabs}", after)
        self.assertIn(r"\caption{Measured values}", after)
        self.assertIn(r"\label{tab:measured}", after)
        self.assertIn("Value &", after)
        self.assertIn("0 &", after)
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), self.before)
        self.editor.redo()
        self.assertEqual(self.editor.toPlainText(), after)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(self.window.compile_authorized_roots, set())

    def test_exec_and_value_failures_release_dialog_without_source_changes(self):
        for stage in ("exec", "values"):
            with self.subTest(stage=stage):
                with patch("app.gui.insertion_actions.TableDialog", self.driven_dialog("accept", stage)):
                    with self.assertRaisesRegex(RuntimeError, "Synthetic"):
                        self.window.insert_table()
                self.assert_disposed()
                self.assertEqual(self.editor.toPlainText(), self.before)
                self.assertEqual(self.path.read_bytes(), self.original)

    def test_parent_destruction_during_modal_loop_does_not_double_delete(self):
        from shiboken6 import isValid
        with patch("app.gui.insertion_actions.TableDialog", self.driven_dialog("parent-destroyed")):
            self.window.insert_table()
        self.assert_disposed()
        self.assertFalse(isValid(self.window))
        self.assertEqual(self.path.read_bytes(), self.original)

    def assert_target_change_refused(self, mutation):
        observed = {}
        with patch("app.gui.insertion_actions.TableDialog", self.driven_dialog(
            "accept", mutation=mutation, observed=observed,
        )):
            self.window.insert_table()
        self.assert_disposed()
        self.assertNotIn("error", observed)
        self.assertEqual(observed, {"open": True, "draft_preserved": True,
                                    "preview_visible": True, "source_unchanged": True})
        self.assertEqual(self.window.compile_authorized_roots, set())

    def test_external_reload_during_table_edit_refuses_stale_target(self):
        cursor = self.editor.textCursor()
        start = self.before.index("Body")
        cursor.setPosition(start)
        cursor.setPosition(start + 4, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        changed = b"% External edit adds a header line.\r\n" + self.original.replace(b"Body", b"NEW!")

        def reload():
            self.path.write_bytes(changed)
            self.window.documents.reload_external_change(str(self.path))

        self.assert_target_change_refused(reload)
        self.assertEqual(self.editor.toPlainText(), changed.decode().replace("\r\n", "\n"))
        self.assertEqual(self.path.read_bytes(), changed)

    def test_source_edit_then_undo_still_refuses_old_table_target(self):
        def edit_then_undo():
            self.editor.insertPlainText("new edit")
            self.editor.undo()

        self.assert_target_change_refused(edit_then_undo)
        self.assertEqual(self.editor.toPlainText(), self.before)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_changed_cursor_refuses_old_table_target(self):
        def move_cursor():
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.editor.setTextCursor(cursor)

        self.assert_target_change_refused(move_cursor)
        self.assertEqual(self.editor.toPlainText(), self.before)

    def test_closed_editor_refuses_table_target_without_destroying_draft(self):
        def close_editor():
            self.window.close_tab(self.window._index_for_tab_id(id(self.editor)))
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        self.assert_target_change_refused(close_editor)
        self.assertEqual(self.path.read_bytes(), self.original)


class GeneratedInsertionTransactionTests(TestCase):
    def setUp(self):
        self.application = app()
        self.window = MainWindow(settings_store=isolated_settings())
        self.addCleanup(self.dispose)
        self.window.auto_compile_action.setChecked(False)
        self.window.new_document()
        self.tab = self.window.current_tab()
        self.editor = self.tab.editor
        self.before = "% \U0001f600\U0001f680\n\\documentclass{article}\n\\begin{document}\nBody\n\\end{document}\n"
        self.editor.setPlainText(self.before)

    def dispose(self):
        for tab in self.window.tabs.values():
            self.window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        self.window.close()
        self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def select_body(self, *, backward=False):
        text = self.editor.toPlainText()
        start = len(text[:text.index("Body")].encode("utf-16-le")) // 2
        end = start + len("Body")
        cursor = self.editor.textCursor()
        cursor.setPosition(end if backward else start)
        cursor.setPosition(start if backward else end, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

    def test_snippet_and_new_packages_keep_prior_undo_history(self):
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.beginEditBlock()
        cursor.insertText("% earlier edit\n")
        cursor.endEditBlock()
        self.editor.setTextCursor(cursor)
        edited = self.editor.toPlainText()
        self.window._insert_generated_snippet(self.tab, "Inserted", ("array",), "Inserted")
        after = self.editor.toPlainText()
        self.assertEqual(after, edited.replace("\\begin{document}", "\\usepackage{array}\n\\begin{document}") + "Inserted")
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), edited)
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), self.before)
        self.editor.redo()
        self.assertEqual(self.editor.toPlainText(), edited)
        self.editor.redo()
        self.assertEqual(self.editor.toPlainText(), after)
        self.assertEqual(self.window.compile_authorized_roots, set())

    def test_package_only_keeps_selection_direction_and_is_undoable(self):
        for backward in (False, True):
            with self.subTest(backward=backward):
                self.editor.setPlainText(self.before)
                self.select_body(backward=backward)
                before_cursor = self.editor.textCursor()
                positions = (before_cursor.position(), before_cursor.anchor())
                self.window.insertions.ensure_packages(self.tab, ("array", "booktabs"))
                inserted = "\\usepackage{array}\n\\usepackage{booktabs}\n"
                after = self.before.replace("\\begin{document}", inserted + "\\begin{document}")
                self.assertEqual(self.editor.toPlainText(), after)
                current = self.editor.textCursor()
                self.assertEqual(current.selectedText(), "Body")
                self.assertEqual((current.position(), current.anchor()), tuple(p + len(inserted) for p in positions))
                steps = self.editor.document().availableUndoSteps()
                self.window.insertions.ensure_packages(self.tab, ("array", "booktabs"))
                self.assertEqual(self.editor.document().availableUndoSteps(), steps)
                self.editor.undo()
                self.assertEqual(self.editor.toPlainText(), self.before)
                self.editor.redo()
                self.assertEqual(self.editor.toPlainText(), after)

    def test_block_replaces_both_selection_directions_with_correct_padding(self):
        for backward in (False, True):
            for packages in ((), ("array",)):
                with self.subTest(backward=backward, packages=packages):
                    self.editor.setPlainText(self.before)
                    self.select_body(backward=backward)
                    self.window._insert_generated_snippet(self.tab, "Inserted", packages, "Inserted")
                    expected = self.before.replace("Body", "Inserted")
                    if packages:
                        expected = expected.replace("\\begin{document}", "\\usepackage{array}\n\\begin{document}")
                    self.assertEqual(self.editor.toPlainText(), expected)
                    self.editor.undo()
                    self.assertEqual(self.editor.toPlainText(), self.before)

    def test_block_padding_at_utf16_eof_and_empty_preamble(self):
        for text in ("\U0001f600\U0001f680", "Body"):
            with self.subTest(text=text):
                self.editor.setPlainText(text)
                cursor = self.editor.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.editor.setTextCursor(cursor)
                self.window._insert_generated_snippet(self.tab, "Inserted", ("array",), "Inserted")
                self.assertEqual(self.editor.toPlainText(), "\\usepackage{array}\n" + text + "\nInserted")
                self.editor.undo()
                self.assertEqual(self.editor.toPlainText(), text)

    def test_inline_insertion_preserves_target_and_cursor_offset(self):
        self.select_body(backward=True)
        self.window._insert_generated_snippet(
            self.tab, "\\href{}{Text}", HYPERLINK_PACKAGES, "Inserted", block=False, cursor_offset=6,
        )
        expected = self.before.replace("Body", "\\href{}{Text}").replace(
            "\\begin{document}", "\\usepackage{hyperref}\n\\begin{document}",
        )
        self.assertEqual(self.editor.toPlainText(), expected)
        expected_cursor = len(expected[:expected.index("\\href{")].encode("utf-16-le")) // 2 + 6
        self.assertEqual(self.editor.textCursor().position(), expected_cursor)
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), self.before)

    def test_existing_package_keeps_consecutive_insertions_separate(self):
        before = self.before.replace("\\begin{document}", "\\usepackage{array}\n\\begin{document}")
        self.editor.setPlainText(before)
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        self.window._insert_generated_snippet(self.tab, "First", ("array",), "Inserted", block=False)
        first = self.editor.toPlainText()
        self.window._insert_generated_snippet(self.tab, "Second", ("array",), "Inserted", block=False)
        self.assertEqual(self.editor.toPlainText(), before + "FirstSecond")
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), first)
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), before)


class WindowLifetimeTests(TestCase):
    def setUp(self):
        self.application = app()

    def test_closed_tab_releases_native_editor_and_preserves_surviving_document(self):
        from shiboken6 import isValid

        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            closed_path = root / "closed.tex"
            kept_path = root / "kept.tex"
            closed_bytes = b"Closed source\r\n"
            kept_bytes = b"Surviving source\n" * 250
            closed_path.write_bytes(closed_bytes)
            kept_path.write_bytes(kept_bytes)
            window = MainWindow(settings_store=isolated_settings())
            try:
                window.auto_compile_action.setChecked(False)
                window.project_files.set_project_root(root)
                window.open_file(closed_path)
                closed = window.current_tab()
                window.open_file(kept_path)
                kept = window.current_tab()
                window.show()
                self.application.processEvents()
                cursor = kept.editor.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                kept.editor.setTextCursor(cursor)
                before = (kept.editor.textCursor().position(),
                          kept.editor.verticalScrollBar().value())
                closed_gutter = closed.editor.line_number_area
                closed_highlighter = closed.editor.highlighter
                window.close_tab(window._index_for_tab_id(id(closed.editor)))
                self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                self.application.processEvents()
                self.assertFalse(isValid(closed.editor))
                self.assertFalse(isValid(closed_gutter))
                self.assertFalse(isValid(closed_highlighter))
                self.assertIs(window.current_tab(), kept)
                self.assertTrue(isValid(kept.editor))
                self.assertEqual(window.editor_tabs.findChildren(LaTeXEditor), [kept.editor])
                self.assertEqual((kept.editor.textCursor().position(),
                                  kept.editor.verticalScrollBar().value()), before)
                self.assertEqual(kept.editor.toPlainText(), kept_bytes.decode())
                self.assertEqual(closed_path.read_bytes(), closed_bytes)
                self.assertEqual(kept_path.read_bytes(), kept_bytes)
                self.assertEqual(window.compile_authorized_roots, set())
            finally:
                window.close()
                self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_unowned_editor_releases_before_background_cyclic_collection(self):
        import gc
        import weakref

        gc.collect()
        finalized_on = []
        automatic_gc = gc.isenabled()
        editor = LaTeXEditor(r"\textc")
        observed = weakref.ref(editor, lambda _: finalized_on.append(threading.get_ident()))
        # No event drain: the highlighter can still have queued Qt work.
        # A gutter back-reference must not strand this Python-owned widget
        # until an unrelated worker thread happens to run cyclic GC.
        editor.close()
        del editor
        try:
            self.assertIsNone(observed())
            self.assertEqual(finalized_on, [threading.get_ident()])
            self.assertEqual(gc.isenabled(), automatic_gc)
        finally:
            # A failing baseline is cleaned on the GUI thread, not left for
            # another test's watcher to collect and crash the entire runner.
            gc.collect()
            self.application.processEvents()

    def test_failed_close_save_preserves_named_and_unnamed_editors(self):
        from shiboken6 import isValid

        with TemporaryDirectory() as directory:
            path = Path(directory) / "original.tex"
            original = b"Original bytes\r\n"
            path.write_bytes(original)
            for source_path in (None, path):
                with self.subTest(named=source_path is not None):
                    window = MainWindow(settings_store=isolated_settings())
                    window.auto_compile_action.setChecked(False)
                    editor = window._make_editor("Unsaved draft")
                    tab = EditorTab(editor=editor, path=source_path, modified=True, dirty=True)
                    window._add_tab(tab, "draft.tex")
                    try:
                        with patch("app.gui.editor_tab_manager.QMessageBox.warning",
                                   return_value=QMessageBox.StandardButton.Save), \
                             patch.object(window, "save_current_as", return_value=False) as save_as, \
                             patch.object(window, "flush_pending_save", return_value=False) as save:
                            window.close_tab(0)
                        self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                        self.assertIs(window.current_tab(), tab)
                        self.assertTrue(isValid(editor))
                        self.assertEqual(editor.toPlainText(), "Unsaved draft")
                        self.assertTrue(tab.modified and tab.dirty)
                        self.assertEqual(path.read_bytes(), original)
                        if source_path is None:
                            save_as.assert_called_once_with()
                            save.assert_not_called()
                        else:
                            save.assert_called_once_with(tab, compile_after_save=False)
                            save_as.assert_not_called()
                    finally:
                        tab.modified = tab.dirty = False
                        window.close()
                        self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_qt_parent_keeps_editor_and_gutter_alive_without_external_reference(self):
        import gc
        import weakref
        from PySide6.QtWidgets import QWidget
        from shiboken6 import isValid

        host = QWidget()
        editor = LaTeXEditor("line one\nline two")
        editor.setParent(host)
        observed = weakref.ref(editor)
        del editor
        try:
            gc.collect()
            self.assertTrue(isValid(observed()))
            self.assertEqual(observed().toPlainText(), "line one\nline two")
            host.show()
            self.application.processEvents()
            self.assertEqual(observed().line_number_area.sizeHint().width(),
                             observed().line_number_area_width())
            self.assertFalse(observed().line_number_area.grab().isNull())
        finally:
            host.close()
            host.deleteLater()
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertIsNone(observed())

    def test_scale_pins_cyclic_widgets_only_during_synchronous_update(self):
        import gc
        import weakref
        from PySide6.QtWidgets import QLabel
        from shiboken6 import isValid

        window = MainWindow(settings_store=isolated_settings())
        manager = self.application.ui_scale_manager
        old_scale = manager.scale
        target = 1.25 if old_scale != 1.25 else 1.0
        automatic_gc = gc.isenabled()
        refs, observed = [], []
        original_font = self.application.setFont
        original_style = self.application.setStyleSheet
        original_event = self.application.sendEvent

        def collect_and_call(name, callback, value):
            gc.collect()
            self.assertTrue(all(ref() is not None and isValid(ref()) for ref in refs), name)
            observed.append(name)
            callback(value)

        def dispatch_style(widget, event):
            if event.type() == QEvent.Type.StyleChange and "style" not in observed:
                collect_and_call("style", lambda value: original_event(widget, value), event)
                return True
            return original_event(widget, event)

        try:
            gc.disable()
            for _ in range(4):
                widget = QLabel("Synthetic cyclic widget")
                widget.ensurePolished()
                widget.cycle = widget
                refs.append(weakref.ref(widget))
                del widget
            with patch.object(self.application, "setFont", side_effect=lambda value:
                              collect_and_call("font", original_font, value)), \
                 patch.object(self.application, "setStyleSheet", side_effect=lambda value:
                              collect_and_call("style", original_style, value)), \
                 patch.object(self.application, "sendEvent", side_effect=dispatch_style):
                manager.apply_scale(target)
            self.assertEqual(observed, ["font", "style"])
            self.assertFalse(gc.isenabled())  # Application must not change GC policy.
            gc.collect()
            self.assertTrue(all(ref() is None for ref in refs))  # No lasting widget cache.
        finally:
            gc.collect()
            manager.apply_scale(old_scale)
            window.close()
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            if automatic_gc:
                gc.enable()

    def test_scale_collection_inside_real_qt_style_dispatch_is_safe(self):
        import json
        import subprocess
        import sys

        # A regression must fail this test, not crash the entire GUI test runner.
        with TemporaryDirectory() as directory:
            output = Path(directory) / "style-gc"
            result = subprocess.run([
                sys.executable, str(Path(__file__).resolve().parents[1] / "tools/probe_qt_style_lifecycle.py"),
                "--output", str(output), "--windows", "1", "--cycles", "1",
                "--collect-during-style", "--orphan-widgets", "8", "--expect-released",
            ], env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONFAULTHANDLER": "1"},
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-4000:])
            evidence = json.loads((output / "result.json").read_text(encoding="utf-8"))
            self.assertFalse(evidence["hold_style_widgets"])  # No probe-only keepalive control.
            self.assertEqual(len(evidence["orphan_deletions"]), 8)
            self.assertEqual({row["phase"] for row in evidence["orphan_deletions"]}, {"final-gc"})
            self.assertGreater(evidence["rows"][-1]["style_collections"], 0)
            # Qt can also retire transient popup widgets; track only the owned
            # cyclic targets, not an assumed constant QApplication total.
            self.assertEqual(evidence["rows"][0]["live_orphan_wrappers"], 8)
            self.assertEqual(evidence["rows"][-1]["live_orphan_wrappers"], 0)
            self.assertEqual(evidence["rows"][-1]["live_closed_wrappers"], 0)

    def test_confirmed_close_destroys_only_closed_window_at_event_boundary(self):
        from shiboken6 import isValid

        survivor = MainWindow(settings_store=isolated_settings())
        closed = survivor.spawn_window()
        child = closed.pdf_panel
        manager = self.application.ui_scale_manager
        try:
            self.assertTrue(closed.close())
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.assertFalse(isValid(closed))
            self.assertFalse(isValid(child))
            self.assertNotIn(closed, manager._windows)
            self.assertNotIn(closed, self.application._icstex_windows)
            self.assertIn(survivor, self.application._icstex_windows)
            self.assertTrue(isValid(survivor))
            self.assertFalse(survivor.readiness._closed)
            manager.apply_scale(1.25)
            manager.apply_scale(1.0)
            self.assertTrue(isValid(survivor.pdf_panel))
        finally:
            for window in (closed, survivor):
                if isValid(window):
                    window.close()
                    window.deleteLater()
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_cancelled_close_keeps_draft_and_window_alive_until_discard(self):
        from shiboken6 import isValid

        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor("Unstored synthetic draft")
        tab = EditorTab(editor=editor, modified=True, dirty=True)
        window._add_tab(tab, "unsaved.tex")
        try:
            with patch("app.gui.editor_tab_manager.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.Cancel):
                self.assertFalse(window.close())
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.assertTrue(isValid(window))
            self.assertEqual(editor.toPlainText(), "Unstored synthetic draft")
            self.assertFalse(window.readiness._closed)
            self.assertIn(window, self.application.ui_scale_manager._windows)
            with patch("app.gui.editor_tab_manager.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.Discard):
                self.assertTrue(window.close())
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.assertFalse(isValid(window))
        finally:
            if isValid(window):
                tab.modified = tab.dirty = False
                window.close()
                window.deleteLater()
                self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class GuiEditorTests(TestCase):
    def setUp(self) -> None:
        app()

    def test_window_close_block_cancel_preserves_both_controllers_and_draft(self):
        from app.core.blocks.project_repository import load_project
        from app.core.blocks.model import content_for_text
        from app.gui.blocks.project_session import ProjectSession
        from app.gui.block_mode import _install_session, _set_block_mode
        from tests.v1_fixtures import create_project
        with TemporaryDirectory() as directory:
            sample = create_project(Path(directory).resolve(), "block")
            loaded = load_project(sample.root.parent)
            session = ProjectSession(**{key: loaded[key] for key in
                ("registry", "layout", "sources", "document_theme", "project_dir")})
            window = MainWindow(settings_store=isolated_settings())
            try:
                _install_session(window, session)
                _set_block_mode(window, True)
                block = session.registry.blocks()[0]
                before = {p: p.read_bytes() for p in sample.root.parent.rglob("*") if p.is_file()}
                session.registry.update(block.id, {"content": content_for_text("Pending close draft")})
                session.notify_model_changed("qa")
                with patch("app.gui.blocks.close_guard.QMessageBox.warning", return_value=QMessageBox.StandardButton.Cancel):
                    event = QCloseEvent()
                    window.closeEvent(event)
                self.assertFalse(event.isAccepted())
                self.assertIs(window.block_session, session)
                self.assertFalse(session._closed)
                self.assertTrue(session._save_timer.isActive())
                self.assertFalse(window.workspace._closed)
                self.assertEqual({p: p.read_bytes() for p in before}, before)
                self.assertIn("Pending close draft", str(block.content))
            finally:
                session.shutdown()
                window.close()

    def test_source_close_cancel_keeps_pending_block_save_paused_until_decision(self):
        from app.gui.blocks.project_session import ProjectSession
        from app.gui.block_mode import _install_session
        with TemporaryDirectory() as directory:
            session = ProjectSession(project_dir=Path(directory).resolve())
            window = MainWindow(settings_store=isolated_settings())
            try:
                _install_session(window, session)
                session.notify_model_changed("pending Block change")
                window.new_document()
                tab = window.current_tab()
                tab.editor.insertPlainText("Unsaved source")
                def cancel(_tab):
                    self.assertFalse(session._save_timer.isActive())
                    return QMessageBox.StandardButton.Cancel
                with patch.object(window.tab_manager, "_ask_unsaved_choice", side_effect=cancel):
                    event = QCloseEvent()
                    window.closeEvent(event)
                self.assertFalse(event.isAccepted())
                self.assertTrue(session._save_timer.isActive())
                self.assertFalse(session._closed)
            finally:
                session.shutdown()
                for item in window.tabs.values():
                    window.documents.cancel_save_timer(item)
                    item.modified = item.dirty = False
                window.close()

    def test_project_wizard_cancel_and_conflict_preserve_destination_and_fields(self):
        with TemporaryDirectory() as directory:
            dialog = ProjectWizardDialog()
            dialog.parent_edit.setText(directory)
            dialog.name_edit.setText("中文 项目")
            self.assertIn("中文 项目", dialog.destination.text())
            dialog.reject()
            self.assertEqual(list(Path(directory).iterdir()), [])
            existing = Path(directory) / "中文 项目"
            existing.mkdir()
            dialog.accept()
            self.assertIsNone(dialog.created_project)
            self.assertIn("目标已存在", dialog.error.text())
            self.assertEqual(dialog.name_edit.text(), "中文 项目")
            self.assertEqual(list(existing.iterdir()), [])

    def test_create_project_opens_verified_files_without_compiling(self):
        from app.core.project_profile import load_profile
        with TemporaryDirectory() as directory:
            window = MainWindow(settings_store=isolated_settings())
            self.addCleanup(window.close)
            dialog = ProjectWizardDialog(window)
            dialog.parent_edit.setText(directory)
            dialog.name_edit.setText("中文 项目")
            dialog.template_combo.setCurrentIndex(dialog.template_combo.findData("chinese_xelatex_article"))
            dialog.open_new_window.setChecked(False)
            dialog.accept()
            self.assertIsNotNone(dialog.created_project, dialog.error.text())
            with patch("app.gui.main_window.ProjectWizardDialog", return_value=dialog), \
                 patch.object(dialog, "exec", return_value=QDialog.DialogCode.Accepted), \
                 patch.object(window.compile, "compile_current") as compile_, \
                 patch.object(CompileManager, "compile_async") as compiler:
                window.new_project()
                compile_.assert_not_called()
                compiler.assert_not_called()
            project = dialog.created_project
            self.assertEqual(window.current_tab().path, project.tex_file)
            self.assertEqual(window.current_engine, LaTeXEngine.AUTO)
            self.assertEqual(load_profile(project.root_dir).profile.engine, "xelatex")
            self.assertEqual(window.compile_authorized_roots, set())
            window.workspace.refresh()
            self.assertIn("中文 项目", window.workspace.title.full_text)
            self.assertIn("main.tex", window.workspace.details.full_text)
            window.close()

    def test_project_wizard_defaults_to_new_window_when_source_is_open(self):
        window = MainWindow(settings_store=isolated_settings())
        window.new_document()
        dialog = ProjectWizardDialog(window)
        self.assertTrue(dialog.open_new_window.isChecked())
        dialog.reject()
        window.current_tab().modified = window.current_tab().dirty = False
        window.close()

    def test_workspace_header_reads_cached_state_and_does_not_compile_or_scan(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "main.tex"
            path.write_text("\\documentclass{article}\n\\begin{document}A\\end{document}")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window.project_files.set_project_root(root)
            window.open_file(path)
            with patch("app.core.project_dependencies.static_dependencies", side_effect=AssertionError("scan")), \
                 patch.object(window, "_compile_root_for_tab", side_effect=AssertionError("resolve")), \
                 patch.object(window, "create_compile_manager", side_effect=AssertionError("manager")), \
                 patch.object(window.compile, "compile_current") as compile_:
                window.workspace.refresh()
                compile_.assert_not_called()
            self.assertIn("入口：main.tex", window.workspace.details.full_text)
            self.assertIn("已保存", window.workspace.details.full_text)
            window.toolchain = LaTeXToolchain(None, None)
            window.workspace.refresh()
            self.assertIs(window.workspace.next_button.defaultAction(), window.environment_doctor_action)
            window.close()
            window.workspace.schedule()
            self.assertFalse(window.workspace._timer.isActive())

    def test_workspace_saves_current_root_and_preserves_cursor(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "main.tex"
            path.write_text("\\documentclass{article}\n\\begin{document}A\\end{document}")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window.open_file(path)
            tab = window.current_tab()
            with patch.object(window.documents, "schedule_save"):
                tab.editor.insertPlainText("% changed\n")
            position = tab.editor.textCursor().position()
            window.workspace.refresh()
            self.assertIs(window.workspace.next_button.defaultAction(), window.workspace.save_action)
            with patch.object(CompileManager, "compile_async") as compile_:
                window.workspace.next_button.click()
                from tests.test_gui_dependencies import wait_until
                self.assertTrue(wait_until(lambda: not window.dependencies.is_busy))
                compile_.assert_not_called()
            self.assertFalse(tab.modified)
            self.assertEqual(tab.editor.textCursor().position(), position)
            self.assertEqual(path.read_text(), tab.editor.toPlainText())
            window.close()

    def test_workspace_root_child_navigation_keeps_project_asset_and_search_scope(self):
        with TemporaryDirectory() as directory:
            from tests.v1_fixtures import create_project
            sample = create_project(Path(directory).resolve())
            window = MainWindow(settings_store=isolated_settings())
            window.project_files.set_project_root(sample.root.parent)
            window.open_file(sample.draft_path)
            self.addCleanup(window.close)
            window.show()
            QApplication.processEvents()
            window.workspace.refresh()
            self.assertIn("入口：main.tex", window.workspace.details.full_text)
            with patch("app.gui.project_panel_controller.search_project", return_value=[]) as search:
                window.project_panels.run_project_search("sample", False, False)
                self.assertEqual(search.call_args.args[0], sample.root.parent)
            window.workspace._source_navigation(3)
            self.assertIn(sample.root.parent, window.project_panels._asset_indexes)
            self.assertNotIn(sample.draft_path.parent, window.project_panels._asset_indexes)
            window.close()

    def test_panel_edit_burst_refreshes_only_visible_dirty_domain(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.new_document()
        tab = window.current_tab()
        window.show()
        window.toolbox_dock.show()
        window.sidebar_tabs.setCurrentIndex(1)
        QApplication.processEvents()
        with patch.object(window.outline_panel, "set_outline", wraps=window.outline_panel.set_outline) as outline, \
                patch("app.gui.project_panel_controller.AssetIndex.scan") as scan, \
                patch("app.gui.project_panel_controller.list_snapshots") as history, \
                patch.object(window.references_panel, "set_references") as references:
            for title in ("One", "Two", "Latest"):
                tab.editor.setPlainText("\\section{" + title + "}\n\\label{latest}")
            self.assertEqual(outline.call_count, 0)
            self.assertTrue(wait_until(lambda: outline.call_count == 1))
            self.assertEqual(outline.call_args.args[0][0].title, "Latest")
            scan.assert_not_called()
            history.assert_not_called()
            references.assert_not_called()
            self.assertEqual(tab.editor._completion_labels, ["latest"])
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_hidden_panel_waits_until_visible_and_latest_tab_wins(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.new_document()
        first = window.current_tab()
        window.show()
        window.sidebar_tabs.setCurrentIndex(1)
        window.toolbox_dock.hide()
        with patch.object(window.outline_panel, "set_outline", wraps=window.outline_panel.set_outline) as outline:
            first.editor.setPlainText(r"\section{First}")
            window.new_document()
            second = window.current_tab()
            second.editor.setPlainText(r"\section{Second}")
            self.assertTrue(wait_until(lambda: not window.project_panels._timer.isActive()))
            outline.assert_not_called()
            window.toolbox_dock.show()
            self.assertTrue(wait_until(lambda: outline.call_count > 0))
            self.assertEqual(outline.call_args.args[0][0].title, "Second")
        for tab in (first, second):
            tab.modified = False
            tab.dirty = False
        window.close()

    def test_panel_reconcile_finds_new_images_but_text_edits_do_not_scan_assets(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "main.tex"
            source.write_text("initial", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window.save_debounce_ms = 60_000
            window.open_file(source)
            tab = window.current_tab()
            window.show()
            window.toolbox_dock.show()
            window.sidebar_tabs.setCurrentIndex(3)
            QApplication.processEvents()
            with patch("app.gui.project_panel_controller.AssetIndex.scan", wraps=window.project_panels._asset_indexes[root].scan) as scan, \
                    patch("app.core.asset_index._graphics_references") as usage_scan:
                tab.editor.insertPlainText("changed")
                self.assertTrue(wait_until(lambda: not window.project_panels._timer.isActive()))
                scan.assert_not_called()
                usage_scan.assert_not_called()
            (root / "new.png").write_bytes(b"image")
            window.project_panels.reconcile()
            self.assertEqual(window.images_panel.table.rowCount(), 1)
            self.assertEqual(window.images_panel.table.item(0, 2).text(), "使用待检查")
            self.assertTrue(window.images_panel.check_detail.isReadOnly())
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_history_refresh_is_snapshot_driven_and_explicit_refresh_is_full(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "main.tex"
            source.write_text("initial", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window.open_file(source)
            tab = window.current_tab()
            window.show()
            window.toolbox_dock.show()
            window.sidebar_tabs.setCurrentIndex(4)
            QApplication.processEvents()
            with patch("app.gui.project_panel_controller.list_snapshots", return_value=[]) as history:
                tab.editor.insertPlainText("changed")
                self.assertTrue(window.flush_pending_save(tab, compile_after_save=False))
                history.assert_not_called()
                self.assertTrue(wait_until(lambda: history.call_count == 1))
            with patch("app.gui.project_panel_controller.AssetIndex.scan", return_value={}) as scan, \
                    patch.object(window.labels_panel, "set_labels") as labels:
                window.toolbox_dock.hide()
                window.refresh_project_panels()
                scan.assert_called_once()
                labels.assert_called_once()
            window.close()
            self.assertFalse(window.project_panels._timer.isActive())
            self.assertFalse(window.project_panels._reconcile_timer.isActive())

    def test_editor_smoke_and_line_number_width(self) -> None:
        editor = LaTeXEditor("one\ntwo")

        self.assertEqual(editor.blockCount(), 2)
        self.assertGreater(editor.line_number_area_width(), 0)
        self.assertIsNotNone(editor.highlighter)
        self.assertEqual(editor.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth)

    def test_file_tree_is_read_only_drag_source_with_project_assets(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        self.assertTrue(window.model.isReadOnly())
        self.assertTrue(window.tree.dragEnabled())
        self.assertFalse(window.tree.acceptDrops())
        self.assertEqual(
            window.tree.dragDropMode(),
            QAbstractItemView.DragDropMode.DragOnly,
        )
        self.assertEqual(
            window.tree.contextMenuPolicy(),
            Qt.ContextMenuPolicy.CustomContextMenu,
        )
        self.assertTrue(
            {"*.tex", "*.bib", "*.png", "*.jpg", "*.jpeg", "*.pdf", "*.eps", "*.svg"}
            <= set(window.model.nameFilters())
        )
        self.assertEqual(
            window.new_window_action.shortcut(),
            QKeySequence("Ctrl+Shift+N"),
        )
        window.close()

    def test_opening_child_keeps_selected_project_tree_root(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            chapters = root / "chapters"
            chapters.mkdir()
            child = chapters / "one.tex"
            child.write_text("Child", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.project_files.set_project_root(root)

            window.open_file(child)

            tree_root = Path(window.model.filePath(window.tree.rootIndex())).resolve()
            self.assertEqual(window.selected_project_scope, root)
            self.assertEqual(tree_root, root)
            window.close()

    def test_dropped_tex_opens_tab_without_changing_project_root(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            main = root / "main.tex"
            child = root / "child.tex"
            main.write_text("Main", encoding="utf-8")
            child.write_text("Child", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.project_files.set_project_root(root)
            window.open_file(main)
            tab = window.current_tab()
            assert tab is not None
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(child))])
            event = QDropEvent(
                QPointF(1, 1),
                Qt.DropAction.CopyAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )

            tab.editor.dropEvent(event)

            self.assertEqual(window.editor_tabs.count(), 2)
            self.assertEqual(window.current_tab().path, child)
            self.assertEqual(
                Path(window.model.filePath(window.tree.rootIndex())).resolve(),
                root,
            )
            window.close()

    def test_dropped_tex_opens_from_empty_welcome_surface(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "main.tex"
            source.write_text("Main", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.project_files.set_project_root(root)
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(source))])
            event = QDropEvent(
                QPointF(1, 1),
                Qt.DropAction.CopyAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )

            handled = window.project_files.eventFilter(window.welcome_page, event)

            self.assertTrue(handled)
            self.assertTrue(event.isAccepted())
            self.assertEqual(window.editor_tabs.count(), 1)
            self.assertEqual(window.current_tab().path, source)
            window.close()

    def test_tree_image_drag_uses_existing_safe_import_pipeline(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            figures = root / "figures"
            figures.mkdir()
            main = root / "main.tex"
            image = figures / "plot.png"
            main.write_text("\\documentclass{article}\n", encoding="utf-8")
            image.write_bytes(b"png")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window.project_files.set_project_root(root)
            window.open_file(main)
            tab = window.current_tab()
            assert tab is not None
            image_index = window.model.index(str(image))
            self.assertTrue(image_index.isValid())
            mime = window.model.mimeData([image_index])
            self.assertTrue(mime.hasUrls())
            event = QDropEvent(
                QPointF(1, 1),
                Qt.DropAction.CopyAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )

            tab.editor.dropEvent(event)

            self.assertTrue(
                wait_until(lambda: "\\includegraphics" in tab.editor.toPlainText())
            )
            self.assertIn("figures/plot.png", tab.editor.toPlainText())
            tab.modified = tab.dirty = False
            window.close()

    def test_safe_rename_updates_open_tab_and_recent_path(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "draft.tex"
            destination = root / "notes.tex"
            source.write_text("Draft", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window.project_files.set_project_root(root)
            window.open_file(source)
            window.show()
            app().processEvents()
            editor = window.current_tab().editor
            editor.moveCursor(QTextCursor.MoveOperation.End)
            before_view = (editor.textCursor().position(), editor.verticalScrollBar().value())

            moved = window.project_files.perform_move(
                source,
                destination,
                operation_label="重命名",
            )

            self.assertTrue(moved)
            self.assertFalse(source.exists())
            self.assertEqual(destination.read_text(encoding="utf-8"), "Draft")
            self.assertEqual(window.current_tab().path, destination)
            self.assertIn(destination, window.app_settings.recent_files())
            self.assertNotIn(source, window.app_settings.recent_files())
            self.assertTrue(wait_until(lambda: Path(window.model.filePath(window.tree.currentIndex())) == destination))
            self.assertEqual(Path(window.model.filePath(window.tree.rootIndex())), root)
            self.assertIs(window.current_tab().editor, editor)
            self.assertEqual((editor.textCursor().position(), editor.verticalScrollBar().value()), before_view)
            self.assertFalse(window.compile_authorized_roots)
            window.close()

    def test_safe_rename_blocks_referenced_file_without_mutation(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            main = root / "main.tex"
            child = root / "child.tex"
            destination = root / "renamed.tex"
            main.write_text("\\input{child}\n", encoding="utf-8")
            child.write_text("Child", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.project_files.set_project_root(root)

            with patch("app.gui.project_file_controller.QMessageBox.warning") as warning:
                moved = window.project_files.perform_move(
                    child,
                    destination,
                    operation_label="重命名",
                )

            self.assertFalse(moved)
            self.assertTrue(child.exists())
            self.assertFalse(destination.exists())
            self.assertIn("引用失效", warning.call_args.args[2])
            window.close()

    def test_rename_deferred_selection_is_cancelled_when_window_is_destroyed(self) -> None:
        import sys
        from shiboken6 import isValid

        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, destination = root / "draft.tex", root / "notes.tex"
            source.write_bytes(b"Synthetic source\r\n")
            window = MainWindow(settings_store=isolated_settings())
            window.project_files.set_project_root(root)
            errors = []
            try:
                with patch.object(sys, "excepthook", side_effect=lambda _type, value, _tb: errors.append(str(value))):
                    self.assertTrue(window.project_files.perform_move(source, destination))
                    self.assertTrue(window.close())
                    app().sendPostedEvents(None, QEvent.Type.DeferredDelete)
                    self.assertFalse(isValid(window))
                    drained = []
                    QTimer.singleShot(0, lambda: drained.append(True))
                    self.assertTrue(wait_until(lambda: bool(drained)))
                self.assertEqual(errors, [])
                self.assertFalse(source.exists())
                self.assertEqual(destination.read_bytes(), b"Synthetic source\r\n")
            finally:
                if isValid(window):
                    window.close()
                app().sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_rename_deferred_selection_cannot_select_into_a_different_project(self) -> None:
        with TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root, other = base / "one", base / "two"
            root.mkdir()
            other.mkdir()
            source, destination, active = root / "draft.tex", root / "notes.tex", other / "active.tex"
            source.write_bytes(b"Synthetic source\r\n")
            active.write_bytes(b"Unrelated source\n")
            window = MainWindow(settings_store=isolated_settings())
            try:
                window.project_files.set_project_root(root)
                self.assertTrue(window.project_files.perform_move(source, destination))
                window.project_files.set_project_root(other)
                window.tree.setCurrentIndex(window.model.index(str(active)))
                drained = []
                QTimer.singleShot(0, lambda: drained.append(True))
                self.assertTrue(wait_until(lambda: bool(drained)))
                self.assertEqual(Path(window.model.filePath(window.tree.currentIndex())), active)
                self.assertEqual(Path(window.model.filePath(window.tree.rootIndex())), other)
                self.assertEqual(destination.read_bytes(), b"Synthetic source\r\n")
                self.assertEqual(active.read_bytes(), b"Unrelated source\n")
            finally:
                window.close()
                app().sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_safe_rename_refuses_to_race_active_compile(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "draft.tex"
            destination = root / "notes.tex"
            source.write_text("Draft", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.project_files.set_project_root(root)
            window.open_file(source)
            tab = window.current_tab()
            assert tab is not None
            manager = Mock(root_file=source, is_busy=True)
            tab.manager = manager
            window.compile_managers[source] = manager

            with patch("app.gui.project_file_controller.QMessageBox.warning") as warning:
                moved = window.project_files.perform_move(source, destination)

            self.assertFalse(moved)
            self.assertTrue(source.exists())
            self.assertFalse(destination.exists())
            self.assertIn("正在编译", warning.call_args.args[2])
            tab.manager = None
            window.compile_managers.clear()
            window.close()

    def test_spawned_window_is_registered_and_removed_on_close(self) -> None:
        application = app()
        existing = list(getattr(application, "_icstex_windows", []))
        parent = MainWindow(settings_store=isolated_settings())

        child = parent.spawn_window()

        windows = getattr(application, "_icstex_windows")
        self.assertIn(parent, windows)
        self.assertIn(child, windows)
        child.close()
        QApplication.processEvents()
        self.assertNotIn(child, windows)
        self.assertIn(parent, windows)
        parent.close()
        QApplication.processEvents()
        self.assertEqual(windows, existing)

    def test_open_in_new_window_preserves_the_same_project_scope(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            child_path = root / "child.tex"
            child_path.write_text("Child", encoding="utf-8")
            parent = MainWindow(settings_store=isolated_settings())
            parent.project_files.set_project_root(root)

            child = parent.project_files.open_in_new_window(child_path)

            self.assertEqual(child.selected_project_scope, root)
            self.assertEqual(child.current_tab().path, child_path)
            self.assertEqual(
                Path(child.model.filePath(child.tree.rootIndex())).resolve(),
                root,
            )
            child.close()
            parent.close()

    def test_export_and_reveal_pdf(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        self.assertEqual(window.export_pdf_action.text(), "导出 PDF")
        self.assertIn("PDF", window.reveal_pdf_action.text())

        # Without a successful PDF both actions are disabled and safe no-ops.
        self.assertFalse(window.export_pdf_action.isEnabled())
        self.assertFalse(window.reveal_pdf_action.isEnabled())
        self.assertFalse(window.pdf_panel.export_pdf_button.isEnabled())
        self.assertFalse(window.pdf_panel.reveal_pdf_button.isEnabled())
        self.assertFalse(window.export_pdf())
        with patch("app.gui.main_window.subprocess.Popen") as popen, patch(
            "app.gui.main_window.QDesktopServices.openUrl"
        ) as open_url:
            window.reveal_pdf()
        popen.assert_not_called()
        open_url.assert_not_called()

        with TemporaryDirectory() as tmp:
            tex = Path(tmp) / "main.tex"
            tex.write_text("x", encoding="utf-8")
            source = Path(tmp) / "main.pdf"
            source.write_bytes(b"%PDF-1.4 fake")
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            tab = EditorTab(editor=window._make_editor("x"), path=tex)
            window._add_tab(tab, tex.name)
            window.pdf_state.begin_build(tex, 1)
            window.pdf_state.finish_build(tex, 1, CompileOutcome.SUCCESS, pdf_file=source)
            window._update_pdf_action_state()
            self.assertTrue(window.export_pdf_action.isEnabled())
            self.assertTrue(window.pdf_panel.reveal_pdf_button.isEnabled())
            self.assertEqual(window.pdf_panel.freshness_label.text(), "PDF 已是最新")

            # A cached fake PDF record is not build-input evidence. The UI now
            # dispatches to explicit review; exact-byte publication is covered
            # by test_submission_delivery_gui and the real-FINAL product probe.
            with patch("app.gui.submission_delivery_dialog.show_submission_delivery", return_value=None) as review:
                self.assertFalse(window.export_pdf())
            review.assert_called_once_with(window)
            self.assertEqual(source.read_bytes(), b"%PDF-1.4 fake")

            with patch("app.gui.main_window.subprocess.Popen") as popen, patch(
                "app.gui.main_window.QDesktopServices.openUrl"
            ) as open_url:
                window.reveal_pdf()
            if popen.called:
                args = popen.call_args.args[0]
                self.assertIsInstance(args, list)
                self.assertNotIn("shell", popen.call_args.kwargs)
            else:
                open_url.assert_called_once()

    def test_export_pdf_rejects_empty_and_reviews_stale_without_implicit_rebuild(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window._watch_file = lambda _path: None  # type: ignore[method-assign]

        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "main.tex"
            source.write_text("x", encoding="utf-8")
            tab = EditorTab(editor=window._make_editor("x"), path=source)
            window._add_tab(tab, source.name)

            # Zero-byte PDF: not a valid successful build, actions stay disabled.
            empty_pdf = Path(tmp) / "empty.pdf"
            empty_pdf.write_bytes(b"")
            window.pdf_state.begin_build(source, 1)
            window.pdf_state.finish_build(source, 1, CompileOutcome.SUCCESS, pdf_file=empty_pdf)
            window._update_pdf_action_state()
            self.assertFalse(window.export_pdf_action.isEnabled())
            with patch("app.gui.main_window.QFileDialog.getSaveFileName") as dialog:
                self.assertFalse(window.export_pdf())
            dialog.assert_not_called()

            # A stale PDF is never copied. Save/FINAL now require separate
            # explicit actions within the reviewed submission workflow.
            pdf = Path(tmp) / "main.pdf"
            pdf.write_bytes(b"%PDF-1.4 old")
            window.pdf_state.begin_build(source, 2)
            window.pdf_state.finish_build(source, 2, CompileOutcome.SUCCESS, pdf_file=pdf)
            window.pdf_state.mark_edited(source)
            window._update_pdf_action_state()
            self.assertTrue(window.export_pdf_action.isEnabled())
            self.assertEqual(window.pdf_panel.freshness_label.text(), "源码已修改，PDF 待更新")

            exported = Path(tmp) / "exported"
            tab.manager = window.create_compile_manager(source)
            with patch.object(tab.manager, "compile_async") as compile_async, patch(
                "app.gui.submission_delivery_dialog.show_submission_delivery", return_value=None,
            ) as review:
                self.assertFalse(window.export_pdf())
            review.assert_called_once_with(window)
            compile_async.assert_not_called()
            self.assertFalse(exported.with_suffix(".pdf").exists())
            self.assertIsNone(window.pdf_export.pending_for(source))

    def test_main_window_smoke(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        self.assertEqual(window.windowTitle(), "ICSTeX")
        self.assertEqual(window.error_table.columnCount(), 3)
        self.assertEqual(window.engine_selector.count(), 4)
        self.assertEqual(window.current_engine, LaTeXEngine.AUTO)
        self.assertEqual(window.sidebar_tabs.count(), 9)
        self.assertIsInstance(window.toolbox_navigation, ToolboxNavigation)
        self.assertEqual(window.sidebar_tabs.tabText(0), "文件")
        self.assertEqual(window.sidebar_tabs.tabText(1), "大纲")
        self.assertEqual(window.sidebar_tabs.tabText(2), "搜索")
        self.assertEqual(window.sidebar_tabs.tabText(3), "图片")
        self.assertEqual(window.sidebar_tabs.tabText(4), "历史")
        self.assertEqual(window.sidebar_tabs.tabText(5), "插入")
        self.assertEqual(window.sidebar_tabs.tabText(6), "模板")
        self.assertEqual(window.sidebar_tabs.tabText(7), "引用")
        self.assertEqual(window.sidebar_tabs.tabText(8), "标签")
        self.assertTrue(window.toolbox_navigation.navigationButton(0).isChecked())
        self.assertEqual(window.toolbox_navigation.navigationButton(0).toolTip(), "项目文件")
        self.assertEqual(Path(window.model.filePath(window.tree.rootIndex())), Path.home())
        self.assertEqual(window.tree.accessibleName(), "项目文件")
        self.assertIn("effective", window.word_count_labels)
        self.assertIn("numbers", window.word_count_labels)
        self.assertIsInstance(window.word_count_panel, QScrollArea)
        self.assertGreaterEqual(window.word_count_labels["effective"].minimumHeight(), 28)
        self.assertIsInstance(window.find_replace_bar, FindReplaceBar)
        self.assertIsInstance(window.welcome_page, WelcomePage)
        self.assertIsInstance(window.diagnostic_panel, DiagnosticsPanel)
        self.assertEqual(window.source_stack.currentWidget(), window.welcome_page)
        self.assertEqual(window.main_splitter.count(), 2)
        self.assertEqual(window.vertical_splitter.count(), 2)
        self.assertFalse(window.vertical_splitter.isCollapsible(0))
        self.assertFalse(window.vertical_splitter.isCollapsible(1))
        self.assertTrue(window.toolbox_dock.isHidden())
        self.assertFalse(window.toolbox_action.isChecked())
        window.toolbox_action.setChecked(True)
        self.assertFalse(window.toolbox_dock.isHidden())
        window.toolbox_action.setChecked(False)
        self.assertTrue(window.toolbox_dock.isHidden())
        self.assertTrue(hasattr(window.pdf_panel, "page_spin"))
        if window.pdf_panel._view is not None and window.pdf_panel._search_model is not None:
            self.assertIs(window.pdf_panel._view.searchModel(), window.pdf_panel._search_model)
        self.assertTrue(hasattr(window, "settings_action"))
        self.assertTrue(hasattr(window, "stop_compile_action"))
        self.assertTrue(hasattr(window, "health_check_action"))
        self.assertTrue(hasattr(window, "environment_doctor_action"))
        self.assertTrue(hasattr(window, "feedback_bundle_action"))
        self.assertTrue(hasattr(window, "user_guide_action"))
        self.assertGreaterEqual(window.templates_panel.template_combo.count(), 9)
        insert_labels = {button.text() for button in window.insert_panel.findChildren(QPushButton)}
        self.assertIn("章节标题", insert_labels)
        self.assertNotIn("分段函数", insert_labels)
        self.assertIn("图片布局", insert_labels)
        self.assertEqual(window.welcome_page.guide_button.text(), "新手导引")
        self.assertTrue(hasattr(window, "auto_compile_toggle"))
        self.assertIsInstance(window.auto_compile_toggle, AutoCompileToggle)
        self.assertFalse(window.stop_compile_action.isEnabled())
        for action in (
            window.save_action,
            window.save_as_action,
            window.compile_action,
            window.clean_build_action,
            window.full_rebuild_action,
            window.health_check_action,
            window.word_count_action,
            window.find_action,
            window.replace_action,
            window.sync_pdf_action,
        ):
            self.assertFalse(action.isEnabled())
        self.assertEqual(window.status_engine_label.text(), "Auto")
        self.assertEqual(window.auto_compile_toggle.isChecked(), window.auto_compile_action.isChecked())
        window.auto_compile_toggle.setChecked(False)
        self.assertFalse(window.auto_compile_action.isChecked())
        window.auto_compile_action.setChecked(True)
        self.assertTrue(window.auto_compile_toggle.isChecked())
        self.assertEqual(window.status_auto_label.text(), "自动编译")
        window.close()

    def test_document_actions_follow_editor_availability(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        window.new_document()
        for action in (
            window.save_action,
            window.save_as_action,
            window.compile_action,
            window.clean_build_action,
            window.full_rebuild_action,
            window.health_check_action,
            window.word_count_action,
            window.find_action,
            window.replace_action,
        ):
            self.assertTrue(action.isEnabled())
        self.assertFalse(window.sync_pdf_action.isEnabled())

        tab = window.current_tab()
        assert tab is not None
        tab.modified = tab.dirty = False
        window.close_tab(0)
        self.assertFalse(window.compile_action.isEnabled())
        self.assertFalse(window.save_action.isEnabled())
        window.close()

    def test_support_project_only_opens_repository_after_explicit_action(self) -> None:
        with patch("app.gui.main_window_actions.QDesktopServices.openUrl", return_value=True) as open_url:
            window = MainWindow(settings_store=isolated_settings())
            try:
                app().processEvents()
                open_url.assert_not_called()
                action = window.support_project_action
                menu_actions = window.menuBar().actions()
                help_action = next(item for item in menu_actions if item.text() == "帮助")
                help_menu = help_action.menu()
                self.assertIn(action, help_menu.actions())
                self.assertTrue(action.isEnabled())
                self.assertFalse(action.isCheckable())
                self.assertIn("Star", action.text())
                self.assertIn("完全自愿", action.toolTip())
                action.trigger()
                open_url.assert_called_once_with(QUrl("https://github.com/leoXu-612/ICSTeX"))
                self.assertNotIn("已 Star", window.statusBar().currentMessage())
            finally:
                window.close()

    def test_support_project_browser_failure_reports_link_without_modal(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        try:
            with patch("app.gui.main_window_actions.QDesktopServices.openUrl", return_value=False), \
                    patch.object(QMessageBox, "information") as information:
                window.support_project_action.trigger()
            self.assertIn("https://github.com/leoXu-612/ICSTeX", window.statusBar().currentMessage())
            information.assert_not_called()
        finally:
            window.close()

    def test_recent_projects_hide_internal_folders_and_remember_real_root(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "paper"
            build_dir = root / ".latex_build"
            history_dir = root / ".icstex" / "history" / "main.tex"
            root.mkdir()
            build_dir.mkdir()
            history_dir.mkdir(parents=True)
            source = root / "main.tex"
            build_file = build_dir / "main.bbl"
            snapshot = history_dir / "snapshot.tex"
            source.write_text("\\documentclass{article}\n\\begin{document}Now\\end{document}\n", encoding="utf-8")
            build_file.write_text("build output", encoding="utf-8")
            snapshot.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            settings = isolated_settings()
            settings.add_recent_project(root)
            settings.add_recent_project(build_dir)
            settings.add_recent_project(history_dir)

            window = MainWindow(settings_store=settings)
            recent_tooltips = {
                button.toolTip()
                for button in window.welcome_page.findChildren(QPushButton)
                if button.objectName() == "welcomeRecent"
            }
            self.assertIn(str(root.resolve()), recent_tooltips)
            self.assertNotIn(str(build_dir.resolve()), recent_tooltips)
            self.assertNotIn(str(history_dir.resolve()), recent_tooltips)

            window._remember_recent_file(build_file)
            self.assertEqual(settings.recent_projects()[0], root.resolve())
            window._remember_recent_file(snapshot)
            self.assertEqual(settings.recent_projects()[0], root.resolve())
            window.close()

    def test_bottom_console_header_stays_available_when_collapsed(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.new_document()
        window.show()
        app().processEvents()

        self.assertLessEqual(window.vertical_splitter.sizes()[1], 44)
        window.bottom_collapse_button.click()
        app().processEvents()
        self.assertGreater(window.vertical_splitter.sizes()[1], 44)
        window.bottom_collapse_button.click()
        app().processEvents()
        self.assertLessEqual(window.vertical_splitter.sizes()[1], 44)
        self.assertEqual(window.bottom_collapse_button.toolTip(), "展开控制台：日志、错误、字数和检查")

        window.bottom_collapse_button.click()
        app().processEvents()
        self.assertGreater(window.vertical_splitter.sizes()[1], 44)
        window.close()

    def test_open_declared_cp1252_preserves_encoding_on_save(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "legacy.tex"
            original = "% !TEX encoding = Windows Latin 1\nRésumé".encode("cp1252")
            source.write_bytes(original)
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)

            with patch.object(window, "compile_current"):
                window.open_file(source)

            tab = window.current_tab()
            self.assertIsNotNone(tab)
            assert tab is not None
            self.assertEqual(tab.encoding, "cp1252")
            self.assertIn("Résumé", tab.editor.toPlainText())
            self.assertIn("编码：cp1252", window.editor_tabs.tabToolTip(0))
            cursor = tab.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            tab.editor.setTextCursor(cursor)
            tab.editor.insertPlainText("!")
            self.assertTrue(window.save_current())
            self.assertEqual(source.read_bytes(), original + b"!")
            tab.modified = tab.dirty = False
            window.close()

    def test_open_file_never_starts_compile(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("\\documentclass{article}", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())

            with patch.object(window, "compile_current") as compile_current:
                window.open_file(source)

            compile_current.assert_not_called()
            self.assertIn("首次编译", window.statusBar().currentMessage())
            window.close()

    def test_open_invalid_utf8_can_be_cancelled_without_replacement(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "unknown.tex"
            source.write_bytes(b"Paper \x81 text")
            window = MainWindow(settings_store=isolated_settings())

            with patch(
                "app.gui.main_window.QInputDialog.getItem",
                return_value=("简体中文（GB18030）", False),
            ):
                window.open_file(source)

            self.assertEqual(window.editor_tabs.count(), 0)
            self.assertEqual(source.read_bytes(), b"Paper \x81 text")
            window.close()

    def test_open_invalid_utf8_uses_user_selected_encoding(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "legacy.tex"
            source.write_bytes("Résumé".encode("cp1252"))
            window = MainWindow(settings_store=isolated_settings())

            with (
                patch(
                    "app.gui.main_window.QInputDialog.getItem",
                    return_value=("Windows 西文（CP1252）", True),
                ),
                patch.object(window, "compile_current"),
            ):
                window.open_file(source)

            tab = window.current_tab()
            self.assertIsNotNone(tab)
            assert tab is not None
            self.assertEqual(tab.encoding, "cp1252")
            self.assertEqual(tab.editor.toPlainText(), "Résumé")
            tab.modified = tab.dirty = False
            window.close()

    def test_unrepresentable_character_does_not_overwrite_legacy_file(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "legacy.tex"
            original = "% !TEX encoding = Windows Latin 1\nRésumé".encode("cp1252")
            source.write_bytes(original)
            window = MainWindow(settings_store=isolated_settings())
            with patch.object(window, "compile_current"):
                window.open_file(source)
            tab = window.current_tab()
            assert tab is not None
            tab.editor.setPlainText(tab.editor.toPlainText() + "\n中文")

            with patch("app.gui.document_lifecycle.QMessageBox.warning") as warning:
                saved = window.save_current()

            self.assertFalse(saved)
            self.assertEqual(source.read_bytes(), original)
            self.assertIn("cp1252", warning.call_args.args[2])
            tab.modified = tab.dirty = False
            window.close()

    def test_external_encoding_change_preserves_current_editor(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("Original", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            with patch.object(window, "compile_current"):
                window.open_file(source)
            tab = window.current_tab()
            assert tab is not None
            source.write_bytes(b"Changed \x81")

            with patch.object(window, "_watch_file"):
                window.reload_external_change(str(source))

            self.assertEqual(tab.editor.toPlainText(), "Original")
            self.assertIn("编码与 utf-8 不一致", window.statusBar().currentMessage())
            source.write_text("Original", encoding="utf-8")
            tab.modified = tab.dirty = False
            window.close()

    def test_corrupt_history_snapshot_does_not_replace_editor_text(self) -> None:
        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "snapshot.tex"
            snapshot.write_bytes(b"Corrupt \xff")
            window = MainWindow(settings_store=isolated_settings())
            editor = window._make_editor("Current paper")
            tab = EditorTab(editor=editor)
            window._add_tab(tab, "main.tex")

            with (
                patch(
                    "app.gui.insertion_actions.QMessageBox.question",
                    return_value=QMessageBox.StandardButton.Yes,
                ),
                patch("app.gui.insertion_actions.QMessageBox.warning") as warning,
            ):
                window.restore_history_snapshot(str(snapshot))

            self.assertEqual(editor.toPlainText(), "Current paper")
            self.assertIn("恢复失败", warning.call_args.args[1])
            tab.modified = tab.dirty = False
            window.close()

    def test_restored_history_marks_existing_pdf_as_stale(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.tex"
            pdf = root / "main.pdf"
            source.write_text("Current paper", encoding="utf-8")
            saved_history = create_snapshot(source, "Older paper", "saved")
            snapshot = saved_history.snapshot_path
            pdf.write_bytes(b"%PDF-1.4 current")
            window = MainWindow(settings_store=isolated_settings())
            editor = window._make_editor("Current paper")
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            record = window.pdf_state.record_for(source)
            record.last_successful_pdf = pdf
            record.freshness = PdfFreshness.CURRENT
            window._update_pdf_action_state()

            with patch(
                "app.gui.insertion_actions.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                window.restore_history_snapshot(str(snapshot))

            self.assertEqual(editor.toPlainText(), "Older paper")
            self.assertEqual(record.freshness, PdfFreshness.DIRTY)
            self.assertEqual(window.pdf_panel.freshness_label.text(), "源码已修改，PDF 待更新")
            self.assertEqual(editor.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth)
            tab.modified = tab.dirty = False
            window.close()

    def test_history_restore_is_one_undo_and_never_saves_or_compiles(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("saved bytes")
            history = create_snapshot(source, "older history", "saved")
            window = MainWindow(settings_store=isolated_settings())
            editor = window._make_editor("unsaved current draft")
            tab = EditorTab(editor=editor, path=source, modified=True, dirty=True)
            window._add_tab(tab, source.name)
            window.documents.schedule_save(tab, compile_after_save=True)
            with patch("app.gui.insertion_actions.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
                window.restore_history_snapshot(str(history.snapshot_path))
            self.assertEqual(editor.toPlainText(), "older history")
            self.assertTrue(editor.document().isUndoAvailable())
            self.assertFalse(tab.save_timer.isActive())
            self.assertFalse(tab.pending_compile_after_save)
            self.assertEqual(source.read_text(), "saved bytes")
            editor.undo()
            self.assertEqual(editor.toPlainText(), "unsaved current draft")
            editor.redo()
            self.assertEqual(editor.toPlainText(), "older history")
            window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
            window.close()

    def test_history_restore_rejects_unregistered_path(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("saved bytes")
            outside = Path(directory) / "not-history.tex"
            outside.write_text("not a registered history")
            window = MainWindow(settings_store=isolated_settings())
            editor = window._make_editor("current draft")
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            with patch("app.gui.insertion_actions.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), patch(
                    "app.gui.insertion_actions.QMessageBox.warning") as warning:
                window.restore_history_snapshot(str(outside))
            self.assertEqual(editor.toPlainText(), "current draft")
            self.assertTrue(warning.called)
            tab.modified = tab.dirty = False
            window.close()

    def test_history_confirmation_cannot_overwrite_newer_editor_or_history(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("saved bytes")
            history = create_snapshot(source, "older history", "saved")
            window = MainWindow(settings_store=isolated_settings())
            editor = window._make_editor("current draft")
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            def change_editor(*_args, **_kwargs):
                editor.setPlainText("newer input during confirmation")
                return QMessageBox.StandardButton.Yes
            with patch("app.gui.insertion_actions.QMessageBox.question", side_effect=change_editor), patch(
                    "app.gui.insertion_actions.QMessageBox.warning"):
                window.restore_history_snapshot(str(history.snapshot_path))
            self.assertEqual(editor.toPlainText(), "newer input during confirmation")
            window.documents.cancel_save_timer(tab)
            def change_history(*_args, **_kwargs):
                history.snapshot_path.write_text("changed valid UTF-8 history")
                return QMessageBox.StandardButton.Yes
            with patch("app.gui.insertion_actions.QMessageBox.question", side_effect=change_history), patch(
                    "app.gui.insertion_actions.QMessageBox.warning"):
                window.restore_history_snapshot(str(history.snapshot_path))
            self.assertEqual(editor.toPlainText(), "newer input during confirmation")
            self.assertEqual(source.read_text(), "saved bytes")
            tab.modified = tab.dirty = False
            window.close()

    def test_history_cancel_preserves_draft_undo_and_paused_save_request(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("disk original")
            history = create_snapshot(source, "older history", "saved")
            window = MainWindow(settings_store=isolated_settings())
            editor = window._make_editor("draft")
            tab = EditorTab(editor=editor, path=source, modified=True, dirty=True)
            window._add_tab(tab, source.name)
            editor.moveCursor(QTextCursor.MoveOperation.End)
            editor.insertPlainText(" plus edit")
            def cancel(*_args, **_kwargs):
                self.assertFalse(tab.save_timer.isActive())
                self.assertEqual(source.read_text(), "disk original")
                return QMessageBox.StandardButton.No
            with patch("app.gui.insertion_actions.QMessageBox.question", side_effect=cancel):
                window.restore_history_snapshot(str(history.snapshot_path))
            self.assertEqual(editor.toPlainText(), "draft plus edit")
            self.assertTrue(tab.save_timer.isActive())
            editor.undo()
            self.assertEqual(editor.toPlainText(), "draft")
            window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
            window.close()

    def test_history_confirmation_rejects_tab_switch_and_window_close(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("disk original")
            history = create_snapshot(source, "older history", "saved")
            window = MainWindow(settings_store=isolated_settings())
            editor = window._make_editor("first draft")
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            other = EditorTab(editor=window._make_editor("other draft"))
            window._add_tab(other, "other")
            window.editor_tabs.setCurrentWidget(editor)
            def switch(*_args, **_kwargs):
                window.editor_tabs.setCurrentWidget(other.editor)
                return QMessageBox.StandardButton.Yes
            with patch("app.gui.insertion_actions.QMessageBox.question", side_effect=switch), patch(
                    "app.gui.insertion_actions.QMessageBox.warning"):
                window.restore_history_snapshot(str(history.snapshot_path))
            self.assertEqual(editor.toPlainText(), "first draft")
            self.assertEqual(other.editor.toPlainText(), "other draft")
            window.editor_tabs.setCurrentWidget(editor)
            def close(*_args, **_kwargs):
                window.close()
                return QMessageBox.StandardButton.Yes
            with patch("app.gui.insertion_actions.QMessageBox.question", side_effect=close), patch(
                    "app.gui.insertion_actions.QMessageBox.warning") as warning:
                window.restore_history_snapshot(str(history.snapshot_path))
            self.assertFalse(warning.called)
            self.assertEqual(editor.toPlainText(), "first draft")
            self.assertEqual(source.read_text(), "disk original")

    def test_history_index_error_is_visible_and_does_not_break_source_save(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("disk original")
            history = create_snapshot(source, "older history", "saved")
            manifest = history.snapshot_path.parent / "manifest.json"
            manifest.write_bytes(b"malformed index")
            window = MainWindow(settings_store=isolated_settings())
            editor = window._make_editor("new saved source")
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            window.refresh_project_panels()
            self.assertIn("历史不可用", window.history_panel.status_label.text())
            self.assertFalse(window.history_panel.restore_button.isEnabled())
            with patch.object(window, "_watch_file"), patch.object(window, "create_compile_manager", return_value=None):
                self.assertTrue(window.documents.save_tab(tab, source))
            self.assertEqual(source.read_text(), "new saved source")
            self.assertEqual(manifest.read_bytes(), b"malformed index")
            tab.modified = tab.dirty = False
            window.close()

    def test_cancel_keeps_modified_tab_open(self) -> None:
        from shiboken6 import isValid

        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor("Draft")
        tab = EditorTab(editor=editor, modified=True, dirty=True)
        window._add_tab(tab, "未命名.tex")

        with patch(
            "app.gui.editor_tab_manager.QMessageBox.warning",
            return_value=QMessageBox.StandardButton.Cancel,
        ) as warning:
            window.close_tab(0)

        self.assertEqual(window.editor_tabs.count(), 1)
        self.assertIs(window.current_tab(), tab)
        app().sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertTrue(isValid(editor))
        self.assertEqual(editor.toPlainText(), "Draft")
        buttons = warning.call_args.args[3]
        self.assertTrue(buttons & QMessageBox.StandardButton.Save)
        self.assertTrue(buttons & QMessageBox.StandardButton.Discard)
        self.assertTrue(buttons & QMessageBox.StandardButton.Cancel)
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_cancel_aborts_window_close_before_cleanup(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor("Draft")
        tab = EditorTab(editor=editor, modified=True, dirty=True)
        window._add_tab(tab, "未命名.tex")
        event = QCloseEvent()

        with (
            patch(
                "app.gui.editor_tab_manager.QMessageBox.warning",
                return_value=QMessageBox.StandardButton.Cancel,
            ),
            patch.object(window.file_watcher, "stop") as stop_watcher,
        ):
            window.closeEvent(event)

        self.assertFalse(event.isAccepted())
        self.assertEqual(window.editor_tabs.count(), 1)
        stop_watcher.assert_not_called()
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_discard_closes_modified_tab_without_saving(self) -> None:
        from shiboken6 import isValid

        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor("Draft")
        tab = EditorTab(editor=editor, modified=True, dirty=True)
        window._add_tab(tab, "未命名.tex")

        with (
            patch(
                "app.gui.editor_tab_manager.QMessageBox.warning",
                return_value=QMessageBox.StandardButton.Discard,
            ),
            patch.object(window, "save_current_as") as save_current_as,
        ):
            window.close_tab(0)

        self.assertEqual(window.editor_tabs.count(), 0)
        save_current_as.assert_not_called()
        app().sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(isValid(editor))
        window.close()

    def test_late_cancel_keeps_all_tab_managers_running(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        first = EditorTab(
            editor=window._make_editor("First"),
            modified=True,
            dirty=True,
            manager=Mock(root_file=Path("/tmp/first.tex")),
        )
        second = EditorTab(
            editor=window._make_editor("Second"),
            modified=True,
            dirty=True,
            manager=Mock(root_file=Path("/tmp/second.tex")),
        )
        window._add_tab(first, "first.tex")
        window._add_tab(second, "second.tex")
        event = QCloseEvent()

        with patch(
            "app.gui.editor_tab_manager.QMessageBox.warning",
            side_effect=[
                QMessageBox.StandardButton.Discard,
                QMessageBox.StandardButton.Cancel,
            ],
        ):
            window.closeEvent(event)

        self.assertFalse(event.isAccepted())
        self.assertEqual(window.editor_tabs.count(), 2)
        first.manager.stop_current.assert_not_called()
        second.manager.stop_current.assert_not_called()
        first.modified = first.dirty = False
        second.modified = second.dirty = False
        first.manager = second.manager = None
        window.close()

    def test_insert_dialogs_smoke(self) -> None:
        dialogs = [
            FigureDialog(),
            FigureLayoutDialog(),
            TableDialog(),
            HyperlinkDialog(),
            ProjectWizardDialog(),
            BibEntryDialog(),
            BibImportDialog(),
            SettingsDialog(isolated_settings().load_preferences()),
        ]

        for dialog in dialogs:
            self.assertIsNotNone(dialog.windowTitle())
            dialog.close()

    def test_figure_layout_dialog_switches_layout_and_keeps_per_layout_widths(self) -> None:
        dialog = FigureLayoutDialog()

        vertical_index = dialog.layout_combo.findData(FigureLayout.VERTICAL.value)
        dialog.layout_combo.setCurrentIndex(vertical_index)
        self.assertEqual(dialog.values().layout, FigureLayout.VERTICAL)
        self.assertEqual(len(dialog.values().items), 2)
        self.assertEqual([item.width for item in dialog.values().items], [0.8, 0.8])
        self.assertTrue(dialog.item_groups[2].isHidden())

        grid_index = dialog.layout_combo.findData(FigureLayout.GRID_2X2.value)
        dialog.layout_combo.setCurrentIndex(grid_index)
        for index, edit in enumerate(dialog.image_edits):
            edit.setText(f"/tmp/{index}.png")
        for spin, width in zip(dialog.width_spins, (0.55, 0.40, 0.45, 0.50), strict=True):
            spin.setValue(width)
        values = dialog.values()

        self.assertEqual(values.layout, FigureLayout.GRID_2X2)
        self.assertEqual(len(values.items), 4)
        self.assertEqual([item.width for item in values.items], [0.55, 0.40, 0.45, 0.50])
        self.assertFalse(dialog.item_groups[3].isHidden())
        self.assertIn("上排 0.95", dialog.layout_hint.text())
        self.assertIn("不会拉伸变形", dialog.layout_hint.text())
        self.assertGreaterEqual(
            dialog.minimumWidth(),
            dialog.item_container.sizeHint().width() + 48,
        )
        self.assertLessEqual(dialog.item_scroll.height(), 300)
        dialog.close()

    def test_normal_mode_inserts_adjustable_grid_figure_layout(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.tex"
            source.write_text(
                "\\documentclass{article}\n\\begin{document}\n\\end{document}\n",
                encoding="utf-8",
            )
            image_paths = []
            for name in ("a.png", "b.png", "c.png", "d.png"):
                image = root / name
                image.write_bytes(b"image")
                image_paths.append(image)

            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            dialog = Mock()
            dialog.exec.return_value = QDialog.DialogCode.Accepted
            dialog.values.return_value = FigureLayoutSpec(
                layout=FigureLayout.GRID_2X2,
                items=tuple(
                    FigureLayoutItem(str(path), width, path.stem.upper())
                    for path, width in zip(
                        image_paths,
                        (0.55, 0.40, 0.45, 0.50),
                        strict=True,
                    )
                ),
                caption="Four panels",
                label="fig:grid",
            )

            with patch("app.gui.insertion_actions.FigureLayoutDialog", return_value=dialog):
                window.insert_side_by_side_figures()

            text = editor.toPlainText()
            self.assertEqual(text.count("\\begin{subfigure}"), 4)
            self.assertIn("\\begin{subfigure}{0.55\\textwidth}", text)
            self.assertIn("\\begin{subfigure}{0.4\\textwidth}", text)
            self.assertEqual(text.count("\\hfill"), 2)
            self.assertIn("\\par\\medskip", text)
            self.assertIn("\\usepackage{subcaption}", text)
            self.assertIn("\\label{fig:grid}", text)
            for image in image_paths:
                self.assertTrue((root / "figures" / image.name).is_file())
            tab.modified = tab.dirty = False
            window.close()

    def test_layout_asset_copy_rolls_back_partial_failure(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.tex"
            source.write_text("", encoding="utf-8")
            first = root / "first.png"
            second = root / "second.png"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            window = MainWindow(settings_store=isolated_settings())
            tab = EditorTab(editor=window._make_editor(""), path=source)

            def copy_then_fail(source_path: Path, destination: Path) -> None:
                if source_path == second:
                    raise OSError("simulated copy failure")
                destination.write_bytes(source_path.read_bytes())

            with (
                patch("app.gui.insertion_actions.copy_image_atomic", side_effect=copy_then_fail),
                patch("app.gui.insertion_actions.QMessageBox.warning") as warning,
            ):
                result = window.insertions.copy_image_assets(tab, [str(first), str(second)])

            self.assertIsNone(result)
            self.assertEqual(list((root / "figures").glob("*")), [])
            self.assertIn("已回滚新增图片", warning.call_args.args[2])
            window.close()

    def test_environment_doctor_dialog_smoke(self) -> None:
        from app.core.environment_doctor import build_environment_report

        report = build_environment_report(LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None))
        dialog = EnvironmentDoctorDialog(report)

        self.assertIn("环境诊断报告", dialog.report_view.toPlainText())
        dialog.close()

    def test_environment_doctor_dialog_copies_feedback_bundle(self) -> None:
        from app.core.environment_doctor import build_environment_report
        from app.gui.environment_doctor_dialog import FeedbackContext

        report = build_environment_report(LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None))
        provider = lambda: FeedbackContext(recent_log="compile log tail line", project_file="thesis.tex")
        dialog = EnvironmentDoctorDialog(report, feedback_context_provider=provider)

        dialog.feedback_button.click()

        clipboard_text = QApplication.clipboard().text()
        self.assertIn("反馈包", clipboard_text)
        self.assertIn("thesis.tex", clipboard_text)
        self.assertIn("compile log tail line", clipboard_text)
        self.assertEqual(dialog.feedback_button.text(), "已复制反馈包")
        dialog.close()

    def test_direct_feedback_action_copies_privacy_safe_bundle(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "SecretProject" / "main.tex"
            source.parent.mkdir()
            source.write_text("\\documentclass{article}\nPrivate paper text", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            window.log_view.setPlainText(
                f"Running: latexmk {source}\n"
                "l.42 Private paper text echoed by TeX"
            )

            window.feedback_bundle_action.trigger()

            bundle = QApplication.clipboard().text()
            self.assertIn("ICSTeX 反馈包", bundle)
            self.assertIn("main.tex", bundle)
            self.assertNotIn("SecretProject", bundle)
            self.assertNotIn("Private paper text", bundle)
            self.assertNotIn("Running: latexmk", bundle)
            self.assertIsNone(window._build_feedback_context(include_recent_log=False).recent_log)
            self.assertIn("原始编译日志", window.statusBar().currentMessage())
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_table_dialog_values_include_grid_content(self) -> None:
        dialog = TableDialog()
        dialog.preview_table.item(0, 0).setText("Mass")
        dialog.preview_table.item(0, 1).setText("Time")
        dialog.preview_table.item(1, 0).setText("1 kg")
        dialog.preview_table.item(1, 1).setText("2 s")

        values = dialog.values()

        self.assertEqual(values.headers[:2], ("Mass", "Time"))
        self.assertEqual(values.cells[0][:2], ("1 kg", "2 s"))
        dialog.close()

    def test_table_resize_preserves_blank_cells_and_has_no_sample_data(self):
        dialog = TableDialog()
        self.assertEqual(dialog._cell_text(1, 0), "")
        dialog.preview_table.item(1, 1).setText("data")
        dialog.columns_spin.setValue(4)
        self.assertEqual(dialog._cell_text(1, 0), "")
        self.assertEqual(dialog._cell_text(1, 1), "data")
        self.assertNotIn("Header", dialog.source_preview.toPlainText())
        self.assertNotIn("Cell", dialog.source_preview.toPlainText())
        dialog.close()

    def test_table_rectangle_paste_and_clear_are_single_undo(self):
        dialog = TableDialog()
        before = dialog.values()
        dialog.preview_table.setCurrentCell(1, 1)
        dialog.paste_clipboard_text("a\tb\n\t\nc\td")
        self.assertEqual(dialog._cell_text(1, 1), "a")
        self.assertEqual(dialog._cell_text(2, 1), "")
        self.assertEqual(dialog._cell_text(3, 2), "d")
        dialog.undo()
        self.assertEqual(dialog.values(), before)
        dialog.redo()
        self.assertEqual(dialog._cell_text(3, 2), "d")
        dialog.preview_table.selectAll()
        dialog.clear_selection()
        self.assertEqual(dialog._cell_text(3, 2), "")
        dialog.undo()
        self.assertEqual(dialog._cell_text(3, 2), "d")
        dialog.close()

    def test_table_shrink_cancel_and_undo_protect_data(self):
        dialog = TableDialog()
        dialog.preview_table.item(3, 2).setText("keep")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            dialog.rows_spin.setValue(1)
        self.assertEqual(dialog.rows_spin.value(), 3)
        self.assertEqual(dialog._cell_text(3, 2), "keep")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.rows_spin.setValue(1)
        self.assertEqual(dialog.rows_spin.value(), 1)
        dialog.undo()
        self.assertEqual(dialog._cell_text(3, 2), "keep")
        dialog.close()

    def test_table_oversize_paste_and_import_leave_draft_unchanged(self):
        dialog = TableDialog()
        before = dialog.values()
        dialog.paste_clipboard_text("\t".join(["x"] * 13))
        self.assertEqual(dialog.values(), before)
        dialog.load_spec(replace(before, columns=13))
        self.assertEqual(dialog.values(), before)
        self.assertIn("未导入", dialog.status_label.text())
        dialog.close()

    def test_table_import_is_undoable_and_empty_label_stays_empty(self):
        dialog = TableDialog()
        before = dialog.values()
        dialog.load_spec(replace(before, headers=("A", "B", "C"), label=""))
        dialog.undo()
        self.assertEqual(dialog.values(), before)
        dialog.redo()
        self.assertEqual(dialog.values().label, "")
        self.assertEqual(dialog._cell_text(0, 0), "A")
        dialog.close()

    def test_table_dialog_load_spec_fills_grid(self) -> None:
        from app.core.latex_insertions import parse_tabular, table_snippet

        spec = parse_tabular(
            table_snippet(
                replace(
                    TableDialog().values(),
                    rows=1,
                    columns=2,
                    headers=("Mass", "Time"),
                    cells=(("1 kg", "2 s"),),
                )
            )
        )
        dialog = TableDialog()
        dialog.load_spec(spec)

        self.assertEqual(dialog.columns_spin.value(), 2)
        self.assertEqual(dialog._cell_text(0, 0), "Mass")
        self.assertEqual(dialog._cell_text(1, 1), "2 s")
        dialog.close()

    def test_table_dialog_load_spec_from_delimited_paste(self) -> None:
        from app.core.latex_insertions import parse_delimited

        dialog = TableDialog()
        dialog.load_spec(parse_delimited("Name\tScore\nAlice\t90"))

        self.assertEqual(dialog.columns_spin.value(), 2)
        self.assertEqual(dialog._cell_text(0, 1), "Score")
        self.assertEqual(dialog._cell_text(1, 0), "Alice")
        dialog.close()

    def test_bib_import_dialog_online_checkbox_defaults_off(self) -> None:
        dialog = BibImportDialog()

        self.assertFalse(dialog.online())
        dialog.online_check.setChecked(True)
        self.assertTrue(dialog.online())
        dialog.close()

    def test_engine_selector_updates_current_engine(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        index = window.engine_selector.findData(LaTeXEngine.XELATEX.value)
        window.engine_selector.setCurrentIndex(index)

        self.assertEqual(window.current_engine, LaTeXEngine.XELATEX)
        self.assertTrue(window.engine_actions[LaTeXEngine.XELATEX].isChecked())
        window.close()

    def test_editor_soft_wrap_is_enabled_by_default(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        editor = window._make_editor("A very long line " * 40)

        self.assertTrue(editor.soft_wrap_enabled)
        self.assertEqual(editor.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth)
        window.close()

    def test_soft_wrap_preference_applies_to_open_editors(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        editor = window._make_editor("A very long line " * 40)
        tab = EditorTab(editor=editor)
        window._add_tab(tab, "Untitled.tex")

        window.apply_preferences(replace(window.preferences, soft_wrap=False))

        self.assertFalse(editor.soft_wrap_enabled)
        self.assertEqual(editor.lineWrapMode(), QPlainTextEdit.LineWrapMode.NoWrap)
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_generated_table_and_hyperlink_preserve_soft_wrap(self) -> None:
        from app.core.latex_insertions import (
            HYPERLINK_PACKAGES,
            TABLE_PACKAGES,
            HyperlinkSpec,
            TableSpec,
            hyperlink_snippet,
            table_snippet,
        )

        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor("\\documentclass{article}\n\\begin{document}\n\n\\end{document}\n")
        tab = EditorTab(editor=editor)
        window._add_tab(tab, "Untitled.tex")

        long_url = "https://example.com/" + "verylongsegment" * 40
        table = TableSpec(
            rows=2,
            columns=8,
            headers=tuple(f"VeryLongHeaderName{index}" for index in range(8)),
        )
        window.insertions.insert_snippet(
            tab,
            hyperlink_snippet(HyperlinkSpec(text="Long link", url=long_url)),
            HYPERLINK_PACKAGES,
            "link",
            block=False,
        )
        window.insertions.insert_snippet(tab, table_snippet(table), TABLE_PACKAGES, "table")

        QApplication.processEvents()
        self.assertTrue(editor.soft_wrap_enabled)
        self.assertEqual(editor.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.assertEqual(editor.horizontalScrollBar().maximum(), 0)
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_compile_manager_honors_magic_root_and_program_in_auto_mode(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "main.tex"
            chapter = root / "chapter.tex"
            main.write_text("\\documentclass{article}\n\\begin{document}\n\\input{chapter}\n\\end{document}", encoding="utf-8")
            chapter.write_text("% !TEX root = main.tex\n% !TEX program = xelatex\nText", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.current_engine = LaTeXEngine.AUTO

            manager = window.compile.create_manager(chapter)

            self.assertEqual(manager.root_file, main.resolve())
            self.assertEqual(manager.engine, LaTeXEngine.XELATEX)
            window.close()

    def test_manual_engine_selection_overrides_magic_program(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("% !TEX program = xelatex\n\\documentclass{article}", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.current_engine = LaTeXEngine.PDFLATEX

            manager = window.compile.create_manager(source)

            self.assertEqual(manager.engine, LaTeXEngine.PDFLATEX)
            window.close()

    def test_startup_without_latex_does_not_show_modal_warning(self) -> None:
        missing_toolchain = LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None)
        with patch("app.gui.main_window.detect_toolchain", return_value=missing_toolchain), patch.object(QMessageBox, "warning") as warning:
            window = MainWindow(settings_store=isolated_settings())

        warning.assert_not_called()
        self.assertIn("LaTeX 环境未就绪", window.statusBar().currentMessage())
        window.close()

    def test_compile_without_latex_warns_only_when_user_triggers_compile(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("\\begin{document}Hello\\end{document}", encoding="utf-8")
            missing_toolchain = LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None)
            window = MainWindow(settings_store=isolated_settings())
            window.toolchain = missing_toolchain
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            with patch.object(QMessageBox, "warning") as warning:
                window.compile_current(immediate=True)
                warning.assert_not_called()
                window.compile_current(immediate=True, show_missing_warning=True)

            warning.assert_called_once()
            window.close()

    def test_auto_compile_off_editor_change_does_not_schedule_compile(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("Original", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            with patch.object(window, "schedule_save") as schedule_save:
                editor.setPlainText("Changed")

            self.assertTrue(tab.modified)
            self.assertTrue(tab.dirty)
            schedule_save.assert_called_once()
            self.assertFalse(schedule_save.call_args.kwargs["compile_after_save"])
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_auto_compile_on_editor_change_schedules_compile_after_save(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("Original", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(True)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            with patch.object(window, "schedule_save") as schedule_save:
                editor.setPlainText("Changed")

            self.assertTrue(tab.modified)
            self.assertTrue(tab.dirty)
            schedule_save.assert_called_once()
            self.assertTrue(schedule_save.call_args.kwargs["compile_after_save"])
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_editor_change_waits_for_flush_before_saving(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("Original", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            editor.setPlainText("Changed")

            self.assertEqual(source.read_text(encoding="utf-8"), "Original")
            self.assertTrue(tab.modified)
            self.assertTrue(tab.dirty)
            self.assertIsNotNone(tab.save_timer)
            self.assertTrue(tab.save_timer.isActive())

            self.assertTrue(window.flush_pending_save(tab))
            self.assertEqual(source.read_text(encoding="utf-8"), "Changed")
            self.assertFalse(tab.modified)
            self.assertFalse(tab.dirty)
            window.close()

    def test_external_save_echo_does_not_reload_or_jump_to_top(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            text = "\n".join(f"Line {index}" for index in range(80))
            source.write_text(text, encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(text)
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            cursor = editor.textCursor()
            cursor.setPosition(len(text))
            editor.setTextCursor(cursor)

            with patch.object(window, "compile_current") as compile_current:
                window.reload_external_change(str(source))

            self.assertEqual(editor.textCursor().position(), len(text))
            compile_current.assert_not_called()
            window.close()

    def test_external_conflict_pauses_autosave_until_explicit_save_confirmation(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "main.tex"
            source.write_text("original", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window.save_debounce_ms = 60_000
            window.open_file(source)
            tab = window.current_tab()
            tab.editor.setPlainText("local change")
            source.write_text("external change", encoding="utf-8")
            window.reload_external_change(str(source))
            self.assertTrue(tab.external_conflict)
            self.assertFalse(tab.save_timer.isActive())
            self.assertFalse(window.flush_pending_save(tab))
            self.assertEqual(source.read_text(), "external change")
            self.assertEqual(tab.editor.toPlainText(), "local change")
            tab.editor.insertPlainText("more ")
            self.assertFalse(tab.save_timer.isActive())
            with patch("app.gui.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
                self.assertFalse(window.save_current())
            self.assertEqual(source.read_text(), "external change")
            with patch("app.gui.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), \
                 patch.object(window, "flush_pending_save", return_value=False):
                self.assertFalse(window.save_current())
            self.assertTrue(tab.external_conflict)
            tab.editor.insertPlainText("after failed save ")
            self.assertFalse(tab.save_timer.isActive())
            self.assertEqual(source.read_text(), "external change")
            with patch("app.gui.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
                self.assertTrue(window.save_current())
            self.assertFalse(tab.external_conflict)
            self.assertEqual(source.read_text(), tab.editor.toPlainText())
            window.close()

    def test_external_reload_preserves_cursor_position(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            text = "\n".join(f"Line {index}" for index in range(80))
            updated = text.replace("Line 20", "Changed 20")
            source.write_text(text, encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(text)
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            cursor = editor.textCursor()
            cursor.setPosition(len(text))
            editor.setTextCursor(cursor)
            source.write_text(updated, encoding="utf-8")

            with patch.object(window, "compile_current") as compile_current:
                window.reload_external_change(str(source))

            self.assertEqual(editor.toPlainText(), updated)
            self.assertEqual(editor.textCursor().position(), min(len(text), len(updated)))
            compile_current.assert_not_called()
            window.close()

    def test_external_edit_racing_own_save_is_not_silently_dropped(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            original = "Original"
            source.write_text(original, encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(original)
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            self.assertTrue(window._save_tab(tab, source))

            # A real external edit lands on disk within the same save-echo
            # window. It must not be silently discarded just because it is
            # close in time to our own save.
            raced_content = "Raced external edit"
            source.write_text(raced_content, encoding="utf-8")

            assert tab.manager is not None
            window.compile_authorized_roots.add(tab.manager.root_file)
            with patch.object(tab.manager, "schedule_compile") as schedule_compile:
                window.reload_external_change(str(source))

            self.assertEqual(editor.toPlainText(), raced_content)
            schedule_compile.assert_not_called()
            window.close()

    def test_external_change_requires_auto_toggle_and_session_authorization(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("original", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window._watch_file = lambda _path: None
            tab = EditorTab(editor=window._make_editor("original"), path=source)
            window._add_tab(tab, source.name)
            tab.manager = window.create_compile_manager(source)
            manager = tab.manager
            try:
                for index, (enabled, authorized) in enumerate(
                    ((False, False), (False, True), (True, False), (True, True))
                ):
                    window.auto_compile_action.setChecked(enabled)
                    window.compile_authorized_roots.clear()
                    if authorized:
                        window.compile_authorized_roots.add(manager.root_file)
                    source.write_text(f"external {index}", encoding="utf-8")
                    before = window.pdf_state.record_for(manager.root_file).source_revision
                    with patch.object(manager, "schedule_compile") as scheduled:
                        window.reload_external_change(str(source))
                        from tests.test_gui_dependencies import wait_until
                        self.assertTrue(wait_until(lambda: not window.dependencies.is_busy))
                    self.assertEqual(tab.editor.toPlainText(), f"external {index}")
                    self.assertEqual(scheduled.call_count, int(enabled and authorized))
                    self.assertGreater(window.pdf_state.record_for(manager.root_file).source_revision, before)
            finally:
                window.close()

    def test_disabling_auto_before_save_timer_fires_does_not_compile(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("original", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window._watch_file = lambda _path: None
            tab = EditorTab(editor=window._make_editor("original"), path=source)
            window._add_tab(tab, source.name)
            tab.manager = window.create_compile_manager(source)
            window.compile_authorized_roots.add(tab.manager.root_file)
            window.auto_compile_action.setChecked(True)
            tab.editor.insertPlainText("new ")
            window.auto_compile_action.setChecked(False)
            with patch.object(tab.manager, "compile_async") as compile_async:
                self.assertTrue(window.flush_pending_save(tab))
            compile_async.assert_not_called()
            self.assertEqual(source.read_text(encoding="utf-8"), tab.editor.toPlainText())
            window.close()

    def test_finished_compile_for_inactive_tab_does_not_override_pdf(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tex_a = root / "a.tex"
            tex_b = root / "b.tex"
            tex_a.write_text("A", encoding="utf-8")
            tex_b.write_text("B", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window._watch_file = lambda _path: None  # type: ignore[method-assign]

            tab_a = EditorTab(editor=window._make_editor("A"), path=tex_a)
            window._add_tab(tab_a, tex_a.name)
            tab_a.manager = window.create_compile_manager(tex_a)

            tab_b = EditorTab(editor=window._make_editor("B"), path=tex_b)
            window._add_tab(tab_b, tex_b.name)  # becomes the active tab

            self.assertIs(window.current_tab(), tab_b)

            tab_a.manager.output_dir.mkdir(parents=True, exist_ok=True)
            tab_a.manager.pdf_file.write_bytes(b"%PDF-1.4 A")
            stale_result = CompileResult(
                root_file=tab_a.manager.root_file,
                output_dir=tab_a.manager.output_dir,
                pdf_file=tab_a.manager.pdf_file,
                log_file=tab_a.manager.log_file,
                command=[],
                returncode=0,
                stdout="",
                stderr="",
                duration_seconds=0.1,
                outcome=CompileOutcome.SUCCESS,
                errors=[],
                build_id=1,
            )

            with patch.object(window.pdf_panel, "load_pdf") as load_pdf:
                window.compile.on_finished(stale_result)

            load_pdf.assert_not_called()
            # B has no successful PDF of its own; A's result must not enable export.
            self.assertFalse(window.export_pdf_action.isEnabled())
            window.close()

    def test_compile_current_refreshes_engine_from_magic_comment(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            original = "\\documentclass{article}\n\\begin{document}\nA\n\\end{document}\n"
            source.write_text(original, encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.toolchain = LaTeXToolchain(
                latexmk="/bin/latexmk", pdflatex="/bin/pdflatex", texcount=None, synctex=None
            )
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(original)
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            tab.manager = window.create_compile_manager(source)
            self.assertEqual(tab.manager.engine, LaTeXEngine.AUTO)

            # User adds a "% !TEX program" comment to an already-open
            # document and saves; this should pick a different engine the
            # very next time it compiles, without needing to reopen the file.
            updated = "% !TEX program = xelatex\n" + original
            editor.setPlainText(updated)

            with patch.object(tab.manager, "schedule_compile") as schedule_compile:
                window.compile_current()
                from tests.test_gui_dependencies import wait_until
                self.assertTrue(wait_until(lambda: schedule_compile.called))

            self.assertEqual(tab.manager.engine, LaTeXEngine.XELATEX)
            schedule_compile.assert_called_once()
            window.close()

    def test_enter_continues_item(self) -> None:
        editor = LaTeXEditor("\\begin{itemize}\n  \\item One")
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)

        editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "\r"))

        self.assertTrue(editor.toPlainText().endswith("\\item One\n  \\item "))

    def test_environment_completion_after_closing_brace(self) -> None:
        editor = LaTeXEditor("\\begin{equation")
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)

        editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_BraceRight, Qt.KeyboardModifier.NoModifier, "}"))

        self.assertEqual(editor.toPlainText(), "\\begin{equation}\n  \n\\end{equation}")

    def test_completion_enter_uses_popup_highlighted_row(self) -> None:
        editor = LaTeXEditor(r"\text")
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)
        editor.show()
        editor._show_completion_if_available()
        app().processEvents()

        popup = editor._completer.popup()
        completion_model = editor._completer.completionModel()
        textit_row = next(
            row
            for row in range(completion_model.rowCount())
            if completion_model.index(row, 0).data() == r"\textit{}"
        )
        popup.setCurrentIndex(completion_model.index(textit_row, 0))
        self.assertEqual(popup.currentIndex().data(), r"\textit{}")
        self.assertNotEqual(editor._completer.currentCompletion(), r"\textit{}")

        editor.keyPressEvent(
            QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Return,
                Qt.KeyboardModifier.NoModifier,
                "\r",
            )
        )

        self.assertEqual(editor.toPlainText(), r"\textit{}")
        editor.close()

    def test_textcolor_completion_inserts_template_and_focuses_color(self) -> None:
        editor = LaTeXEditor(r"\textc")
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)
        editor.show()
        editor._show_completion_if_available()
        app().processEvents()

        editor.keyPressEvent(
            QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Return,
                Qt.KeyboardModifier.NoModifier,
                "\r",
            )
        )

        self.assertEqual(editor.toPlainText(), r"\textcolor{}{}")
        self.assertEqual(editor.textCursor().position(), len(r"\textcolor{"))
        editor.close()

    def test_tab_expands_snippet(self) -> None:
        editor = LaTeXEditor("fig")
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)

        editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier, "\t"))

        self.assertIn("\\begin{figure}", editor.toPlainText())
        self.assertIn("\\includegraphics", editor.toPlainText())

    def test_insert_latex_snippet_moves_cursor(self) -> None:
        editor = LaTeXEditor("Hello")

        editor.insert_latex_snippet("\\begin{equation}\n  \n\\end{equation}", len("\\begin{equation}\n  "))

        self.assertIn("\\end{equation}", editor.toPlainText())
        self.assertEqual(editor.textCursor().position(), len("\\begin{equation}\n  "))

    def test_editor_drop_emits_image_paths_only_for_images(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "plot.png"
            text_file = root / "notes.txt"
            image.write_bytes(b"image")
            text_file.write_text("notes", encoding="utf-8")
            editor = LaTeXEditor()
            received: list[str] = []
            editor.imageDropped.connect(lambda paths: received.extend(paths))

            image_mime = QMimeData()
            image_mime.setUrls([QUrl.fromLocalFile(str(image))])
            image_event = QDropEvent(
                QPointF(1, 1),
                Qt.DropAction.CopyAction,
                image_mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            editor.dropEvent(image_event)

            text_mime = QMimeData()
            text_mime.setUrls([QUrl.fromLocalFile(str(text_file))])
            text_event = QDropEvent(
                QPointF(1, 1),
                Qt.DropAction.CopyAction,
                text_mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            editor.dropEvent(text_event)

        self.assertEqual(received, [str(image)])

    def test_generated_snippet_inserts_package_and_text(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        window.new_document()
        tab = window.current_tab()
        assert tab is not None

        window._insert_generated_snippet(
            tab,
            "\\href{https://example.com}{Example}",
            HYPERLINK_PACKAGES,
            "已插入超链接。",
            block=False,
        )

        text = tab.editor.toPlainText()
        self.assertIn("\\usepackage{hyperref}", text)
        self.assertIn("\\href{https://example.com}{Example}", text)
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_dropped_image_inserts_figure_and_copies_asset(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.tex"
            image = root / "raw image.png"
            source.write_text("\\documentclass{article}\n\\begin{document}\n\\end{document}\n", encoding="utf-8")
            image.write_bytes(b"image")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            window.insert_dropped_images([str(image)])
            self.assertTrue(
                wait_until(lambda: "\\includegraphics" in editor.toPlainText()),
                "drop import did not complete",
            )

            text = editor.toPlainText()
            # Already inside the project: reused without creating a copy.
            self.assertFalse((root / "figures").exists())
            self.assertIn("\\usepackage{graphicx}", text)
            self.assertIn("\\includegraphics[width=0.8\\textwidth]{raw image.png}", text)
            self.assertIn("\\caption{raw image}", text)
            self.assertIn("\\label{fig:raw_image}", text)
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_dropped_external_image_is_copied_into_figures(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            outside = Path(directory).parent / "external-source"
            outside.mkdir(exist_ok=True)
            image = outside / "plot.png"
            image.write_bytes(b"image")
            source = root / "main.tex"
            source.write_text("\\documentclass{article}\n\\begin{document}\n\\end{document}\n", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            window.insert_dropped_images([str(image)])
            self.assertTrue(
                wait_until(lambda: "\\includegraphics" in editor.toPlainText()),
                "drop import did not complete",
            )

            self.assertTrue((root / "figures" / "plot.png").exists())
            self.assertIn("{figures/plot.png}", editor.toPlainText())
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_dropped_images_insert_multiple_figures(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.tex"
            first = root / "first.png"
            second = root / "second.jpg"
            source.write_text("\\documentclass{article}\n\\begin{document}\n\\end{document}\n", encoding="utf-8")
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            window.insert_dropped_images([str(first), str(second)])
            self.assertTrue(
                wait_until(lambda: editor.toPlainText().count("\\begin{figure}") == 2),
                "drop import did not complete",
            )

            text = editor.toPlainText()
            self.assertEqual(text.count("\\begin{figure}"), 2)
            self.assertIn("{first.png}", text)
            self.assertIn("{second.jpg}", text)
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_dropped_images_roll_back_on_failure(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            outside = Path(directory).parent / "external-fail-source"
            outside.mkdir(exist_ok=True)
            good = outside / "good.png"
            good.write_bytes(b"good")
            missing = outside / "missing.png"
            source = root / "main.tex"
            source.write_text("\\documentclass{article}\n\\begin{document}\n\\end{document}\n", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            with patch("app.gui.insertion_actions.QMessageBox.warning") as warning:
                window.insert_dropped_images([str(good), str(missing)])
                self.assertTrue(
                    wait_until(lambda: warning.called),
                    "failure warning did not appear",
                )

            self.assertNotIn("\\begin{figure}", editor.toPlainText())
            self.assertFalse((root / "figures" / "good.png").exists())
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_dropped_image_requires_saved_document(self) -> None:
        with TemporaryDirectory() as directory:
            image = Path(directory) / "plot.png"
            image.write_bytes(b"image")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor("\\documentclass{article}\n\\begin{document}\n\\end{document}\n")
            tab = EditorTab(editor=editor)
            window._add_tab(tab, "Untitled.tex")

            with patch.object(QMessageBox, "information") as information:
                window.insert_dropped_images([str(image)])

            information.assert_called_once()
            self.assertNotIn("\\includegraphics", editor.toPlainText())
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_word_count_refresh_reads_unsaved_editor_text(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.toolchain = LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None)
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor("\\begin{document}Hello 42 world.\\end{document}")
        tab = EditorTab(editor=editor)
        window._add_tab(tab, "Untitled.tex")

        window.update_word_count()
        self.assertTrue(wait_until(lambda: not window.word_counts.is_busy))

        self.assertEqual(window.word_count_labels["effective"].text(), "2")
        self.assertEqual(window.word_count_labels["numbers"].text(), "1")
        self.assertIn("ICSTeX 结构化统计", window.word_count_meta.text())
        self.assertIn("未找到 TeXcount", window.word_count_meta.text())
        self.assertIn("当前编辑器内容", window.word_count_meta.text())
        self.assertEqual(window.word_count_view.last_mode_label, "ICSTeX 结构化统计")
        window.close()

    def test_word_count_uses_project_root_and_unsaved_child_buffer(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            child = Path(directory) / "child.tex"
            root.write_text(
                "\\documentclass{article}\n\\begin{document}Root.\\input{child}\\end{document}",
                encoding="utf-8",
            )
            child.write_text("Old disk text.", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.toolchain = LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None)
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor("Unsaved child buffer has five words.")
            tab = EditorTab(editor=editor, path=child, modified=True, dirty=True)
            window._add_tab(tab, child.name)

            window.update_word_count()
            self.assertTrue(wait_until(lambda: not window.word_counts.is_busy))

            self.assertEqual(window.word_count_labels["effective"].text(), "7")
            preview = window.word_count_view.preview_browser.toPlainText()
            self.assertIn("main.tex", preview)
            self.assertIn("child.tex", preview)
            self.assertIn("Unsaved child buffer has five words", preview)
            self.assertNotIn("Old disk text", preview)
            self.assertEqual(child.read_text(encoding="utf-8"), "Old disk text.")
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_feedback_context_includes_non_private_debug_metadata(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "main.tex"
            chapter = root / "chapter.tex"
            main.write_text("\\documentclass{article}\n\\begin{document}\n\\input{chapter}\n\\end{document}", encoding="utf-8")
            chapter.write_text("% !TEX root = main.tex\nBody", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.current_engine = LaTeXEngine.XELATEX
            editor = window._make_editor(chapter.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=chapter)
            window._add_tab(tab, chapter.name)
            # Set after _add_tab: tab activation now syncs the timer label to
            # the active root's record.
            window.compile_time_label.setText("上次编译 7.25s")
            window.word_count_view.last_mode_label = "TeXcount 兼容统计"

            context = window._build_feedback_context()

            # Tab registration now fixes the canonical buffer identity once.
            self.assertEqual(context.project_file, chapter.resolve())
            self.assertIsNotNone(context.metadata)
            assert context.metadata is not None
            self.assertEqual(Path(str(context.metadata.root_file)).name, "main.tex")
            self.assertEqual(context.metadata.root_source, "magic comment")
            self.assertEqual(context.metadata.selected_engine, "XeLaTeX")
            self.assertEqual(context.metadata.latest_compile_seconds, 7.25)
            self.assertEqual(context.metadata.word_count_mode, "TeXcount 兼容统计")
            window.close()

    def test_word_count_worker_does_not_block_gui_and_only_latest_pending_runs(self) -> None:
        from app.core.word_count import count_text
        entered = threading.Event()
        release = threading.Event()
        calls = []
        gui_thread = threading.get_ident()
        tools = LaTeXToolchain(None, None)

        def slow_count(text, **kwargs):
            calls.append((text, threading.get_ident()))
            if len(calls) == 1:
                entered.set()
                release.wait(3)
            return count_text(text, toolchain=tools)

        window = MainWindow(settings_store=isolated_settings())
        window.toolchain = tools
        editor = window._make_editor("old")
        tab = EditorTab(editor=editor)
        window._add_tab(tab, "Untitled")
        self.assertTrue(wait_until(lambda: not window.word_counts.is_busy))
        try:
            with patch("app.gui.word_count_controller.count_text", side_effect=slow_count):
                window.update_word_count(force=True)
                self.assertTrue(wait_until(entered.is_set))
                heartbeat = []
                QTimer.singleShot(0, lambda: heartbeat.append(True))
                self.assertTrue(wait_until(lambda: bool(heartbeat)))
                self.assertFalse(release.is_set())
                editor.setPlainText("middle revision")
                window.update_word_count()
                editor.setPlainText("newest has three")
                window.update_word_count()
                self.assertEqual(len(calls), 1)
                self.assertIsNotNone(window.word_counts._pending)
                self.assertIn("统计", window.word_count_meta.text())
                release.set()
                self.assertTrue(wait_until(lambda: not window.word_counts.is_busy))
                self.assertEqual([text for text, _ in calls], ["old", "newest has three"])
                self.assertTrue(all(thread != gui_thread for _, thread in calls))
                self.assertEqual(window.word_count_labels["effective"].text(), "3")
                window.update_word_count()
                self.assertEqual(len(calls), 2)
                window.update_word_count(force=True)
                self.assertTrue(wait_until(lambda: not window.word_counts.is_busy))
                self.assertEqual(len(calls), 3)
        finally:
            release.set()
            tab.dirty = tab.modified = False
            window.close()

    def test_word_count_disk_dependency_change_invalidates_cached_result(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            child = Path(directory) / "child.tex"
            root.write_text("\\begin{document}Root \\input{child}\\end{document}", encoding="utf-8")
            child.write_text("one", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.toolchain = LaTeXToolchain(None, None)
            window._watch_file = lambda _path: None
            window.open_file(root)
            try:
                window.update_word_count()
                self.assertTrue(wait_until(lambda: not window.word_counts.is_busy))
                self.assertEqual(window.word_count_labels["effective"].text(), "2")
                before = child.stat()
                child.write_text("a b", encoding="utf-8")
                os.utime(child, ns=(before.st_atime_ns, before.st_mtime_ns))
                window.update_word_count()
                self.assertTrue(wait_until(lambda: not window.word_counts.is_busy))
                self.assertEqual(window.word_count_labels["effective"].text(), "3")
            finally:
                window.close()

    def test_word_count_late_result_cannot_overwrite_other_tab_or_closed_window(self) -> None:
        from app.core.word_count import count_text
        entered = threading.Event()
        release = threading.Event()
        tools = LaTeXToolchain(None, None)

        def slow_count(text, **kwargs):
            if text == "old":
                entered.set()
                release.wait(3)
            return count_text(text, toolchain=tools)

        window = MainWindow(settings_store=isolated_settings())
        window.toolchain = tools
        tab = EditorTab(editor=window._make_editor("old"))
        window._add_tab(tab, "Old")
        self.assertTrue(wait_until(lambda: not window.word_counts.is_busy))
        try:
            with patch("app.gui.word_count_controller.count_text", side_effect=slow_count):
                window.update_word_count(force=True)
                self.assertTrue(wait_until(entered.is_set))
                other = EditorTab(editor=window._make_editor("new has three"))
                window._add_tab(other, "New")
                window.update_word_count()
                release.set()
                self.assertTrue(wait_until(lambda: not window.word_counts.is_busy))
                self.assertEqual(window.word_count_labels["effective"].text(), "3")
                entered.clear()
                release.clear()
                window.editor_tabs.setCurrentWidget(tab.editor)
                window.update_word_count(force=True)
                self.assertTrue(wait_until(entered.is_set))
                window.close()
                with patch.object(window.word_count_view, "set_result") as publish:
                    release.set()
                    wait_until(lambda: not any(t.name == "icstex-word-count" for t in threading.enumerate()))
                    QApplication.processEvents()
                publish.assert_not_called()
                self.assertFalse(window.word_counts.is_busy)
        finally:
            release.set()
            window.close()

    def test_refresh_project_panels_reads_labels_and_bib_keys(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bib").mkdir()
            source = root / "main.tex"
            source.write_text(
                "\\documentclass{article}\n\\begin{document}\n\\section{Intro}\n\\label{sec:intro}\\cite{Storm2024}\n\\end{document}\n",
                encoding="utf-8",
            )
            (root / "bib" / "references.bib").write_text("@article{Storm2024,\n  title = {Weather}\n}\n", encoding="utf-8")
            (root / "figures").mkdir()
            (root / "figures" / "plot.png").write_text("", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            window.refresh_project_panels()

            self.assertEqual(window.labels_panel.table.item(0, 0).text(), "sec:intro")
            self.assertEqual(window.references_panel.table.item(0, 0).text(), "Storm2024")
            self.assertTrue(window.references_panel.check_detail.isReadOnly())
            self.assertEqual(window.references_panel.health_table.editTriggers(),
                             QAbstractItemView.EditTrigger.NoEditTriggers)
            self.assertIn("快捷库", window.references_panel.status_label.text())
            self.assertEqual(window.outline_panel.table.item(0, 0).text(), "Intro")
            self.assertEqual(window.images_panel.table.item(0, 0).text(), "plot.png")
            self.assertEqual(editor._completion_labels, ["sec:intro"])
            self.assertEqual(editor._completion_citations, ["Storm2024"])
            window.close()

    def test_clean_build_cache_removes_current_build_dir(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("Original", encoding="utf-8")
            build_dir = source.parent / ".latex_build"
            build_dir.mkdir()
            (build_dir / "main.aux").write_text("", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            self.assertTrue(window.clean_build_cache())

            self.assertFalse(build_dir.exists())
            window.close()

    def test_clean_build_cache_refuses_while_worker_has_not_stopped(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("x", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            tab = EditorTab(editor=window._make_editor("x"), path=source)
            window._add_tab(tab, source.name)
            tab.manager = window.create_compile_manager(source)
            build_dir = tab.manager.output_dir
            build_dir.mkdir(parents=True)
            marker = build_dir / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            tab.manager._idle_event.clear()

            try:
                with patch.object(tab.manager, "stop_current", return_value=False), patch(
                    "app.gui.compile_controller.QMessageBox.warning"
                ) as warning, patch("app.gui.compile_controller.shutil.rmtree") as rmtree:
                    self.assertFalse(window.clean_build_cache())

                warning.assert_called_once()
                rmtree.assert_not_called()
                self.assertTrue(marker.exists())
            finally:
                tab.manager._idle_event.set()
                tab.modified = False
                tab.dirty = False
                window.close()

    def test_welcome_page_hides_when_document_opens_and_returns_when_closed(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        self.assertEqual(window.source_stack.currentWidget(), window.welcome_page)

        window.new_document()
        self.assertEqual(window.source_stack.currentWidget(), window.editor_tabs)

        tab = window.current_tab()
        assert tab is not None
        tab.modified = False
        tab.dirty = False
        window.close_tab(0)

        self.assertEqual(window.source_stack.currentWidget(), window.welcome_page)
        window.close()

    def test_project_check_and_fix_insert_missing_package(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.toolchain = LaTeXToolchain(latexmk="/bin/latexmk", pdflatex="/bin/pdflatex", texcount=None, synctex=None)
        editor = window._make_editor(
            "\\documentclass{article}\n\\begin{document}\n\\includegraphics{figures/a.png}\n\\end{document}\n"
        )
        tab = EditorTab(editor=editor)
        window._add_tab(tab, "Untitled.tex")

        diagnostics = window.run_project_check(switch_to_panel=False)
        fix_index = next(index for index, diagnostic in enumerate(diagnostics) if diagnostic.fix is not None)
        before = editor.toPlainText()
        window.fix_diagnostic(fix_index)

        self.assertIn("\\usepackage{graphicx}", editor.toPlainText())
        after = editor.toPlainText()
        editor.undo()
        self.assertEqual(editor.toPlainText(), before)
        editor.redo()
        self.assertEqual(editor.toPlainText(), after)
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_log_bridge_install_and_uninstall(self) -> None:
        import logging
        from app.gui.log_bridge import QtLogBridge

        bridge = QtLogBridge()
        logger_name = "icstex.test.log_bridge_smoke"
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()

        bridge.install_on(logger_name, level=logging.DEBUG)
        self.assertIn(bridge.handler, logger.handlers)
        self.assertLessEqual(logger.level, logging.DEBUG)

        received: list[str] = []
        bridge.messageEmitted.connect(lambda _name, _level, msg: received.append(msg))
        logger.info("hello from log bridge")
        QApplication.processEvents()
        self.assertTrue(any("hello from log bridge" in m for m in received))

        bridge.uninstall()
        self.assertNotIn(bridge.handler, logger.handlers)
        self.assertEqual(bridge._installed_loggers, [])


class GuiPdfStateTests(TestCase):
    """Root-scoped PDF freshness scenarios from the state-machine assignment."""

    def setUp(self) -> None:
        app()
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.window = MainWindow(settings_store=isolated_settings())
        self.window._watch_file = lambda _path: None  # type: ignore[method-assign]
        self.window.auto_compile_action.setChecked(False)
        self.addCleanup(self._close_window)

    def _close_window(self) -> None:
        for tab in self.window.tabs.values():
            tab.modified = False
            tab.dirty = False
        self.window.close()

    def _add_doc(self, name: str, text: str = "hello") -> EditorTab:
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        tab = EditorTab(editor=self.window._make_editor(text), path=path)
        self.window._add_tab(tab, path.name)
        tab.manager = self.window.create_compile_manager(path)
        return tab

    def _result(
        self,
        manager: CompileManager,
        outcome: CompileOutcome,
        build_id: int,
        *,
        returncode: int = 0,
        errors: list[LaTeXError] | None = None,
        stderr: str = "",
        purpose: BuildPurpose = BuildPurpose.FINAL,
        preview_asset_paths: tuple[Path, ...] = (),
    ) -> CompileResult:
        return CompileResult(
            root_file=manager.root_file,
            output_dir=manager.output_dir_for(purpose),
            pdf_file=manager.pdf_file_for(purpose),
            log_file=manager.log_file_for(purpose),
            command=[],
            returncode=returncode,
            stdout="",
            stderr=stderr,
            duration_seconds=0.1,
            outcome=outcome,
            errors=errors or [],
            build_id=build_id,
            purpose=purpose,
            preview_fidelity="proxy" if purpose is BuildPurpose.PREVIEW else None,
            preview_manifest_digest="digest" if purpose is BuildPurpose.PREVIEW else None,
            preview_asset_paths=preview_asset_paths,
        )

    def _begin_preview_owned_by(self, manager: CompileManager, build_id: int) -> None:
        with manager._lock:
            manager._active_purpose = BuildPurpose.PREVIEW
        self.window.compile._emit_started(manager, manager.root_file, build_id)

    def _late_preview_result(
        self,
        manager: CompileManager,
        build_id: int,
        asset: Path,
    ) -> CompileResult:
        pdf = manager.pdf_file_for(BuildPurpose.PREVIEW)
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(b"%PDF-1.4 late")
        return self._result(
            manager,
            CompileOutcome.SUCCESS,
            build_id,
            purpose=BuildPurpose.PREVIEW,
            preview_asset_paths=(asset,),
        )

    def _finish_success(self, tab: EditorTab, build_id: int, pdf_bytes: bytes = b"%PDF-1.4 x") -> Path:
        manager = tab.manager
        assert manager is not None
        manager.output_dir.mkdir(parents=True, exist_ok=True)
        manager.pdf_file.write_bytes(pdf_bytes)
        self.window.compile._emit_started(manager, manager.root_file, build_id)
        self.window.compile.on_finished(self._result(manager, CompileOutcome.SUCCESS, build_id))
        return manager.pdf_file

    def _banner(self) -> str:
        return self.window.pdf_panel.freshness_label.text()

    def test_closed_manager_late_signals_cannot_restore_state_or_watchers(self) -> None:
        tab = self._add_doc("close.tex")
        manager = tab.manager
        assert manager is not None
        asset = self.dir / "close.png"
        asset.write_bytes(b"image")
        self._begin_preview_owned_by(manager, 101)
        result = self._late_preview_result(manager, 101, asset)

        index = self.window._index_for_tab_id(id(tab.editor))
        self.window.close_tab(index)
        self.window.compile._emit_started(manager, manager.root_file, 102)
        self.window.compile.on_finished(result)

        self.assertNotIn(manager.root_file, self.window.compile_managers)
        self.assertNotIn(asset.resolve(), self.window.preview_asset_roots)
        self.assertFalse(self.window.preview_state.record_for(manager.root_file).has_valid_pdf)

    def test_save_as_manager_late_signals_cannot_restore_old_root(self) -> None:
        tab = self._add_doc("old.tex")
        manager = tab.manager
        assert manager is not None
        asset = self.dir / "old.png"
        asset.write_bytes(b"image")
        self._begin_preview_owned_by(manager, 111)
        result = self._late_preview_result(manager, 111, asset)

        new_path = self.dir / "new.tex"
        self.assertTrue(self.window.documents.save_tab(tab, new_path))
        self.window.compile._emit_started(manager, manager.root_file, 112)
        self.window.compile.on_finished(result)

        self.assertIsNot(tab.manager, manager)
        self.assertNotIn(manager.root_file, self.window.compile_managers)
        self.assertNotIn(asset.resolve(), self.window.preview_asset_roots)
        self.assertFalse(self.window.preview_state.record_for(manager.root_file).has_valid_pdf)

    def test_rebuilt_manager_late_signals_cannot_mutate_new_owner(self) -> None:
        tab = self._add_doc("rebuild.tex")
        manager = tab.manager
        assert manager is not None
        asset = self.dir / "rebuild.png"
        asset.write_bytes(b"image")
        self._begin_preview_owned_by(manager, 121)
        result = self._late_preview_result(manager, 121, asset)
        queued_key = (manager.root_file, 122)
        self.window.compile_build_owners[queued_key] = manager
        self.window.compile_purposes[queued_key] = BuildPurpose.PREVIEW

        self.window.compile.rebuild_managers()
        replacement = tab.manager
        assert replacement is not None
        # Simulate a started signal that was emitted before retirement but was
        # still queued in Qt until after the same-root replacement was created.
        self.window.compile.on_started(str(manager.root_file), 122)
        self.window.compile.on_finished(result)

        self.assertIsNot(replacement, manager)
        self.assertIs(self.window.compile_managers[manager.root_file], replacement)
        self.assertNotIn(asset.resolve(), self.window.preview_asset_roots)
        self.assertFalse(self.window.preview_state.record_for(manager.root_file).has_valid_pdf)
        self.assertIsNot(
            self.window.preview_state.record_for(manager.root_file).freshness,
            PreviewFreshness.COMPILING,
        )
        self.assertNotIn(manager.root_file, self.window.compile_active_builds)
        self.assertNotIn(manager.root_file, self.window.compile_start_times)
        self.assertFalse(self.window.stop_compile_action.isEnabled())
        self.assertFalse(self.window.compile_progress.isVisible())

    def test_success_then_edit_keeps_pdf_and_shows_dirty(self) -> None:
        tab = self._add_doc("a.tex")
        pdf = self._finish_success(tab, 1)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)
        self.assertEqual(self._banner(), "PDF 已是最新")
        self.assertTrue(self.window.export_pdf_action.isEnabled())

        tab.editor.insertPlainText("more text")

        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)
        self.assertEqual(self._banner(), "源码已修改，PDF 待更新")
        self.assertTrue(self.window.export_pdf_action.isEnabled())

    def test_new_revision_reloads_same_pdf_path_with_root_logical_key(self) -> None:
        tab = self._add_doc("a.tex")
        pdf = self._finish_success(tab, 1)
        manager = tab.manager
        assert manager is not None

        tab.editor.insertPlainText("new revision")
        with patch.object(self.window.pdf_panel, "load_pdf") as load_pdf:
            self._finish_success(tab, 2, b"%PDF-1.4 updated")

        load_pdf.assert_called_once_with(pdf, logical_key=manager.root_file)

    def test_displayed_final_banner_ignores_non_displayed_preview_failure(self) -> None:
        tab = self._add_doc("a.tex")
        self._finish_success(tab, 1)
        manager = tab.manager
        assert manager is not None

        self.window.preview_state.record_failed_attempt(manager.root_file)
        self.window._update_pdf_action_state()

        displayed = self.window.displayed_pdfs[manager.root_file]
        self.assertIs(displayed.purpose, BuildPurpose.FINAL)
        self.assertEqual(self._banner(), "PDF 已是最新")

    def test_failed_stale_preview_banner_preserves_failure_semantics(self) -> None:
        tab = self._add_doc("a.tex")
        manager = tab.manager
        assert manager is not None
        preview_pdf = manager.pdf_file_for(BuildPurpose.PREVIEW)
        preview_pdf.parent.mkdir(parents=True, exist_ok=True)
        preview_pdf.write_bytes(b"%PDF-1.4 preview")

        self.window.preview_state.begin_build(manager.root_file, 1)
        self.window.preview_state.finish_build(
            manager.root_file,
            1,
            success=True,
            pdf_file=preview_pdf,
            fidelity="proxy",
            manifest_digest="digest",
        )
        self.window.preview_state.mark_edited(manager.root_file)
        self.window.preview_state.begin_build(manager.root_file, 2)
        self.window.preview_state.finish_build(manager.root_file, 2, success=False)
        self.window._sync_pdf_panel_to_active_root()

        displayed = self.window.displayed_pdfs[manager.root_file]
        self.assertIs(displayed.purpose, BuildPurpose.PREVIEW)
        self.assertEqual(self._banner(), "预览失败，当前显示上次成功版本")

    def test_failure_after_success_keeps_old_pdf_with_stale_warning(self) -> None:
        tab = self._add_doc("a.tex")
        pdf = self._finish_success(tab, 1)
        manager = tab.manager
        assert manager is not None

        self.window.compile._emit_started(manager, manager.root_file, 2)
        self.window.compile.on_finished(
            self._result(manager, CompileOutcome.LATEX_ERROR, 2, returncode=1)
        )

        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)
        self.assertEqual(self._banner(), "编译未成功，当前显示上次成功版本")
        self.assertTrue(self.window.export_pdf_action.isEnabled())

    def test_stop_after_success_keeps_old_pdf_with_stale_warning(self) -> None:
        tab = self._add_doc("a.tex")
        pdf = self._finish_success(tab, 1)
        manager = tab.manager
        assert manager is not None

        self.window.compile._emit_started(manager, manager.root_file, 2)
        self.window.compile.on_finished(
            self._result(manager, CompileOutcome.STOPPED, 2, returncode=3)
        )

        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)
        self.assertEqual(self._banner(), "编译未成功，当前显示上次成功版本")
        self.assertIn("编译已停止", self.window.log_view.toPlainText())

    def test_first_compile_failure_shows_empty_panel_and_no_pdf(self) -> None:
        tab = self._add_doc("a.tex")
        manager = tab.manager
        assert manager is not None

        self.window.compile._emit_started(manager, manager.root_file, 1)
        self.window.compile.on_finished(
            self._result(manager, CompileOutcome.LATEX_ERROR, 1, returncode=1)
        )

        self.assertIsNone(self.window.pdf_panel.current_pdf)
        self.assertEqual(self._banner(), "编译未成功，暂无可用 PDF")
        self.assertFalse(self.window.export_pdf_action.isEnabled())
        self.assertFalse(self.window.export_pdf())

    def test_background_build_does_not_touch_active_tab_widgets(self) -> None:
        tab_a = self._add_doc("a.tex")
        self._add_doc("b.tex")  # active tab, uncompiled

        manager = tab_a.manager
        assert manager is not None
        manager.output_dir.mkdir(parents=True, exist_ok=True)
        manager.pdf_file.write_bytes(b"%PDF-1.4 A")
        with patch.object(self.window.pdf_panel, "load_pdf") as load_pdf:
            self.window.compile._emit_started(manager, manager.root_file, 1)
            self.window.compile.on_finished(
                self._result(manager, CompileOutcome.SUCCESS, 1)
            )

        load_pdf.assert_not_called()
        self.assertEqual(self._banner(), "尚未编译")
        self.assertFalse(self.window.export_pdf_action.isEnabled())

    def test_switch_to_uncompiled_tab_clears_viewer_and_blocks_export(self) -> None:
        tab_a = self._add_doc("a.tex")
        pdf_a = self._finish_success(tab_a, 1)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf_a)

        self._add_doc("b.tex")  # becomes active; has no build

        self.assertIsNone(self.window.pdf_panel.current_pdf)
        if self.window.pdf_panel._document is not None:
            self.assertIs(
                self.window.pdf_panel._stack.currentWidget(), self.window.pdf_panel._empty_state
            )
        self.assertEqual(self._banner(), "尚未编译")
        self.assertFalse(self.window.export_pdf_action.isEnabled())
        self.assertFalse(self.window.pdf_panel.export_pdf_button.isEnabled())
        with patch("app.gui.main_window.QFileDialog.getSaveFileName") as dialog:
            self.assertFalse(self.window.export_pdf())
        dialog.assert_not_called()

    def test_each_tab_loads_and_prepares_only_its_own_pdf(self) -> None:
        tab_a = self._add_doc("a.tex")
        pdf_a = self._finish_success(tab_a, 1, b"%PDF-1.4 AAA")
        tab_b = self._add_doc("b.tex")
        pdf_b = self._finish_success(tab_b, 2, b"%PDF-1.4 BBB")
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf_b)

        index_a = self.window._index_for_tab_id(id(tab_a.editor))
        self.window.editor_tabs.setCurrentIndex(index_a)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf_a)
        reviewed = []
        def inspect(window):
            request = window.readiness.capture_request()
            reviewed.append((request.root, request.final.last_successful_pdf))
            return None  # No confirmed delivery from this synthetic record.
        with patch("app.gui.submission_delivery_dialog.show_submission_delivery", side_effect=inspect):
            self.assertFalse(self.window.export_pdf())
        self.assertEqual(reviewed[-1], (tab_a.path.resolve(), pdf_a))

        index_b = self.window._index_for_tab_id(id(tab_b.editor))
        self.window.editor_tabs.setCurrentIndex(index_b)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf_b)
        with patch("app.gui.submission_delivery_dialog.show_submission_delivery", side_effect=inspect):
            self.assertFalse(self.window.export_pdf())
        self.assertEqual(reviewed[-1], (tab_b.path.resolve(), pdf_b))
        self.assertEqual(pdf_a.read_bytes(), b"%PDF-1.4 AAA")
        self.assertEqual(pdf_b.read_bytes(), b"%PDF-1.4 BBB")
        self.assertFalse((self.dir / "out-a.pdf").exists())
        self.assertFalse((self.dir / "out-b.pdf").exists())

    def test_child_tabs_share_root_record_and_dirty_it(self) -> None:
        root_tab = self._add_doc("main.tex", "\\documentclass{article}\n\\input{child}\n\\input{part}\n")
        pdf = self._finish_success(root_tab, 1)
        root = root_tab.manager.root_file

        # Magic-root child shares the record: opening it keeps the root's PDF.
        child_path = self.dir / "child.tex"
        child_path.write_text("% !TEX root = main.tex\ntext", encoding="utf-8")
        child_tab = EditorTab(editor=self.window._make_editor("% !TEX root = main.tex\ntext"), path=child_path)
        self.window._add_tab(child_tab, child_path.name)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)
        self.assertEqual(self._banner(), "PDF 已是最新")

        child_tab.editor.insertPlainText("edited ")
        record = self.window.pdf_state.record_for(root)
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)
        self.assertEqual(self._banner(), "源码已修改，PDF 待更新")

        # \input child without a magic comment still dirties the known root record.
        self._finish_success(root_tab, 2)
        part_path = self.dir / "part.tex"
        part_path.write_text("part text", encoding="utf-8")
        part_tab = EditorTab(editor=self.window._make_editor("part text"), path=part_path)
        self.window._add_tab(part_tab, part_path.name)
        part_tab.editor.insertPlainText("more ")
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)

    def test_edit_during_build_never_shows_current(self) -> None:
        tab = self._add_doc("a.tex")
        manager = tab.manager
        assert manager is not None
        self.window.compile._emit_started(manager, manager.root_file, 1)
        self.assertEqual(self._banner(), "正在编译…")

        tab.editor.insertPlainText("edited during build")

        manager.output_dir.mkdir(parents=True, exist_ok=True)
        manager.pdf_file.write_bytes(b"%PDF-1.4 x")
        self.window.compile.on_finished(self._result(manager, CompileOutcome.SUCCESS, 1))

        self.assertEqual(self.window.pdf_panel.current_pdf, manager.pdf_file)
        self.assertEqual(self._banner(), "源码已修改，PDF 待更新")

    def test_late_result_from_older_build_is_ignored(self) -> None:
        tab = self._add_doc("a.tex")
        manager = tab.manager
        assert manager is not None
        pdf = self._finish_success(tab, 2)

        old_pdf = self.dir / "old.pdf"
        old_pdf.write_bytes(b"%PDF-1.4 old")
        stale = CompileResult(
            root_file=manager.root_file,
            output_dir=manager.output_dir,
            pdf_file=old_pdf,
            log_file=manager.log_file,
            command=[],
            returncode=0,
            stdout="",
            stderr="",
            duration_seconds=0.1,
            outcome=CompileOutcome.SUCCESS,
            errors=[],
            build_id=1,
        )
        with patch.object(self.window.pdf_panel, "load_pdf") as load_pdf:
            self.window.compile.on_finished(stale)

        load_pdf.assert_not_called()
        record = self.window.pdf_state.record_for(manager.root_file)
        self.assertEqual(record.last_successful_pdf, pdf)
        self.assertEqual(record.freshness, PdfFreshness.CURRENT)

    def test_clean_cache_clears_viewer_and_disables_actions(self) -> None:
        tab = self._add_doc("a.tex")
        self._finish_success(tab, 1)
        self.assertTrue(self.window.export_pdf_action.isEnabled())

        self.assertTrue(self.window.clean_build_cache())

        self.assertIsNone(self.window.pdf_panel.current_pdf)
        self.assertEqual(self._banner(), "尚未编译")
        self.assertFalse(self.window.export_pdf_action.isEnabled())
        self.assertFalse(self.window.pdf_panel.export_pdf_button.isEnabled())

    def test_legacy_copy_controller_failure_leaves_no_partial_files(self) -> None:
        tab = self._add_doc("a.tex")
        self._finish_success(tab, 1)
        target = self.dir / "exported.pdf"

        # Internal compatibility helper, not the reviewed user-facing entrance.
        with patch("app.gui.pdf_export_controller.shutil.copy2", side_effect=OSError("disk full")), patch(
            "app.gui.main_window.QMessageBox.warning"
        ) as warning:
            self.assertFalse(self.window.pdf_export.request_export(tab.path, target))

        warning.assert_called_once()
        self.assertFalse(target.exists())
        self.assertEqual(list(self.dir.glob("*.part")), [])
        self.assertEqual(list(self.dir.glob("*.pdf.part")), [])

    def test_log_headline_matches_outcome_and_leads_with_first_error(self) -> None:
        tab = self._add_doc("a.tex")
        manager = tab.manager
        assert manager is not None
        footer = "Latexmk: Errors, so did not complete cycle"
        self.window.compile._emit_started(manager, manager.root_file, 1)
        self.window.compile.on_finished(
            self._result(
                manager,
                CompileOutcome.LATEX_ERROR,
                1,
                returncode=12,
                stderr=footer,
                errors=[LaTeXError(message="Undefined control sequence \\foo", line=3)],
            )
        )

        log_text = self.window.log_view.toPlainText()
        self.assertIn("编译失败：", log_text)
        headline_index = log_text.index("编译失败：")
        footer_index = log_text.index("Latexmk")
        self.assertLess(headline_index, footer_index)
        first_line = next(line for line in log_text.splitlines() if line.startswith("编译失败："))
        self.assertNotIn("Latexmk", first_line)

    def test_lua_font_loader_failure_is_visible_without_source_fix_or_current_pdf(self) -> None:
        from app.core.log_parser import parse_latex_errors

        source = "\\documentclass{article}\n\\begin{document}\nSynthetic text.\n\\end{document}\n"
        tab = self._add_doc("lua.tex", source)
        manager = tab.manager
        self._finish_success(tab, 1)
        before = (tab.editor.textCursor().position(), tab.editor.verticalScrollBar().value())
        output = ('luaotfload | load : FATAL ERROR\n'
                  'luaotfload | load : Failed to load "luaotfload" module "multiscript".\n')
        self.window.compile._emit_started(manager, manager.root_file, 2)
        self.window.compile.on_finished(self._result(
            manager, CompileOutcome.LATEX_ERROR, 2, returncode=12,
            errors=parse_latex_errors(output), stderr=output,
        ))
        panel = self.window.diagnostic_panel
        self.assertEqual(len(panel.diagnostics), 1)
        self.assertEqual(panel.table.item(0, 1).text(), "LuaLaTeX 字体组件失败")
        self.assertFalse(panel.fix_button.isEnabled())
        self.assertIsNone(panel.diagnostics[0].file)
        self.assertIsNone(panel.diagnostics[0].line)
        self.assertIs(self.window.bottom_tabs.currentWidget(), panel)
        # The menu remains available to open M5's review, not to publish an old PDF.
        self.assertNotEqual(self.window.pdf_state.record_for(manager.root_file).freshness, PdfFreshness.CURRENT)
        self.assertEqual(tab.path.read_text(encoding="utf-8"), source)
        self.assertEqual(tab.editor.toPlainText(), source)
        self.assertEqual((tab.editor.textCursor().position(), tab.editor.verticalScrollBar().value()), before)

    def test_missing_toolchain_compile_updates_active_root_state(self) -> None:
        tab = self._add_doc("a.tex")
        self.window.toolchain = LaTeXToolchain(
            latexmk=None, pdflatex=None, texcount=None, synctex=None
        )
        self.window.compile_current()
        record = self.window.pdf_state.record_for(tab.manager.root_file)
        self.assertEqual(record.last_outcome, CompileOutcome.TOOLCHAIN_MISSING)
        self.assertEqual(self._banner(), "编译未成功，暂无可用 PDF")
        self.assertFalse(self.window.export_pdf_action.isEnabled())

    def test_external_reload_marks_pdf_dirty_immediately(self) -> None:
        tab = self._add_doc("a.tex", "original")
        pdf = self._finish_success(tab, 1)
        self.assertEqual(self._banner(), "PDF 已是最新")

        assert tab.path is not None and tab.manager is not None
        tab.path.write_text("changed on disk", encoding="utf-8")
        with patch.object(tab.manager, "schedule_compile"):
            self.window.reload_external_change(str(tab.path))

        self.assertEqual(tab.editor.toPlainText(), "changed on disk")
        self.assertEqual(self._banner(), "源码已修改，PDF 待更新")
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)
        record = self.window.pdf_state.record_for(tab.manager.root_file)
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)

    def test_background_build_does_not_touch_compile_indicators(self) -> None:
        tab_a = self._add_doc("a.tex")
        self._add_doc("b.tex")  # active
        manager = tab_a.manager
        assert manager is not None

        self.window.compile._emit_started(manager, manager.root_file, 1)

        self.assertIsNone(self.window.compile_started_at)
        self.assertFalse(self.window.stop_compile_action.isEnabled())
        self.assertFalse(self.window.compile_timer.isActive())
        self.assertNotIn("正在", self.window.statusBar().currentMessage())
        self.assertEqual(self.window.compile_time_label.text(), "空闲")

        manager.output_dir.mkdir(parents=True, exist_ok=True)
        manager.pdf_file.write_bytes(b"%PDF-1.4 A")
        self.window.compile.on_finished(self._result(manager, CompileOutcome.SUCCESS, 1))
        self.assertEqual(self.window.compile_time_label.text(), "空闲")

    def test_compile_indicators_follow_active_tab(self) -> None:
        tab_a = self._add_doc("a.tex")
        tab_b = self._add_doc("b.tex")  # active
        manager_b = tab_b.manager
        assert manager_b is not None

        self.window.compile._emit_started(manager_b, manager_b.root_file, 1)
        self.assertTrue(self.window.stop_compile_action.isEnabled())
        self.assertIsNotNone(self.window.compile_started_at)

        self.window.editor_tabs.setCurrentIndex(self.window._index_for_tab_id(id(tab_a.editor)))
        self.assertFalse(self.window.stop_compile_action.isEnabled())
        self.assertIsNone(self.window.compile_started_at)

        self.window.editor_tabs.setCurrentIndex(self.window._index_for_tab_id(id(tab_b.editor)))
        self.assertTrue(self.window.stop_compile_action.isEnabled())
        self.assertIsNotNone(self.window.compile_started_at)

        manager_b.output_dir.mkdir(parents=True, exist_ok=True)
        manager_b.pdf_file.write_bytes(b"%PDF-1.4 B")
        self.window.compile.on_finished(self._result(manager_b, CompileOutcome.SUCCESS, 1))
        self.assertFalse(self.window.stop_compile_action.isEnabled())

    def test_root_and_child_share_one_compile_manager(self) -> None:
        main = self.dir / "main.tex"
        main.write_text("\\documentclass{article}\n\\input{child}\n", encoding="utf-8")
        child = self.dir / "child.tex"
        child.write_text("% !TEX root = main.tex\ntext", encoding="utf-8")

        manager_main = self.window.create_compile_manager(main)
        manager_child = self.window.create_compile_manager(child)

        self.assertIs(manager_main, manager_child)
        self.assertEqual(manager_main.root_file, main.resolve())

    def test_plain_input_child_shares_parent_compile_manager(self) -> None:
        main = self.dir / "main.tex"
        main.write_text("\\documentclass{article}\n\\begin{document}\n\\input{child}\n\\end{document}", encoding="utf-8")
        child = self.dir / "child.tex"
        child.write_text("text without magic root", encoding="utf-8")

        manager_main = self.window.create_compile_manager(main)
        manager_child = self.window.create_compile_manager(child)

        self.assertIs(manager_main, manager_child)
        self.assertEqual(manager_child.root_file, main.resolve())

    def test_closing_child_tab_keeps_shared_manager_running(self) -> None:
        main_tab = self._add_doc("main.tex", "\\documentclass{article}\n\\input{child}\n")
        child_path = self.dir / "child.tex"
        child_path.write_text("% !TEX root = main.tex\ntext", encoding="utf-8")
        child_tab = EditorTab(editor=self.window._make_editor("text"), path=child_path)
        self.window._add_tab(child_tab, child_path.name)
        child_tab.manager = self.window.create_compile_manager(child_path)
        self.assertIs(child_tab.manager, main_tab.manager)

        manager = main_tab.manager
        assert manager is not None
        with patch.object(manager, "stop_current") as stop_current:
            self.window.close_tab(self.window._index_for_tab_id(id(child_tab.editor)))
            stop_current.assert_not_called()
            self.assertIn(manager.root_file, self.window.compile_managers)
            self.window.close_tab(self.window._index_for_tab_id(id(main_tab.editor)))
            stop_current.assert_called_once()
        self.assertNotIn(manager.root_file, self.window.compile_managers)

    def test_clean_cache_invalidates_in_flight_result(self) -> None:
        tab = self._add_doc("a.tex")
        manager = tab.manager
        assert manager is not None
        self._finish_success(tab, 1)

        self.window.compile._emit_started(manager, manager.root_file, 2)
        self.assertTrue(self.window.clean_build_cache())
        self.assertEqual(self._banner(), "尚未编译")

        self.window.compile.on_finished(
            self._result(manager, CompileOutcome.STOPPED, 2, returncode=-15)
        )

        record = self.window.pdf_state.record_for(manager.root_file)
        self.assertEqual(record.freshness, PdfFreshness.UNCOMPILED)
        self.assertEqual(self._banner(), "尚未编译")
        self.assertFalse(self.window.export_pdf_action.isEnabled())

    def test_save_as_rebinds_pdf_state_to_new_root(self) -> None:
        tab = self._add_doc("a.tex")
        old_manager = tab.manager
        assert old_manager is not None
        pdf_a = self._finish_success(tab, 1)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf_a)

        new_path = self.dir / "renamed.tex"
        with patch(
            "app.gui.main_window.QFileDialog.getSaveFileName",
            return_value=(str(new_path), ""),
        ):
            self.assertTrue(self.window.save_current_as())

        self.assertEqual(tab.path, new_path.resolve())
        self.assertIsNot(tab.manager, old_manager)
        self.assertNotIn(old_manager.root_file, self.window.compile_managers)
        self.assertIsNone(self.window.pdf_panel.current_pdf)
        self.assertEqual(self._banner(), "尚未编译")
        self.assertFalse(self.window.export_pdf_action.isEnabled())
        with patch("app.gui.main_window.QFileDialog.getSaveFileName") as dialog:
            self.assertFalse(self.window.export_pdf())
        dialog.assert_not_called()

    def test_deep_nested_child_edit_marks_root_dirty(self) -> None:
        (self.dir / "chapters").mkdir()
        root_tab = self._add_doc("main.tex", "\\documentclass{article}\n\\input{chapters/ch1}\n")
        chapter = self.dir / "chapters" / "ch1.tex"
        chapter.write_text("\\input{sec1}", encoding="utf-8")
        section = self.dir / "chapters" / "sec1.tex"
        section.write_text("deep text", encoding="utf-8")
        # A successful compile now follows a completed graph preflight. Keep
        # this fixture's injected success consistent with that real boundary.
        from tests.test_gui_dependencies import wait_until
        self.window.dependencies.refresh_memberships(force=True)
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        self._finish_success(root_tab, 1)
        root = root_tab.manager.root_file

        section_tab = EditorTab(editor=self.window._make_editor("deep text"), path=section)
        self.window._add_tab(section_tab, section.name)
        section_tab.editor.insertPlainText("edited ")

        record = self.window.pdf_state.record_for(root)
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)

    def test_synctex_never_falls_back_to_foreign_pdf(self) -> None:
        tab_a = self._add_doc("a.tex")
        pdf_a = self._finish_success(tab_a, 1)
        self._add_doc("b.tex")  # active, uncompiled

        # Even a stale viewer path must not drive SyncTeX for another root.
        self.window.pdf_panel.current_pdf = pdf_a
        with patch("app.gui.main_window.pdf_to_source") as pdf_to_source:
            self.window.sync_pdf_to_source(1, 10.0, 10.0)
        pdf_to_source.assert_not_called()

    def test_reveal_pdf_failure_shows_hint_instead_of_raising(self) -> None:
        tab = self._add_doc("a.tex")
        self._finish_success(tab, 1)

        with patch(
            "app.gui.main_window.subprocess.Popen", side_effect=OSError("no file manager")
        ), patch("app.gui.main_window.QDesktopServices.openUrl", return_value=False):
            self.window.reveal_pdf()  # must not raise

        self.assertIn("无法打开文件管理器", self.window.log_view.toPlainText())


class FormulaSourceTargetTests(TestCase):
    def setUp(self):
        self.application = app()
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "main.tex"
        self.before = ("% \U0001f600\U0001f680\n\\documentclass{article}\n"
                       "\\newcommand{\\studentMacro}[1]{#1}\n\\begin{document}\n"
                       "Before $x$ after.\n\\end{document}\n")
        self.original = self.before.replace("\n", "\r\n").encode()
        self.path.write_bytes(self.original)
        self.window = MainWindow(settings_store=isolated_settings())
        self.addCleanup(self.dispose)
        self.window.auto_compile_action.setChecked(False)
        self.window.save_debounce_ms = 60_000
        self.window.open_file(self.path)
        self.tab = self.window.current_tab()
        self.editor = self.tab.editor

    def dispose(self):
        from shiboken6 import isValid
        if isValid(self.window):
            for tab in self.window.tabs.values():
                self.window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            self.window.close()
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def select_formula(self, *, backward=False):
        cursor = self.editor.document().find("$x$")
        self.assertFalse(cursor.isNull())
        if backward:
            start, end = cursor.selectionStart(), cursor.selectionEnd()
            cursor.setPosition(end)
            cursor.setPosition(start, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

    def drive(self, replacement, *, mutation=None, cancel=False):
        observed = {}
        class DrivenDialog(FormulaDialog):
            def exec(self):
                observed["seed"] = self.source_edit.toPlainText()

                def respond():
                    try:
                        self.source_mode_check.setChecked(True)
                        self.source_edit.setPlainText(replacement)
                        if mutation:
                            mutation()
                        if cancel:
                            observed["draft"] = self.source_edit.toPlainText()
                            self.reject()
                            return
                        self._on_apply()
                        observed.update(open=self.isVisible(), draft=self.source_edit.toPlainText(),
                                        plan=self.plan(), preview=self.preview_edit.toPlainText(),
                                        target_error=self.target_error_label.isVisible())
                    except Exception as exc:
                        observed["error"] = exc
                    finally:
                        # Failed/blocked Apply must not leave a modal test hanging.
                        if self.isVisible():
                            self.reject()

                QTimer.singleShot(0, self, respond)
                return super().exec()

        with patch("app.gui.insertion_actions.FormulaDialog", DrivenDialog), \
                patch("app.gui.insertion_actions.QMessageBox.information") as information, \
                patch("app.gui.insertion_actions.QMessageBox.warning") as warning:
            self.window.open_formula_composer()
        self.assertNotIn("error", observed)
        information.assert_not_called()
        warning.assert_not_called()
        self.assertIn("seed", observed)
        return observed

    def test_actual_selection_after_non_bmp_opens_and_replaces_exact_formula(self):
        replacement = r"\(\studentMacro{x}+y\)"
        for backward in (False, True):
            with self.subTest(backward=backward):
                self.editor.setPlainText(self.before)
                self.select_formula(backward=backward)
                observed = self.drive(replacement)
                self.assertEqual(observed["seed"], "$x$")
                self.assertFalse(observed["open"])
                after = self.before.replace("$x$", replacement)
                self.assertEqual(self.editor.toPlainText(), after)
                self.editor.undo()
                self.assertEqual(self.editor.toPlainText(), self.before)
                self.editor.redo()
                self.assertEqual(self.editor.toPlainText(), after)
                self.assertEqual(self.path.read_bytes(), self.original)
                self.assertEqual(self.window.compile_authorized_roots, set())

    def test_cancel_after_non_bmp_retains_unknown_formula_and_selection(self):
        source = self.before.replace("$x$", r"$\studentMacro{x}$")
        self.editor.setPlainText(source)
        cursor = self.editor.document().find(r"$\studentMacro{x}$")
        self.editor.setTextCursor(cursor)
        view = (cursor.position(), cursor.anchor(), self.editor.verticalScrollBar().value())
        self.drive(r"$\studentMacro{changed}$", cancel=True)
        current = self.editor.textCursor()
        self.assertEqual(self.editor.toPlainText(), source)
        self.assertEqual((current.position(), current.anchor(), self.editor.verticalScrollBar().value()), view)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_python_plan_converts_package_range_and_unicode_body_cursor(self):
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.beginEditBlock()
        cursor.insertText("% prior edit\n")
        cursor.endEditBlock()
        source = self.editor.toPlainText()
        body = "\\text{\U0001f600}+x"
        start = source.index("$x$")
        plan = final_edit_plan(source, start, start + 3,
                               FormulaDraft(FormulaMode.EQUATION_STAR, body),
                               body_cursor_offset=body.index("+") + 1)
        self.assertIsNotNone(plan)
        self.assertTrue(self.window.insertions.apply_formula_plan(self.tab, plan))
        expected = source.replace("$x$", plan.text).replace(
            "\\newcommand", "\\usepackage{amsmath}\n\\newcommand", 1,
        )
        self.assertEqual(self.editor.toPlainText(), expected)
        prefix = expected[:expected.index(plan.text)] + plan.text[:plan.cursor_offset]
        self.assertEqual(self.editor.textCursor().position(), len(prefix.encode("utf-16-le")) // 2)
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), source)
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), self.before)

    def test_non_bmp_inside_original_formula_remains_exact(self):
        seed = "$\\text{\U0001f600}+x$"
        source = self.before.replace("$x$", seed)
        self.editor.setPlainText(source)
        self.editor.setTextCursor(self.editor.document().find(seed))
        replacement = "$\\text{\U0001f600}+y$"
        observed = self.drive(replacement)
        self.assertEqual(observed["seed"], seed)
        self.assertEqual(self.editor.toPlainText(), source.replace(seed, replacement))
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), source)

    def test_source_mode_wrapper_change_preserves_utf16_cursor(self):
        seed = "$\\studentMacro{\U0001f600\U0001f680\U0001f600\U0001f680}$"
        dialog = FormulaDialog(self.window, seed, 0, len(seed))
        dialog.source_mode_check.setChecked(True)
        cursor = dialog.source_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        dialog.source_edit.setTextCursor(cursor)
        position = cursor.position()
        self.assertTrue(dialog.set_mode(FormulaMode.INLINE_PAREN))
        self.assertEqual(dialog.source_edit.textCursor().position(), position)
        self.assertEqual(dialog.source_edit.toPlainText(), "\\(" + seed[1:-1] + "\\)")

    def test_insertion_at_non_bmp_eof_uses_actual_cursor(self):
        source = "Before \U0001f600\U0001f680"
        self.editor.setPlainText(source)
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        observed = self.drive("$x+y$")
        self.assertFalse(observed["open"])
        self.assertEqual(self.editor.toPlainText(), source + "$x+y$")
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), source)

    def test_external_reload_during_insertion_preserves_draft_and_new_source(self):
        # ASCII isolates the target guard from the independent coordinate bug.
        source = self.before.split("\n", 1)[1]
        self.path.write_text(source)
        self.window.documents.reload_external_change(str(self.path))
        cursor = self.editor.document().find("$x$")
        cursor.clearSelection()
        self.editor.setTextCursor(cursor)
        changed = "% external header\n" + source

        def reload():
            self.path.write_text(changed)
            self.window.documents.reload_external_change(str(self.path))

        observed = self.drive("$x+y$", mutation=reload)
        self.assertTrue(observed["open"])
        self.assertTrue(observed["target_error"])
        self.assertIsNone(observed["plan"])
        self.assertEqual(observed["draft"], "$x+y$")
        self.assertEqual(observed["preview"], "$x+y$")
        self.assertEqual(self.editor.toPlainText(), changed)
        self.assertEqual(self.path.read_text(), changed)
        self.assertEqual(self.window.compile_authorized_roots, set())

    def test_closed_target_keeps_formula_draft_without_native_access(self):
        source = self.before.split("\n", 1)[1]
        self.editor.setPlainText(source)
        self.tab.modified = self.tab.dirty = False
        self.select_formula()

        def close_tab():
            self.window.close_tab(self.window._index_for_tab_id(id(self.editor)))
            self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        observed = self.drive("$x+y$", mutation=close_tab)
        self.assertTrue(observed["open"])
        self.assertTrue(observed["target_error"])
        self.assertIsNone(observed["plan"])
        self.assertEqual(observed["draft"], "$x+y$")
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_zero_length_plan_after_document_truncation_is_refused(self):
        position = len(self.before)
        plan = final_edit_plan(self.before, position, position, FormulaDraft(FormulaMode.INLINE_DOLLAR, "x"))
        self.assertIsNotNone(plan)
        self.editor.setPlainText("New shorter source")
        with patch("app.gui.insertion_actions.QMessageBox.warning"):
            self.assertFalse(self.window.insertions.apply_formula_plan(self.tab, plan))
        self.assertEqual(self.editor.toPlainText(), "New shorter source")


class FormulaComposerTests(TestCase):
    """Focused tests for the DS-001 formula composer GUI slice."""

    def setUp(self) -> None:
        app()

    def test_source_composition_is_local_until_commit_and_cancel_never_applies(self):
        seed = r"$\studentMacro{x}$"
        document = "Before " + seed + " after"
        dialog = FormulaDialog(None, document, 7, 7 + len(seed))
        self.addCleanup(dialog.deleteLater)
        dialog.source_mode_check.setChecked(True)
        editor = dialog.source_edit
        cursor = editor.textCursor()
        cursor.setPosition(len(seed) - 1)
        editor.setTextCursor(cursor)
        for preedit in ("zhong", "zhongwen", ""):
            QApplication.sendEvent(editor, QInputMethodEvent(preedit, []))
            self.assertEqual(editor.toPlainText(), seed)
            self.assertEqual(dialog.build_plan().text, seed)
            self.assertIsNone(dialog.plan())
        event = QInputMethodEvent()
        event.setCommitString("中文")
        QApplication.sendEvent(editor, event)
        self.assertEqual(editor.toPlainText(), seed[:-1] + "中文$")
        self.assertEqual(dialog._document_text, document)
        dialog.undo_button.click()
        self.assertEqual(editor.toPlainText(), seed)
        dialog.redo_button.click()
        self.assertEqual(editor.toPlainText(), seed[:-1] + "中文$")
        dialog.reject()
        self.assertIsNone(dialog.plan())
        self.assertEqual(dialog._document_text, document)

    def test_visual_preedit_blocks_apply_and_source_switch_until_ime_finishes(self):
        document = "Before $x+$ after"
        dialog = FormulaDialog(None, document, 7, 11)
        self.addCleanup(dialog.deleteLater)
        QApplication.sendEvent(dialog.visual_edit, QInputMethodEvent("zhongwen", []))
        self.assertFalse(dialog._ok_button.isEnabled())
        self.assertIn("组合输入", dialog.status_label.text())
        dialog._on_apply()
        self.assertIsNone(dialog.plan())
        dialog.source_mode_check.setChecked(True)
        self.assertFalse(dialog.source_mode_check.isChecked())
        self.assertTrue(dialog.visual_edit.has_preedit)
        event = QInputMethodEvent()
        event.setCommitString("中文")
        QApplication.sendEvent(dialog.visual_edit, event)
        self.assertTrue(dialog._ok_button.isEnabled())
        self.assertEqual(dialog.source_edit.toPlainText(), "$x+中文$")
        dialog.undo_button.click()
        self.assertEqual(dialog.build_plan().text, "$x+$")
        dialog.redo_button.click()
        dialog._on_apply()
        self.assertEqual(dialog.plan().text, "$x+中文$")
        self.assertEqual(dialog._document_text, document)

    def test_source_preedit_blocks_apply_and_visual_switch_until_ime_finishes(self):
        dialog = FormulaDialog(None, "Before $x+$ after", 7, 11)
        self.addCleanup(dialog.deleteLater)
        dialog.source_mode_check.setChecked(True)
        cursor = dialog.source_edit.textCursor()
        cursor.setPosition(3)
        dialog.source_edit.setTextCursor(cursor)
        QApplication.sendEvent(dialog.source_edit, QInputMethodEvent("zhongwen", []))
        self.assertTrue(dialog._source_has_preedit())
        self.assertFalse(dialog._ok_button.isEnabled())
        dialog._on_apply()
        self.assertIsNone(dialog.plan())
        dialog.source_mode_check.setChecked(False)
        self.assertTrue(dialog.source_mode_check.isChecked())
        self.assertTrue(dialog._source_has_preedit())
        event = QInputMethodEvent()
        event.setCommitString("中文")
        QApplication.sendEvent(dialog.source_edit, event)
        self.assertFalse(dialog._source_has_preedit())
        dialog._on_apply()
        self.assertEqual(dialog.plan().text, "$x+中文$")

    def test_visual_replacement_cannot_apply_an_ambiguous_new_envelope(self):
        dialog = FormulaDialog(None, "Before $x$ after", 7, 10)
        self.addCleanup(dialog.deleteLater)
        dialog.visual_edit.type_key("$")
        self.assertIsNone(dialog.build_plan())
        self.assertFalse(dialog._ok_button.isEnabled())
        self.assertIn("草稿", dialog.status_label.text())
        self.assertNotIn("公式有效", dialog.status_label.text())
        self.assertNotIn("重新选择", dialog.status_label.text())
        with patch.object(QMessageBox, "warning") as warning:
            dialog._on_apply()
        warning.assert_called_once()
        self.assertIsNone(dialog.plan())
        self.assertFalse(dialog._submitted)
        dialog.visual_edit.undo()
        self.assertEqual(dialog.build_plan().text, "$x$")
        self.assertTrue(dialog._ok_button.isEnabled())
        dialog.reject()

    def test_unknown_formula_source_survives_failed_visual_switch_and_cancel(self):
        body = "\n  " + r"\studentMacro{a}{b} + x_1^2 + \unknown^{2} % keep $ \)" + "\n\t"
        seed = "\\(" + body + "\\)"
        document = "Before " + seed + " after"
        dialog = FormulaDialog(None, document, 7, 7 + len(seed))
        self.addCleanup(dialog.deleteLater)
        self.assertTrue(dialog.source_mode_check.isChecked())
        cursor = dialog.source_edit.textCursor()
        cursor.setPosition(len(seed) - 2)
        dialog.source_edit.setTextCursor(cursor)
        dialog.source_edit.insertPlainText("+z")
        draft = seed[:-2] + "+z" + seed[-2:]
        dialog.source_mode_check.setChecked(False)
        self.assertTrue(dialog.source_mode_check.isChecked())
        self.assertEqual(dialog.source_edit.toPlainText(), draft)
        self.assertEqual(dialog.build_plan().text, draft)
        dialog.undo_button.click()
        self.assertEqual(dialog.source_edit.toPlainText(), seed)
        self.assertEqual(dialog.build_plan().text, seed)
        dialog.reject()
        self.assertIsNone(dialog.plan())
        self.assertEqual(dialog._document_text, document)

    def test_visual_paste_preserves_comment_newlines_unknown_macro_and_undo(self):
        dialog = FormulaDialog(None, "Before $x$ after", 7, 10)
        self.addCleanup(dialog.deleteLater)
        pasted = "\n + " + r"\studentMacro{a}{b} % keep $ \)" + "\n\t + z\n"
        dialog.visual_edit.paste_clipboard("\\(" + pasted + "\\)")
        self.assertEqual(dialog.visual_edit.latex(), "x" + pasted)
        self.assertEqual(dialog.build_plan().text, "$x" + pasted + "$")
        self.assertEqual(dialog.preview_edit.toPlainText(), "$x" + pasted + "$")
        dialog.source_mode_check.setChecked(True)
        self.assertEqual(dialog.source_edit.toPlainText(), "$x" + pasted + "$")
        dialog.source_mode_check.setChecked(False)
        dialog.undo_button.click()
        self.assertEqual(dialog.build_plan().text, "$x$")
        dialog.reject()
        self.assertIsNone(dialog.plan())

    def test_physical_typing_undo_and_paste_refresh_source_preview(self):
        from PySide6.QtTest import QTest
        dialog = FormulaDialog(None, "", 0, 0, seed_text="$x$")
        QTest.keyClicks(dialog.visual_edit, "2")
        self.assertEqual(dialog.preview_edit.toPlainText(), "$x2$")
        self.assertEqual(dialog.source_edit.toPlainText(), "$x2$")
        dialog.undo_button.click()
        self.assertEqual(dialog.preview_edit.toPlainText(), "$x$")
        dialog.visual_edit.paste_clipboard("+1")
        self.assertEqual(dialog.preview_edit.toPlainText(), "$x+1$")
        dialog.close()

    def test_source_wrapper_change_is_effective_and_undoable(self):
        dialog = FormulaDialog(None, "", 0, 0, seed_text="$x$")
        dialog.source_mode_check.setChecked(True)
        dialog.set_mode(FormulaMode.EQUATION)
        self.assertEqual(dialog.source_edit.toPlainText(), r"\begin{equation}x\end{equation}")
        self.assertEqual(dialog.build_plan().text, r"\begin{equation}x\end{equation}")
        self.assertEqual(dialog.preview_edit.toPlainText(), dialog.source_edit.toPlainText())
        dialog.undo_button.click()
        self.assertEqual(dialog.source_edit.toPlainText(), "$x$")
        self.assertEqual(dialog.mode_combo.currentData(), FormulaMode.INLINE_DOLLAR.value)
        dialog.close()

    def test_invalid_source_disables_apply_and_retains_original(self):
        dialog = FormulaDialog(None, "", 0, 0, seed_text="$x$")
        dialog.source_mode_check.setChecked(True)
        dialog.source_edit.setPlainText("$x$ $y$")
        self.assertFalse(dialog._ok_button.isEnabled())
        self.assertEqual(dialog.preview_edit.toPlainText(), "")
        with patch.object(QMessageBox, "warning"):
            dialog.source_mode_check.setChecked(False)
        self.assertTrue(dialog.source_mode_check.isChecked())
        self.assertFalse(dialog.keyboard.isEnabled())
        self.assertEqual(dialog.source_edit.toPlainText(), "$x$ $y$")
        dialog.close()

    def test_pending_command_is_included_on_explicit_apply(self):
        dialog = FormulaDialog(None, "", 0, 0, seed_text=r"\(\)")
        for char in r"\alpha":
            dialog.visual_edit.type_key(char)
        self.assertIn(r"\alpha", dialog.status_label.text())
        dialog._on_apply()
        self.assertEqual(dialog.plan().text, r"\(\alpha\)")
        dialog.close()

    def test_mode_round_trip_without_source_edits_keeps_visual_undo(self):
        dialog = FormulaDialog(None, "", 0, 0, seed_text="$x$")
        dialog.visual_edit.type_key("2")
        dialog.source_mode_check.setChecked(True)
        dialog.source_mode_check.setChecked(False)
        dialog.undo_button.click()
        self.assertEqual(dialog.visual_edit.latex(), "x")
        dialog.close()

    def test_ocr_seed_syncs_wrapper_and_still_requires_apply(self):
        dialog = FormulaDialog(None, "", 0, 0, seed_text="$x$")
        dialog._seed_editor_latex(r"\alpha")
        self.assertEqual(dialog.mode_combo.currentData(), FormulaMode.INLINE_PAREN.value)
        self.assertEqual(dialog.preview_edit.toPlainText(), r"\(\alpha\)")
        self.assertIsNone(dialog.plan())
        dialog.close()

    def test_matrix_template_moves_to_editable_source_with_package_hint(self):
        dialog = FormulaDialog(None, "", 0, 0, seed_text=r"\(\)")
        dialog._on_keyboard_action("structure:matrix")
        self.assertTrue(dialog.source_mode_check.isChecked())
        self.assertIn(r"\begin{matrix}", dialog.source_edit.toPlainText())
        self.assertEqual(dialog.build_plan().packages, ("amsmath",))
        self.assertIsNone(dialog.plan())
        dialog.close()

    def _window_with_document(self, text: str) -> tuple[MainWindow, EditorTab]:
        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor(text)
        tab = EditorTab(editor=editor)
        window._add_tab(tab, "formula_test.tex")
        return window, tab

    @staticmethod
    def _select(editor: LaTeXEditor, start: int, end: int) -> None:
        cursor = editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)

    @staticmethod
    def _close(window: MainWindow, tab: EditorTab) -> None:
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_apply_plan_replaces_formula_and_merges_package_into_one_undo(self) -> None:
        source = "\\documentclass{article}\n\\begin{document}\nText $a+b$ here\n\\end{document}\n"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        start = source.index("$")
        end = start + len("$a+b$")

        envelope = parse_document_selection(source, start, end)
        assert envelope is not None
        fraction = apply_formula_template(
            FormulaDraft(mode=envelope.mode, body=envelope.body), "fraction"
        )
        assert fraction is not None
        draft = FormulaDraft(mode=FormulaMode.EQUATION_STAR, body=fraction.draft.body)
        plan = final_edit_plan(
            source,
            start,
            end,
            draft,
            body_cursor_offset=fraction.cursor_offset,
        )
        assert plan is not None
        self.assertEqual(plan.packages, ("amsmath",))

        applied = window.insertions.apply_formula_plan(tab, plan)

        self.assertTrue(applied)
        text = editor.toPlainText()
        self.assertIn("\\usepackage{amsmath}", text)
        self.assertIn("\\begin{equation*}\\frac{a+b}{}\\end{equation*}", text)
        self.assertNotIn("$a+b$", text)
        # A single Undo step restores both the package and the formula text.
        editor.undo()
        self.assertEqual(editor.toPlainText(), source)
        self._close(window, tab)

    def test_apply_plan_refuses_stale_selection(self) -> None:
        source = "Text $a+b$ here"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        start = source.index("$")
        end = start + len("$a+b$")
        plan = final_edit_plan(
            source,
            start,
            end,
            FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="a+b"),
        )
        assert plan is not None

        editor.setPlainText("Text $x+y$ here")  # external edit at the same offsets
        with patch("app.gui.insertion_actions.QMessageBox.warning") as warning:
            applied = window.insertions.apply_formula_plan(tab, plan)

        self.assertFalse(applied)
        self.assertEqual(editor.toPlainText(), "Text $x+y$ here")
        warning.assert_called_once()
        self._close(window, tab)

    def test_composer_requires_exact_formula_selection(self) -> None:
        source = "Text $a+b$ here"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        self._select(editor, 0, len(source))

        with patch("app.gui.insertion_actions.QMessageBox.information") as information:
            window.open_formula_composer()

        self.assertEqual(editor.toPlainText(), source)
        information.assert_called_once()
        self._close(window, tab)

    def test_composer_without_selection_opens_dialog_and_inserts_new_formula(self) -> None:
        source = "\\documentclass{article}\n\\begin{document}\n\n\\end{document}\n"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        position = len(source) - len("\\end{document}\n")
        cursor = editor.textCursor()
        cursor.setPosition(position)
        editor.setTextCursor(cursor)

        with patch("app.gui.insertion_actions.FormulaDialog") as dialog_cls:
            dialog_cls.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog_cls.return_value.plan.return_value = final_edit_plan(
                source,
                position,
                position,
                FormulaDraft(mode=FormulaMode.EQUATION, body=""),
                body_cursor_offset=0,
            )
            window.open_formula_composer()

        _, kwargs = dialog_cls.call_args
        self.assertEqual(kwargs.get("seed_text"), r"\begin{equation}\end{equation}")
        self.assertIn(r"\begin{equation}\end{equation}", editor.toPlainText())
        editor.undo()
        self.assertEqual(editor.toPlainText(), source)
        self._close(window, tab)

    def test_toolbox_equation_button_routes_through_composer(self) -> None:
        source = "\\documentclass{article}\n\\begin{document}\n\n\\end{document}\n"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        cursor = editor.textCursor()
        cursor.setPosition(len(source) - len("\\end{document}\n"))
        editor.setTextCursor(cursor)

        with patch("app.gui.insertion_actions.FormulaDialog") as dialog_cls:
            dialog_cls.return_value.exec.return_value = QDialog.DialogCode.Rejected
            window.insert_panel.equationRequested.emit()

        dialog_cls.assert_called_once()
        self.assertEqual(editor.toPlainText(), source)
        self._close(window, tab)

    def test_dialog_seeds_from_selection_and_builds_plan(self) -> None:
        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        self.assertEqual(dialog.visual_edit.latex(), "a+b")
        self.assertTrue(dialog.apply_template("fraction"))
        self.assertEqual(dialog.visual_edit.latex(), r"a+b\frac{}{}")
        self.assertTrue(dialog.set_mode(FormulaMode.EQUATION))

        plan = dialog.build_plan()
        assert plan is not None
        self.assertEqual(plan.start, start)
        self.assertEqual(plan.end, end)
        self.assertEqual(plan.text, r"\begin{equation}a+b\frac{}{}\end{equation}")
        dialog.close()

    def test_dialog_apply_is_idempotent(self) -> None:
        source = r"Before \(E=mc^2\) after."
        seed = r"\(E=mc^2\)"
        start = source.index(seed)
        end = start + len(seed)
        dialog = FormulaDialog(None, source, start, end)

        original_accept = QDialog.accept
        accept_calls: list = []

        def spy(self) -> None:
            accept_calls.append(self)
            original_accept(self)

        with patch.object(QDialog, "accept", new=spy):
            dialog._on_apply()
            dialog._on_apply()
        self.assertEqual(len(accept_calls), 1)
        self.assertTrue(dialog._submitted)
        self.assertIsNotNone(dialog.plan())
        self.assertFalse(dialog._ok_button.isEnabled())
        dialog.close()

    def test_ocr_button_ignores_rapid_repeated_clicks(self) -> None:
        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        with patch.object(FormulaDialog, "_get_ocr_manager", return_value=object()), patch(
            "app.gui.formula_ocr.batch_dialog.BatchRecognitionDialog"
        ) as dialog_cls:
            instance = dialog_cls.return_value
            instance.exec.return_value = QDialog.DialogCode.Rejected
            dialog._open_batch_ocr()
            dialog._open_batch_ocr()
        self.assertEqual(dialog_cls.call_count, 1)
        self.assertTrue(dialog.ocr_button.isEnabled())
        self.assertFalse(dialog._ocr_open)

        dialog._ocr_ts = 0.0  # debounce window expired
        with patch.object(FormulaDialog, "_get_ocr_manager", return_value=object()), patch(
            "app.gui.formula_ocr.batch_dialog.BatchRecognitionDialog"
        ) as dialog_cls:
            instance = dialog_cls.return_value
            instance.exec.return_value = QDialog.DialogCode.Rejected
            dialog._open_batch_ocr()
        self.assertEqual(dialog_cls.call_count, 1)
        dialog.close()

    def test_dialog_rejects_template_and_plan_on_invalid_text(self) -> None:
        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        dialog.source_mode_check.setChecked(True)
        dialog.source_edit.setPlainText("$a$ $b$")
        self.assertFalse(dialog.apply_template("fraction"))
        self.assertEqual(dialog.source_edit.toPlainText(), "$a$ $b$")
        self.assertIsNone(dialog.build_plan())
        self.assertIsNone(dialog.plan())
        dialog.close()

    def test_dialog_accepts_explicit_seed_text_for_insertion(self) -> None:
        source = "Text here"
        dialog = FormulaDialog(
            None,
            source,
            4,
            4,
            seed_text=r"\begin{equation}\end{equation}",
        )

        self.assertEqual(dialog.visual_edit.latex(), "")
        self.assertTrue(dialog.apply_template("fraction"))
        self.assertEqual(dialog.visual_edit.latex(), r"\frac{}{}")
        plan = dialog.build_plan()
        assert plan is not None
        self.assertEqual(plan.start, 4)
        self.assertEqual(plan.end, 4)
        self.assertEqual(plan.source_text, "")
        self.assertEqual(plan.text, r"\begin{equation}\frac{}{}\end{equation}")
        dialog.close()

    def test_dialog_paste_into_visual_editor(self) -> None:
        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        dialog.visual_edit.paste_clipboard(r"\cdot c")
        plan = dialog.build_plan()

        assert plan is not None
        self.assertEqual(plan.text, r"$a+b\cdot c$")
        dialog.close()

    def test_keyboard_fraction_button_inserts_structure(self) -> None:
        from app.gui.math_keyboard import MathKeyButton

        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        fraction_button = next(
            button
            for button in dialog.keyboard.findChildren(MathKeyButton)
            if button.action == "structure:fraction"
        )
        fraction_button.click()

        self.assertEqual(dialog.visual_edit.latex(), r"a+b\frac{}{}")
        self.assertEqual(dialog.keyboard.isEnabled(), True)
        dialog.close()

    def test_keyboard_digits_and_symbols_insert_text(self) -> None:
        from app.gui.math_keyboard import MathKeyButton

        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        actions = {
            button.action: button
            for button in dialog.keyboard.findChildren(MathKeyButton)
        }
        actions["text:7"].click()
        actions["text:+"].click()
        actions["text:8"].click()
        actions["command:times"].click()
        actions["command:pi"].click()

        self.assertEqual(dialog.visual_edit.latex(), r"a+b7+8\times\pi")
        dialog.close()

    def test_keyboard_category_switch_preserves_formula(self) -> None:
        from app.gui.math_keyboard import MathKeyButton

        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        sqrt_button = next(
            button
            for button in dialog.keyboard.findChildren(MathKeyButton)
            if button.action == "structure:sqrt"
        )
        sqrt_button.click()
        self.assertEqual(dialog.visual_edit.latex(), r"a+b\sqrt{}")

        from PySide6.QtWidgets import QPushButton

        greek_button = next(
            button
            for button in dialog.keyboard.findChildren(QPushButton)
            if button.text() == "希腊字母"
        )
        greek_button.click()

        self.assertEqual(dialog.visual_edit.latex(), r"a+b\sqrt{}")
        dialog.close()

    def test_keyboard_disabled_in_source_mode(self) -> None:
        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        dialog.source_mode_check.setChecked(True)
        self.assertFalse(dialog.keyboard.isEnabled())
        dialog.source_mode_check.setChecked(False)
        self.assertTrue(dialog.keyboard.isEnabled())
        dialog.close()

    def test_acceptance_inline_fraction_never_forces_newline(self) -> None:
        source = r"The result is \(\) under this condition."
        window, tab = self._window_with_document(source)
        editor = tab.editor
        start = source.index(r"\(")
        end = start + len(r"\(\)")
        self._select(editor, start, end)

        class InlineFractionDialog(FormulaDialog):
            def exec(self) -> QDialog.DialogCode:
                self.visual_edit.insert_structure("fraction")
                self.visual_edit.type_key("a")
                self.visual_edit.cursor_tab()
                self.visual_edit.type_key("b")
                self.set_mode(FormulaMode.INLINE_PAREN)
                self._on_apply()
                return QDialog.DialogCode.Accepted

        with patch("app.gui.insertion_actions.FormulaDialog", InlineFractionDialog):
            window.open_formula_composer()

        text = editor.toPlainText()
        self.assertEqual(text, r"The result is \(\frac{a}{b}\) under this condition.")
        self.assertNotIn("\n", text)
        self._close(window, tab)

    def test_acceptance_read_back_and_modify_formula(self) -> None:
        source = r"See \(E=mc^2\) here."
        window, tab = self._window_with_document(source)
        editor = tab.editor
        start = source.index(r"\(")
        end = start + len(r"\(E=mc^2\)")
        self._select(editor, start, end)

        class ModifyDialog(FormulaDialog):
            def exec(self) -> QDialog.DialogCode:
                self.visual_edit.cursor_home()
                self.visual_edit.cursor_right()  # enter the base slot
                self.visual_edit.cursor_right()
                self.visual_edit.cursor_right()  # right after "E="
                for char in ("\\", "g", "a", "m", "m", "a", " "):
                    self.visual_edit.type_key(char)
                self._on_apply()
                return QDialog.DialogCode.Accepted

        with patch("app.gui.insertion_actions.FormulaDialog", ModifyDialog):
            window.open_formula_composer()

        self.assertEqual(editor.toPlainText(), r"See \(E=\gamma mc^2\) here.")
        self._close(window, tab)

    def test_composer_end_to_end_apply_via_dialog(self) -> None:
        source = "Text $a+b$ here"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        start = source.index("$")
        end = start + len("$a+b$")
        self._select(editor, start, end)

        class FakeDialog:
            def __init__(self, _parent, document_text: str, sel_start: int, sel_end: int,
                         *, validate_target) -> None:
                self._document_text = document_text
                self._sel_start = sel_start
                self._sel_end = sel_end
                self._validate_target = validate_target

            def exec(self) -> QDialog.DialogCode:
                assert self._validate_target() == ""
                return QDialog.DialogCode.Accepted

            def plan(self):
                envelope = parse_document_selection(
                    self._document_text, self._sel_start, self._sel_end
                )
                assert envelope is not None
                fraction = apply_formula_template(
                    FormulaDraft(mode=envelope.mode, body=envelope.body), "fraction"
                )
                assert fraction is not None
                return final_edit_plan(
                    self._document_text,
                    self._sel_start,
                    self._sel_end,
                    fraction.draft,
                    body_cursor_offset=fraction.cursor_offset,
                )

        with patch("app.gui.insertion_actions.FormulaDialog", FakeDialog):
            window.open_formula_composer()

        self.assertIn(r"$\frac{a+b}{}$", editor.toPlainText())
        self.assertNotIn("$a+b$", editor.toPlainText())
        # Cursor lands inside the empty denominator slot: 1 ($) + 11 (body offset).
        self.assertEqual(editor.textCursor().position(), start + 12)
        self._close(window, tab)

    def test_cancel_leave_editor_untouched(self) -> None:
        source = "Text $a+b$ here"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        start = source.index("$")
        end = start + len("$a+b$")
        self._select(editor, start, end)

        with patch(
            "app.gui.insertion_actions.FormulaDialog.exec",
            return_value=QDialog.DialogCode.Rejected,
        ):
            window.open_formula_composer()

        self.assertEqual(editor.toPlainText(), source)
        self._close(window, tab)

    def test_images_refresh_reuses_memory_index_without_project_cache_writes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            figures = root / "figures"
            figures.mkdir()
            (figures / "a.png").write_bytes(b"png-asset")
            source = root / "main.tex"
            source.write_text(
                "\\documentclass{article}\n\\begin{document}\n\\end{document}\n",
                encoding="utf-8",
            )
            before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            try:
                with patch("app.gui.project_panel_controller._read_image_size", return_value=(120, 60)) as metadata, \
                        patch("app.gui.project_panel_controller.import_metrics.record_index_scan") as scans, \
                        patch("app.core.asset_index.AssetIndex.load") as load, \
                        patch("app.core.asset_index.AssetIndex.save") as save:
                    window._add_tab(tab, source.name)
                    window.refresh_project_panels()
                    self.assertEqual(window.images_panel.table.rowCount(), 1)
                    index = next(iter(window.project_panels._asset_indexes.values()))
                    record = index._records["figures/a.png"]
                    window.refresh_project_panels()
                    self.assertIs(next(iter(window.project_panels._asset_indexes.values())), index)
                    self.assertIs(index._records["figures/a.png"], record)
                    self.assertEqual(window.images_panel.table.rowCount(), 1)
                    self.assertIn("使用待检查", window.images_panel.table.item(0, 2).text())
                    metadata.assert_called_once()
                    load.assert_not_called()
                    save.assert_not_called()
                    self.assertGreaterEqual(scans.call_count, 2)
                    self.assertTrue(scans.call_args_list[0].kwargs["full"])
                    self.assertTrue(all(not call.kwargs["full"] for call in scans.call_args_list[1:]))
                self.assertEqual(before, {path.relative_to(root): path.read_bytes()
                                          for path in root.rglob("*") if path.is_file()})
                self.assertFalse((root / ".icstex" / "asset-index.json").exists())
                self.assertFalse(window.compile_authorized_roots)
            finally:
                tab.modified = tab.dirty = False
                window.close()
                window.deleteLater()
                QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_import_perf_dialog_shows_summaries(self) -> None:
        from app.core.import_metrics import import_metrics
        from app.gui.import_perf_dialog import ImportPerfDialog

        recorder = import_metrics.begin_transaction("perf-test")
        import_metrics.record_compile_request("asset_import")
        import_metrics.record_compile_start("preview")
        import_metrics.record_compile_finish("preview")

        dialog = ImportPerfDialog(None)
        text = dialog.text.toPlainText()
        self.assertIn("perf-test", text)
        self.assertIn("compile requested=1", text)
        self.assertIn("started=1", text)
        dialog.close()
