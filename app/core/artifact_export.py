"""Frozen disk inputs and no-overwrite publication for existing Agent exports.

This is not the GUI's reviewed submission workflow or authority to read buffers,
apply Block drafts, compile, upload, or expand the MCP protocol.
"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import hashlib
from itertools import islice
import os
from pathlib import Path
import stat
import uuid

from app.core.build_evidence import capture_compile_inputs
from app.core.compiler import BuildPurpose, CompileOutcome
from app.core.project_checkpoint import (
    MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES, _METADATA, _OutputParent,
    _cancel, _read_file, _signature,
)
from app.core.project_dependencies import observe_input, safe_project_input
from app.core.submission_delivery import _no_pending_write


EXPORT_CONTEXT_PATHS = tuple(sorted(_METADATA | {
    "icstex.project.json", "styles/document-theme.json",
}))


@dataclass(frozen=True)
class ExportInput:
    path: str
    payload: bytes | None
    signature: tuple | None


@dataclass(frozen=True)
class ExportInputs:
    project: Path
    identity: tuple[int, int]
    files: tuple[ExportInput, ...]


def _project_identity(project):
    info = project.lstat()
    if (not stat.S_ISDIR(info.st_mode) or project.resolve(strict=True) != project
            or (hasattr(project, "is_junction") and project.is_junction())):
        raise OSError("Export project identity is unsafe")
    return info.st_dev, info.st_ino


def capture_export_inputs(project, paths, *, cancelled=None):
    """Capture only caller-selected, bounded paths, including absent observations."""
    project = Path(project)
    identity = _project_identity(project)
    _no_pending_write(project)
    selected = tuple(islice(paths, MAX_FILES + 1))
    if len(selected) > MAX_FILES or len(set(selected)) != len(selected):
        raise ValueError("Export input selection is duplicate or exceeds 2000 files")
    files, total = [], 0
    for relative in sorted(selected):
        _cancel(cancelled)
        path = project / relative
        if (not isinstance(relative, str) or len(relative.encode()) > 4096
                or safe_project_input(project, path, allow_internal=True) != path):
            raise ValueError("Export input path is unsafe")
        try:
            payload, signature = _read_file(project, relative, cancelled)
        except FileNotFoundError:
            payload = signature = None
        if payload is not None:
            total += len(payload)
            if total > MAX_TOTAL_BYTES:
                raise ValueError("Export inputs exceed 256 MiB")
        files.append(ExportInput(relative, payload, signature))
    captured = ExportInputs(project, identity, tuple(files))
    recheck_export_inputs(captured, cancelled=cancelled)
    return captured


def recheck_export_inputs(captured, *, cancelled=None):
    project = captured.project
    if _project_identity(project) != captured.identity:
        raise OSError("Export project changed")
    _no_pending_write(project)
    for entry in captured.files:
        _cancel(cancelled)
        path = project / entry.path
        if safe_project_input(project, path, allow_internal=True) != path:
            raise OSError("Export input path changed")
        try:
            payload, signature = _read_file(project, entry.path, cancelled)
        except FileNotFoundError:
            payload = signature = None
        if (payload, signature) != (entry.payload, entry.signature):
            raise OSError("Export input changed: " + entry.path)
    if _project_identity(project) != captured.identity:
        raise OSError("Export project changed during verification")
    _no_pending_write(project)


def current_final_pdf(result, context, *, cancelled=None):
    """Revalidate a real result, never manufacture freshness from a wire dict."""
    _cancel(cancelled)
    recheck_export_inputs(context, cancelled=cancelled)
    project = context.project
    key, evidence = result.job_key, result.input_evidence
    if (result.purpose is not BuildPurpose.FINAL or result.outcome is not CompileOutcome.SUCCESS
            or key is None or key.purpose is not BuildPurpose.FINAL
            or key.root_file != result.root_file or key.output_dir != result.output_dir
            or safe_project_input(project, result.root_file) != result.root_file
            or result.pdf_file != result.output_dir / (result.root_file.stem + ".pdf")
            or safe_project_input(project, result.pdf_file, allow_internal=True) != result.pdf_file
            or ".icstex" in result.pdf_file.relative_to(project).parts
            or evidence is None or not evidence.stable or evidence.pdf is None
            or not evidence.pdf.stable or not evidence.pdf.digest):
        raise ValueError("A successful current FINAL with actual input/PDF evidence is required")
    extras = tuple(path for path, _ in evidence.observations)

    def check_build():
        _cancel(cancelled)
        current = capture_compile_inputs(result.root_file, project, extras)
        if not current.complete or current.observations != evidence.observations:
            raise OSError("FINAL inputs changed before export")
        if observe_input(result.pdf_file, project, allow_internal=True) != evidence.pdf:
            raise OSError("FINAL PDF changed before export")

    check_build()
    payload, _ = _read_file(project, result.pdf_file.relative_to(project).as_posix(), cancelled)
    if not payload or hashlib.sha256(payload).hexdigest() != evidence.pdf.digest:
        raise OSError("FINAL PDF bytes do not match the recorded build")
    check_build()
    recheck_export_inputs(context, cancelled=cancelled)
    return payload


def publish_exact_file(target, payload, *, check_source, cancelled=None,
                       publication_guard=nullcontext):
    """Stage/read back exact bytes, then publish exclusively; never os.replace."""
    if not payload or len(payload) > MAX_FILE_BYTES:
        raise ValueError("Export file must contain 1 byte to 64 MiB")
    _cancel(cancelled)
    with _OutputParent(target) as parent:
        name = ".icstex-export.incomplete-" + uuid.uuid4().hex
        descriptor = parent.create_file(name)
        initial = os.fstat(descriptor)
        owned = initial.st_dev, initial.st_ino
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
                signature = _signature(os.fstat(stream.fileno()))
            observed, current = _read_file(parent.path, name, cancelled)
            if observed != payload or current != signature:
                raise OSError("Staged PDF changed before publication")
            check_source()
            _cancel(cancelled)
            with publication_guard():
                parent.publish_file(name, signature)
            actual, _ = _read_file(parent.path, parent.target.name, cancelled=None)
            if actual != payload:
                raise OSError("Published PDF changed; output exists but is not accepted")
            return parent.target
        finally:
            parent.remove_file(name, owned)
