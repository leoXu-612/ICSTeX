from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.gui.assets import asset_path


class IconProvider:
    """Load the bundled Lucide SVG subset and cache rendered Qt icons."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or asset_path("icons")
        self._cache: dict[tuple[str, str, int], QIcon] = {}

    def icon(self, name: str, color: str = "#5f6561", size: int = 18) -> QIcon:
        key = (name, color.lower(), size)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        if not name.replace("-", "").replace("_", "").isalnum():
            return QIcon()
        path = self.root / f"{name}.svg"
        try:
            source = path.read_text(encoding="utf-8").replace("currentColor", color)
        except OSError:
            return QIcon()

        renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
        if not renderer.isValid():
            return QIcon()
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        rendered = QIcon(pixmap)
        self._cache[key] = rendered
        return rendered

    def clear(self) -> None:
        self._cache.clear()


_PROVIDER = IconProvider()


def icon(name: str, color: str = "#5f6561", size: int = 18) -> QIcon:
    return _PROVIDER.icon(name, color, size)
