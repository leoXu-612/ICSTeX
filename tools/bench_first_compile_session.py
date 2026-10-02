"""First explicit build and same-window auto-save/preview session on an isolated copy.

Offscreen widget pixels are an observation upper bound, not native/compositor
evidence. Project caches start empty; OS/font caches are not flushed. Run this
same evaluator with --source-repo pointing at each compared source checkout.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import gc
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import sys
import threading
import time
from unittest.mock import patch


def run(args):
    started = time.perf_counter()
    repo = args.source_repo.expanduser().resolve()
    source_root = args.project.expanduser()
    if source_root.is_symlink():
        raise ValueError("The project entry must not be a symlink")
    source_root = source_root.resolve(strict=True)
    output = args.output.expanduser().resolve()
    if output.is_relative_to(source_root.parent):
        raise ValueError("Evidence must be outside the original project")
    output.mkdir(parents=True, exist_ok=False)
    report = dict(completed=False, source_repo=str(repo), samples=[], builds=[], callback_errors=[],
        platform=platform.platform(), python=platform.python_version(), cycles=args.cycles,
        evaluator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        diagnostic_instrumentation=args.profile_phases,
        limits="Offscreen Qt pixels; synthetic edits, not physical input/native screen; empty project build/proxy caches, not OS cold cache; bounded session, not a leak test")
    window = app = probe = None
    previous_hook = sys.excepthook
    digest = None
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    sys.path.insert(0, str(repo))
    try:
        project = output / "project"
        shutil.copytree(source_root.parent, project, symlinks=True,
            ignore=shutil.ignore_patterns(".git", ".icstex", ".latex_build", "__pycache__", ".DS_Store"))
        if any(path.is_symlink() for path in project.rglob("*")):
            raise ValueError("Use a self-contained project without symlinks")
        root = project / source_root.name
        source = root.read_text(encoding="utf-8")
        report["original_entry_sha256"] = hashlib.sha256(source_root.read_bytes()).hexdigest()
        from PySide6.QtCore import QEvent, QObject, QSettings
        from PySide6.QtGui import QColor, QImage, QPainter, QTextCursor
        from PySide6.QtWidgets import QApplication
        from shiboken6 import isValid
        from app.core.compiler import BuildPurpose
        first_purpose = BuildPurpose(args.first_purpose)
        from app.core.settings import AppPreferences, AppSettings
        from app.gui.main_window import MainWindow
        from app.gui.theme import apply_theme
        from tools.bench_auto_compile_latency import marker_pixels, marker_source
        from tools.bench_dependency_membership import rss_kib
        from tools.bench_pdf_pipeline import PaintProbe, source_digest, wait_gui
        digest = source_digest
        assert Path(sys.modules["app"].__file__).resolve().parent == repo / "app"
        report["app_sha256"] = digest()
        report["first_purpose"] = first_purpose.value
        report["helper_sha256"] = {name: hashlib.sha256(Path(sys.modules[name].__file__).read_bytes()).hexdigest()
            for name in ("tools.bench_auto_compile_latency", "tools.bench_dependency_membership", "tools.bench_pdf_pipeline")}
        report["setup_and_import_ms"] = (time.perf_counter() - started) * 1000
        colors = ((17, 219, 153), (234, 18, 142), (171, 37, 231), (239, 133, 17), (31, 107, 233), (177, 199, 23))
        extra_colors = tuple(color for color in product(range(16, 241, 32), repeat=3)
            if max(color) - min(color) >= 128
            and all(max(abs(a - b) for a, b in zip(color, existing)) > 16 for existing in colors))
        colors += extra_colors[:max(0, args.cycles + 1 - len(colors))]
        assert len(colors) >= args.cycles + 1 and len(colors) == len(set(colors))
        check = QImage(120, 120, QImage.Format.Format_RGB32)
        check.fill(QColor("white"))
        assert marker_pixels(check, colors[0]) == 0
        painter = QPainter(check)
        painter.fillRect(20, 20, 60, 60, QColor(*colors[0]))
        painter.end()
        assert marker_pixels(check, colors[0]) > 20 and marker_pixels(check, colors[1]) == 0
        root.write_text(marker_source(source, colors[0]), encoding="utf-8")
        assert not any(path.name in {".icstex", ".latex_build"} for path in project.rglob("*"))
        settings = AppSettings(QSettings(str(output / "settings.ini"), QSettings.Format.IniFormat))
        preferences = AppPreferences(auto_compile=False, fast_preview=True)
        settings.save_preferences(preferences)
        report["settings"] = {key: getattr(preferences, key) for key in
            ("fast_preview", "save_debounce_ms", "compile_debounce_ms", "ui_scale")}
        QApplication.setDesktopSettingsAware(False)
        gui_start = time.perf_counter()
        app = QApplication([])
        app.setQuitOnLastWindowClosed(False)
        apply_theme(app)
        sys.excepthook = lambda kind, value, trace: report["callback_errors"].append(f"{kind.__name__}: {value}")
        window = MainWindow(settings_store=settings)
        window.resize(1440, 900)
        window.show()
        report["gui_construct_ms"] = (time.perf_counter() - gui_start) * 1000
        opened = time.perf_counter()
        window.project_files.set_project_root(project)
        window.open_file(root)
        editor = window.current_tab().editor
        window.source_preview_area.select_pdf(True)
        report["project_open_call_ms"] = (time.perf_counter() - opened) * 1000
        assert not window.compile_authorized_roots

        class CurrentPaint(PaintProbe):
            target = colors[0]
            purpose = first_purpose

            def observe(self):
                self.pending = False
                result = self.events.get("result")
                displayed = window.displayed_pdfs.get(root)
                if (result is None or not result.ok or result.root_file != root
                        or result.purpose is not self.purpose
                        or not self.viewport.isVisible() or window.pdf_panel.current_pdf != result.pdf_file
                        or displayed is None or displayed.root_file != root
                        or displayed.build_id != result.build_id or displayed.purpose is not self.purpose
                        or displayed.revision != result.job_key.source_revision
                        or result.job_key.source_revision != window.pdf_state.record_for(root).source_revision):
                    return
                self.capturing = True
                try:
                    grab_begin = time.perf_counter()
                    image = self.viewport.grab().toImage()
                    grab_end = time.perf_counter()
                    pixels = marker_pixels(image, self.target)
                    scan_end = time.perf_counter()
                finally:
                    self.capturing = False
                if pixels > 20:
                    self.events.update(grab_begin=grab_begin, grab_end=grab_end, scan_end=scan_end)
                    self.events["visible_content_observed"] = time.perf_counter()
                    self.events["marker_pixels"] = pixels

        probe = CurrentPaint(window, None)
        original_finished, original_auto = window.compile._emit_finished, window.compile.compile_for_root

        def finished(manager, result):
            probe.events["result"] = result
            probe.events["worker_finished"] = time.perf_counter()
            report["builds"].append(dict(build_id=result.build_id, purpose=result.purpose.value,
                revision=result.job_key.source_revision, outcome=result.outcome.value))
            return original_finished(manager, result)

        def auto(*a, **kw):
            probe.events.setdefault("auto_requested", time.perf_counter())
            return original_auto(*a, **kw)

        window.signals.started.connect(lambda *_: probe.events.setdefault("compiler_started", time.perf_counter()))
        window.dependencies.membership_metrics_hook = lambda row: probe.events.setdefault("membership", []).append(row)

        def resources():
            return dict(rss_kib=rss_kib(), python_gc_objects=len(gc.get_objects()),
                window_qobjects=len(window.findChildren(QObject)), python_threads=threading.active_count())

        def timed(name, method):
            def measured(*a, **kw):
                tick = time.perf_counter()
                try:
                    return method(*a, **kw)
                finally:
                    probe.events.setdefault("phases_ms", {}).setdefault(name, []).append((time.perf_counter() - tick) * 1000)
            return measured

        def wait_visible():
            result = probe.events.get("result")
            if report["callback_errors"] or (result is not None and not result.ok):
                raise RuntimeError("Qt callback or compile failed; inspect retained report and fixture logs")
            return "visible_content_observed" in probe.events

        with ExitStack() as stack:
            stack.enter_context(patch.object(window.compile, "_emit_finished", finished))
            stack.enter_context(patch.object(window.compile, "compile_for_root", auto))
            if args.profile_phases:
                for owner, name in ((window.compile, "_prepare_preview"), (window.compile, "on_finished"),
                        (window.project_panels, "run_project_check"), (window.dependencies, "_apply_memberships"),
                        (window.pdf_panel, "load_pdf")):
                    stack.enter_context(patch.object(owner, name, timed(name, getattr(owner, name))))
            for cycle in range(args.cycles + 1):
                probe.target = colors[cycle % len(colors)]
                probe.purpose = first_purpose if cycle == 0 else BuildPurpose.PREVIEW
                previous_frame_target_pixels = None
                if cycle == 0:
                    probe.reset("first-" + first_purpose.value)
                    window.compile_current(immediate=True, purpose=first_purpose)
                else:
                    # A color already present in the old frame cannot prove this revision painted.
                    probe.capturing = True
                    try:
                        previous_frame_target_pixels = marker_pixels(probe.viewport.grab().toImage(), probe.target)
                    finally:
                        probe.capturing = False
                    assert previous_frame_target_pixels == 0, (
                        f"Old frame contains next marker color {probe.target}: {previous_frame_target_pixels} samples")
                    # Change only the marker digits through the real editor undo/save path.
                    old = ",".join(map(str, colors[(cycle - 1) % len(colors)]))
                    needle = "\\color[RGB]{" + old + "}"
                    text = editor.toPlainText()
                    assert text.count(needle) == 1
                    offset = text.index(needle) + len("\\color[RGB]{")
                    position = len(text[:offset].encode("utf-16-le")) // 2
                    cursor = editor.textCursor()
                    cursor.setPosition(position)
                    cursor.setPosition(position + len(old), QTextCursor.MoveMode.KeepAnchor)
                    editor.setTextCursor(cursor)
                    probe.reset(f"auto-{cycle}")
                    editor.insertPlainText(",".join(map(str, probe.target)))
                view_state = editor.textCursor().position(), editor.verticalScrollBar().value()
                wait_gui(wait_visible, timeout=180)
                events, result = probe.events, probe.events["result"]
                assert root.read_text(encoding="utf-8") == editor.toPlainText()
                assert view_state == (editor.textCursor().position(), editor.verticalScrollBar().value())
                row = dict(cycle=cycle, first_compile=cycle == 0, build_id=result.build_id,
                    revision=result.job_key.source_revision, purpose=result.purpose.value,
                    event_to_visible_ms=(events["visible_content_observed"] - events["request"]) * 1000,
                    compiler_reported_ms=result.duration_seconds * 1000,
                    marker_pixels=events["marker_pixels"], pages=window.pdf_panel._document.pageCount(),
                    previous_frame_target_pixels=previous_frame_target_pixels,
                    grab_ms=(events["grab_end"] - events["grab_begin"]) * 1000,
                    scan_ms=(events["scan_end"] - events["grab_end"]) * 1000,
                    phases_ms=events.get("phases_ms", {}), membership=events.get("membership", []),
                    event_offsets_ms={key: (value - events["request"]) * 1000 for key, value in events.items()
                        if isinstance(value, float)}, cursor_scroll_preserved=True)
                if cycle == 0:
                    report["project_open_to_first_visible_ms"] = (events["visible_content_observed"] - opened) * 1000
                    report["gui_start_to_first_visible_ms"] = (events["visible_content_observed"] - gui_start) * 1000
                else:
                    row["auto_request_to_visible_ms"] = (events["visible_content_observed"] - events["auto_requested"]) * 1000
                report["samples"].append(row)
                wait_gui(lambda: not window.dependencies.is_busy and not window.current_tab().manager.is_busy
                    and not window.word_counts.is_busy, timeout=60)
                row["settled_resources"] = resources()
                print(json.dumps(row), flush=True)
                if cycle == 0:
                    window.auto_compile_action.setChecked(True)
        values = [row["event_to_visible_ms"] for row in report["samples"][1:]]
        report["session_summary_ms"] = dict(median=statistics.median(values), max=max(values), count=len(values))
        assert len(report["builds"]) == args.cycles + 1, "Unexpected duplicate compile"
        report["completed"] = not report["callback_errors"]
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        if probe is not None:
            report["failure_state"] = probe.snapshot()
            report["failure_events"] = {key: value for key, value in probe.events.items() if key != "result"}
            result = probe.events.get("result")
            if result is not None:
                report["compile_failure"] = dict(outcome=result.outcome.value, returncode=result.returncode,
                    log_file=str(result.log_file), build_id=result.build_id)
        raise
    finally:
        try:
            if window is not None:
                window.auto_compile_action.setChecked(False)
                for tab in window.tabs.values():
                    window.documents.cancel_save_timer(tab)
                    tab.modified = tab.dirty = False
                assert window.close(), "Owned probe window failed to close"
                app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                report["window_destroyed"] = not isValid(window)
            if digest is not None:
                report["app_sha256_after"] = digest()
                report["source_unchanged"] = report["app_sha256"] == report["app_sha256_after"]
            report["original_entry_sha256_after"] = hashlib.sha256(source_root.read_bytes()).hexdigest()
            report["original_unchanged"] = report.get("original_entry_sha256") == report["original_entry_sha256_after"]
            report["completed"] = bool(report["completed"] and report.get("window_destroyed")
                and report.get("source_unchanged") and report["original_unchanged"])
        except BaseException as exc:
            report["completed"] = False
            report["cleanup_error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            report["elapsed_seconds"] = time.perf_counter() - started
            (output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            sys.excepthook = previous_hook
    assert (report["completed"] and report["window_destroyed"]
            and report["source_unchanged"] and report["original_unchanged"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cycles", type=int, default=6)
    parser.add_argument("--first-purpose", choices=("final", "preview"), default="final",
                        help="FINAL matches the normal toolbar's first explicit build")
    parser.add_argument("--profile-phases", action="store_true", help="Diagnostic timings, separate from acceptance samples")
    args = parser.parse_args()
    if not 1 <= args.cycles <= 100:
        parser.error("Use 1..100 bounded session cycles")
    run(args)
