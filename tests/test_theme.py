from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.blocks.schema import validate_theme
from app.core.blocks.theme import AppTheme, DocumentTheme, theme_from_dict
from app.core.blocks.theme_renderer import render_document_theme_sty
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain


TOOLCHAIN = detect_toolchain()


def app_theme_dict(mode: str = "light", **overrides: object) -> dict:
    data = {
        "schemaVersion": "1.0.0",
        "kind": "app-theme",
        "id": "theme_warm_light",
        "name": "Warm Light",
        "mode": mode,
        "tokens": {
            "background": "#F5F3EE",
            "surface": "#FAF9F6",
            "surfaceElevated": "#FFFFFF",
            "foreground": "#1D1B16",
            "foregroundMuted": "#77736C",
            "border": "#DDD9D2",
            "accent": "#DA7756",
            "accentForeground": "#FFFFFF",
            "selection": "#F3D8CE",
            "success": "#2F7D4A",
            "warning": "#A36A00",
            "error": "#C64536",
            "layoutGuide": "#3984C6",
        },
        "typography": {"uiFont": "system-ui", "codeFont": "SF Mono", "uiSizePx": 14, "codeSizePx": 12},
        "effects": {"translucentSidebar": False, "reducedMotion": "system", "contrast": 60},
    }
    data.update(overrides)
    return data


def document_theme_dict(**overrides: object) -> dict:
    data = {
        "schemaVersion": "1.0.0",
        "kind": "document-theme",
        "id": "doc_academic_clean",
        "name": "Academic Clean",
        "page": {
            "size": "a4",
            "orientation": "portrait",
            "columns": 1,
            "margin": {"topMm": 25, "rightMm": 25, "bottomMm": 25, "leftMm": 30},
        },
        "typography": {
            "textFamily": "",
            "mathFamily": "",
            "monoFamily": "",
            "baseSizePt": 11,
            "lineSpacing": 1.15,
        },
        "headings": {"section": {"weight": 600, "spaceBeforePt": 16, "spaceAfterPt": 7}},
        "figures": {"captionPosition": "bottom", "captionSize": "small", "alignment": "center"},
        "tables": {"preset": "booktabs", "verticalRules": False, "headerWeight": 600, "cellPaddingPt": 4},
        "layout": {"blockGapPt": 10, "gridGapPt": 12},
    }
    data.update(overrides)
    return data


class ThemeModelTests(TestCase):
    def test_app_theme_valid_with_all_tokens(self) -> None:
        self.assertEqual(validate_theme(app_theme_dict()), [])

    def test_missing_token_and_invalid_mode_rejected(self) -> None:
        missing = app_theme_dict()
        del missing["tokens"]["accent"]
        self.assertTrue(validate_theme(missing))
        self.assertIn("accent", AppTheme(**{**missing, "tokens": missing["tokens"]}).missing_tokens())
        self.assertTrue(validate_theme(app_theme_dict(mode="neon")))

    def test_document_theme_valid_and_required_fields(self) -> None:
        self.assertEqual(validate_theme(document_theme_dict()), [])
        broken = document_theme_dict()
        del broken["typography"]
        self.assertTrue(validate_theme(broken))

    def test_theme_from_dict(self) -> None:
        app_theme = theme_from_dict(app_theme_dict())
        doc_theme = theme_from_dict(document_theme_dict())
        self.assertIsInstance(app_theme, AppTheme)
        self.assertIsInstance(doc_theme, DocumentTheme)


class ThemeRendererTests(TestCase):
    def test_sty_is_deterministic(self) -> None:
        first = render_document_theme_sty(theme_from_dict(document_theme_dict()))
        second = render_document_theme_sty(theme_from_dict(document_theme_dict()))
        self.assertEqual(first, second)

    def test_sty_changes_with_theme(self) -> None:
        base = render_document_theme_sty(theme_from_dict(document_theme_dict()))
        changed = render_document_theme_sty(
            theme_from_dict(document_theme_dict(page={"size": "letter", "orientation": "portrait", "columns": 1, "margin": {"leftMm": 20}}))
        )
        self.assertNotEqual(base, changed)
        self.assertIn("letter", changed)
        self.assertNotIn("letter", base)

    def test_headings_emit_titlespacing(self) -> None:
        theme = theme_from_dict(
            document_theme_dict(headings={"section": {"spaceBeforePt": 16, "spaceAfterPt": 7}})
        )
        latex = render_document_theme_sty(theme)
        self.assertIn("\\usepackage{titlesec}", latex)
        self.assertIn("\\titlespacing*{\\section}{0pt}{16pt}{7pt}", latex)

        plain = render_document_theme_sty(theme_from_dict(document_theme_dict(headings={})))
        self.assertNotIn("titlesec", plain)

    def test_app_theme_never_reaches_latex(self) -> None:
        latex = render_document_theme_sty(theme_from_dict(document_theme_dict()))
        self.assertNotIn("app-theme", latex)
        self.assertNotIn("background", latex)


@skipUnless(TOOLCHAIN.is_compile_ready, "latexmk or xelatex is not available")
class DocumentThemeCompileTests(TestCase):
    def test_generated_sty_compiles(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            main = project / "main.tex"
            sty = render_document_theme_sty(theme_from_dict(document_theme_dict()))
            main.write_text(
                "\\documentclass{ctexart}\n"
                f"{sty}"
                "\\usepackage{graphicx}\n"
                "\\begin{document}\n"
                "测试主题编译。\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            result = CompileManager(main, toolchain=TOOLCHAIN, engine=LaTeXEngine.XELATEX).compile_now(
                BuildPurpose.FINAL
            )
            self.assertTrue(result.ok, result.combined_output)
