from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from app.core.log_parser import parse_latex_errors


class LogParserTests(TestCase):
    def test_parses_file_line_error(self) -> None:
        output = "./chapters/intro.tex:12: Undefined control sequence."

        errors = parse_latex_errors(output, Path("/tmp/project"))

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].file, Path("/tmp/project/chapters/intro.tex").resolve())
        self.assertEqual(errors[0].line, 12)
        self.assertIn("Undefined control sequence", errors[0].message)

    def test_parses_bang_error_with_nearby_line_number(self) -> None:
        output = "\n".join(
            [
                "! Missing $ inserted.",
                "<inserted text>",
                "$",
                "l.42 Some text",
            ]
        )

        errors = parse_latex_errors(output)

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].message, "Missing $ inserted.")
        self.assertEqual(errors[0].line, 42)

    def test_joins_wrapped_file_line_error_message(self) -> None:
        output = "\n".join(
            [
                "/tmp/project/IA.tex:108: Undefined contr",
                "ol sequence.",
                "l.108     \\legend",
            ]
        )

        errors = parse_latex_errors(output)

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].message, "Undefined control sequence.")

    def test_joins_wrapped_latex_error_message(self) -> None:
        output = "\n".join(
            [
                "/tmp/project/IA.tex:117: LaTeX Error: Th",
                "ere's no line here to end.",
                "",
                "See the LaTeX manual or LaTeX Companion for explanation.",
            ]
        )

        errors = parse_latex_errors(output)

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].message, "LaTeX Error: There's no line here to end.")
