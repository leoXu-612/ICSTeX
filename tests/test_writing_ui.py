"""Writing-first chrome keeps existing compilation and document state intact."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolBar
from app.core.compiler import BuildPurpose
from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tests.test_pdf_panel import _write_zoom_pdf


class WritingUiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        apply_theme(cls.app)

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = AppSettings(QSettings(str(Path(self.tmp.name) / "ui.ini"), QSettings.Format.IniFormat))
        self.window = MainWindow(settings_store=self.settings)
        self.window.set_ui_scale(1.)
        self.window.resize(1440, 900)
        self.window.new_document()
        self.window.auto_compile_action.setChecked(False)
        self.window.show()
        self.window.activateWindow()
        self.settle()

    def tearDown(self):
        for tab in self.window.tabs.values():
            self.window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        self.window.close()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.ui_scale_manager.apply_scale(1.)

    def settle(self):
        for _ in range(8):
            self.app.processEvents()

    def test_empty_preview_is_compact_actionable_and_has_no_fake_page_count(self):
        panel = self.window.pdf_panel
        self.assertTrue(panel._toolbar.isHidden())
        self.assertEqual(panel.page_count_label.text(), "")
        self.assertLessEqual(self.window.pdf_panel_wrapper.width(), 270)
        self.assertGreater(self.window.current_tab().editor.viewport().width(), 1000)
        with patch.object(self.window, "compile_current") as compile:
            panel.empty_compile_button.click()
            compile.assert_called_once_with(immediate=True, show_missing_warning=True, purpose=BuildPurpose.FINAL)
        self.assertFalse(self.window.compile_authorized_roots)

    def test_console_fully_collapses_and_reopens_without_losing_content(self):
        self.assertTrue(self.window.bottom_panel.isHidden())
        self.assertEqual(self.window.vertical_splitter.sizes()[1], 0)
        self.window.log_view.setPlainText("keep diagnostics")
        self.window.bottom_collapse_button.click()
        self.settle()
        self.assertFalse(self.window.bottom_panel.isHidden())
        self.assertGreater(self.window.vertical_splitter.sizes()[1], 100)
        self.window.bottom_collapse_button.click()
        self.window.update_document_view_state()
        self.settle()
        self.assertTrue(self.window.bottom_panel.isHidden())
        self.assertEqual(self.window.log_view.toPlainText(), "keep diagnostics")

    def test_console_entry_toggles_all_tabs_without_forcing_word_count(self):
        toolbar = self.window.findChild(QToolBar, "mainToolbar")
        action = self.window.console_action
        self.assertIn(action, toolbar.actions())
        self.assertNotIn(self.window.word_count_action, toolbar.actions())
        self.assertEqual(action.text(), "控制台")
        self.assertTrue(action.isCheckable())
        self.assertIs(self.window.bottom_collapse_button.defaultAction(), action)
        with patch.object(self.window, "update_word_count") as count:
            action.trigger()
            self.settle()
            self.assertTrue(action.isChecked())
            self.assertFalse(self.window.bottom_panel.isHidden())
            self.window.bottom_tabs.setCurrentWidget(self.window.error_table)
            action.trigger()
            self.settle()
            self.assertFalse(action.isChecked())
            self.assertTrue(self.window.bottom_panel.isHidden())
            self.window.bottom_collapse_button.click()
            self.settle()
            self.assertTrue(action.isChecked())
            self.assertIs(self.window.bottom_tabs.currentWidget(), self.window.error_table)
            count.assert_not_called()
        with patch.object(self.window, "update_word_count") as count:
            self.window.word_count_action.trigger()
            self.assertIs(self.window.bottom_tabs.currentWidget(), self.window.word_count_panel)
            count.assert_called_once_with(force=True)

    def test_first_pdf_restores_reading_split_without_editing_or_moving_cursor(self):
        editor = self.window.current_tab().editor
        text = "\n".join(f"Line {i}: " + "readable text " * 12 for i in range(100))
        editor.setPlainText(text)
        editor.verticalScrollBar().setValue(60)
        self.settle()
        position = editor.textCursor().position()
        before_line = editor.firstVisibleBlock().blockNumber()
        area = self.window.source_preview_area
        preference = tuple(area._wide_sizes)
        pdf = Path(self.tmp.name) / "preview.pdf"
        _write_zoom_pdf(pdf)
        self.window.pdf_panel.load_pdf(pdf)
        QTest.qWait(160)
        self.assertTrue(area._preview_available)
        self.assertEqual(tuple(area._wide_sizes), preference)
        self.assertGreater(self.window.pdf_panel_wrapper.width(), 500)
        self.assertEqual(editor.toPlainText(), text)
        self.assertEqual(editor.textCursor().position(), position)
        self.assertEqual(editor.firstVisibleBlock().blockNumber(), before_line)

    def test_toolbar_labels_toggle_scale_and_source_header_share_one_row(self):
        toolbar = self.window.findChild(QToolBar, "mainToolbar")
        for scale in (.9, 1., 1.1, 1.25, 1.5, 1.):
            self.window.set_ui_scale(scale)
            self.settle()
            toggle = self.window.auto_compile_toggle
            self.assertEqual(toggle.height(), round(32 * scale))
            self.assertGreaterEqual(toggle.width(), toggle.sizeHint().width())
            self.assertFalse(self.window.toolBarBreak(self.window.workspace.toolbar))
            for action in (self.window.open_file_action, self.window.save_action, self.window.console_action):
                self.assertEqual(toolbar.widgetForAction(action).toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button = toolbar.widgetForAction(self.window.compile_action)
            self.assertTrue(button.visibleRegion().contains(button.rect()))
        self.assertFalse(self.window.current_tab().editor.highlighter.comment_format.fontItalic())
