from __future__ import annotations

import os
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.gui.math_editor_widget import MathEditorWidget


def app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class MathEditorWidgetTests(TestCase):
    def setUp(self) -> None:
        app()

    def test_inline_fraction_no_newline(self) -> None:
        widget = MathEditorWidget()
        widget.set_latex("")
        widget.insert_structure("fraction")
        self.assertEqual(widget.latex(), r"\frac{}{}")

        widget.type_key("a")
        self.assertEqual(widget.latex(), r"\frac{a}{}")
        widget.cursor_tab()
        widget.type_key("b")
        self.assertEqual(widget.latex(), r"\frac{a}{b}")
        self.assertNotIn("\n", widget.latex())

    def test_nested_structure_editing(self) -> None:
        widget = MathEditorWidget()
        widget.set_latex("")
        widget.insert_structure("fraction")
        widget.type_key("x")
        widget.insert_structure("superscript")
        widget.type_key("2")
        widget.cursor_right()  # exit superscript back into the numerator
        widget.type_key("+")
        widget.type_key("1")
        self.assertEqual(widget.latex(), r"\frac{x^2+1}{}")

        widget.cursor_down()  # numerator -> denominator
        widget.insert_structure("sqrt")
        widget.type_key("y")
        widget.type_key("_")
        widget.type_key("1")
        widget.cursor_right()  # exit subscript into the radicand
        widget.type_key("+")
        widget.type_key("y")
        widget.type_key("_")
        widget.type_key("2")
        self.assertEqual(widget.latex(), r"\frac{x^2+1}{\sqrt{y_1+y_2}}")

    def test_read_back_and_modify_existing_formula(self) -> None:
        widget = MathEditorWidget()
        widget.set_latex(r"E=mc^2")
        self.assertEqual(widget.latex(), r"E=mc^2")

        # Position the caret right after "E=" (before the mc^2 script).
        widget.cursor_home()
        widget.cursor_right()  # enter the base slot of the mc^2 script
        for _ in range(2):
            widget.cursor_right()
        for char in ("\\", "g", "a", "m", "m", "a", " "):
            widget.type_key(char)

        self.assertEqual(widget.latex(), r"E=\gamma mc^2")

    def test_editing_continuity_undo_redo_delete(self) -> None:
        widget = MathEditorWidget()
        widget.set_latex("x")
        widget.type_key("^")
        widget.type_key("2")
        self.assertEqual(widget.latex(), "x^2")

        widget.cursor_right()  # back into the root sequence
        widget.insert_structure("fraction")
        widget.type_key("a")
        widget.cursor_tab()
        widget.type_key("b")
        self.assertEqual(widget.latex(), r"x^2\frac{a}{b}")

        widget.undo()  # remove "b"
        self.assertEqual(widget.latex(), r"x^2\frac{a}{}")
        widget.undo()  # remove "a" from the empty fraction
        self.assertEqual(widget.latex(), r"x^2\frac{}{}")
        widget.undo()  # remove the fraction
        self.assertEqual(widget.latex(), "x^2")
        widget.undo()  # remove the superscript content
        self.assertEqual(widget.latex(), "x^{}")
        widget.undo()  # remove the superscript node
        self.assertEqual(widget.latex(), "x")
        widget.redo()
        self.assertEqual(widget.latex(), "x^{}")
        widget.redo()
        self.assertEqual(widget.latex(), "x^2")
        widget.redo()
        self.assertEqual(widget.latex(), r"x^2\frac{}{}")
        widget.redo()
        self.assertEqual(widget.latex(), r"x^2\frac{a}{}")
        widget.redo()
        self.assertEqual(widget.latex(), r"x^2\frac{a}{b}")

        widget.delete_backspace()  # remove "b" in the denominator
        self.assertEqual(widget.latex(), r"x^2\frac{a}{}")
        widget.delete_backspace()  # empty denominator: exit to the root
        widget.delete_backspace()  # remove the script before the fraction
        self.assertEqual(widget.latex(), r"\frac{a}{}")

    def test_shortcut_conversions(self) -> None:
        widget = MathEditorWidget()
        widget.set_latex("")
        for char in ("\\", "a", "l", "p", "h", "a", " "):
            widget.type_key(char)
        self.assertEqual(widget.latex(), r"\alpha")

        widget.set_latex("")
        for char in ("\\", "f", "r", "a", "c", " "):
            widget.type_key(char)
        self.assertEqual(widget.latex(), r"\frac{}{}")

        widget.set_latex("")
        widget.type_key("/")
        self.assertEqual(widget.latex(), r"\frac{}{}")

    def test_unknown_command_round_trips_through_widget(self) -> None:
        widget = MathEditorWidget()
        widget.set_latex(r"\mystery{a}{b}")
        self.assertEqual(widget.latex(), r"\mystery{a}{b}")

    def test_selection_delete(self) -> None:
        widget = MathEditorWidget()
        widget.set_latex("abcd")
        widget.select_all()
        widget.delete_backspace()
        self.assertEqual(widget.latex(), "")

    def test_paint_smoke_renders_supported_and_fallback_content(self) -> None:
        widget = MathEditorWidget()
        widget.resize(420, 180)
        widget.set_latex(r"\frac{x^2+1}{\sqrt{y_1+y_2}} + \sum_{i=0}^{n} a_i")
        pixmap = widget.grab()
        self.assertFalse(pixmap.isNull())
        self.assertGreater(pixmap.width(), 0)

        widget.set_latex(r"\begin{matrix}a&b\\c&d\end{matrix}")
        pixmap = widget.grab()
        self.assertFalse(pixmap.isNull())

    def test_mouse_click_does_not_lose_content(self) -> None:
        widget = MathEditorWidget()
        widget.resize(420, 180)
        widget.set_latex("abc+def")
        widget._hit_test(30, 40)
        self.assertEqual(widget.latex(), "abc+def")
