"""Actual Cocoa formula/clipboard QA, driven by the desktop tool, not QTest.

Only new synthetic files/settings are used. Stage messages describe the next
external input; the observer never pastes, edits, applies or dismisses a dialog.
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

from PySide6.QtCore import QEvent, QSettings, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.core.compiler import BuildPurpose
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness
from app.core.settings import AppSettings
from app.gui.formula_dialog import FormulaDialog
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.probe_history_restore import app_digest, visible_pdf_ink
from tools.probe_submission_delivery import pdf_text


PASTE_BODY = "\n + " + r"\studentMacro{a}{b} % keep $ \)" + "\n\t + z\n"
PASTE = "\\(" + PASTE_BODY + "\\)"
FALLBACK_BODY = "\n  " + r"\studentMacro{a}{b} + x_1^2 + \unknown^{2} % keep $ \)" + "\n\t"
FALLBACK = "\\(" + FALLBACK_BODY + "\\)"
FALLBACK_DRAFT = FALLBACK[:-2] + "+q" + FALLBACK[-2:]


def emit(**value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def wait_for(predicate, seconds=600):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Native formula QA observation timed out")


def select(editor, text):
    start = editor.toPlainText().index(text)
    cursor = editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(start + len(text), QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    editor.ensureCursorVisible()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.native:
        parser.error("This probe requires --native and QT_QPA_PLATFORM=cocoa")
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    app = QApplication.instance() or QApplication([])
    assert app.platformName() == "cocoa"
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("ICSTeX Formula Clipboard QA")
    apply_theme(app)
    project = output / "synthetic-project"
    project.mkdir()
    root = project / "main.tex"
    original = ("\\documentclass{article}\n\\newcommand{\\studentMacro}[2]{#1+#2}\n"
                "\\newcommand{\\unknown}{z}\n" + "% synthetic scroll padding\n" * 80
                + "\\begin{document}\nFormula result: $x$.\nFallback result: " + FALLBACK
                + ".\n\\end{document}\n")
    root.write_bytes(original.encode())
    digest = app_digest()
    report = {"app_sha256": digest, "platform": platform.platform(),
              "python": platform.python_version(), "qt_platform": app.platformName(),
              "synthetic_only": True, "dialog_observations": []}
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / "qa.ini"), QSettings.Format.IniFormat)))
    window.auto_compile_action.setChecked(False)
    window.save_debounce_ms = 3600000
    window.project_files.set_project_root(project)
    window.open_file(root)
    window.resize(1120, 820)
    window.show()
    window.raise_()
    window.activateWindow()
    tab = window.current_tab()
    editor = tab.editor
    timer = QTimer()
    timer.setInterval(50)
    stage = ""
    previous = None
    dialog_seen = None
    failures = []

    def observe():
        nonlocal previous, dialog_seen
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, FormulaDialog):
            return
        dialog_seen = dialog
        try:
            plan = dialog.build_plan()
            value = {"stage": stage, "source_mode": dialog.source_mode_check.isChecked(),
                     "visual": dialog.visual_edit.latex(), "source": dialog.source_edit.toPlainText(),
                     "plan": plan.text if plan is not None else None,
                     "apply_enabled": dialog._ok_button.isEnabled(),
                     "status": dialog.status_label.text()}
            assert root.read_bytes() == original.encode(), "Draft UI unexpectedly saved source"
            assert not window.compile_authorized_roots, "Draft UI granted compilation"
            if value != previous:
                previous = value
                report["dialog_observations"].append(value)
                emit(**value)
                assert dialog.grab().save(str(output / f"{stage}-{len(report['dialog_observations']):02d}.png"))
        except Exception as exc:
            failures.append(repr(exc))
            dialog.reject()

    def dialog_stage(name, selection):
        nonlocal stage, previous, dialog_seen
        stage, previous, dialog_seen = name, None, None
        select(editor, selection)
        saved_selection = (editor.textCursor().selectionStart(), editor.textCursor().selectionEnd())
        saved_scroll = editor.verticalScrollBar().value()
        emit(stage=name, clipboard_text=PASTE if name != "source_fallback" else FALLBACK_DRAFT)
        timer.start()
        window.formula_composer_action.trigger()
        timer.stop()
        assert not failures, failures
        assert dialog_seen is not None
        observations = [item for item in report["dialog_observations"] if item["stage"] == name]
        return dialog_seen, observations, saved_selection, saved_scroll

    timer.timeout.connect(observe)
    try:
        first, states, selection, scroll = dialog_stage("visual_cancel", "$x$")
        assert first.plan() is None and editor.toPlainText() == original
        assert root.read_bytes() == original.encode()
        assert (editor.textCursor().selectionStart(), editor.textCursor().selectionEnd()) == selection
        assert editor.verticalScrollBar().value() == scroll and scroll > 0
        assert any(s["visual"] == "x$" and not s["apply_enabled"] and s["plan"] is None for s in states)
        assert any(s["visual"] == "x$" and "请修正草稿" in s["status"] for s in states)
        assert sum(s["plan"] == "$x$" and s["apply_enabled"] for s in states) >= 2
        assert sum(s["plan"] == "$x" + PASTE_BODY + "$" for s in states) >= 2
        report["native_invalid_refusal_local_undo_redo_cancel_exact_bytes"] = True

        second, states, _, _ = dialog_stage("visual_apply", "$x$")
        expected = original.replace("Formula result: $x$", "Formula result: $x" + PASTE_BODY + "$")
        assert second.plan() is not None and editor.toPlainText() == expected
        assert any(s["plan"] == "$x" + PASTE_BODY + "$" for s in states)
        assert root.read_bytes() == original.encode()
        editor.setFocus()
        emit(stage="document_undo", expected="One native Command+Z restores the whole source")
        wait_for(lambda: editor.toPlainText() == original)
        assert root.read_bytes() == original.encode()
        emit(stage="document_redo", expected="One native Command+Shift+Z reapplies the whole formula")
        wait_for(lambda: editor.toPlainText() == expected)
        report["native_apply_and_single_document_undo_redo"] = True

        third, states, selection, scroll = dialog_stage("source_fallback", FALLBACK)
        assert third.plan() is None and editor.toPlainText() == expected
        assert root.read_bytes() == original.encode()
        assert (editor.textCursor().selectionStart(), editor.textCursor().selectionEnd()) == selection
        assert editor.verticalScrollBar().value() == scroll
        assert states[0]["source_mode"] and states[0]["source"] == FALLBACK
        assert any(s["source"] == FALLBACK_DRAFT and "无法无损转换" in s["status"] for s in states)
        assert sum(s["source"] == FALLBACK for s in states) >= 2
        assert any(s["source"] == "$x$$" and s["plan"] is None and not s["apply_enabled"] for s in states)
        report["native_source_fallback_failed_switch_undo_invalid_cancel"] = True

        cursor_before = editor.textCursor().position()
        scroll_before = editor.verticalScrollBar().value()
        assert window.save_current()
        assert root.read_bytes() == expected.encode()
        assert editor.textCursor().position() == cursor_before
        assert editor.verticalScrollBar().value() == scroll_before
        window.compile.set_engine(LaTeXEngine.PDFLATEX, compile_after=False)
        emit(stage="explicit_final")
        window.compile_current(immediate=True, purpose=BuildPurpose.FINAL)
        wait_for(lambda: window.pdf_state.record_for(root).freshness == PdfFreshness.CURRENT, seconds=90)
        manager = window.compile_managers[root]
        wait_for(lambda: window.pdf_panel._document is not None
                 and window.pdf_panel._document.pageCount() > 0, seconds=90)
        window.pdf_panel.fit_width()
        wait_for(lambda: not manager.is_busy and visible_pdf_ink(window) > 20, seconds=90)
        wait_for(lambda: "FINAL" in window.workspace.details.full_text
                 and "正在编译" not in window.workspace.details.full_text, seconds=15)
        assert root.read_bytes() == expected.encode()
        assert editor.textCursor().position() == cursor_before
        assert editor.verticalScrollBar().value() == scroll_before
        text = pdf_text(manager.pdf_file)
        assert "Formula result:" in text and "x+a+b+z" in text.replace(" ", ""), text
        assert window.grab().save(str(output / "formula-final.png"))
        raw = manager.pdf_file.read_bytes()
        (output / "formula-final.pdf").write_bytes(raw)
        report.update(final_pdf_sha256=hashlib.sha256(raw).hexdigest(), final_pdf_text=text,
                      saved_source_sha256=hashlib.sha256(root.read_bytes()).hexdigest(),
                      final_workspace_status=window.workspace.details.full_text,
                      save_compile_cursor_scroll_preserved=True)
    finally:
        timer.stop()
        for other in window.tabs.values():
            window.documents.cancel_save_timer(other)
            other.modified = other.dirty = False
        assert window.close()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(window)
    assert digest == app_digest()
    report["limits"] = ["Desktop-generated native keys and clipboard are not human or IME acceptance",
        "Existing scoped AX selected-children guard remains; no AX stress/VoiceOver/Windows claim",
        "Only synthetic source and current macOS/Qt/pdfLaTeX; no package, install or release"]
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    emit(stage="complete", report=str(output / "report.json"))


if __name__ == "__main__":
    main()
