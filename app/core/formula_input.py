"""Source-first visual formula composer: pure core contract (DS-001).

Deterministic, pure-Python rules for recognizing LaTeX formula envelopes,
rendering formula drafts, and planning selection-aware template edits. LaTeX
text is the only source of truth for formula content.

Canonicalization contract
-------------------------
Changing a draft's formula mode may intentionally regenerate the outer
wrapper (for example, ``$a+b$`` becomes ``\\begin{equation}a+b\\end{equation}``),
but the body is never rewritten: whitespace, comments, custom macros, and
unknown commands are preserved byte-for-byte.

Safety contract
---------------
- Only an exact, complete formula envelope is recognized: ``$...$``,
  ``\\(...\\)``, ``\\[...\\]``, ``equation``, and ``equation*``.
- Incomplete, ambiguous, multi-formula, or structurally unsafe selections
  return ``None`` (non-applicable); the caller must never guess a replacement
  range.
- Escape sequences and ``%`` comments are respected, so an escaped or
  commented-out closing delimiter is never treated as a real one.
- Delimiter checks are deliberately conservative: unescaped math delimiters
  or nested equation tags anywhere in a body, including inside text commands,
  make the selection non-applicable because static analysis cannot prove they
  are inert.

This module must stay free of PySide6, ``app.gui``, filesystem I/O,
subprocesses, networking, and TeX compilation; it returns data only.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Callable


_MODE_WRAPPERS = {
    "inline_dollar": ("$", "$"),
    "inline_paren": (r"\(", r"\)"),
    "display_bracket": (r"\[", r"\]"),
    "equation": (r"\begin{equation}", r"\end{equation}"),
    "equation_star": (r"\begin{equation*}", r"\end{equation*}"),
}

_ENV_TAGS = (
    r"\begin{equation}",
    r"\begin{equation*}",
    r"\end{equation}",
    r"\end{equation*}",
)


class FormulaMode(Enum):
    """Immutable formula wrapper mode; wrapper text is regenerable data."""

    INLINE_DOLLAR = "inline_dollar"
    INLINE_PAREN = "inline_paren"
    DISPLAY_BRACKET = "display_bracket"
    EQUATION = "equation"
    EQUATION_STAR = "equation_star"

    @property
    def wrapper_prefix(self) -> str:
        return _MODE_WRAPPERS[self.value][0]

    @property
    def wrapper_suffix(self) -> str:
        return _MODE_WRAPPERS[self.value][1]

    @property
    def is_display(self) -> bool:
        return self in (FormulaMode.DISPLAY_BRACKET, FormulaMode.EQUATION, FormulaMode.EQUATION_STAR)


@dataclass(frozen=True)
class FormulaDraft:
    """An immutable formula: a mode plus the exact body text."""

    mode: FormulaMode
    body: str


@dataclass(frozen=True)
class ParsedEnvelope:
    """A recognized exact formula envelope with its text range."""

    mode: FormulaMode
    body: str
    start: int
    end: int


@dataclass(frozen=True)
class TemplateEditResult:
    """Result of applying a template to a draft; pure data, no mutation."""

    template: str
    draft: FormulaDraft
    packages: tuple[str, ...] = ()
    cursor_offset: int | None = None  # offset inside draft.body


@dataclass(frozen=True)
class FinalTextEditPlan:
    """Pure text replacement plan; execution belongs to the GUI layer."""

    start: int
    end: int
    source_text: str
    text: str
    packages: tuple[str, ...] = ()
    cursor_offset: int | None = None  # offset inside text, relative to start


def render_formula(draft: FormulaDraft) -> str:
    """Render a draft as LaTeX text, regenerating only the outer wrapper."""

    return draft.mode.wrapper_prefix + draft.body + draft.mode.wrapper_suffix


def change_formula_mode(draft: FormulaDraft, mode: FormulaMode) -> FormulaDraft:
    """Return a draft in ``mode`` with the body preserved byte-for-byte.

    This is the documented canonicalization path: the wrapper may be
    regenerated, but the body is never rewritten.
    """

    return FormulaDraft(mode=mode, body=draft.body)


def recognize_formula(text: str) -> ParsedEnvelope | None:
    """Recognize ``text`` as exactly one formula envelope, or return None.

    The returned envelope carries offsets relative to ``text`` (start=0,
    end=len(text)). Invalid input is never partially recognized.
    """

    parsed = (
        _parse_inline_dollar(text)
        or _parse_control_pair(text, r"\(", r"\)", FormulaMode.INLINE_PAREN)
        or _parse_control_pair(text, r"\[", r"\]", FormulaMode.DISPLAY_BRACKET)
        or _parse_equation(text, starred=False)
        or _parse_equation(text, starred=True)
    )
    if parsed is None:
        return None
    mode, body = parsed
    return ParsedEnvelope(mode=mode, body=body, start=0, end=len(text))


def parse_document_selection(document: str, start: int, end: int) -> ParsedEnvelope | None:
    """Recognize ``document[start:end]`` as exactly one formula envelope.

    Returns an envelope with absolute offsets, or None when the range is
    out of bounds or the selection is not exactly one formula. The range is
    never guessed or extended.
    """

    if not (0 <= start <= end <= len(document)):
        return None
    envelope = recognize_formula(document[start:end])
    if envelope is None:
        return None
    return ParsedEnvelope(mode=envelope.mode, body=envelope.body, start=start, end=end)


def mode_packages(mode: FormulaMode) -> tuple[str, ...]:
    """Packages required by a wrapper mode, as data.

    ``equation`` is a LaTeX kernel environment; ``equation*`` requires
    amsmath. The inline and bracket wrappers require no package.
    """

    if mode is FormulaMode.EQUATION_STAR:
        return ("amsmath",)
    return ()


FORMULA_TEMPLATE_KEYS: tuple[str, ...] = (
    "fraction",
    "sqrt",
    "superscript",
    "subscript",
    "sum",
    "integral",
    "greek_alpha",
)


def apply_formula_template(draft: FormulaDraft, template: str) -> TemplateEditResult | None:
    """Apply a deterministic template to a draft; returns data or None.

    The mode is preserved; only the body is transformed by the template rule.
    Empty bodies and unknown template keys return an explicit non-applicable
    result where the rule cannot produce a safe edit.
    """

    rule = _TEMPLATE_RULES.get(template)
    if rule is None:
        return None
    transformed = rule(draft.body)
    if transformed is None:
        return None
    new_body, cursor_offset = transformed
    return TemplateEditResult(
        template=template,
        draft=FormulaDraft(mode=draft.mode, body=new_body),
        packages=_template_packages(template),
        cursor_offset=cursor_offset,
    )


def final_edit_plan(
    document: str,
    start: int,
    end: int,
    draft: FormulaDraft,
    *,
    body_cursor_offset: int | None = None,
    packages: tuple[str, ...] = (),
) -> FinalTextEditPlan | None:
    """Build the text replacement plan for a validated formula selection.

    With a non-empty range, the current selection must still be exactly one
    formula envelope; otherwise None is returned and nothing is planned. With
    an empty range (start == end), this is an insertion: the draft itself must
    render as a complete formula envelope, and the plan inserts it at the
    cursor without touching existing content. The plan carries the full
    replacement text, the exact source text it replaces ("" for insertion),
    required package names, and an optional cursor offset. No editor, file,
    or state is touched.
    """

    if not (0 <= start <= end <= len(document)):
        return None
    if start < end:
        if parse_document_selection(document, start, end) is None:
            return None
    elif recognize_formula(render_formula(draft)) is None:
        return None
    text = render_formula(draft)
    source_text = document[start:end]
    cursor_offset = None
    if body_cursor_offset is not None:
        cursor_offset = len(draft.mode.wrapper_prefix) + body_cursor_offset
    merged_packages = tuple(dict.fromkeys((*mode_packages(draft.mode), *packages)))
    return FinalTextEditPlan(
        start=start,
        end=end,
        source_text=source_text,
        text=text,
        packages=merged_packages,
        cursor_offset=cursor_offset,
    )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _backslashes_before(text: str, index: int) -> int:
    count = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        count += 1
        index -= 1
    return count


def _is_escaped_char(text: str, index: int) -> bool:
    """True when text[index] is escaped by an odd run of backslashes."""

    return _backslashes_before(text, index) % 2 == 1


def _is_real_control_symbol(text: str, index: int) -> bool:
    """True when text[index:index+2] is a real TeX control symbol.

    TeX consumes backslashes left to right: ``\\`` pairs are line breaks and
    a control symbol (``\\(``, ``\\)``, ``\\[``, ``\\]``) is real only when
    the backslash run ending at ``index`` has odd length.
    """

    count = 1
    index -= 1
    while index >= 0 and text[index] == "\\":
        count += 1
        index -= 1
    return count % 2 == 1


def _comment_consumes_tail(body: str) -> bool:
    """True when an unescaped ``%`` comments out the end of ``body``."""

    in_comment = False
    for index, char in enumerate(body):
        if in_comment:
            if char == "\n":
                in_comment = False
            continue
        if char == "%" and not _is_escaped_char(body, index):
            in_comment = True
    return in_comment


def _body_has_unsafe_delimiters(body: str) -> bool:
    """True when the body contains delimiters that make it structurally unsafe.

    Comment content is skipped before checks. Unescaped math shifts, real math
    control delimiters, and equation environment tags are rejected even inside
    text commands, because static analysis cannot prove such content is inert;
    the selection is then non-applicable.
    """

    in_comment = False
    index = 0
    while index < len(body):
        char = body[index]
        if in_comment:
            if char == "\n":
                in_comment = False
            index += 1
            continue
        if char == "%" and not _is_escaped_char(body, index):
            in_comment = True
            index += 1
            continue
        if char == "$" and not _is_escaped_char(body, index):
            return True
        if (
            char in "()[]"
            and index > 0
            and body[index - 1] == "\\"
            and _is_real_control_symbol(body, index - 1)
        ):
            return True
        if any(body.startswith(tag, index) for tag in _ENV_TAGS):
            return True
        index += 1
    return False


def _parse_inline_dollar(text: str) -> tuple[FormulaMode, str] | None:
    if len(text) < 2 or text[0] != "$" or text[-1] != "$":
        return None
    if _is_escaped_char(text, len(text) - 1):
        return None  # trailing \$ is not a real closing delimiter
    body = text[1:-1]
    if not body:
        return None  # "$$" is the display-math delimiter pair, not an inline envelope
    if _comment_consumes_tail(body) or _body_has_unsafe_delimiters(body):
        return None
    return FormulaMode.INLINE_DOLLAR, body


def _parse_control_pair(
    text: str, opener: str, closer: str, mode: FormulaMode
) -> tuple[FormulaMode, str] | None:
    if not text.startswith(opener) or not text.endswith(closer):
        return None
    close_index = len(text) - len(closer)
    if not _is_real_control_symbol(text, close_index):
        return None  # the trailing pair is an escaped literal, not a real close
    body = text[len(opener):close_index]
    if _comment_consumes_tail(body) or _body_has_unsafe_delimiters(body):
        return None
    return mode, body


def _parse_equation(text: str, *, starred: bool) -> tuple[FormulaMode, str] | None:
    begin = r"\begin{equation*}" if starred else r"\begin{equation}"
    end = r"\end{equation*}" if starred else r"\end{equation}"
    if not text.startswith(begin) or not text.endswith(end):
        return None
    body = text[len(begin):-len(end)]
    if _comment_consumes_tail(body) or _body_has_unsafe_delimiters(body):
        return None
    return (FormulaMode.EQUATION_STAR if starred else FormulaMode.EQUATION), body


# ---------------------------------------------------------------------------
# Template rules
# ---------------------------------------------------------------------------


_SINGLE_TOKEN_RE = re.compile(r"[A-Za-z0-9]|\\(?:[a-zA-Z]+|.)|\{.*\}")


def _is_single_token(body: str) -> bool:
    """True when the body is one base token that needs no grouping braces."""

    return _SINGLE_TOKEN_RE.fullmatch(body) is not None


def _apply_fraction(body: str) -> tuple[str, int]:
    new_body = r"\frac{" + body + r"}{}"
    return new_body, len(r"\frac{") + len(body) + 2


def _apply_sqrt(body: str) -> tuple[str, int]:
    new_body = r"\sqrt{" + body + "}"
    return new_body, len(r"\sqrt{") + len(body)


def _apply_superscript(body: str) -> tuple[str, int] | None:
    if not body:
        return None  # superscript on an empty base would be invalid TeX
    base = body if _is_single_token(body) else "{" + body + "}"
    new_body = base + "^{}"
    return new_body, len(base) + 2


def _apply_subscript(body: str) -> tuple[str, int] | None:
    if not body:
        return None  # subscript on an empty base would be invalid TeX
    base = body if _is_single_token(body) else "{" + body + "}"
    new_body = base + "_{}"
    return new_body, len(base) + 2


def _apply_sum(body: str) -> tuple[str, int]:
    new_body = r"\sum_{}^{}" + body
    return new_body, len(r"\sum_{")


def _apply_integral(body: str) -> tuple[str, int]:
    new_body = r"\int_{}^{}" + body
    return new_body, len(r"\int_{")


def _apply_greek_alpha(body: str) -> tuple[str, int]:
    new_body = r"\alpha" if not body else r"\alpha " + body
    return new_body, len(new_body)


def _template_packages(template: str) -> tuple[str, ...]:
    # Every MVP template (fraction, sqrt, super/subscript, sum, integral,
    # greek alpha) is defined by the LaTeX kernel; none requires a package.
    return ()


_TEMPLATE_RULES: dict[str, Callable[[str], tuple[str, int] | None]] = {
    "fraction": _apply_fraction,
    "sqrt": _apply_sqrt,
    "superscript": _apply_superscript,
    "subscript": _apply_subscript,
    "sum": _apply_sum,
    "integral": _apply_integral,
    "greek_alpha": _apply_greek_alpha,
}
