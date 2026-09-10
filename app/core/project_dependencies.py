"""Conservative, project-scoped static and recorder input dependencies.

These paths grant no compilation or network authority. Generated files,
out-of-scope paths and symbolic links are excluded before reading or watching.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import hashlib
from itertools import islice
import os
from pathlib import Path
import re
import stat
from typing import Callable, Mapping

from app.core.file_observation import file_signature
from app.core.image_assets import IMAGE_SUFFIXES
from app.core.paths import strip_latex_comments
from app.core.text_encoding import LatexTextDecodeError, decode_latex_bytes


INTERNAL_DIRS = frozenset({".latex_build", ".icstex", ".git", "__pycache__"})
GENERATED_SUFFIXES = frozenset({
    ".aux", ".log", ".out", ".toc", ".fls", ".fdb_latexmk", ".synctex",
    ".gz", ".bbl", ".bcf", ".blg", ".tmp", ".importing", ".xdv", ".dvi",
})
SOURCE_SUFFIXES = frozenset({".tex", ".sty", ".cls", ".ltx"})
MAX_INPUTS = 2_000
MAX_SOURCE_BYTES = 4 * 1024 * 1024
_DYNAMIC = frozenset("\\#$%{}~\x00\r\n")
_REFERENCE = re.compile(
    r"\\(?P<command>input|include|subfile|includegraphics|includesvg|includepdf|bibliography|addbibresource|"
    r"bibliographystyle|documentclass|usepackage|RequirePackage|LoadClass)\*?"
    r"\s*(?:\[[^\]]*\]\s*)?\{(?P<target>[^{}]+)\}"
)
_UNBRACED_INPUT = re.compile(r"\\input\s+([^\s%{}]+)")
_GRAPHICSPATH = re.compile(r"\\graphicspath\s*\{((?:\s*\{[^{}]*\}\s*)+)\}")
_BRACED = re.compile(r"\{([^{}]*)\}")


def safe_project_input(scope: Path, path: Path, *, allow_internal: bool = False) -> Path | None:
    """Canonicalize lexically while rejecting every traversed symlink."""
    scope = scope.expanduser().resolve()
    candidate = path if path.is_absolute() else scope / path
    try:
        parts = candidate.relative_to(scope).parts
    except ValueError:
        return None
    current = scope
    for part in parts:
        if part in {"", "."}:
            continue
        if part == "..":
            current = current.parent
            if not current.is_relative_to(scope):
                return None
            continue
        if not allow_internal and part in INTERNAL_DIRS:
            return None
        current /= part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            return None
    if current == scope or not current.is_relative_to(scope):
        return None
    if not allow_internal and current.suffix.lower() in GENERATED_SUFFIXES:
        return None
    return current


@contextmanager
def _open_safe_input(scope: Path, path: Path, *, allow_internal: bool = False):
    safe = safe_project_input(scope, path, allow_internal=allow_internal)
    if safe is None:
        raise PermissionError("Input is not a safe project file")
    handles: list[int] = []
    leaf: int | None = None
    try:
        if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
            directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            directory = os.open(safe.anchor, directory_flags)
            handles.append(directory)
            for component in safe.parts[1:-1]:
                directory = os.open(component, directory_flags, dir_fd=directory)
                handles.append(directory)
            leaf = os.open(safe.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        else:
            # Platforms without openat still reject known links/junctions and
            # non-regular files before opening and validate after observation.
            if not safe.is_file():
                raise FileNotFoundError(safe)
            leaf = os.open(safe, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        if not stat.S_ISREG(os.fstat(leaf).st_mode):
            raise PermissionError("Input is not a regular file")
        stream = os.fdopen(leaf, "rb")
        leaf = None
        with stream:
            yield stream
    finally:
        if leaf is not None:
            os.close(leaf)
        for handle in reversed(handles):
            os.close(handle)


def _read_source_bytes(path: Path, scope: Path, *, allow_internal: bool = False,
                       max_bytes: int = MAX_SOURCE_BYTES) -> bytes:
    with _open_safe_input(scope, path, allow_internal=allow_internal) as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise OSError("Dependency source exceeds the bounded parser size")
    return data


@dataclass(frozen=True)
class InputReference:
    source: Path
    line: int
    command: str
    value: str
    candidates: tuple[Path, ...] = ()
    unresolved: bool = False
    rejected_candidates: bool = False


def read_project_bytes(path: Path, scope: Path, *, allow_internal: bool = False,
                       max_bytes: int = MAX_SOURCE_BYTES) -> bytes:
    """Read one bounded regular file without following links or leaving scope."""
    if not 0 < max_bytes <= MAX_SOURCE_BYTES:
        raise ValueError("Read limit must remain within the bounded parser size")
    return _read_source_bytes(path, scope, allow_internal=allow_internal, max_bytes=max_bytes)


def read_project_source(path: Path, scope: Path) -> str:
    """Read bounded source with the same strict path/encoding rules as tracking."""
    return decode_latex_bytes(_read_source_bytes(path, scope)).text


@dataclass(frozen=True)
class DependencySnapshot:
    paths: frozenset[Path]
    complete: bool = True
    references: tuple[InputReference, ...] = ()


def static_dependencies(
    root: Path, scope: Path, buffers: Mapping[Path, str] | None = None,
    *, max_inputs: int = MAX_INPUTS, source_reader: Callable[[Path], str] | None = None,
    max_references: int | None = None,
) -> DependencySnapshot:
    """Resolve literal inputs without executing macros or searching a distro."""
    root = safe_project_input(scope, root)
    if root is None:
        return DependencySnapshot(frozenset(), False)
    source_buffers = buffers or {}
    paths: set[Path] = {root}
    visited: set[Path] = set()
    queue = [root]
    graphics_dirs: set[Path] = set()
    found: list[InputReference] = []
    complete = True
    while queue:
        source = queue.pop(0)
        if source in visited or source.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        visited.add(source)
        if safe_project_input(scope, source) is None:
            continue
        text = source_buffers.get(source)
        if text is None:
            try:
                text = (source_reader(source) if source_reader is not None
                        else decode_latex_bytes(_read_source_bytes(source, scope)).text)
            except FileNotFoundError:
                continue
            except (OSError, LatexTextDecodeError):
                complete = False
                continue
        clean = strip_latex_comments(text)
        for group in _GRAPHICSPATH.finditer(clean):
            for raw_dir in _BRACED.findall(group.group(1)):
                if any(char in _DYNAMIC for char in raw_dir):
                    continue
                for base in (root.parent, source.parent):
                    directory = safe_project_input(scope, base / raw_dir)
                    if directory is not None:
                        graphics_dirs.add(directory)
        allowance = max_references - len(found) + 1 if max_references is not None else None
        references = [(match.group("command"), match.group("target"), match.start())
                      for match in islice(_REFERENCE.finditer(clean), allowance)]
        references.extend(("input", match.group(1), match.start())
                          for match in islice(_UNBRACED_INPUT.finditer(clean), allowance))
        if max_references is not None and len(found) + len(references) > max_references:
            return DependencySnapshot(frozenset(paths), False, tuple(found))
        recognized = {offset for _, _, offset in references}
        for match in re.finditer(r"\\(?:input|include|subfile|includegraphics|includesvg|includepdf|bibliography|addbibresource)\b", clean):
            if match.start() not in recognized:
                if max_references is not None and len(found) >= max_references:
                    return DependencySnapshot(frozenset(paths), False, tuple(found))
                found.append(InputReference(source, clean.count("\n", 0, match.start()) + 1,
                                            match.group()[1:], "dynamic", unresolved=True))
        for command, targets, offset in references:
            line = clean.count("\n", 0, offset) + 1
            values = targets.split(",") if command in {"bibliography", "usepackage", "RequirePackage"} else [targets]
            for value in values:
                if max_references is not None and len(found) >= max_references:
                    return DependencySnapshot(frozenset(paths), False, tuple(found))
                raw = value.strip().strip('"')
                if not raw or any(char in _DYNAMIC for char in raw):
                    found.append(InputReference(source, line, command, raw, unresolved=True))
                    continue
                literal = Path(raw)
                suffixes = _suffixes_for(command, literal)
                bases = [root.parent, source.parent]
                if command == "includegraphics":
                    bases.extend(sorted(graphics_dirs))
                candidates: list[Path] = []
                rejected = False
                for base in dict.fromkeys(bases):
                    candidate = literal if literal.is_absolute() else base / literal
                    for suffix in suffixes:
                        expanded = candidate.with_suffix(suffix) if suffix else candidate
                        safe = safe_project_input(scope, expanded)
                        if safe is None:
                            rejected = True
                            continue
                        if safe not in candidates:
                            candidates.append(safe)
                        if safe in paths:
                            continue
                        if len(paths) >= max_inputs:
                            return DependencySnapshot(frozenset(paths), False, tuple(found))
                        paths.add(safe)
                        if safe.suffix.lower() in SOURCE_SUFFIXES:
                            queue.append(safe)
                found.append(InputReference(source, line, command, raw, tuple(candidates), not candidates, rejected))
    return DependencySnapshot(frozenset(paths), complete, tuple(found))


def _suffixes_for(command: str, path: Path) -> tuple[str, ...]:
    if path.suffix:
        return ("",)
    if command == "includegraphics":
        return tuple(sorted(IMAGE_SUFFIXES))
    if command == "includesvg":
        return (".svg",)
    if command == "includepdf":
        return (".pdf",)
    if command in {"bibliography", "addbibresource"}:
        return (".bib",)
    if command in {"usepackage", "RequirePackage"}:
        return (".sty",)
    if command in {"documentclass", "LoadClass"}:
        return (".cls",)
    if command == "bibliographystyle":
        return (".bst",)
    return (".tex", "") if command == "input" else (".tex",)


def recorder_dependencies(text: str, *, root: Path, scope: Path) -> DependencySnapshot:
    """INPUT minus OUTPUT, always bounded by the explicitly selected project."""
    inputs: set[Path] = set()
    outputs: set[Path] = set()
    complete = True
    for line in text.splitlines():
        kind, separator, raw = line.partition(" ")
        if not separator or kind not in {"INPUT", "OUTPUT"}:
            continue
        value = raw.strip().strip('"')
        if not value or "\x00" in value:
            continue
        literal = Path(value)
        candidate = literal if literal.is_absolute() else root.parent / literal
        safe = safe_project_input(scope, candidate, allow_internal=kind == "OUTPUT")
        if safe is None:
            continue
        target = inputs if kind == "INPUT" else outputs
        if len(target) >= MAX_INPUTS:
            complete = False
            continue
        target.add(safe)
    return DependencySnapshot(frozenset(inputs - outputs), complete)


def read_recorder_dependencies(path: Path, *, root: Path, scope: Path) -> DependencySnapshot | None:
    safe = safe_project_input(scope, path, allow_internal=True)
    if safe is None:
        return None
    try:
        text = _read_source_bytes(safe, scope, allow_internal=True).decode("utf-8", errors="strict")
        return recorder_dependencies(text, root=root, scope=scope)
    except (OSError, UnicodeError):
        return None


@dataclass(frozen=True)
class InputObservation:
    digest: str | None
    stable: bool
    readable: bool = True


def observe_input(path: Path, scope: Path, *, allow_internal: bool = False) -> InputObservation:
    """Hash only safe inputs; callers run this I/O outside the GUI thread."""
    if safe_project_input(scope, path, allow_internal=allow_internal) is None:
        return InputObservation(None, True, False)
    before = file_signature(path)
    if before is None:
        return InputObservation(None, True)
    digest = hashlib.sha256()
    try:
        with _open_safe_input(scope, path, allow_internal=allow_internal) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return InputObservation(None, False, False)
    stable = (before == file_signature(path)
              and safe_project_input(scope, path, allow_internal=allow_internal) is not None)
    return InputObservation(digest.hexdigest(), stable)
