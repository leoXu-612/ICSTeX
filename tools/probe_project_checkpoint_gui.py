"""Synthetic actual checkpoint dialogs, independent drafts and reopened FINAL."""
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
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.blocks.project_repository import load_project
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness
from app.core.project_checkpoint import inspect_checkpoint
from app.core.settings import AppSettings
from app.gui.block_mode import _install_session
from app.gui.blocks.project_session import ProjectSession
from app.gui.main_window import MainWindow
from app.gui.project_checkpoint_dialog import ProjectCheckpointDialog
from app.gui.theme import apply_theme
from tests.v1_fixtures import create_project
from tools.probe_history_restore import app_digest, visible_pdf_ink
from tools.probe_submission_check import wait_for


def window_for(output, name):
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / f"{name}.ini"), QSettings.Format.IniFormat)))
    window.auto_compile_action.setChecked(False)
    window.save_debounce_ms = 3600000
    window.resize(1120, 820)
    return window


def close(window):
    for tab in window.tabs.values():
        window.documents.cancel_save_timer(tab)
        tab.modified = tab.dirty = False
    session = getattr(window, "block_session", None)
    if session:
        session.editor_drafts.clear()
        session._dirty = False
    window.close()
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def drive(window, output, name, archive, target, *, restore=False, cancel_confirmation=False):
    timer = QTimer()
    timer.setInterval(20)
    phase = {"value": "start"}
    seen, errors = [], []
    started = time.monotonic()

    def step():
        modal = QApplication.activeModalWidget()
        try:
            assert time.monotonic() - started < 45, "Checkpoint dialog timed out"
            if isinstance(modal, QMessageBox):
                seen.append("confirmation")
                modal.grab().save(str(output / f"{name}-confirmation.png"))
                QTest.mouseClick(modal.button(QMessageBox.StandardButton.No if cancel_confirmation
                                             else QMessageBox.StandardButton.Yes), Qt.MouseButton.LeftButton)
                return
            if not isinstance(modal, ProjectCheckpointDialog) or modal.busy:
                return
            if phase["value"] == "start" and restore:
                phase["value"] = "ready"
                modal.load_archive(archive)
                return
            if phase["value"] in {"start", "ready"}:
                assert modal.tree.topLevelItemCount() > 0, modal.status.text()
                for index in range(modal.tree.topLevelItemCount()):
                    item = modal.tree.topLevelItem(index)
                    if item.data(0, Qt.ItemDataRole.UserRole)[0] == "draft":
                        modal.tree.setCurrentItem(item)
                        break
                modal.target.setText(str(target))
                assert modal.grab().save(str(output / f"{name}-review.png"))
                phase["value"] = "sent"
                QTimer.singleShot(0, lambda: QTest.mouseClick(modal.action_button, Qt.MouseButton.LeftButton))
                return
            if phase["value"] == "sent":
                if not seen:
                    return
                assert cancel_confirmation or target.exists(), modal.status.text()
                assert modal.grab().save(str(output / f"{name}-result.png"))
                phase["value"] = "done"
                modal.reject()
        except Exception as exc:
            errors.append(str(exc))
            if isinstance(modal, ProjectCheckpointDialog):
                modal.reject()
            elif modal is not None:
                modal.reject()

    timer.timeout.connect(step)
    timer.start()
    (window.restore_checkpoint_action if restore else window.project_checkpoint_action).trigger()
    timer.stop()
    assert phase["value"] == "done" and not errors, (phase, errors)
    assert not getattr(QApplication.instance(), "_icstex_checkpoint_dialog", None)


def run(output):
    output = output.expanduser().resolve()
    output.mkdir(parents=False, exist_ok=False)
    application = QApplication.instance() or QApplication([])
    application.setQuitOnLastWindowClosed(False)
    apply_theme(application)
    initial_app = app_digest()
    evidence = {"app_sha256": initial_app, "platform": platform.platform(),
                "qt_platform": application.platformName(), "synthetic_only": True, "workflows": []}
    for kind in ("multi", "block"):
        fixture = create_project(output, kind)
        project = fixture.root.parent
        (project / "legacy.tex").write_bytes(b"% " + "原始字节".encode("gbk") + b"\r\n")
        original = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
        window = window_for(output, kind)
        try:
            window.project_files.set_project_root(project)
            window.open_file(fixture.root)
            window.open_file(fixture.draft_path)
            editor = window.current_tab().editor
            editor.moveCursor(editor.textCursor().MoveOperation.End)
            editor.insertPlainText("\n% actual unsaved GUI buffer\n")
            source_draft = editor.toPlainText()
            if kind == "block":
                model = load_project(project)
                session = ProjectSession(project_dir=project, registry=model["registry"], layout=model["layout"],
                                         sources=model["sources"], document_theme=model["document_theme"])
                assert _install_session(window, session)
                window.block_mode_action.setChecked(True)
                block = session.registry.blocks()[0]
                session.selection.select_block(block.id, source="checkpoint-probe")
                alias = window.block_inspector.alias_edit
                alias.setFocus()
                alias.selectAll()
                QTest.keyClicks(alias, "pending-recovery-alias")
                assert session.editor_drafts, "Actual Inspector input did not form a draft"
                assert block.alias != "pending-recovery-alias"
            window.show()
            application.processEvents()
            cancelled = output / f"{kind}-cancelled.icstex-checkpoint"
            drive(window, output, f"{kind}-cancel", None, cancelled, cancel_confirmation=True)
            assert not cancelled.exists()
            assert all((project / p).read_bytes() == raw for p, raw in original.items())
            archive = output / f"{kind}.icstex-checkpoint"
            drive(window, output, f"{kind}-create", None, archive)
            info = inspect_checkpoint(archive)
            assert {entry.path for entry in info.files} == set(original)
            assert len(info.drafts) == (2 if kind == "block" else 1)
            restored = output / f"{kind}-restored"
            drive(window, output, f"{kind}-restore", archive, restored, restore=True)
            assert all((project / p).read_bytes() == raw for p, raw in original.items())
            assert all((restored / "project" / p).read_bytes() == raw for p, raw in original.items())
            text_entry = next(entry for entry in info.drafts if entry.kind == "source-text")
            assert (restored / "drafts" / f"{text_entry.id}.txt").read_text() == source_draft
            if kind == "block":
                block_entry = next(entry for entry in info.drafts if entry.kind == "block-state")
                draft = json.loads((restored / "drafts" / f"{block_entry.id}.json").read_text())
                assert draft["unapplied"][0]["values"]["alias"] == "pending-recovery-alias"
                assert draft["model"]["blocks"][0]["alias"] != "pending-recovery-alias"
                assert load_project(restored / "project")["registry"].blocks()[0].alias == block.alias
            assert not window.compile_authorized_roots
        finally:
            close(window)
        # Explicitly reopen and compile only the restored saved version, not drafts.
        window = window_for(output, kind + "-reopened")
        try:
            root = restored / "project/main.tex"
            window.project_files.set_project_root(root.parent)
            window.open_file(root)
            window.compile.set_engine(LaTeXEngine.XELATEX, compile_after=False)
            window.show()
            window.compile_action.trigger()
            wait_for(lambda: window.pdf_state.record_for(root).freshness == PdfFreshness.CURRENT)
            wait_for(lambda: window.pdf_panel._document is not None and window.pdf_panel._document.pageCount() > 0)
            window.pdf_panel.fit_width()
            if kind == "block":
                # This fixture has one short, thin-font line. Exercise the real
                # zoom controls before measuring ink; do not lower the visibility
                # assertion just because its fit-width raster has few dark pixels.
                for _ in range(3):
                    QTest.mouseClick(window.pdf_panel.zoom_in_button, Qt.MouseButton.LeftButton)
            try:
                wait_for(lambda: visible_pdf_ink(window) > 30, seconds=15)
            except RuntimeError:
                window.grab().save(str(output / f"{kind}-pdf-wait-failed.png"))
                print(f"{kind}: visible dark pixels={visible_pdf_ink(window)}", flush=True)
                raise
            wait_for(lambda: "FINAL" in window.workspace.details.full_text
                     and "正在编译" not in window.workspace.details.full_text)
            assert window.grab().save(str(output / f"{kind}-reopened-final.png"))
            pdf = window.pdf_state.record_for(root).last_successful_pdf
            text = window.pdf_panel._document.getAllText(0).text()
            assert ("Synthetic analysis" if kind == "block" else "Synthetic sample") in text, text
            evidence["workflows"].append({"kind": kind, "files": len(info.files), "drafts": len(info.drafts),
                "cancel_zero_writes": True, "original_bytes_unchanged": True, "restored_bytes_exact": True,
                "actual_gui_drafts_separate": True, "final_pages": window.pdf_panel._document.pageCount(),
                "final_pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                "saved_version_not_draft_was_compiled": True})
        finally:
            close(window)
    assert app_digest() == initial_app
    evidence["limits"] = ["File-picker automation not exercised; explicit paths entered into real dialogs",
                          "Offscreen is not native IME/AX/Windows or human acceptance",
                          "Block draft JSON is independently recovered, not applied or migrated automatically",
                          "No application package, installed-app replacement, Git operation or release"]
    (output / "result.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    run(parser.parse_args().output)
