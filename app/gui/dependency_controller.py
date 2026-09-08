"""Root-owned dependency watches and bounded off-thread input observations."""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import logging
from pathlib import Path
import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot

from app.core.build_events import automatic_build_purpose
from app.core.project_dependencies import (
    MAX_INPUTS, InputObservation, observe_input,
    safe_project_input, static_dependencies,
)

if TYPE_CHECKING:
    from app.core.compiler import CompileResult
    from app.gui.main_window import MainWindow


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Probe:
    path: Path
    scope: Path
    serial: int
    owners: tuple[tuple[Path, int], ...]
    previous: InputObservation | None
    changed: bool
    attempts: int = 0


class _Signals(QObject):
    completed = Signal(object, object)


def _observe(probes: tuple[_Probe, ...], signals: _Signals, closed: threading.Event) -> None:
    observations = []
    for probe in probes:
        if closed.is_set():
            return
        try:
            observation = observe_input(probe.path, probe.scope)
        except Exception:  # noqa: BLE001 - keep the bounded queue recoverable
            logger.exception("Dependency observation failed: %s", probe.path)
            observation = InputObservation(None, False, False)
        observations.append(observation)
    try:
        signals.completed.emit(probes, tuple(observations))
    except RuntimeError:
        pass


class DependencyController(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self._scopes: dict[Path, Path] = {}
        self._root_paths: dict[Path, frozenset[Path]] = {}
        self._recorded: dict[Path, frozenset[Path]] = {}
        self._extra: dict[Path, frozenset[Path]] = {}
        self._path_roots: dict[Path, set[Path]] = {}
        self._root_tokens: dict[Path, int] = {}
        self._generations: dict[Path, int] = {}
        self._token = 0
        self._serials: dict[Path, int] = {}
        self._observed: dict[Path, InputObservation] = {}
        self._queued: dict[Path, _Probe] = {}
        self._active: tuple[_Probe, ...] | None = None
        self._closed = threading.Event()
        self._signals = _Signals()
        self._signals.completed.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._launch)
        self._membership_timer = QTimer(self)
        self._membership_timer.setSingleShot(True)
        self._membership_timer.setInterval(200)
        self._membership_timer.timeout.connect(self.refresh_memberships)
        self._reconcile_timer = QTimer(self)
        self._reconcile_timer.setInterval(30_000)
        self._reconcile_timer.timeout.connect(self.reconcile)
        self._reconcile_timer.start()

    @property
    def is_busy(self) -> bool:
        return bool(self._active or self._queued or self._timer.isActive() or self._membership_timer.isActive())

    def roots_for(self, path: Path) -> frozenset[Path]:
        return frozenset(self._path_roots.get(path, ()))

    def paths_for(self, root: Path) -> frozenset[Path]:
        return self._root_paths.get(root, frozenset())

    def generation_for(self, root: Path) -> int:
        return self._generations.get(root, 0)

    def schedule_membership_refresh(self) -> None:
        if not self._closed.is_set():
            self._membership_timer.start()

    def refresh_memberships(self) -> None:
        if self._closed.is_set():
            return
        self._membership_timer.stop()
        window = self.window
        roots = {
            root for tab in window.tabs.values()
            if (root := window._compile_root_for_tab(tab)) is not None
        }
        for root in self._scopes.keys() - roots:
            # Once observation stops, an old PDF cannot remain certified fresh
            # across an arbitrary closed/reopened interval.
            window.pdf_state.mark_edited(root)
            window.preview_state.mark_edited(root)
            window.compile_authorized_roots.discard(root)
            window.file_watcher.set_paths(("dependency", root), set(), canonical=True)
            self._root_paths.pop(root, None)
            self._recorded.pop(root, None)
            self._extra.pop(root, None)
            self._root_tokens.pop(root, None)
        buffers = {tab.path.resolve(): tab.editor.toPlainText() for tab in window.tabs.values() if tab.path}
        scopes = {}
        for root in roots:
            selected = window.selected_project_scope
            scope = selected if selected is not None else root.parent
            scopes[root] = scope
            if root not in self._root_tokens:
                self._token += 1
                self._root_tokens[root] = self._token
            static = static_dependencies(root, scope, buffers)
            candidates = {
                path for path in static.paths | self._recorded.get(root, frozenset()) | self._extra.get(root, frozenset())
                if path.is_relative_to(scope)
            }
            previous = self._root_paths.get(root, frozenset())
            # Previously owned missing paths stay observable through recreation;
            # a substituted symlink never grants target access.
            retained = {
                path for path in previous
                if path.is_relative_to(scope) and (not path.exists() or safe_project_input(scope, path) is None)
            }
            current = set(sorted(candidates)[:MAX_INPUTS])
            for path in sorted(retained - current):
                if len(current) >= MAX_INPUTS:
                    break
                current.add(path)
            self._root_paths[root] = frozenset(current)
            window.file_watcher.set_paths(("dependency", root), current, canonical=True)
            if not static.complete or len(candidates | retained) > MAX_INPUTS:
                logger.warning("Dependency tracking limit or unreadable source: %s", root)
                window.statusBar().showMessage("部分依赖无法完整追踪；请显式重新编译确认 PDF。", 6000)
        self._scopes = scopes
        path_roots: dict[Path, set[Path]] = {}
        for root, paths in self._root_paths.items():
            for path in paths:
                path_roots.setdefault(path, set()).add(root)
        self._path_roots = path_roots
        for path in set(self._observed) - path_roots.keys():
            self._observed.pop(path, None)
        for path in set(self._queued) - path_roots.keys():
            self._queued.pop(path, None)
        self._serials = {path: value for path, value in self._serials.items() if path in path_roots}
        active_paths = {probe.path for probe in self._active or ()}
        for path in path_roots.keys() - self._observed.keys() - self._queued.keys() - active_paths:
            self._queue(path, changed=False)
        if self._queued and self._active is None and not self._timer.isActive():
            self._timer.start(0)

    def register_extra(self, root: Path, paths: tuple[Path, ...]) -> None:
        scope = self._scopes.get(root, root.parent)
        self._extra[root] = frozenset(path for path in paths if safe_project_input(scope, path) is not None)
        self.refresh_memberships()

    def accept_build(self, result: "CompileResult") -> None:
        root = result.root_file
        scope = self._scopes.get(root)
        if scope is None or not result.ok:
            return
        recorded = result.recorder_inputs
        if recorded is not None:
            previous = self._recorded.get(root, frozenset())
            admitted = frozenset(path for path in recorded if safe_project_input(scope, path) is not None)
            self._recorded[root] = admitted | frozenset(path for path in previous if not path.exists())
        self.refresh_memberships()

    def remember_disk(self, path: Path, data: bytes) -> bool:
        """A decoded open-file reload/save echo already has its exact bytes."""
        if path not in self._path_roots:
            return True
        self._serials[path] = self._serials.get(path, 0) + 1
        self._queued.pop(path, None)
        observation = InputObservation(hashlib.sha256(data).hexdigest(), True)
        changed = self._observed.get(path) != observation
        self._observed[path] = observation
        return changed

    def handle_external_change(self, path: Path) -> bool:
        if self._closed.is_set() or path not in self._path_roots:
            return False
        self._queue(path, changed=True)
        self._timer.start(200)
        return True

    def _queue(self, path: Path, *, changed: bool) -> None:
        roots = self.roots_for(path)
        if not roots:
            return
        serial = self._serials.get(path, 0) + 1
        self._serials[path] = serial
        prior = self._queued.get(path)
        self._queued[path] = _Probe(
            path, self._scopes[next(iter(roots))], serial,
            tuple(sorted((root, self._root_tokens[root]) for root in roots)),
            prior.previous if prior is not None else self._observed.get(path),
            changed or (prior.changed if prior else False),
        )

    def _launch(self) -> None:
        if self._closed.is_set() or self._active is not None or not self._queued:
            return
        probes = tuple(sorted(self._queued.values(), key=lambda probe: not probe.changed)[:32])
        for probe in probes:
            self._queued.pop(probe.path, None)
        self._active = probes
        threading.Thread(
            target=_observe, args=(probes, self._signals, self._closed),
            daemon=True, name="icstex-input-observation",
        ).start()

    @Slot(object, object)
    def _finished(self, probes: tuple[_Probe, ...], observations: tuple[InputObservation, ...]) -> None:
        if self._closed.is_set() or self._active is not probes:
            return
        self._active = None
        changed_roots: set[Path] = set()
        automatic_roots: set[Path] = set()
        changed_paths: list[Path] = []
        for probe, observation in zip(probes, observations):
            if probe.serial != self._serials.get(probe.path):
                continue
            roots = {
                root for root, token in probe.owners
                if self._root_tokens.get(root) == token and root in self.roots_for(probe.path)
            }
            if not roots:
                continue
            confirm_missing = probe.changed and observation.digest is None and probe.attempts == 0
            if (not observation.stable or confirm_missing) and probe.attempts < 2:
                self._queued[probe.path] = replace(probe, attempts=probe.attempts + 1)
                self._timer.start(200)
                continue
            self._observed[probe.path] = observation
            if probe.changed and (probe.previous is None or observation != probe.previous):
                changed_paths.append(probe.path)
                changed_roots.update(roots)
                if observation.stable and observation.readable:
                    automatic_roots.update(roots)
        if changed_roots:
            self.invalidate_roots(changed_roots, automatic_roots=automatic_roots)
            for path in changed_paths:
                self.window.project_panels.external_changed(path)
            self.window.word_counts.schedule()
            self.refresh_memberships()
        # A root may close and reopen while the old observation is running.
        # Its token-invalidated reply cannot seed the new membership baseline.
        for path in self._path_roots.keys() - self._observed.keys() - self._queued.keys():
            self._queue(path, changed=False)
        if self._queued and not self._timer.isActive():
            self._timer.start(0)

    def invalidate_roots(self, roots: set[Path], *, automatic_roots: set[Path] | None = None) -> None:
        window = self.window
        for root in roots:
            window.pdf_state.mark_edited(root)
            window.preview_state.mark_edited(root)
            self._generations[root] = self.generation_for(root) + 1
            window.compile.sync_input_revision(root)
        window._invalidate_include_cache()
        if window._compile_root_for_tab(window.current_tab()) in roots:
            window._update_pdf_action_state()
        for root in automatic_roots or ():
            self.schedule_root(root)

    def schedule_root(self, root: Path) -> None:
        window = self.window
        purpose = automatic_build_purpose(
            enabled=window.auto_compile_action.isChecked(),
            authorized=root in window.compile_authorized_roots,
            fast_preview=window.preferences.fast_preview,
        )
        if purpose is None or not window.documents.flush_root_documents(root):
            return
        manager = window.compile_managers.get(root)
        if manager is not None:
            manager.schedule_compile("输入依赖修改", purpose)

    def reconcile(self) -> None:
        if self._closed.is_set():
            return
        self.refresh_memberships()
        self.window.file_watcher.reconcile()
        for path in self._path_roots:
            if self.window._tab_for_path(path) is None:
                self._queue(path, changed=True)
        if self._queued:
            self._timer.start(200)

    def shutdown(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        self._timer.stop()
        self._membership_timer.stop()
        self._reconcile_timer.stop()
        self._queued.clear()
        self._active = None
        self._signals.completed.disconnect(self._finished)
