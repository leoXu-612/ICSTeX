"""Responsive layout tests: breakpoints, welcome reflow, tab bars, PDF tools."""
from __future__ import annotations

import os
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.gui.responsive.helpers import LayoutBreakpoints, configure_tab_bar, resolve_layout_mode


def _app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class BreakpointTests(TestCase):
    def test_resolution(self) -> None:
        self.assertEqual(resolve_layout_mode(1200), "wide")
        self.assertEqual(resolve_layout_mode(1100), "wide")
        self.assertEqual(resolve_layout_mode(900), "medium")
        self.assertEqual(resolve_layout_mode(760), "medium")
        self.assertEqual(resolve_layout_mode(600), "narrow")
        self.assertEqual(LayoutBreakpoints.WIDE, 1100)
        self.assertEqual(LayoutBreakpoints.MEDIUM, 760)


class WelcomeReflowTests(TestCase):
    def setUp(self) -> None:
        _app()
        from app.gui.welcome_page import WelcomePage

        self.page = WelcomePage()

    def tearDown(self) -> None:
        self.page.deleteLater()

    def test_welcome_reflows_to_4_2_1_columns(self) -> None:
        def rows(grid):
            return [grid.getItemPosition(index)[0] for index in range(grid.count())]

        self.page._apply_layout_mode("wide")
        self.assertEqual(rows(self.page.action_grid), [0, 0, 0, 0])
        self.assertEqual(rows(self.page.cards_grid), [0, 0])

        self.page._apply_layout_mode("medium")
        self.assertEqual(rows(self.page.action_grid), [0, 0, 1, 1])
        self.assertEqual(rows(self.page.cards_grid), [0, 1])

        self.page._apply_layout_mode("narrow")
        self.assertEqual(rows(self.page.action_grid), [0, 1, 2, 3])
        self.assertEqual(rows(self.page.cards_grid), [0, 1])

    def test_welcome_is_scrollable(self) -> None:
        self.assertTrue(self.page.scroll.widgetResizable())
        self.assertIsNotNone(self.page.scroll.widget())


class TabBarTests(TestCase):
    def test_source_tabs_configured(self) -> None:
        from itertools import count
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from PySide6.QtCore import QSettings

        from app.core.settings import AppSettings
        from app.gui.main_window import MainWindow

        tmp = TemporaryDirectory()
        settings = AppSettings(QSettings(str(Path(tmp.name) / "t.ini"), QSettings.Format.IniFormat))
        window = MainWindow(settings_store=settings)
        tab_bar = window.editor_tabs.tabBar()
        self.assertFalse(tab_bar.expanding())
        self.assertTrue(tab_bar.usesScrollButtons())
        self.assertEqual(tab_bar.elideMode(), Qt.TextElideMode.ElideRight)
        window.close()
        tmp.cleanup()


class PdfToolbarResponsiveTests(TestCase):
    def test_narrow_toolbar_shows_more_menu(self) -> None:
        _app()
        from app.gui.pdf_panel import PdfPanel

        panel = PdfPanel()
        panel.show()
        panel.resize(500, 700)
        QApplication.processEvents()
        panel._update_toolbar_mode()
        self.assertTrue(panel._more_button.isVisibleTo(panel))
        self.assertFalse(panel._secondary_panel.isVisibleTo(panel))

        panel.resize(1200, 700)
        QApplication.processEvents()
        panel._update_toolbar_mode()
        self.assertFalse(panel._more_button.isVisibleTo(panel))
        self.assertTrue(panel._secondary_panel.isVisibleTo(panel))
        panel.close()


class MainToolbarStructureTests(TestCase):
    def test_main_toolbar_is_qtoolbar_with_core_actions(self) -> None:
        from itertools import count
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QToolBar

        from app.core.settings import AppSettings
        from app.gui.main_window import MainWindow

        tmp = TemporaryDirectory()
        settings = AppSettings(QSettings(str(Path(tmp.name) / "t.ini"), QSettings.Format.IniFormat))
        window = MainWindow(settings_store=settings)
        toolbar = window.findChild(QToolBar, "mainToolbar")
        self.assertIsNotNone(toolbar)
        action_texts = [action.text() for action in toolbar.actions()]
        self.assertIn("保存", action_texts)
        self.assertIn("编译", action_texts)
        self.assertEqual(toolbar.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonIconOnly)
        window.close()
        tmp.cleanup()
