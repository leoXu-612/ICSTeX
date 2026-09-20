"""Measure real GUI membership refresh separately from off-thread file hashing.

Only temporary generated projects and the explicitly selected JSON report are
written. Offscreen event-loop latency is not native screen presentation latency.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QEvent, QSettings, QTimer
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from tools.bench_response_pipeline import dependency_probe, wait_gui
from tools.probe_project_migration import digest_tree


def rss_kib():
    return int(subprocess.check_output(["ps", "-o", "rss=", "-p", str(os.getpid())], text=True))


def sample_summary(values):
    """Nearest-rank p95 only when the requested minimum sample size is met."""
    return {"count": len(values), "p50_ms": round(statistics.median(values), 3),
            "p95_ms": round(sorted(values)[math.ceil(len(values) * .95) - 1], 3) if len(values) >= 30 else None,
            "max_ms": round(max(values), 3), "over_50_ms": sum(value > 50 for value in values)}


def run(output, *, repetitions=30):
    if not 1 <= repetitions <= 300:
        raise ValueError("Use one to 300 bounded repetitions")
    if output.exists():
        raise ValueError("Select a new evidence path; previous measurements are retained")
    app = QApplication.instance() or QApplication([])
    source = digest_tree()
    report = {"app_sha256": source, "platform": platform.platform(), "python": platform.python_version(),
              "qt_platform": app.platformName(), "samples": [], "repetitions": repetitions,
              "percentile_method": "nearest rank; p95 omitted for fewer than 30 observations",
              "memory_boundary": "Current process RSS includes Qt/Python allocators and caches; not a leak diagnosis"}
    with TemporaryDirectory(prefix="icstex-membership-probe-") as directory:
        base = Path(directory).resolve()
        report["core"] = dependency_probe(base)
        for sample in report["core"]:
            project = base / f"dependencies-{sample['children']}"
            original = {p: p.read_bytes() for p in project.glob("*.tex")}
            window = MainWindow(settings_store=AppSettings(QSettings(str(project / "qa.ini"), QSettings.Format.IniFormat)))
            window.auto_compile_action.setChecked(False)
            window.project_files.set_project_root(project)
            started = time.perf_counter()
            window.open_file(project / "main.tex")
            opened_ms = (time.perf_counter() - started) * 1000
            result = {"children": sample["children"], "open_call_ms": round(opened_ms, 3), "refresh": []}
            try:
                wait_gui(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy, timeout=30)
                window.file_watcher.stop()
                editor = window.current_tab().editor
                cursor, scroll = editor.textCursor().position(), editor.verticalScrollBar().value()
                result["rss_open_kib"] = rss_kib()
                phases = []
                window.dependencies.membership_metrics_hook = phases.append
                for trial in range(repetitions):
                    events = {}

                    def refresh():
                        start = time.perf_counter()
                        # Force real recomputation, not a cached no-op; keep
                        # dispatch/worker/commit timings separate from the old
                        # synchronous full callback timing.
                        window.dependencies.refresh_memberships(force=True)
                        events["call_ms"] = (time.perf_counter() - start) * 1000

                    start = time.perf_counter()
                    QTimer.singleShot(0, refresh)
                    QTimer.singleShot(10, lambda: events.update(heartbeat=time.perf_counter()))
                    wait_gui(lambda: "heartbeat" in events)
                    result["refresh"].append({"trial": trial, "call_ms": round(events["call_ms"], 3),
                        "timer_lateness_ms": round(max(0, (events["heartbeat"] - start) * 1000 - 10), 3)})
                    wait_gui(lambda: not window.dependencies.is_busy, timeout=30)
                    accepted = [row for row in phases if row["accepted"]]
                    assert len(accepted) == trial + 1, phases
                    result["refresh"][-1]["phases"] = accepted[-1]
                result["refresh_summary"] = sample_summary([row["call_ms"] for row in result["refresh"]])
                result["timer_lateness_summary"] = sample_summary([row["timer_lateness_ms"] for row in result["refresh"]])
                result["phase_summaries"] = {name: sample_summary([row["phases"][name] for row in result["refresh"]])
                    for name in ("capture_ms", "worker_ms", "commit_ms", "capture_to_commit_ms")}
                assert window.dependencies.paths_for(project / "main.tex") == frozenset(original)
                assert not window.compile_authorized_roots
                assert all(path.read_bytes() == data for path, data in original.items())
                assert (editor.textCursor().position(), editor.verticalScrollBar().value()) == (cursor, scroll)
                result["source_cursor_scroll_and_authority_preserved"] = True
            finally:
                assert window.close()
                QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                assert not isValid(window)
                QApplication.processEvents()
            result["rss_after_close_kib"] = rss_kib()
            result["closed_window_destroyed"] = True
            report["samples"].append(result)
    assert digest_tree() == source
    report["app_hash_matches_after_run"] = True
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=30)
    args = parser.parse_args()
    run(args.output, repetitions=args.repetitions)
