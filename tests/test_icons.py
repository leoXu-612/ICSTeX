from __future__ import annotations

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.gui.assets import asset_path
from app.gui.icons import IconProvider


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class IconProviderTests(TestCase):
    def setUp(self) -> None:
        _app()

    def test_bundled_icon_renders_and_is_cached(self) -> None:
        provider = IconProvider(asset_path("icons"))
        first = provider.icon("play", "#a93632", 18)
        second = provider.icon("play", "#a93632", 18)

        self.assertFalse(first.isNull())
        self.assertEqual(first.cacheKey(), second.cacheKey())

    def test_unknown_and_unsafe_icon_names_return_null_icon(self) -> None:
        provider = IconProvider(asset_path("icons"))

        self.assertTrue(provider.icon("not-present").isNull())
        self.assertTrue(provider.icon("../play").isNull())

    def test_every_bundled_svg_is_renderable(self) -> None:
        root = asset_path("icons")
        provider = IconProvider(root)

        icons = sorted(root.glob("*.svg"))
        self.assertGreaterEqual(len(icons), 25)
        for path in icons:
            with self.subTest(icon=path.name):
                self.assertFalse(provider.icon(path.stem).isNull())

    def test_asset_path_uses_pyinstaller_bundle_root(self) -> None:
        with TemporaryDirectory() as directory:
            with patch.object(sys, "_MEIPASS", directory, create=True):
                self.assertEqual(
                    asset_path("icons/play.svg"),
                    Path(directory) / "app" / "assets" / "icons" / "play.svg",
                )
