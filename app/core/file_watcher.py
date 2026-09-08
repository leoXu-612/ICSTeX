from __future__ import annotations

import logging
from pathlib import Path
from queue import Empty, SimpleQueue
import threading
from typing import Callable

from watchdog.events import FileSystemEventHandler, FileSystemMovedEvent
from watchdog.observers.polling import PollingObserver

from app.core.file_observation import FileSignature, file_signature


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
        self._owners: dict[Path, set[object]] = {}
        self._dir_watches: dict[Path, object] = {}
        self._known_signatures: dict[Path, FileSignature] = {}
        self._lock = threading.RLock()
        # The native macOS FSEvents backend can terminate the whole process
        # when a watched directory is rapidly scheduled/unscheduled. ICSTeX
        # uses non-recursive watches on input directories; missing parents use
        # their nearest existing ancestor until those directories are restored.
        self._observer = PollingObserver(timeout=0.5)
        self._handler = _Handler(self)
        self._started = False
        self._closed = False
        self._repair_event = threading.Event()
        self._invalidated_dirs: SimpleQueue[Path] = SimpleQueue()
        self._repair_thread: threading.Thread | None = None

    @staticmethod
    def _path(path: str | Path) -> Path:
        candidate = Path(path).expanduser()
        # Canonicalize the parent, but do not turn a replaced leaf symlink into
        # an implicit request to watch its target.
        return candidate.parent.resolve() / candidate.name

    def watch(self, path: str | Path, *, owner: object = "editor") -> None:
        file_path = self._path(path)
        with self._lock:
            if self._closed:
                return
            self._owners.setdefault(file_path, set()).add(owner)
            if file_path not in self._files:
                self._known_signatures[file_path] = self._signature(file_path)
            self._files.add(file_path)
            self._reconcile_watches()

    def unwatch(self, path: str | Path, *, owner: object = "editor") -> None:
        raw = Path(path).expanduser().absolute()
        with self._lock:
            file_path = raw if raw in self._files else self._path(path)
            owners = self._owners.get(file_path, set())
            owners.discard(owner)
            if owners:
                return
            self._owners.pop(file_path, None)
            self._files.discard(file_path)
            self._known_signatures.pop(file_path, None)
            self._reconcile_watches()

    def set_paths(self, owner: object, paths: set[Path], *, canonical: bool = False) -> None:
        """Atomically replace one owner's membership, preserving other owners."""
        with self._lock:
            if self._closed:
                return
            desired = {Path(path).absolute() if canonical else self._path(path) for path in paths}
            for path, owners in tuple(self._owners.items()):
                if owner in owners and path not in desired:
                    owners.discard(owner)
                    if not owners:
                        self._owners.pop(path, None)
                        self._files.discard(path)
                        self._known_signatures.pop(path, None)
            for path in desired:
                self._owners.setdefault(path, set()).add(owner)
                if path not in self._files:
                    self._known_signatures[path] = self._signature(path)
                self._files.add(path)
            self._reconcile_watches()

    @staticmethod
    def _nearest_directory(path: Path) -> Path:
        directory = path.parent
        # A newly substituted ancestor symlink must not move the watch outside
        # the original tree. Watch its parent for removal/recreation instead.
        for parent in reversed((directory, *directory.parents)):
            if parent.is_symlink():
                directory = parent.parent
                break
        while not directory.is_dir() or directory.is_symlink():
            parent = directory.parent
            if parent == directory:
                break
            directory = parent
        return directory

    def _reconcile_watches(self) -> None:
        if self._closed:
            return
        while True:
            try:
                invalidated = self._invalidated_dirs.get_nowait()
            except Empty:
                break
            watch = self._dir_watches.pop(invalidated, None)
            if watch is not None:
                try:
                    self._observer.unschedule(watch)
                except KeyError:
                    pass
        desired = {self._nearest_directory(path) for path in self._files}
        for directory in tuple(self._dir_watches):
            if directory not in desired or not directory.is_dir() or directory.is_symlink():
                try:
                    self._observer.unschedule(self._dir_watches.pop(directory))
                except KeyError:
                    pass
        for directory in desired - self._dir_watches.keys():
            try:
                self._dir_watches[directory] = self._observer.schedule(
                    self._handler, str(directory), recursive=False,
                )
            except OSError:
                logger.debug("Watch directory changed during registration: %s", directory)
        if self._dir_watches and not self._started:
            self._observer.start()
            self._started = True
            self._repair_thread = threading.Thread(
                target=self._repair_loop, daemon=True, name="icstex-watch-repair",
            )
            self._repair_thread.start()

    def _repair_loop(self) -> None:
        while True:
            self._repair_event.wait()
            self._repair_event.clear()
            if self._closed:
                return
            self.reconcile()

    def schedule_reconcile(self, invalidated: str | None = None) -> None:
        # Watchdog dispatch holds its own lock. Do not acquire our membership
        # lock or schedule/unschedule observers from that callback (ABBA risk).
        if invalidated is not None:
            self._invalidated_dirs.put(Path(invalidated).absolute())
        self._repair_event.set()

    @classmethod
    def _signature(cls, path: Path) -> FileSignature:
        if path.is_symlink() or cls._nearest_directory(path) != path.parent:
            return None
        return file_signature(path)

    def reconcile(self) -> None:
        """Repair registrations and detect file creation before a new snapshot."""
        changed: list[Path] = []
        with self._lock:
            if self._closed:
                return
            self._reconcile_watches()
            for path in self._files:
                signature = self._signature(path)
                if signature != self._known_signatures.get(path):
                    self._known_signatures[path] = signature
                    changed.append(path)
        for path in changed:
            self.handle_event_path(path)

    def stop(self) -> None:
        # Serialize closure with registration. Joining without this boundary
        # could reset _started while an earlier repair still starts observers.
        with self._lock:
            self._closed = True
            self._repair_event.set()
            started = self._started
            repair_thread = self._repair_thread
        if started:
            self._observer.stop()
            self._observer.join(timeout=2)
            with self._lock:
                self._started = False
            logger.debug("File watcher stopped")
        if repair_thread is not None and repair_thread is not threading.current_thread():
            repair_thread.join(timeout=2)

    def handle_event_path(self, path: str | Path) -> None:
        file_path = Path(path).expanduser().absolute()
        if self._closed or file_path not in self._files:
            return
        self._known_signatures[file_path] = self._signature(file_path)
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
        if event.is_directory:
            self._watcher.schedule_reconcile()
        else:
            self._watcher.handle_event_path(event.src_path)

    def on_deleted(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.is_directory:
            self._watcher.schedule_reconcile(event.src_path)
        else:
            self._watcher.handle_event_path(event.src_path)

    def on_moved(self, event: FileSystemMovedEvent) -> None:
        if event.is_directory:
            self._watcher.schedule_reconcile(event.src_path)
        else:
            self._watcher.handle_event_path(event.src_path)
            self._watcher.handle_event_path(event.dest_path)
