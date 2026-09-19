from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler, FileSystemMovedEvent
from watchdog.observers.polling import PollingObserver


logger = logging.getLogger(__name__)


IGNORED_SUFFIXES = {
    ".aux",
    ".log",
    ".out",
    ".toc",
    ".fls",
    ".fdb_latexmk",
    ".synctex",
    ".gz",
    ".bbl",
    ".bcf",
    ".blg",
    ".run.xml",
    ".tmp",
    ".importing",
}


class ExternalFileWatcher:
    """Watch source files that may be changed outside the editor."""

    def __init__(self, on_change: Callable[[Path], None]) -> None:
        self._on_change = on_change
        self._files: set[Path] = set()
        self._dir_watches: dict[Path, object] = {}
        # The native macOS FSEvents backend can terminate the whole process
        # when a watched directory is rapidly scheduled/unscheduled. ICSTeX
        # watches only a handful of open source files, so polling is a small
        # cost for deterministic cross-platform behavior.
        self._observer = PollingObserver(timeout=0.5)
        self._handler = _Handler(self)
        self._started = False

    def watch(self, path: str | Path) -> None:
        file_path = Path(path).expanduser().resolve()
        self._files.add(file_path)
        directory = file_path.parent
        if directory not in self._dir_watches:
            watch = self._observer.schedule(self._handler, str(directory), recursive=False)
            self._dir_watches[directory] = watch
            logger.debug("Watching directory %s for changes to %s", directory, file_path.name)
        if not self._started:
            self._observer.start()
            self._started = True
            logger.debug("File watcher started")

    def unwatch(self, path: str | Path) -> None:
        file_path = Path(path).expanduser().resolve()
        self._files.discard(file_path)
        directory = file_path.parent
        if directory in self._dir_watches and not any(f.parent == directory for f in self._files):
            self._observer.unschedule(self._dir_watches.pop(directory))
            logger.debug("Stopped watching directory %s, no files left in it", directory)

    def stop(self) -> None:
        if self._started:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._started = False
            logger.debug("File watcher stopped")

    def handle_event_path(self, path: str | Path) -> None:
        file_path = Path(path).expanduser().resolve()
        if file_path not in self._files:
            return
        if (
            ".latex_build" in file_path.parts
            or ".icstex" in file_path.parts
            or file_path.suffix.lower() in IGNORED_SUFFIXES
        ):
            return
        self._on_change(file_path)


class _Handler(FileSystemEventHandler):
    def __init__(self, watcher: ExternalFileWatcher) -> None:
        self._watcher = watcher

    def on_modified(self, event) -> None:  # type: ignore[no-untyped-def]
        if not event.is_directory:
            self._watcher.handle_event_path(event.src_path)

    def on_created(self, event) -> None:  # type: ignore[no-untyped-def]
        if not event.is_directory:
            self._watcher.handle_event_path(event.src_path)

    def on_deleted(self, event) -> None:  # type: ignore[no-untyped-def]
        if not event.is_directory:
            self._watcher.handle_event_path(event.src_path)

    def on_moved(self, event: FileSystemMovedEvent) -> None:
        if not event.is_directory:
            self._watcher.handle_event_path(event.src_path)
            self._watcher.handle_event_path(event.dest_path)
