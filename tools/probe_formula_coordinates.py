"""Offscreen real formula selection/target, Undo, save/reopen and FINAL probe.

Only newly created synthetic data; no physical keys, clipboard or OCR service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QEvent, QSettings, QTimer, qVersion
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QDialogButtonBox
from shiboken6 import isValid

from app.core.compiler import BuildPurpose
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness
from app.core.settings import AppSettings
from app.gui.formula_dialog import FormulaDialog
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.probe_history_restore import app_digest, visible_pdf_ink
from tools.probe_submission_check import wait_for
from tools.probe_submission_delivery import pdf_text


def formula_view_stats(window):
    """Contrast in this centered synthetic formula ROI versus adjacent blank paper.

    R5's actual glyph minimum is 119 and blank paper is 255. Counting only pixels
    below 100 misses all rendered math; keep a blank-region negative control.
    """
    picture = window.pdf_panel._view.viewport().grab().toImage()
    middle = picture.width() // 2
    formula = [picture.pixelColor(x, y).lightness()
               for y in range(20, 140) for x in range(middle - 100, middle + 100)]
    blank = [picture.pixelColor(x, y).lightness()
             for y in range(20, 140) for x in range(20, 90)]
    return {"formula_pixels_below_160": sum(value < 160 for value in formula),
            "blank_pixels_below_160": sum(value < 160 for value in blank),
            "formula_white_fraction": sum(value == 255 for value in formula) / len(formula)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    application = QApplication.instance() or QApplication([])
    assert application.platformName() == "offscreen", "Use QT_QPA_PLATFORM=offscreen"
    application.setQuitOnLastWindowClosed(False)
    output.mkdir(exist_ok=False)
    apply_theme(application)
    project = output / "synthetic-project"
    project.mkdir()
    root = project / "main.tex"
    seed = r"\(\studentMacro{x}\)"
    before = ("% \U0001f600\U0001f680 Unicode comment\n\\documentclass{article}\n"
              "\\newcommand{\\studentMacro}[1]{#1}\n\\begin{document}\n"
              "Before " + seed + " after.\n\\end{document}\n")
    original = before.replace("\n", "\r\n").encode()
    root.write_bytes(original)
    replacement = ("\\begin{equation*}\n\\studentMacro{x}+y % \U0001f600\U0001f680 preserved comment\n"
                   "\\end{equation*}")
    digest = app_digest()
    report = {"app_sha256": digest, "python": platform.python_version(), "qt": qVersion(),
              "platform": platform.platform(), "qt_platform": "offscreen", "synthetic_only": True}
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / "qa.ini"), QSettings.Format.IniFormat)))

    def select_formula(editor):
        cursor = editor.document().find(seed)
        assert not cursor.isNull() and cursor.selectedText() == seed
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        cursor.setPosition(end)
        cursor.setPosition(start, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)

    def drive(*, accept, change_path=None):
        failures, observations = [], []

        def respond():
            dialog = QApplication.activeModalWidget()
            try:
                assert isinstance(dialog, FormulaDialog), type(dialog)
                assert dialog.source_edit.toPlainText() == seed
                dialog.source_mode_check.setChecked(True)
                dialog.source_edit.setPlainText(replacement)
                buttons = dialog.findChild(QDialogButtonBox)
                if change_path is not None:
                    changed = b"% External header shifts the target.\r\n" + change_path.read_bytes()
                    change_path.write_bytes(changed)
                    window.documents.reload_external_change(str(change_path))
                    source = window.current_tab().editor.toPlainText()
                    buttons.button(QDialogButtonBox.StandardButton.Ok).click()
                    assert dialog.isVisible() and dialog.target_error_label.isVisible()
                    assert dialog.plan() is None and not dialog._submitted
                    assert dialog.source_edit.toPlainText() == replacement
                    assert dialog.preview_edit.toPlainText() == replacement
                    assert window.current_tab().editor.toPlainText() == source
                    assert change_path.read_bytes() == changed
                    assert dialog.grab().save(str(output / "formula-target-refused.png"))
                    observations.append("refused_with_copyable_draft")
                else:
                    assert dialog.grab().save(str(output / ("formula-apply.png" if accept else "formula-cancel.png")))
                    observations.append("accepted" if accept else "cancelled")
                choice = QDialogButtonBox.StandardButton.Ok if accept else QDialogButtonBox.StandardButton.Cancel
                buttons.button(choice).click()
                if accept:
                    assert not dialog.isVisible() and dialog.plan() is not None
            except Exception as exc:
                failures.append(exc)
                if dialog is not None:
                    dialog.reject()

        QTimer.singleShot(0, window, respond)
        window.open_formula_composer()
        assert not failures, failures
        assert len(observations) == 1
        return observations[0]

    try:
        window.auto_compile_action.setChecked(False)
        window.save_debounce_ms = 3_600_000
        window.project_files.set_project_root(project)
        window.open_file(root)
        window.resize(1120, 820)
        window.show()
        wait_for(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
        editor = window.current_tab().editor
        select_formula(editor)
        cursor = editor.textCursor()
        view = (cursor.position(), cursor.anchor(), editor.verticalScrollBar().value())
        report["cancel"] = drive(accept=False)
        cursor = editor.textCursor()
        assert (cursor.position(), cursor.anchor(), editor.verticalScrollBar().value()) == view
        assert editor.toPlainText() == before and root.read_bytes() == original
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.beginEditBlock()
        cursor.insertText("% prior unsaved edit\n")
        cursor.endEditBlock()
        prior = editor.toPlainText()
        select_formula(editor)
        report["apply"] = drive(accept=True)
        expected = prior.replace(seed, replacement).replace("\\newcommand", "\\usepackage{amsmath}\n\\newcommand", 1)
        assert editor.toPlainText() == expected
        editor.undo()
        assert editor.toPlainText() == prior
        editor.undo()
        assert editor.toPlainText() == before
        editor.redo()
        assert editor.toPlainText() == prior
        editor.redo()
        assert editor.toPlainText() == expected
        assert root.read_bytes() == original and not window.compile_authorized_roots
        report["exact_unicode_source_and_prior_undo_preserved"] = True
        view = (editor.textCursor().position(), editor.verticalScrollBar().value())
        assert window.save_current()
        assert root.read_text(encoding="utf-8") == expected
        assert (editor.textCursor().position(), editor.verticalScrollBar().value()) == view
        saved = root.read_bytes()
        window.close_tab(window._index_for_tab_id(id(editor)))
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(editor)
        window.open_file(root)
        editor = window.current_tab().editor
        assert editor.toPlainText() == expected
        view = (editor.textCursor().position(), editor.verticalScrollBar().value())
        window.compile.set_engine(LaTeXEngine.PDFLATEX, compile_after=False)
        window.compile_current(immediate=True, purpose=BuildPurpose.FINAL)
        wait_for(lambda: window.pdf_state.record_for(root).freshness == PdfFreshness.CURRENT)
        manager = window.compile_managers[root]
        wait_for(lambda: not manager.is_busy and window.pdf_panel._document is not None
                 and window.pdf_panel._document.pageCount() > 0)
        window.pdf_panel.fit_width()
        # Inspect this known synthetic equation at 200%, with it inside the view.
        # Its actual PDF glyph bounds are x=294..317, y=141..149 points. At fitted
        # scale antialiasing defeats the dark-pixel count; one zoom also clips it.
        window.pdf_panel.zoom_by(2.0 / window.pdf_panel._view.zoomFactor())
        view_widget = window.pdf_panel._view
        wait_for(lambda: view_widget.horizontalScrollBar().maximum() > 0)
        view_widget.horizontalScrollBar().setValue(view_widget.horizontalScrollBar().maximum() // 2)
        view_widget.verticalScrollBar().setValue(view_widget.verticalScrollBar().maximum() // 6)
        report["pdf_inspection_scroll"] = [view_widget.horizontalScrollBar().value(),
                                           view_widget.verticalScrollBar().value()]
        report["pdf_zoom_factor"] = window.pdf_panel._view.zoomFactor()
        try:
            wait_for(lambda: formula_view_stats(window)["formula_pixels_below_160"] > 20, seconds=15)
            stats = formula_view_stats(window)
            assert stats["blank_pixels_below_160"] == 0 and stats["formula_white_fraction"] > 0.8, stats
            report["visible_formula_contrast"] = stats
        except RuntimeError:
            window.grab().save(str(output / "formula-render-timeout.png"))
            print(json.dumps({"stage": "render_timeout", "ink": visible_pdf_ink(window),
                              "pdf_text": pdf_text(manager.pdf_file),
                              "viewport": [window.pdf_panel._view.viewport().width(),
                                           window.pdf_panel._view.viewport().height()]}, ensure_ascii=False), flush=True)
            raise
        wait_for(lambda: "FINAL" in window.workspace.details.full_text
                 and "\u6b63\u5728\u7f16\u8bd1" not in window.workspace.details.full_text, seconds=15)
        assert root.read_bytes() == saved
        assert (editor.textCursor().position(), editor.verticalScrollBar().value()) == view
        text = pdf_text(manager.pdf_file)
        assert "x+y" in text.replace(" ", "") and "Before" in text and "after." in text, text
        assert window.grab().save(str(output / "formula-final.png"))
        raw = manager.pdf_file.read_bytes()
        (output / "formula-final.pdf").write_bytes(raw)
        report.update(save_reopen_final=True, save_compile_view_preserved=True,
                      workspace_status=window.workspace.details.full_text, final_pdf_text=text,
                      final_pdf_sha256=hashlib.sha256(raw).hexdigest(),
                      saved_source_sha256=hashlib.sha256(saved).hexdigest())
        changed_path = project / "external-case.tex"
        changed_path.write_bytes(original)
        window.open_file(changed_path)
        editor = window.current_tab().editor
        select_formula(editor)
        report["external_reload"] = drive(accept=False, change_path=changed_path)
        assert seed in editor.toPlainText() and replacement not in editor.toPlainText()
        assert root.read_bytes() == saved
    finally:
        for tab in window.tabs.values():
            window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        assert window.close()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(window)
    assert digest == app_digest()
    report["limits"] = ["Offscreen widgets/PDF only; not native IME/AX/clipboard or Unicode-font acceptance",
                        "OCR workers and installed app unchanged; no release or student content edits"]
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
