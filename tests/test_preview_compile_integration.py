from __future__ import annotations

from pathlib import Path
import re
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

from PySide6.QtGui import QColor, QImage, QImageWriter

from app.core.compiler import BuildPurpose, CompileManager, PreviewPreparation
from app.core.latex_tools import detect_toolchain
from app.core.paths import preview_assets_dir_for
from app.gui.image_proxy_cache import ImageProxyCache


TOOLCHAIN = detect_toolchain()


@skipUnless(
    TOOLCHAIN.latexmk is not None and TOOLCHAIN.pdflatex is not None,
    "latexmk and pdflatex are required for image-overlay integration",
)
class PreviewCompileIntegrationTests(TestCase):
    def test_fls_proves_preview_uses_proxy_and_final_uses_original(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            figures = project / "figures"
            figures.mkdir()
            original = figures / "large.png"
            image = QImage(2600, 1300, QImage.Format.Format_ARGB32)
            image.fill(QColor(20, 80, 140, 180))
            writer = QImageWriter(str(original), b"png")
            self.assertTrue(writer.write(image), writer.errorString())
            root = project / "main.tex"
            root.write_text(
                "\\documentclass{article}\n"
                "\\usepackage{graphicx}\n"
                "\\graphicspath{{figures/}}\n"
                "\\begin{document}\n"
                "\\includegraphics[width=.8\\linewidth]{large}\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            cache = ImageProxyCache()

            def prepare(root_file: Path, _output_dir: Path) -> PreviewPreparation:
                result = cache.prepare(root_file, preview_assets_dir_for(root_file))
                return PreviewPreparation(
                    overlay_dir=result.overlay_dir if result.proxy_count else None,
                    fidelity=result.fidelity,
                    manifest_digest=result.manifest_digest,
                    asset_paths=result.referenced_paths,
                )

            manager = CompileManager(
                root,
                toolchain=TOOLCHAIN,
                preview_preparer=prepare,
            )
            preview = manager.compile_now(BuildPurpose.PREVIEW, timeout_seconds=300)
            final = manager.compile_now(BuildPurpose.FINAL, timeout_seconds=300)

            assert preview is not None and final is not None
            self.assertTrue(preview.ok, preview.combined_output)
            self.assertTrue(final.ok, final.combined_output)
            self.assertNotEqual(preview.output_dir, final.output_dir)
            proxy = preview_assets_dir_for(root) / "figures" / "large.png"
            self.assertTrue(proxy.is_file())
            self.assertLess(proxy.stat().st_size, original.stat().st_size)

            preview_inputs = self._image_inputs(preview.output_dir / "main.fls", project)
            final_inputs = self._image_inputs(final.output_dir / "main.fls", project)
            self.assertIn(proxy.resolve(), preview_inputs)
            self.assertNotIn(original.resolve(), preview_inputs)
            self.assertIn(original.resolve(), final_inputs)
            self.assertNotIn(proxy.resolve(), final_inputs)

    def test_proxy_preserves_graphic_natural_width(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            figures = project / "figures"
            figures.mkdir()
            explicit = figures / "explicit.png"
            no_density = figures / "no-density.png"
            jpeg = figures / "explicit.jpg"
            for path, color in (
                (explicit, QColor("navy")),
                (no_density, QColor("green")),
                (jpeg, QColor("maroon")),
            ):
                image = QImage(2400, 1200, QImage.Format.Format_RGB32)
                image.fill(color)
                writer = QImageWriter(str(path), b"jpeg" if path.suffix == ".jpg" else b"png")
                self.assertTrue(writer.write(image), writer.errorString())
            self._remove_png_density(no_density)
            root = project / "main.tex"
            root.write_text(
                "\\documentclass{article}\n"
                "\\usepackage{graphicx}\n"
                "\\newsavebox{\\explicitbox}\n"
                "\\newsavebox{\\nodensitybox}\n"
                "\\newsavebox{\\jpegbox}\n"
                "\\begin{document}\n"
                "\\sbox{\\explicitbox}{\\includegraphics{figures/explicit.png}}\n"
                "\\typeout{ICSTEX-EXPLICIT-WIDTH=\\the\\wd\\explicitbox}\n"
                "\\sbox{\\nodensitybox}{\\includegraphics{figures/no-density.png}}\n"
                "\\typeout{ICSTEX-NODENSITY-WIDTH=\\the\\wd\\nodensitybox}\n"
                "\\sbox{\\jpegbox}{\\includegraphics{figures/explicit.jpg}}\n"
                "\\typeout{ICSTEX-JPEG-WIDTH=\\the\\wd\\jpegbox}\n"
                "x\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            cache = ImageProxyCache()

            def prepare(root_file: Path, _output_dir: Path) -> PreviewPreparation:
                result = cache.prepare(root_file, preview_assets_dir_for(root_file))
                return PreviewPreparation(
                    overlay_dir=result.overlay_dir if result.proxy_count else None,
                    fidelity=result.fidelity,
                    manifest_digest=result.manifest_digest,
                    asset_paths=result.referenced_paths,
                )

            manager = CompileManager(root, toolchain=TOOLCHAIN, preview_preparer=prepare)
            preview = manager.compile_now(BuildPurpose.PREVIEW, timeout_seconds=300)
            final = manager.compile_now(BuildPurpose.FINAL, timeout_seconds=300)

            assert preview is not None and final is not None
            self.assertTrue(preview.ok, preview.combined_output)
            self.assertTrue(final.ok, final.combined_output)
            preview_widths = self._natural_widths(preview.log_file)
            final_widths = self._natural_widths(final.log_file)
            self.assertEqual(set(preview_widths), {"EXPLICIT", "NODENSITY", "JPEG"})
            self.assertEqual(set(final_widths), {"EXPLICIT", "NODENSITY", "JPEG"})
            for name in final_widths:
                self.assertAlmostEqual(preview_widths[name], final_widths[name], delta=1.0)

    @staticmethod
    def _image_inputs(fls_file: Path, project: Path) -> set[Path]:
        inputs: set[Path] = set()
        for line in fls_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith("INPUT ") or not line.lower().endswith("large.png"):
                continue
            path = Path(line.removeprefix("INPUT "))
            inputs.add((path if path.is_absolute() else project / path).resolve())
        return inputs

    @staticmethod
    def _natural_widths(log_file: Path) -> dict[str, float]:
        text = log_file.read_text(encoding="utf-8", errors="replace")
        return {
            name: float(value)
            for name, value in re.findall(
                r"ICSTEX-(EXPLICIT|NODENSITY|JPEG)-WIDTH=([0-9.]+)pt",
                text,
            )
        }

    @staticmethod
    def _remove_png_density(path: Path) -> None:
        payload = path.read_bytes()
        output = bytearray(payload[:8])
        position = 8
        while position + 12 <= len(payload):
            length = int.from_bytes(payload[position : position + 4], "big")
            end = position + 12 + length
            if payload[position + 4 : position + 8] != b"pHYs":
                output.extend(payload[position:end])
            position = end
        path.write_bytes(bytes(output))
