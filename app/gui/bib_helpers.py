"""Per-tab BibTeX file/text helpers and bibliography block insertion."""
from __future__ import annotations

from pathlib import Path

from app.core.project_tools import ensure_bibliography
from app.core.text_encoding import write_latex_text_atomic
from app.gui.main_window_support import EditorTab


def bib_file_for_tab(tab: EditorTab, *, create: bool = False) -> Path | None:
    if tab.path is None:
        return None
    project_dir = tab.path.parent
    nested = project_dir / "bib" / "references.bib"
    flat = project_dir / "references.bib"
    target = nested if nested.exists() or not flat.exists() else flat
    if create:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            write_latex_text_atomic(target, "% 在这里添加 BibTeX 条目。\n", encoding="utf-8")
    return target


def bib_text_for_tab(tab: EditorTab) -> str:
    bib_file = bib_file_for_tab(tab)
    if bib_file is None or not bib_file.exists():
        return ""
    try:
        return bib_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def ensure_bibliography_block(tab: EditorTab) -> None:
    """Ensure the document has a ``\\bibliography{...}`` block, preserving cursor."""
    editor = tab.editor
    old_text = editor.toPlainText()
    new_text = ensure_bibliography(old_text)
    if new_text == old_text:
        return
    cursor = editor.textCursor()
    old_position = cursor.position()
    editor.setPlainText(new_text)
    cursor = editor.textCursor()
    cursor.setPosition(min(old_position, len(new_text)))
    editor.setTextCursor(cursor)
