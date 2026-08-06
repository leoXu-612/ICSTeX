from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from PySide6.QtCore import QSettings

from app.core.latex_tools import LaTeXEngine
from app.core.settings import AppPreferences, AppSettings, MAX_RECENT_ITEMS


class SettingsTests(TestCase):
    def test_preferences_round_trip(self) -> None:
        with TemporaryDirectory() as directory:
            settings = AppSettings(QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat))
            preferences = AppPreferences(
                default_engine=LaTeXEngine.XELATEX,
                auto_compile=False,
                fast_preview=False,
                save_debounce_ms=500,
                compile_debounce_ms=1500,
                editor_font_size=16,
                auto_item=False,
                auto_environment=False,
                auto_pairs=False,
                snippets=False,
                soft_wrap=False,
            )

            settings.save_preferences(preferences)
            loaded = settings.load_preferences()

        self.assertEqual(loaded, preferences)

    def test_recent_items_are_deduped_and_limited(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = AppSettings(QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat))
            paths = [root / f"file-{index}.tex" for index in range(MAX_RECENT_ITEMS + 3)]

            for path in paths:
                settings.add_recent_file(path)
            settings.add_recent_file(paths[-2])

            recent = settings.recent_files()

        self.assertEqual(recent[0], paths[-2].resolve())
        self.assertEqual(len(recent), MAX_RECENT_ITEMS)
        self.assertEqual(len(set(recent)), len(recent))
