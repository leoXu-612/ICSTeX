from __future__ import annotations

from unittest import TestCase

from app.core.formula_tree import (
    BigOp,
    Command,
    Frac,
    Group,
    MathSequence,
    Script,
    Sqrt,
    Text,
    latex_of,
    parse_math_latex,
)


class ParseRoundTripTests(TestCase):
    def test_round_trips_supported_structures(self) -> None:
        cases = (
            r"\frac{a+b}{c}",
            r"\frac{x^2+1}{\sqrt{y_1+y_2}}",
            r"\sqrt{x+1}",
            "x^2",
            "x^{2}",
            "x_1",
            r"E=mc^2",
            r"\gamma mc^2",
            r"\sum_{i=0}^{n} a_i",
            r"\int_0^1 x\,dx",
            r"\int_{a}^{b} f(x)",
            r"\lim_{x\to\infty} f(x)",
            r"\alpha + \beta = \gamma",
            r"{x+1}",
            r"\left( x \right)",
            r"\frac{\sqrt{x}}{y} + z^{2}",
            "2x + 3y = 5",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(latex_of(parse_math_latex(text)), text)

    def test_unknown_commands_are_preserved(self) -> None:
        text = r"\mystery{a}{b} + \unknown"
        self.assertEqual(latex_of(parse_math_latex(text)), text)

    def test_environments_are_preserved(self) -> None:
        text = r"\begin{matrix}a&b\\c&d\end{matrix}"
        self.assertEqual(latex_of(parse_math_latex(text)), text)

    def test_malformed_frac_is_preserved(self) -> None:
        for text in (r"\frac{a", r"\frac{a}{", r"\frac"):
            with self.subTest(text=text):
                self.assertEqual(latex_of(parse_math_latex(text)), text)

    def test_standalone_script_is_preserved(self) -> None:
        for text in ("^2", "_{i}", "^x"):
            with self.subTest(text=text):
                self.assertEqual(latex_of(parse_math_latex(text)), text)

    def test_empty_input_round_trips(self) -> None:
        self.assertEqual(latex_of(parse_math_latex("")), "")


class TreeStructureTests(TestCase):
    def test_frac_parses_typed_nodes(self) -> None:
        tree = parse_math_latex(r"\frac{a+b}{c}")
        frac = tree.items[0]
        self.assertIsInstance(frac, Frac)
        self.assertEqual(latex_of(frac.numerator), "a+b")
        self.assertEqual(latex_of(frac.denominator), "c")

    def test_sqrt_and_scripts_parse_typed_nodes(self) -> None:
        tree = parse_math_latex(r"\sqrt{y_1+y_2}")
        self.assertIsInstance(tree.items[0], Sqrt)
        self.assertEqual(latex_of(tree.items[0].radicand), "y_1+y_2")

        tree = parse_math_latex("x^2_1")
        self.assertIsInstance(tree.items[0], Script)
        self.assertEqual(tree.items[0].super_raw, "2")
        self.assertEqual(tree.items[0].sub_raw, "1")

    def test_bigop_limits_and_body(self) -> None:
        tree = parse_math_latex(r"\sum_{i=0}^{n} a_i")
        op = tree.items[0]
        self.assertIsInstance(op, BigOp)
        self.assertEqual(op.symbol, "sum")
        self.assertEqual(latex_of(op.lower), "i=0")
        self.assertEqual(latex_of(op.upper), "n")
        # The operand following a parsed operator stays a sibling; the body
        # slot is only used by operators created in the visual editor.
        self.assertEqual(latex_of(op.body), "")
        self.assertEqual(len(tree.items), 2)
        self.assertEqual(latex_of(tree.items[1]), " a_i")

    def test_known_command_has_display_form(self) -> None:
        tree = parse_math_latex(r"\alpha")
        self.assertIsInstance(tree.items[0], Command)
        self.assertEqual(tree.items[0].latex, r"\alpha")
        self.assertEqual(tree.items[0].display, "α")

    def test_group_preserves_braces(self) -> None:
        tree = parse_math_latex("{x+1}")
        self.assertIsInstance(tree.items[0], Group)
        self.assertEqual(latex_of(tree.items[0]), "{x+1}")

    def test_text_run_coalescing(self) -> None:
        tree = parse_math_latex("abc+def")
        self.assertEqual(len(tree.items), 1)
        self.assertIsInstance(tree.items[0], Text)
        self.assertEqual(tree.items[0].text, "abc+def")

    def test_command_space_separator(self) -> None:
        tree = MathSequence(items=[Command(latex=r"\gamma", display="γ"), Text("mc")])
        self.assertEqual(latex_of(tree), r"\gamma mc")
