"""Offscreen real-dialog insertion, Undo, save/reopen and visible FINAL probe.

Uses only a newly created synthetic project. No native focus or keyboard claim.
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
from app.gui.insert_panel import TableDialog
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.probe_history_restore import app_digest, visible_pdf_ink
from tools.probe_submission_check import wait_for
from tools.probe_submission_delivery import pdf_text


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
    original = ("% \U0001f600\U0001f680 synthetic Unicode comment\r\n"
                "\\documentclass{article}\r\n"
                "\\newcommand{\\studentMacro}{Unchanged macro}\r\n"
                "\\begin{document}\r\n\\studentMacro\r\nBody\r\n\\end{document}\r\n").encode()
    root.write_bytes(original)
    digest = app_digest()
    report = {"app_sha256": digest, "python": platform.python_version(),
              "qt": qVersion(), "platform": platform.platform(), "qt_platform": "offscreen",
              "synthetic_only": True, "cancel_cycles": 0}
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / "qa.ini"), QSettings.Format.IniFormat)))

    def insert(*, accept, screenshot=False, change_path=None):
        dialogs, failures = [], []

        def respond():
            dialog = QApplication.activeModalWidget()
            try:
                assert isinstance(dialog, TableDialog), type(dialog)
                dialogs.append(dialog)
                dialog.preview_table.item(0, 0).setText("Value")
                dialog.preview_table.item(1, 0).setText("0")
                dialog.caption_edit.setText("Measured values")
                dialog.label_edit.setText("tab:measured")
                if screenshot:
                    assert dialog.grab().save(str(output / "table-dialog.png"))
                buttons = dialog.findChild(QDialogButtonBox)
                if change_path is not None:
                    changed = b"% External edit adds a header line.\r\n" + change_path.read_bytes()
                    change_path.write_bytes(changed)
                    window.documents.reload_external_change(str(change_path))
                    before = window.current_tab().editor.toPlainText()
                    draft = dialog.values()
                    buttons.button(QDialogButtonBox.StandardButton.Ok).click()
                    assert dialog.isVisible() and dialog.target_error_label.isVisible()
                    assert dialog.values() == draft and dialog.source_preview.isVisible()
                    assert window.current_tab().editor.toPlainText() == before
                    assert change_path.read_bytes() == changed
                    assert dialog.grab().save(str(output / "table-target-refused.png"))
                    report["external_reload_refused_with_copyable_draft"] = True
                choice = QDialogButtonBox.StandardButton.Ok if accept else QDialogButtonBox.StandardButton.Cancel
                buttons.button(choice).click()
            except Exception as exc:
                failures.append(exc)
                if dialog is not None:
                    dialog.reject()

        QTimer.singleShot(0, window, respond)
        window.insert_table()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not failures, failures
        assert len(dialogs) == 1 and not isValid(dialogs[0])
        assert not window.findChildren(TableDialog)

    try:
        window.auto_compile_action.setChecked(False)
        window.save_debounce_ms = 3_600_000
        window.project_files.set_project_root(project)
        window.open_file(root)
        window.resize(1120, 820)
        window.show()
        wait_for(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
        tab = window.current_tab()
        editor = tab.editor
        before = editor.toPlainText()
        for index in range(6):
            insert(accept=False, screenshot=index == 0)
            assert editor.toPlainText() == before and root.read_bytes() == original
            report["cancel_cycles"] += 1
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.beginEditBlock()
        cursor.insertText("% prior unsaved edit\n")
        cursor.endEditBlock()
        prior = editor.toPlainText()
        start = len(prior[:prior.index("Body")].encode("utf-16-le")) // 2
        cursor.setPosition(start + 4)
        cursor.setPosition(start, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        insert(accept=True)
        after = editor.toPlainText()
        assert "Body" not in after and r"\caption{Measured values}" in after
        assert r"\label{tab:measured}" in after and "0 &" in after
        assert after.count(r"\usepackage{array}") == after.count(r"\usepackage{booktabs}") == 1
        editor.undo()
        assert editor.toPlainText() == prior
        editor.undo()
        assert editor.toPlainText() == before
        editor.redo()
        assert editor.toPlainText() == prior
        editor.redo()
        assert editor.toPlainText() == after
        assert root.read_bytes() == original and not window.compile_authorized_roots
        report["one_undo_and_prior_history_preserved"] = True
        view = (editor.textCursor().position(), editor.verticalScrollBar().value())
        assert window.save_current()
        assert root.read_text(encoding="utf-8") == after
        assert (editor.textCursor().position(), editor.verticalScrollBar().value()) == view
        assert not window.compile_authorized_roots
        saved = root.read_bytes()
        window.close_tab(window._index_for_tab_id(id(editor)))
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(editor)
        window.open_file(root)
        editor = window.current_tab().editor
        assert editor.toPlainText() == after
        view = (editor.textCursor().position(), editor.verticalScrollBar().value())
        window.compile.set_engine(LaTeXEngine.PDFLATEX, compile_after=False)
        window.compile_current(immediate=True, purpose=BuildPurpose.FINAL)
        wait_for(lambda: window.pdf_state.record_for(root).freshness == PdfFreshness.CURRENT)
        manager = window.compile_managers[root]
        wait_for(lambda: not manager.is_busy and window.pdf_panel._document is not None
                 and window.pdf_panel._document.pageCount() > 0)
        window.pdf_panel.fit_width()
        wait_for(lambda: visible_pdf_ink(window) > 20)
        wait_for(lambda: "FINAL" in window.workspace.details.full_text
                 and "\u6b63\u5728\u7f16\u8bd1" not in window.workspace.details.full_text, seconds=15)
        text = pdf_text(manager.pdf_file)
        assert "Measured values" in text and "Value" in text and "0" in text and "Unchanged macro" in text, text
        assert root.read_bytes() == saved
        assert (editor.textCursor().position(), editor.verticalScrollBar().value()) == view
        assert window.grab().save(str(output / "table-final.png"))
        raw = manager.pdf_file.read_bytes()
        (output / "table-final.pdf").write_bytes(raw)
        report.update(save_reopen_final=True, save_compile_view_preserved=True,
                      workspace_status=window.workspace.details.full_text,
                      final_pdf_text=text, final_pdf_sha256=hashlib.sha256(raw).hexdigest(),
                      saved_source_sha256=hashlib.sha256(saved).hexdigest())
        changed_path = project / "external-case.tex"
        changed_path.write_bytes(original)
        window.open_file(changed_path)
        editor = window.current_tab().editor
        start = len(editor.toPlainText().split("Body")[0].encode("utf-16-le")) // 2
        cursor = editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(start + 4, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        insert(accept=False, change_path=changed_path)
        assert r"\begin{table}" not in editor.toPlainText()
        assert r"\documentclass{article}" in editor.toPlainText()
        assert root.read_bytes() == saved
    finally:
        for tab in window.tabs.values():
            window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        assert window.close()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(window)
    assert digest == app_digest()
    report["limits"] = ["Offscreen actual widgets and PDF only; not Cocoa/physical input/AX acceptance",
                        "No release, installation, packaging or student data changes"]
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
