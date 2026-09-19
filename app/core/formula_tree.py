"""Structured math expression tree for the visual formula editor.

Pure core rules: parse a supported subset of LaTeX math into a mutable
expression tree, export the tree back to LaTeX, and provide the structural
navigation primitives the GUI widget builds on.

Lossless fallback contract
--------------------------
The parser never fails and never drops content. Supported structures
(fractions, roots, scripts, sums/integrals, known symbol commands, grouping
braces) become typed nodes; anything else -- unknown commands, environments,
or malformed syntax -- is preserved as raw text so ``latex_of(parse(text))``
reproduces the original source byte-for-byte. Unsupported constructs still
render (as their literal LaTeX text) and can be edited in source mode.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MathNode:
    """Base class for math tree nodes."""


@dataclass
class Text(MathNode):
    """Plain characters (digits, letters, operators, spaces)."""

    text: str = ""


@dataclass
class Command(MathNode):
    """A LaTeX command rendered as ``display`` and exported as ``latex``."""

    latex: str = ""
    display: str = ""


@dataclass
class MathSequence(MathNode):
    """An ordered list of sibling nodes (a math slot)."""

    items: list[MathNode] = field(default_factory=list)


@dataclass
class Group(MathNode):
    """An explicit ``{...}`` group: rendered invisibly, exported with braces."""

    items: MathSequence = field(default_factory=MathSequence)


@dataclass
class Frac(MathNode):
    numerator: MathSequence = field(default_factory=MathSequence)
    denominator: MathSequence = field(default_factory=MathSequence)


@dataclass
class Sqrt(MathNode):
    radicand: MathSequence = field(default_factory=MathSequence)


@dataclass
class Script(MathNode):
    """A base with an optional superscript and/or subscript."""

    base: MathSequence = field(default_factory=MathSequence)
    super: MathSequence | None = None
    sub: MathSequence | None = None
    super_raw: str | None = None
    super_braced: bool = True
    sub_raw: str | None = None
    sub_braced: bool = True


@dataclass
class BigOp(MathNode):
    """A large operator such as ``\\sum``, ``\\int`` or ``\\lim``.

    ``body`` is the operand rendered after the operator; ``lower``/``upper``
    are the optional script limits.
    """

    symbol: str = "sum"
    lower: MathSequence | None = None
    upper: MathSequence | None = None
    body: MathSequence = field(default_factory=MathSequence)
    lower_raw: str | None = None
    lower_braced: bool = True
    upper_raw: str | None = None
    upper_braced: bool = True


_SYMBOL_COMMANDS = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "varepsilon": "ε",
    "zeta": "ζ",
    "eta": "η",
    "theta": "θ",
    "vartheta": "ϑ",
    "iota": "ι",
    "kappa": "κ",
    "lambda": "λ",
    "mu": "μ",
    "nu": "ν",
    "xi": "ξ",
    "pi": "π",
    "rho": "ρ",
    "sigma": "σ",
    "tau": "τ",
    "upsilon": "υ",
    "phi": "φ",
    "varphi": "φ",
    "chi": "χ",
    "psi": "ψ",
    "omega": "ω",
    "Gamma": "Γ",
    "Delta": "Δ",
    "Theta": "Θ",
    "Lambda": "Λ",
    "Xi": "Ξ",
    "Pi": "Π",
    "Sigma": "Σ",
    "Upsilon": "Υ",
    "Phi": "Φ",
    "Psi": "Ψ",
    "Omega": "Ω",
    "cdot": "·",
    "times": "×",
    "div": "÷",
    "pm": "±",
    "mp": "∓",
    "leq": "≤",
    "geq": "≥",
    "neq": "≠",
    "approx": "≈",
    "equiv": "≡",
    "to": "→",
    "rightarrow": "→",
    "leftarrow": "←",
    "leftrightarrow": "↔",
    "infty": "∞",
    "partial": "∂",
    "nabla": "∇",
    "in": "∈",
    "notin": "∉",
    "subset": "⊂",
    "subseteq": "⊆",
    "cup": "∪",
    "cap": "∩",
    "dots": "…",
    "ldots": "…",
    "cdots": "⋯",
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "log": "log",
    "ln": "ln",
    "exp": "exp",
}

_CONTROL_SYMBOLS = {
    "\\{": "{",
    "\\}": "}",
    "\\|": "‖",
    "\\%": "%",
    "\\#": "#",
    "\\&": "&",
    "\\_": "_",
    "\\$": "$",
    "\\,": " ",
    "\\;": " ",
    "\\!": "",
    "\\ ": " ",
}


def latex_of(node: MathNode) -> str:
    """Render a math tree back to LaTeX text."""

    if isinstance(node, Text):
        return node.text
    if isinstance(node, Command):
        return node.latex
    if isinstance(node, MathSequence):
        parts: list[str] = []
        for index, item in enumerate(node.items):
            piece = latex_of(item)
            if index > 0 and _needs_command_space(node.items[index - 1], piece):
                parts.append(" ")
            parts.append(piece)
        return "".join(parts)
    if isinstance(node, Group):
        return "{" + latex_of(node.items) + "}"
    if isinstance(node, Frac):
        return "\\frac{" + latex_of(node.numerator) + "}{" + latex_of(node.denominator) + "}"
    if isinstance(node, Sqrt):
        return "\\sqrt{" + latex_of(node.radicand) + "}"
    if isinstance(node, Script):
        out = latex_of(node.base)
        if node.super is not None:
            out += "^" + _script_fragment(node.super, node.super_raw, node.super_braced)
        if node.sub is not None:
            out += "_" + _script_fragment(node.sub, node.sub_raw, node.sub_braced)
        return out
    if isinstance(node, BigOp):
        out = "\\" + node.symbol
        if node.lower is not None:
            out += "_" + _script_fragment(node.lower, node.lower_raw, node.lower_braced)
        if node.upper is not None:
            out += "^" + _script_fragment(node.upper, node.upper_raw, node.upper_braced)
        out += latex_of(node.body)
        return out
    raise TypeError(f"unknown math node: {type(node).__name__}")


def symbol_display(name: str) -> str | None:
    """Return the display form for a known symbol command, or None."""

    return _SYMBOL_COMMANDS.get(name)


def _needs_command_space(previous: MathNode, next_latex: str) -> bool:
    return (
        isinstance(previous, Command)
        and len(previous.latex) > 1
        and previous.latex[1].isalpha()
        and bool(next_latex)
        and next_latex[0].isalpha()
    )


def _script_fragment(sequence: MathSequence, raw: str | None, braced: bool) -> str:
    current = latex_of(sequence)
    if raw is not None and current == raw:
        return ("{" + raw + "}") if braced else raw
    if len(current) == 1 and current not in "{}":
        return current
    return "{" + current + "}"


def parse_math_latex(text: str) -> MathSequence:
    """Parse a math body into a MathSequence, preserving unsupported content.

    The parser is intentionally lossless: unknown commands, environments, and
    malformed fragments are kept as raw text/command nodes so export matches
    the input exactly. See module docstring for the fallback contract.
    """

    parser = _Parser(text)
    return parser.parse_sequence()


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.length = len(text)
        self.index = 0

    def parse_sequence(self) -> MathSequence:
        seq = MathSequence()
        while self.index < self.length:
            char = self.text[self.index]
            if char == "\\":
                self._parse_command(seq)
            elif char == "{":
                inner, after = self._braced(self.index)
                if inner is None:
                    seq.items.append(Text("{"))
                    self.index += 1
                else:
                    seq.items.append(Group(self.parse_math(inner)))
                    self.index = after
            elif char == "}":
                seq.items.append(Text("}"))
                self.index += 1
            elif char in "^_":
                self._parse_script(seq, char)
            else:
                run_end = self.index
                while run_end < self.length and self.text[run_end] not in "\\{}^_":
                    run_end += 1
                seq.items.append(Text(self.text[self.index : run_end]))
                self.index = run_end
        return seq

    def parse_math(self, text: str) -> MathSequence:
        saved = self.text, self.length, self.index
        self.text, self.length, self.index = text, len(text), 0
        try:
            return self.parse_sequence()
        finally:
            self.text, self.length, self.index = saved

    def _parse_command(self, seq: MathSequence) -> None:
        name_start = self.index + 1
        if name_start < self.length and self.text[name_start].isalpha():
            name_end = name_start
            while name_end < self.length and self.text[name_end].isalpha():
                name_end += 1
            name = self.text[name_start:name_end]
            if name == "frac":
                numerator, after = self._braced(name_end)
                denominator, after = self._braced(after)
                if numerator is not None and denominator is not None:
                    seq.items.append(
                        Frac(
                            numerator=self.parse_math(numerator),
                            denominator=self.parse_math(denominator),
                        )
                    )
                    self.index = after
                    return
                seq.items.append(Command(latex=r"\frac", display=r"\frac"))
                self.index = name_end
                return
            if name == "sqrt":
                radicand, after = self._braced(name_end)
                if radicand is not None:
                    seq.items.append(Sqrt(radicand=self.parse_math(radicand)))
                    self.index = after
                    return
                seq.items.append(Command(latex=r"\sqrt", display=r"\sqrt"))
                self.index = name_end
                return
            if name in ("sum", "int", "lim"):
                op = BigOp(symbol=name)
                index = name_end
                lower = self._optional_script(index, "_")
                if lower is not None:
                    op.lower = self.parse_math(lower[0])
                    op.lower_raw = lower[0]
                    op.lower_braced = self._limit_braced(index, "_")
                    index = lower[1]
                upper = self._optional_script(index, "^")
                if upper is not None:
                    op.upper = self.parse_math(upper[0])
                    op.upper_raw = upper[0]
                    op.upper_braced = self._limit_braced(index, "^")
                    index = upper[1]
                seq.items.append(op)
                self.index = index
                return
            if name in _SYMBOL_COMMANDS:
                seq.items.append(
                    Command(latex="\\" + name, display=_SYMBOL_COMMANDS[name])
                )
                self.index = name_end
                return
            # Unknown command: preserve raw text so export round-trips.
            seq.items.append(Command(latex="\\" + name, display="\\" + name))
            self.index = name_end
            return

        if name_start >= self.length:
            seq.items.append(Text("\\"))
            self.index = self.length
            return
        control = "\\" + self.text[name_start]
        if control in _CONTROL_SYMBOLS:
            seq.items.append(Command(latex=control, display=_CONTROL_SYMBOLS[control]))
        else:
            seq.items.append(Command(latex=control, display=control))
        self.index = name_start + 1

    def _parse_script(self, seq: MathSequence, marker: str) -> None:
        argument = self._script_argument(self.index, marker)
        if argument is None:
            seq.items.append(Text(marker))
            self.index += 1
            return
        content, after = argument
        base = seq.items.pop() if seq.items else None
        if isinstance(base, Script):
            if marker == "^":
                base.super = self.parse_math(content)
                base.super_raw = content
                base.super_braced = self._argument_braced(marker)
            else:
                base.sub = self.parse_math(content)
                base.sub_raw = content
                base.sub_braced = self._argument_braced(marker)
            seq.items.append(base)
        else:
            base_sequence = MathSequence(items=[base]) if base is not None else MathSequence()
            script = Script(base=base_sequence)
            if marker == "^":
                script.super = self.parse_math(content)
                script.super_raw = content
                script.super_braced = self._argument_braced(marker)
            else:
                script.sub = self.parse_math(content)
                script.sub_raw = content
                script.sub_braced = self._argument_braced(marker)
            seq.items.append(script)
        self.index = after

    def _argument_braced(self, marker: str) -> bool:
        return self.index + 1 < self.length and self.text[self.index + 1] == "{"

    def _limit_braced(self, index: int, marker: str) -> bool:
        return index + 1 < self.length and self.text[index + 1] == "{"

    def _script_argument(self, index: int, marker: str) -> tuple[str, int] | None:
        if index + 1 >= self.length:
            return None
        if self.text[index + 1] == "{":
            return self._braced(index + 1)
        if self.text[index + 1] not in "\\{}^_":
            return self.text[index + 1], index + 2
        return None

    def _optional_script(self, index: int, marker: str) -> tuple[str, int] | None:
        if index >= self.length or self.text[index] != marker:
            return None
        return self._script_argument(index, marker)

    def _braced(self, open_index: int) -> tuple[str | None, int]:
        """Return (inner_text, index_after) for a balanced ``{...}`` group."""

        if open_index >= self.length or self.text[open_index] != "{":
            return None, open_index
        depth = 0
        index = open_index
        while index < self.length:
            char = self.text[index]
            if char == "\\" and index + 1 < self.length:
                index += 2
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return self.text[open_index + 1 : index], index + 1
            index += 1
        return None, open_index
