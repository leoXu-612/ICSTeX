"""Root-owned dependency watches and bounded off-thread input observations."""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import logging
from pathlib import Path
import threading
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot

from app.core.build_events import automatic_build_purpose
from app.core.dependency_membership import MembershipInputs, MembershipResult, calculate_memberships
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
    membership_completed = Signal(object, object, object)


@dataclass(frozen=True)
class _MembershipJob:
    key: tuple
    inputs: MembershipInputs
    cancelled: threading.Event
    captured_at: float
    capture_ms: float


def _membership_work(job: _MembershipJob, signals: _Signals) -> None:
    started = time.perf_counter()
    result, error = None, None
    try:
        result = calculate_memberships(job.inputs, cancelled=job.cancelled.is_set, scan=static_dependencies)
    except Exception as exc:  # noqa: BLE001 - retain old watches on a failed calculation
        logger.exception("Dependency membership calculation failed")
        error = str(exc)
    try:
        signals.membership_completed.emit(job, (result, (time.perf_counter() - started) * 1000), error)
    except RuntimeError:
        pass


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
    memberships_ready = Signal()

    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self._scopes: dict[Path, Path] = {}
        self._root_paths: dict[Path, frozenset[Path]] = {}
        self._tab_roots: dict[int, Path] = {}
        self._tab_root_keys: dict[int, tuple] = {}
        self._membership_version = 0
        self._membership_settled_key = None
        self._membership_active = self._membership_pending = None
        self._uncertain_roots: set[Path] = set()
        self.membership_metrics_hook = None
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
        self._signals.membership_completed.connect(self._membership_finished, Qt.ConnectionType.QueuedConnection)
        self.memberships_ready.connect(window.compile.resume_dependencies, Qt.ConnectionType.QueuedConnection)
        self.memberships_ready.connect(window.documents.resume_root_save, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._launch)
        self._membership_timer = QTimer(self)
        self._membership_timer.setSingleShot(True)
        # Let continuous typing settle before rescanning the project. Explicit
        # save/compile calls still refresh immediately when they need the graph.
        self._membership_timer.setInterval(500)
        self._membership_timer.timeout.connect(self.refresh_memberships)
        self._reconcile_timer = QTimer(self)
        self._reconcile_timer.setInterval(30_000)
        self._reconcile_timer.timeout.connect(self.reconcile)
        self._reconcile_timer.start()

    @property
    def is_busy(self) -> bool:
        return not self._closed.is_set() and bool(self._active or self._queued or self._timer.isActive()
            or self._membership_timer.isActive() or self._membership_active or self._membership_pending
            or self.window.file_watcher.has_pending_memberships or self.window.compile._deferred_dependencies
            or self.window.documents.root_save_pending)

    def roots_for(self, path: Path) -> frozenset[Path]:
        # A changed root may have acquired this child before its new graph is
        # ready. Until commit, do not use absence from the old graph as proof.
        uncertain = {root for root in self._uncertain_roots
                     if path.is_relative_to(self._scopes.get(root, root.parent))}
        return frozenset(root for root in self._path_roots.get(path, ()) if root in self._root_tokens) | uncertain

    def paths_for(self, root: Path) -> frozenset[Path]:
        return self._root_paths.get(root, frozenset())

    def root_for_tab(self, tab) -> Path | None:
        """Last resolved root for presentation; never scan or create a manager."""
        if tab is None:
            return None
        if tab.manager is not None:
            return tab.manager.root_file
        identity = id(tab.editor)
        if self._tab_root_keys.get(identity) != (tab.path, self.window.selected_project_scope):
            return None
        return self._tab_roots.get(identity)

    def cache_tab_root(self, tab, root: Path) -> None:
        self._tab_roots[id(tab.editor)] = root
        self._tab_root_keys[id(tab.editor)] = (tab.path, self.window.selected_project_scope)

    def _membership_key(self) -> tuple:
        return (self.window.selected_project_scope,
                tuple((id(tab.editor), tab.path, tab.manager.root_file if tab.manager else None,
                       tab.editor.source_revision, tab.modified or tab.dirty, tab.encoding) for tab in self.window.tabs.values()),
                self._membership_version)

    @property
    def memberships_current(self) -> bool:
        return (not self._closed.is_set() and self._membership_settled_key == self._membership_key()
                and not self._active and not self._queued and not self._timer.isActive())

    def generation_for(self, root: Path) -> int:
        return self._generations.get(root, 0)

    def observations_for(self, root: Path) -> tuple[tuple[Path, InputObservation], ...]:
        """Immutable view for read-only checks; no scan or state mutation."""
        return tuple((path, self._observed[path]) for path in sorted(self.paths_for(root))
                     if path in self._observed)

    def schedule_membership_refresh(self) -> None:
        if not self._closed.is_set():
            if self._membership_active and self._membership_active.key != self._membership_key():
                self._membership_active.cancelled.set()
            self._membership_timer.start()

    def refresh_memberships(self, *, force: bool = False) -> None:
        if self._closed.is_set():
            return
        if force:
            self._membership_version += 1
        self._membership_timer.stop()
        window = self.window
        live = {id(tab.editor) for tab in window.tabs.values()}
        self._tab_roots = {identity: root for identity, root in self._tab_roots.items() if identity in live}
        self._tab_root_keys = {identity: key for identity, key in self._tab_root_keys.items() if identity in live}
        roots = set(self._tab_roots.values()) | {tab.manager.root_file for tab in window.tabs.values() if tab.manager}
        for root in self._scopes.keys() - roots:
            # Once observation stops, an old PDF cannot remain certified fresh
            # across an arbitrary closed/reopened interval.
            window.pdf_state.mark_edited(root)
            window.preview_state.mark_edited(root)
            window.compile_authorized_roots.discard(root)
            window.file_watcher.set_paths(("dependency", root), set(), canonical=True, defer_metadata=True)
            self._root_paths.pop(root, None)
            self._recorded.pop(root, None)
            self._extra.pop(root, None)
            self._root_tokens.pop(root, None)
            self._uncertain_roots.discard(root)
            self._scopes.pop(root, None)
        # Drop the old observation baseline at the last-owner boundary, not
        # after a later async graph. Reopening must not inherit a closed root's
        # baseline and interpret it as a new-root edit.
        self._path_roots = {path: owners & self._root_tokens.keys()
                            for path, owners in self._path_roots.items() if owners & self._root_tokens.keys()}
        for path in self._observed.keys() - self._path_roots.keys():
            self._observed.pop(path, None)
            self._queued.pop(path, None)
            self._serials.pop(path, None)
        key = self._membership_key()
        if key == self._membership_settled_key:
            return
        if self._membership_active and self._membership_active.key == key and not self._membership_active.cancelled.is_set():
            return
        started = time.perf_counter()
        inputs = MembershipInputs(
            tuple((id(tab.editor), tab.path, tab.manager.root_file if tab.manager else None)
                  for tab in window.tabs.values() if tab.path), window.selected_project_scope,
            tuple((tab.path, tab.editor.toPlainText()) for tab in window.tabs.values() if tab.path),
            tuple(self._recorded.items()), tuple(self._extra.items()), tuple(self._root_paths.items()),
            frozenset(self._observed),
            tuple((tab.path, tab.encoding) for tab in window.tabs.values()
                  if tab.path and not tab.modified and not tab.dirty))
        job = _MembershipJob(key, inputs, threading.Event(), started, (time.perf_counter() - started) * 1000)
        if self._membership_active:
            self._membership_active.cancelled.set()
            self._membership_pending = job
        else:
            self._start_membership(job)

    def _start_membership(self, job: _MembershipJob) -> None:
        self._membership_active = job
        threading.Thread(target=_membership_work, args=(job, self._signals),
                         daemon=True, name="icstex-dependency-membership").start()

    @Slot(object, object, object)
    def _membership_finished(self, job, measured, error) -> None:
        if self._closed.is_set() or self._membership_active is not job:
            return
        self._membership_active = None
        result, worker_ms = measured
        accepted = not job.cancelled.is_set() and job.key == self._membership_key() and result is not None
        started = time.perf_counter()
        if accepted and result.changed_saved_buffers:
            # Reuse the normal reload/IME/conflict path on the owning GUI
            # thread. A saved buffer no longer matches disk; this graph must
            # not authorize flushing/compiling until a new snapshot is ready.
            accepted = False
            for path in result.changed_saved_buffers:
                self.window.documents.reload_external_change(str(path))
        if accepted:
            self._apply_memberships(result)
            self._membership_settled_key = job.key
            self._uncertain_roots.clear()
            self.memberships_ready.emit()
        elif error and job.key == self._membership_key():
            for root in self.window.compile._deferred_dependencies:
                self.window.pdf_state.mark_edited(root)
                self.window.preview_state.mark_edited(root)
            self.window.compile._deferred_dependencies.clear()
            self.window.documents._pending_root_save = None
            self.window._sync_pdf_panel_to_active_root()
            self.window._sync_compile_indicators_to_active_root()
            self.window.statusBar().showMessage("依赖更新未完成；保留旧监听，请重试。", 6000)
        if self.membership_metrics_hook is not None:
            self.membership_metrics_hook({"accepted": accepted, "capture_ms": job.capture_ms,
                "worker_ms": worker_ms, "commit_ms": (time.perf_counter() - started) * 1000,
                "capture_to_commit_ms": (time.perf_counter() - job.captured_at) * 1000})
        # Reloading a changed saved editor can already dispatch a new job.
        # Keep its latest pending snapshot queued instead of starting a second
        # worker while that reentrant dispatch is still running.
        if self._membership_active is not None:
            return
        pending, self._membership_pending = self._membership_pending, None
        if pending is not None and pending.key == self._membership_key():
            self._start_membership(pending)
        elif self._membership_settled_key != self._membership_key() and not error and not self._membership_timer.isActive():
            # An unstable disk snapshot is retried through the existing debounce,
            # not an unbounded tight loop over a continuously changing file.
            self._membership_timer.start()

    def _apply_memberships(self, result: MembershipResult) -> None:
        window = self.window
        incoming = {item.root for item in result.roots}
        for root in self._root_paths.keys() - incoming:
            window.pdf_state.mark_edited(root)
            window.preview_state.mark_edited(root)
            window.compile_authorized_roots.discard(root)
            window.file_watcher.set_paths(("dependency", root), set(), canonical=True, defer_metadata=True)
            self._root_paths.pop(root, None)
            self._recorded.pop(root, None)
            self._extra.pop(root, None)
            self._root_tokens.pop(root, None)
        self._uncertain_roots.intersection_update(incoming)
        for identity, root in result.tab_roots:
            tab = window.tabs.get(identity)
            if tab is not None:
                self.cache_tab_root(tab, root)
        scopes = {}
        for membership in result.roots:
            root, scope, current = membership.root, membership.scope, membership.paths
            scopes[root] = scope
            if root not in self._root_tokens:
                self._token += 1
                self._root_tokens[root] = self._token
            self._root_paths[root] = frozenset(current)
            window.file_watcher.set_paths(("dependency", root), set(current), canonical=True, defer_metadata=True)
            if not membership.complete:
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
        seeded = set()
        for path, observation in result.initial_observations:
            if path in path_roots and path not in self._observed:
                self._observed[path] = observation
                seeded.add(path)
            elif path in path_roots and self._observed.get(path) != observation:
                self._queue(path, changed=True)
        active_paths = {probe.path for probe in self._active or ()}
        for path in path_roots.keys() - self._observed.keys() - self._queued.keys() - active_paths:
            self._queue(path, changed=False)
        for path in seeded - self._queued.keys():
            self._queue(path, changed=True)
        if self._queued and self._active is None and not self._timer.isActive():
            self._timer.start(0)
        if hasattr(window, "workspace"):
            window.workspace.schedule()
        window._sync_pdf_panel_to_active_root()

    def register_extra(self, root: Path, paths: tuple[Path, ...]) -> None:
        scope = self._scopes.get(root, root.parent)
        selected = frozenset(path for path in paths if safe_project_input(scope, path) is not None)
        if self._extra.get(root) != selected:
            self._extra[root] = selected
            self._membership_version += 1
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
            selected = admitted | frozenset(path for path in previous if not path.exists())
            if self._recorded.get(root) != selected:
                self._recorded[root] = selected
                self._membership_version += 1
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
        roots = self.roots_for(path) & self._root_tokens.keys()
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
            confirm_missing = (probe.changed and observation.digest is None and probe.attempts == 0
                               and observation != probe.previous)
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
        if self.memberships_current:
            self.memberships_ready.emit()

    def invalidate_roots(self, roots: set[Path], *, automatic_roots: set[Path] | None = None) -> None:
        window = self.window
        self._uncertain_roots.update(roots)
        self._membership_version += 1
        for root in roots:
            window.pdf_state.mark_edited(root)
            window.preview_state.mark_edited(root)
            self._generations[root] = self.generation_for(root) + 1
            window.compile.sync_input_revision(root)
        window._invalidate_include_cache()
        if window._compile_root_for_tab(window.current_tab()) in roots:
            window._update_pdf_action_state()
            if hasattr(window, "readiness"):
                window.readiness.invalidate()
        for root in automatic_roots or ():
            self.schedule_root(root)

    def schedule_root(self, root: Path) -> None:
        window = self.window
        purpose = automatic_build_purpose(
            enabled=window.auto_compile_action.isChecked(),
            authorized=root in window.compile_authorized_roots,
            fast_preview=window.preferences.fast_preview,
        )
        if purpose is None:
            return
        window.compile.compile_for_root(root, purpose, reason="输入依赖修改")

    def reconcile(self) -> None:
        if self._closed.is_set():
            return
        self._membership_version += 1
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
        self.window.documents._pending_root_save = None
        self.window.compile._deferred_dependencies.clear()
        if self._membership_active:
            self._membership_active.cancelled.set()
        self._membership_pending = None
        self._timer.stop()
        self._membership_timer.stop()
        self._reconcile_timer.stop()
        self._queued.clear()
        self._active = None
        self._signals.completed.disconnect(self._finished)
        self._signals.membership_completed.disconnect(self._membership_finished)
