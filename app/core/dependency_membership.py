"""Immutable dependency membership calculation; no widgets or state publication."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Callable

from app.core.paths import resolve_root_tex
from app.core.project_dependencies import (
    MAX_INPUTS, InputObservation, observe_input, read_project_bytes, safe_project_input, static_dependencies,
)
from app.core.text_encoding import decode_latex_bytes


@dataclass(frozen=True)
class MembershipInputs:
    tabs: tuple[tuple[int, Path, Path | None], ...]
    selected_scope: Path | None
    buffers: tuple[tuple[Path, str], ...]
    recorded: tuple[tuple[Path, frozenset[Path]], ...]
    extra: tuple[tuple[Path, frozenset[Path]], ...]
    previous: tuple[tuple[Path, frozenset[Path]], ...]
    observed_paths: frozenset[Path]
    saved_buffers: tuple[tuple[Path, str], ...] = ()


@dataclass(frozen=True)
class RootMembership:
    root: Path
    scope: Path
    paths: frozenset[Path]
    complete: bool


@dataclass(frozen=True)
class MembershipResult:
    tab_roots: tuple[tuple[int, Path], ...]
    roots: tuple[RootMembership, ...]
    initial_observations: tuple[tuple[Path, InputObservation], ...]
    changed_saved_buffers: tuple[Path, ...] = ()


def calculate_memberships(inputs: MembershipInputs, *, cancelled: Callable[[], bool],
                          scan=static_dependencies) -> MembershipResult | None:
    # Resolve parent aliases (for example /var -> /private/var on macOS), but
    # leave the leaf lexical so a substituted file symlink is still rejected.
    canonical = lambda path: path.parent.resolve() / path.name
    buffers = {canonical(path): text for path, text in inputs.buffers}
    tab_roots, scopes_by_path = [], {}
    for identity, path, explicit_root in inputs.tabs:
        if cancelled():
            return None
        root = explicit_root or resolve_root_tex(path, selected_scope=inputs.selected_scope).root or canonical(path)
        tab_roots.append((identity, root))
        scopes_by_path[canonical(path)] = inputs.selected_scope or root.parent
    saved_observations = {}
    changed = []
    for path, encoding in inputs.saved_buffers:
        if cancelled():
            return None
        path = canonical(path)
        if safe_project_input(scopes_by_path[path], path) is None:
            # Other open tabs can be outside the newly selected project.
            # Do not read them or let them block the in-scope membership batch.
            continue
        raw = read_project_bytes(path, scopes_by_path[path])
        text = decode_latex_bytes(raw, encoding=encoding).text
        # Compare the existing Qt plain-text projection, not a rewritten source
        # or a normalized byte identity. Actual build/file evidence stays raw.
        text = text.replace("\r\n", "\n").translate({13: "\n", 0x2028: "\n", 0x2029: "\n", 0xA0: " "})
        if text != buffers[path]:
            changed.append(path)
        saved_observations[path] = InputObservation(hashlib.sha256(raw).hexdigest(), True)
    if changed:
        return MembershipResult((), (), (), tuple(changed))
    recorded, extra, previous = map(dict, (inputs.recorded, inputs.extra, inputs.previous))
    memberships, observations = [], {}
    for root in sorted({root for _, root in tab_roots}):
        if cancelled():
            return None
        scope = inputs.selected_scope or root.parent
        parsed = {path: observation for path, observation in saved_observations.items()
                  if path.is_relative_to(scope)}

        def read_source(path):
            raw = read_project_bytes(path, scope)
            parsed[path] = InputObservation(hashlib.sha256(raw).hexdigest(), True)
            return decode_latex_bytes(raw).text

        static = scan(root, scope, buffers, source_reader=read_source)
        # A child changing while it is parsed could introduce an unseen grandchild.
        # Reject that calculation instead of certifying a graph of mixed bytes.
        for path, before in parsed.items():
            if cancelled() or observe_input(path, scope) != before:
                return None
            observations[path] = before
        candidates = {path for path in static.paths | recorded.get(root, frozenset())
                      | extra.get(root, frozenset()) if path.is_relative_to(scope)}
        retained = {path for path in previous.get(root, ()) if path.is_relative_to(scope)
                    and (not path.exists() or safe_project_input(scope, path) is None)}
        current = set(sorted(candidates)[:MAX_INPUTS])
        current.update(sorted(retained - current)[:MAX_INPUTS - len(current)])
        memberships.append(RootMembership(root, scope, frozenset(current),
            static.complete and len(candidates | retained) <= MAX_INPUTS))
        # Seed new watches from a worker-captured content observation, then the
        # existing observation queue rechecks them after GUI publication. A
        # changed file cannot disappear into a new watch's metadata baseline.
        for path in sorted(current - inputs.observed_paths - observations.keys()):
            if cancelled():
                return None
            observations[path] = observe_input(path, scope)
    return MembershipResult(tuple(tab_roots), tuple(memberships), tuple(observations.items()))
