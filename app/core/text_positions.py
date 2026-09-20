"""Explicit boundaries between Python character indexes and UTF-16 offsets."""
from __future__ import annotations


def utf16_length(text: str) -> int:
    """Return the number of UTF-16 code units, without a byte-order marker."""
    return len(text.encode("utf-16-le")) // 2


def python_index_from_utf16(text: str, position: int) -> int | None:
    """Translate an exact boundary; reject out-of-range or split-surrogate offsets."""
    if position < 0:
        return None
    encoded = text.encode("utf-16-le")
    if position * 2 > len(encoded):
        return None
    try:
        return len(encoded[:position * 2].decode("utf-16-le"))
    except UnicodeDecodeError:
        return None
