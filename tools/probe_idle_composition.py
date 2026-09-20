"""Observe physical Pinyin partial commits under the real default save timer.

Only synthetic fixture setup is automated. Native desktop control must perform
input, partial commit, cancellation, Undo/Redo, optional Save and window close.
No save/input method is patched and no Qt key/input events are synthesized.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QSettings, QTimer
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.probe_history_restore import app_digest
from tools.probe_project_checkpoint_gui import close


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    project = output / "synthetic-project"
    project.mkdir()
    source = project / "main.tex"
    original = ("\\documentclass{ctexart}\n\\begin{document}\n"
                "Native idle input: base \n\\end{document}\n")
    source.write_text(original, encoding="utf-8")
    position = original.index("base ") + len("base ")
    application = QApplication([])
    assert application.platformName() == "cocoa"
    application.setQuitOnLastWindowClosed(False)
    application.setApplicationName("ICSTeX Native Idle QA")
    apply_theme(application)
    initial_hash = app_digest()
    window = MainWindow(settings_store=AppSettings(QSettings(
        str(output / "settings.ini"), QSettings.Format.IniFormat)))
    assert window.save_debounce_ms == 800
    window.auto_compile_action.setChecked(False)
    window.project_files.set_project_root(project)
    window.open_file(source)
    tab = window.current_tab()
    editor = tab.editor
    cursor = editor.textCursor()
    cursor.setPosition(position)
    editor.setTextCursor(cursor)
    window.resize(1320, 900)
    events, states, keys, timeouts = [], [], [], []
    started = time.monotonic()
    timeout = False
    manual_saves = 0
    compile_starts = []
    watched_save_timer = None
    previous_value = None
    last_recorded = -1.0

    def snapshot():
        raw = source.read_bytes()
        stat = source.stat()
        cursor = editor.textCursor()
        block = editor.document().begin()
        preedits = []
        while block.isValid():
            layout = block.layout()
            if layout is not None and layout.preeditAreaText():
                preedits.append({"block": block.blockNumber(),
                                "start": layout.preeditAreaPosition(),
                                "text": layout.preeditAreaText()})
            block = block.next()
        return {"text": editor.toPlainText(), "disk": raw.decode("utf-8"),
                "disk_sha256": hashlib.sha256(raw).hexdigest(),
                "disk_stat": [stat.st_ino, stat.st_size, stat.st_mtime_ns],
                "preedits": preedits, "source_revision": editor.source_revision,
                "cursor": cursor.position(), "anchor": cursor.anchor(),
                "scroll": editor.verticalScrollBar().value(),
                "undo_steps": editor.document().availableUndoSteps(),
                "redo_steps": editor.document().availableRedoSteps(),
                "dirty": tab.dirty, "modified": tab.modified,
                "conflict": tab.external_conflict,
                "save_timer_active": bool(tab.save_timer and tab.save_timer.isActive()),
                "save_timer_interval": tab.save_timer.interval() if tab.save_timer else None,
                "save_timeout_count": len(timeouts), "manual_saves": manual_saves,
                "event_count": len(events), "manager_created": tab.manager is not None,
                "compile_start_count": len(compile_starts),
                "auto_compile_enabled": window.auto_compile_action.isChecked()}

    def save_timeout():
        value = snapshot()
        value["seconds"] = round(time.monotonic() - started, 4)
        timeouts.append(value)
        print(json.dumps({"save_timeout": value}, ensure_ascii=False), flush=True)
        record_state("save-timeout")

    def record_state(cause="poll"):
        nonlocal watched_save_timer, previous_value, last_recorded
        if not isValid(window):
            return
        if tab.save_timer is not None and watched_save_timer is not tab.save_timer:
            watched_save_timer = tab.save_timer
            watched_save_timer.timeout.connect(save_timeout)
        value = snapshot()
        now = time.monotonic() - started
        changed = previous_value != value
        if changed or now - last_recorded >= 1.0:
            record = {"seconds": round(now, 4), "cause": cause, **value}
            states.append(record)
            if changed:
                filename = f"state-{len(states):04d}.png"
                window.grab().save(str(output / filename))
                record["image"] = filename
                print(json.dumps({"state": record}, ensure_ascii=False), flush=True)
            last_recorded, previous_value = now, value

    def manual_save():
        nonlocal manual_saves
        manual_saves += 1
        record_state("manual-save")

    window.save_action.triggered.connect(manual_save)

    def compile_started(root, build_id):
        compile_starts.append({"seconds": round(time.monotonic() - started, 4),
                               "root": root, "build_id": build_id})
        record_state("compile-started")

    window.signals.started.connect(compile_started)

    class Observer(QObject):
        def eventFilter(self, watched, event):
            if watched is not editor:
                return False
            if event.type() in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride):
                value = {"seconds": round(time.monotonic() - started, 4),
                         "type": event.type().name, "key": event.key(),
                         "modifiers": event.modifiers().value}
                keys.append(value)
                print(json.dumps({"native_key": value}), flush=True)
            if event.type() == QEvent.Type.InputMethod:
                value = {"seconds": round(time.monotonic() - started, 4),
                         "preedit": event.preeditString(), "commit": event.commitString(),
                         "replacement_start": event.replacementStart(),
                         "replacement_length": event.replacementLength()}
                events.append(value)
                print(json.dumps({"native_ime": value}, ensure_ascii=False), flush=True)
            if event.type() in (QEvent.Type.InputMethod, QEvent.Type.KeyPress):
                QTimer.singleShot(0, window, lambda: record_state("native-event"))
            return False

    observer = Observer(window)
    application.installEventFilter(observer)
    timer = QTimer(window)
    timer.setInterval(100)
    timer.timeout.connect(record_state)
    window.show()
    window.raise_()
    window.activateWindow()
    editor.setFocus()
    timer.start()
    record_state("ready")
    print("READY: physical partial commit; hold remainder; cancel; Undo/Redo; close", flush=True)
    try:
        while isValid(window):
            application.processEvents()
            if time.monotonic() - started > 600:
                timeout = True
                break
            time.sleep(0.01)
    finally:
        if isValid(window):
            record_state("cleanup")
            timer.stop()
            close(window)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    report = {"synthetic_only": True, "qt_platform": application.platformName(),
              "platform": platform.platform(), "python": platform.python_version(),
              "pyside": pyside_version, "save_debounce_ms": 800,
              "app_sha256": initial_hash, "app_sha256_after": app_digest(),
              "original": original, "insertion_position": position,
              "events": events, "states": states, "keys": keys, "save_timeouts": timeouts,
              "saved": source.read_text(encoding="utf-8"), "manual_saves": manual_saves,
              "compile_starts": compile_starts,
              "timeout": timeout, "window_destroyed": not isValid(window)}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"observation_completed": not timeout, "window_destroyed": report["window_destroyed"],
                      "events": len(events), "save_timeouts": len(timeouts)}, ensure_ascii=False), flush=True)
    # An observation receipt is not itself an acceptance decision.
    return 0 if not timeout and report["window_destroyed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
