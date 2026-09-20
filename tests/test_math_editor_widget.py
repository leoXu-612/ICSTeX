from __future__ import annotations

import os
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QInputMethodEvent, QKeyEvent, QTextCharFormat
from PySide6.QtTest import QTest

from app.gui.math_editor_widget import MathEditorWidget


def app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class MathEditorWidgetTests(TestCase):
    def setUp(self) -> None:
        app()

    def test_spaced_text_uses_same_boundaries_for_mouse_and_editing(self):
        from PySide6.QtGui import QFont, QFontMetricsF
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.set_latex("abc")
        font, _small, _big, box = widget._paint_layout()
        text = box.children[0][0]
        plain = QFont(font)
        plain.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0)
        self.assertGreater(text.w, QFontMetricsF(plain).horizontalAdvance("abc"))
        widget._hit_test(text.x + text.boundaries[2] + 0.1, text.y + text.h / 2)
        caret = widget._caret_rect(box, font)
        self.assertAlmostEqual(caret.center().x(), text.x + text.boundaries[2])
        widget.type_key("X")
        self.assertEqual(widget.latex(), "abXc")
        widget.undo()
        self.assertEqual(widget.latex(), "abc")

    def test_nested_layout_bounds_and_fraction_rules_leave_clearance(self):
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.set_latex(r"\frac{\frac{a+b}{c+d}}{x_i^2}+\sqrt{\frac{x}{y}}"
                         r"+x^{\frac{\frac{\frac{a}{b}}{c}}{d}}+x^{\frac{\frac{\frac{a}{b}}{c}}{d}}_i")
        original = widget.latex()
        _font, _small, _big, root = widget._paint_layout()

        def check(box):
            if box.kind == "frac":
                numerator, denominator = [item[0] for item in box.children]
                rule_y = box.y + box.baseline
                self.assertGreaterEqual(rule_y - (numerator.y + numerator.h), 5.0)
                self.assertGreaterEqual(denominator.y - rule_y, 5.0)
            if box.kind == "script" and box.node.super is not None and box.node.sub is not None:
                _base, upper, lower = [item[0] for item in box.children]
                self.assertGreaterEqual(lower.y - (upper.y + upper.h), 4.0)
            for child, x, y in box.children:
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(x + child.w, box.w + 0.001)
                self.assertLessEqual(y + child.h, box.h + 0.001)
                check(child)

        check(root)
        self.assertEqual(widget.latex(), original)
        self.assertFalse(widget.can_undo)

    def test_script_spacing_and_painted_fonts_match_the_measured_slots(self):
        from unittest.mock import Mock
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.set_latex("x^{ab}_{cd}")
        font, small, big, root = widget._paint_layout()
        script = root.children[0][0]
        base, upper, lower = [entry[0] for entry in script.children]
        self.assertGreaterEqual(upper.x - (base.x + base.w), 5.0)
        self.assertLess(upper.y + upper.baseline, base.y + base.baseline)
        self.assertGreater(lower.y, base.y + base.baseline)
        self.assertGreater(lower.y - (upper.y + upper.h), 4.0)
        painter = Mock()
        drawn = []
        painter.drawText.side_effect = lambda point, text: drawn.append(
            (text, painter.setFont.call_args.args[0].pointSizeF()))
        widget._draw(painter, root, font, small, big)
        self.assertEqual(drawn, [("x", font.pointSizeF()), ("ab", small.pointSizeF()),
                                 ("cd", small.pointSizeF())])

    def test_wide_operator_limits_do_not_overlap_body_or_duplicate_glyph(self):
        from unittest.mock import Mock
        from app.core.formula_tree import BigOp, MathSequence, parse_math_latex
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        operator = BigOp(symbol="sum", lower=parse_math_latex("i=12345"),
                         upper=parse_math_latex("n+100"), body=parse_math_latex("x"))
        widget.root = MathSequence(items=[operator])
        font, small, big, root = widget._paint_layout()
        box = root.children[0][0]
        symbol, upper, lower, body = [entry[0] for entry in box.children]
        self.assertGreaterEqual(body.x - max(item.x + item.w for item in (symbol, upper, lower)), 8.0)
        self.assertGreaterEqual(symbol.y - (upper.y + upper.h), 5.0)
        self.assertGreaterEqual(lower.y - (symbol.y + symbol.h), 5.0)
        painter = Mock()
        drawn = []
        painter.drawText.side_effect = lambda point, text: drawn.append(
            (text, painter.setFont.call_args.args[0].pointSizeF()))
        widget._draw(painter, root, font, small, big)
        self.assertEqual(drawn, [("∑", big.pointSizeF()), ("n+100", small.pointSizeF()),
                                ("i=12345", small.pointSizeF()), ("x", font.pointSizeF())])

    def test_input_method_commit_is_inserted_once_and_undoable(self):
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.set_latex("x+")
        event = QInputMethodEvent()
        event.setCommitString("中文")
        QApplication.sendEvent(widget, event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(widget.latex(), "x+中文")
        widget.undo()
        self.assertEqual(widget.latex(), "x+")

    def test_preedit_is_rendered_with_attributes_but_not_exported_or_undoable(self):
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.resize(400, 100)
        widget.set_latex("x+")
        style = QTextCharFormat()
        style.setForeground(QColor("red"))
        style.setBackground(QColor("yellow"))
        style.setFontUnderline(True)
        attributes = [
            QInputMethodEvent.Attribute(QInputMethodEvent.AttributeType.TextFormat, 0, 5, style),
            QInputMethodEvent.Attribute(QInputMethodEvent.AttributeType.Cursor, 2, 1, QColor("blue")),
        ]
        original = widget.grab().toImage()
        original_caret = widget.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle)
        changes = []
        widget.latexChanged.connect(changes.append)
        QApplication.sendEvent(widget, QInputMethodEvent("zhong", attributes))
        self.assertTrue(widget.has_preedit)
        self.assertEqual(widget.latex(), "x+")
        self.assertFalse(widget.can_undo)
        self.assertGreater(widget.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle).x(), original_caret.x())
        self.assertNotEqual(widget.grab().toImage(), original)
        QApplication.sendEvent(widget, QInputMethodEvent())
        self.assertFalse(widget.has_preedit)
        self.assertEqual(widget.grab().toImage(), original)
        self.assertEqual(changes, [])

    def test_composition_replaces_selection_in_one_undo_and_preserves_other_nodes(self):
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.set_latex(r"\unknown{a}+abc")
        original = widget.latex()
        widget.cursor_end()
        # The existing structured cursor has a separate end-of-slot boundary.
        widget.cursor_left(select=True)
        widget.cursor_left(select=True)
        widget.cursor_left(select=True)
        self.assertEqual(widget.selected_latex(), "bc")
        QApplication.sendEvent(widget, QInputMethodEvent("zhongwen", []))
        self.assertEqual(widget.latex(), r"\unknown{a}+a")
        event = QInputMethodEvent()
        event.setCommitString("中文")
        QApplication.sendEvent(widget, event)
        self.assertEqual(widget.latex(), r"\unknown{a}+a中文")
        widget.undo()
        self.assertEqual(widget.latex(), original)
        self.assertFalse(widget.can_undo)
        widget.redo()
        self.assertEqual(widget.latex(), r"\unknown{a}+a中文")

    def test_reconversion_is_utf16_scoped_and_does_not_damage_a_fraction(self):
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.insert_structure("fraction")
        widget.insert_text("a\U0001f642")
        original = widget.latex()
        self.assertEqual(widget.inputMethodQuery(Qt.InputMethodQuery.ImSurroundingText), "a\U0001f642")
        self.assertEqual(widget.inputMethodQuery(Qt.InputMethodQuery.ImCursorPosition), 3)
        event = QInputMethodEvent()
        event.setCommitString("中", -2, 2)
        QApplication.sendEvent(widget, event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(widget.latex(), r"\frac{a中}{}")
        widget.undo()
        self.assertEqual(widget.latex(), original)
        invalid = QInputMethodEvent()
        invalid.setCommitString("BAD", -1, 1)
        QApplication.sendEvent(widget, invalid)
        self.assertFalse(invalid.isAccepted())
        self.assertEqual(widget.latex(), original)

    def test_commit_and_next_preedit_have_separate_undo_and_cancel_keeps_commit(self):
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.set_latex("x+")
        event = QInputMethodEvent("wen", [])
        event.setCommitString("中")
        QApplication.sendEvent(widget, event)
        self.assertEqual(widget.latex(), "x+中")
        self.assertTrue(widget.has_preedit)
        QApplication.sendEvent(widget, QInputMethodEvent())
        widget.undo()
        self.assertEqual(widget.latex(), "x+")
        self.assertFalse(widget.can_undo)

    def test_partial_commits_after_selection_keep_distinct_undo_boundaries(self):
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.set_latex("old")
        widget.select_all()
        QApplication.sendEvent(widget, QInputMethodEvent("zhong", []))
        event = QInputMethodEvent("wen", [])
        event.setCommitString("中")
        QApplication.sendEvent(widget, event)
        event = QInputMethodEvent()
        event.setCommitString("文")
        QApplication.sendEvent(widget, event)
        self.assertEqual(widget.latex(), "中文")
        widget.undo()
        self.assertEqual(widget.latex(), "中")
        widget.undo()
        self.assertEqual(widget.latex(), "old")
        self.assertFalse(widget.can_undo)

    def test_surrounding_structure_is_atomic_and_selection_query_is_plain_text(self):
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.set_latex(r"a\frac{x}{y}b")
        self.assertEqual(widget.inputMethodQuery(Qt.InputMethodQuery.ImSurroundingText), "a\ufffcb")
        widget.select_all()
        self.assertEqual(widget.inputMethodQuery(Qt.InputMethodQuery.ImCurrentSelection), "a\ufffcb")
        event = QInputMethodEvent()
        event.setCommitString("中文")
        QApplication.sendEvent(widget, event)
        self.assertEqual(widget.latex(), "中文")
        widget.undo()
        self.assertEqual(widget.latex(), r"a\frac{x}{y}b")

    def test_typing_replaces_selection_in_one_undo(self):
        widget = MathEditorWidget()
        widget.set_latex("abc")
        widget.select_all()
        widget.type_key("x")
        self.assertEqual(widget.latex(), "x")
        widget.undo()
        self.assertEqual(widget.latex(), "abc")

    def test_arrow_motion_does_not_select_or_delete_text(self):
        widget = MathEditorWidget()
        widget.set_latex("abc")
        widget.cursor_home()
        widget.cursor_right()
        widget.type_key("x")
        self.assertEqual(widget.latex(), "axbc")

    def test_vertical_arrows_visit_super_base_sub_without_editing(self):
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.set_latex(r"x^{ab}_{cd}")
        before = widget.latex()
        changes = []
        widget.latexChanged.connect(changes.append)
        for key, role in ((Qt.Key.Key_Up, "super"), (Qt.Key.Key_Down, "base"),
                          (Qt.Key.Key_Down, "sub"), (Qt.Key.Key_Up, "base"),
                          (Qt.Key.Key_Up, "super")):
            QTest.keyClick(widget, key)
            self.assertEqual(widget.path[-1][0], role)
        self.assertEqual(widget.latex(), before)
        self.assertEqual(changes, [])
        self.assertFalse(widget.can_undo)
        self.assertIsNone(widget.anchor)
        widget.cursor_end()
        widget.type_key("z")
        self.assertEqual(widget.latex(), r"x^{abz}_{cd}")
        widget.undo()
        self.assertEqual(widget.latex(), before)

    def test_missing_script_is_not_created_by_navigation(self):
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.set_latex("x^2")
        widget.cursor_down()
        self.assertEqual(widget.path[-1][0], "root")
        widget.cursor_up()
        self.assertEqual(widget.path[-1][0], "super")
        widget.cursor_up()  # no higher level; do not jump down to the base
        self.assertEqual(widget.path[-1][0], "super")
        widget.cursor_down()
        self.assertEqual(widget.path[-1][0], "base")
        widget.cursor_down()
        self.assertEqual(widget.path[-1][0], "base")
        self.assertEqual(widget.latex(), "x^2")
        self.assertFalse(widget.can_undo)

    def test_horizontal_entry_repaints_the_caret_without_editing(self):
        from unittest.mock import patch
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.set_latex(r"\frac{a}{b}")
        widget.cursor_home()
        with patch.object(widget, "update") as repaint:
            widget.cursor_right()
            repaint.assert_called()
        self.assertEqual(widget.path[-1][0], "frac_num")
        self.assertEqual(widget.latex(), r"\frac{a}{b}")

    def test_exit_nested_structure_keeps_long_prefix_on_both_sides(self):
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                widget = MathEditorWidget()
                self.addCleanup(widget.deleteLater)
                widget.set_latex("longprefix+")
                widget.insert_structure("fraction")
                widget.type_key("a")
                if direction < 0:
                    widget.cursor_home()
                    widget.cursor_left()
                else:
                    widget.cursor_right()
                widget.type_key("Y")
                expected = r"longprefix+Y\frac{a}{}" if direction < 0 else r"longprefix+\frac{a}{}Y"
                self.assertEqual(widget.latex(), expected)

    def test_vertical_navigation_exits_inner_root_and_aligns_fraction_caret(self):
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.insert_structure("fraction")
        widget.insert_structure("sqrt")
        widget.type_key("a")
        widget.cursor_down()
        self.assertEqual(widget.path[-1][0], "frac_den")
        widget.type_key("b")
        self.assertEqual(widget.latex(), r"\frac{\sqrt{a}}{b}")
        widget.set_latex(r"\frac{abcdef}{xy}")
        widget.cursor_home()
        widget.cursor_up()
        self.assertEqual(widget.path[-1][0], "frac_num")
        widget.cursor_home()
        widget.cursor_down()
        self.assertEqual(widget.path[-1][0], "frac_den")
        self.assertEqual(widget.index, 0)
        widget.type_key("z")
        self.assertEqual(widget.latex(), r"\frac{abcdef}{zxy}")

    def test_sum_limits_are_reachable_from_body(self):
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        widget.insert_structure("sum")
        for key, role in ((Qt.Key.Key_Up, "upper"), (Qt.Key.Key_Down, "body"),
                          (Qt.Key.Key_Down, "lower"), (Qt.Key.Key_Up, "body")):
            QTest.keyClick(widget, key)
            self.assertEqual(widget.path[-1][0], role)

    def test_shift_selection_copy_and_replacement_preserve_adjacent_text(self):
        widget = MathEditorWidget()
        widget.set_latex("abcd")
        widget.cursor_home()
        widget.cursor_right()
        widget.cursor_right(select=True)
        widget.cursor_right(select=True)
        self.assertEqual(widget.selected_latex(), "bc")
        widget.paste_clipboard("X")
        self.assertEqual(widget.latex(), "aXd")
        widget.undo()
        self.assertEqual(widget.latex(), "abcd")

    def test_tab_key_reaches_fraction_denominator(self):
        widget = MathEditorWidget()
        widget.insert_structure("fraction")
        widget.type_key("a")
        QTest.keyClick(widget, Qt.Key.Key_Tab)
        widget.type_key("b")
        self.assertEqual(widget.latex(), r"\frac{a}{b}")
        QTest.keyClick(widget, Qt.Key.Key_Backtab)
        self.assertEqual(widget.path[-1][0], "frac_num")

    def test_pending_command_can_be_corrected_and_committed(self):
        widget = MathEditorWidget()
        for char in r"\alphx":
            widget.type_key(char)
        widget.delete_backspace()
        widget.type_key("a")
        self.assertEqual(widget.pending_command, r"\alpha")
        QTest.keyClick(widget, Qt.Key.Key_Return)
        self.assertEqual(widget.latex(), r"\alpha")
        self.assertEqual(widget.pending_command, "")

    def test_mutations_publish_once_and_navigation_does_not_publish_latex(self):
        widget = MathEditorWidget()
        changes = []
        widget.latexChanged.connect(changes.append)
        widget.type_key("/")
        self.assertEqual(changes, [r"\frac{}{}"])
        widget.cursor_right()
        self.assertEqual(len(changes), 1)
        widget.undo()
        self.assertEqual(changes[-1], "")

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

    def test_paste_plain_text_at_cursor(self) -> None:
        widget = MathEditorWidget()
        widget.set_latex("x")
        widget.paste_clipboard("+y^2")
        self.assertEqual(widget.latex(), "x+y^2")

    def test_paste_wrapped_formula_strips_wrapper(self) -> None:
        widget = MathEditorWidget()
        widget.set_latex("")
        widget.paste_clipboard(r"\(\frac{a}{b}\)")
        self.assertEqual(widget.latex(), r"\frac{a}{b}")

        widget.set_latex("")
        widget.paste_clipboard(r"$E=mc^2$")
        self.assertEqual(widget.latex(), r"E=mc^2")

    def test_paste_replaces_selection(self) -> None:
        widget = MathEditorWidget()
        widget.set_latex("abc+def")
        widget.select_all()
        widget.paste_clipboard(r"\sqrt{x}")
        self.assertEqual(widget.latex(), r"\sqrt{x}")

    def test_paste_is_undoable(self) -> None:
        widget = MathEditorWidget()
        widget.set_latex("x")
        widget.paste_clipboard("+1")
        self.assertEqual(widget.latex(), "x+1")
        widget.undo()
        self.assertEqual(widget.latex(), "x")

    def test_paste_unknown_content_is_lossless(self) -> None:
        widget = MathEditorWidget()
        widget.set_latex("")
        widget.paste_clipboard(r"\begin{matrix}a&b\\c&d\end{matrix}")
        self.assertEqual(widget.latex(), r"\begin{matrix}a&b\\c&d\end{matrix}")

    def test_paste_preserves_whitespace_comments_and_non_round_trip_projection(self) -> None:
        widget = MathEditorWidget()
        self.addCleanup(widget.deleteLater)
        for body in ("\n  " + r"\studentMacro{a} % preserve" + "\n\t + y\n",
                     "x_1^2", " \t ", "a\r\nb", "a\rb"):
            for wrapped in (False, True):
                with self.subTest(body=body, wrapped=wrapped):
                    widget.set_latex("x")
                    widget.paste_clipboard("\\(" + body + "\\)" if wrapped else body)
                    self.assertEqual(widget.latex(), "x" + body)
                    widget.undo()
                    self.assertEqual(widget.latex(), "x")
                    widget.redo()
                    self.assertEqual(widget.latex(), "x" + body)

    def test_paste_via_keyboard_shortcut(self) -> None:
        app().clipboard().setText(r"\frac{1}{2}")
        widget = MathEditorWidget()
        widget.set_latex("x=")
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_V,
            Qt.KeyboardModifier.ControlModifier,
            "v",
        )
        widget.keyPressEvent(event)
        self.assertEqual(widget.latex(), r"x=\frac{1}{2}")
        app().clipboard().clear()

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
