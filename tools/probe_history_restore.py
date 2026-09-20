"""Actual synthetic History panel/confirmation/Undo/save/reopen/FINAL workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QEvent, QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMessageBox
from app.core.history import create_snapshot, list_snapshots
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness
from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.probe_submission_check import wait_for


def app_digest():
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def drive_restore(window, output, name, *, accept, error=False):
    timer = QTimer()
    timer.setInterval(15)
    seen, failures = [], []
    start = time.monotonic()

    def respond():
        dialog = QApplication.activeModalWidget()
        if dialog is None:
            return
        try:
            assert isinstance(dialog, QMessageBox), type(dialog)
            assert time.monotonic() - start < 10, "History modal timed out"
            assert dialog.grab().save(str(output / (name + "-dialog.png")))
            seen.append(dialog.text().splitlines()[0])
            if error:
                assert dialog.text().startswith("历史恢复失败"), dialog.text()
                button = dialog.button(QMessageBox.StandardButton.Ok)
            else:
                assert dialog.text().startswith("文件：main.tex"), dialog.text()
                button = dialog.button(QMessageBox.StandardButton.Yes if accept else QMessageBox.StandardButton.No)
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        except Exception as exc:
            failures.append(str(exc))
            dialog.reject()
    timer.timeout.connect(respond)
    timer.start()
    assert window.history_panel.restore_button.isEnabled()
    QTest.mouseClick(window.history_panel.restore_button, Qt.MouseButton.LeftButton)
    timer.stop()
    assert seen and not failures, (seen, failures)


def close(window):
    for tab in window.tabs.values():
        window.documents.cancel_save_timer(tab)
        tab.modified = tab.dirty = False
    window.close()
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def visible_pdf_ink(window):
    picture = window.pdf_panel._view.viewport().grab().toImage()
    # Inspect every pixel: a stride of two aliases thin, antialiased glyphs and
    # rejected an actually rendered page (verified in the retained r4/r5 images).
    return sum(picture.pixelColor(x, y).lightness() < 100
               for y in range(20, max(20, picture.height() - 20))
               for x in range(20, max(20, picture.width() - 20)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.expanduser().resolve()
    output.mkdir(parents=False, exist_ok=False)
    application = QApplication.instance() or QApplication([])
    application.setQuitOnLastWindowClosed(False)
    apply_theme(application)
    project = output / "synthetic-project"
    project.mkdir()
    source = project / "main.tex"
    old = ("\\documentclass{article}\n\\newcommand{\\localmacro}[1]{#1}\n"
           "\\begin{document}\n\\section{Recovered history}\n"
           "\\localmacro{An unchanged custom macro.}\n\\end{document}\n")
    saved = old.replace("Recovered history", "Current saved version")
    draft = saved.replace("Current saved version", "Unapplied current draft")
    source.write_bytes(saved.encode())
    snapshot = create_snapshot(source, old, "synthetic prior version")
    before = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    evidence = {"app_sha256": app_digest(), "platform": platform.platform(),
                "qt_platform": application.platformName(), "synthetic_only": True}
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / "qa.ini"), QSettings.Format.IniFormat)))
    try:
        window.auto_compile_action.setChecked(False)
        window.project_files.set_project_root(project)
        window.open_file(source)
        window.resize(1120, 820)
        window.show()
        wait_for(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
        tab = window.current_tab()
        editor = tab.editor
        editor.setPlainText(draft)
        window.documents.cancel_save_timer(tab)
        tab.pending_compile_after_save = False
        window.toolbox_dock.show()
        window.sidebar_tabs.setCurrentIndex(4)
        window.refresh_project_panels()
        assert window.history_panel.table.rowCount() == 1
        window.history_panel.table.selectRow(0)
        assert window.grab().save(str(output / "history-before.png"))
        drive_restore(window, output, "cancel", accept=False)
        assert editor.toPlainText() == draft
        assert all((project / path).read_bytes() == data for path, data in before.items())
        evidence["cancel_all_project_bytes_unchanged"] = True
        snapshot.snapshot_path.write_text("valid UTF-8 but corrupt history", encoding="utf-8")
        drive_restore(window, output, "corrupt", accept=True, error=True)
        assert editor.toPlainText() == draft and source.read_bytes() == saved.encode()
        snapshot.snapshot_path.write_bytes(old.encode())
        evidence["corrupt_history_refused"] = True
        drive_restore(window, output, "restore", accept=True)
        assert editor.toPlainText() == old and source.read_bytes() == saved.encode()
        assert not tab.save_timer.isActive() and not tab.pending_compile_after_save
        assert not window.compile_authorized_roots
        assert window.grab().save(str(output / "history-restored-unsaved.png"))
        editor.setFocus()
        QTest.keySequence(editor, QKeySequence(QKeySequence.StandardKey.Undo))
        assert editor.toPlainText() == draft
        window.documents.cancel_save_timer(tab)
        QTest.keySequence(editor, QKeySequence(QKeySequence.StandardKey.Redo))
        assert editor.toPlainText() == old
        window.documents.cancel_save_timer(tab)
        evidence["one_undo_redo_restores_both_drafts"] = True
        evidence["restore_does_not_save_or_authorize_compile"] = True
        # The following is a separate explicit Save, not a side effect of Restore.
        assert window.save_current()
        assert source.read_bytes() == old.encode()
        assert any(item.sha256 == hashlib.sha256(old.encode()).hexdigest() for item in list_snapshots(source))
        evidence["explicit_save_matches_chosen_history"] = True
    finally:
        close(window)
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / "reopen.ini"), QSettings.Format.IniFormat)))
    try:
        window.auto_compile_action.setChecked(False)
        window.project_files.set_project_root(project)
        window.open_file(source)
        assert window.current_tab().editor.toPlainText() == old
        window.compile.set_engine(LaTeXEngine.PDFLATEX, compile_after=False)
        window.resize(1120, 820)
        window.show()
        assert not window.compile_authorized_roots
        window.compile_action.trigger()
        wait_for(lambda: window.pdf_state.record_for(source).freshness == PdfFreshness.CURRENT)
        wait_for(lambda: window.pdf_panel._document is not None and window.pdf_panel._document.pageCount() > 0)
        window.pdf_panel.fit_width()
        try:
            wait_for(lambda: visible_pdf_ink(window) > 30, seconds=15)
        except RuntimeError:
            window.grab().save(str(output / "pdf-wait-failed.png"))
            print("Visible ink pixels:", visible_pdf_ink(window), flush=True)
            raise
        wait_for(lambda: "FINAL" in window.workspace.details.full_text
                 and "正在编译" not in window.workspace.details.full_text, seconds=5)
        pdf = window.pdf_state.record_for(source).last_successful_pdf
        payload = pdf.read_bytes()
        (output / "history-final.pdf").write_bytes(payload)
        evidence["final_pdf_sha256"] = hashlib.sha256(payload).hexdigest()
        evidence["final_pages"] = window.pdf_panel._document.pageCount()
        evidence["visible_pdf_dark_pixels"] = visible_pdf_ink(window)
        pdf_text = window.pdf_panel._document.getAllText(0).text()
        assert "Recovered history" in pdf_text and "An unchanged custom macro." in pdf_text, pdf_text
        evidence["final_pdf_text_matches_selected_history"] = True
        evidence["workspace_final_status"] = window.workspace.details.full_text
        assert source.read_bytes() == old.encode()
        assert window.grab().save(str(output / "history-reopened-final.png"))
    finally:
        close(window)
    assert app_digest() == evidence["app_sha256"]
    evidence["limits"] = ["Synthetic offscreen workflow is not native IME/AX or Windows acceptance",
                           "Single-source text history is not the M4 project checkpoint GUI",
                           "No package, installed-app replacement, network lookup or release"]
    (output / "result.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
