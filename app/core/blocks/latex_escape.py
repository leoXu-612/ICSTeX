"""LaTeX special-character escaping for user text."""
from __future__ import annotations


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in user text (backslash first)."""

    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("#", r"\#")
        .replace("$", r"\$")
        .replace("%", r"\%")
        .replace("&", r"\&")
        .replace("_", r"\_")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("~", r"\textasciitilde{}")
        .replace("^", r"\textasciicircum{}")
    )
