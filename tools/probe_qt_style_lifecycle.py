"""Bounded diagnostic for closed-window lifetime and Qt repolish.

Creates only disposable empty windows with isolated settings. No application
source patch, student project, compile, network or installed app. Offscreen by
default; --native requires explicit Cocoa selection and foreground permission.
Optional forced GC during StyleChange is fault injection, not normal-use proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
import faulthandler
import gc
import json
import os
from pathlib import Path
import sys
import time
import weakref

try:
    import resource
except ImportError:  # The subprocess regression also runs on Windows.
    resource = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QLabel
from shiboken6 import isValid

from app.gui.theme import apply_theme
from tools.probe_history_restore import app_digest
from tools.bench_dependency_membership import rss_kib
from tools.probe_project_checkpoint_gui import window_for


def run(output, mode, windows, cycles, forced_gc, native=False, expect_released=False,
        orphan_widgets=0, hold_style_widgets=False):
    backend = "cocoa" if native else "offscreen"
    if os.environ.get("QT_QPA_PLATFORM") != backend:
        raise SystemExit(f"Requires QT_QPA_PLATFORM={backend}; native also requires --native")
    if not 1 <= windows <= 30 or not 1 <= cycles <= 20:
        raise SystemExit("Bounded diagnostic: 1..30 windows, 1..20 cycles")
    if not 0 <= orphan_widgets <= 30 or (orphan_widgets and not forced_gc):
        raise SystemExit("0..30 cyclic orphan widgets require explicit forced GC")
    faulthandler.enable()
    output = output.expanduser().resolve()
    output.mkdir(exist_ok=False)
    digest = app_digest()
    print(json.dumps({"event": "start", "pid": os.getpid(), "app_sha256": digest,
                      "orphan_widgets": orphan_widgets, "hold_style_widgets": hold_style_widgets}), flush=True)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    assert app.platformName() == backend
    state = {"phase": "setup", "collections": 0, "style_collections": 0}
    orphan_deletions, orphan_refs = [], []
    records, refs = [], []

    def gc_observation(phase, info):
        if phase == "start":
            state["collections"] += 1
            if state["phase"].startswith("scale"):
                state["style_collections"] += 1
                frame = sys._getframe().f_back
                names = []
                while frame is not None and len(names) < 6:
                    names.append(frame.f_code.co_name)
                    frame = frame.f_back
                print(json.dumps({"event": "gc_in_scale", "phase": state["phase"],
                                  "generation": info["generation"], "frames": names}), flush=True)

    class CollectOnStyle(QObject):
        active = False

        def eventFilter(self, watched, event):
            if forced_gc and event.type() == QEvent.Type.StyleChange and not self.active:
                self.active = True
                try:
                    print(json.dumps({"event": "forced_gc_in_style"}), flush=True)
                    gc.collect()
                finally:
                    self.active = False
            return False

    sentinel = window_for(output, "sentinel")
    if native:
        sentinel.show()
        app.processEvents()
        assert sentinel.grab().save(str(output / "surviving-window-before.png"))
    collector = CollectOnStyle(sentinel)
    sentinel.installEventFilter(collector)
    gc.callbacks.append(gc_observation)
    auto_gc = gc.isenabled()

    def orphan_destroyed(index):
        row = {"event": "orphan_destroyed", "index": index, "phase": state["phase"]}
        orphan_deletions.append(row)
        print(json.dumps(row), flush=True)

    if orphan_widgets:
        # Deliberately defer collection of synthetic cycles to the first style
        # callback. This is fault injection, never a production GC policy.
        gc.disable()
        for index in range(orphan_widgets):
            orphan = QLabel(f"Synthetic orphan {index}")
            orphan.ensurePolished()
            orphan.cycle = orphan
            orphan_refs.append(weakref.ref(orphan))
            orphan.destroyed.connect(lambda _obj=None, i=index: orphan_destroyed(i))
            del orphan

    def snapshot(label):
        state["phase"] = "snapshot-" + label
        kinds = Counter(type(widget).__name__ for widget in app.allWidgets())
        row = {"phase": label, "widgets": sum(kinds.values()),
               "top_levels": len(app.topLevelWidgets()), "main_windows": kinds["MainWindow"],
               "live_closed_wrappers": sum(ref() is not None and isValid(ref()) for ref in refs),
               "live_orphan_wrappers": sum(ref() is not None and isValid(ref()) for ref in orphan_refs),
               "max_rss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None,
               "current_rss_kib": rss_kib() if sys.platform == "darwin" else None,
               "collections": state["collections"], "style_collections": state["style_collections"]}
        records.append(row)
        print(json.dumps(row), flush=True)

    try:
        snapshot("baseline")
        for cycle in range(cycles):
            state["phase"] = f"create-{cycle}"
            for index in range(windows):
                window = window_for(output, f"window-{cycle}-{index}")
                refs.append(weakref.ref(window))
                if native:
                    window.show()
                    app.processEvents()
                assert window.close()
                if mode == "delete":
                    window.deleteLater()
                del window
            # Model the event-loop boundary in either mode. An accepted close
            # must enqueue its own destruction; delete mode is the control.
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            snapshot(f"closed-{cycle}")
            if expect_released:
                assert records[-1]["live_closed_wrappers"] == 0, records[-1]
                assert records[-1]["main_windows"] == 1, records[-1]
            for scale in (1.25, 1.0, 1.5, 1.0):
                state["phase"] = f"scale-{cycle}-{scale}"
                print(json.dumps({"event": "scale_start", "phase": state["phase"]}), flush=True)
                started = time.perf_counter()
                # Diagnostic control: retain wrappers while Qt traverses its
                # raw widget pointers. No change to the application manager.
                keep_alive = app.allWidgets() if hold_style_widgets else None
                app.ui_scale_manager.apply_scale(scale)
                del keep_alive
                print(json.dumps({"event": "scale_end", "phase": state["phase"],
                                  "seconds": time.perf_counter() - started}), flush=True)
            snapshot(f"scaled-{cycle}")
        state["phase"] = "final-gc"
        gc.collect()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        snapshot("after-final-gc")
        if native:
            app.processEvents()
            assert sentinel.grab().save(str(output / "surviving-window-after.png"))
        assert app_digest() == digest
        result = {"app_sha256": digest, "backend": backend, "mode": mode, "windows": windows, "cycles": cycles,
                  "forced_gc_fault_injection": forced_gc, "pid": os.getpid(), "rows": records,
                  "orphan_widgets": orphan_widgets, "hold_style_widgets": hold_style_widgets,
                  "orphan_deletions": orphan_deletions,
                  "limits": f"Empty synthetic {backend} windows; forced GC is fault injection, not general lifecycle acceptance"}
        (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    finally:
        if auto_gc:
            gc.enable()
        gc.callbacks.remove(gc_observation)
        sentinel.close()
        sentinel.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("close", "delete"), default="close")
    parser.add_argument("--windows", type=int, default=8)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--collect-during-style", action="store_true")
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--expect-released", action="store_true")
    parser.add_argument("--orphan-widgets", type=int, default=0)
    parser.add_argument("--hold-style-widgets", action="store_true")
    args = parser.parse_args()
    run(args.output, args.mode, args.windows, args.cycles, args.collect_during_style,
        args.native, args.expect_released, args.orphan_widgets, args.hold_style_widgets)
