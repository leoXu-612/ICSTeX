from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.image_assets import copy_image_atomic, scan_image_assets


class ImageAssetsTests(TestCase):
    def test_scan_image_assets_marks_used_and_unused_images(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            figures = root / "figures"
            figures.mkdir()
            (figures / "used.png").write_text("", encoding="utf-8")
            (figures / "unused.jpg").write_text("", encoding="utf-8")
            (root / "main.tex").write_text("\\includegraphics{figures/used}\n", encoding="utf-8")

            assets = scan_image_assets(root)

            by_name = {asset.path.name: asset for asset in assets}
            self.assertEqual(by_name["used.png"].used_count, 1)
            self.assertEqual(by_name["unused.jpg"].used_count, 0)

    def test_copy_image_atomic_publishes_complete_file(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            destination = root / "figures" / "source.png"
            source.write_bytes(b"complete-image")

            copy_image_atomic(source, destination)

            self.assertEqual(destination.read_bytes(), b"complete-image")
            self.assertEqual(list(destination.parent.glob(".source.png.*.tmp")), [])

    def test_copy_failure_removes_partial_temp_and_destination(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            destination = root / "figures" / "source.png"
            source.write_bytes(b"complete-image")

            def fail_after_partial_copy(_source: Path, temporary: Path) -> None:
                Path(temporary).write_bytes(b"partial")
                raise OSError("copy failed")

            with (
                patch("app.core.image_assets.shutil.copy2", side_effect=fail_after_partial_copy),
                self.assertRaises(OSError),
            ):
                copy_image_atomic(source, destination)

            self.assertFalse(destination.exists())
            self.assertEqual(list(destination.parent.glob(".source.png.*.tmp")), [])
