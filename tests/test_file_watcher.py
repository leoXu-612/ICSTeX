from __future__ import annotations

from pathlib import Path
import shutil
import threading
import time
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.core.file_watcher import ExternalFileWatcher


class ExternalFileWatcherTests(TestCase):
    def test_profile_opt_in_does_not_enable_other_metadata_or_outputs(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            profile = root / ".icstex" / "project-profile.json"
            other = root / ".icstex" / "sources.json"
            output = root / ".icstex" / "preview" / "main.tex"
            output.parent.mkdir(parents=True)
            changed = []
            watcher = ExternalFileWatcher(changed.append)
            try:
                watcher.set_paths("profile", {profile, other, output}, canonical=True)
                watcher.handle_event_path(profile)
                self.assertFalse(changed)
                watcher.set_paths("profile", {profile, other, output}, canonical=True, project_profile=True)
                for path in (profile, other, output):
                    watcher.handle_event_path(path)
                self.assertEqual(changed, [profile])
                watcher.set_paths("profile", set(), canonical=True)
                self.assertNotIn("profile", watcher._profile_metadata_owners)
            finally:
                watcher.stop()

    def test_block_metadata_is_opt_in_and_never_enables_preview_outputs(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            metadata = root / ".icstex" / "sources.json"
            preview = root / ".icstex" / "preview" / "main.tex"
            preview.parent.mkdir(parents=True)
            metadata.write_text('{"sources":[]}')
            preview.write_text("preview")
            changed = []
            watcher = ExternalFileWatcher(changed.append)
            try:
                watcher.set_paths("source", {metadata, preview}, canonical=True)
                watcher.handle_event_path(metadata)
                self.assertEqual(changed, [])
                watcher.set_paths("check", {metadata, preview}, canonical=True, block_metadata=True)
                watcher.handle_event_path(metadata)
                watcher.handle_event_path(preview)
                self.assertEqual(changed, [metadata])
                watcher.set_paths("check", set(), canonical=True)
                watcher.handle_event_path(metadata)
                self.assertEqual(changed, [metadata])
                self.assertIn(metadata, watcher._files, "another owner still holds membership")
            finally:
                watcher.stop()

    def test_stop_cannot_race_registration_and_restart_observer(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "main.tex"
            path.write_text("text")
            watcher = ExternalFileWatcher(lambda _path: None)
            watcher.watch(path)
            entered, release, stopped = threading.Event(), threading.Event(), threading.Event()
            original = watcher._nearest_directory
            errors = []

            def delayed(candidate):
                entered.set()
                release.wait(2)
                return original(candidate)

            def repair():
                try:
                    watcher.reconcile()
                except Exception as error:
                    errors.append(error)

            with patch.object(watcher, "_nearest_directory", side_effect=delayed):
                worker = threading.Thread(target=repair)
                worker.start()
                self.assertTrue(entered.wait(1))
                stopper = threading.Thread(target=lambda: (watcher.stop(), stopped.set()))
                stopper.start()
                try:
                    self.assertFalse(stopped.wait(0.02))
                finally:
                    release.set()
                    worker.join(2)
                    stopper.join(2)
            self.assertTrue(stopped.is_set())
            self.assertFalse(errors)
            self.assertFalse(watcher._observer.is_alive())

    def test_shared_membership_survives_editor_close(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "child.tex"
            path.write_text("text")
            watcher = ExternalFileWatcher(lambda _path: None)
            try:
                watcher.watch(path)
                watcher.set_paths(("dependency", "main"), {path})
                watcher.unwatch(path)
                self.assertIn(path, watcher._files)
                watcher.set_paths(("dependency", "main"), set())
                self.assertNotIn(path, watcher._files)
                self.assertFalse(watcher._dir_watches)
            finally:
                watcher.stop()

    def test_missing_nested_parent_and_deleted_directory_recover_with_polling(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "chapters" / "nested" / "child.tex"
            changes: list[Path] = []
            watcher = ExternalFileWatcher(changes.append)

            def wait_for(predicate) -> bool:
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    if predicate():
                        return True
                    time.sleep(0.02)
                return predicate()

            try:
                watcher.watch(path)
                self.assertIn(root, watcher._dir_watches)
                path.parent.mkdir(parents=True)
                path.write_text("created")
                self.assertTrue(wait_for(lambda: path in changes))
                self.assertTrue(wait_for(lambda: path.parent in watcher._dir_watches))
                changes.clear()
                shutil.rmtree(root / "chapters")
                self.assertTrue(wait_for(lambda: path in changes))
                changes.clear()
                path.parent.mkdir(parents=True)
                path.write_text("recreated")
                self.assertTrue(wait_for(lambda: path in changes))
                self.assertTrue(wait_for(lambda: path.parent in watcher._dir_watches))
                changes.clear()
                path.write_text("later edit")
                self.assertTrue(wait_for(lambda: path in changes))
            finally:
                watcher.stop()

    def test_ignores_build_artifacts_and_unwatched_files(self) -> None:
        changed: list[Path] = []
        watcher = ExternalFileWatcher(changed.append)
        watcher._files.add(Path("/tmp/project/main.tex").resolve())

        watcher.handle_event_path("/tmp/project/main.log")
        watcher.handle_event_path("/tmp/project/.latex_build/main.tex")
        watcher.handle_event_path("/tmp/project/.icstex/preview/main.tex")
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
