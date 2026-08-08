"""Performance diagnostics for image drag-and-drop import (phase 1).

Records a per-transaction timeline with stage durations, counts compile
requests vs actual starts vs coalesced requests, counts full index scans, and
formats evidence-based summaries such as:

    transaction=asset-import-7f82
    compile requested: 1
    compile actually started: 1
    compile requests coalesced: 0
    full index scans: 1
    stages: copy=0.12s index=0.01s source=0.01s compile=6.20s total=6.35s

Pure core module: no Qt, no filesystem writes, no subprocesses.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import threading
import time
import uuid


_STAGE_ORDER = (
    "drop_received",
    "source_validated",
    "destination_resolved",
    "copy_started",
    "copy_finished",
    "metadata_started",
    "metadata_finished",
    "index_update_started",
    "index_update_finished",
    "source_edit_started",
    "source_edit_finished",
    "compile_requested",
    "compile_started",
    "compile_finished",
    "preview_reload_started",
    "preview_reload_finished",
    "import_finished",
)


@dataclass
class ImportStage:
    """One timed stage of an import transaction."""

    name: str
    elapsed: float
    meta: dict[str, str] = field(default_factory=dict)


class ImportRecorder:
    """Per-transaction timeline and compile/index counters."""

    def __init__(self, transaction_id: str | None = None) -> None:
        self.transaction_id = transaction_id or f"asset-import-{uuid.uuid4().hex[:8]}"
        self.started_at = time.perf_counter()
        self.stages: list[ImportStage] = []
        self.compile_requested = 0
        self.compile_started = 0
        self.full_index_scans = 0
        self._last_stage_started: float | None = None

    def step(self, name: str, **meta: object) -> None:
        """End the previous stage (if any) and record ``name`` as a stage."""

        now = time.perf_counter()
        if self._last_stage_started is not None and self.stages:
            self.stages[-1].elapsed = now - self._last_stage_started
        self.stages.append(ImportStage(name=name, elapsed=0.0, meta={str(k): str(v) for k, v in meta.items()}))
        self._last_stage_started = now

    def record(self, name: str, elapsed: float, **meta: object) -> None:
        """Record a stage with an explicit duration."""

        self.stages.append(ImportStage(name=name, elapsed=max(0.0, elapsed), meta={str(k): str(v) for k, v in meta.items()}))
        self._last_stage_started = None

    def finish(self) -> None:
        now = time.perf_counter()
        if self._last_stage_started is not None and self.stages:
            self.stages[-1].elapsed = now - self._last_stage_started
        self._last_stage_started = None

    def total(self) -> float:
        return time.perf_counter() - self.started_at

    def summary(self) -> dict[str, object]:
        return {
            "transaction_id": self.transaction_id,
            "compile_requested": self.compile_requested,
            "compile_started": self.compile_started,
            "compile_coalesced": max(0, self.compile_requested - self.compile_started),
            "full_index_scans": self.full_index_scans,
            "stages": {stage.name: round(stage.elapsed, 3) for stage in self.stages},
            "total_seconds": round(self.total(), 3),
        }

    def format_summary(self) -> str:
        data = self.summary()
        lines = [
            f"transaction={data['transaction_id']}",
            f"compile requested: {data['compile_requested']}",
            f"compile actually started: {data['compile_started']}",
            f"compile requests coalesced: {data['compile_coalesced']}",
            f"full index scans: {data['full_index_scans']}",
        ]
        stages = data["stages"]
        stage_text = " ".join(f"{name}={value}s" for name, value in stages.items())
        lines.append(f"stages: {stage_text} total={data['total_seconds']}s")
        return "\n".join(lines)


class ImportMetrics:
    """Collects the active transaction, compile/index counters, and history."""

    def __init__(self, max_summaries: int = 20) -> None:
        self._lock = threading.Lock()
        self._current: ImportRecorder | None = None
        self._awaiting: ImportRecorder | None = None
        self._summaries: deque[dict[str, object]] = deque(maxlen=max_summaries)
        self._global_requested = 0
        self._global_started = 0

    def begin_transaction(self, transaction_id: str | None = None) -> ImportRecorder:
        with self._lock:
            stale = self._awaiting or self._current
        if stale is not None:
            # One import at a time: finalize any open transaction so compile
            # attribution for the next import cannot be polluted.
            self._finalize(stale)
        with self._lock:
            recorder = ImportRecorder(transaction_id)
            self._current = recorder
            return recorder

    def current(self) -> ImportRecorder | None:
        with self._lock:
            return self._current

    def finish_transaction(self, recorder: ImportRecorder | None = None) -> dict[str, object]:
        recorder = recorder or self._current
        if recorder is None:
            return {}
        recorder.step("import_finished")
        with self._lock:
            awaiting = self._awaiting is recorder
        if awaiting:
            # The compile starts after the debounce; keep the transaction open
            # so the start is attributed to this import.
            return recorder.summary()
        return self._finalize(recorder)

    def record_compile_request(self, reason: str = "asset_import") -> None:
        with self._lock:
            self._global_requested += 1
            recorder = self._current
        if recorder is not None:
            recorder.step("compile_requested", reason=reason)
            recorder.compile_requested += 1
            with self._lock:
                self._awaiting = recorder

    def record_compile_start(self, reason: str = "") -> None:
        with self._lock:
            self._global_started += 1
            recorder = self._awaiting
        if recorder is not None:
            recorder.step("compile_started", reason=reason)
            recorder.compile_started += 1

    def record_compile_finish(self, reason: str = "") -> None:
        with self._lock:
            recorder = self._awaiting
        if recorder is not None:
            recorder.step("compile_finished", reason=reason)
            self._finalize(recorder)

    def record_index_scan(self, *, full: bool) -> None:
        recorder = self._current
        if recorder is not None and full:
            recorder.full_index_scans += 1

    def record_compile_event(self, event: str, reason: str = "") -> None:
        if event == "request":
            self.record_compile_request(reason)
        elif event == "start":
            self.record_compile_start(reason)
        elif event == "finish":
            self.record_compile_finish(reason)

    def finalize_expired(self, max_age: float = 30.0) -> None:
        with self._lock:
            recorder = self._awaiting
        if recorder is not None and time.perf_counter() - recorder.started_at > max_age:
            self._finalize(recorder)

    def _finalize(self, recorder: ImportRecorder) -> dict[str, object]:
        recorder.finish()
        summary = recorder.summary()
        with self._lock:
            self._summaries.append(summary)
            if self._awaiting is recorder:
                self._awaiting = None
            if self._current is recorder:
                self._current = None
        return summary

    def latest_summary(self) -> dict[str, object] | None:
        with self._lock:
            return self._summaries[-1] if self._summaries else None

    def summaries(self) -> list[dict[str, object]]:
        with self._lock:
            return list(self._summaries)

    def global_counts(self) -> dict[str, int]:
        with self._lock:
            return {
                "compile_requested": self._global_requested,
                "compile_started": self._global_started,
            }


import_metrics = ImportMetrics()
