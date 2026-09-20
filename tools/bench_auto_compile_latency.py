"""Actual auto-save -> auto-compile -> current PDF pixel latency on a copy."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import sys
import time
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def marker_source(source, rgb):
    marker = (r"\usepackage{xcolor}" + "\n"
              r"\AddToHook{shipout/foreground}{\put(16,-24){\color[RGB]{"
              + ",".join(map(str, rgb)) + r"}\rule{16pt}{16pt}}}" + "\n")
    assert source.count(r"\begin{document}") == 1
    return source.replace(r"\begin{document}", marker + r"\begin{document}", 1)


def marker_pixels(image, rgb):
    count = 0
    for y in range(0, image.height(), 3):
        for x in range(0, image.width(), 3):
            color = image.pixelColor(x, y)
            if all(abs(value - target) < 8 for value, target in zip(
                    (color.red(), color.green(), color.blue()), rgb)):
                count += 1
    return count


def run(args):
    os.environ["QT_QPA_PLATFORM"] = "cocoa" if args.native else "offscreen"
    from PySide6.QtCore import QEvent, QSettings, QTimer
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QApplication
    from shiboken6 import isValid
    from app.core.compiler import BuildPurpose
    from app.core.settings import AppSettings
    from app.gui.main_window import MainWindow
    from app.gui.theme import apply_theme
    from tools.bench_pdf_pipeline import PaintProbe, source_digest, wait_gui

    # The observer must reject white pixels and the preceding revision's color.
    check = QImage(120, 120, QImage.Format.Format_RGB32)
    check.fill(QColor("white"))
    assert marker_pixels(check, (234, 18, 142)) == 0
    painter = QPainter(check)
    painter.fillRect(20, 20, 60, 60, QColor(234, 18, 142))
    painter.end()
    assert marker_pixels(check, (234, 18, 142)) > 20
    assert marker_pixels(check, (17, 219, 153)) == 0

    source_root = args.project.resolve()
    output = args.output.resolve()
    assert not output.is_relative_to(source_root.parent)
    output.mkdir(parents=True, exist_ok=False)
    project = output / "project"
    shutil.copytree(source_root.parent, project, symlinks=True,
                    ignore=shutil.ignore_patterns(".icstex", ".latex_build", ".git", ".DS_Store", "__pycache__"))
    assert not any(path.is_symlink() for path in project.rglob("*")), "Use a self-contained fixture"
    root = project / source_root.name
    source = root.read_text(encoding="utf-8")
    report = {"completed": False, "app_sha256": source_digest(), "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
              "backend": os.environ["QT_QPA_PLATFORM"], "samples": [], "callback_errors": [],
              "metric": "Source-change event to matching new PDF color pixels; also first automatic compile request to pixels",
              "limits": "GUI source runtime, isolated copy, warm incremental runs after one preview warmup; screenshot observation upper bound, not compositor time. No p95 with five samples."}
    preferences = replace(AppSettings().load_preferences(), auto_compile=False)
    settings = AppSettings(QSettings(str(output / "settings.ini"), QSettings.Format.IniFormat))
    settings.save_preferences(preferences)
    report["settings"] = {key: getattr(preferences, key) for key in ("fast_preview", "save_debounce_ms", "compile_debounce_ms", "ui_scale")}
    QApplication.setDesktopSettingsAware(False)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    previous_hook = sys.excepthook
    sys.excepthook = lambda kind, value, trace: report["callback_errors"].append(f"{kind.__name__}: {value}")
    window = MainWindow(settings_store=settings)
    probe = None
    try:
        window.project_files.set_project_root(project)
        window.open_file(root)
        window.setWindowTitle(f"ICSTeX - AUTO COMPILE COPY - {os.getpid()}")
        window.resize(1440, 900)
        window.show()
        if args.native:
            window.raise_()
            window.activateWindow()
            wait_gui(lambda: window.isActiveWindow() and window.windowHandle().isExposed(), timeout=10)
        window.compile_current(immediate=True, purpose=BuildPurpose.FINAL)
        wait_gui(lambda: window.compile.final_evidence_for(root) is not None, timeout=120)
        wait_gui(lambda: not window.dependencies.is_busy)
        window.source_preview_area.select_pdf(True)
        editor = window.current_tab().editor
        manager = window.current_tab().manager

        class CurrentPaint(PaintProbe):
            target = None

            def observe(self):
                self.pending = False
                result = self.events.get("result")
                if (result is None or not result.ok or not self.viewport.isVisible()
                        or self.window.pdf_panel.current_pdf != result.pdf_file):
                    return
                displayed = window.displayed_pdfs.get(root)
                if displayed is None or displayed.build_id != result.build_id:
                    return
                if result.job_key.source_revision != window.pdf_state.record_for(root).source_revision:
                    return
                self.capturing = True
                image = self.viewport.grab().toImage()
                self.capturing = False
                pixels = marker_pixels(image, self.target)
                if pixels > 20:
                    self.events["visible_content_observed"] = time.perf_counter()
                    self.events["marker_pixels"] = pixels

        probe = CurrentPaint(window, None)
        original_finished = manager.on_finished
        original_auto = window.compile.compile_for_root

        def finished(result):
            probe.events["result"] = result
            probe.events["worker_finished"] = time.perf_counter()
            original_finished(result)

        def auto(*a, **kw):
            probe.events.setdefault("auto_requested", time.perf_counter())
            return original_auto(*a, **kw)

        def started(*_):
            probe.events.setdefault("compiler_started", time.perf_counter())

        manager.on_finished = finished
        window.signals.started.connect(started)
        window.dependencies.membership_metrics_hook = lambda row: probe.events.setdefault("membership", []).append(row)
        window.auto_compile_action.setChecked(True)
        colors = ((17, 219, 153), (234, 18, 142), (171, 37, 231), (239, 133, 17),
                  (31, 107, 233), (177, 199, 23))
        def timed(name, method):
            def measured(*a, **kw):
                start = time.perf_counter()
                try:
                    return method(*a, **kw)
                finally:
                    probe.events.setdefault("phases_ms", {}).setdefault(name, []).append(
                        (time.perf_counter() - start) * 1000)
            return measured

        with ExitStack() as stack:
            stack.enter_context(patch.object(window.compile, "compile_for_root", side_effect=auto))
            if args.profile_phases:
                report["diagnostic_instrumentation"] = True
                for owner, name in ((manager, "preview_preparer"), (window.compile, "on_finished"),
                                    (window.project_panels, "run_project_check"),
                                    (window.dependencies, "_apply_memberships"),
                                    (window.pdf_panel, "load_pdf")):
                    stack.enter_context(patch.object(owner, name, timed(name, getattr(owner, name))))
            for trial in range(args.trials + 1):
                if args.native:
                    assert window.isActiveWindow() and window.windowHandle().isExposed(), "Owned window lost foreground"
                probe.target = colors[trial % len(colors)]
                probe.reset(f"auto-{trial}")
                editor.setPlainText(marker_source(source, probe.target))
                wait_gui(lambda: "visible_content_observed" in probe.events, timeout=120)
                events = probe.events
                result = events["result"]
                assert result.job_key.source_revision == window.pdf_state.record_for(root).source_revision
                assert result.purpose is (BuildPurpose.PREVIEW if preferences.fast_preview else BuildPurpose.FINAL)
                assert root.read_text(encoding="utf-8") == editor.toPlainText()
                row = {"trial": trial, "warmup": trial == 0, "build_id": result.build_id,
                       "purpose": result.purpose.value, "pages": window.pdf_panel._document.pageCount(),
                       "event_to_visible_ms": (events["visible_content_observed"] - events["request"]) * 1000,
                       "auto_request_to_visible_ms": (events["visible_content_observed"] - events["auto_requested"]) * 1000,
                       "event_to_auto_request_ms": (events["auto_requested"] - events["request"]) * 1000,
                       "event_to_compiler_started_ms": (events["compiler_started"] - events["request"]) * 1000,
                       "event_to_worker_finished_ms": (events["worker_finished"] - events["request"]) * 1000,
                       "membership": events.get("membership", []), "marker_pixels": events["marker_pixels"],
                       "compiler_reported_ms": result.duration_seconds * 1000,
                       "phases_ms": events.get("phases_ms", {}),
                       "pdf_sha256": hashlib.sha256(result.pdf_file.read_bytes()).hexdigest()}
                report["samples"].append(row)
                print(json.dumps(row), flush=True)
                wait_gui(lambda: not window.dependencies.is_busy and not manager.is_busy)
        wait_gui(lambda: not window.word_counts.is_busy, timeout=30)
        report["word_count_settled"] = True
        window.grab().save(str(output / "last.png"))
        values = [row["event_to_visible_ms"] for row in report["samples"] if not row["warmup"]]
        report["event_to_visible_summary_ms"] = {"median": statistics.median(values), "max": max(values), "samples": values}
        report["completed"] = not report["callback_errors"]
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        if probe is not None:
            report["failure_state"] = probe.snapshot()
            report["failure_events"] = {key: value for key, value in probe.events.items() if key != "result"}
        raise
    finally:
        window.auto_compile_action.setChecked(False)
        for tab in window.tabs.values():
            window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        window.close()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        report["window_destroyed"] = not isValid(window)
        report["app_sha256_after"] = source_digest()
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        sys.excepthook = previous_hook
    assert report["completed"] and report["window_destroyed"] and report["app_sha256"] == report["app_sha256_after"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--profile-phases", action="store_true", help="Diagnostic method timings, not acceptance measurements")
    args = parser.parse_args()
    if not 1 <= args.trials <= 5:
        parser.error("Use one to five bounded compile trials")
    run(args)
