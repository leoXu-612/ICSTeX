from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.core.image_assets import ImageAsset
from app.gui.project_panels import ImagesPanel, _ImageThumbnailCache


def _app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class ImagesPanelThumbnailTests(TestCase):
    def setUp(self) -> None:
        _app()

    def test_reader_scales_during_decode_and_applies_image_transform(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "large.jpg"
            path.write_bytes(b"placeholder")
            decoded = QImage(44, 22, QImage.Format.Format_RGB32)

            with patch("app.gui.project_panels.QImageReader") as reader_type:
                reader = reader_type.return_value
                reader.size.return_value = QSize(4000, 2000)
                reader.read.return_value = decoded
                panel = ImagesPanel()
                panel.set_assets([ImageAsset(path=path, relative_path="large.jpg", used_count=1)])

            reader_type.assert_called_once_with(str(path.resolve()))
            reader.setAutoTransform.assert_called_once_with(True)
            reader.setScaledSize.assert_called_once_with(QSize(44, 22))
            self.assertFalse(panel.table.item(0, 0).icon().isNull())

    def test_unchanged_file_uses_cache_and_changed_file_is_decoded_again(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "figure.png"
            path.write_bytes(b"one")
            asset = ImageAsset(path=path, relative_path="figure.png", used_count=0)
            decoded = QImage(20, 20, QImage.Format.Format_RGB32)

            with patch("app.gui.project_panels.QImageReader") as reader_type:
                reader = reader_type.return_value
                reader.size.return_value = QSize(20, 20)
                reader.read.return_value = decoded
                panel = ImagesPanel()
                panel.set_assets([asset])
                panel.set_assets([asset])
                self.assertEqual(reader_type.call_count, 1)

                path.write_bytes(b"a different size")
                panel.set_assets([asset])

            self.assertEqual(reader_type.call_count, 2)

    def test_cache_is_bounded(self) -> None:
        with TemporaryDirectory() as directory:
            paths = [Path(directory) / f"image-{index}.png" for index in range(3)]
            for path in paths:
                path.write_bytes(path.name.encode("ascii"))
            decoded = QImage(10, 10, QImage.Format.Format_RGB32)
            cache = _ImageThumbnailCache(max_entries=2, target_size=QSize(44, 44))

            with patch("app.gui.project_panels.QImageReader") as reader_type:
                reader = reader_type.return_value
                reader.size.return_value = QSize(10, 10)
                reader.read.return_value = decoded
                for path in paths:
                    cache.icon_for(path)

            self.assertEqual(len(cache._entries), 2)
            self.assertNotIn(str(paths[0].resolve()), {key[0] for key in cache._entries})

    def test_corrupt_image_is_listed_without_an_icon_or_exception(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "broken.png"
            path.write_bytes(b"not an image")
            panel = ImagesPanel()

            panel.set_assets([ImageAsset(path=path, relative_path="broken.png", used_count=0)])

            self.assertEqual(panel.table.item(0, 0).text(), "broken.png")
            self.assertTrue(panel.table.item(0, 0).icon().isNull())
            self.assertEqual(panel.table.item(0, 1).text(), "broken.png")
