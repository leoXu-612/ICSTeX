"""Multi-line formula image splitter (projection-based line segmentation).

pix2tex recognises single-line formulas; this module splits a multi-line
formula image into per-line crops using horizontal dark-row bands, so each
line can be OCR'd separately and re-joined in an ``aligned`` environment.
Operates on QImage only (no new dependencies).
"""
from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QImage


DARK_THRESHOLD = 140
MIN_DARK_RATIO = 0.01
GAP_TOLERANCE = 4
PADDING = 6


def _row_dark_counts(image: QImage) -> tuple[list[int], int]:
    gray = image.convertToFormat(QImage.Format.Format_Grayscale8)
    width, height = gray.width(), gray.height()
    bytes_per_line = gray.bytesPerLine()
    data = bytes(gray.bits())
    counts: list[int] = []
    for y in range(height):
        start = y * bytes_per_line
        counts.append(sum(1 for value in data[start : start + width] if value < DARK_THRESHOLD))
    return counts, width


def split_formula_lines(image: QImage, *, padding: int = PADDING) -> list[QImage]:
    """Split a formula image into single-line crops (top-to-bottom)."""
    width, height = image.width(), image.height()
    if width == 0 or height == 0:
        return []
    counts, width = _row_dark_counts(image)
    min_dark = max(1, int(width * MIN_DARK_RATIO))

    content_rows = [count >= min_dark for count in counts]
    bands: list[tuple[int, int]] = []
    start: int | None = None
    for y, is_content in enumerate(content_rows):
        if is_content and start is None:
            start = y
        elif not is_content and start is not None:
            if y - start > 1:
                bands.append((start, y - 1))
            start = None
    if start is not None:
        bands.append((start, height - 1))

    merged: list[tuple[int, int]] = []
    for band in bands:
        if merged and band[0] - merged[-1][1] - 1 <= GAP_TOLERANCE:
            merged[-1] = (merged[-1][0], band[1])
        else:
            merged.append(band)

    gray = image.convertToFormat(QImage.Format.Format_Grayscale8)
    bytes_per_line = gray.bytesPerLine()
    data = bytes(gray.bits())
    crops: list[QImage] = []
    for y0, y1 in merged:
        x_min = width
        x_max = -1
        for y in range(y0, y1 + 1):
            row = data[y * bytes_per_line : y * bytes_per_line + width]
            for x, value in enumerate(row):
                if value < DARK_THRESHOLD:
                    if x < x_min:
                        x_min = x
                    if x > x_max:
                        x_max = x
        if x_max < x_min:
            continue
        rect = QRect(
            max(0, x_min - padding),
            max(0, y0 - padding),
            min(width, x_max + padding) - max(0, x_min - padding),
            min(height, y1 + padding) - max(0, y0 - padding),
        )
        crops.append(image.copy(rect))
    return crops
