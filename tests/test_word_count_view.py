from __future__ import annotations

import os
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.word_count import WordCountResult, WordCountSegment
from app.gui.word_count_view import BREAKDOWN, WordCountView, wrap_in_scroll


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


class WordCountViewTests(TestCase):
    def setUp(self) -> None:
        app()

    def test_breakdown_shows_exact_values_and_relative_scale(self) -> None:
        view = WordCountView()
        result = WordCountResult(
            total_words=150,
            effective_words=100,
            header_words=20,
            caption_words=10,
            math_inline=8,
            math_display=4,
            numbers=20,
            source="fallback",
            visual_segments=(
                WordCountSegment("Main title", "headers", "main.tex"),
                WordCountSegment("\nBody text ", "effective", "main.tex"),
                WordCountSegment("42", "numbers", "chapter.tex"),
            ),
        )

        view.set_result(result, "main.tex", False)

        expected = {
            "effective": 100,
            "headers": 20,
            "captions": 10,
            "math_inline": 8,
            "math_display": 4,
            "numbers": 20,
        }
        self.assertEqual(set(view.category_bars), {key for key, _label in BREAKDOWN})
        for key, value in expected.items():
            self.assertEqual(view.category_bars[key].maximum(), 100)
            self.assertEqual(view.category_bars[key].value(), value)
            self.assertEqual(view.category_values[key].text(), f"{value:,}")
        self.assertIn("Main title", view.preview_browser.toPlainText())
        self.assertIn("Body text", view.preview_browser.toPlainText())
        self.assertIn("42", view.preview_browser.toPlainText())
        self.assertIn("main.tex", view.preview_browser.toPlainText())
        self.assertIn("chapter.tex", view.preview_browser.toPlainText())
        self.assertIn("background-color", view.preview_browser.toHtml())

    def test_zero_result_and_reset_keep_all_rows_stable(self) -> None:
        view = WordCountView()
        result = WordCountResult(
            total_words=0,
            effective_words=0,
            header_words=0,
            caption_words=0,
            math_inline=0,
            math_display=0,
            numbers=0,
            source="fallback",
        )

        view.set_result(result, "empty.tex", False)
        for key, _label in BREAKDOWN:
            self.assertEqual(view.category_bars[key].maximum(), 1)
            self.assertEqual(view.category_bars[key].value(), 0)
            self.assertEqual(view.category_values[key].text(), "0")

        view.reset("未选择文档")
        for key, _label in BREAKDOWN:
            self.assertEqual(view.category_bars[key].value(), 0)
            self.assertEqual(view.category_values[key].text(), "-")
        self.assertEqual(view.meta_label.text(), "未选择文档")
        self.assertIn("未选择文档", view.preview_browser.toPlainText())

    def test_scroll_wrapper_never_uses_horizontal_scrollbar(self) -> None:
        scroll = wrap_in_scroll(WordCountView())

        self.assertEqual(
            scroll.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
