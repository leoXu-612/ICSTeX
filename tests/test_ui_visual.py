from __future__ import annotations

import os
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt, QEvent
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolBar

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


class WorkbenchVisualSmokeTests(TestCase):
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
            self.assertGreaterEqual(window.main_splitter.widget(1).width(), 360)

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
