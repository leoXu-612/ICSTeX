"""LaTeX special-character escaping for user text."""
from __future__ import annotations


LATEX_ESCAPES = {"\\": r"\textbackslash{}", "#": r"\#", "$": r"\$", "%": r"\%",
                 "&": r"\&", "_": r"\_", "{": r"\{", "}": r"\}",
                 "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}

def escape_latex(text: str) -> str:
    """Escape once: never re-escape braces introduced by another replacement."""
    return text.translate(str.maketrans(LATEX_ESCAPES))
