"""Read-only citation health for captured ordinary-source projects."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from threading import Event

from app.core.citation_syntax import (
    literal_bib_value, mask_tex_noncontent, parse_bibliography, scan_citation_uses,
)
from app.core.project_dependencies import (
    MAX_SOURCE_BYTES, _open_safe_input, read_project_bytes, safe_project_input, static_dependencies,
)
from app.core.text_encoding import decode_latex_bytes


class CitationCancelled(Exception):
    pass


@dataclass(frozen=True)
class CitationRequest:
    key: object
    scope: Path
    root: Path
    buffers: tuple[tuple[Path, str], ...] = ()
    max_bytes: int = 32 * 1024 * 1024
    max_inputs: int = 2000
    max_items: int = 10000


@dataclass(frozen=True)
class CitationLocation:
    path: Path
    line: int


@dataclass(frozen=True)
class CitationItem:
    rule: str
    status: str
    key: str
    message: str
    locations: tuple[CitationLocation, ...]


@dataclass(frozen=True)
class CitationReport:
    key: object
    input_id: str
    items: tuple[CitationItem, ...]
    watched_paths: frozenset[Path]
    complete: bool
    stable: bool
    inputs: tuple[tuple[Path, str, str], ...]  # path, buffer/disk, SHA-256


def check_citations(request: CitationRequest, cancelled: Event | None = None) -> CitationReport:
    """Inspect declared static dependencies and captured buffers, never save/compile.

    The byte bound applies to unique input content. A second bounded read of disk
    inputs detects changes before accepting the report, not an immutable snapshot.
    """
    def check_cancel():
        if cancelled is not None and cancelled.is_set():
            raise CitationCancelled()

    check_cancel()
    scope = request.scope.resolve()
    root = safe_project_input(scope, request.root)
    if root is None:
        item = CitationItem("root_unknown", "unknown", "", "Compile root is not a safe project input", ())
        return CitationReport(request.key, "", (item,), frozenset(), False, False, ())
    buffers = dict(request.buffers)
    documents, failures, observations, sizes = {}, {}, {}, {}
    used_bytes = 0

    def load(path):
        nonlocal used_bytes
        check_cancel()
        if path in documents:
            return documents[path]
        if path in failures:
            raise failures[path]
        try:
            if len(documents) >= request.max_inputs:
                raise OSError("Input count limit exceeded")
            if safe_project_input(scope, path) is None:
                raise PermissionError("Unsafe input path")
            limit = min(MAX_SOURCE_BYTES, max(0, request.max_bytes - used_bytes))
            if path in buffers:
                text = buffers[path]
                if len(text) > limit:
                    raise OSError("Captured buffer exceeds the input byte limit")
                payload = text.encode("utf-8")
                if len(payload) > limit:
                    raise OSError("Captured buffer exceeds the input byte limit")
                kind = "buffer"
                used_bytes += len(payload)
            else:
                with _open_safe_input(scope, path) as stream:
                    if os.fstat(stream.fileno()).st_size > limit:
                        raise OSError("Disk input exceeds the input byte limit")
                    payload = stream.read(limit + 1)
                    used_bytes += len(payload)
                if len(payload) > limit:
                    raise OSError("Disk input grew beyond the input byte limit")
                text = decode_latex_bytes(payload).text
                kind = "disk"
            documents[path] = text
            sizes[path] = len(payload)
            observations[path] = (kind, hashlib.sha256(payload).hexdigest())
            return text
        except (OSError, UnicodeError) as exc:
            # Missing distribution styles/classes remain optional to the static
            # graph. Preserve FileNotFoundError; literal user inputs are checked
            # separately below and still receive an explicit unknown result.
            error = exc if isinstance(exc, OSError) else OSError(str(exc))
            failures[path] = error
            raise error

    items = []

    def add(rule, status, key, message, locations):
        items.append(CitationItem(rule, status, key, message, tuple(locations)))

    graph = static_dependencies(root, scope, max_inputs=request.max_inputs,
                                source_reader=lambda path: mask_tex_noncontent(load(path))[0],
                                max_references=request.max_items)
    complete = graph.complete
    if not graph.complete:
        add("dependency_unknown", "unknown", "", "Static dependency scan was unreadable or exceeded a bound",
            (CitationLocation(root, 1),))
    watched = {root}
    bib_paths = set()
    declarations = False
    for reference in graph.references:
        check_cancel()
        if reference.command not in {"input", "include", "subfile", "bibliography", "addbibresource"}:
            continue
        location = CitationLocation(reference.source, reference.line)
        if reference.command in {"bibliography", "addbibresource"}:
            declarations = True
        if reference.unresolved:
            complete = False
            add("dependency_unknown", "unknown", "", f"Unresolved {reference.command}: {reference.value}", (location,))
            continue
        available = []
        for path in reference.candidates:
            watched.add(path)
            try:
                load(path)
                available.append(path)
            except OSError:
                pass
        if not available:
            complete = False
            add("input_unreadable", "unknown", "", f"No readable input for {reference.command}: {reference.value}",
                (location, *[CitationLocation(path, 1) for path in reference.candidates]))
        elif len(available) > 1:
            complete = False
            add("dependency_unknown", "unknown", "", "Multiple static path candidates; engine search order is not evaluated",
                (location, *[CitationLocation(path, 1) for path in available]))
        if reference.command in {"input", "include", "subfile"} and any(
                path.suffix.lower() not in {".tex", ".ltx", ".sty", ".cls"} for path in available):
            complete = False
            add("dependency_unknown", "unknown", "", "Nonstandard source suffix is not recursively parsed", (location,))
        if reference.command in {"bibliography", "addbibresource"}:
            bib_paths.update(available)
    if root not in documents:
        complete = False
        add("input_unreadable", "unknown", "", str(failures.get(root, "Compile root could not be read")),
            (CitationLocation(root, 1),))
    if not declarations:
        # Preserve the app's optional conventional library, but identify its use
        # explicitly; declarations elsewhere are never replaced by this fallback.
        for path in (scope / "bib/references.bib", scope / "references.bib"):
            watched.add(path)
            try:
                load(path)
                bib_paths.add(path)
                add("library_fallback", "unknown", "", "Conventional library; no literal bibliography declaration was found",
                    (CitationLocation(path, 1),))
                complete = False
                break
            except OSError:
                pass
    definitions, uses, relations = {}, {}, {}
    include_all = False
    count = field_count = relation_count = 0
    for path, text in tuple(documents.items()):
        check_cancel()
        if path.suffix.lower() not in {".tex", ".ltx", ".sty", ".cls"}:
            continue
        scan = scan_citation_uses(text, max_items=max(0, request.max_items - count))
        count += len(scan.uses) + len(scan.issues)
        include_all |= scan.include_all
        complete &= scan.complete
        for issue in scan.issues:
            add("citation_unparsed", "unknown", "", issue.message, (CitationLocation(path, issue.line),))
        for use in scan.uses:
            uses.setdefault(use.key, []).append(CitationLocation(path, use.line))
    for path in sorted(bib_paths):
        check_cancel()
        scan = parse_bibliography(documents[path], max_items=max(0, request.max_items - max(count, field_count)))
        count += len(scan.entries)
        complete &= scan.complete
        for issue in scan.issues:
            add("bib_unparsed", "unknown", "", issue.message, (CitationLocation(path, issue.line),))
        for entry in scan.entries:
            field_count += len(entry.fields)
            location = CitationLocation(path, entry.line)
            definitions.setdefault(entry.key, []).append(location)
            for field, raw in entry.fields:
                if field == "ids":
                    complete = False
                    add("relation_unparsed", "unknown", entry.key, "BibLaTeX key aliases are not resolved", (location,))
                    continue
                if field not in {"crossref", "xref", "xdata", "related", "entryset"}:
                    continue
                literal = literal_bib_value(raw)
                if literal is None:
                    complete = False
                    add("relation_unparsed", "unknown", entry.key, f"Dynamic {field} is not expanded", (location,))
                    continue
                for key in (key.strip() for key in literal.split(",")):
                    if key:
                        if relation_count >= request.max_items:
                            complete = False
                            add("relation_unparsed", "unknown", entry.key, "Bibliography relation limit exceeded", (location,))
                            break
                        relation_count += 1
                        relations.setdefault(entry.key, []).append((key, location))
    if uses and not declarations and not bib_paths:
        complete = False
        add("dependency_unknown", "unknown", "", "No literal or conventional BibTeX library; manual/dynamic bibliography is not resolved",
            (CitationLocation(root, 1),))
    used = set(definitions) if include_all else set(uses)
    queue = list(used)
    while queue:
        check_cancel()
        current = queue.pop()
        for key, location in relations.get(current, ()):
            if key not in used:
                used.add(key)
                queue.append(key)
            if key not in definitions:
                add("relation_missing", "fail" if complete else "unknown", key,
                    f"No definition for the bibliography relation from {current}", (location,))
    for key, locations in sorted(uses.items()):
        if key not in definitions:
            add("citation_missing", "fail" if complete else "unknown", key,
                "No matching entry in the inspected bibliography inputs", locations)
    for key, locations in sorted(definitions.items()):
        if len(locations) > 1:
            add("key_duplicate", "fail" if complete else "unknown", key,
                "Multiple entry declarations share this key", locations)
        if key in used:
            add("entry_used", "info", key, "Direct, nocite or bibliography-relation use", (*locations, *uses.get(key, ())))
        elif complete:
            add("entry_unused", "suggestion", key, "No supported static use found; keep the entry unless the author chooses otherwise", locations)
        else:
            add("entry_usage_unknown", "unknown", key, "Usage coverage is incomplete; not classified as unused", locations)
    stable = True
    for path, (kind, digest) in observations.items():
        check_cancel()
        if kind == "disk":
            try:
                raw = read_project_bytes(path, scope, max_bytes=max(1, sizes[path]))
                stable &= hashlib.sha256(raw).hexdigest() == digest
            except OSError:
                stable = False
        else:
            stable &= safe_project_input(scope, path) is not None
    if not stable:
        complete = False
        add("inputs_changed", "unknown", "", "Inputs changed while checking; discard and refresh", ())
    digest = hashlib.sha256()
    for path, (kind, value) in sorted(observations.items()):
        digest.update((path.relative_to(scope).as_posix() + "\0" + kind + "\0" + value + "\0").encode())
    check_cancel()
    return CitationReport(request.key, digest.hexdigest(), tuple(items),
                          frozenset(watched | observations.keys()), bool(complete), bool(stable),
                          tuple((path, kind, value) for path, (kind, value) in sorted(observations.items())))
