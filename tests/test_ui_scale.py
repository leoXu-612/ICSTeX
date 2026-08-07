"""UI Scale tests: tiers from base font, metrics, isolation, persistence."""
from __future__ import annotations

import os
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QToolBar

from app.core.settings import AppSettings
from app.gui.theme import apply_theme, stylesheet
from app.gui.theme.ui_metrics import TypographyMetrics, UiMetrics
from app.gui.theme.ui_scale_manager import SCALE_TIERS, UiScaleManager


_TEMP = TemporaryDirectory()
_COUNTER = count()


def _app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
        apply_theme(instance)
    return instance


def _settings() -> AppSettings:
    settings_file = Path(_TEMP.name) / f"scale-{next(_COUNTER)}.ini"
    return AppSettings(QSettings(str(settings_file), QSettings.Format.IniFormat))


class ScaleManagerTests(TestCase):
    def setUp(self) -> None:
        self.app = _app()
        if not hasattr(self.app, "ui_scale_manager"):
            self.app.ui_scale_manager = UiScaleManager(self.app)
        self.manager = self.app.ui_scale_manager
        self.manager.apply_scale(1.0)

    def tearDown(self) -> None:
        # Never leave the shared manager at a non-default scale: subsequent
        # windows would trigger expensive app-wide stylesheet rebuilds.
        self.manager.apply_scale(1.0)

    def test_tiers_are_fixed(self) -> None:
        self.assertEqual(SCALE_TIERS, (0.90, 1.00, 1.10, 1.25, 1.50))

    def test_font_scales_from_base_without_drift(self) -> None:
        base_pt = self.manager._base_point_size
        self.manager.apply_scale(1.25)
        self.assertAlmostEqual(self.app.font().pointSizeF(), base_pt * 1.25, places=2)
        self.manager.apply_scale(1.0)
        self.assertAlmostEqual(self.app.font().pointSizeF(), base_pt, places=2)
        # repeated cycles never accumulate
        for _ in range(2):
            self.manager.apply_scale(1.5)
            self.manager.apply_scale(1.0)
        self.assertAlmostEqual(self.app.font().pointSizeF(), base_pt, places=2)

    def test_metrics_are_proportional(self) -> None:
        for scale in SCALE_TIERS:
            metrics = UiMetrics(scale)
            self.assertEqual(metrics.control_height, round(34 * scale))
            self.assertEqual(metrics.icon_size, round(18 * scale))
            self.assertEqual(metrics.dock_min_width, round(230 * scale))
            self.assertEqual(TypographyMetrics(scale).body_pt, 13.0 * scale)

    def test_toolbar_icon_size_follows_scale(self) -> None:
        from app.gui.main_window import MainWindow

        window = MainWindow(settings_store=_settings())
        toolbar = window.findChild(QToolBar, "mainToolbar")
        self.assertIsNotNone(toolbar)
        self.manager.apply_scale(1.25)
        self.assertEqual(toolbar.iconSize().width(), round(20 * 1.25))
        window.close()

    def test_pdf_zoom_does_not_change_ui_scale_or_font(self) -> None:
        from app.gui.pdf_panel import PdfPanel

        panel = PdfPanel()
        base_pt = self.app.font().pointSizeF()
        scale_before = self.manager.scale
        if panel._view is not None:
            panel.zoom_by(1.5)
            panel.zoom_by(1 / 1.5)
        self.assertEqual(self.manager.scale, scale_before)
        self.assertEqual(self.app.font().pointSizeF(), base_pt)
        panel.close()

    def test_ui_scale_does_not_touch_project_data_or_stable_latex(self) -> None:
        from app.core.blocks.model import content_for_text
        from app.core.blocks.registry import BlockRegistry, CreateBlockInput
        from app.gui.blocks.project_session import ProjectSession

        with TemporaryDirectory() as directory:
            project = Path(directory) / "proj"
            registry = BlockRegistry()
            registry.create(CreateBlockInput(type="text", alias="t", content=content_for_text("x")))
            session = ProjectSession(registry=registry, project_dir=project)
            session.save_now()
            before = (project / ".icstex" / "blocks.json").read_bytes()
            latex_before = session.assemble_latex().read_bytes()

            self.manager.apply_scale(1.25)
            self.manager.apply_scale(1.0)

            self.assertEqual((project / ".icstex" / "blocks.json").read_bytes(), before)
            self.assertEqual(session.assemble_latex().read_bytes(), latex_before)

    def test_scale_persists_across_settings_reload(self) -> None:
        from app.gui.main_window import MainWindow

        settings = _settings()
        window = MainWindow(settings_store=settings)
        window.set_ui_scale(1.25)
        window.close()
        reloaded = settings.load_preferences()
        self.assertAlmostEqual(reloaded.ui_scale, 1.25, places=3)

    def test_stylesheet_renders_at_all_tiers(self) -> None:
        for scale in SCALE_TIERS:
            qss = stylesheet(UiMetrics(scale), TypographyMetrics(scale))
            self.assertIn(f"font-size: {round(13 * scale)}px", qss)


class ButtonMinimumSizeTests(TestCase):
    def test_key_welcome_buttons_never_clip(self) -> None:
        _app()
        from PySide6.QtGui import QFontMetrics

        from app.gui.theme.ui_metrics import UiMetrics
        from app.gui.welcome_page import WelcomePage

        page = WelcomePage()
        for button in page._action_buttons:
            text_width = QFontMetrics(button.font()).horizontalAdvance(button.text())
            self.assertGreaterEqual(button.minimumWidth(), text_width + 16, button.text())
        page.deleteLater()
