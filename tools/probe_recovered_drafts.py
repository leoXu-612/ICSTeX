"""Actual synthetic capture/review/resume/edit/save/reopen/FINAL workflows."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.blocks.model import content_for_text
from app.core.blocks.project_repository import load_project
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness
from app.gui.block_mode import _install_session, _set_block_mode
from app.gui.blocks.project_session import ProjectSession
from app.gui.project_recovery_dialog import RecoveryDraftDialog
from app.gui.theme import apply_theme
from tests.v1_fixtures import create_project
from tools.probe_history_restore import app_digest, visible_pdf_ink
from tools.probe_project_checkpoint_gui import close, drive, window_for
from tools.probe_submission_check import wait_for


def resume(window, output, name, directory, *, cancel=False):
    timer = QTimer()
    timer.setInterval(20)
    state = {"phase": "start", "dialog": None, "confirmed": False}
    errors = []
    start = time.monotonic()
    def step():
        modal = QApplication.activeModalWidget()
        try:
            assert time.monotonic() - start < 45, "Recovery UI timed out"
            if isinstance(modal, QMessageBox):
                modal.grab().save(str(output / f"{name}-confirmation.png"))
                state["confirmed"] = True
                QTest.mouseClick(modal.button(QMessageBox.StandardButton.No if cancel else QMessageBox.StandardButton.Yes),
                                 Qt.MouseButton.LeftButton)
                return
            if not isinstance(modal, RecoveryDraftDialog) or modal.busy:
                return
            state["dialog"] = modal
            if state["phase"] == "start":
                state["phase"] = "loaded"
                modal.load_directory(directory)
                return
            if state["phase"] == "loaded":
                assert modal.copy is not None, modal.status.text()
                item = modal.tree.topLevelItem(0)
                assert item is not None
                item.setCheckState(0, Qt.CheckState.Checked)
                modal.tree.setCurrentItem(item)
                assert modal.grab().save(str(output / f"{name}-review.png"))
                state["phase"] = "sent"
                QTimer.singleShot(0, lambda: QTest.mouseClick(modal.apply_button, Qt.MouseButton.LeftButton))
            elif state["phase"] == "sent" and state["confirmed"]:
                if cancel:
                    modal.reject()
                elif modal.opened_window is None:
                    raise AssertionError(modal.status.text())
        except Exception as exc:
            errors.append(str(exc))
            if modal is not None:
                modal.reject()
    timer.timeout.connect(step)
    timer.start()
    window.recovery_drafts_action.trigger()
    timer.stop()
    assert not errors and state["confirmed"], (state, errors)
    result = state["dialog"].opened_window
    assert (result is None) == cancel
    return result


def install_block(window, project):
    loaded = load_project(project)
    session = ProjectSession(**{key: loaded[key] for key in
        ("registry", "layout", "sources", "document_theme", "project_dir")})
    assert not session.save_error, session.save_error
    assert _install_session(window, session)
    _set_block_mode(window, True)
    return session


def compile_and_check(window, kind, expected):
    if kind == "block":
        window.block_compile_action.trigger()
        wait_for(lambda: window.block_session.last_result is not None and window.block_session.last_result.ok)
        pdf = window.block_session.last_result.pdf_file
        if window.block_preview_area.pdf_button.isVisible():
            QTest.mouseClick(window.block_preview_area.pdf_button, Qt.MouseButton.LeftButton)
    else:
        root = window.selected_project_scope / "main.tex"
        window.open_file(root)
        window.compile.set_engine(LaTeXEngine.XELATEX, compile_after=False)
        window.compile_action.trigger()
        wait_for(lambda: window.pdf_state.record_for(root).freshness is PdfFreshness.CURRENT)
        pdf = window.pdf_state.record_for(root).last_successful_pdf
    wait_for(lambda: window.pdf_panel._document is not None and window.pdf_panel._document.pageCount() > 0)
    window.pdf_panel.fit_width()
    for _ in range(2):
        QTest.mouseClick(window.pdf_panel.zoom_in_button, Qt.MouseButton.LeftButton)
    if kind == "block":
        # The reopened compact window has a 196-pixel PDF viewport; at this
        # zoom the first line is below its bottom edge. Scroll the real view
        # into the page instead of treating a blank margin as renderer failure.
        bar = window.pdf_panel._view.verticalScrollBar()
        bar.setValue(bar.value() + max(1, bar.pageStep() // 3))
    wait_for(lambda: visible_pdf_ink(window) > 30, seconds=15)
    text = " ".join(window.pdf_panel._document.getAllText(i).text()
                    for i in range(window.pdf_panel._document.pageCount()))
    assert expected in " ".join(text.split()), text
    return hashlib.sha256(pdf.read_bytes()).hexdigest()


def run(output):
    output = output.expanduser().resolve()
    output.mkdir(parents=False, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    digest = app_digest()
    evidence = {"app_sha256": digest, "platform": platform.platform(), "qt_platform": app.platformName(),
                "synthetic_only": True, "workflows": []}
    for kind in ("multi", "block"):
        fixture = create_project(output, kind)
        project = fixture.root.parent
        before = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
        window = window_for(output, kind)
        new = reopened = None
        try:
            window.project_files.set_project_root(project)
            window.open_file(fixture.root)
            window.show()
            if kind == "multi":
                window.open_file(fixture.draft_path)
                window.current_tab().editor.appendPlainText("Recovered source working text.")
                expected = "Recovered source working text."
            else:
                session = install_block(window, project)
                block = session.registry.blocks()[0]
                session.registry.update(block.id, {"content": content_for_text("Recovered Block model text.")})
                session.notify_model_changed("synthetic-unsaved-model")
                session.selection.select_block(block.id, source="recovery-probe")
                content = window.block_inspector.content_edit
                content.selectAll()
                QTest.keyClicks(content, "Recovered Block editing draft.")
                expected = "Recovered Block editing draft."
                assert session.editor_drafts
            archive = output / f"{kind}.icstex-checkpoint"
            restored = output / f"{kind}-recovered"
            drive(window, output, f"{kind}-create", None, archive)
            drive(window, output, f"{kind}-restore", archive, restored, restore=True)
            draft_files = {p: p.read_bytes() for p in (restored / "drafts").iterdir()}
            resume(window, output, f"{kind}-cancel", restored, cancel=True)
            assert all((restored / "project" / p).read_bytes() == raw for p, raw in before.items())
            new = resume(window, output, f"{kind}-resume", restored)
            new.resize(1280, 850)
            app.processEvents()
            assert new.grab().save(str(output / f"{kind}-resumed-editor.png"))
            QTest.qWait(900)
            assert all((restored / "project" / p).read_bytes() == raw for p, raw in before.items())
            if kind == "multi":
                text = new.current_tab().editor.toPlainText()
                new.current_tab().editor.undo()
                assert expected not in new.current_tab().editor.toPlainText()
                new.current_tab().editor.redo()
                assert new.current_tab().editor.toPlainText() == text
                new.save_action.trigger()
                assert not new.current_tab().modified
            else:
                recovered = new.block_session
                assert recovered.registry.get(block.id).content["text"] == "Recovered Block model text."
                assert new.block_inspector.content_edit.toPlainText() == expected
                QTest.mouseClick(new.block_inspector.apply_button, Qt.MouseButton.LeftButton)
                assert not recovered.editor_drafts
                assert recovered.registry.get(block.id).content["text"] == expected
                recovered.undo_stack.undo()
                assert recovered.registry.get(block.id).content["text"] == "Recovered Block model text."
                recovered.undo_stack.redo()
                QTest.qWait(800)
                assert all((restored / "project" / p).read_bytes() == raw for p, raw in before.items())
                new.block_save_action.trigger()
                assert recovered.last_save_ok, recovered.save_error
            first_pdf = compile_and_check(new, kind, expected)
            assert new.grab().save(str(output / f"{kind}-resumed-final.png"))
            assert all((project / p).read_bytes() == raw for p, raw in before.items())
            assert all(p.read_bytes() == raw for p, raw in draft_files.items())
            close(new)
            new = None
            reopened = window_for(output, kind + "-reopened")
            recovered_project = restored / "project"
            reopened.project_files.set_project_root(recovered_project)
            if kind == "block":
                loaded = install_block(reopened, recovered_project)
                assert loaded.registry.get(block.id).content["text"] == expected
            else:
                reopened.open_file(recovered_project / "main.tex")
            reopened.show()
            second_pdf = compile_and_check(reopened, kind, expected)
            assert reopened.grab().save(str(output / f"{kind}-saved-reopened-final.png"))
            evidence["workflows"].append({"kind": kind, "cancel_zero_project_writes": True,
                "no_implicit_save_or_apply": True, "actual_draft_resume_undo_redo_save": True,
                "original_and_draft_bytes_unchanged": True, "saved_reopened_final_contains": expected,
                "resumed_final_pdf_sha256": first_pdf, "reopened_final_pdf_sha256": second_pdf})
        finally:
            for live in (reopened, new, window):
                if live is not None:
                    close(live)
    assert app_digest() == digest
    evidence["limits"] = ["Native directory picker not automated; paths entered in actual dialogs",
        "Offscreen does not establish native IME, AX, Windows or human acceptance",
        "No journal recovery or format migration acceptance in this probe",
        "No package, installation, Git operation, credentials or release"]
    (output / "result.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
