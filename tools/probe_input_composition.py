"""Observe real Cocoa IME events in an isolated formula dialog.

The observer never generates input events, types, applies or chooses candidates.
Use a configured Chinese input source through native desktop control. Commit
Chinese text, use the dialog Undo/Redo buttons, then Apply. No student file or
installed application is opened. The receipt distinguishes native events from
the separate synthetic QInputMethodEvent regression tests.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.gui.formula_dialog import FormulaDialog
from app.gui.macos_accessibility import install_selected_children_guard
from app.gui.theme import apply_theme
from tools.probe_history_restore import app_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-mode", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    app = QApplication([])
    assert app.platformName() == "cocoa", "Use QT_QPA_PLATFORM=cocoa for native QA"
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("ICSTeX IME QA")
    install_selected_children_guard()
    apply_theme(app)
    original = "Before $x+$ after"
    dialog = FormulaDialog(None, original, 7, 11)
    if args.source_mode:
        dialog.source_mode_check.setChecked(True)
        cursor = dialog.source_edit.textCursor()
        cursor.setPosition(3)
        dialog.source_edit.setTextCursor(cursor)
    dialog.setWindowTitle("ICSTeX IME QA - synthetic only")
    records = []
    states = []
    started = time.monotonic()
    before = app_digest()

    class Observer(QObject):
        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.InputMethod:
                record = {"seconds": round(time.monotonic() - started, 3),
                          "preedit": event.preeditString(), "commit": event.commitString(),
                          "replacement_start": event.replacementStart(),
                          "replacement_length": event.replacementLength()}
                records.append(record)
                print(json.dumps({"native_input_event": record}, ensure_ascii=False), flush=True)
            return False

    observer = Observer(dialog)
    active_editor = dialog._active_editor()
    active_editor.installEventFilter(observer)

    def record_state():
        draft = dialog.current_draft()
        value = {"latex": draft.body if draft else None,
                 "preedit": dialog._source_has_preedit() if args.source_mode else dialog.visual_edit.has_preedit,
                 "source": dialog.source_edit.toPlainText(),
                 "apply_enabled": dialog._ok_button.isEnabled()}
        if not states or states[-1] != value:
            states.append(value)
            print(json.dumps({"state": value}, ensure_ascii=False), flush=True)
            dialog.grab().save(str(output / f"state-{len(states):02d}.png"))

    dialog.visual_edit.stateChanged.connect(record_state)
    dialog.source_edit.textChanged.connect(record_state)
    timeout = QTimer(dialog)
    timeout.setSingleShot(True)
    timeout.timeout.connect(dialog.reject)
    timeout.start(600000)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    active_editor.setFocus()
    record_state()
    print("READY: use native Chinese IME, commit Chinese, Undo, Redo, Apply", flush=True)
    result = dialog.exec()
    timeout.stop()
    plan = dialog.plan()
    final = plan.text if plan is not None else None
    committed = any(any("\u4e00" <= char <= "\u9fff" for char in item["commit"]) for item in records)
    saw_preedit = any(item["preedit"] for item in records)
    changed = [i for i, state in enumerate(states) if state["latex"] == "x+\u4e2d\u6587" and not state["preedit"]]
    undo = bool(changed and any(state["latex"] == "x+" for state in states[changed[0] + 1:]))
    redo = bool(undo and changed[-1] > changed[0])
    original_preserved = dialog._document_text == original
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    report = {"app_sha256": before, "app_sha256_after": app_digest(),
              "platform": platform.platform(), "python": platform.python_version(), "pyside": pyside_version,
              "qt_platform": app.platformName(), "synthetic_only": True,
              "source_mode": args.source_mode,
              "events": records, "states": states, "dialog_result": result, "plan": final,
              "physical_ime_preedit_observed": saw_preedit, "chinese_commit_observed": committed,
              "undo_observed": undo, "redo_observed": redo, "original_document_preserved": original_preserved,
              "window_destroyed": not isValid(dialog)}
    report["passed"] = bool(saw_preedit and committed and undo and redo and final == "$x+\u4e2d\u6587$"
                             and original_preserved and not isValid(dialog) and before == report["app_sha256_after"])
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
