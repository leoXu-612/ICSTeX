"""Read-only citation layout observations in an isolated source MainWindow.

No compilation or native input is generated. Offscreen rendering is not native
IME/accessibility acceptance. Use a fresh --output directory for each run.
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
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.core.compiler import CompileOutcome, CompileResult
from app.core.diagnostics import Diagnostic
from app.core.log_parser import LaTeXError
from app.core.latex_tools import LaTeXToolchain
from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.probe_citation_health import close
from tools.probe_history_restore import app_digest
from tools.probe_submission_check import wait_for


def observe_native(application, window, output, project, originals, evidence):
    """Observe actual native actions without selecting, scrolling or checking."""
    assert application.platformName() == "cocoa"
    application.setQuitOnLastWindowClosed(False)
    navigation = window.toolbox_navigation
    panel = window.references_panel
    scroll = navigation.widget(7)
    states, keys, actions, compile_starts, observation_errors = [], [], [], [], []
    started = time.monotonic()
    timed_out = False
    interrupted = False
    controls = {
        "check": panel.check_button,
        "refresh": panel.check_refresh_button,
        "cancel": panel.check_cancel_button,
        "locate": panel.check_locate_button,
        "health": panel.health_table,
        "detail": panel.check_detail,
        "locations": panel.check_locations,
    }
    controls.update({f"rail-{i}": navigation.navigationButton(i)
                     for i in range(navigation.count())})
    tables = ({"outline": window.outline_panel.table,
               "search": window.search_panel.table,
               "errors": window.error_table,
               "diagnostics": window.diagnostic_panel.table}
              if evidence.get("navigation_fixture") else {})
    controls.update(tables)
    if tables:
        controls.update({"diagnostic-refresh": window.diagnostic_panel.refresh_button,
                         "diagnostic-fix": window.diagnostic_panel.fix_button,
                         "console-collapse": window.bottom_collapse_button})
    reading = evidence.get("reading_fixture", False)
    if reading:
        controls.update({"word-refresh": window.word_count_view.refresh_button,
                         "word-preview": window.word_count_view.preview_browser,
                         "submission-refresh": window.submission_panel.refresh_button,
                         "submission-cancel": window.submission_panel.cancel_button,
                         "submission-action": window.submission_panel.action_button,
                         "submission-results": window.submission_panel.tree,
                         "submission-detail": window.submission_panel.detail,
                         "console-collapse": window.bottom_collapse_button})

    def geometry(widget):
        rect = widget.rect()
        rect.moveTopLeft(widget.mapTo(window, rect.topLeft()))
        return {"visible": widget.isVisible(), "enabled": widget.isEnabled(),
                "unclipped": widget.visibleRegion().contains(widget.rect()),
                "inside_window": window.rect().contains(rect),
                "rect": [rect.x(), rect.y(), rect.width(), rect.height()]}

    def text_edges(editor):
        result = {}
        for name, position in (("first", QTextCursor.MoveOperation.Start), ("last", QTextCursor.MoveOperation.End)):
            cursor = QTextCursor(editor.document())
            cursor.movePosition(position)
            result[name] = editor.viewport().visibleRegion().contains(editor.cursorRect(cursor))
        return result

    def capture_state():
        if not isValid(window):
            return
        focus = application.focusWidget()
        focus_role = next((name for name, widget in controls.items() if widget is focus), None)
        report = panel.citation_report
        tab = window.current_tab()
        value = {
            "scale": window.preferences.ui_scale,
            "window": [window.width(), window.height()],
            "tool_index": navigation.currentIndex(),
            "tool_label": navigation.tabText(navigation.currentIndex()),
            "reference_tab": panel.reference_tabs.currentIndex(),
            "bottom_tab": window.bottom_tabs.tabText(window.bottom_tabs.currentIndex()),
            "focus_role": focus_role,
            "focus_class": focus.metaObject().className() if focus is not None else None,
            "controls": {name: geometry(widget) for name, widget in controls.items()},
            "rail_scroll": navigation.rail_scroll.verticalScrollBar().value(),
            "panel_scroll": scroll.verticalScrollBar().value(),
            "panel_horizontal_max": scroll.horizontalScrollBar().maximum(),
            "report_ready": report is not None,
            "report_complete": report.complete if report is not None else None,
            "report_stable": report.stable if report is not None else None,
            "report_identity": report.input_id if report is not None else None,
            "check_busy": window.citations.is_busy,
            "selected_rule": (report.items[panel.health_table.currentRow()].rule
                              if report is not None and 0 <= panel.health_table.currentRow() < len(report.items)
                              else None),
            "detail": panel.check_detail.toPlainText(),
            "locations": [panel.check_locations.item(i).text()
                          for i in range(panel.check_locations.count())],
            "current_path": str(tab.path.relative_to(project)) if tab and tab.path else None,
            "cursor_line": tab.editor.textCursor().blockNumber() + 1 if tab else None,
            "source_buffers": {str(item.path.relative_to(project)): item.editor.toPlainText()
                               for item in window.tabs.values() if item.path is not None},
            "files_unchanged": all(path.read_bytes() == raw for path, raw in originals.items()),
            "compile_authorized": bool(window.compile_authorized_roots),
            "compile_start_count": len(compile_starts),
            "action_count": len(actions),
        }
        if tables:
            value["console_sizes"] = window.vertical_splitter.sizes()
            value["console_collapsed"] = window.bottom_tabs.isHidden()
            value["diagnostic_scroll"] = window.diagnostic_panel.scroll.verticalScrollBar().value()
            value["navigation_tables"] = {
                name: {"row": table.currentRow(), "column": table.currentColumn(),
                       "current_cell_visible": (table.currentIndex().isValid()
                                                and table.viewport().visibleRegion().contains(
                                                    table.visualRect(table.currentIndex()))),
                       "selected_rows": [index.row() for index in table.selectionModel().selectedRows()],
                       "cells": [[table.item(row, column).text() if table.item(row, column) else None
                                  for column in range(table.columnCount())]
                                 for row in range(table.rowCount())]}
                for name, table in tables.items()}
        if reading:
            word = window.word_count_view
            submission = window.submission_panel
            index = submission.tree.currentIndex()
            value["console_sizes"] = window.vertical_splitter.sizes()
            value["console_collapsed"] = window.bottom_tabs.isHidden()
            value["word_count"] = {
                "busy": window.word_counts.is_busy, "mode": word.last_mode_label,
                "meta": word.meta_label.text(), "preview": word.preview_browser.toPlainText(),
                "scroll": window.word_count_panel.verticalScrollBar().value(),
                "preview_scroll": word.preview_browser.verticalScrollBar().value(),
                "preview_scroll_max": word.preview_browser.verticalScrollBar().maximum(),
                "cursor": word.preview_browser.textCursor().position(),
                "cursor_visible": word.preview_browser.viewport().visibleRegion().contains(word.preview_browser.cursorRect()),
                "text_edges_visible": text_edges(word.preview_browser),
                "values": {key: label.text() for key, label in word.labels.items()},
            }
            value["submission"] = {
                "busy": window.readiness.is_busy, "summary": submission.summary.text(),
                "input_id": submission.report.input_id if submission.report else None,
                "items": ([{"rule": item.rule_id, "status": item.status.value, "title": item.title}
                           for item in submission.report.items] if submission.report else []),
                "row": index.row(), "detail": submission.detail.toPlainText(),
                "row_visible": index.isValid() and submission.tree.viewport().visibleRegion().contains(
                    submission.tree.visualRect(index)),
                "scroll": submission.scroll.verticalScrollBar().value(),
                "detail_scroll": submission.detail.verticalScrollBar().value(),
                "detail_scroll_max": submission.detail.verticalScrollBar().maximum(),
                "cursor": submission.detail.textCursor().position(),
                "cursor_visible": submission.detail.viewport().visibleRegion().contains(submission.detail.cursorRect()),
                "text_edges_visible": text_edges(submission.detail),
            }
        if not states or states[-1]["value"] != value:
            index = len(states) + 1
            image = f"native-{index:04d}.png"
            assert window.grab().save(str(output / image))
            state = {"seconds": round(time.monotonic() - started, 4), "image": image, "value": value}
            states.append(state)
            print(json.dumps({"state": state}, ensure_ascii=False), flush=True)

    def record_state(*_args):
        if observation_errors:
            return
        try:
            capture_state()
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
            observation_errors.append(error)
            print(json.dumps({"observation_error": error}), flush=True)

    def action(name, *values):
        tab = window.current_tab()
        actions.append({"seconds": round(time.monotonic() - started, 4),
                        "name": name, "values": list(values),
                        "current_path": str(tab.path.relative_to(project)) if tab and tab.path else None,
                        "cursor_line": tab.editor.textCursor().blockNumber() + 1 if tab else None})

    class Observer(QObject):
        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.KeyPress:
                keys.append({"seconds": round(time.monotonic() - started, 4),
                             "key": event.key(), "modifiers": event.modifiers().value,
                             "target": watched.metaObject().className()})
            return False

    observer = Observer(window)
    application.installEventFilter(observer)
    application.focusChanged.connect(record_state)
    panel.checkRequested.connect(lambda: action("check"))
    panel.locationRequested.connect(lambda row, location: action("locate", row, location))
    for name, table in tables.items():
        table.cellActivated.connect(lambda row, column, name=name: action("table_activation", name, row, column))
    if reading:
        window.word_count_view.refreshRequested.connect(lambda: action("word_refresh"))
        window.submission_panel.refreshRequested.connect(lambda: action("submission_refresh"))
        window.submission_panel.actionRequested.connect(lambda index: action("submission_action", index))
    window.signals.started.connect(lambda root, build_id: compile_starts.append([root, build_id]))
    timer = QTimer(window)
    timer.setInterval(100)
    timer.timeout.connect(record_state)
    window.resize(1080, 720)
    window.raise_()
    window.activateWindow()
    timer.start()
    record_state()
    print("READY: native Check, navigate, rail keys, scale menu and close only", flush=True)
    try:
        while isValid(window):
            application.processEvents()
            if observation_errors:
                break
            if time.monotonic() - started > 600:
                timed_out = True
                break
            time.sleep(0.01)
    except KeyboardInterrupt:
        interrupted = True
    finally:
        application.focusChanged.disconnect(record_state)
        if isValid(window):
            record_state()
            timer.stop()
            close(window)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    evidence.update({"native_observation": True, "states": states, "keys": keys,
                     "observation_errors": observation_errors,
                     "actions": actions, "compile_starts": compile_starts,
                     "timeout": timed_out, "interrupted": interrupted,
                     "window_destroyed": not isValid(window),
                     "read_only": all(path.read_bytes() == raw for path, raw in originals.items()),
                     "app_sha256_after": app_digest(),
                     "limits": ["Observation receipt, not a broad pass predicate",
                                "Physical desktop keys/AX and screenshots require separate review",
                                "No PDF/FINAL, all-AX, human or Windows acceptance"]})
    payload = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    (output / "report.json").write_text(payload, encoding="utf-8")
    print(json.dumps({"observation_completed": not timed_out and not interrupted and not observation_errors,
                      "window_destroyed": evidence["window_destroyed"],
                      "report_sha256": hashlib.sha256(payload.encode()).hexdigest()}), flush=True)
    assert not timed_out and not interrupted and not observation_errors and evidence["window_destroyed"] and evidence["read_only"]
    assert evidence["app_sha256_after"] == evidence["app_sha256"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native-observe", action="store_true")
    parser.add_argument("--readonly-navigation", action="store_true",
                        help="Use the labelled outline/search/diagnostic/error fixture for native observation")
    parser.add_argument("--readonly-console", action="store_true",
                        help="Observe actual Word Count/Submission Check with explicitly absent tool paths")
    args = parser.parse_args()
    if args.readonly_navigation and not args.native_observe:
        parser.error("--readonly-navigation requires --native-observe")
    if args.readonly_console and (not args.native_observe or args.readonly_navigation):
        parser.error("--readonly-console requires --native-observe without --readonly-navigation")
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    application = QApplication([])
    application.setApplicationName("ICSTeX Citation Layout QA")
    apply_theme(application)
    before_hash = app_digest()
    project = output / "synthetic-project"
    chapter = project / "chapters" / "long-path-for-source-navigation"
    chapter.mkdir(parents=True)
    root, child, bib = project / "main.tex", chapter / "child.tex", project / "catalog.bib"
    root.write_text("\\documentclass{article}\n\\begin{document}\n"
                    + ("\\section{First}\nSynthetic text\n\\section{Second}\n" if args.readonly_navigation else "") +
                    ("\n\n".join(f"Synthetic reading paragraph {i}." for i in range(40)) + "\n"
                     if args.readonly_console else "") +
                    "\\input{chapters/long-path-for-source-navigation/child}\n"
                    "\\bibliography{catalog}\n\\end{document}\n", encoding="utf-8")
    child.write_text("% !TeX root = ../../main.tex\n\\cite{Known,MissingWithLongIdentifier2026}\n"
                     + ("navigationneedle\nSynthetic fourth line\n" if args.readonly_navigation else ""), encoding="utf-8")
    bib.write_text("@book{Known,title={Known}}\n@book{Unused,title={Keep this book}}\n", encoding="utf-8")
    before = {p: p.read_bytes() for p in (root, child, bib)}
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / "qa.ini"), QSettings.Format.IniFormat)))
    evidence = {"platform": platform.platform(), "python": platform.python_version(),
                "pyside": pyside_version, "qt_platform": application.platformName(),
                "app_sha256": before_hash, "synthetic_only": True, "layouts": [],
                "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "navigation_fixture": args.readonly_navigation, "reading_fixture": args.readonly_console}
    try:
        window.auto_compile_action.setChecked(False)
        if args.readonly_console:
            window.toolchain = LaTeXToolchain(None, None)
            evidence["fixture_limits"] = [
                "Actual local word count and read-only check, not a successful build",
                "Tool paths explicitly absent; no save/compile/next-step action is authorized by the probe",
            ]
        window.project_files.set_project_root(project)
        window.open_file(root)
        window.show()
        window.set_toolbox_visible(True)
        window.sidebar_tabs.setCurrentIndex(7)
        panel = window.references_panel
        scroll = window.sidebar_tabs.widget(7)
        if args.readonly_navigation:
            window.sidebar_tabs.setCurrentIndex(1)
            window.project_panels.refresh()
            window.diagnostic_panel.set_diagnostics([
                Diagnostic("info", "Synthetic location A", "Navigation fixture, not a project check", root, 3),
                Diagnostic("info", "Synthetic location B", "Navigation fixture, not a project check", child, 4),
            ])
            window.compile.show_errors(CompileResult(
                root_file=root, output_dir=project / "not-built", pdf_file=project / "not-built/main.pdf",
                log_file=project / "not-built/main.log", command=[], returncode=1, stdout="", stderr="",
                duration_seconds=0, outcome=CompileOutcome.LATEX_ERROR,
                errors=[LaTeXError("Synthetic navigation record A; no compilation ran", child, 2),
                        LaTeXError("Synthetic navigation record B; no compilation ran", root, 3)],
            ))
            evidence["fixture_limits"] = [
                "Outline parsed from actual synthetic source; search must be explicitly triggered",
                "Diagnostics and compile-error records are synthetic navigation inputs, not engine evidence",
                "Expected second outline main.tex:5; search child.tex:3; second error main.tex:3; second diagnostic child.tex:4",
            ]
        if args.native_observe:
            observe_native(application, window, output, project, before, evidence)
            return
        wait_for(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
        panel.check_button.click()
        wait_for(lambda: not window.citations.is_busy)
        report = panel.citation_report
        assert report is not None and report.complete and report.stable
        missing = next(i for i, item in enumerate(report.items) if item.rule == "citation_missing")
        panel.health_table.selectRow(missing)
        for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
            window.set_ui_scale(scale)
            for width, height in ((1120, 820), (880, 640)):
                window.resize(width, height)
                application.processEvents()
                label = f"{round(scale * 100)}-{width}"
                controls = []
                for button in (panel.check_refresh_button, panel.check_cancel_button, panel.check_locate_button):
                    scroll.ensureWidgetVisible(button)
                    application.processEvents()
                    rect = button.rect()
                    rect.moveTopLeft(button.mapTo(scroll.viewport(), rect.topLeft()))
                    controls.append({"text": button.text(), "fully_visible": scroll.viewport().rect().contains(rect),
                                     "unclipped": button.visibleRegion().contains(button.rect()),
                                     "width": button.width(), "hint_width": button.sizeHint().width()})
                assert window.grab().save(str(output / f"controls-{label}.png"))
                scroll.ensureWidgetVisible(panel.health_table)
                application.processEvents()
                assert window.grab().save(str(output / f"health-{label}.png"))
                rows = [{"height": panel.health_table.rowHeight(row),
                         "font_height": panel.health_table.fontMetrics().height(),
                         "values": [panel.health_table.item(row, col).text() for col in range(3)]}
                        for row in range(panel.health_table.rowCount())]
                evidence["layouts"].append({"scale": scale, "requested": [width, height],
                    "actual": [window.width(), window.height()], "controls": controls, "rows": rows,
                    "table_viewport": [panel.health_table.viewport().width(), panel.health_table.viewport().height()],
                    "table_horizontal_max": panel.health_table.horizontalScrollBar().maximum(),
                    "panel_horizontal_max": scroll.horizontalScrollBar().maximum(),
                    "detail": panel.check_detail.toPlainText(),
                    "location": panel.check_locations.item(0).text()})
                scroll.ensureWidgetVisible(panel.check_locations)
                application.processEvents()
                assert window.grab().save(str(output / f"location-{label}.png"))
                scroll.verticalScrollBar().setValue(0)
                application.processEvents()
                assert window.grab().save(str(output / f"status-{label}.png"))
        panel.check_locations.setCurrentRow(0)
        panel.check_locate_button.click()
        assert window.current_tab().path == child
        assert window.current_tab().editor.textCursor().blockNumber() == 1
        evidence["navigation"] = "chapters/long-path-for-source-navigation/child.tex:2"
        evidence["read_only"] = all(p.read_bytes() == raw for p, raw in before.items())
        assert evidence["read_only"] and not window.compile_authorized_roots
        evidence["compile_authorized"] = False
        evidence["layout_contract_passed"] = all(
            item["panel_horizontal_max"] == 0 and all(
                control["fully_visible"] and control["unclipped"] and control["width"] >= control["hint_width"]
                for control in item["controls"])
            for item in evidence["layouts"])
        evidence["app_sha256_after"] = app_digest()
        assert before_hash == evidence["app_sha256_after"]
    finally:
        if isValid(window):
            close(window)
    evidence["window_closed"] = True
    evidence["limits"] = ["Layout observations, not an all-pass readability predicate",
                          "No physical input, native AX or Windows acceptance"]
    payload = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    (output / "report.json").write_text(payload, encoding="utf-8")
    print(json.dumps({"output": str(output), "report_sha256": hashlib.sha256(payload.encode()).hexdigest(),
                      "layouts": evidence["layouts"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
