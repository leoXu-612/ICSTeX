"""Observe physical keyboard creation/delivery/recovery in synthetic native UI.

The QA menu opens only fixture windows or changes scale. It never generates
keys, changes dialog fields, confirms dialogs or compiles on the operator's
behalf. Production actions own all workflow writes and compilation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QEvent, QObject, QPoint, QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QDialog,
    QLabel, QLineEdit, QPlainTextEdit, QTabWidget, QTextEdit, QTreeWidget, QWidget)
from shiboken6 import isValid

from app.core.blocks.project_repository import load_project
from app.gui.blocks.project_dialog import BlockProjectDialog
from app.gui.theme import apply_theme
from tests.v1_fixtures import create_project
from tools.probe_history_restore import app_digest
from tools.probe_project_checkpoint_gui import close, window_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=1800)
    parser.add_argument("--existing-synthetic-project", type=Path,
                        help="Reopen a retained synthetic main.tex without compiling")
    args = parser.parse_args()
    assert os.environ.get("QT_QPA_PLATFORM") == "cocoa"
    output = args.output.expanduser().resolve()
    output.mkdir(exist_ok=False)
    (output / "projects").mkdir()
    block = create_project(output / "fixtures", "block")
    application = QApplication([])
    assert application.platformName() == "cocoa"
    application.setQuitOnLastWindowClosed(False)
    apply_theme(application)
    window = window_for(output, "keyboard")
    if args.existing_synthetic_project:
        source = args.existing_synthetic_project.expanduser().resolve()
        window.project_files.set_project_root(source.parent)
        window.open_file(source)
    window.setWindowTitle("ICSTeX - SYNTHETIC MODAL KEYBOARD QA")
    windows = [window]
    states, keys, actions, errors, destroyed = [], [], [], [], []
    start, source_hash = time.monotonic(), app_digest()
    interrupted = timed_out = False

    def elapsed():
        return round(time.monotonic() - start, 3)

    def action(name):
        actions.append({"seconds": elapsed(), "name": name})

    for name in ("new_project_action", "project_profile_action", "prepare_submission_action",
                 "project_checkpoint_action", "restore_checkpoint_action", "migrate_project_action",
                 "save_action", "compile_action", "recovery_drafts_action"):
        getattr(window, name).triggered.connect(lambda _checked=False, name=name: action(name))

    def standalone():
        loaded = load_project(block.root.parent)
        owner = BlockProjectDialog(registry=loaded["registry"], layout=loaded["layout"],
            document_theme=loaded["document_theme"], project_dir=block.root.parent)
        windows.append(owner)
        owner.setWindowTitle("SYNTHETIC standalone Block keyboard QA")
        owner.show()
        action("fixture_standalone_open")

    def finish():
        action("qa_finish")
        application.quit()

    menu = window.menuBar().addMenu("Synthetic QA")
    for text, callback in (("Open standalone Block fixture", standalone),
                           ("UI 100%", lambda: window.set_ui_scale(1.0)),
                           ("UI 150%", lambda: window.set_ui_scale(1.5)),
                           ("Finish keyboard QA", finish)):
        item = QAction(text, window)
        item.triggered.connect(callback)
        menu.addAction(item)

    def scalar(value):
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, (str, int, bool, float, type(None))):
            return value
        if hasattr(value, "directory"):
            return str(value.directory)
        return type(value).__name__

    def describe(widget):
        result = {"class": type(widget).__name__, "name": widget.accessibleName(),
                  "enabled": widget.isEnabled(), "visible": widget.isVisible(),
                  "geometry": [widget.x(), widget.y(), widget.width(), widget.height()]}
        if isinstance(widget, QAbstractButton):
            result.update(text=widget.text(), checked=widget.isChecked())
        elif isinstance(widget, (QLineEdit, QLabel)):
            result["text"] = widget.text()[:1600]
        elif isinstance(widget, (QPlainTextEdit, QTextEdit)):
            result["text"] = widget.toPlainText()[:2000]
        elif isinstance(widget, QComboBox):
            result.update(index=widget.currentIndex(), text=widget.currentText())
        elif isinstance(widget, QTreeWidget):
            result["rows"] = [[widget.topLevelItem(i).text(c) for c in range(widget.columnCount())]
                              for i in range(min(widget.topLevelItemCount(), 32))]
            result["checked"] = [widget.topLevelItem(i).checkState(0).value
                                 for i in range(min(widget.topLevelItemCount(), 32))]
            result["current_row"] = widget.indexOfTopLevelItem(widget.currentItem())
        elif isinstance(widget, QTabWidget):
            result["index"] = widget.currentIndex()
        return result

    last_signature = None

    def observe():
        nonlocal last_signature
        surface = application.activeModalWidget() or application.activeWindow()
        if surface is None or not isValid(surface):
            return
        focus = application.focusWidget()
        value = {"window": type(surface).__name__, "title": surface.windowTitle(),
                 "scale": application.ui_scale_manager.scale,
                 "size": [surface.width(), surface.height()],
                 "focus": describe(focus) if focus else None,
                 "controls": {}, "actions": len(actions)}
        if focus and surface.isAncestorOf(focus):
            point = focus.mapTo(surface, QPoint())
            value["focus_in_window"] = [point.x(), point.y(), focus.width(), focus.height()]
        if isinstance(surface, QDialog):
            for i, widget in enumerate(surface.findChildren(QWidget)):
                if widget.isVisible() and isinstance(widget, (QAbstractButton, QLineEdit, QLabel,
                        QPlainTextEdit, QTextEdit, QComboBox, QTreeWidget, QTabWidget)):
                    value["controls"][str(i)] = describe(widget)
            for name in ("busy", "status", "result", "result_path", "created_project", "archive"):
                field = getattr(surface, name, None)
                if name != "status":
                    value[name] = scalar(field)
        if isValid(window):
            tab = window.current_tab()
            if tab:
                value["source"] = {"path": str(tab.path), "buffer": tab.editor.toPlainText(),
                    "disk_sha256": hashlib.sha256(tab.path.read_bytes()).hexdigest() if tab.path and tab.path.exists() else None,
                    "dirty": tab.modified, "cursor": tab.editor.textCursor().position()}
        signature = json.dumps(value, sort_keys=True, ensure_ascii=False)
        if signature == last_signature:
            return
        last_signature = signature
        record = {"seconds": elapsed(), "value": value}
        if len(states) < 1500:
            record["image"] = f"state-{len(states):04d}.png"
            surface.grab().save(str(output / record["image"]))
            states.append(record)
        (output / "live.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
        print(f"STATE {len(states)} {value['window']} {value['title']}", flush=True)

    class Observer(QObject):
        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.KeyPress and len(keys) < 20000:
                keys.append({"seconds": elapsed(), "target": type(watched).__name__,
                             "key": event.key(), "modifiers": event.modifiers().value,
                             "text": event.text()[:80]})
            return super().eventFilter(watched, event)

    observer = Observer(application)
    application.installEventFilter(observer)
    timer = QTimer(observer)
    timer.setInterval(120)

    def tick():
        nonlocal timed_out
        try:
            observe()
            if time.monotonic() - start > args.seconds:
                timed_out = True
                application.quit()
        except Exception as exc:
            errors.append(repr(exc))
            application.quit()

    def interrupt(*_args):
        nonlocal interrupted
        interrupted = True
        application.quit()

    timer.timeout.connect(tick)
    signal.signal(signal.SIGINT, interrupt)
    window.resize(1080, 720)
    window.show()
    timer.start()
    print(f"READY synthetic parent: {output / 'projects'}", flush=True)
    try:
        application.exec()
    finally:
        timer.stop()
        application.removeEventFilter(observer)
        for widget in list(application.topLevelWidgets()):
            if isinstance(widget, QDialog) and isValid(widget):
                if getattr(widget, "busy", False):
                    widget.cancel.set()
                widget.reject()
        deadline = time.monotonic() + 10
        while any(getattr(w, "busy", False) for w in application.topLevelWidgets()
                  if isValid(w)) and time.monotonic() < deadline:
            application.processEvents()
            time.sleep(.02)
        for owner in list(application.topLevelWidgets()):
            if not isValid(owner):
                continue
            if hasattr(owner, "tabs") and isinstance(owner.tabs, dict):
                close(owner)
            elif isinstance(owner, BlockProjectDialog):
                owner.session._dirty = False
                owner.session.editor_drafts.clear()
                owner.close()
                owner.deleteLater()
        application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        destroyed = [not isValid(w) for w in windows]
    report = {"synthetic_only": True, "platform": platform.platform(), "pyside": pyside_version,
              "app_sha256": source_hash, "app_sha256_after": app_digest(),
              "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "states": states, "keys": keys, "actions": actions, "errors": errors,
              "timeout": timed_out, "interrupted": interrupted, "windows_destroyed": destroyed,
              "limits": ["Physical keyboard/picker paths require CUA evidence review",
                         "QA fixture opens and scale changes are setup, not user workflows",
                         "No all-platform, VoiceOver, human or release acceptance"]}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print("REPORT " + str(output / "report.json"), flush=True)
    return int(bool(errors or interrupted or timed_out or not all(destroyed)))


if __name__ == "__main__":
    raise SystemExit(main())
