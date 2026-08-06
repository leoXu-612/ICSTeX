from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from app.core.file_watcher import ExternalFileWatcher


class ExternalFileWatcherTests(TestCase):
    def test_ignores_build_artifacts_and_unwatched_files(self) -> None:
        changed: list[Path] = []
        watcher = ExternalFileWatcher(changed.append)
        watcher._files.add(Path("/tmp/project/main.tex").resolve())

        watcher.handle_event_path("/tmp/project/main.log")
        watcher.handle_event_path("/tmp/project/.latex_build/main.tex")
        watcher.handle_event_path("/tmp/project/chapter.tex")

        self.assertEqual(changed, [])

    def test_emits_for_watched_tex_file(self) -> None:
        changed: list[Path] = []
        watcher = ExternalFileWatcher(changed.append)
        path = Path("/tmp/project/main.tex").resolve()
        watcher._files.add(path)

        watcher.handle_event_path(path)

        self.assertEqual(changed, [path])

    def test_deleted_watched_asset_emits_change(self) -> None:
        changed: list[Path] = []
        watcher = ExternalFileWatcher(changed.append)
        path = Path("/tmp/project/figure.png").resolve()
        watcher._files.add(path)

        watcher._handler.on_deleted(SimpleNamespace(is_directory=False, src_path=str(path)))

        self.assertEqual(changed, [path])

    def test_watched_pdf_graphic_emits_change(self) -> None:
        changed: list[Path] = []
        watcher = ExternalFileWatcher(changed.append)
        path = Path("/tmp/project/figure.pdf").resolve()
        watcher._files.add(path)

        watcher.handle_event_path(path)

        self.assertEqual(changed, [path])

    def test_moved_watched_asset_emits_source_change_when_destination_is_unwatched(self) -> None:
        changed: list[Path] = []
        watcher = ExternalFileWatcher(changed.append)
        source = Path("/tmp/project/figure.png").resolve()
        destination = Path("/tmp/project/renamed.png").resolve()
        watcher._files.add(source)

        watcher._handler.on_moved(
            SimpleNamespace(
                is_directory=False,
                src_path=str(source),
                dest_path=str(destination),
            )
        )

        self.assertEqual(changed, [source])

    def test_unwatch_stops_watching_directory_once_empty(self) -> None:
        # Each watched directory keeps an OS-level watch alive. Once every
        # file in a directory has been unwatched (tab closed / moved), the
        # directory watch must be released, otherwise it leaks for the life
        # of the app as the user opens and closes projects.
        with TemporaryDirectory() as directory:
            root = Path(directory)
            sub_a = root / "a"
            sub_b = root / "b"
            sub_a.mkdir()
            sub_b.mkdir()
            file_a1 = sub_a / "one.tex"
            file_a2 = sub_a / "two.tex"
            file_b1 = sub_b / "three.tex"
            for f in (file_a1, file_a2, file_b1):
                f.write_text("", encoding="utf-8")

            watcher = ExternalFileWatcher(lambda _path: None)
            try:
                watcher.watch(file_a1)
                watcher.watch(file_a2)
                watcher.watch(file_b1)

                self.assertIn(sub_a.resolve(), watcher._dir_watches)
                self.assertIn(sub_b.resolve(), watcher._dir_watches)

                watcher.unwatch(file_a1)
                self.assertIn(sub_a.resolve(), watcher._dir_watches)

                watcher.unwatch(file_a2)
                self.assertNotIn(sub_a.resolve(), watcher._dir_watches)
                self.assertIn(sub_b.resolve(), watcher._dir_watches)
            finally:
                watcher.stop()
