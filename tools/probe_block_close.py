"""Native synthetic Block save/cancel/conflict/FINAL probe.

Edits use the existing UI command controller; close choices use real native
QMessageBoxes and keyboard Space. This is not IME or human usability evidence.
Only disposable project/settings files and a new evidence directory are written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.blocks.model import content_for_text
from app.core.blocks.project_repository import load_project
from app.core.compiler import BuildPurpose
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness
from app.core.settings import AppSettings
from app.gui.block_mode import _install_session, _set_block_mode
from app.gui.blocks.project_dialog import BlockProjectDialog
from app.gui.blocks.project_session import ProjectSession
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tests.v1_fixtures import create_project
from tools.probe_submission_check import wait_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("ICSTeX V1 Block Close QA")
    apply_theme(app)
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    evidence = {"platform": platform.platform(), "python": platform.python_version(),
                "qt_platform": app.platformName(), "app_python_tree_sha256": digest.hexdigest()}
    errors = []
    with TemporaryDirectory(prefix="icstex-v1-block-close-qa-") as directory:
        base = Path(directory).resolve()
        source = create_project(base, "single")
        block = create_project(base, "block")
        source_bytes = source.root.read_bytes()
        settings = AppSettings(QSettings(str(base / "qa.ini"), QSettings.Format.IniFormat))
        window = MainWindow(settings_store=settings)
        owned_dialog = None

        def install():
            state = load_project(block.root.parent)
            session = ProjectSession(**{key: state[key] for key in
                ("registry", "layout", "sources", "document_theme", "project_dir")})
            assert _install_session(window, session)
            _set_block_mode(window, True)
            return session

        def edit(session, text):
            item = session.registry.blocks()[0]
            window.block_nav.controller.update_block(item.id, {"content": content_for_text(text)})
            assert session.has_unsaved_changes
            return item

        def choices(session, steps, unchanged=None):
            pending = list(steps)
            deadline = time.monotonic() + 20
            def advance():
                dialog = app.activeModalWidget()
                if not isinstance(dialog, QMessageBox):
                    if time.monotonic() < deadline:
                        QTimer.singleShot(40, advance)
                    else:
                        errors.append("Expected a native close warning")
                    return
                button_id, name, hold = pending.pop(0)
                try:
                    assert not session._save_timer.isActive()
                    assert not session._preview_timer.isActive()
                    if hold:
                        QTest.qWait(650)
                    if unchanged is not None:
                        assert all(path.read_bytes() == data for path, data in unchanged.items())
                    assert dialog.grab().save(str(output / f"{name}.png"))
                    button = dialog.button(button_id)
                    assert button is not None, (dialog.windowTitle(), name)
                    button.setFocus()
                    # A save error can enter another modal loop during keyClick.
                    if pending:
                        QTimer.singleShot(60, advance)
                    QTest.keyClick(button, Qt.Key.Key_Space)
                except BaseException as exc:
                    errors.append(f"{name}: {exc!r}")
                    dialog.done(QMessageBox.StandardButton.Cancel)
            QTimer.singleShot(80, advance)

        try:
            window.auto_compile_action.setChecked(False)
            window.project_files.set_project_root(source.root.parent)
            window.open_file(source.root)
            window.set_engine(LaTeXEngine.PDFLATEX)
            window.resize(1120, 860)
            window.show()
            window.raise_()
            window.activateWindow()
            window.compile_action.trigger()
            wait_for(lambda: window.pdf_state.record_for(source.root).freshness is PdfFreshness.CURRENT)
            source_record = window.pdf_state.record_for(source.root)
            source_pdf = source_record.last_successful_pdf
            wait_for(lambda: window.pdf_panel._document is not None and window.pdf_panel._document.pageCount() > 0)
            tab = window.current_tab()
            cursor = tab.editor.textCursor()
            cursor.setPosition(14)
            tab.editor.setTextCursor(cursor)
            source_view = (cursor.position(), tab.editor.verticalScrollBar().value())

            session = install()
            original = {p: p.read_bytes() for p in block.root.parent.rglob("*") if p.is_file()}
            item = edit(session, "Native save-close draft")
            content = dict(item.content)
            choices(session, [(QMessageBox.StandardButton.Cancel, "block-cancel-100", True)], original)
            window.close_block_project_action.trigger()
            assert not errors, errors
            assert window.block_session is session and not session._closed
            assert session.has_unsaved_changes and session._save_timer.isActive()
            assert all(p.read_bytes() == data for p, data in original.items())
            assert session.compile_manager is None
            evidence["cancel_paused_writes_and_retained_draft"] = True
            choices(session, [(QMessageBox.StandardButton.Save, "block-save-100", False)])
            window.close_block_project_action.trigger()
            assert not errors, errors
            assert session._closed and window.block_session is None
            assert load_project(block.root.parent)["registry"].get(item.id).content == content
            assert session.compile_manager is None
            assert b"Native save-close draft" in block.draft_path.read_bytes()
            assert window.pdf_panel.current_pdf == source_pdf
            assert (tab.editor.textCursor().position(), tab.editor.verticalScrollBar().value()) == source_view
            evidence["save_close_model_readback_no_compile_source_view_preserved"] = True

            # Reopen the same saved model/generation version, without compiling.
            session = install()
            assert not session.save_error, session.save_error
            pulses = []
            heartbeat = QTimer()
            heartbeat.setInterval(10)
            heartbeat.timeout.connect(lambda: pulses.append(time.monotonic()))
            heartbeat.start()
            start = time.monotonic()
            assert window.block_compile_action.isEnabled()
            window.block_compile_action.trigger()
            evidence["final_action_dispatch_ms"] = (time.monotonic() - start) * 1000
            wait_for(lambda: session.compile_manager is not None and session.compile_manager.is_busy)
            assert window.block_stop_action.isEnabled()
            window.workspace.refresh()
            assert window.workspace.next_button.defaultAction() is window.block_stop_action
            wait_for(lambda: session.last_result is not None)
            heartbeat.stop()
            result = session.last_result
            assert result.ok and result.purpose is BuildPurpose.FINAL, result
            assert result.job_key.source_revision == session._revision
            assert session.final_evidence is not None
            assert len(pulses) > 2, pulses
            assert window.pdf_state.record_for(source.root) is source_record
            wait_for(lambda: not session.compile_manager.is_busy)
            wait_for(lambda: window.pdf_panel.current_pdf == result.pdf_file and
                     window.pdf_panel._document is not None and window.pdf_panel._document.pageCount() > 0)
            evidence["final_heartbeat_ticks"] = len(pulses)
            evidence["final_pdf_pages"] = window.pdf_panel._document.pageCount()
            pdf_text = window.pdf_panel._document.getAllText(0).text()
            assert "Native save-close draft" in pdf_text, pdf_text
            evidence["final_contains_saved_draft"] = True
            evidence["final_sha256"] = hashlib.sha256(result.pdf_file.read_bytes()).hexdigest()
            (output / "block-final.pdf").write_bytes(result.pdf_file.read_bytes())
            evidence["final_job_purpose"] = result.purpose.value
            QTest.qWait(500)
            assert window.block_compile_action.isEnabled()
            assert not window.block_stop_action.isEnabled()
            assert not session.final_is_running
            window.workspace.refresh()
            window.block_preview_area.pdf_button.click()
            QTest.qWait(200)
            assert window.grab().save(str(output / "block-final-100.png"))

            window.set_ui_scale(1.5)
            QTest.qWait(200)
            edit(session, "Unsaved conflicting native model")
            winner_path = block.root.parent / ".icstex/sources.json"
            winner = winner_path.read_bytes() + b" \n"
            winner_path.write_bytes(winner)
            conflict_before = {p: p.read_bytes() for p in original}
            choices(session, [(QMessageBox.StandardButton.Save, "window-save-conflict-150", True),
                              (QMessageBox.StandardButton.Ok, "save-refused-150", False)], conflict_before)
            assert not window.close()
            assert not errors, errors
            assert window.isVisible() and window.block_session is session and not session._closed
            assert session.has_unsaved_changes and session.save_error
            assert not session._save_timer.isActive() and not session._preview_timer.isActive()
            assert all(p.read_bytes() == data for p, data in conflict_before.items())
            window.workspace.refresh()
            assert window.grab().save(str(output / "conflict-draft-retained-150.png"))
            evidence["external_conflict_refused_close_and_preserved_both_sides"] = True
            choices(session, [(QMessageBox.StandardButton.Discard, "discard-150", False)], conflict_before)
            assert window.close()
            assert session._closed
            session.save_now()
            session.request_save("synthetic late callback")
            session._fire_preview()
            QTest.qWait(750)
            assert all(p.read_bytes() == data for p, data in conflict_before.items())
            assert source.root.read_bytes() == source_bytes
            evidence["discard_and_late_callbacks_did_not_change_external_winner"] = True

            # Legacy owned dialog Esc uses the same real Save/Discard/Cancel gate.
            owned_dialog = BlockProjectDialog(project_dir=base / "new-dialog-project")
            dialog_session = owned_dialog.session
            owned_dialog.controller.add_block("text", content=content_for_text("Owned dialog draft"))
            owned_dialog.show()
            choices(dialog_session, [(QMessageBox.StandardButton.Cancel, "dialog-escape-cancel", False)])
            QTest.keyClick(owned_dialog, Qt.Key.Key_Escape)
            assert not errors and owned_dialog.isVisible() and not dialog_session._closed, errors
            choices(dialog_session, [(QMessageBox.StandardButton.Discard, "dialog-close-discard", False)])
            assert owned_dialog.close()
            assert not errors and dialog_session._closed, errors
            assert not (base / "new-dialog-project").exists()
            evidence["owned_dialog_escape_cancel_and_close_discard"] = True
            evidence["limits"] = ["Synthetic controller edits, not IME or human keyboard acceptance",
                "No AX/Windows/installation acceptance", "Block high-scale body layout still needs work",
                "Pending write evidence is not a completed M4 checkpoint"]
        finally:
            if owned_dialog is not None:
                owned_dialog.session.shutdown()
                owned_dialog.close()
            if window.block_session is not None:
                window.block_session.shutdown()
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            window.close()
            app.processEvents()
    (output / "report.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
