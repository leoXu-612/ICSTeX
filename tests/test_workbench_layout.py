from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QWidget
from shiboken6 import isValid

from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.responsive.editor_pdf_area import EditorPdfArea
from app.gui.theme import apply_theme


class WorkbenchLayoutMemoryTests(TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        if not hasattr(self.app, "ui_scale_manager"):
            apply_theme(self.app)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = AppSettings(QSettings(str(Path(self.temp.name) / "layout.ini"), QSettings.Format.IniFormat))
        self.windows = []
        self.addCleanup(self.dispose)

    def drain(self):
        for _ in range(3):
            self.app.processEvents()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def dispose(self):
        for window in self.windows:
            if isValid(window):
                for tab in window.tabs.values():
                    tab.modified = tab.dirty = False
                window.close()
        self.drain()

    def window(self, *, width=1920, document=True):
        window = MainWindow(settings_store=self.settings)
        self.windows.append(window)
        window.auto_compile_action.setChecked(False)
        window.resize(width, 1000)
        if document:
            window.new_document()
        window.show()
        self.drain()
        if document:
            # Layout availability only; no PDF pixels or compilation are claimed.
            window.source_preview_area.set_preview_available(True)
            self.drain()
        return window

    def choose_layout(self, window):
        area = window.source_preview_area
        self.assertFalse(area._is_compact())
        area.splitter.moveSplitter(round(sum(area.splitter.sizes()) * 0.63), 1)
        window.source_panels.set_console(True)
        self.drain()
        self.assertFalse(window.source_panels._is_compact())
        window.vertical_splitter.moveSplitter(round(sum(window.vertical_splitter.sizes()) * 0.68), 1)
        self.drain()
        return area.wide_ratio(), window.source_panels._console_ratio

    def test_new_user_wide_document_shows_navigation_but_welcome_hides_it(self):
        self.assertFalse(self.settings.settings.contains("window/block_console_state"))
        window = self.window(document=False)
        self.assertTrue(window.toolbox_dock.isHidden())
        window.new_document()
        self.drain()
        self.assertTrue(window.toolbox_dock.isVisible())
        window.close_tab(window.editor_tabs.currentIndex())
        self.drain()
        self.assertIsNone(window.current_tab())
        self.assertTrue(window.toolbox_dock.isHidden())

    def test_files_and_outline_share_visible_project_page_without_recreation(self):
        window = self.window(width=1440)
        navigation = window.toolbox_navigation
        splitter = navigation.project_splitter
        original = [navigation.widget(index) for index in range(9)]
        signals = []
        navigation.currentChanged.connect(signals.append)
        self.assertEqual(navigation.currentIndex(), 0)
        self.assertIs(original[0], window.tree)
        self.assertIs(original[1], window.outline_panel)
        self.assertEqual([splitter.widget(i).findChild(QLabel, "workbenchPanelTitle").text() for i in range(2)],
                         ["项目文件", "章节大纲"])
        for index in (0, 1, 2, 7, 8, 3, 0):
            navigation.setCurrentIndex(index)
            self.drain()
            self.assertEqual(navigation.currentIndex(), index)
            self.assertIs(navigation.currentWidget(), original[index])
            self.assertTrue(navigation.navigationButton(index).isChecked())
            self.assertEqual([navigation.widget(i) for i in range(9)], original)
            self.assertEqual(window.tree.isVisible(), index < 2)
            self.assertEqual(window.outline_panel.isVisible(), index < 2)
            if index < 2:
                self.assertIs(navigation.stack.currentWidget(), splitter)
                self.assertTrue(all(size > 120 for size in splitter.sizes()), splitter.sizes())
        self.assertEqual(signals, [1, 2, 7, 8, 3, 0])
        self.assertFalse(window.compile_authorized_roots)

    def test_shared_project_page_keyboard_entry_and_titles_fit_narrow_large_scale(self):
        window = self.window(width=1080)
        self.addCleanup(self.app.ui_scale_manager.apply_scale, self.app.ui_scale_manager.scale)
        window.set_ui_scale(1.5)
        window.set_toolbox_visible(True)
        window.activateWindow()
        self.drain()
        navigation = window.toolbox_navigation
        for index, target in ((0, window.tree), (1, window.outline_panel.table)):
            navigation.setCurrentIndex(index)
            button = navigation.navigationButton(index)
            button.setFocus()
            self.drain()
            QTest.keyClick(button, Qt.Key.Key_Tab)
            self.drain()
            self.assertIs(self.app.focusWidget(), target)
            self.assertTrue(target.isVisible())
            QTest.keyClick(target, Qt.Key.Key_Backtab)
            self.assertIsNot(self.app.focusWidget(), target)
        for title in navigation.project_splitter.findChildren(QLabel, "workbenchPanelTitle"):
            self.assertTrue(title.visibleRegion().contains(title.rect()), title.text())
            self.assertGreaterEqual(title.width(), title.fontMetrics().horizontalAdvance(title.text()) + 12)

    def test_files_page_refreshes_only_shown_outline_and_preserves_editor(self):
        from tests.test_gui_editor import wait_until
        window = self.window(width=1440)
        tab = window.current_tab()
        with patch.object(window.outline_panel, "set_outline", wraps=window.outline_panel.set_outline) as outline, \
             patch("app.gui.project_panel_controller.AssetIndex.scan") as assets, \
             patch("app.gui.project_panel_controller.list_snapshots") as history, \
             patch.object(window.references_panel, "set_references") as references, \
             patch.object(window.compile, "compile_current") as compile_:
            tab.editor.setPlainText("\\section{Visible}\nText")
            position = tab.editor.textCursor().position()
            scroll = tab.editor.verticalScrollBar().value()
            self.assertTrue(wait_until(lambda: window.outline_panel.table.rowCount() == 1))
            self.assertEqual(window.outline_panel.table.item(0, 0).text(), "Visible")
            self.assertEqual(tab.editor.textCursor().position(), position)
            self.assertEqual(tab.editor.verticalScrollBar().value(), scroll)
            assets.assert_not_called()
            history.assert_not_called()
            references.assert_not_called()
            compile_.assert_not_called()
            window.sidebar_tabs.setCurrentIndex(2)
            outline.reset_mock()
            tab.editor.setPlainText("\\section{Later}\nText")
            self.assertTrue(wait_until(lambda: not window.project_panels._timer.isActive()))
            outline.assert_not_called()
            window.sidebar_tabs.setCurrentIndex(0)
            self.assertEqual(window.outline_panel.table.item(0, 0).text(), "Later")
            outline.assert_called_once()
            window.set_toolbox_visible(False)
            outline.reset_mock()
            tab.editor.setPlainText("\\section{Hidden}\nText")
            self.assertTrue(wait_until(lambda: not window.project_panels._timer.isActive()))
            outline.assert_not_called()
            window.set_toolbox_visible(True)
            self.assertEqual(window.outline_panel.table.item(0, 0).text(), "Hidden")
        self.assertFalse(window.compile_authorized_roots)

    def test_project_split_saved_only_after_accepted_close_and_restored(self):
        window = self.window(width=1440)
        splitter = window.toolbox_navigation.project_splitter
        splitter.moveSplitter(round(sum(splitter.sizes()) * 0.64), 1)
        self.drain()
        ratio = window.source_panels._project_ratio
        self.assertAlmostEqual(ratio, 0.64, delta=0.015)
        self.assertFalse(self.settings.settings.contains("window/project_outline_ratio"))
        window.current_tab().editor.insertPlainText("Unsaved")
        with patch("app.gui.editor_tab_manager.QMessageBox.warning", return_value=QMessageBox.StandardButton.Cancel):
            self.assertFalse(window.close())
        self.assertFalse(self.settings.settings.contains("window/project_outline_ratio"))
        window.current_tab().modified = window.current_tab().dirty = False
        self.assertTrue(window.close())
        self.drain()
        self.assertAlmostEqual(float(self.settings.settings.value("window/project_outline_ratio")), ratio)
        restarted = self.window(width=1440)
        restored = restarted.toolbox_navigation.project_splitter.sizes()
        self.assertAlmostEqual(restored[0] / sum(restored), ratio, delta=0.01)

    def test_project_split_hidden_compact_and_minimum_clamps_preserve_ratio(self):
        window = self.window(width=1440)
        splitter = window.toolbox_navigation.project_splitter
        splitter.moveSplitter(round(sum(splitter.sizes()) * 0.64), 1)
        self.drain()
        ratio = window.source_panels._project_ratio
        for visible in (False, True):
            window.set_toolbox_visible(visible)
            self.drain()
            self.assertAlmostEqual(window.source_panels._project_ratio, ratio)
        splitter.widget(1).setMinimumHeight(540)
        window.resize(1440, 760)
        self.drain()
        self.assertAlmostEqual(window.source_panels._project_ratio, ratio)
        splitter.widget(1).setMinimumHeight(0)
        window.resize(1080, 720)
        self.drain()
        window.set_toolbox_visible(True)
        splitter.moveSplitter(round(sum(splitter.sizes()) * 0.4), 1)
        self.assertAlmostEqual(window.source_panels._project_ratio, ratio)
        window.resize(1440, 1000)
        self.drain()
        sizes = splitter.sizes()
        self.assertAlmostEqual(sizes[0] / sum(sizes), ratio, delta=0.01)
        window.close_tab(window.editor_tabs.currentIndex())
        self.drain()
        self.assertTrue(window.close())
        self.drain()
        self.assertAlmostEqual(float(self.settings.settings.value("window/project_outline_ratio")), ratio)

    def test_explicitly_hidden_navigation_stays_hidden_after_accepted_close(self):
        window = self.window()
        self.assertTrue(window.toolbox_dock.isVisible())
        window.set_toolbox_visible(False)
        self.drain()
        self.assertTrue(window.toolbox_dock.isHidden())
        self.assertTrue(window.close())
        self.drain()
        self.assertTrue(self.settings.settings.contains("window/block_console_state"))
        self.settings.settings.sync()
        self.settings = AppSettings(QSettings(self.settings.settings.fileName(), QSettings.Format.IniFormat))
        restarted = self.window()
        self.assertTrue(restarted.toolbox_dock.isHidden())
        self.assertFalse(restarted.source_panels._wide["toolbox"])

    def test_close_in_compact_mode_preserves_wide_navigation_choice(self):
        for visible in (True, False):
            with self.subTest(visible=visible):
                self.settings.settings.remove("window/block_console_state")
                window = self.window()
                if not visible:
                    window.set_toolbox_visible(False)
                window.current_tab().editor.setFocus()
                self.drain()
                self.assertEqual(window.toolbox_dock.isVisible(), visible)
                self.assertEqual(window.source_panels._wide["toolbox"], visible)
                window.resize(1080, 720)
                self.drain()
                self.assertTrue(window.source_panels._is_compact())
                self.assertTrue(window.toolbox_dock.isHidden())
                self.assertIsNotNone(window.current_tab())
                self.assertTrue(window.close())
                self.drain()
                self.settings.settings.sync()
                self.settings = AppSettings(QSettings(self.settings.settings.fileName(), QSettings.Format.IniFormat))
                restarted = self.window()
                self.assertEqual(restarted.toolbox_dock.isVisible(), visible)
                self.assertEqual(restarted.source_panels._wide["toolbox"], visible)
                self.assertTrue(restarted.close())
                self.drain()

    def test_preferences_write_only_after_accepted_close(self):
        window = self.window()
        horizontal, console = self.choose_layout(window)
        self.assertIsNotNone(console)
        self.assertFalse(self.settings.settings.contains("window/source_pdf_ratio"))
        self.assertFalse(self.settings.settings.contains("window/source_console_ratio"))
        window.current_tab().editor.insertPlainText("Unsaved draft")
        with patch("app.gui.editor_tab_manager.QMessageBox.warning", return_value=QMessageBox.StandardButton.Cancel):
            self.assertFalse(window.close())
        self.assertTrue(isValid(window))
        self.assertFalse(self.settings.settings.contains("window/source_pdf_ratio"))
        self.assertFalse(self.settings.settings.contains("window/source_console_ratio"))
        window.current_tab().modified = window.current_tab().dirty = False
        self.assertTrue(window.close())
        self.drain()
        self.assertAlmostEqual(float(self.settings.settings.value("window/source_pdf_ratio")), horizontal)
        self.assertAlmostEqual(float(self.settings.settings.value("window/source_console_ratio")), console)

    def test_restart_wide_narrow_wide_restores_ratios_without_rebuilding_panes(self):
        window = self.window()
        horizontal, console = self.choose_layout(window)
        self.assertTrue(window.close())
        self.drain()
        self.settings.settings.sync()
        self.settings = AppSettings(QSettings(self.settings.settings.fileName(), QSettings.Format.IniFormat))
        restarted = self.window(width=1080)
        self.addCleanup(self.app.ui_scale_manager.apply_scale, self.app.ui_scale_manager.scale)
        restarted.set_ui_scale(1.5)
        self.drain()
        area = restarted.source_preview_area
        identities = (area.editor, area.pdf, restarted.pdf_panel, restarted.current_tab().editor)
        self.assertTrue(area._is_compact(), (restarted.width(), restarted.minimumWidth(),
                                            area.width(), area._compact_width))
        self.assertAlmostEqual(area.wide_ratio(), horizontal)
        self.assertAlmostEqual(restarted.source_panels._console_ratio, console)
        restarted.source_panels.set_console(True)
        restarted.set_ui_scale(1.0)
        restarted.resize(1920, 1000)
        self.drain()
        self.assertFalse(area._is_compact())
        self.assertEqual((area.editor, area.pdf, restarted.pdf_panel, restarted.current_tab().editor), identities)
        self.assertAlmostEqual(area.splitter.sizes()[0] / sum(area.splitter.sizes()), horizontal, delta=0.01)
        self.assertAlmostEqual(restarted.vertical_splitter.sizes()[1] / sum(restarted.vertical_splitter.sizes()), console, delta=0.02)

    def test_resize_clamping_compact_and_welcome_do_not_replace_wide_preferences(self):
        window = self.window()
        horizontal, console = self.choose_layout(window)
        area = window.source_preview_area
        area.editor.setMinimumWidth(1000)
        window.resize(1450, 750)
        self.drain()
        self.assertAlmostEqual(area.wide_ratio(), horizontal)
        self.assertAlmostEqual(window.source_panels._console_ratio, console)
        area.editor.setMinimumWidth(0)
        window.resize(960, 700)
        self.drain()
        window.source_panels.set_console(False)
        window.close_tab(window.editor_tabs.currentIndex())
        self.drain()
        self.assertIsNone(window.current_tab())
        self.assertTrue(window.close())
        self.drain()
        self.assertAlmostEqual(float(self.settings.settings.value("window/source_pdf_ratio")), horizontal)
        self.assertAlmostEqual(float(self.settings.settings.value("window/source_console_ratio")), console)

    def test_missing_and_invalid_settings_keep_default_layout(self):
        for value in (None, "broken", [], {}, -1, 0, 1, float("nan"), float("inf")):
            with self.subTest(value=value):
                self.settings.settings.remove("window/source_pdf_ratio")
                self.settings.settings.remove("window/source_console_ratio")
                self.settings.settings.remove("window/project_outline_ratio")
                if value is not None:
                    self.settings.settings.setValue("window/source_pdf_ratio", value)
                    self.settings.settings.setValue("window/source_console_ratio", value)
                    self.settings.settings.setValue("window/project_outline_ratio", value)
                window = self.window(document=False)
                self.assertAlmostEqual(window.source_preview_area.wide_ratio(), 790 / (790 + 650))
                self.assertIsNone(window.source_panels._console_ratio)
                self.assertAlmostEqual(window.source_panels._project_ratio, 0.55)
                window.close()
                self.drain()

    def test_source_memory_does_not_apply_to_independent_block_area(self):
        self.settings.settings.setValue("window/source_pdf_ratio", 0.7)
        self.settings.settings.setValue("window/source_console_ratio", 0.3)
        window = self.window()
        block = EditorPdfArea(QWidget(), QWidget())
        try:
            self.assertAlmostEqual(window.source_preview_area.wide_ratio(), 0.7)
            self.assertAlmostEqual(block.wide_ratio(), 0.6)
            window.source_panels.set_active(False)
            window.vertical_splitter.moveSplitter(500, 1)
            self.assertAlmostEqual(window.source_panels._console_ratio, 0.3)
            self.assertTrue(window.close())
            self.drain()
            self.assertAlmostEqual(float(self.settings.settings.value("window/source_console_ratio")), 0.3)
        finally:
            block.deleteLater()
            self.drain()

    def test_console_tab_minimum_and_unavailable_preview_do_not_replace_preferences(self):
        window = self.window()
        horizontal, console = self.choose_layout(window)
        tall_page = QWidget()
        tall_page.setMinimumHeight(580)
        index = window.bottom_tabs.addTab(tall_page, "Synthetic tall panel")
        window.bottom_tabs.setCurrentIndex(index)
        window.source_preview_area.set_preview_available(False)
        self.drain()
        window.source_preview_area.splitter.moveSplitter(500, 1)
        self.assertGreaterEqual(window.bottom_panel.height(), 580)
        self.assertAlmostEqual(window.source_preview_area.wide_ratio(), horizontal)
        self.assertAlmostEqual(window.source_panels._console_ratio, console)
        self.assertTrue(window.close())
        self.drain()
        self.assertAlmostEqual(float(self.settings.settings.value("window/source_pdf_ratio")), horizontal)
        self.assertAlmostEqual(float(self.settings.settings.value("window/source_console_ratio")), console)

    def test_block_mode_round_trip_and_close_preserve_source_preferences(self):
        from app.core.blocks.project_repository import load_project
        from app.gui.block_mode import _install_session, _set_block_mode
        from app.gui.blocks.project_session import ProjectSession
        from tests.v1_fixtures import create_project

        window = self.window()
        horizontal, console = self.choose_layout(window)
        source_editor = window.current_tab().editor
        pdf_panel = window.pdf_panel
        sample = create_project(Path(self.temp.name).resolve() / "block-fixture", "block")
        loaded = load_project(sample.root.parent)
        session = ProjectSession(**{key: loaded[key] for key in
            ("registry", "layout", "sources", "document_theme", "project_dir")})
        _install_session(window, session)
        _set_block_mode(window, True)
        self.drain()
        self.assertFalse(window.source_panels._active)
        window.block_preview_area.splitter.moveSplitter(500, 1)
        self.assertAlmostEqual(window.source_preview_area.wide_ratio(), horizontal)
        self.assertAlmostEqual(window.source_panels._console_ratio, console)
        _set_block_mode(window, False)
        self.drain()
        self.assertIs(window.current_tab().editor, source_editor)
        self.assertIs(window.pdf_panel, pdf_panel)
        self.assertAlmostEqual(window.source_preview_area.wide_ratio(), horizontal)
        self.assertAlmostEqual(window.source_panels._console_ratio, console)
        _set_block_mode(window, True)
        self.assertTrue(window.close())
        self.drain()
        self.assertAlmostEqual(float(self.settings.settings.value("window/source_pdf_ratio")), horizontal)
        self.assertAlmostEqual(float(self.settings.settings.value("window/source_console_ratio")), console)
