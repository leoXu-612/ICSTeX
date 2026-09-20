"""Synthetic large-image and native visible-PDF pipeline probe.

QT_QPA_PLATFORM=cocoa python3 tools/bench_pdf_pipeline.py --output report.json
The observed first nonblank viewport is an upper bound sampled after a real
paint event; it is not a hardware/compositor presentation timestamp. Only
temporary fixtures and explicitly requested evidence files are written.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import re
import statistics
import shutil
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QEvent, QObject, QSettings, QTimer, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.core.compiler import BuildPurpose
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from app.core.paths import preview_assets_dir_for
from app.core.settings import AppSettings
from app.gui import image_proxy_cache
from app.gui.main_window import MainWindow


def wait_gui(predicate, timeout=60):
    deadline = time.perf_counter() + timeout
    while not predicate() and time.perf_counter() < deadline:
        QApplication.processEvents()
        time.sleep(0.001)
    assert predicate(), "Probe timed out"


def source_digest():
    digest = hashlib.sha256()
    for source in sorted((REPO / "app").rglob("*.py")):
        digest.update(source.relative_to(REPO).as_posix().encode() + b"\0")
        digest.update(source.read_bytes() + b"\0")
    return digest.hexdigest()


def make_project(base):
    root = base / "main.tex"
    width, height = 6000, 4000
    pixels = random.Random(20260908).randbytes(width * height * 3)
    image = QImage(pixels, width, height, width * 3, QImage.Format.Format_RGB888).copy()
    painter = QPainter(image)
    painter.fillRect(0, 0, width // 2, height // 2, QColor(220, 25, 35))
    painter.end()
    assert image.save(str(base / "noise.jpg"), "JPEG", 93)
    assert image.save(str(base / "noise.png"), "PNG")
    root.write_text(
        "\\documentclass{article}\n\\usepackage{graphicx}\n"
        "\\begin{document}\nSynthetic 24 MP image pipeline probe.\\par\n"
        "\\includegraphics[width=.85\\linewidth]{noise.jpg}\n\\newpage\n"
        "\\includegraphics[width=.85\\linewidth]{noise.png}\n\\end{document}\n",
        encoding="utf-8",
    )
    return root, {path.name: path.stat().st_size for path in (base / "noise.jpg", base / "noise.png")}


def image_probe(root):
    cache = image_proxy_cache.ImageProxyCache()
    overlay = preview_assets_dir_for(root)
    report = []
    for case in ("cold", "warm", "warm", "warm", "warm", "warm"):
        phases = {}

        def instrument(name, function):
            def call(*args, **kwargs):
                started = time.perf_counter()
                try:
                    return function(*args, **kwargs)
                finally:
                    item = phases.setdefault(name, {"calls": 0, "ms": 0})
                    item["calls"] += 1
                    item["ms"] += (time.perf_counter() - started) * 1000
            return call

        with patch.object(image_proxy_cache, "_sha256_file", instrument("hash", image_proxy_cache._sha256_file)), \
             patch.object(image_proxy_cache, "_read_proxy_image", instrument("decode_scale", image_proxy_cache._read_proxy_image)), \
             patch.object(image_proxy_cache, "_write_proxy_atomic", instrument("proxy_write_including_decode_hash", image_proxy_cache._write_proxy_atomic)):
            started = time.perf_counter()
            result = cache.prepare(root, overlay)
            duration = (time.perf_counter() - started) * 1000
        report.append({
            "case": case, "duration_ms": round(duration, 3),
            "proxy_count": result.proxy_count, "fallback_count": result.fallback_count,
            "phases": {name: {"calls": value["calls"], "ms": round(value["ms"], 3)} for name, value in phases.items()},
        })
    return {
        "samples": report,
        "warm_median_ms": round(statistics.median(item["duration_ms"] for item in report[1:]), 3),
        "proxy_bytes": {path.name: path.stat().st_size for path in overlay.iterdir() if path.is_file()},
    }


class PaintProbe(QObject):
    def __init__(self, window, screenshot_dir):
        super().__init__(window)
        self.window = window
        self.viewport = window.pdf_panel._view.viewport()
        self.screenshot_dir = screenshot_dir
        self.events = {}
        self.pending = self.capturing = False
        self.case = ""
        self.transitions = deque(maxlen=64)
        window.pdf_panel.viewChanged.connect(self._view_changed)
        self.viewport.installEventFilter(self)
        self.window.installEventFilter(self)
        if window.windowHandle() is not None:
            window.windowHandle().installEventFilter(self)
        window.pdf_panel._document.statusChanged.connect(self.status_changed)

    def _view_changed(self, view):
        self.viewport.removeEventFilter(self)
        self.viewport = view.viewport()
        self.viewport.installEventFilter(self)

    def reset(self, case):
        self.case = case
        self.events = {"request": time.perf_counter()}
        self.transitions.clear()
        self.ready_state = None
        self.start_state = self.snapshot()

    def snapshot(self):
        """Test-owned state only; visibility is not native exposure or paint."""
        handle = self.window.windowHandle()
        panel = self.window.pdf_panel
        tab = self.window.current_tab()
        modal = QApplication.activeModalWidget()
        return {
            "case": self.case,
            "window_visible": self.window.isVisible(),
            "window_active": self.window.isActiveWindow(),
            "window_exposed": handle.isExposed() if handle is not None else None,
            "window_minimized": self.window.isMinimized(),
            "application_state": QApplication.applicationState().name,
            "modal_class": type(modal).__name__ if modal is not None else None,
            "viewport_visible": self.viewport.isVisible(),
            "viewport_size": [self.viewport.width(), self.viewport.height()],
            "viewport_dpr": self.viewport.devicePixelRatioF(),
            "document_status": panel._document.status().name,
            "pages": panel._document.pageCount(),
            "current_pdf": str(panel.current_pdf) if panel.current_pdf else None,
            "active_root": str(self.window._compile_root_for_tab(tab)) if tab else None,
            "observation_pending": self.pending,
        }

    def status_changed(self, status):
        self.transitions.append({"event": "document_" + status.name, "at": time.perf_counter()})
        if status == QPdfDocument.Status.Ready and "request" in self.events:
            self.events.setdefault("document_ready", time.perf_counter())
            self.ready_state = self.snapshot()

    def eventFilter(self, watched, event):
        if event.type() in {QEvent.Type.Paint, QEvent.Type.Show, QEvent.Type.Hide,
                            QEvent.Type.Expose, QEvent.Type.WindowActivate,
                            QEvent.Type.WindowDeactivate} and not self.capturing:
            self.transitions.append({"event": event.type().name,
                "target": "viewport" if watched is self.viewport else type(watched).__name__,
                "at": time.perf_counter()})
        if (watched is self.viewport and event.type() == QEvent.Type.Paint
                and not self.capturing and not self.pending
                and "document_ready" in self.events and "visible_content_observed" not in self.events):
            self.events.setdefault("first_paint_event", time.perf_counter())
            self.pending = True
            QTimer.singleShot(0, self, self.observe)
        return False

    def observe(self):
        self.pending = False
        if not self.viewport.isVisible() or "visible_content_observed" in self.events:
            return
        self.capturing = True
        grab_started = time.perf_counter()
        image = self.viewport.grab().toImage()
        grab_finished = time.perf_counter()
        self.capturing = False
        # The synthetic red region distinguishes rendered PDF content from
        # white pages, gray placeholders, and black UI/text pixels.
        red = sum(
            1 for y in range(0, image.height(), 12) for x in range(0, image.width(), 12)
            if (color := image.pixelColor(x, y)).red() > 150
            and color.green() < 90 and color.blue() < 110
        )
        self.events.setdefault("observations", []).append({
            "grab_started": grab_started, "grab_finished": grab_finished,
            "scan_finished": time.perf_counter(), "red_samples": red})
        if red > 20:
            self.events["visible_content_observed"] = time.perf_counter()
            self.events["red_samples"] = red
            if self.screenshot_dir:
                self.screenshot_dir.mkdir(parents=True, exist_ok=True)
                path = self.screenshot_dir / f"{self.case}.png"
                assert self.window.grab().save(str(path))
                self.events["screenshot"] = str(path)


def visible_probe(root, screenshot_dir, *, reports=None):
    tools = detect_toolchain()
    assert tools.latexmk and tools.xelatex, "Existing latexmk and XeLaTeX required"
    settings = AppSettings(QSettings(str(root.parent / "settings.ini"), QSettings.Format.IniFormat))
    window = MainWindow(settings_store=settings)
    window.auto_compile_action.setChecked(False)
    window.current_engine = LaTeXEngine.XELATEX
    window.open_file(root)
    window.setWindowTitle(f"ICSTeX - SYNTHETIC PDF PROBE - {os.getpid()}")
    window.resize(1440, 920)
    window.show()
    window.raise_()
    wait_gui(lambda: window.isVisible())
    if QApplication.platformName() == "cocoa":
        window.activateWindow()
        wait_gui(lambda: window.windowHandle().isExposed() and window.isActiveWindow(), timeout=10)
    wait_gui(lambda: not window.word_counts.is_busy and not window.dependencies.is_busy)
    probe = PaintProbe(window, screenshot_dir)
    if reports is None:
        reports = []
    try:
        tab = window.current_tab()
        tab.manager = window.create_compile_manager(root)
        manager = tab.manager
        original_finished = manager.on_finished
        original_run = window.compile.on_finished
        original_load = window.pdf_panel.load_pdf
        original_popen = __import__("subprocess").Popen

        def popen(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            command = args[0] if args else kwargs.get("args", [])
            if not command or str(command[0]) != tools.latexmk:
                return process
            communicate = process.communicate

            def measured(*args, **kwargs):
                result = communicate(*args, **kwargs)
                probe.events["process_exit_observed"] = time.perf_counter()
                return result

            process.communicate = measured
            return process

        def finished(result):
            probe.events["worker_result"] = time.perf_counter()
            probe.events["result"] = result
            original_finished(result)

        def accepted(result):
            probe.events["artifact_callback"] = time.perf_counter()
            return original_run(result)

        def load(path, **kwargs):
            probe.events["artifact_accepted"] = time.perf_counter()
            returned = original_load(path, **kwargs)
            probe.events["load_returned"] = time.perf_counter()
            if window.pdf_panel.last_load_reused:
                # Reused verified bytes are already displayed. No fresh Ready
                # or Paint event is required; record that distinct path.
                probe.events["document_reused"] = time.perf_counter()
                probe.events["document_ready"] = time.perf_counter()
                probe.pending = True
                QTimer.singleShot(0, probe, probe.observe)
            return returned

        manager.on_finished = finished
        with patch("app.core.compiler.subprocess.Popen", side_effect=popen), \
             patch.object(window.compile, "on_finished", side_effect=accepted), \
             patch.object(window.pdf_panel, "load_pdf", side_effect=load):
            for case, purpose in (("preview_cold_build", BuildPurpose.PREVIEW),
                                  ("preview_unchanged", BuildPurpose.PREVIEW),
                                  ("final_cold_build", BuildPurpose.FINAL),
                                  ("final_unchanged", BuildPurpose.FINAL),
                                  ("preview_text_edit", BuildPurpose.PREVIEW)):
                if case == "preview_text_edit":
                    tab.editor.insertPlainText("% synthetic edit\n")
                    window.documents.cancel_save_timer(tab)
                probe.reset(case)
                window.compile_current(immediate=True, purpose=purpose)
                try:
                    wait_gui(lambda: "visible_content_observed" in probe.events, timeout=90)
                except AssertionError:
                    print({key: value for key, value in probe.events.items() if key != "result"}, file=sys.stderr)
                    print("status:", window.statusBar().currentMessage(), file=sys.stderr)
                    print("result:", probe.events.get("result"), file=sys.stderr)
                    print("viewport:", probe.viewport.isVisible(), probe.viewport.size(), file=sys.stderr)
                    if screenshot_dir:
                        screenshot_dir.mkdir(parents=True, exist_ok=True)
                        failure = {
                            "case": case, "status": "failed", "reason": "visible-content timeout",
                            "events": {key: value for key, value in probe.events.items() if key != "result"},
                            "start_state": probe.start_state,
                            "ready_state": getattr(probe, "ready_state", None),
                            "timeout_state": probe.snapshot(),
                            "transitions": list(probe.transitions),
                        }
                        (screenshot_dir / "incomplete-state.json").write_text(
                            json.dumps(failure, indent=2) + "\n", encoding="utf-8")
                        window.grab().save(str(screenshot_dir / "incomplete-probe.png"))
                        result = probe.events.get("result")
                        if result is not None:
                            for path in (result.pdf_file, result.log_file):
                                if path is not None and path.is_file():
                                    shutil.copy2(path, screenshot_dir / ("incomplete-" + path.name))
                    raise
                result = probe.events["result"]
                assert result.ok
                origin = probe.events["request"]
                timeline = {key: round((value - origin) * 1000, 3) for key, value in probe.events.items() if key in {
                    "process_exit_observed", "worker_result", "artifact_callback", "artifact_accepted", "document_ready", "document_reused", "load_returned", "first_paint_event", "visible_content_observed",
                }}
                reports.append({
                    "case": case, "purpose": purpose.value, "timeline_from_request_ms": timeline,
                    "proxy_cache_state": "warm; separate cold preparation measured above",
                    "exit_to_visible_ms": round((probe.events["visible_content_observed"] - probe.events["process_exit_observed"]) * 1000, 3),
                    "pages": window.pdf_panel._document.pageCount(),
                    "red_samples": probe.events["red_samples"],
                    "screenshot": probe.events.get("screenshot"),
                    "pdf_bytes": result.pdf_file.stat().st_size,
                    "displayed_path_matches_result": window.pdf_panel.current_pdf == result.pdf_file,
                    "purpose_output_isolated": manager.preview_output_dir != manager.output_dir,
                    "forced_rebuild": "-g" in result.command,
                    "rules": re.findall(r"Run number \d+ of rule '([^']+)'", result.stdout),
                    "pdf_sha256": hashlib.sha256(result.pdf_file.read_bytes()).hexdigest(),
                    "native_visible": window.isVisible() and QApplication.platformName() not in {"offscreen", "minimal"},
                    "verified_document_reused": "document_reused" in probe.events,
                    "start_state": probe.start_state,
                    "visible_state": probe.snapshot(),
                    "transitions": list(probe.transitions),
                    "observation_costs_ms": [{"grab_ms": (item["grab_finished"] - item["grab_started"]) * 1000,
                        "scan_ms": (item["scan_finished"] - item["grab_finished"]) * 1000,
                        "paint_to_grab_start_ms": ((item["grab_started"] - probe.events["first_paint_event"]) * 1000
                                                   if "first_paint_event" in probe.events else None),
                        "red_samples": item["red_samples"]} for item in probe.events.get("observations", ())],
                })
                wait_gui(lambda: not manager.is_busy)
    finally:
        for tab in window.tabs.values():
            window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        assert window.close(), "Synthetic clean window refused close"
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(window), "Accepted window retained its Qt object"
        QApplication.processEvents()
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--trials", type=int, default=1)
    args = parser.parse_args()
    if args.output.exists() or (args.screenshots is not None and args.screenshots.exists()):
        parser.error("Select new output and screenshot paths; previous evidence is retained")
    app = QApplication.instance() or QApplication([])
    assert 1 <= args.trials <= 5, "Use one to five bounded synthetic trials"
    # The benchmark deliberately creates another window after closing the last
    # one. A real single-window app would exit at that boundary instead.
    app.setQuitOnLastWindowClosed(False)
    report = {
        "app_python_tree_sha256": source_digest(), "platform": platform.platform(),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(), "pyside6": importlib.metadata.version("PySide6"),
        "pid": os.getpid(), "completed": False,
        "screens": [{"name": screen.name(), "geometry": list(screen.geometry().getRect()),
                     "available_geometry": list(screen.availableGeometry().getRect()),
                     "dpr": screen.devicePixelRatio(), "refresh_hz": screen.refreshRate()}
                    for screen in app.screens()],
        "qt_platform": app.platformName(), "display_sampling_interval_ms": 1,
        "first_visible_definition": "Upper bound: nonblank viewport grab after native Paint; includes observation overhead, not compositor scanout",
        "fixture": "Two deterministic 24 MP RGB noise images with red region, JPEG quality 93 and PNG; synthetic decode/IO stress, not a typical student project",
    }
    report["trials"] = []
    try:
        for trial in range(args.trials):
            with TemporaryDirectory(prefix="icstex-pdf-probe-") as directory:
                root, sizes = make_project(Path(directory).resolve())
                item = {"trial": trial, "original_bytes": sizes, "visible_pdf": [], "completed": False}
                report["trials"].append(item)
                print(f"Trial {trial}: measuring image preparation...", file=sys.stderr, flush=True)
                item["image_preparation"] = image_probe(root)
                print(f"Trial {trial}: measuring visible PDF pipeline...", file=sys.stderr, flush=True)
                screenshots = args.screenshots / f"trial-{trial}" if args.screenshots else None
                visible_probe(root, screenshots, reports=item["visible_pdf"])
                item.update(completed=True, closed_window_destroyed=True)
        assert source_digest() == report["app_python_tree_sha256"], "Shared app source changed during measurement"
        report["completed"] = True
    except BaseException as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        report["app_hash_matches_after_run"] = source_digest() == report["app_python_tree_sha256"]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
