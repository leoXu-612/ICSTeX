from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from PySide6.QtGui import QColor, QImage, QImageReader, QImageWriter

from app.gui.image_proxy_cache import (
    ALLOWED_SUFFIXES,
    ImageProxyCache,
    MAX_PROXY_EDGE,
    TEX_DEFAULT_IMAGE_DPI,
    prepare,
    referenced_paths,
    _has_explicit_physical_density,
    _read_proxy_image,
)


class ImageProxyCacheTests(TestCase):
    def test_builds_only_referenced_proxy_without_mutating_original(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            source = project / "figures" / "large.png"
            unused = project / "figures" / "unused.jpg"
            self._write_image(source, 2000, 1000, QColor(20, 40, 80, 120))
            self._write_image(unused, 40, 20, QColor("red"))
            root = self._write_tex(project, "\\includegraphics{figures/large.png}\n")
            overlay = project / ".icstex" / "preview" / "assets"
            overlay.mkdir(parents=True)
            (overlay / "not-allowed.txt").write_text("remove me", encoding="utf-8")
            (overlay / "stale.pdf").write_bytes(b"not an image proxy")
            original = source.read_bytes()

            result = prepare(root, overlay)

            proxy = overlay / "figures" / "large.png"
            self.assertEqual(source.read_bytes(), original)
            self.assertTrue(proxy.is_file())
            self.assertFalse((overlay / "figures" / "unused.jpg").exists())
            self.assertEqual(result.proxy_count, 1)
            self.assertEqual(result.fallback_count, 0)
            self.assertEqual(result.fidelity, "proxy")
            self.assertEqual(result.referenced_paths, (source.resolve(),))
            self.assertEqual(referenced_paths(root), (source.resolve(),))
            self.assertEqual(result.overlay_dir, overlay.resolve())

            proxy_reader = QImageReader(str(proxy))
            proxy_size = proxy_reader.size()
            self.assertLessEqual(max(proxy_size.width(), proxy_size.height()), MAX_PROXY_EDGE)
            self.assertTrue(proxy_reader.read().hasAlphaChannel())
            self.assertEqual(proxy.suffix, source.suffix)
            self.assertEqual(
                {path.suffix.lower() for path in overlay.rglob("*") if path.is_file()},
                {".png"},
            )
            manifest = overlay.parent / "manifest.json"
            self.assertTrue(manifest.is_file())
            self.assertFalse((overlay / "manifest.json").exists())
            self.assertEqual(result.manifest_digest, hashlib.sha256(manifest.read_bytes()).hexdigest())

    def test_cache_hit_skips_qt_reencoding_and_policy_change_invalidates(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            source = project / "figures" / "plot.jpg"
            self._write_image(source, 80, 60, QColor("navy"))
            root = self._write_tex(project, "\\includegraphics{figures/plot.jpg}\n")
            overlay = project / ".icstex" / "preview" / "assets"
            cache = ImageProxyCache()
            first = cache.prepare(root, overlay)
            proxy_bytes = (overlay / "figures" / "plot.jpg").read_bytes()

            with patch(
                "app.gui.image_proxy_cache._write_proxy_atomic",
                side_effect=AssertionError("cache miss"),
            ):
                second = cache.prepare(root, overlay)

            self.assertEqual(second.manifest_digest, first.manifest_digest)
            self.assertEqual((overlay / "figures" / "plot.jpg").read_bytes(), proxy_bytes)

            with patch("app.gui.image_proxy_cache._write_proxy_atomic", wraps=self._writer()) as writer:
                changed_policy = ImageProxyCache(policy_version="test-policy-v2").prepare(root, overlay)
            self.assertEqual(writer.call_count, 1)
            self.assertNotEqual(changed_policy.manifest_digest, first.manifest_digest)

    def test_source_content_change_invalidates_proxy_and_manifest(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            source = project / "figures" / "plot.png"
            self._write_image(source, 100, 60, QColor("red"))
            root = self._write_tex(project, "\\includegraphics{figures/plot.png}\n")
            overlay = project / ".icstex" / "preview" / "assets"
            first = prepare(root, overlay)
            first_proxy = (overlay / "figures" / "plot.png").read_bytes()

            self._write_image(source, 100, 60, QColor("blue"))
            changed_source = source.read_bytes()
            second = prepare(root, overlay)

            self.assertNotEqual(second.manifest_digest, first.manifest_digest)
            self.assertNotEqual((overlay / "figures" / "plot.png").read_bytes(), first_proxy)
            self.assertEqual(source.read_bytes(), changed_source)
            manifest = json.loads((overlay.parent / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["references"]["figures/plot.png"]["source_sha256"],
                hashlib.sha256(changed_source).hexdigest(),
            )

            source.write_bytes(b"corrupt-after-a-valid-proxy")
            failed = prepare(root, overlay)
            self.assertEqual(failed.proxy_count, 0)
            self.assertEqual(failed.fallback_count, 1)
            self.assertFalse((overlay / "figures" / "plot.png").exists())

    def test_deleted_or_unreferenced_source_removes_stale_proxy(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            source = project / "figures" / "plot.png"
            self._write_image(source, 80, 40, QColor("green"))
            root = self._write_tex(project, "\\includegraphics{figures/plot.png}\n")
            overlay = project / ".icstex" / "preview" / "assets"
            first = prepare(root, overlay)
            proxy = overlay / "figures" / "plot.png"
            self.assertEqual(first.proxy_count, 1)
            self.assertTrue(proxy.exists())

            source.unlink()
            missing = prepare(root, overlay)

            self.assertFalse(proxy.exists())
            self.assertEqual(missing.proxy_count, 0)
            self.assertEqual(missing.fallback_count, 1)
            self.assertEqual(missing.referenced_paths, (source.resolve(),))
            manifest = json.loads((overlay.parent / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["entries"], {})

            self._write_image(source, 80, 40, QColor("green"))
            prepare(root, overlay)
            root.write_text("\\documentclass{article}\n", encoding="utf-8")
            unreferenced = prepare(root, overlay)
            self.assertFalse(proxy.exists())
            self.assertEqual(unreferenced.proxy_count, 0)
            self.assertEqual(unreferenced.fallback_count, 0)

    def test_external_dynamic_nonwhitelist_and_corrupt_images_fall_back(self) -> None:
        with TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "project"
            corrupt = project / "figures" / "broken.png"
            corrupt.parent.mkdir(parents=True)
            corrupt.write_bytes(b"not-a-png")
            pdf = project / "figures" / "chart.pdf"
            pdf.write_bytes(b"%PDF-not-relevant")
            external = workspace / "outside.jpg"
            self._write_image(external, 20, 20, QColor("orange"))
            root = self._write_tex(
                project,
                "\n".join(
                    (
                        "\\includegraphics{figures/broken.png}",
                        f"\\includegraphics{{{external}}}",
                        "\\includegraphics{figures/chart.pdf}",
                        "\\includegraphics{\\dynamic/image.png}",
                        "\\includegraphics{./figures/broken.png}",
                    )
                ),
            )
            overlay = project / ".icstex" / "preview" / "assets"

            first = prepare(root, overlay)
            corrupt.write_bytes(b"still-not-a-png-but-different")
            second = prepare(root, overlay)

            self.assertEqual(second.proxy_count, 0)
            self.assertEqual(second.fallback_count, 5)
            self.assertEqual(second.fidelity, "original_fallback")
            self.assertEqual(second.referenced_paths, (corrupt.resolve(), pdf.resolve()))
            self.assertNotEqual(second.manifest_digest, first.manifest_digest)
            self.assertEqual([path for path in overlay.rglob("*") if path.is_file()], [])

    def test_dependency_reference_prefers_project_root_and_mirrors_extension(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            root_image = project / "figures" / "choice.jpeg"
            child_image = project / "chapters" / "figures" / "choice.jpeg"
            self._write_image(root_image, 50, 30, QColor("purple"))
            self._write_image(child_image, 50, 30, QColor("yellow"))
            child = project / "chapters" / "part.tex"
            child.parent.mkdir(parents=True, exist_ok=True)
            child.write_text("\\includegraphics{figures/choice}\n", encoding="utf-8")
            root = self._write_tex(project, "\\input{chapters/part}\n")
            overlay = project / ".icstex" / "preview" / "assets"

            result = prepare(root, overlay)

            self.assertEqual(result.referenced_paths, (root_image.resolve(),))
            self.assertTrue((overlay / "figures" / "choice.jpeg").is_file())
            self.assertFalse((overlay / "chapters" / "figures" / "choice.jpeg").exists())

    def test_graphicspath_reference_is_proxied_and_watched(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            source = project / "figures" / "plot.png"
            self._write_image(source, 2000, 1000, QColor("teal"))
            root = self._write_tex(
                project,
                "\\graphicspath{{figures/}}\n\\includegraphics{plot}\n",
            )
            overlay = project / ".icstex" / "preview" / "assets"

            result = prepare(root, overlay)

            self.assertEqual(result.proxy_count, 1)
            self.assertEqual(result.fallback_count, 0)
            self.assertEqual(result.referenced_paths, (source.resolve(),))
            self.assertTrue((overlay / "figures" / "plot.png").is_file())

    def test_static_fallback_and_missing_paths_remain_watchable(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            dot_image = project / "figures" / "dot.png"
            absolute_image = project / "figures" / "absolute.jpg"
            pdf = project / "figures" / "chart.pdf"
            self._write_image(dot_image, 40, 20, QColor("blue"))
            self._write_image(absolute_image, 40, 20, QColor("red"))
            pdf.write_bytes(b"%PDF-placeholder")
            missing = project / "figures" / "missing.png"
            root = self._write_tex(
                project,
                "\n".join(
                    (
                        "\\includegraphics{./figures/dot.png}",
                        f"\\includegraphics{{{absolute_image}}}",
                        "\\includegraphics{figures/chart.pdf}",
                        "\\includegraphics{figures/missing.png}",
                    )
                ),
            )
            overlay = project / ".icstex" / "preview" / "assets"

            result = prepare(root, overlay)

            self.assertEqual(result.proxy_count, 0)
            self.assertEqual(result.fallback_count, 4)
            self.assertEqual(
                set(result.referenced_paths),
                {dot_image.resolve(), absolute_image.resolve(), pdf.resolve(), missing.resolve()},
            )

    def test_proxy_density_preserves_natural_size(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            explicit = root / "explicit.png"
            no_density = root / "no-density.png"
            self._write_image(explicit, 3600, 1800, QColor("navy"))
            image = QImage(3600, 1800, QImage.Format.Format_RGB32)
            image.fill(QColor("green"))
            writer = QImageWriter(str(no_density), b"png")
            self.assertTrue(writer.write(image), writer.errorString())
            self._remove_png_density(no_density)

            explicit_image = QImageReader(str(explicit)).read()
            explicit_proxy = _read_proxy_image(explicit)
            no_density_proxy = _read_proxy_image(no_density)

            self.assertTrue(_has_explicit_physical_density(explicit))
            self.assertFalse(_has_explicit_physical_density(no_density))
            self.assertAlmostEqual(
                explicit_proxy.width() / explicit_proxy.dotsPerMeterX(),
                explicit_image.width() / explicit_image.dotsPerMeterX(),
                places=3,
            )
            self.assertAlmostEqual(
                no_density_proxy.width() / no_density_proxy.dotsPerMeterX(),
                3600 / round(TEX_DEFAULT_IMAGE_DPI / 0.0254),
                places=3,
            )

    def test_containment_and_overlay_whitelist_reject_escaping_paths(self) -> None:
        with TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "project"
            outside = workspace / "outside.png"
            self._write_image(outside, 20, 20, QColor("black"))
            outside_bytes = outside.read_bytes()
            linked = project / "figures" / "linked.png"
            linked.parent.mkdir(parents=True)
            linked.symlink_to(outside)
            root = self._write_tex(
                project,
                "\\includegraphics{../outside.png}\n\\includegraphics{figures/linked.png}\n",
            )
            overlay = project / ".icstex" / "preview" / "assets"
            overlay.mkdir(parents=True)
            (overlay / "note.json").write_text("{}", encoding="utf-8")
            (overlay / "old.pdf").write_bytes(b"old")

            result = prepare(root, overlay)

            self.assertEqual(result.proxy_count, 0)
            self.assertEqual(result.fallback_count, 2)
            self.assertEqual(result.referenced_paths, ())
            self.assertEqual([path for path in overlay.rglob("*") if path.is_file()], [])
            self.assertEqual(outside.read_bytes(), outside_bytes)

            # A caller mistake must not turn the project root into a cache that
            # is cleaned as an overlay.
            rejected = prepare(root, project)
            self.assertEqual(rejected.proxy_count, 0)
            self.assertTrue(root.is_file())
            self.assertTrue(outside.is_file())

            foreign_overlay = workspace / "foreign-cache" / "assets"
            rejected_foreign = prepare(root, foreign_overlay)
            self.assertEqual(rejected_foreign.proxy_count, 0)
            self.assertFalse(foreign_overlay.exists())

    @staticmethod
    def _write_tex(project: Path, body: str) -> Path:
        project.mkdir(parents=True, exist_ok=True)
        root = project / "main.tex"
        root.write_text(f"\\documentclass{{article}}\n{body}", encoding="utf-8")
        return root

    @staticmethod
    def _write_image(path: Path, width: int, height: int, color: QColor) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        image_format = QImage.Format.Format_ARGB32 if path.suffix.lower() == ".png" else QImage.Format.Format_RGB32
        image = QImage(width, height, image_format)
        image.fill(color)
        writer_format = b"png" if path.suffix.lower() == ".png" else b"jpeg"
        writer = QImageWriter(str(path), writer_format)
        if not writer.write(image):
            raise AssertionError(writer.errorString())

    @staticmethod
    def _remove_png_density(path: Path) -> None:
        payload = path.read_bytes()
        output = bytearray(payload[:8])
        position = 8
        while position + 12 <= len(payload):
            length = int.from_bytes(payload[position : position + 4], "big")
            end = position + 12 + length
            chunk = payload[position + 4 : position + 8]
            if chunk != b"pHYs":
                output.extend(payload[position:end])
            position = end
        path.write_bytes(bytes(output))

    @staticmethod
    def _writer():
        from app.gui.image_proxy_cache import _write_proxy_atomic

        return _write_proxy_atomic


class ImageProxyConstantsTests(TestCase):
    def test_proxy_formats_are_strictly_limited(self) -> None:
        self.assertEqual(ALLOWED_SUFFIXES, (".png", ".jpg", ".jpeg"))

    def test_proxy_decode_preserves_raw_orientation_for_latex_fidelity(self) -> None:
        image = QImage(40, 20, QImage.Format.Format_RGB32)
        with patch("app.gui.image_proxy_cache.QImageReader") as reader_type:
            reader = reader_type.return_value
            reader.size.return_value = image.size()
            reader.read.return_value = image

            decoded = _read_proxy_image(Path("oriented.jpg"))

        reader.setAutoTransform.assert_called_once_with(False)
        self.assertEqual(decoded.size(), image.size())
