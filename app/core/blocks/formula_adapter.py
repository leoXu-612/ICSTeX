"""FormulaBlock adapter over the existing formula engine.

The adapter wraps ``app.core.formula_tree`` so the formula Block keeps a
managed AST (authoritative) plus a regenerable ``latexCache``; AST and cache
must never diverge. Unsupported constructs survive losslessly as raw text.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.blocks.model import Block
from app.core.formula_tree import (
    BigOp,
    Command,
    Frac,
    Group,
    MathNode,
    MathSequence,
    Script,
    Sqrt,
    Text,
    latex_of,
    parse_math_latex,
)


FORMAT = "icstex-formula-ast"
AST_VERSION = "1.0.0"


@dataclass(frozen=True)
class FormulaValidationIssue:
    severity: str
    message: str


def ast_to_json(node: MathNode) -> dict:
    if isinstance(node, Text):
        return {"kind": "text", "text": node.text}
    if isinstance(node, Command):
        return {"kind": "command", "latex": node.latex, "display": node.display}
    if isinstance(node, MathSequence):
        return {"kind": "seq", "items": [ast_to_json(item) for item in node.items]}
    if isinstance(node, Group):
        return {"kind": "group", "items": ast_to_json(node.items)["items"]}
    if isinstance(node, Frac):
        return {
            "kind": "frac",
            "numerator": ast_to_json(node.numerator)["items"],
            "denominator": ast_to_json(node.denominator)["items"],
        }
    if isinstance(node, Sqrt):
        return {"kind": "sqrt", "radicand": ast_to_json(node.radicand)["items"]}
    if isinstance(node, Script):
        return {
            "kind": "script",
            "base": ast_to_json(node.base),
            "super": ast_to_json(node.super)["items"] if node.super is not None else None,
            "sub": ast_to_json(node.sub)["items"] if node.sub is not None else None,
            "superRaw": node.super_raw,
            "superBraced": node.super_braced,
            "subRaw": node.sub_raw,
            "subBraced": node.sub_braced,
        }
    if isinstance(node, BigOp):
        return {
            "kind": "bigop",
            "symbol": node.symbol,
            "lower": ast_to_json(node.lower)["items"] if node.lower is not None else None,
            "upper": ast_to_json(node.upper)["items"] if node.upper is not None else None,
            "body": ast_to_json(node.body)["items"],
            "lowerRaw": node.lower_raw,
            "lowerBraced": node.lower_braced,
            "upperRaw": node.upper_raw,
            "upperBraced": node.upper_braced,
        }
    raise TypeError(f"unknown math node: {type(node).__name__}")


def json_to_ast(data: dict) -> MathNode:
    kind = data["kind"]
    if kind == "text":
        return Text(data.get("text", ""))
    if kind == "command":
        return Command(latex=data.get("latex", ""), display=data.get("display", ""))
    if kind == "seq":
        return MathSequence(items=[json_to_ast(item) for item in data.get("items", [])])
    if kind == "group":
        return Group(items=MathSequence(items=[json_to_ast(item) for item in data.get("items", [])]))
    if kind == "frac":
        return Frac(
            numerator=MathSequence(items=[json_to_ast(item) for item in data.get("numerator", [])]),
            denominator=MathSequence(items=[json_to_ast(item) for item in data.get("denominator", [])]),
        )
    if kind == "sqrt":
        return Sqrt(radicand=MathSequence(items=[json_to_ast(item) for item in data.get("radicand", [])]))
    if kind == "script":
        script = Script(
            base=json_to_ast(data["base"]),
            super=MathSequence(items=[json_to_ast(item) for item in data.get("super", [])])
            if data.get("super") is not None
            else None,
            sub=MathSequence(items=[json_to_ast(item) for item in data.get("sub", [])])
            if data.get("sub") is not None
            else None,
        )
        script.super_raw = data.get("superRaw")
        script.super_braced = bool(data.get("superBraced", True))
        script.sub_raw = data.get("subRaw")
        script.sub_braced = bool(data.get("subBraced", True))
        return script
    if kind == "bigop":
        operator = BigOp(
            symbol=data.get("symbol", "sum"),
            lower=MathSequence(items=[json_to_ast(item) for item in data.get("lower", [])])
            if data.get("lower") is not None
            else None,
            upper=MathSequence(items=[json_to_ast(item) for item in data.get("upper", [])])
            if data.get("upper") is not None
            else None,
            body=MathSequence(items=[json_to_ast(item) for item in data.get("body", [])]),
        )
        operator.lower_raw = data.get("lowerRaw")
        operator.lower_braced = bool(data.get("lowerBraced", True))
        operator.upper_raw = data.get("upperRaw")
        operator.upper_braced = bool(data.get("upperBraced", True))
        return operator
    raise ValueError(f"unknown formula ast kind: {kind}")


class FormulaBlockAdapter:
    """Creates and validates formula Block content from the math engine."""

    def latex_to_ast(self, latex: str) -> dict:
        return ast_to_json(parse_math_latex(latex))

    def render_latex(self, ast: dict) -> str:
        return latex_of(json_to_ast(ast))

    def content_for(self, latex: str) -> dict:
        ast = self.latex_to_ast(latex)
        return {
            "format": FORMAT,
            "astVersion": AST_VERSION,
            "ast": ast,
            "latexCache": latex_of(parse_math_latex(latex)),
        }

    def update_ast(self, ast: dict) -> dict:
        return {
            "format": FORMAT,
            "astVersion": AST_VERSION,
            "ast": ast,
            "latexCache": self.render_latex(ast),
        }

    def get_ast(self, block: Block) -> dict:
        if block.content.get("format") != FORMAT:
            raise ValueError("不是受管理的公式 Block")
        return block.content["ast"]

    def validate(self, ast: dict) -> list[FormulaValidationIssue]:
        issues: list[FormulaValidationIssue] = []
        node = json_to_ast(ast)
        if isinstance(node, MathSequence) and not node.items:
            issues.append(FormulaValidationIssue("error", "公式为空"))
        if self._has_unknown_command(node):
            issues.append(
                FormulaValidationIssue(
                    "warning",
                    "存在未识别命令，将按原样保留为源码文本",
                )
            )
        return issues

    def _has_unknown_command(self, node: MathNode) -> bool:
        if isinstance(node, Command) and node.latex == node.display and node.latex.startswith("\\"):
            return True
        if isinstance(node, MathSequence):
            return any(self._has_unknown_command(item) for item in node.items)
        if isinstance(node, Frac):
            return self._has_unknown_command(node.numerator) or self._has_unknown_command(node.denominator)
        if isinstance(node, Sqrt):
            return self._has_unknown_command(node.radicand)
        if isinstance(node, Script):
            found = self._has_unknown_command(node.base)
            if node.super is not None:
                found = found or self._has_unknown_command(node.super)
            if node.sub is not None:
                found = found or self._has_unknown_command(node.sub)
            return found
        if isinstance(node, BigOp):
            found = self._has_unknown_command(node.body)
            if node.lower is not None:
                found = found or self._has_unknown_command(node.lower)
            if node.upper is not None:
                found = found or self._has_unknown_command(node.upper)
            return found
        if isinstance(node, Group):
            return self._has_unknown_command(node.items)
        return False
