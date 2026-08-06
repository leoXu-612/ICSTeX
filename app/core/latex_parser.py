"""Project-wide ``pylatexenc`` configuration.

Provides a reusable ``LatexWalker`` with the custom macros our heuristics need
(``\\href``, ``\\caption``, ``\\captionof``, etc.) registered so their arguments
are attached to the macro node rather than appearing as sibling group nodes.
"""
from __future__ import annotations

from pylatexenc.latexwalker import LatexWalker, get_default_latex_context_db
from pylatexenc.macrospec import MacroSpec


# Macros not in pylatexenc's default DB that we still want fully parsed.
# Argument signature legend (pylatexenc 2.x):
#   "{"  required group arg
#   "["  optional bracket arg
#   "*"  optional star
_CUSTOM_MACROS: tuple[tuple[str, str], ...] = (
    # Hyperlinks / citations
    ("href", "{{"),
    ("parencite", "[{"),
    ("textcite", "[{"),
    ("autocite", "[{"),
    ("pageref", "{"),
    # Captions and floats
    ("caption", "[{"),
    ("captionof", "{{"),
    # Document structure
    ("paragraph", "{"),
    ("part", "{"),
    ("addbibresource", "{"),
    ("bibliographystyle", "{"),
)


def _build_context_db():
    db = get_default_latex_context_db()
    macros = [MacroSpec(name, args_parser=sig) for name, sig in _CUSTOM_MACROS]
    db.add_context_category("icstex-custom", macros=macros, prepend=True)
    return db


_CONTEXT_DB = _build_context_db()


def make_walker(text: str, *, tolerant: bool = True) -> LatexWalker:
    """Return a ``LatexWalker`` configured for ICSTeX heuristics."""
    return LatexWalker(text, latex_context=_CONTEXT_DB, tolerant_parsing=tolerant)
