from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.blocks.demo import build_demo
from app.core.blocks.export_package import export_package
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain


TOOLCHAIN = detect_toolchain()


@skipUnless(TOOLCHAIN.is_compile_ready, "latexmk or xelatex is not available")
class DemoBuildTests(TestCase):
    def test_demo_builds_pdf_and_expected_files(self) -> None:
        with TemporaryDirectory() as directory:
            demo = build_demo(Path(directory) / "demo")

            self.assertTrue(demo.pdf.is_file())
            self.assertGreater(demo.pdf.stat().st_size, 0)
            self.assertTrue(demo.main_tex.is_file())
            self.assertTrue((demo.project_dir / "icstex.project.json").exists())
            self.assertTrue((demo.project_dir / ".icstex" / "blocks.json").exists())
            self.assertTrue((demo.project_dir / ".icstex" / "layouts.json").exists())
            self.assertTrue((demo.project_dir / ".icstex" / "sources.json").exists())
            self.assertTrue((demo.project_dir / "styles" / "icstex-generated.sty").exists())
            self.assertEqual(len(list((demo.project_dir / "blocks").glob("*.tex"))), 4)
            self.assertEqual(len(demo.registry.blocks()), 4)

    def test_demo_export_compiles_in_empty_directory(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            demo = build_demo(root / "demo")
            exported = root / "exported"
            export_package(demo.project_dir, exported)

            self.assertTrue((exported / "main.tex").exists())
            self.assertTrue((exported / "manifest.json").exists())
            self.assertFalse((exported / ".icstex").exists())
            result = CompileManager(
                exported / "main.tex",
                toolchain=TOOLCHAIN,
                engine=LaTeXEngine.XELATEX,
            ).compile_now(BuildPurpose.FINAL)
            self.assertTrue(result.ok, result.combined_output)
            self.assertTrue(result.pdf_file.exists())
