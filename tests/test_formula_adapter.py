from __future__ import annotations

from unittest import TestCase

from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.blocks.model import Semantic
from app.core.blocks.registry import BlockRegistry, CreateBlockInput


class FormulaBlockAdapterTests(TestCase):
    def setUp(self) -> None:
        self.adapter = FormulaBlockAdapter()

    def test_latex_to_ast_and_back_round_trips(self) -> None:
        for latex in (
            r"\frac{x^2+1}{\sqrt{y_1+y_2}}",
            r"E=mc^2",
            r"\sum_{i=0}^{n} a_i",
            r"\alpha + \beta",
            r"\mystery{a}{b}",
        ):
            with self.subTest(latex=latex):
                ast = self.adapter.latex_to_ast(latex)
                self.assertEqual(self.adapter.render_latex(ast), latex)

    def test_content_holds_ast_and_consistent_cache(self) -> None:
        content = self.adapter.content_for(r"E=mc^2")
        self.assertEqual(content["format"], "icstex-formula-ast")
        self.assertEqual(content["latexCache"], r"E=mc^2")
        self.assertEqual(self.adapter.render_latex(content["ast"]), content["latexCache"])

    def test_update_ast_regenerates_cache(self) -> None:
        content = self.adapter.content_for("E")
        new_ast = self.adapter.latex_to_ast(r"E=\gamma mc^2")
        updated = self.adapter.update_ast(new_ast)
        self.assertEqual(updated["latexCache"], r"E=\gamma mc^2")

    def test_get_ast_and_validate(self) -> None:
        registry = BlockRegistry()
        block = registry.create(
            CreateBlockInput(
                type="formula",
                alias="eq",
                content=self.adapter.content_for(r"E=mc^2"),
            )
        )
        self.assertEqual(self.adapter.get_ast(block)["kind"], "seq")
        self.assertEqual(self.adapter.validate(self.adapter.get_ast(block)), [])

        empty = self.adapter.validate(self.adapter.latex_to_ast(""))
        self.assertEqual(empty[0].severity, "error")
        unknown = self.adapter.validate(self.adapter.latex_to_ast(r"\mystery{x}"))
        self.assertEqual(unknown[0].severity, "warning")

    def test_formula_block_persists_through_registry(self) -> None:
        registry = BlockRegistry()
        block = registry.create(
            CreateBlockInput(
                type="formula",
                alias="eq-energy",
                semantic=Semantic(role="equation", label="eq:energy"),
                content=self.adapter.content_for(r"E=mc^2"),
            )
        )
        self.assertEqual(block.content["latexCache"], r"E=mc^2")
        self.assertEqual(registry.get(block.id).semantic.label, "eq:energy")
