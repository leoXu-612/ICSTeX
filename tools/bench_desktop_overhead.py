"""E2 isolated offscreen startup, scale, idle and window-retirement measurements.

Fresh interpreters are not OS-cache-cold starts. Synchronous Qt timings and
offscreen captures do not prove Cocoa/compositor latency or human acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import cProfile
import io
import json
import math
import os
from pathlib import Path
import platform
import pstats
import resource
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def summary(samples):
    result = {"n": len(samples), "samples_ms": samples, "median_ms": statistics.median(samples), "max_ms": max(samples)}
    if len(samples) >= 30:
        result["p95_ms"] = sorted(samples)[math.ceil(len(samples) * .95) - 1]
    return result


def rss_bytes():
    result = subprocess.run(["/bin/ps", "-o", "rss=", "-p", str(os.getpid())],
                            capture_output=True, text=True, timeout=5, check=True)
    return int(result.stdout.strip()) * 1024


def event_loop(milliseconds):
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(milliseconds)
    loop.exec()


def bootstrap(base, *, profiler=None):
    phases = {}
    if profiler is not None:
        profiler.enable()
    start = time.perf_counter()
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from app.core.settings import AppSettings
    from app.gui.main_window import MainWindow
    from app.gui.theme import apply_theme
    phases["imports_ms"] = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    phases["qapplication_ms"] = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    apply_theme(app)
    phases["theme_ms"] = (time.perf_counter() - start) * 1000
    settings = AppSettings(QSettings(str(base / "main.ini"), QSettings.Format.IniFormat))
    settings.settings.setValue("editor/auto_compile", False)
    start = time.perf_counter()
    window = MainWindow(settings_store=settings)
    phases["window_construct_ms"] = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    window.show()
    event_loop(0)
    phases["show_to_event_loop_ms"] = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    pixmap = window.grab()
    assert not pixmap.isNull()
    phases["offscreen_grab_ms"] = (time.perf_counter() - start) * 1000
    del pixmap
    start = time.perf_counter()
    window.new_document()
    event_loop(0)
    phases["first_new_document_ms"] = (time.perf_counter() - start) * 1000
    if profiler is not None:
        profiler.disable()
    return app, window, phases


def retirement(window):
    from tools.probe_project_checkpoint_gui import close
    from shiboken6 import isValid
    close(window)
    assert not isValid(window), "A supposedly closed window still exists"


def startup_child(profile=None):
    with TemporaryDirectory(prefix="icstex-overhead-start-") as temporary:
        profiler = cProfile.Profile() if profile else None
        app, window, phases = bootstrap(Path(temporary), profiler=profiler)
        try:
            result = {"phases": phases, "rss_after_first_document_bytes": rss_bytes(),
                      "profiled": profile is not None, "backend": app.platformName()}
            from tools.bench_pdf_pipeline import source_digest
            result["app_sha256"] = source_digest()
            if profiler is not None:
                profiler.dump_stats(str(profile / "startup.pstats"))
                stream = io.StringIO()
                pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(50)
                (profile / "startup-profile.txt").write_text(stream.getvalue())
        finally:
            retirement(window)
        result["window_destroyed"] = True
    print("ICSTEX_BENCH_JSON=" + json.dumps(result))


def runtime(output, *, repetitions, idle_seconds, profiled=False, freeze_updates=False):
    with TemporaryDirectory(prefix="icstex-overhead-runtime-") as temporary:
        base = Path(temporary)
        app, window, phases = bootstrap(base)
        from PySide6.QtCore import QEvent, QObject, QSettings
        from PySide6.QtWidgets import QApplication
        from app.core.settings import AppSettings
        from app.core.blocks.registry import BlockRegistry, CreateBlockInput
        from app.gui.blocks.project_session import ProjectSession
        from app.gui.block_mode import _install_session, _set_block_mode
        from app.gui.formula_dialog import FormulaDialog
        from app.gui.main_window import MainWindow
        from tools.bench_pdf_pipeline import source_digest
        from shiboken6 import isValid
        report = {"app_sha256": source_digest(), "phases": phases, "scaling": {}, "cycles": [], "profiled": profiled,
                  "variant": "freeze_updates" if freeze_updates else "unchanged_product",
                  "completed": False, "callback_errors": [], "backend": app.platformName()}
        old_hook = sys.excepthook
        sys.excepthook = lambda kind, value, trace: report["callback_errors"].append(f"{kind.__name__}: {value}")
        other = formula = None
        editor = window.current_tab().editor
        editor.insertPlainText("% Synthetic unsaved scale draft\n")
        original = (editor.toPlainText(), editor.textCursor().position(), editor.textCursor().anchor())
        try:
            for scenario in ("one_source_window", "source_block_and_formula"):
                if scenario != "one_source_window":
                    other = MainWindow(AppSettings(QSettings(str(base / "block.ini"), QSettings.Format.IniFormat)))
                    registry = BlockRegistry()
                    registry.create(CreateBlockInput(type="text", alias="Synthetic", content={"text": "Original block text"}))
                    session = ProjectSession(registry=registry)
                    assert _install_session(other, session)
                    _set_block_mode(other, True)
                    other.show()
                    session.selection.select_block(registry.blocks()[0].id, source="benchmark")
                    other.block_inspector.content_edit.insertPlainText("Unapplied synthetic draft ")
                    block_drafts = dict(session.editor_drafts)
                    formula = FormulaDialog(window, "$x+1$", 0, 5)
                    formula.visual_edit.insert_text("y")
                    formula.show()
                    formula_latex = formula.visual_edit.latex()
                values = []
                thread_cpu_values, process_cpu_values = [], []
                for index in range(repetitions):
                    scale = (.9, 1.1, 1., 1.25, 1.5)[index % 5]
                    thread_started = time.thread_time()
                    process_started = time.process_time()
                    started = time.perf_counter()
                    paused = [widget for widget in app.topLevelWidgets()
                              if widget.isVisible() and widget.updatesEnabled()] if freeze_updates else []
                    try:
                        for widget in paused:
                            widget.setUpdatesEnabled(False)
                        window.set_ui_scale(scale)
                    finally:
                        for widget in paused:
                            if isValid(widget):
                                widget.setUpdatesEnabled(True)
                    wall_ms = (time.perf_counter() - started) * 1000
                    thread_cpu_ms = (time.thread_time() - thread_started) * 1000
                    process_cpu_ms = (time.process_time() - process_started) * 1000
                    values.append(wall_ms)
                    thread_cpu_values.append(thread_cpu_ms)
                    process_cpu_values.append(process_cpu_ms)
                    event_loop(0)
                    assert (editor.toPlainText(), editor.textCursor().position(), editor.textCursor().anchor()) == original
                    if formula is not None:
                        assert formula.visual_edit.latex() == formula_latex and formula._accepted_plan is None
                        assert session.editor_drafts == block_drafts
                report["scaling"][scenario] = summary(values)
                report.setdefault("scaling_cpu", {})[scenario] = {
                    "gui_thread": summary(thread_cpu_values),
                    "process": summary(process_cpu_values),
                    "wall_minus_gui_thread": summary([wall - cpu for wall, cpu in zip(values, thread_cpu_values)]),
                }
            report["cpu_clock_limits"] = (
                "Thread/process CPU clocks surround the same synchronous scaling call; "
                "wall-minus-thread may include scheduling, waits or other-thread work, not a causal diagnosis."
            )
            formula.reject()
            formula.deleteLater()
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            assert not isValid(formula)
            formula = None
            retirement(other)
            other = None
            window.set_ui_scale(1.)
            window.activateWindow()
            editor.setFocus()
            event_loop(300)

            class TimerObserver(QObject):
                def __init__(self):
                    super().__init__()
                    self.counts = Counter()

                def eventFilter(self, watched, event):
                    if event.type() == QEvent.Type.Timer:
                        parent = watched.parent()
                        self.counts[type(watched).__name__ + "/" + (type(parent).__name__ if parent else "no-parent")] += 1
                    return False

            observer = TimerObserver()
            for observed in (False, True):
                if observed:
                    app.installEventFilter(observer)
                before = resource.getrusage(resource.RUSAGE_SELF)
                cpu, wall = time.process_time(), time.perf_counter()
                event_loop(round(idle_seconds * 1000))
                cpu, wall = time.process_time() - cpu, time.perf_counter() - wall
                after = resource.getrusage(resource.RUSAGE_SELF)
                report["idle_observed" if observed else "idle_plain"] = {"wall_seconds": wall,
                    "cpu_seconds": cpu, "one_cpu_percent": 100 * cpu / wall,
                    "voluntary_context_switches": after.ru_nvcsw - before.ru_nvcsw,
                    "involuntary_context_switches": after.ru_nivcsw - before.ru_nivcsw,
                    "rss_bytes": rss_bytes(), "timer_events": dict(observer.counts) if observed else None}
                if observed:
                    app.removeEventFilter(observer)
            report["baseline_widgets"] = len(app.allWidgets())
            for index in range(5):
                transient = MainWindow(AppSettings(QSettings(str(base / f"cycle-{index}.ini"), QSettings.Format.IniFormat)))
                transient.show()
                event_loop(0)
                retirement(transient)
                event_loop(0)
                report["cycles"].append({"cycle": index + 1, "rss_bytes": rss_bytes(), "widgets": len(app.allWidgets())})
            assert not window.compile_authorized_roots
            assert (editor.toPlainText(), editor.textCursor().position(), editor.textCursor().anchor()) == original
            report["drafts_preserved"] = True
            report["no_compilation"] = True
            report["checks_completed"] = True
        finally:
            if formula is not None and isValid(formula):
                formula.reject()
                formula.deleteLater()
            if other is not None and isValid(other):
                retirement(other)
            retirement(window)
            report["all_test_windows_destroyed"] = True
            report["app_sha256_after"] = source_digest()
            report["completed"] = (report.get("checks_completed", False) and not report["callback_errors"]
                                   and report["app_sha256"] == report["app_sha256_after"])
            sys.excepthook = old_hook
            (output / "runtime.json").write_text(json.dumps(report, indent=2) + "\n")
        assert report["completed"], report
    return report


def main():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("startup", "runtime", "runtime-profile", "profile", "startup-child"), required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--idle-seconds", type=float, default=8)
    parser.add_argument("--freeze-updates", action="store_true", help="Measurement-only candidate; product code remains unchanged")
    args = parser.parse_args()
    if args.mode == "startup-child":
        startup_child(args.output)
        return
    if args.output is None or not 30 <= args.repetitions <= 100 or not 1 <= args.idle_seconds <= 20:
        parser.error("Choose a new output directory, 30..100 interactions, and 1..20 seconds idle")
    args.output.mkdir(parents=True, exist_ok=False)
    if args.mode in ("runtime", "runtime-profile"):
        profiler = cProfile.Profile() if args.mode == "runtime-profile" else None
        if profiler is not None:
            profiler.enable()
        report = runtime(args.output, repetitions=1 if profiler else args.repetitions,
                         idle_seconds=1 if profiler else args.idle_seconds, profiled=profiler is not None,
                         freeze_updates=args.freeze_updates)
        if profiler is not None:
            profiler.disable()
            profiler.dump_stats(str(args.output / "runtime.pstats"))
            stream = io.StringIO()
            pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(65)
            (args.output / "runtime-profile.txt").write_text(stream.getvalue())
    else:
        trials = []
        for index in range(1 if args.mode == "profile" else 5):
            command = [sys.executable, str(Path(__file__).resolve()), "--mode", "startup-child"]
            if args.mode == "profile":
                command += ["--output", str(args.output.resolve())]
            run = subprocess.run(command, capture_output=True, text=True, timeout=60, cwd=REPO)
            (args.output / f"startup-{index}.log").write_text(run.stdout + "\nSTDERR\n" + run.stderr)
            assert run.returncode == 0, run.stderr
            lines = [line for line in run.stdout.splitlines() if line.startswith("ICSTEX_BENCH_JSON=")]
            assert len(lines) == 1, run.stdout
            trials.append(json.loads(lines[0].split("=", 1)[1]))
        report = {"trials": trials, "phase_summary": {name: summary([row["phases"][name] for row in trials])
                   for name in trials[0]["phases"]}, "platform": platform.platform(), "python": platform.python_version(),
                  "conditions": "Fresh interpreter, isolated settings, offscreen; OS caches unchanged; no startup p95 from 5 samples"}
        (args.output / "startup.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
