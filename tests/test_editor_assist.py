from __future__ import annotations

from unittest import TestCase

from app.core.editor_assist import (
    active_environments,
    enter_assist,
    environment_completion_for_line,
    is_in_list_environment,
    snippet_for_trigger,
    trigger_before_cursor,
)


class EditorAssistTests(TestCase):
    def test_detects_active_list_environment(self) -> None:
        text = "\\begin{itemize}\n  \\item One"

        self.assertEqual(active_environments(text), ["itemize"])
        self.assertTrue(is_in_list_environment(text))

    def test_enter_after_nonempty_item_continues_item(self) -> None:
        text = "\\begin{itemize}\n  \\item One"

        assist = enter_assist(text)

        self.assertIsNotNone(assist)
        assert assist is not None
        self.assertFalse(assist.replace_current_line)
        self.assertEqual(assist.replacement, "\n  \\item ")

    def test_enter_after_empty_item_exits_one_indent_level(self) -> None:
        text = "\\begin{itemize}\n  \\item "

        assist = enter_assist(text)

        self.assertIsNotNone(assist)
        assert assist is not None
        self.assertTrue(assist.replace_current_line)
        self.assertEqual(assist.replacement, "")

    def test_environment_completion_for_begin_line(self) -> None:
        completion = environment_completion_for_line("  \\begin{equation}")

        self.assertIsNotNone(completion)
        assert completion is not None
        self.assertEqual(completion.env_name, "equation")
        self.assertEqual(completion.insertion, "\n    \n  \\end{equation}")
        self.assertEqual(completion.cursor_offset, len("\n    "))

    def test_snippet_expands_and_reports_cursor_offset(self) -> None:
        snippet = snippet_for_trigger("fig")

        self.assertIsNotNone(snippet)
        assert snippet is not None
        self.assertIn("\\begin{figure}", snippet.text)
        self.assertNotIn("|", snippet.text)
        self.assertEqual(snippet.text[snippet.cursor_offset - 1], "{")

    def test_trigger_before_cursor_reads_current_word(self) -> None:
        self.assertEqual(trigger_before_cursor("\\section{A}\nfig"), "fig")
