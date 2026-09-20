"""Bounded rectangular text clipboard rules, without header inference."""
from __future__ import annotations

import csv
import io

MAX_CLIPBOARD_CELLS = 100_000

def parse_grid(text: str, *, max_rows: int, max_columns: int) -> list[list[str]]:
    """Preserve empty cells/rows and reject oversize input without truncation."""
    if not text:
        return []
    if len(text) > 2_000_000:
        raise ValueError("Clipboard text is too large.")
    delimiter = "\t" if "\t" in text else ","
    rows: list[list[str]] = []
    try:
        for row in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True):
            if len(rows) >= max_rows or len(row) > max_columns:
                raise ValueError(f"Paste exceeds {max_rows} rows or {max_columns} columns.")
            rows.append(row or [""])
    except csv.Error as exc:
        raise ValueError("Invalid CSV quoting.") from exc
    width = max((len(row) for row in rows), default=0)
    if len(rows) * width > MAX_CLIPBOARD_CELLS:
        raise ValueError("Clipboard rectangle exceeds the cell limit.")
    return [row + [""] * (width - len(row)) for row in rows]


def format_grid(rows: list[list[str]]) -> str:
    stream = io.StringIO(newline="")
    csv.writer(stream, delimiter="\t", lineterminator="\n").writerows(rows)
    return stream.getvalue()
