from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from app.core.log_parser import parse_latex_errors


class LogParserTests(TestCase):
    def test_luaotfload_fatal_preserves_details_without_student_location(self) -> None:
        output = '\n'.join([
            'luaotfload | load : FATAL ERROR',
            'luaotfload | load :   \u00d7 Failed to load "luaotfload" module "multiscript".',
            'luaotfload | load :   \u00d7 Error message:',
            'luaotfload | load :     \u00d7 "luaotfload-multiscript.lua:70: attempt to index a nil value".',
            '', 'stack traceback:', 'l.99 unrelated context',
        ])
        errors = parse_latex_errors(output + '\n' + output, Path('/tmp/project'))
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].message.startswith('luaotfload: FATAL ERROR'))
        self.assertIn('multiscript.lua:70', errors[0].message)
        self.assertIsNone(errors[0].file)
        self.assertIsNone(errors[0].line)
        self.assertNotIn('unrelated context', errors[0].message)

    def test_luaotfload_informational_or_quoted_fatal_is_not_an_error(self) -> None:
        output = '\n'.join([
            'luaotfload | init : Loading fontloader from kpse-resolved path',
            'Quoted text: luaotfload | load : FATAL ERROR',
            'luaotfload | load : Information about FATAL ERROR handling',
        ])
        self.assertEqual(parse_latex_errors(output), [])

    def test_luaotfload_quoted_detail_wrap_does_not_consume_next_tex_error(self) -> None:
        output = '\n'.join([
            'luaotfload | load : FATAL ERROR',
            'luaotfload | load :   \u00d7 Error message:',
            'luaotfload | load :     \u00d7 "...mf-dist/tex/luatex/luaotfload/luaotfload-multiscr',
            'ipt.lua:70: attempt to index a nil value (local \'f\')".',
            '! Undefined control sequence.',
            'l.42 \\broken',
        ])
        errors = parse_latex_errors(output)
        self.assertEqual(len(errors), 2)
        self.assertIn("multiscript.lua:70: attempt to index a nil value (local 'f')", errors[0].message)
        self.assertNotIn('Undefined control sequence', errors[0].message)
        self.assertIsNone(errors[0].file)
        self.assertIsNone(errors[0].line)
        self.assertEqual(errors[1].message, 'Undefined control sequence.')
        self.assertEqual(errors[1].line, 42)

    def test_luaotfload_incomplete_quote_stops_before_stack_trace(self) -> None:
        errors = parse_latex_errors('\n'.join([
            'luaotfload | load : FATAL ERROR',
            'luaotfload | load :   \u00d7 "incomplete error',
            'stack traceback:',
            'l.99 unrelated context',
        ]))
        self.assertEqual(len(errors), 1)
        self.assertNotIn('stack traceback', errors[0].message)
        self.assertIsNone(errors[0].line)

    def test_luaotfload_fatal_without_details_remains_an_error(self) -> None:
        errors = parse_latex_errors('luaotfload | load : FATAL ERROR')
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].message, 'luaotfload: FATAL ERROR')

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
