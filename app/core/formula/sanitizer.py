"""Formula LaTeX sanitizer for OCR candidates and external input.

OCR output must never reach a project directly: strip wrappers, reject
document/command/file/URL constructs, enforce length/depth limits, and keep
the original text intact on failure so the user can fix it in source mode.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


FORBIDDEN_COMMANDS = {
    "input",
    "include",
    "includegraphics",
    "write",
    "write18",
    "openout",
    "read",
    "usepackage",
    "documentclass",
    "catcode",
    "csname",
    "newcommand",
    "renewcommand",
    "def",
    "loop",
    "inputencoding",
    "immediate",
    "closeout",
    "special",
    "href",
    "url",
}

FORBIDDEN_ENVIRONMENTS = {"document", "verbatim", "filecontents", "lstlisting", "tikzpicture"}

MAX_LATEX_LENGTH = 2000
MAX_BRACE_DEPTH = 64

_COMMAND_RE = re.compile(r"\\([A-Za-z]+)")
_ENV_RE = re.compile(r"\\begin\{([^}]+)\}")
_URL_RE = re.compile(r"(?:https?://|file://|ftp://|~/|(?<![\\A-Za-z])[A-Za-z]:[\\/])")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass(frozen=True)
class SanitizeResult:
    text: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def strip_wrappers(latex: str) -> str:
    """Remove a single $...$, $$...$$, \\(...\\) or \\[...\\] wrapper."""
    text = latex.strip()
    if text.startswith("$$") and text.endswith("$$") and len(text) >= 4:
        return text[2:-2].strip()
    if text.startswith("$") and text.endswith("$") and len(text) >= 2:
        return text[1:-1].strip()
    if text.startswith(r"\(") and text.endswith(r"\)") and len(text) >= 4:
        return text[2:-2].strip()
    if text.startswith(r"\[") and text.endswith(r"\]") and len(text) >= 4:
        return text[2:-2].strip()
    return text


def sanitize_formula_latex(raw: str) -> SanitizeResult:
    """Validate an OCR candidate; returns errors that block auto-commit."""
    text = strip_wrappers(raw)
    warnings: list[str] = []
    errors: list[str] = []

    if not text.strip():
        errors.append("empty_formula")
        return SanitizeResult(text=text, warnings=warnings, errors=errors)
    if len(text) > MAX_LATEX_LENGTH:
        errors.append(f"too_long:{len(text)}")
    if _CONTROL_CHAR_RE.search(text):
        errors.append("control_characters")
    if _URL_RE.search(text):
        errors.append("url_or_path")
    if _COMMAND_RE.search(text):
        commands = {match.group(1).lower() for match in _COMMAND_RE.finditer(text)}
        forbidden = commands & FORBIDDEN_COMMANDS
        if forbidden:
            errors.append("forbidden_command:" + ",".join(sorted(forbidden)))
    environments = {match.group(1).lower() for match in _ENV_RE.finditer(text)}
    if environments & FORBIDDEN_ENVIRONMENTS:
        errors.append("forbidden_environment:" + ",".join(sorted(environments & FORBIDDEN_ENVIRONMENTS)))

    depth = 0
    max_depth = 0
    for char in text:
        if char == "{":
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == "}":
            depth = max(0, depth - 1)
    if max_depth > MAX_BRACE_DEPTH:
        errors.append(f"too_deep:{max_depth}")

    if len(text) > MAX_LATEX_LENGTH * 4 // 5:
        warnings.append("near_length_limit")
    return SanitizeResult(text=text, warnings=warnings, errors=errors)
