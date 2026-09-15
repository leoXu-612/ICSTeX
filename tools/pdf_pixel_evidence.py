"""Pixel presence in the white, single-page synthetic PDF fixtures only.

This is not a general PDF blank-page detector: legitimate page whitespace and
non-white page backgrounds require a fixture-specific region or marker.
"""
from PySide6.QtGui import QImage


def interior_ink_pixels(image, margin=20):
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    data = rgba.constBits()
    stride = rgba.bytesPerLine()
    return sum(1 for y in range(margin, rgba.height() - margin)
               for x in range(margin, rgba.width() - margin)
               if data[y * stride + x * 4] < 200
               and data[y * stride + x * 4 + 1] < 200
               and data[y * stride + x * 4 + 2] < 200)
