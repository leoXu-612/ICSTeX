"""Frozen inputs, new exports and explicitly remembered ordinary PDF replacements.

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

from app.core.build_evidence import FinalBuildEvidence, capture_compile_inputs, final_build_evidence
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


@dataclass(frozen=True)
class ExportedPdf:
    """Last bytes and filesystem identity we published, not authority over any other PDF."""
    target: Path
    digest: str
    signature: tuple[int, ...]
    parent_identity: tuple[int, int]


def exported_pdf(target: Path, payload: bytes) -> ExportedPdf:
    """Enroll only the exact successfully published bytes; never adopt external changes."""
    data, signature = _read_file(target.parent, target.name)
    if data != payload:
        raise OSError("Exported PDF changed before remembering its destination")
    return ExportedPdf(target, hashlib.sha256(data).hexdigest(), signature,
                       _project_identity(target.parent))


def pdf_export_destination(target: Path, proof: FinalBuildEvidence) -> Path:
    """Resolve only the output parent, matching publication; never replace a build input."""
    target = target.parent.resolve(strict=True) / target.name
    if (target == proof.pdf_file or any(target == path for path, _ in proof.inputs.observations)
            or any(part in {".icstex", ".latex_build", ".git"} for part in target.parts)):
        raise ValueError("Export destination is a build output, input or internal record")
    return target


class _RememberedPdfParent(_OutputParent):
    """Opt-in exception to exclusive publication, only for our unchanged previous export."""
    def __init__(self, target, previous):
        super().__init__(target)
        self.previous = previous

    def absent(self):
        previous = self.previous
        if self.target != previous.target or self.identity != previous.parent_identity:
            raise OSError("Export destination directory changed")
        data, signature = _read_file(self.path, self.target.name)
        if signature != previous.signature or hashlib.sha256(data).hexdigest() != previous.digest:
            raise OSError("Export destination was changed outside ICSTeX")

    def publish_file(self, name, expected):
        self.check()
        self.check_owned(name, expected)
        self.absent()  # Recheck after staging/source validation, immediately before replacement.
        kwargs = {"src_dir_fd": self.fd, "dst_dir_fd": self.fd} if self.fd is not None else {}
        os.replace(self.name(name), self.name(self.target.name), **kwargs)


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
    key = result.job_key
    if (result.purpose is not BuildPurpose.FINAL or result.outcome is not CompileOutcome.SUCCESS
            or key is None or key.purpose is not BuildPurpose.FINAL
            or key.root_file != result.root_file or key.output_dir != result.output_dir):
        raise ValueError("A successful current FINAL with actual input/PDF evidence is required")
    proof = final_build_evidence(result)
    assert proof is not None
    return verified_final_pdf(proof, context, cancelled=cancelled)


def verified_final_pdf(proof: FinalBuildEvidence, context, *, cancelled=None):
    """Read exact FINAL bytes from the immutable evidence retained by GUI and Agent callers."""
    _cancel(cancelled)
    recheck_export_inputs(context, cancelled=cancelled)
    project = context.project
    key, evidence = proof.job_key, proof.inputs
    if (proof.outcome is not CompileOutcome.SUCCESS or key.purpose is not BuildPurpose.FINAL
            or safe_project_input(project, key.root_file) != key.root_file
            or proof.pdf_file != key.output_dir / (key.root_file.stem + ".pdf")
            or safe_project_input(project, proof.pdf_file, allow_internal=True) != proof.pdf_file
            or ".icstex" in proof.pdf_file.relative_to(project).parts
            or evidence is None or not evidence.stable or evidence.pdf is None
            or not evidence.pdf.stable or not evidence.pdf.digest):
        raise ValueError("A successful current FINAL with actual input/PDF evidence is required")
    extras = tuple(path for path, _ in evidence.observations)

    def check_build():
        _cancel(cancelled)
        current = capture_compile_inputs(key.root_file, project, extras)
        if not current.complete or current.observations != evidence.observations:
            raise OSError("FINAL inputs changed before export")
        if observe_input(proof.pdf_file, project, allow_internal=True) != evidence.pdf:
            raise OSError("FINAL PDF changed before export")

    check_build()
    payload, _ = _read_file(project, proof.pdf_file.relative_to(project).as_posix(), cancelled)
    if not payload or hashlib.sha256(payload).hexdigest() != evidence.pdf.digest:
        raise OSError("FINAL PDF bytes do not match the recorded build")
    check_build()
    recheck_export_inputs(context, cancelled=cancelled)
    return payload


def publish_exact_file(target, payload, *, check_source, cancelled=None,
                       publication_guard=nullcontext, previous: ExportedPdf | None = None):
    """Publish exclusively by default; replace only an explicitly remembered export.

    Replacement stages in the same directory and checks the prior identity/bytes again
    immediately before os.replace, like conflict-aware source saving. This is not a
    filesystem compare-and-swap against an uncooperative concurrent writer.
    """
    if not payload or len(payload) > MAX_FILE_BYTES:
        raise ValueError("Export file must contain 1 byte to 64 MiB")
    _cancel(cancelled)
    output = _OutputParent(target) if previous is None else _RememberedPdfParent(target, previous)
    with output as parent:
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
