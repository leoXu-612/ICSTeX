"""Qt composition-event contracts, not native Chinese IME acceptance."""
import os
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QInputMethodEvent, QTextCursor
from PySide6.QtWidgets import QApplication

from app.gui.latex_editor import LaTeXEditor


class SourceCompositionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.editor = LaTeXEditor()
        self.addCleanup(self.dispose)

    def dispose(self):
        self.editor.close()
        self.editor.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_preedit_updates_cancel_and_commit_are_separate_from_source_and_undo(self):
        editor = self.editor
        original = r"\section{Title}" + "\nBody "
        editor.setPlainText(original)
        editor.moveCursor(QTextCursor.MoveOperation.End)
        changes = []
        editor.textChanged.connect(lambda: changes.append(editor.toPlainText()))
        for text in ("zhong", "zhongwen", ""):
            QApplication.sendEvent(editor, QInputMethodEvent(text, []))
            self.assertEqual(editor.toPlainText(), original)
            self.assertFalse(editor.document().isUndoAvailable())
        # Qt emits textChanged for preedit layout changes too; only committed
        # document bytes and undo history distinguish actual source edits.
        self.assertTrue(all(text == original for text in changes))
        changes.clear()
        event = QInputMethodEvent()
        event.setCommitString("\u4e2d\u6587")
        QApplication.sendEvent(editor, event)
        self.assertEqual(editor.toPlainText(), original + "\u4e2d\u6587")
        self.assertEqual(changes, [original + "\u4e2d\u6587"])
        editor.undo()
        self.assertEqual(editor.toPlainText(), original)
        editor.redo()
        self.assertEqual(editor.toPlainText(), original + "\u4e2d\u6587")

    def test_reconversion_uses_utf16_positions_without_changing_adjacent_tex(self):
        editor = self.editor
        original = "a\U0001f642" + r"\unknown{x}"
        editor.setPlainText(original)
        cursor = editor.textCursor()
        cursor.setPosition(3)  # Qt counts the non-BMP character as two UTF-16 units.
        editor.setTextCursor(cursor)
        event = QInputMethodEvent()
        event.setCommitString("\u4e2d", -2, 2)
        QApplication.sendEvent(editor, event)
        self.assertEqual(editor.toPlainText(), "a\u4e2d" + r"\unknown{x}")
        editor.undo()
        self.assertEqual(editor.toPlainText(), original)

    def test_source_notifications_ignore_preedit_but_keep_partial_commits_and_undo(self):
        editor = self.editor
        editor.setPlainText("base ")
        editor.moveCursor(QTextCursor.MoveOperation.End)
        changes = []
        editor.sourceTextChanged.connect(lambda: changes.append(editor.toPlainText()))
        revision = editor.source_revision
        QApplication.sendEvent(editor, QInputMethodEvent("zhongwen", []))
        self.assertTrue(editor.has_preedit())
        self.assertEqual(changes, [])
        self.assertEqual(editor.source_revision, revision)
        event = QInputMethodEvent("wen", [])
        event.setCommitString("\u4e2d")
        QApplication.sendEvent(editor, event)
        self.assertEqual(changes, ["base \u4e2d"])
        self.assertEqual(editor.source_revision, revision + 1)
        self.assertTrue(editor.has_preedit())
        event = QInputMethodEvent()
        event.setCommitString("\u6587")
        QApplication.sendEvent(editor, event)
        self.assertEqual(changes, ["base \u4e2d", "base \u4e2d\u6587"])
        self.assertEqual(editor.source_revision, revision + 2)
        self.assertFalse(editor.has_preedit())
        editor.undo()
        editor.undo()
        self.assertEqual(editor.toPlainText(), "base ")
        self.assertGreater(editor.source_revision, revision + 2)
        editor.redo()
        editor.redo()
        self.assertEqual(changes[-1], "base \u4e2d\u6587")

    def test_source_notifications_preserve_reconversion_deletion_and_blocked_reload(self):
        editor = self.editor
        original = "a\U0001f642" + r"\unknown{x}"
        editor.setPlainText(original)
        cursor = editor.textCursor()
        cursor.setPosition(3)
        editor.setTextCursor(cursor)
        changes = []
        editor.sourceTextChanged.connect(lambda: changes.append(editor.toPlainText()))
        revision = editor.source_revision
        event = QInputMethodEvent()
        event.setCommitString("", -2, 2)
        QApplication.sendEvent(editor, event)
        self.assertEqual(changes, ["a" + r"\unknown{x}"])
        self.assertEqual(editor.source_revision, revision + 1)
        editor.undo()
        self.assertEqual(changes[-1], original)
        revision = editor.source_revision
        editor.blockSignals(True)
        editor.setPlainText("external")
        editor.blockSignals(False)
        self.assertEqual(len(changes), 2)
        self.assertGreater(editor.source_revision, revision)
        editor.insertPlainText("new ")
        self.assertEqual(changes[-1], "new external")

    def test_source_notifications_include_selection_removal_at_native_preedit_boundary(self):
        editor = self.editor
        original = "a\U0001f642" + r"\unknown{x}"
        editor.setPlainText(original)
        cursor = editor.textCursor()
        cursor.setPosition(1)
        cursor.setPosition(3, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        changes = []
        editor.sourceTextChanged.connect(lambda: changes.append(editor.toPlainText()))
        revision = editor.source_revision
        # Qt removes an existing selection when composition begins. This is a
        # real document edit even without commitString; do not filter by the
        # event's commit/replacement fields alone or silently miss that change.
        QApplication.sendEvent(editor, QInputMethodEvent("zhong", []))
        self.assertEqual(changes, ["a" + r"\unknown{x}"])
        self.assertEqual(editor.source_revision, revision + 1)
        QApplication.sendEvent(editor, QInputMethodEvent())
        self.assertEqual(editor.source_revision, revision + 1)
        editor.undo()
        self.assertEqual(editor.toPlainText(), original)
        self.assertEqual(changes[-1], original)

    def test_revision_advances_before_notification_without_full_text_reads(self):
        editor = self.editor
        editor.setPlainText("base")
        revisions = [editor.source_revision]
        editor.sourceTextChanged.connect(lambda: revisions.append(editor.source_revision))
        with patch.object(editor, "toPlainText", side_effect=AssertionError("no full-text polling")):
            editor.insertPlainText("new ")
            editor.undo()
            editor.redo()
        self.assertEqual(len(revisions), 4)
        self.assertTrue(all(new > old for old, new in zip(revisions, revisions[1:])), revisions)

    def test_blocked_reload_cannot_reuse_a_revision_even_when_text_returns(self):
        editor = self.editor
        editor.setPlainText("base")
        revisions = [editor.source_revision]
        editor.blockSignals(True)
        try:
            for text in ("external", "base", "base", ""):
                editor.setPlainText(text)
                revisions.append(editor.source_revision)
        finally:
            editor.blockSignals(False)
        self.assertTrue(all(new > old for old, new in zip(revisions, revisions[1:])), revisions)
