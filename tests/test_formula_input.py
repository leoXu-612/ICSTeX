from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest import TestCase

from app.core.formula_input import (
    FORMULA_TEMPLATE_KEYS,
    FinalTextEditPlan,
    FormulaDraft,
    FormulaMode,
    ParsedEnvelope,
    TemplateEditResult,
    apply_formula_template,
    change_formula_mode,
    final_edit_plan,
    mode_packages,
    parse_document_selection,
    recognize_formula,
    render_formula,
)


class RecognizeFormulaTests(TestCase):
    def test_matrix_package_is_planned_only_for_real_uncommented_environment(self):
        for body, packages in ((r"\begin{matrix}a&b\\c&d\end{matrix}", ("amsmath",)),
                               (r"\begin{cases}x&x>0\end{cases}", ("amsmath",)),
                               ("x % \\begin{matrix}\n+ y", ())):
            plan = final_edit_plan("", 0, 0, FormulaDraft(mode=FormulaMode.INLINE_PAREN, body=body))
            self.assertEqual(plan.packages, packages)

    def test_recognizes_every_supported_wrapper(self) -> None:
        cases = (
            (r"$a+b$", FormulaMode.INLINE_DOLLAR, "a+b"),
            (r"\(a+b\)", FormulaMode.INLINE_PAREN, "a+b"),
            (r"\[a+b\]", FormulaMode.DISPLAY_BRACKET, "a+b"),
            (r"\begin{equation}a+b\end{equation}", FormulaMode.EQUATION, "a+b"),
            (r"\begin{equation*}a+b\end{equation*}", FormulaMode.EQUATION_STAR, "a+b"),
        )
        for text, mode, body in cases:
            with self.subTest(text=text):
                envelope = recognize_formula(text)
                self.assertIsNotNone(envelope)
                assert envelope is not None
                self.assertEqual(envelope.mode, mode)
                self.assertEqual(envelope.body, body)
                self.assertEqual(envelope.start, 0)
                self.assertEqual(envelope.end, len(text))

    def test_exact_body_round_trips_for_every_wrapper(self) -> None:
        texts = (
            r"$a+b$",
            r"\(a+b\)",
            r"\[a+b\]",
            r"\begin{equation}a+b\end{equation}",
            r"\begin{equation*}a+b\end{equation*}",
            r"$x \mystery{a}{b} % keep" + "\n" + r" + \beta$",
            r"\[\alpha^2 + \beta^2\]",
            r"\begin{equation}\n  a &= b\n\end{equation}",
        )
        for text in texts:
            with self.subTest(text=text):
                envelope = recognize_formula(text)
                self.assertIsNotNone(envelope)
                assert envelope is not None
                draft = FormulaDraft(mode=envelope.mode, body=envelope.body)
                self.assertEqual(render_formula(draft), text)

    def test_empty_bodies(self) -> None:
        self.assertEqual(recognize_formula(r"\(\)").body, "")  # type: ignore[union-attr]
        self.assertEqual(recognize_formula(r"\[\]").body, "")  # type: ignore[union-attr]
        self.assertEqual(recognize_formula(r"\begin{equation}\end{equation}").body, "")  # type: ignore[union-attr]
        self.assertEqual(recognize_formula(r"\begin{equation*}\end{equation*}").body, "")  # type: ignore[union-attr]
        envelope = recognize_formula("$ $")
        assert envelope is not None
        self.assertEqual(envelope.body, " ")

    def test_empty_dollar_pair_is_ambiguous(self) -> None:
        self.assertIsNone(recognize_formula("$$"))
        self.assertIsNone(recognize_formula("$$a$$"))

    def test_escaped_delimiters(self) -> None:
        envelope = recognize_formula(r"$a\$b$")
        assert envelope is not None
        self.assertEqual(envelope.body, r"a\$b")

        envelope = recognize_formula(r"$\$$")
        assert envelope is not None
        self.assertEqual(envelope.body, r"\$")

        envelope = recognize_formula(r"\(a\\\)")
        assert envelope is not None
        self.assertEqual(envelope.body, r"a\\")

        envelope = recognize_formula(r"\(\left(x\right)\)")
        assert envelope is not None
        self.assertEqual(envelope.body, r"\left(x\right)")

    def test_escaped_or_literal_delimiters_are_not_closers(self) -> None:
        self.assertIsNone(recognize_formula(r"$a\$"))  # trailing \$ is escaped
        self.assertIsNone(recognize_formula(r"$a\\$b$"))  # even backslash run leaves literal $
        self.assertIsNone(recognize_formula(r"\(a\\)"))  # trailing ) is literal

    def test_comments_are_preserved(self) -> None:
        text = "$a % comment\n b$"
        envelope = recognize_formula(text)
        assert envelope is not None
        self.assertEqual(envelope.body, "a % comment\n b")

        text = r"\(a % comment" + "\n" + r" b\)"
        envelope = recognize_formula(text)
        assert envelope is not None
        self.assertEqual(envelope.body, "a % comment\n b")

    def test_comment_consuming_closing_delimiter_is_rejected(self) -> None:
        self.assertIsNone(recognize_formula("$a % comment$"))
        self.assertIsNone(recognize_formula(r"\(a % comment\)"))
        self.assertIsNone(recognize_formula(r"\[a % comment\]"))
        self.assertIsNone(recognize_formula(r"\begin{equation}a % comment\end{equation}"))

    def test_unknown_macros_are_preserved(self) -> None:
        envelope = recognize_formula(r"$\mystery{a}{b} \unknown^{2}$")
        assert envelope is not None
        self.assertEqual(envelope.body, r"\mystery{a}{b} \unknown^{2}")

    def test_malformed_input_is_rejected(self) -> None:
        for text in (
            "",
            "$a",
            "a$",
            r"\(a",
            "a\\)",
            r"\[x",
            r"\begin{equation} a",
            r"a\end{equation}",
            r"\begin{equation} a \end{equation*}",
            r"\begin{equation*} a \end{equation}",
            r"\begin{equation",
            "plain text",
            "$",
        ):
            with self.subTest(text=text):
                self.assertIsNone(recognize_formula(text))

    def test_multi_formula_and_ambiguous_input_is_rejected(self) -> None:
        for text in (
            "$a$ $b$",
            "$a$b$",
            r"\(a\)\(b\)",
            r"\(a\)b\)",
            r"\begin{equation}a\end{equation}\begin{equation}b\end{equation}",
            r"\begin{equation}a\begin{equation*}b\end{equation*}\end{equation}",
        ):
            with self.subTest(text=text):
                self.assertIsNone(recognize_formula(text))


class ParseDocumentSelectionTests(TestCase):
    def test_exact_selection_returns_absolute_offsets(self) -> None:
        document = "Text $a+b$ more"
        start = document.index("$")
        end = start + len("$a+b$")

        envelope = parse_document_selection(document, start, end)

        self.assertIsNotNone(envelope)
        assert envelope is not None
        self.assertEqual(envelope.mode, FormulaMode.INLINE_DOLLAR)
        self.assertEqual(envelope.body, "a+b")
        self.assertEqual(envelope.start, start)
        self.assertEqual(envelope.end, end)

    def test_selection_spanning_extra_text_is_rejected(self) -> None:
        document = "Text $a+b$ more"
        self.assertIsNone(parse_document_selection(document, 0, len(document)))
        self.assertIsNone(parse_document_selection(document, document.index("$"), len(document)))

    def test_out_of_bounds_selection_is_rejected(self) -> None:
        document = "$a$"
        self.assertIsNone(parse_document_selection(document, -1, 2))
        self.assertIsNone(parse_document_selection(document, 0, 99))
        self.assertIsNone(parse_document_selection(document, 2, 1))

    def test_unknown_macro_body_round_trips_through_document(self) -> None:
        document = r"see $\mystery{a}{b} x$ here"
        start = document.index("$")
        end = len(document) - len(" here")
        envelope = parse_document_selection(document, start, end)
        assert envelope is not None
        draft = FormulaDraft(mode=envelope.mode, body=envelope.body)
        self.assertEqual(render_formula(draft), document[start:end])


class FormulaModeTests(TestCase):
    def test_wrapper_prefixes_and_suffixes(self) -> None:
        cases = (
            (FormulaMode.INLINE_DOLLAR, "$", "$"),
            (FormulaMode.INLINE_PAREN, r"\(", r"\)"),
            (FormulaMode.DISPLAY_BRACKET, r"\[", r"\]"),
            (FormulaMode.EQUATION, r"\begin{equation}", r"\end{equation}"),
            (FormulaMode.EQUATION_STAR, r"\begin{equation*}", r"\end{equation*}"),
        )
        for mode, prefix, suffix in cases:
            with self.subTest(mode=mode):
                self.assertEqual(mode.wrapper_prefix, prefix)
                self.assertEqual(mode.wrapper_suffix, suffix)

    def test_display_flag(self) -> None:
        self.assertFalse(FormulaMode.INLINE_DOLLAR.is_display)
        self.assertFalse(FormulaMode.INLINE_PAREN.is_display)
        self.assertTrue(FormulaMode.DISPLAY_BRACKET.is_display)
        self.assertTrue(FormulaMode.EQUATION.is_display)
        self.assertTrue(FormulaMode.EQUATION_STAR.is_display)

    def test_domain_types_are_immutable(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="x")
        with self.assertRaises(FrozenInstanceError):
            draft.body = "y"  # type: ignore[misc]

        envelope = ParsedEnvelope(mode=FormulaMode.EQUATION, body="x", start=0, end=3)
        with self.assertRaises(FrozenInstanceError):
            envelope.body = "z"  # type: ignore[misc]

        result = TemplateEditResult(template="fraction", draft=draft)
        with self.assertRaises(FrozenInstanceError):
            result.template = "sqrt"  # type: ignore[misc]

        plan = FinalTextEditPlan(start=0, end=3, source_text="$x$", text="$x$")
        with self.assertRaises(FrozenInstanceError):
            plan.text = "$y$"  # type: ignore[misc]


class TemplateTests(TestCase):
    def test_fraction(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="a+b")
        result = apply_formula_template(draft, "fraction")
        assert result is not None
        self.assertEqual(result.draft.body, r"\frac{a+b}{}")
        self.assertEqual(result.draft.mode, FormulaMode.INLINE_DOLLAR)
        self.assertEqual(result.cursor_offset, 11)
        self.assertEqual(result.packages, ())

    def test_fraction_with_empty_body(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.EQUATION, body="")
        result = apply_formula_template(draft, "fraction")
        assert result is not None
        self.assertEqual(result.draft.body, r"\frac{}{}")
        self.assertEqual(result.draft.mode, FormulaMode.EQUATION)

    def test_sqrt(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_PAREN, body="a+b")
        result = apply_formula_template(draft, "sqrt")
        assert result is not None
        self.assertEqual(result.draft.body, r"\sqrt{a+b}")
        self.assertEqual(result.cursor_offset, 9)

    def test_sqrt_with_empty_body(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.DISPLAY_BRACKET, body="")
        result = apply_formula_template(draft, "sqrt")
        assert result is not None
        self.assertEqual(result.draft.body, r"\sqrt{}")
        self.assertEqual(result.cursor_offset, 6)

    def test_superscript(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="x")
        result = apply_formula_template(draft, "superscript")
        assert result is not None
        self.assertEqual(result.draft.body, "x^{}")
        self.assertEqual(result.cursor_offset, 3)

    def test_superscript_braces_multi_token_base(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="a+b")
        result = apply_formula_template(draft, "superscript")
        assert result is not None
        self.assertEqual(result.draft.body, "{a+b}^{}")
        self.assertEqual(result.cursor_offset, 7)

    def test_superscript_keeps_single_command_base(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body=r"\alpha")
        result = apply_formula_template(draft, "superscript")
        assert result is not None
        self.assertEqual(result.draft.body, r"\alpha^{}")
        self.assertEqual(result.cursor_offset, 8)

    def test_superscript_with_empty_body_is_non_applicable(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="")
        self.assertIsNone(apply_formula_template(draft, "superscript"))

    def test_subscript(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="x")
        result = apply_formula_template(draft, "subscript")
        assert result is not None
        self.assertEqual(result.draft.body, "x_{}")
        self.assertEqual(result.cursor_offset, 3)

    def test_subscript_braces_multi_token_base(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="a+b")
        result = apply_formula_template(draft, "subscript")
        assert result is not None
        self.assertEqual(result.draft.body, "{a+b}_{}")
        self.assertEqual(result.cursor_offset, 7)

    def test_subscript_with_empty_body_is_non_applicable(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="")
        self.assertIsNone(apply_formula_template(draft, "subscript"))

    def test_sum(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.EQUATION, body="a+b")
        result = apply_formula_template(draft, "sum")
        assert result is not None
        self.assertEqual(result.draft.body, r"\sum_{}^{}a+b")
        self.assertEqual(result.cursor_offset, 6)

    def test_sum_with_empty_body(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.EQUATION, body="")
        result = apply_formula_template(draft, "sum")
        assert result is not None
        self.assertEqual(result.draft.body, r"\sum_{}^{}")

    def test_integral(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.EQUATION, body="a+b")
        result = apply_formula_template(draft, "integral")
        assert result is not None
        self.assertEqual(result.draft.body, r"\int_{}^{}a+b")
        self.assertEqual(result.cursor_offset, 6)

    def test_integral_with_empty_body(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.EQUATION, body="")
        result = apply_formula_template(draft, "integral")
        assert result is not None
        self.assertEqual(result.draft.body, r"\int_{}^{}")

    def test_greek_alpha_prepends_symbol(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="a+b")
        result = apply_formula_template(draft, "greek_alpha")
        assert result is not None
        self.assertEqual(result.draft.body, r"\alpha a+b")
        self.assertEqual(result.cursor_offset, len(r"\alpha a+b"))

    def test_greek_alpha_with_empty_body(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="")
        result = apply_formula_template(draft, "greek_alpha")
        assert result is not None
        self.assertEqual(result.draft.body, r"\alpha")

    def test_unknown_template_is_non_applicable(self) -> None:
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="x")
        self.assertIsNone(apply_formula_template(draft, "matrix"))

    def test_template_catalog_is_stable(self) -> None:
        self.assertEqual(
            FORMULA_TEMPLATE_KEYS,
            ("fraction", "sqrt", "superscript", "subscript", "sum", "integral", "greek_alpha"),
        )


class FinalEditPlanTests(TestCase):
    def test_plan_replaces_valid_selection(self) -> None:
        document = "x $a+b$ y"
        start = document.index("$")
        end = start + len("$a+b$")
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body=r"\frac{a+b}{}")

        plan = final_edit_plan(document, start, end, draft, body_cursor_offset=11)

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.start, start)
        self.assertEqual(plan.end, end)
        self.assertEqual(plan.source_text, "$a+b$")
        self.assertEqual(plan.text, r"$\frac{a+b}{}$")
        self.assertEqual(plan.packages, ())
        self.assertEqual(plan.cursor_offset, 12)

    def test_plan_requires_amsmath_for_equation_star(self) -> None:
        document = r"x \begin{equation*}a+b\end{equation*} y"
        start = document.index(r"\begin{equation*}")
        end = start + len(r"\begin{equation*}a+b\end{equation*}")
        draft = FormulaDraft(mode=FormulaMode.EQUATION_STAR, body="a+b")

        plan = final_edit_plan(document, start, end, draft)

        assert plan is not None
        self.assertEqual(plan.text, r"\begin{equation*}a+b\end{equation*}")
        self.assertEqual(plan.packages, ("amsmath",))

    def test_plan_merges_and_deduplicates_packages(self) -> None:
        document = r"x \begin{equation*}a+b\end{equation*} y"
        start = document.index(r"\begin{equation*}")
        end = start + len(r"\begin{equation*}a+b\end{equation*}")
        draft = FormulaDraft(mode=FormulaMode.EQUATION_STAR, body="a+b")

        plan = final_edit_plan(document, start, end, draft, packages=("amsmath", "mathtools"))

        assert plan is not None
        self.assertEqual(plan.packages, ("amsmath", "mathtools"))

    def test_plan_rejects_invalid_selection(self) -> None:
        document = "x $a+b$ y"
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body=r"\frac{a+b}{}")
        self.assertIsNone(final_edit_plan(document, 0, len(document), draft))
        self.assertIsNone(final_edit_plan(document, 0, 99, draft))

    def test_plan_supports_insertion_at_cursor(self) -> None:
        document = "Text here"
        draft = FormulaDraft(mode=FormulaMode.EQUATION, body="")

        plan = final_edit_plan(document, 4, 4, draft, body_cursor_offset=0)

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.start, 4)
        self.assertEqual(plan.end, 4)
        self.assertEqual(plan.source_text, "")
        self.assertEqual(plan.text, r"\begin{equation}\end{equation}")
        self.assertEqual(plan.packages, ())
        self.assertEqual(plan.cursor_offset, len(r"\begin{equation}"))

    def test_insertion_plan_rejects_malformed_draft(self) -> None:
        document = "Text here"
        draft = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="a$b")

        self.assertIsNone(final_edit_plan(document, 4, 4, draft))

    def test_mode_change_rewrites_wrapper_but_not_body(self) -> None:
        source = FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="a+b")
        target = change_formula_mode(source, FormulaMode.EQUATION)

        self.assertEqual(target.mode, FormulaMode.EQUATION)
        self.assertEqual(target.body, "a+b")
        self.assertEqual(render_formula(target), r"\begin{equation}a+b\end{equation}")

    def test_mode_change_plan(self) -> None:
        document = "x $a+b$ y"
        start = document.index("$")
        end = start + len("$a+b$")
        draft = change_formula_mode(
            FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="a+b"),
            FormulaMode.EQUATION,
        )

        plan = final_edit_plan(document, start, end, draft)

        assert plan is not None
        self.assertEqual(plan.text, r"\begin{equation}a+b\end{equation}")
        self.assertEqual(document, "x $a+b$ y")  # planning never mutates the document

    def test_mode_packages(self) -> None:
        self.assertEqual(mode_packages(FormulaMode.INLINE_DOLLAR), ())
        self.assertEqual(mode_packages(FormulaMode.INLINE_PAREN), ())
        self.assertEqual(mode_packages(FormulaMode.DISPLAY_BRACKET), ())
        self.assertEqual(mode_packages(FormulaMode.EQUATION), ())
        self.assertEqual(mode_packages(FormulaMode.EQUATION_STAR), ("amsmath",))


class NoGuiDependencyTests(TestCase):
    def test_module_has_no_gui_or_environment_dependencies(self) -> None:
        source_path = Path(__file__).resolve().parent.parent / "app" / "core" / "formula_input.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")

        forbidden = ("PySide6", "app.gui", "subprocess", "os", "sys", "socket", "pathlib")
        for name in imports:
            for root in forbidden:
                self.assertFalse(
                    name == root or name.startswith(root + "."),
                    msg=f"forbidden import in formula_input: {name}",
                )
