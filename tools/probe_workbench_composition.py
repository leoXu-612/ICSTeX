"""Observe native IME editing in the actual ordinary/Block workbench.

Only fixture creation and initial navigation are automated. Desktop control
must type Chinese, cancel a second candidate, undo/redo, apply a Block draft,
save and close the window. The observer never synthesizes input or clicks.
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
from PySide6.QtWidgets import QApplication, QLineEdit
from shiboken6 import isValid

from app.core.blocks.layout import LayoutNode, block_slot
from app.core.blocks.model import content_for_text
from app.core.blocks.project_repository import load_project
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow
from app.gui.block_mode import _install_session, _set_block_mode
from app.gui.blocks.project_session import ProjectSession
from app.gui.theme import apply_theme
from tools.probe_history_restore import app_digest
from tools.probe_project_checkpoint_gui import close, window_for


def observations_pass(report):
    """Evaluate captured observations; this does not generate native input."""
    states, events = report["states"], report["events"]
    original, expected = report["original"], report["expected"]
    if (not states or not events or report["timeout"] or not report["window_destroyed"]
            or report["saved"] != expected or not report["other_table_preserved"]
            or report["actions"]["save"] < 1
            or report["app_sha256"] != report["app_sha256_after"]):
        return False
    counts = [value["event_count"] for value in states]
    if counts != sorted(counts) or counts[0] < 0 or counts[-1] > len(events):
        return False
    commit = next((i for i, value in enumerate(events) if value["commit"] == "\u4e2d\u6587"), None)
    if commit is None or not any(value["preedit"] for value in events[:commit]):
        return False
    candidate = next((i for i in range(commit + 1, len(events)) if events[i]["preedit"]), None)
    if candidate is None:
        return False
    cancelled = next((i for i in range(candidate + 1, len(events))
                      if not events[i]["preedit"] and not events[i]["commit"]
                      and not events[i].get("replacement_length", 0)), None)
    if cancelled is None or any(value["commit"] for value in events[candidate:]):
        return False

    # Require commit -> Undo -> Redo in that order, before the second candidate.
    # Two identical snapshots preceding Undo are not evidence of Redo.
    position = -1
    for text in (expected, original, expected):
        position = next((i for i in range(position + 1, len(states))
                         if states[i]["text"] == text and not states[i]["preedit"]
                         and commit < counts[i] <= candidate), None)
        if position is None:
            return False
    first_preedit = [value for value in states if value["preedit"] and value["event_count"] <= commit]
    second_preedit = [value for value in states if candidate < value["event_count"] <= cancelled]
    after_cancel = [value for value in states if value["event_count"] > cancelled]
    if (not first_preedit or any(value["text"] != original for value in first_preedit)
            or not second_preedit or not any(value["preedit"] for value in second_preedit)
            or any(value["text"] != expected for value in second_preedit)
            or not after_cancel or any(value["text"] != expected or value["preedit"] for value in after_cancel)):
        return False
    if report["kind"] == "ordinary":
        return all(value["files_unchanged"] for value in states if not value["actions"]["save"])
    if report["actions"]["apply"] < 1 or any(value["compile_created"] for value in states):
        return False
    before_apply = [value for value in states if not value["actions"]["apply"]]
    after_apply = [value for value in states if value["actions"]["apply"]]
    return bool(before_apply and after_apply
                and all(value["model"] == original and value["files_unchanged"] for value in before_apply)
                and all(value["model"] == expected for value in after_apply))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("ordinary", "inspector", "table"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    application = QApplication([])
    assert application.platformName() == "cocoa"
    application.setQuitOnLastWindowClosed(False)
    application.setApplicationName("ICSTeX Workbench IME QA")
    apply_theme(application)
    source_hash = app_digest()
    window = window_for(output, args.kind)
    window.resize(1320, 900)
    project = output / "synthetic-project"
    root = project / "main.tex"
    session = None
    target = None
    if args.kind == "ordinary":
        project.mkdir()
        original = ("\\documentclass{ctexart}\n\\begin{document}\n"
                    "Native input: base \n\\end{document}\n")
        root.write_text(original, encoding="utf-8")
        window.project_files.set_project_root(project)
        window.open_file(root)
        editor = window.current_tab().editor
        cursor = editor.textCursor()
        position = original.index("base ") + len("base ")
        cursor.setPosition(position)
        editor.setTextCursor(cursor)
        expected = original[:position] + "\u4e2d\u6587" + original[position:]
    else:
        registry = BlockRegistry()
        text = registry.create(CreateBlockInput(type="text", alias="text_probe", content=content_for_text("base ")))
        tables = []
        for alias in ("table_probe", "other_table"):
            data = TableData(columns=[ColumnSpec(id="c1", name="Value")],
                             rows=[TableRow(id="r1", cells={"c1": Cell("text", "base " if not tables else "untouched")})],
                             header_row_count=0)
            tables.append(registry.create(CreateBlockInput(type="table", alias=alias, content=data.to_content_dict())))
        layout = LayoutNode(id="ime_layout", kind="column", children=tuple(block_slot(block.id) for block in registry.blocks()))
        session = ProjectSession(registry=registry, layout=layout, project_dir=project)
        session.save_now()
        assert session.last_save_ok, session.save_error
        window.project_files.set_project_root(project)
        window.open_file(root)
        assert _install_session(window, session)
        _set_block_mode(window, True)
        target = text if args.kind == "inspector" else tables[0]
        session.selection.select_block(target.id, source="native-ime-fixture")
        if args.kind == "table":
            window.block_inspector.table_button.click()  # initial navigation only
            editor = None  # the delegate must be opened by a real double-click
        else:
            editor = window.block_inspector.content_edit
            editor.moveCursor(QTextCursor.MoveOperation.End)
        original, expected = "base ", "base \u4e2d\u6587"

    original_files = {path.relative_to(project).as_posix(): path.read_bytes()
                      for path in project.rglob("*") if path.is_file()}
    events, states, keys = [], [], []
    line_preedit = ""
    actions = {"save": 0, "apply": 0}
    started = time.monotonic()
    timeout = False

    def note_action(name):
        actions[name] += 1
        print(json.dumps({"action": name, "counts": actions}), flush=True)
        record_state()

    save_action = window.block_save_action if session is not None else window.save_action
    save_action.triggered.connect(lambda: note_action("save"))
    if session is not None:
        apply_button = (window.block_workspace.table_apply_button if args.kind == "table"
                        else window.block_inspector.apply_button)
        apply_button.clicked.connect(lambda: note_action("apply"))

    def current_editor():
        if args.kind == "table":
            return window.block_workspace.table_editor._cell_editor
        return editor

    def text_value():
        active = current_editor()
        if active is not None and isValid(active):
            return active.text() if isinstance(active, QLineEdit) else active.toPlainText()
        return window.block_workspace.table_editor.table.item(0, 0).text()

    def record_state():
        if not isValid(window):
            return
        active = current_editor()
        preedit = bool(line_preedit) if isinstance(active, QLineEdit) else False
        if active is not None and isValid(active) and not isinstance(active, QLineEdit):
            preedit = bool(active.textCursor().block().layout().preeditAreaText())
        focus = application.focusWidget()
        value = {"text": text_value(), "preedit": preedit, "event_count": len(events),
                 "focus": focus.metaObject().className() if focus is not None else None,
                 "files_unchanged": all((project / path).read_bytes() == raw for path, raw in original_files.items()),
                 "actions": dict(actions)}
        if args.kind == "inspector":
            inspector = window.block_inspector
            value["focus_role"] = next((name for name, widget in (
                ("content", inspector.content_edit), ("alias", inspector.alias_edit),
                ("apply", inspector.apply_button)) if focus is widget), None)
        if session is not None:
            current = session.registry.get(target.id)
            value.update(model=(None if current is None else current.content["text"] if args.kind == "inspector"
                                else current.content["rows"][0]["cells"]["c1"]["value"]),
                         drafts=sorted([list(key) for key in session.editor_drafts]),
                         dirty=session.has_unsaved_changes, save_ok=session.last_save_ok,
                         compile_created=session.compile_manager is not None)
        else:
            tab = window.current_tab()
            value.update(modified=tab.modified, dirty=tab.dirty,
                         cursor=editor.textCursor().position(), scroll=editor.verticalScrollBar().value())
        if not states or states[-1] != value:
            states.append(value)
            print(json.dumps({"state": value}, ensure_ascii=False), flush=True)
            window.grab().save(str(output / f"state-{len(states):03d}.png"))

    class Observer(QObject):
        def eventFilter(self, watched, event):
            nonlocal line_preedit
            if watched is current_editor() and event.type() in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride):
                value = {"type": event.type().name, "key": event.key(),
                         "modifiers": event.modifiers().value}
                keys.append(value)
                print(json.dumps({"native_key_event": value}), flush=True)
            if event.type() == QEvent.Type.InputMethod and watched is current_editor():
                value = {"seconds": round(time.monotonic() - started, 3),
                         "preedit": event.preeditString(), "commit": event.commitString(),
                         "replacement_start": event.replacementStart(), "replacement_length": event.replacementLength()}
                events.append(value)
                if isinstance(watched, QLineEdit):
                    line_preedit = event.preeditString()
                print(json.dumps({"native_input_event": value}, ensure_ascii=False), flush=True)
            if watched is current_editor() and event.type() in (QEvent.Type.InputMethod, QEvent.Type.KeyPress):
                QTimer.singleShot(0, window, record_state)
            return False

    observer = Observer(window)
    application.installEventFilter(observer)
    timer = QTimer(window)
    timer.setInterval(100)
    timer.timeout.connect(record_state)
    window.show()
    window.raise_()
    window.activateWindow()
    if editor is not None:
        editor.setFocus()
    timer.start()
    record_state()
    print("READY: actual Chinese input, Undo/Redo, cancel second preedit; Apply if Block, Save, close", flush=True)
    try:
        while isValid(window):
            application.processEvents()
            if time.monotonic() - started > 600:
                timeout = True
                break
            time.sleep(0.01)
    finally:
        if isValid(window):
            record_state()
            timer.stop()
            close(window)  # failed-run cleanup of disposable fixtures only
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    if args.kind == "ordinary":
        saved = root.read_text(encoding="utf-8")
        others_preserved = True
    else:
        loaded = load_project(project)["registry"]
        block = loaded.get(target.id)
        saved = block.content["text"] if args.kind == "inspector" else block.content["rows"][0]["cells"]["c1"]["value"]
        others_preserved = loaded.get(tables[1].id).content["rows"][0]["cells"]["c1"]["value"] == "untouched"
    report = {"kind": args.kind, "synthetic_only": True, "app_sha256": source_hash,
              "app_sha256_after": app_digest(), "platform": platform.platform(),
              "python": platform.python_version(), "pyside": pyside_version,
              "qt_platform": application.platformName(), "events": events, "keys": keys, "states": states,
              "saved": saved, "original": original, "expected": expected, "other_table_preserved": others_preserved,
              "actions": actions,
              "window_destroyed": not isValid(window), "timeout": timeout}
    report["passed"] = observations_pass(report)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
