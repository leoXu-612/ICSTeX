from __future__ import annotations

from pathlib import Path
import os
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.asset_index import AssetIndex, AssetRecord
from app.core.image_assets import _graphics_references


def _write_png(path: Path, data: bytes = b"png-bytes") -> None:
    path.write_bytes(data)


class AssetIndexTests(TestCase):
    def test_unchanged_scan_reuses_metadata(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            figures = project / "figures"
            figures.mkdir()
            _write_png(figures / "a.png")
            _write_png(figures / "b.png")

            metadata_calls: list[str] = []

            def read_metadata(path: Path) -> tuple[int | None, int | None]:
                metadata_calls.append(path.name)
                return (10, 20)

            index = AssetIndex(project)
            first = index.scan(read_metadata=read_metadata)
            self.assertEqual(len(first["added"]), 2)
            self.assertEqual(len(metadata_calls), 2)

            second = index.scan(read_metadata=read_metadata)
            self.assertEqual(second, {"added": [], "removed": [], "modified": []})
            self.assertEqual(len(metadata_calls), 2)  # no re-extraction

    def test_add_modify_remove_diff(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            _write_png(project / "a.png")
            index = AssetIndex(project)
            index.scan()

            _write_png(project / "b.png")
            diff = index.scan()
            self.assertEqual(diff["added"], ["b.png"])

            (project / "a.png").write_bytes(b"changed-content")
            diff = index.scan()
            self.assertEqual(diff["modified"], ["a.png"])

            (project / "b.png").unlink()
            diff = index.scan()
            self.assertEqual(diff["removed"], ["b.png"])

    def test_save_and_load_round_trip(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            _write_png(project / "a.png")
            index = AssetIndex(project)
            index.scan(read_metadata=lambda _path: (640, 480))
            index.save()

            index_path = project / ".icstex" / "asset-index.json"
            self.assertTrue(index_path.exists())
            self.assertFalse(index_path.with_name(index_path.name + ".tmp").exists())

            loaded = AssetIndex(project)
            loaded.load()
            self.assertTrue(loaded.was_cached)
            record = loaded._records["a.png"]
            self.assertEqual(record.width, 640)
            self.assertEqual(record.height, 480)

    def test_add_many_remove_and_persist(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            index = AssetIndex(project)
            index.add_many(
                [
                    AssetRecord(
                        asset_id="figures/x.png",
                        filename="x.png",
                        media_type=".png",
                        size=100,
                        modified_time_ns=1,
                    )
                ]
            )
            index.remove(["figures/x.png"])
            index.save()
            self.assertFalse((project / ".icstex" / "asset-index.json").exists())

    def test_image_assets_used_count_from_tex(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "main.tex").write_text(
                "\\documentclass{article}\n\\includegraphics{figures/a}\n",
                encoding="utf-8",
            )
            figures = project / "figures"
            figures.mkdir()
            _write_png(figures / "a.png")
            _write_png(figures / "b.png")

            index = AssetIndex(project)
            index.scan()
            assets = index.image_assets()

            by_name = {asset.relative_path: asset.used_count for asset in assets}
            self.assertEqual(by_name["figures/a.png"], 1)
            self.assertEqual(by_name["figures/b.png"], 0)

    def test_ignores_build_dirs_and_non_images(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            (project / ".latex_build").mkdir()
            (project / ".icstex").mkdir()
            _write_png(project / ".latex_build" / "aux.png")
            _write_png(project / ".icstex" / "preview.png")
            (project / "notes.txt").write_text("x", encoding="utf-8")
            _write_png(project / "real.png")

            index = AssetIndex(project)
            index.scan()

            self.assertEqual(set(index._records), {"real.png"})

    def test_reload_avoids_metadata_reextraction(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            _write_png(project / "a.png")
            first = AssetIndex(project)
            first.scan(read_metadata=lambda _path: (1, 2))
            first.save()

            calls: list[str] = []

            def read_metadata(path: Path) -> tuple[int | None, int | None]:
                calls.append(path.name)
                return (3, 4)

            second = AssetIndex(project)
            second.load()
            second.scan(read_metadata=read_metadata)

            self.assertEqual(calls, [])
            self.assertEqual(second._records["a.png"].width, 1)

    def test_scan_prunes_before_descent_and_skips_symlinks(self) -> None:
        with TemporaryDirectory() as directory, TemporaryDirectory() as outside:
            root = Path(directory).resolve()
            ignored = root / ".latex_build" / "deep"
            ignored.mkdir(parents=True)
            (ignored / "generated.png").write_bytes(b"image")
            (ignored / "generated.tex").write_text(r"\includegraphics{wrong}")
            external = Path(outside)
            (external / "outside.png").write_bytes(b"image")
            (external / "outside.tex").write_text(r"\includegraphics{outside}")
            (root / "linked").symlink_to(external, target_is_directory=True)
            (root / "link.png").symlink_to(external / "outside.png")
            (root / "link.tex").symlink_to(external / "outside.tex")
            (root / "real.png").write_bytes(b"image")
            (root / "main.tex").write_text(r"\includegraphics{real}")
            visited: list[Path] = []
            scandir = os.scandir

            def observe(path):
                visited.append(Path(path))
                return scandir(path)

            with patch("app.core.project_scan.os.scandir", side_effect=observe):
                index = AssetIndex(root)
                index.scan()
                references = _graphics_references(root, current_text="")
            self.assertEqual(set(index._records), {"real.png"})
            self.assertEqual(references, ["real"])
            self.assertTrue(visited)
            self.assertTrue(all(path == root for path in visited))
