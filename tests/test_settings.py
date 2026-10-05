from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from PySide6.QtCore import QSettings

from app.core.latex_tools import LaTeXEngine
from app.core.settings import AppPreferences, AppSettings, MAX_RECENT_ITEMS


class SettingsTests(TestCase):
    def test_export_destination_survives_reload_and_is_root_specific(self):
        from app.core.artifact_export import exported_pdf
        with TemporaryDirectory() as directory:
            scope = Path(directory).resolve()
            root = scope / "main.tex"
            target = scope / "export.pdf"
            target.write_bytes(b"PDF bytes")
            receipt = exported_pdf(target, b"PDF bytes")
            settings_file = str(scope / "settings.ini")
            first = AppSettings(QSettings(settings_file, QSettings.Format.IniFormat))
            first.remember_pdf_export(root, scope, receipt)
            second = AppSettings(QSettings(settings_file, QSettings.Format.IniFormat))
            self.assertEqual(second.pdf_export_target(root), (scope, receipt))
            self.assertIsNone(second.pdf_export_target(scope / "other.tex"))
            second.forget_pdf_export(root)
            self.assertIsNone(second.pdf_export_target(root))

    def test_malformed_export_destination_is_not_adopted(self):
        with TemporaryDirectory() as directory:
            scope = Path(directory).resolve()
            settings = AppSettings(QSettings(str(scope / "settings.ini"), QSettings.Format.IniFormat))
            root = scope / "main.tex"
            for bad in ('bad json', '{}', '[]', '1', '{"scope": null}'):
                settings.settings.setValue(settings._pdf_export_key(root), bad)
                self.assertIsNone(settings.pdf_export_target(root))

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

    def test_remembering_same_recent_item_does_not_rewrite_unchanged_settings(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            settings = AppSettings(QSettings(str(root / "recent.ini"), QSettings.Format.IniFormat))
            first, second = root / "first.tex", root / "second.tex"
            settings.add_recent_file(first)
            settings.add_recent_project(root)
            with patch.object(settings.settings, "setValue", wraps=settings.settings.setValue) as write, \
                 patch.object(settings.settings, "sync", wraps=settings.settings.sync) as sync:
                settings.add_recent_file(first)
                settings.add_recent_project(root)
            write.assert_not_called()
            sync.assert_not_called()
            settings.add_recent_file(second)
            settings.add_recent_file(first)
            self.assertEqual(settings.recent_files(), [first, second])

    def test_recent_dedup_preserves_canonical_path_and_list_normalization(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            settings = AppSettings(QSettings(str(root / "recent.ini"), QSettings.Format.IniFormat))
            source = root / "main.tex"
            for stored in ([str(root / "nested" / ".." / "main.tex")], str(source)):
                settings.settings.setValue("recent/files", stored)
                settings.add_recent_file(source)
                self.assertEqual(settings.settings.value("recent/files"), [str(source)])
                self.assertEqual(settings.recent_files(), [source])
