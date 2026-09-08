"""Root-scoped PDF freshness state machine.

One ``PdfBuildRecord`` per normalized compile root; a root file and its opened
children (``% !TEX root``, ``\\input``, ``\\include``, ``\\subfile``) share the
same record. Monotonic source revisions and build ids are the source of truth;
file mtimes are never consulted here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.core.compiler import CompileOutcome
from app.core.paths import normalize_path


class PdfFreshness(Enum):
    UNCOMPILED = "uncompiled"
    DIRTY = "dirty"
    COMPILING = "compiling"
    CURRENT = "current"
    FAILED_STALE = "failed_stale"
    FAILED_NO_PDF = "failed_no_pdf"


FRESHNESS_LABELS: dict[PdfFreshness, str] = {
    PdfFreshness.UNCOMPILED: "尚未编译",
    PdfFreshness.DIRTY: "源码已修改，PDF 待更新",
    PdfFreshness.COMPILING: "正在编译…",
    PdfFreshness.CURRENT: "PDF 已是最新",
    PdfFreshness.FAILED_STALE: "编译未成功，当前显示上次成功版本",
    PdfFreshness.FAILED_NO_PDF: "编译未成功，暂无可用 PDF",
}

FRESHNESS_SEVERITY: dict[PdfFreshness, str] = {
    PdfFreshness.UNCOMPILED: "neutral",
    PdfFreshness.DIRTY: "warning",
    PdfFreshness.COMPILING: "neutral",
    PdfFreshness.CURRENT: "success",
    PdfFreshness.FAILED_STALE: "warning",
    PdfFreshness.FAILED_NO_PDF: "error",
}

# Export of an older successful PDF is allowed after confirmation.
_EXPORT_WARN_STATES = frozenset(
    {PdfFreshness.DIRTY, PdfFreshness.COMPILING, PdfFreshness.FAILED_STALE}
)


@dataclass
class PdfBuildRecord:
    root_file: Path
    freshness: PdfFreshness = PdfFreshness.UNCOMPILED
    last_successful_pdf: Path | None = None
    source_revision: int = 0
    compile_revision: int | None = None
    last_successful_revision: int | None = None
    latest_build_id: int | None = None
    # Results with build_id <= this are discarded (set by clean-cache so an
    # in-flight build cannot bounce UNCOMPILED back to FAILED).
    invalidated_build_id: int = 0
    last_outcome: CompileOutcome | None = None
    last_duration_seconds: float | None = None
    last_engine: str | None = None

    @property
    def has_valid_pdf(self) -> bool:
        pdf = self.last_successful_pdf
        try:
            return pdf is not None and pdf.exists() and pdf.stat().st_size > 0
        except OSError:
            return False

    @property
    def export_allowed(self) -> bool:
        return self.has_valid_pdf and self.freshness not in (
            PdfFreshness.UNCOMPILED,
            PdfFreshness.FAILED_NO_PDF,
        )

    @property
    def export_needs_warning(self) -> bool:
        return self.freshness in _EXPORT_WARN_STATES


class PdfStateStore:
    """All freshness mutations go through these transition methods."""

    def __init__(self) -> None:
        self._records: dict[Path, PdfBuildRecord] = {}

    def record_for(self, root: str | Path) -> PdfBuildRecord:
        key = normalize_path(root)
        record = self._records.get(key)
        if record is None:
            record = PdfBuildRecord(root_file=key)
            self._records[key] = record
        return record

    def records(self) -> tuple[PdfBuildRecord, ...]:
        return tuple(self._records.values())

    def mark_edited(self, root: str | Path) -> PdfBuildRecord:
        record = self.record_for(root)
        record.source_revision += 1
        record.freshness = PdfFreshness.DIRTY
        return record

    def begin_build(
        self, root: str | Path, build_id: int, *, source_revision: int | None = None,
    ) -> PdfBuildRecord:
        record = self.record_for(root)
        if record.latest_build_id is not None and build_id <= record.latest_build_id:
            return record
        record.latest_build_id = build_id
        record.compile_revision = record.source_revision if source_revision is None else source_revision
        record.freshness = PdfFreshness.COMPILING
        return record

    def finish_build(
        self,
        root: str | Path,
        build_id: int,
        outcome: CompileOutcome,
        *,
        pdf_file: Path | None = None,
        duration_seconds: float | None = None,
        engine: str | None = None,
    ) -> PdfBuildRecord | None:
        """Apply a build result; return None when a newer build supersedes it."""
        record = self.record_for(root)
        if record.latest_build_id is not None and build_id < record.latest_build_id:
            return None
        if build_id <= record.invalidated_build_id:
            return None
        record.last_outcome = outcome
        record.last_duration_seconds = duration_seconds
        record.last_engine = engine
        if outcome is CompileOutcome.SUCCESS and pdf_file is not None:
            record.last_successful_pdf = normalize_path(pdf_file)
            record.last_successful_revision = record.compile_revision
            record.freshness = (
                PdfFreshness.CURRENT
                if record.source_revision == record.compile_revision
                else PdfFreshness.DIRTY
            )
        else:
            record.freshness = (
                PdfFreshness.FAILED_STALE if record.has_valid_pdf else PdfFreshness.FAILED_NO_PDF
            )
        return record

    def record_failed_attempt(self, root: str | Path, outcome: CompileOutcome) -> PdfBuildRecord:
        """A compile attempt that never started a build (e.g. missing toolchain)."""
        record = self.record_for(root)
        record.last_outcome = outcome
        record.freshness = (
            PdfFreshness.FAILED_STALE if record.has_valid_pdf else PdfFreshness.FAILED_NO_PDF
        )
        return record

    def clear_build_output(self, root: str | Path) -> PdfBuildRecord:
        record = self.record_for(root)
        record.last_successful_pdf = None
        record.compile_revision = None
        record.last_successful_revision = None
        record.last_outcome = None
        record.freshness = PdfFreshness.UNCOMPILED
        if record.latest_build_id is not None:
            record.invalidated_build_id = max(record.invalidated_build_id, record.latest_build_id)
        return record
