"""Synthetic key-to-paint observation; no student content or global settings.

Run with QT_QPA_PLATFORM=cocoa and select a new --output directory. Widget
capture is an observation upper bound, not physical keyboard/compositor timing.
"""
from __future__ import annotations

import time
IMPORT_START = time.perf_counter()
import argparse
import json
import os
from pathlib import Path
import platform
import sys
import threading
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from PySide6.QtCore import QEvent, QObject, QRect, QSettings, QTimer, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid
from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.bench_dependency_membership import rss_kib, sample_summary
from tools.bench_pdf_pipeline import source_digest, wait_gui
IMPORT_MS = (time.perf_counter() - IMPORT_START) * 1000


class WritingPaintProbe(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.editor = window.current_tab().editor
        self.viewport = self.editor.viewport()
        self.viewport.installEventFilter(self)
        self.pending = False
        self.events = {}
        self.before = None

    def start(self):
        self.before = self.viewport.grab().toImage()
        self.events = {"request": time.perf_counter()}

    def eventFilter(self, watched, event):
        if (watched is self.viewport and event.type() == QEvent.Type.Paint
                and "handler_return" in self.events and "visible_change" not in self.events
                and not self.pending):
            self.events.setdefault("paint_event", time.perf_counter())
            self.pending = True
            QTimer.singleShot(0, self, self.observe)
        return False

    def observe(self):
        # Compare text to the right of both old/new caret positions. A caret
        # move or blink alone cannot satisfy this observation predicate.
        self.events["observer_enter"] = time.perf_counter()
        cursor = self.editor.cursorRect()
        left = cursor.right() + 20
        rect = QRect(left, cursor.top(), min(300, self.viewport.width() - left), cursor.height())
        if rect.width() > 20 and self.viewport.isVisible():
            self.events["grab_begin"] = time.perf_counter()
            after = self.viewport.grab(rect).toImage()
            self.events["grab_end"] = time.perf_counter()
            dpr = self.before.devicePixelRatio()
            before = self.before.copy(QRect(round(rect.x() * dpr), round(rect.y() * dpr),
                after.width(), after.height()))
            changed = before != after
            self.events["compare_end"] = time.perf_counter()
            if changed:
                self.events["visible_change"] = self.events["compare_end"]
        self.pending = False


class EventTimingApplication(QApplication):
    observer = None

    def notify(self, receiver, event):
        observer = self.observer
        if observer is None or "request" not in observer.events or "visible_change" in observer.events:
            return super().notify(receiver, event)
        started, cpu = time.perf_counter(), time.thread_time()
        name, kind = type(receiver).__name__, event.type().name
        try:
            return super().notify(receiver, event)
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            if elapsed >= 4:
                observer.slow_events.append({"receiver": name, "event": kind,
                    "start_ms": (started - observer.events["request"]) * 1000,
                    "wall_ms": elapsed, "gui_cpu_ms": (time.thread_time() - cpu) * 1000})


def run(output, repetitions, *, children=0, key_interval_ms=0, profile_keys=False, profile_events=False):
    if output.exists():
        raise ValueError("Select a new output directory")
    if os.environ.get("QT_QPA_PLATFORM") != "cocoa":
        raise ValueError("Native observation requires QT_QPA_PLATFORM=cocoa")
    if not 1 <= repetitions <= 100:
        raise ValueError("Use one to 100 bounded repetitions")
    if not 0 <= children <= 200 or not 0 <= key_interval_ms <= 1000:
        raise ValueError("Use 0..200 children and 0..1000 ms between keys")
    output.mkdir(parents=True)
    report = {"completed": False, "app_sha256": source_digest(), "platform": platform.platform(),
        "pid": os.getpid(), "samples": [], "startup": {"imports_ms": IMPORT_MS},
        "measurement": "QTest key injection to changed text pixels after Paint; excludes caret ROI; capture upper bound, not compositor or human IME",
        "conditions": "1440x900, new isolated settings (100%), auto compile off; no OS cache flush",
        "children": children, "key_interval_ms": key_interval_ms, "profile_keys": profile_keys,
        "profile_events": profile_events}
    app = QApplication.instance() or (EventTimingApplication([]) if profile_events else QApplication([]))
    app.setQuitOnLastWindowClosed(False)
    started = time.perf_counter()
    apply_theme(app)
    report["startup"]["theme_ms"] = (time.perf_counter() - started) * 1000
    window = None
    patches, stage = [], [None]
    gui_thread = threading.get_ident()

    def instrument(owner, name, label):
        original = getattr(owner, name)

        def measured(*args, **kwargs):
            if threading.get_ident() != gui_thread:
                return original(*args, **kwargs)
            started = time.perf_counter()
            cpu_started = time.thread_time()
            try:
                return original(*args, **kwargs)
            finally:
                if stage[0] is not None:
                    stage[0][label] = stage[0].get(label, 0) + (time.perf_counter() - started) * 1000
                    stage[0][label + ".cpu"] = stage[0].get(label + ".cpu", 0) + (time.thread_time() - cpu_started) * 1000
                    stage[0][label + ".calls"] = stage[0].get(label + ".calls", 0) + 1

        handle = patch.object(owner, name, measured)
        handle.start()
        patches.append(handle)

    if profile_keys:
        instrument(MainWindow, "_on_editor_changed", "editor_slot_ms")
        from app.core import pdf_state, preview_state
        instrument(pdf_state, "normalize_path", "pdf_state.normalize_path")
        instrument(preview_state, "normalize_path", "preview_state.normalize_path")
    try:
        with TemporaryDirectory(prefix="icstex-writing-latency-") as temporary:
            base = Path(temporary).resolve()
            source = "% Alphabet baseline: abcdefghijklmnopqrstuvwxyz 0123456789. Text moves with each insertion.\n" + (
                "\\documentclass{article}\n\\begin{document}\nSynthetic writing response.\n\\end{document}\n")
            if children:
                from tools.bench_response_pipeline import SENTENCE
                includes = "".join(f"\\input{{child-{index}.tex}}\n" for index in range(children))
                source = source.replace("\\end{document}", includes + "\\end{document}")
                for index in range(children):
                    (base / f"child-{index}.tex").write_text(SENTENCE * (400 // children), encoding="utf-8")
            root = base / "main.tex"
            root.write_text(source, encoding="utf-8")
            settings = AppSettings(QSettings(str(base / "qa.ini"), QSettings.Format.IniFormat))
            started = time.perf_counter()
            window = MainWindow(settings_store=settings)
            if profile_keys:
                for owner, name in ((window, "_mark_source_edited"), (window, "_update_pdf_action_state"),
                        (window, "_set_tab_title"), (window, "schedule_save"),
                        (window.word_counts, "schedule"), (window.readiness, "invalidate"),
                        (window.citations, "invalidate"), (window.materials, "invalidate"),
                        (window.project_panels, "source_changed"), (window.dependencies, "schedule_membership_refresh")):
                    instrument(owner, name, type(owner).__name__ + "." + name)
            report["startup"]["window_construct_ms"] = (time.perf_counter() - started) * 1000
            window.auto_compile_action.setChecked(False)
            window.save_debounce_ms = 60_000
            window.open_file(root)
            window.resize(1440, 900)
            window.setWindowTitle(f"ICSTeX - SYNTHETIC WRITING LATENCY - {os.getpid()}")
            started = time.perf_counter()
            window.show()
            window.raise_()
            window.activateWindow()
            wait_gui(lambda: window.windowHandle() is not None and window.windowHandle().isExposed()
                     and window.isActiveWindow(), timeout=10)
            report["startup"]["show_to_exposed_ms"] = (time.perf_counter() - started) * 1000
            wait_gui(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
            editor = window.current_tab().editor
            editor.moveCursor(QTextCursor.MoveOperation.Start)
            editor.setFocus()
            observer = WritingPaintProbe(window)
            if profile_events:
                app.observer = observer
            window.grab().save(str(output / "before.png"))
            report["editor_size"] = [editor.width(), editor.height()]
            report["viewport_dpr"] = editor.viewport().devicePixelRatioF()
            report["rss_before_kib"] = rss_kib()
            membership_phases = []
            window.dependencies.membership_metrics_hook = membership_phases.append
            for trial in range(repetitions):
                assert window.isActiveWindow() and window.windowHandle().isExposed(), "Native input window lost activity/exposure"
                observer.start()
                observer.slow_events = []
                if profile_keys:
                    stage[0] = {}
                QTest.keyClick(editor, Qt.Key.Key_X, delay=0)
                observer.events["handler_return"] = time.perf_counter()
                stages, stage[0] = stage[0], None
                window.documents.cancel_save_timer(window.current_tab())
                wait_gui(lambda: "visible_change" in observer.events, timeout=5)
                assert editor.toPlainText() == "x" * (trial + 1) + source
                origin = observer.events["request"]
                report["samples"].append({"trial": trial, **{
                    key + "_ms": round((value - origin) * 1000, 3)
                    for key, value in observer.events.items() if key != "request"}})
                if profile_keys:
                    report["samples"][-1]["stages_ms"] = stages
                if profile_events:
                    report["samples"][-1]["slow_events"] = observer.slow_events
                if key_interval_ms and trial + 1 < repetitions:
                    next_key = origin + key_interval_ms / 1000
                    wait_gui(lambda: time.perf_counter() >= next_key, timeout=2)
            assert root.read_text(encoding="utf-8") == source
            assert not window.compile_authorized_roots
            queue_peaks = {"word_count_active_requests": 0, "word_count_pending_requests": 0,
                           "input_observation_active_paths": 0, "input_observation_queued_paths": 0,
                           "membership_active_requests": 0, "membership_pending_requests": 0}

            def queues_idle():
                counts = {"word_count_active_requests": int(window.word_counts._active is not None),
                          "word_count_pending_requests": int(window.word_counts._pending is not None),
                          "input_observation_active_paths": len(window.dependencies._active or ()),
                          "input_observation_queued_paths": len(window.dependencies._queued),
                          "membership_active_requests": int(window.dependencies._membership_active is not None),
                          "membership_pending_requests": int(window.dependencies._membership_pending is not None)}
                for key, value in counts.items():
                    queue_peaks[key] = max(queue_peaks[key], value)
                if window.dependencies.memberships_current:
                    report.setdefault("last_key_to_memberships_current_ms",
                        (time.perf_counter() - observer.events["request"]) * 1000)
                return not window.dependencies.is_busy and not window.word_counts.is_busy

            wait_gui(queues_idle, timeout=10)
            report["post_burst_queue_peaks"] = queue_peaks
            report["membership_phases"] = membership_phases
            report["source_unchanged_no_compile"] = True
            report["summary"] = sample_summary([row["visible_change_ms"] for row in report["samples"]])
            report["rss_after_typing_kib"] = rss_kib()
            window.grab().save(str(output / "after.png"))
            report["completed"] = True
    except BaseException as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        if window is not None and isValid(window):
            handle = window.windowHandle()
            report["failure_context"] = {"active": window.isActiveWindow(),
                "exposed": handle.isExposed() if handle else None,
                "application_state": app.applicationState().name,
                "focus_class": type(app.focusWidget()).__name__}
            window.grab().save(str(output / "failure.png"))
        raise
    finally:
        if window is not None and isValid(window):
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            window.close()
            QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            report["closed_window_destroyed"] = not isValid(window)
        report["rss_after_close_kib"] = rss_kib()
        report["app_hash_matches_after_run"] = source_digest() == report["app_sha256"]
        if not report.get("closed_window_destroyed") or not report["app_hash_matches_after_run"]:
            report["completed"] = False
            report.setdefault("failure", {"type": "AssertionError",
                "message": "Window was retained or application source changed during measurement"})
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        for handle in reversed(patches):
            handle.stop()
    assert report["completed"], report.get("failure")
    print(json.dumps({"output": str(output), "completed": report["completed"], "summary": report["summary"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--children", type=int, default=0)
    parser.add_argument("--key-interval-ms", type=int, default=0)
    parser.add_argument("--profile-keys", action="store_true")
    parser.add_argument("--profile-events", action="store_true")
    args = parser.parse_args()
    run(args.output, args.repetitions, children=args.children, key_interval_ms=args.key_interval_ms,
        profile_keys=args.profile_keys, profile_events=args.profile_events)
