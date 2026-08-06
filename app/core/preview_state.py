"""Root-scoped state for fast preview builds.

Preview artifacts are deliberately tracked separately from proper PDF builds.
Monotonic source revisions and build ids determine freshness; file mtimes are
not part of the state model.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.core.paths import normalize_path


class PreviewFreshness(Enum):
    UNCOMPILED = "uncompiled"
    DIRTY = "dirty"
    COMPILING = "compiling"
    CURRENT = "current"
    FAILED_STALE = "failed_stale"
    FAILED_NO_PDF = "failed_no_pdf"


FRESHNESS_LABELS: dict[PreviewFreshness, str] = {
    PreviewFreshness.UNCOMPILED: "尚无预览",
    PreviewFreshness.DIRTY: "源码已修改，预览待更新",
    PreviewFreshness.COMPILING: "正在更新预览…",
    PreviewFreshness.CURRENT: "预览已是最新",
    PreviewFreshness.FAILED_STALE: "预览失败，当前显示上次成功版本",
    PreviewFreshness.FAILED_NO_PDF: "预览失败，暂无可用预览",
}

FRESHNESS_SEVERITY: dict[PreviewFreshness, str] = {
    PreviewFreshness.UNCOMPILED: "neutral",
    PreviewFreshness.DIRTY: "warning",
    PreviewFreshness.COMPILING: "neutral",
    PreviewFreshness.CURRENT: "success",
    PreviewFreshness.FAILED_STALE: "warning",
    PreviewFreshness.FAILED_NO_PDF: "error",
}


@dataclass
class PreviewBuildRecord:
    root_file: Path
    freshness: PreviewFreshness = PreviewFreshness.UNCOMPILED
    source_revision: int = 0
    build_revision: int | None = None
    last_successful_revision: int | None = None
    last_successful_pdf: Path | None = None
    latest_build_id: int | None = None
    active_build_id: int | None = None
    # Results at or below this watermark were invalidated by ``clear``.
    invalidated_build_id: int = 0
    last_duration_seconds: float | None = None
    last_engine: str | None = None
    fidelity: str | None = None
    manifest_digest: str | None = None

    @property
    def has_valid_pdf(self) -> bool:
        """Whether the last successful preview still exists and is non-empty."""
        pdf = self.last_successful_pdf
        try:
            return pdf is not None and pdf.is_file() and pdf.stat().st_size > 0
        except OSError:
            return False


class PreviewStateStore:
    """Own all preview-state transitions, isolated by normalized root path."""

    def __init__(self) -> None:
        self._records: dict[Path, PreviewBuildRecord] = {}

    def record_for(self, root: str | Path) -> PreviewBuildRecord:
        key = normalize_path(root)
        record = self._records.get(key)
        if record is None:
            record = PreviewBuildRecord(root_file=key)
            self._records[key] = record
        return record

    def records(self) -> tuple[PreviewBuildRecord, ...]:
        return tuple(self._records.values())

    def mark_edited(self, root: str | Path) -> PreviewBuildRecord:
        record = self.record_for(root)
        record.source_revision += 1
        record.freshness = PreviewFreshness.DIRTY
        return record

    def begin_build(self, root: str | Path, build_id: int) -> PreviewBuildRecord:
        record = self.record_for(root)
        if build_id <= record.invalidated_build_id:
            return record
        if record.latest_build_id is not None and build_id <= record.latest_build_id:
            return record

        record.latest_build_id = build_id
        record.active_build_id = build_id
        record.build_revision = record.source_revision
        record.freshness = PreviewFreshness.COMPILING
        return record

    def finish_build(
        self,
        root: str | Path,
        build_id: int,
        *,
        success: bool,
        pdf_file: str | Path | None = None,
        duration_seconds: float | None = None,
        engine: str | None = None,
        fidelity: str | None = None,
        manifest_digest: str | None = None,
    ) -> PreviewBuildRecord | None:
        """Apply the active result, or return ``None`` for a late result."""
        record = self.record_for(root)
        if build_id <= record.invalidated_build_id:
            return None
        if record.active_build_id != build_id:
            return None

        record.active_build_id = None
        record.last_duration_seconds = duration_seconds
        record.last_engine = engine

        candidate = normalize_path(pdf_file) if pdf_file is not None else None
        if success and _is_valid_pdf(candidate):
            record.last_successful_pdf = candidate
            record.last_successful_revision = record.build_revision
            record.fidelity = fidelity
            record.manifest_digest = manifest_digest
            record.freshness = (
                PreviewFreshness.CURRENT
                if record.source_revision == record.build_revision
                else PreviewFreshness.DIRTY
            )
        else:
            record.freshness = (
                PreviewFreshness.FAILED_STALE
                if record.has_valid_pdf
                else PreviewFreshness.FAILED_NO_PDF
            )
        return record

    def record_failed_attempt(
        self,
        root: str | Path,
        *,
        duration_seconds: float | None = None,
        engine: str | None = None,
    ) -> PreviewBuildRecord:
        """Record a failure that occurred before a preview build started."""
        record = self.record_for(root)
        record.last_duration_seconds = duration_seconds
        record.last_engine = engine
        record.freshness = (
            PreviewFreshness.FAILED_STALE
            if record.has_valid_pdf
            else PreviewFreshness.FAILED_NO_PDF
        )
        return record

    def clear(self, root: str | Path) -> PreviewBuildRecord:
        """Forget preview output and invalidate any result currently in flight."""
        record = self.record_for(root)
        if record.latest_build_id is not None:
            record.invalidated_build_id = max(
                record.invalidated_build_id,
                record.latest_build_id,
            )
        record.active_build_id = None
        record.build_revision = None
        record.last_successful_revision = None
        record.last_successful_pdf = None
        record.last_duration_seconds = None
        record.last_engine = None
        record.fidelity = None
        record.manifest_digest = None
        record.freshness = PreviewFreshness.UNCOMPILED
        return record

    def clear_build_output(self, root: str | Path) -> PreviewBuildRecord:
        """Compatibility spelling for callers that mirror ``PdfStateStore``."""
        return self.clear(root)


def _is_valid_pdf(pdf: Path | None) -> bool:
    try:
        return pdf is not None and pdf.is_file() and pdf.stat().st_size > 0
    except OSError:
        return False
