from __future__ import annotations

import os
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.gui.math_keyboard import CATEGORY_LABELS, MathKeyButton, MathKeyboard


def app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def find_button(keyboard: MathKeyboard, action: str) -> MathKeyButton:
    for button in keyboard.findChildren(MathKeyButton):
        if button.action == action:
            return button
    raise AssertionError(f"no button for action {action}")


class MathKeyboardTests(TestCase):
    def setUp(self) -> None:
        app()

    def test_category_pages_exist(self) -> None:
        keyboard = MathKeyboard()
        self.assertEqual(keyboard.stack.count(), len(CATEGORY_LABELS) + 1)
        self.assertEqual(keyboard.stack.indexOf(keyboard.letters_row), len(CATEGORY_LABELS))
        self.assertEqual(keyboard.stack.currentIndex(), 0)  # 基础 is default

    def test_structure_button_emits_action(self) -> None:
        keyboard = MathKeyboard()
        emitted: list[str] = []
        keyboard.actionRequested.connect(emitted.append)

        find_button(keyboard, "structure:fraction").click()
        find_button(keyboard, "text:7").click()
        find_button(keyboard, "command:times").click()
        find_button(keyboard, "cursor:right").click()
        find_button(keyboard, "delete").click()

        self.assertEqual(
            emitted,
            ["structure:fraction", "text:7", "command:times", "cursor:right", "delete"],
        )

    def test_category_switch_keeps_editor_state(self) -> None:
        keyboard = MathKeyboard()
        editor_placeholder = "state-must-survive"
        keyboard.setProperty("editorState", editor_placeholder)

        for index, key in enumerate(CATEGORY_LABELS):
            keyboard._switch_category(key)
            self.assertEqual(keyboard.stack.currentIndex(), index)
            self.assertEqual(keyboard.property("editorState"), editor_placeholder)

    def test_abc_toggle_shows_letters_row(self) -> None:
        keyboard = MathKeyboard()
        self.assertFalse(keyboard.letters_row.isVisibleTo(keyboard))
        find_button(keyboard, "toggle:abc").click()
        self.assertTrue(keyboard.letters_row.isVisibleTo(keyboard))
        find_button(keyboard, "toggle:abc").click()
        self.assertFalse(keyboard.letters_row.isVisibleTo(keyboard))

    def test_responsive_layout_wide_and_narrow(self) -> None:
        keyboard = MathKeyboard()
        keyboard.resize(1000, 420)
        app().processEvents()
        self.assertEqual(keyboard.width(), 1000)

        keyboard.resize(700, 620)
        app().processEvents()
        self.assertEqual(keyboard.width(), 700)

        pixmap = keyboard.grab()
        self.assertFalse(pixmap.isNull())

    def test_keyboard_paint_smoke(self) -> None:
        keyboard = MathKeyboard()
        keyboard.resize(1000, 420)
        keyboard.show()
        app().processEvents()
        for key in CATEGORY_LABELS:
            keyboard._switch_category(key)
            app().processEvents()
            self.assertFalse(keyboard.grab().isNull())

    def test_structural_slots_have_no_solid_fill(self) -> None:
        slot_centers = {
            "frac": (0, -10), "sqrt": (9, 1), "nroot": (9, 1),
            "abs": (0, 0), "script": (7, -9), "sub": (7, 10),
            "matrix": (-7, -7), "cases": (7, -7),
        }
        background = QColor(252, 252, 252)
        for kind, (x, y) in slot_centers.items():
            with self.subTest(kind=kind):
                button = MathKeyButton(kind, kind, "structure:test")
                button.resize(120, 50)
                canvas = QImage(120, 50, QImage.Format.Format_ARGB32)
                canvas.fill(background)
                painter = QPainter(canvas)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                button._draw_preview(painter)
                painter.end()
                self.assertEqual(canvas.pixelColor(60 + x, 25 + y), background)
                self.assertTrue(any(canvas.pixelColor(px, py) != background
                                    for px in range(30, 90) for py in range(5, 45)))

    def test_key_artwork_stays_inside_compact_button_padding(self) -> None:
        keyboard = MathKeyboard()
        background = QColor(252, 252, 252)
        for button in keyboard.findChildren(MathKeyButton):
            for width, height in ((42, 40), (120, 40)):
                with self.subTest(action=button.action, width=width):
                    button.resize(width, height)
                    canvas = QImage(width, height, QImage.Format.Format_ARGB32)
                    canvas.fill(background)
                    painter = QPainter(canvas)
                    painter.setPen(QColor(38, 38, 38))
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    button._draw_preview(painter)
                    painter.end()
                    pixels = [(x, y) for x in range(width) for y in range(height)
                              if canvas.pixelColor(x, y) != background]
                    self.assertTrue(pixels)
                    self.assertGreaterEqual(min(x for x, _ in pixels), 6)
                    self.assertLess(max(x for x, _ in pixels), width - 6)
                    self.assertGreaterEqual(min(y for _, y in pixels), 3)
                    self.assertLess(max(y for _, y in pixels), height - 3)
