"""Freeze reviewed saved inputs and publish only explicit local submission outputs.

The caller owns live GUI/buffer identity and cancellation while this worker runs.
This module never saves, compiles, applies drafts, uploads or opens a project.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
from itertools import islice
import json
from pathlib import Path
from threading import Event

from app import __version__
from app.core.blocks.project_write import PENDING_PATH
from app.core.project_checkpoint import (
    MAX_FILES, MAX_TOTAL_BYTES, _METADATA, _cancel, _check_signature, _read_file,
    _relative, _validate_paths, _publish_payloads, checkpoint_candidates,
)
from app.core.project_dependencies import safe_project_input
from app.core.project_profile import load_profile
from app.core.submission_check import CheckRequest, CheckReport, CheckStatus, check_submission

# Conservative file selection, not a general secret detector. No unselected file
# is exported, even if its suffix looks safe. Known private names are refused.
_PRIVATE_NAMES = frozenset({"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials",
                            "token", "tokens", "secret", "secrets", "api_key", "api-key",
                            "access_token", "access-token", "auth_token", "auth-token"})
_PRIVATE_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"})
_SOURCE_SUFFIXES = frozenset({".tex", ".ltx", ".sty", ".cls", ".bst", ".bib", ".png",
    ".jpg", ".jpeg", ".pdf", ".eps", ".svg", ".csv", ".tsv", ".xlsx", ".txt", ".md", ".json",
    ".ttf", ".otf", ".woff", ".woff2"})
_REQUIRED_RULES = frozenset({"root", "saved", "toolchain", "final_build", "pdf_current", "word_count"})


@dataclass(frozen=True)
class DeliveryOptions:
    include_source: bool = False
    include_report: bool = False
    source_paths: tuple[str, ...] = ()
    pdf_name: str = "submission.pdf"


@dataclass(frozen=True)
class FrozenInput:
    path: str
    payload: bytes | None
    observation: tuple | None


@dataclass(frozen=True)
class PreparedSubmission:
    request: CheckRequest
    options: DeliveryOptions
    report: CheckReport
    inputs: tuple[FrozenInput, ...]
    project_identity: tuple[int, int]
    profile_digest: str | None
    word_target: tuple[int | None, int | None] | None
    pdf_relative: str

    @property
    def unconfirmed(self):
        return tuple(item for item in self.report.items
                     if item.status not in {CheckStatus.PASS, CheckStatus.NOT_APPLICABLE})


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def source_path_allowed(relative, *, suffixes=_SOURCE_SUFFIXES):
    try:
        _relative(relative)
    except ValueError:
        return False
    if relative in _METADATA:
        return True  # Explicit known project metadata, never personal history.
    path = Path(relative)
    return (not any(part.startswith(".") or Path(part).stem.casefold() in _PRIVATE_NAMES for part in path.parts)
            and path.suffix.casefold() in suffixes
            and path.suffix.casefold() not in _PRIVATE_SUFFIXES)


def submission_source_candidates(project, *, cancelled=None):
    paths, warnings = checkpoint_candidates(project, cancelled=cancelled,
        extensions=_SOURCE_SUFFIXES)
    allowed = tuple(p for p in paths if source_path_allowed(p))
    return allowed, (*warnings,
        "Only explicitly selected files are exported; known Block/profile metadata may be selected, never history or drafts.",
        "Selected metadata keeps original local references; review its contents before sharing.",
        "Name filtering is not proof that selected document contents contain no private information.")


def _options(options):
    if type(options.include_source) is not bool or type(options.include_report) is not bool:
        raise ValueError("Delivery choices must be explicit booleans")
    name = _relative(options.pdf_name)
    if "/" in name or Path(name).suffix.lower() != ".pdf":
        raise ValueError("Choose one portable PDF filename, not a path")
    paths = tuple(islice(options.source_paths, MAX_FILES + 1))
    if not options.include_source and paths:
        raise ValueError("Source paths require the separate source-package choice")
    if options.include_source and not 1 <= len(paths) <= MAX_FILES:
        raise ValueError("Review and select 1-2000 source files")
    _validate_paths(paths)
    if any(not source_path_allowed(p) for p in paths):
        raise ValueError("Private, generated, unsupported or unsafe source-package path")
    if tuple(options.source_paths) != paths:
        raise ValueError("Source selection exceeds its bound")
    return paths


def _count_identity(count):
    # TeXcount details can contain its disposable shadow directory. Bind the
    # actual mode/counts/warnings, not a different temp pathname on each pass.
    if count is None:
        return None
    return tuple(getattr(count, name) for name in (
        "source", "total_words", "effective_words", "header_words", "caption_words",
        "math_inline", "math_display", "numbers", "warnings"))


def _no_pending_write(scope):
    marker = scope / PENDING_PATH
    if safe_project_input(scope, marker, allow_internal=True) != marker:
        raise ValueError("Project write-journal path is unsafe")
    try:
        marker.lstat()
    except FileNotFoundError:
        return
    raise ValueError("Unresolved Block write journal; review recovery before preparing delivery")


def _report(request, cancelled):
    _no_pending_write(request.scope)
    report = check_submission(request, cancelled)
    states = {item.rule_id: item.status for item in report.items}
    if not report.stable or any(states.get(rule) is not CheckStatus.PASS for rule in _REQUIRED_RULES):
        raise ValueError("Saved inputs and a current successful FINAL/PDF must be verified before delivery")
    if request.block and states.get("block_generated") is not CheckStatus.PASS:
        raise ValueError("Block generated source is not verified against the saved model")
    if states.get("project_profile") not in {CheckStatus.PASS, CheckStatus.NOT_APPLICABLE}:
        raise ValueError("Project profile is unknown or unstable")
    return report


def prepare_submission(request, options=DeliveryOptions(), *, cancelled: Event | None = None,
                       expected=None):
    """Bind M1 evidence to bounded raw bytes, including absent dependencies.

    Every selected source, metadata/profile observation and the actual FINAL PDF
    is read again. The second M1 check must still identify the same input/report.
    The optional expected value binds a later publication to the review.
    """
    stop = cancelled.is_set if cancelled is not None else None
    _cancel(stop)
    paths = _options(options)
    if request.scope is None or request.root is None:
        raise ValueError("Choose a local saved project and compile root")
    scope, root = request.scope, request.root
    if scope != scope.resolve(strict=True) or root != safe_project_input(scope, root):
        raise ValueError("Project/root must be canonical and link-free")
    initial = scope.stat()
    identity = (initial.st_dev, initial.st_ino)
    report = _report(request, cancelled)
    proof = request.build_evidence
    pdf = proof.pdf_file
    if (safe_project_input(scope, pdf, allow_internal=True) != pdf
            or ".icstex" in pdf.relative_to(scope).parts
            or proof.job_key.output_dir != pdf.parent):
        raise ValueError("Only the recorded canonical FINAL PDF can be delivered")
    relative_pdf = pdf.relative_to(scope).as_posix()
    profile = load_profile(scope)
    required = {path.relative_to(scope).as_posix() for path, observation in proof.inputs.observations
                if observation.digest is not None}
    if options.include_source and not required.issubset(paths):
        raise ValueError("Source selection omits known build inputs: " + ", ".join(sorted(required - set(paths))))
    watched = set(report.watched_paths) | {scope / p for p in paths} | {pdf}
    if len(watched) > MAX_FILES:
        raise ValueError("Delivery inputs exceed 2000 files")
    captured, total = [], 0
    for path in sorted(watched):
        _cancel(stop)
        if safe_project_input(scope, path, allow_internal=True) != path:
            raise ValueError("Delivery input is outside its project or contains a link")
        relative = path.relative_to(scope).as_posix()
        if path != pdf:
            _relative(relative)
        try:
            payload, observed = _read_file(scope, relative, stop)
        except FileNotFoundError:
            payload = observed = None
        if relative in paths and payload is None:
            raise ValueError("Selected source file is missing: " + relative)
        if payload is not None:
            total += len(payload)
            if total > MAX_TOTAL_BYTES:
                raise ValueError("Captured delivery inputs exceed 256 MiB")
            if relative in paths and b"PRIVATE KEY-----" in payload:
                raise ValueError("Selected file contains a private-key marker; not exported")
        captured.append(FrozenInput(relative, payload, observed))
    inputs = tuple(captured)
    actual_pdf = next(value.payload for value in inputs if value.path == relative_pdf)
    if actual_pdf is None or _sha(actual_pdf) != proof.inputs.pdf.digest:
        raise ValueError("FINAL PDF changed during capture")
    for value in inputs:
        _cancel(stop)
        if value.payload is None:
            try:
                _read_file(scope, value.path, stop)
            except FileNotFoundError:
                continue
            raise OSError("Previously absent input appeared during capture")
        payload, observed = _read_file(scope, value.path, stop)
        if payload != value.payload or observed != value.observation:
            raise OSError("Input changed during delivery capture: " + value.path)
    current = _report(request, cancelled)
    if (current.input_id != report.input_id or current.items != report.items
            or _count_identity(current.word_count) != _count_identity(report.word_count) or load_profile(scope) != profile):
        raise OSError("Check, profile or count evidence changed during capture")
    for value in inputs:
        _cancel(stop)
        if value.payload is not None:
            _check_signature(scope, value.path, value.observation)
        else:
            path = scope / value.path
            if safe_project_input(scope, path, allow_internal=True) != path:
                raise OSError("Absent input path changed before acceptance")
            try:
                path.lstat()
            except FileNotFoundError:
                pass
            else:
                raise OSError("Previously absent input appeared before acceptance")
    now = scope.stat()
    if (now.st_dev, now.st_ino) != identity:
        raise OSError("Project directory changed during capture")
    _no_pending_write(scope)
    target = profile.profile.word_target if profile.profile else request.word_target
    prepared = PreparedSubmission(request, options, report, inputs, identity, profile.digest, target, relative_pdf)
    if expected is not None and (
            prepared.request != expected.request or prepared.options != expected.options
            or prepared.report.input_id != expected.report.input_id
            or prepared.report.items != expected.report.items
            or _count_identity(prepared.report.word_count) != _count_identity(expected.report.word_count)
            or prepared.inputs != expected.inputs or prepared.project_identity != expected.project_identity
            or prepared.profile_digest != expected.profile_digest or prepared.word_target != expected.word_target
            or prepared.pdf_relative != expected.pdf_relative):
        raise OSError("Submission changed after review; previous delivery is untouched")
    return prepared


def delivery_report(prepared, payloads):
    """Allowlisted evidence; no absolute user paths or copied diagnostic text."""
    request, report = prepared.request, prepared.report
    proof = request.build_evidence
    def location(path):
        return path.relative_to(request.scope).as_posix() if path and path.is_relative_to(request.scope) else None
    count = report.word_count
    versions = proof.tool_versions
    def version_row(observed):
        return ({"program": observed.program, "version": observed.version,
                 "distribution": observed.distribution} if observed is not None else None)
    value = {
        "format": "icstex-reviewed-delivery", "version": 1, "application_version": __version__,
        "root": location(request.root), "input_id": report.input_id, "checked_at": report.checked_at,
        "engine": request.engine.value, "build_id": proof.build_id,
        "source_revision": proof.job_key.source_revision, "purpose": proof.job_key.purpose.value,
        "toolchain": {f.name: {"executable": Path(path).name, "version": None}
                      for f in fields(request.tools) if (path := getattr(request.tools, f.name))},
        "toolchain_status": "Configured executable names only; not proof these binaries ran",
        "build_tool_versions": {
            "source": "actual_final_stdout_startup_banners" if versions is not None else None,
            "driver": version_row(versions.driver) if versions is not None else None,
            "engine": version_row(versions.engine) if versions is not None else None,
            "capture_truncated": versions.truncated if versions is not None else None,
        },
        "tool_version_status": "Self-reported startup labels only; missing labels and auxiliary tool versions are unknown",
        "profile_sha256": prepared.profile_digest,
        "word_count": {"mode": count.source, "effective_words": count.effective_words,
                       "total_words": count.total_words},
        "word_target": prepared.word_target,
        "inputs": [{"path": f.path, "sha256": _sha(f.payload) if f.payload is not None else None,
                    "size": len(f.payload) if f.payload is not None else None} for f in prepared.inputs],
        "outputs": [{"path": p, "sha256": _sha(b), "size": len(b)} for p, b in payloads],
        "checks": [{"rule": item.rule_id, "status": item.status.value, "path": location(item.file),
                    "line": item.line} for item in report.items],
        "limits": ["Local static/recorded dependencies only; unknown checks are not passes",
                   "Build stdout is not authenticated binary identity; configured paths do not identify driver child binaries",
                   "No academic certification, cloud completeness or cross-environment layout guarantee",
                   "System fonts and TeX distribution packages are external dependencies; not bundled"],
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")


def delivery_payloads(prepared):
    """Exact reviewed output bytes, shared by the preview and publication worker."""
    fresh = prepared
    values = {item.path: item.payload for item in fresh.inputs}
    payloads = [(fresh.options.pdf_name, values[fresh.pdf_relative])]
    if fresh.options.include_source:
        payloads.extend(("source/" + path, values[path]) for path in fresh.options.source_paths)
        payloads.append(("SOURCE_README.txt", (
            "Selected original source bytes are in source/. User README/manifest files are preserved there.\n"
            f"Entry: source/{fresh.request.root.relative_to(fresh.request.scope).as_posix()}\n"
            f"Selected engine: {fresh.request.engine.value}\n"
            "Use your own local TeX distribution and the recorded engine; required system fonts/packages\n"
            "are not bundled. Run with project hooks disabled and shell escape disabled.\n"
            "This selection is not a complete archive of the original project or its independent drafts.\n"
        ).encode()))
    if fresh.options.include_report:
        payloads.append(("submission-report.json", delivery_report(prepared, payloads)))
    # Source paths were validated before prefixing them with the disjoint source/
    # namespace. Revalidating that prefix as a project path would wrongly exclude
    # explicitly selected .icstex/blocks.json while not adding any path safety.
    _validate_paths([path for path, _ in payloads if not path.startswith("source/")])
    if sum(len(raw) for _, raw in payloads) > MAX_TOTAL_BYTES:
        raise ValueError("Delivery exceeds 256 MiB")
    return tuple(payloads)


def publish_submission(prepared, target, *, accept_unconfirmed=False, cancelled: Event | None = None):
    """Publish a new directory only, after a fresh capture matches the review."""
    if prepared.unconfirmed and accept_unconfirmed is not True:
        raise ValueError("Review and explicitly acknowledge unconfirmed checks before delivery")
    stop = cancelled.is_set if cancelled is not None else None
    prepare_submission(prepared.request, prepared.options, cancelled=cancelled, expected=prepared)
    destination = Path(target).expanduser().absolute()
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.is_relative_to(prepared.request.scope):
        raise ValueError("Choose a new delivery directory outside the source project")
    payloads = delivery_payloads(prepared)
    def recheck():
        prepare_submission(prepared.request, prepared.options, cancelled=cancelled, expected=prepared)
    return _publish_payloads(destination, payloads, cancelled=stop, check_source=recheck,
                             prefix=".icstex-delivery.incomplete-")
