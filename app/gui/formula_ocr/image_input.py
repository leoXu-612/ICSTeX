"""Load and preprocess formula images for OCR (temporary copies only)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QImage, QImageReader
from PySide6.QtWidgets import QApplication


MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096


def cache_dir() -> Path:
    base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))
    return base / "formula-ocr"


def image_from_clipboard() -> QImage | None:
    clipboard = QApplication.clipboard()
    if clipboard is None:
        return None
    image = clipboard.image()
    return image if not image.isNull() else None


def image_from_file(path: Path) -> QImage | None:
    if not path.is_file() or path.stat().st_size > MAX_IMAGE_BYTES:
        return None
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    image = reader.read()
    return image if not image.isNull() else None


def preprocess(image: QImage) -> QImage:
    """Grayscale + white background, capped dimensions (non-destructive copy)."""
    processed = image.convertToFormat(QImage.Format.Format_RGB32)
    if processed.width() > MAX_IMAGE_DIMENSION or processed.height() > MAX_IMAGE_DIMENSION:
        processed = processed.scaled(
            MAX_IMAGE_DIMENSION,
            MAX_IMAGE_DIMENSION,
            aspectMode=__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.AspectRatioMode.KeepAspectRatio,
            transformMode=__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.TransformationMode.SmoothTransformation,
        )
    return processed


def save_temp(image: QImage) -> Path:
    directory = cache_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "formula-ocr.png"
    image.save(str(target), "PNG")
    return target
