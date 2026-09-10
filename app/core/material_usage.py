"""Bounded, read-only ordinary-source image usage and content observations.

Static source locations are not TeX execution counts. A same-content candidate
does not prove a move. No cache, baseline, source or asset is written here.
"""
from dataclasses import dataclass
import hashlib
from itertools import islice
import os
from pathlib import Path
import re
from threading import Event

from app.core.blocks.source_registry import (
    SourceCheckCancelled, SourceCheckLimits, _Budget, _candidate_files, _excluded, hash_file,
)
from app.core.citation_syntax import SyntaxIssue, _tex_group, mask_tex_noncontent
from app.core.image_assets import IMAGE_SUFFIXES
from app.core.project_dependencies import (
    MAX_SOURCE_BYTES, SOURCE_SUFFIXES, _open_safe_input, read_project_bytes,
    safe_project_input, static_dependencies,
)
from app.core.text_encoding import decode_latex_bytes


class MaterialCancelled(Exception):
    pass


@dataclass(frozen=True)
class MaterialBaseline:
    path: Path
    digest: str
    observed_at: str


@dataclass(frozen=True)
class MaterialRequest:
    key: object
    scope: Path
    root: Path
    buffers: tuple[tuple[Path, str], ...] = ()
    previous: tuple[MaterialBaseline, ...] = ()
    max_source_bytes: int = 32 * 1024 * 1024
    max_asset_bytes: int = 256 * 1024 * 1024
    max_asset_file_bytes: int = 64 * 1024 * 1024
    max_inputs: int = 2000
    max_scan_entries: int = 2000
    max_references: int = 10000


@dataclass(frozen=True)
class MaterialLocation:
    path: Path
    line: int


@dataclass(frozen=True)
class MaterialItem:
    rule: str
    status: str
    path: Path | None
    label: str
    message: str
    locations: tuple[MaterialLocation, ...] = ()
    candidates: tuple[Path, ...] = ()
    digest: str | None = None
    baseline: MaterialBaseline | None = None


@dataclass(frozen=True)
class MaterialReport:
    key: object
    input_id: str
    items: tuple[MaterialItem, ...]
    watched_paths: frozenset[Path]
    complete: bool
    stable: bool
    sources: tuple[tuple[Path, str, str], ...]  # source, buffer/disk, SHA-256
    assets: tuple[tuple[Path, str], ...]


_UNSUPPORTED_PATHS = re.compile(r"\\(?:epsfig|epsfbox|pdfximage|XeTeXpicfile|svgpath|"
                                r"DeclareGraphicsExtensions|DeclareGraphicsRule|import|subimport)\b")
_GRAPHICS_PATH = re.compile(r"\\graphicspath\s*")


def _path_syntax_issues(clean):
    for match in _UNSUPPORTED_PATHS.finditer(clean):
        yield SyntaxIssue(clean.count("\n", 0, match.start()) + 1, "Unsupported material/path command is not expanded")
    for match in _GRAPHICS_PATH.finditer(clean):
        try:
            pos = match.end()
            if pos >= len(clean) or clean[pos] != "{":
                raise ValueError()
            end = _tex_group(clean, pos)
            pos += 1
            while pos < end - 1:
                if clean[pos].isspace():
                    pos += 1
                    continue
                if clean[pos] != "{":
                    raise ValueError()
                stop = _tex_group(clean, pos)
                if any(char in clean[pos + 1:stop - 1] for char in "\\#$%{}~\x00"):
                    raise ValueError()
                pos = stop
        except ValueError:
            yield SyntaxIssue(clean.count("\n", 0, match.start()) + 1, "Dynamic or malformed graphicspath is not resolved")


def check_materials(request: MaterialRequest, cancelled: Event | None = None) -> MaterialReport:
    try:
        return _check_materials(request, cancelled)
    except SourceCheckCancelled as exc:
        raise MaterialCancelled() from exc


def _check_materials(request, cancelled):
    def check_cancel():
        if cancelled is not None and cancelled.is_set():
            raise MaterialCancelled()

    check_cancel()
    scope = request.scope.resolve()
    root = safe_project_input(scope, request.root)
    if root is None:
        return MaterialReport(request.key, "", (MaterialItem("source_unknown", "unknown", None, "",
            "Compile root is outside the safe project inputs"),), frozenset(), False, False, (), ())
    buffers = dict(request.buffers)
    texts, failures, sources, sizes = {}, {}, {}, {}
    issues, used_source_bytes = [], 0
    items, watched = [], {root}
    complete = True

    def add(rule, status, path, label, message, locations=(), candidates=(), digest=None, baseline=None):
        items.append(MaterialItem(rule, status, path, label, message, tuple(locations), tuple(candidates), digest, baseline))

    def read_source(path):
        nonlocal used_source_bytes
        check_cancel()
        if path in texts:
            return texts[path]
        if path in failures:
            raise failures[path]
        try:
            if len(texts) >= request.max_inputs:
                raise OSError("Source input count limit exceeded")
            if safe_project_input(scope, path) is None:
                raise OSError("Source path is unsafe")
            limit = min(MAX_SOURCE_BYTES, max(0, request.max_source_bytes - used_source_bytes))
            if path in buffers:
                text = buffers[path]
                if len(text) > limit:
                    raise OSError("Captured source exceeds the byte limit")
                raw = text.encode("utf-8")
                if len(raw) > limit:
                    raise OSError("Captured source exceeds the byte limit")
                used_source_bytes += len(raw)
                kind = "buffer"
            else:
                with _open_safe_input(scope, path) as stream:
                    if os.fstat(stream.fileno()).st_size > limit:
                        raise OSError("Source input exceeds the byte limit")
                    raw = stream.read(limit + 1)
                    used_source_bytes += len(raw)
                if len(raw) > limit:
                    raise OSError("Source grew beyond the byte limit")
                text = decode_latex_bytes(raw).text
                kind = "disk"
            clean, parse_issues = mask_tex_noncontent(text, max_items=max(1, request.max_references - len(issues)))
            issues.extend((path, issue) for issue in parse_issues)
            for issue in _path_syntax_issues(clean):
                issues.append((path, issue))
                if len(issues) >= request.max_references:
                    break
            texts[path] = clean
            sources[path] = (kind, hashlib.sha256(raw).hexdigest())
            sizes[path] = len(raw)
            return clean
        except (OSError, UnicodeError) as exc:
            error = exc if isinstance(exc, OSError) else OSError(str(exc))
            failures[path] = error
            raise error

    graph = static_dependencies(root, scope, source_reader=read_source,
                                max_inputs=request.max_inputs, max_references=request.max_references)
    watched.update(graph.paths)
    complete = graph.complete and not issues and root in sources
    if sum(sum(1 for _ in islice(_GRAPHICS_PATH.finditer(text), 2)) for text in texts.values()) > 1:
        complete = False
        add("source_unknown", "unknown", None, "", "Multiple graphicspath scopes are not evaluated",
            (MaterialLocation(root, 1),))
    if not graph.complete or root not in sources:
        add("source_unknown", "unknown", None, "", "Source scan was unreadable or exceeded a limit",
            (MaterialLocation(root, 1),))
    for path, issue in issues:
        add("source_unknown", "unknown", None, "", issue.message, (MaterialLocation(path, issue.line),))

    asset_limits = SourceCheckLimits(max_file_bytes=request.max_asset_file_bytes,
        max_total_bytes=request.max_asset_bytes, max_entries=request.max_scan_entries, max_records=request.max_inputs)
    budget = _Budget(asset_limits, lambda: cancelled is not None and cancelled.is_set())
    assets, asset_errors, absent = {}, {}, set()

    def read_asset(path):
        if path in assets:
            return assets[path]
        if path in asset_errors:
            raise asset_errors[path]
        if path in absent:
            raise FileNotFoundError(path)
        try:
            if len(assets) >= request.max_inputs:
                raise OSError("Asset count limit exceeded")
            if safe_project_input(scope, path) is None or _excluded(path.relative_to(scope).parts):
                raise OSError("Asset path is linked, hidden or internal")
            if path.suffix.lower() not in IMAGE_SUFFIXES:
                raise OSError("Asset format is outside the supported image inventory")
            assets[path] = hash_file(path, project_dir=scope, _budget=budget)
            return assets[path]
        except FileNotFoundError:
            absent.add(path)
            raise
        except OSError as exc:
            asset_errors[path] = exc
            raise

    uses = {}
    missing_refs = []
    for reference in graph.references:
        check_cancel()
        location = MaterialLocation(reference.source, reference.line)
        if reference.command not in {"input", "include", "subfile", "includegraphics", "includesvg", "includepdf"}:
            continue
        if reference.unresolved or reference.rejected_candidates:
            complete = False
            add("source_unknown", "unknown", None, reference.value,
                "Dynamic, excluded or unsafe path candidate; complete resolution is not established", (location,))
            if reference.unresolved:
                continue
        if reference.command not in {"includegraphics", "includesvg", "includepdf"}:
            found = [path for path in reference.candidates if path in sources]
            unparsed_existing = False
            for path in reference.candidates:
                if path.suffix.lower() not in SOURCE_SUFFIXES:
                    try:
                        path.lstat()
                        unparsed_existing = True
                    except FileNotFoundError:
                        pass
                    except OSError:
                        unparsed_existing = True
            if len(found) != 1 or unparsed_existing:
                complete = False
                add("source_unknown", "unknown", None, reference.value,
                    "Source input is absent, unreadable, ambiguous or has an unsupported suffix", (location,))
            continue
        available, errors = [], []
        for path in reference.candidates:
            try:
                read_asset(path)
                available.append(path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                errors.append(str(exc))
        if errors:
            complete = False
            add("asset_unknown", "unknown", None, reference.value, "; ".join(dict.fromkeys(errors)), (location,))
        if len(available) > 1:
            complete = False
            add("asset_ambiguous", "unknown", None, reference.value,
                "Multiple readable path/extension candidates; engine search order is not evaluated", (location,), available)
        elif len(available) == 1:
            uses.setdefault(available[0], []).append(location)
        elif not errors:
            missing_refs.append((reference, location))

    inventory_complete = True
    try:
        for path in _candidate_files(scope, budget, IMAGE_SUFFIXES):
            watched.add(path)
            try:
                read_asset(path)
            except OSError as exc:
                inventory_complete = False
                add("asset_unknown", "unknown", path, path.relative_to(scope).as_posix(), str(exc))
    except OSError as exc:
        inventory_complete = False
        add("asset_unknown", "unknown", None, "", f"Inventory enumeration incomplete: {exc}")
    complete &= inventory_complete
    previous = {base.path: base for base in request.previous[:request.max_inputs]
                if safe_project_input(scope, base.path) is not None and len(base.digest) == 64}
    for reference, location in missing_refs:
        check_cancel()
        baselines = [previous[path] for path in reference.candidates if path in previous]
        baseline = baselines[0] if len(baselines) == 1 else None
        candidates = tuple(sorted(path for path, digest in assets.items() if baseline
                                 and path.suffix.lower() == baseline.path.suffix.lower() and digest == baseline.digest))
        rule, status = ("asset_missing", "fail") if complete else ("asset_unknown", "unknown")
        message = "No readable file at the supported literal reference paths"
        if len(baselines) > 1 or len(candidates) > 1:
            rule, status = "asset_ambiguous", "unknown"
            message = "Multiple prior identities or same-content candidates; no move is inferred"
        elif candidates and inventory_complete:
            rule, status = "asset_candidate", "warning"
            message = "One same-content candidate for a previously observed path; not proof of a move"
        add(rule, status, baseline.path if baseline else None, reference.value, message,
            (location,), candidates, baseline=baseline)
    for path, digest in sorted(assets.items()):
        check_cancel()
        locations = tuple(dict.fromkeys(uses.get(path, ())))
        baseline = previous.get(path)
        if baseline and baseline.digest != digest:
            rule, status, message = "asset_changed", "warning", "Content differs from the previous readable observation"
        elif locations:
            rule, status, message = "asset_present", "info", "Readable asset with supported static source locations"
        elif complete:
            rule, status, message = "asset_unused", "suggestion", "No supported static use under this root; never delete automatically"
        else:
            rule, status, message = "usage_unknown", "unknown", "Static coverage is incomplete; not classified as unused"
        add(rule, status, path, path.relative_to(scope).as_posix(), message, locations,
            digest=digest, baseline=baseline)

    stable = True
    for path, (kind, digest) in sources.items():
        check_cancel()
        try:
            stable &= (hashlib.sha256(read_project_bytes(path, scope, max_bytes=max(1, sizes[path]))).hexdigest() == digest
                       if kind == "disk" else safe_project_input(scope, path) is not None)
        except OSError:
            stable = False
    verification_budget = _Budget(asset_limits, budget.cancelled)
    for path, digest in assets.items():
        try:
            stable &= hash_file(path, project_dir=scope, _budget=verification_budget) == digest
        except OSError:
            stable = False
    for path in absent:
        check_cancel()
        try:
            path.lstat()
        except FileNotFoundError:
            pass
        except OSError:
            stable = False
        else:
            stable = False
    if not stable:
        complete = False
        add("inputs_changed", "unknown", None, "", "Inputs changed while checking; discard and refresh")
    identity = hashlib.sha256()
    records = [(path, kind, digest) for path, (kind, digest) in sources.items()]
    records.extend((path, "asset", digest) for path, digest in assets.items())
    records.extend((path, "absent", "") for path in absent)
    for path, kind, digest in sorted(records):
        identity.update((path.relative_to(scope).as_posix() + "\0" + kind + "\0" + digest + "\0").encode())
    check_cancel()
    return MaterialReport(request.key, identity.hexdigest(), tuple(items), frozenset(watched),
                          bool(complete), bool(stable),
                          tuple((path, kind, digest) for path, (kind, digest) in sorted(sources.items())),
                          tuple(sorted(assets.items())))
