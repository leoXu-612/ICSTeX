"""Deterministic DocumentTheme -> ``.sty`` generator (Sprint 5).

The app theme is never consumed here: only the document theme changes the
final PDF. Output is byte-stable for the same theme (no timestamps, no
absolute paths, fixed order).
"""
from __future__ import annotations

from app.core.blocks.theme import DocumentTheme


def render_document_theme_sty(theme: DocumentTheme) -> str:
    lines = [
        "% ICSTEX:document-theme " + theme.id,
        "% Generated deterministically; do not edit by hand.",
    ]
    page = theme.page or {}
    margins = page.get("margin", {}) or {}
    geometry_options: list[str] = []
    size = str(page.get("size", "a4")).lower()
    if size in ("a4", "letter"):
        geometry_options.append(size + "paper")
    if page.get("orientation") == "landscape":
        geometry_options.append("landscape")
    for geometry_key, margin_key in (
        ("top", "topMm"),
        ("bottom", "bottomMm"),
        ("left", "leftMm"),
        ("right", "rightMm"),
    ):
        value = margins.get(margin_key)
        if value is not None:
            geometry_options.append(f"{geometry_key}={value}mm")
    if geometry_options:
        lines.append(f"\\usepackage[{','.join(geometry_options)}]{{geometry}}")

    typography = theme.typography or {}
    text_family = str(typography.get("textFamily") or "").strip()
    if text_family:
        lines.append("\\usepackage{fontspec}")
        lines.append(f"\\setmainfont{{{_escape_family(text_family)}}}")
    line_spacing = typography.get("lineSpacing")
    if line_spacing:
        lines.append(f"\\linespread{{{float(line_spacing):.2f}}}")

    tables = theme.tables or {}
    preset = tables.get("preset", "booktabs")
    if preset == "booktabs":
        lines.append("\\usepackage{booktabs}")
    if tables.get("verticalRules") is False:
        lines.append("% ICSTEX:table vertical rules disabled")

    headings = theme.headings or {}
    section = headings.get("section") or {}
    before = section.get("spaceBeforePt")
    after = section.get("spaceAfterPt")
    if before is not None or after is not None:
        lines.append("\\usepackage{titlesec}")
        lines.append(
            f"\\titlespacing*{{\\section}}{{0pt}}{{{before or 12}pt}}{{{after or 6}pt}}"
        )

    layout = theme.layout or {}
    block_gap = layout.get("blockGapPt")
    if block_gap:
        lines.append(f"\\setlength{{\\parskip}}{{{float(block_gap):.0f}pt}}")
    return "\n".join(lines) + "\n"


def _escape_family(name: str) -> str:
    return name.replace("\\", " ").replace("{", " ").replace("}", " ").strip()
