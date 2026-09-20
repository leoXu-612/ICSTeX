"""Synthetic File menu -> migration review -> separate open -> visible FINAL.

Defaults to offscreen. Native windows require both --native and cocoa explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer, Qt, qVersion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.blocks.migration import legacy_fixture
from app.core.blocks.model import content_for_text
from app.core.blocks.project_repository import load_project
from app.core.project_migration import read_migration_copy
from app.gui.project_migration_dialog import ProjectMigrationDialog
from app.gui.theme import apply_theme
from tests.v1_fixtures import _png, create_project
from tools.probe_history_restore import app_digest
from tools.probe_project_checkpoint_gui import close, window_for
from tools.probe_recovered_drafts import compile_and_check, install_block


def drive(window, project, target, output, kind, *, cancel=False, observe_ms=0):
    timer = QTimer()
    timer.setInterval(25)
    state = {"phase": "start", "dialog": None, "result": None, "confirmations": [], "observed": set()}
    errors = []
    start = time.monotonic()
    prefix = kind + ("-cancel" if cancel else "")

    def observing(label):
        if label not in state["observed"]:
            state["observed"].add(label)
            state["observe_until"] = time.monotonic() + observe_ms / 1000
            print(f"OBSERVE {prefix} {label}", flush=True)
        return time.monotonic() < state["observe_until"]

    def click(button):
        # QTest sends events only to this probe's widget, never physical input.
        if state["dialog"] is not None:
            if state["dialog"].scroller.isAncestorOf(button):
                state["dialog"].scroller.ensureWidgetVisible(button)
        QTimer.singleShot(0, lambda: QTest.mouseClick(button, Qt.MouseButton.LeftButton))

    def step():
        modal = QApplication.activeModalWidget()
        try:
            assert time.monotonic() - start < 60, "Migration UI timed out"
            if isinstance(modal, QMessageBox):
                phase = state["phase"]
                assert phase in {"publish", "open-cancel", "open"}, (phase, modal.text())
                assert modal.defaultButton() == modal.button(QMessageBox.StandardButton.No)
                if observing(phase + "-confirmation"):
                    return
                state["confirmations"].append(phase)
                assert modal.grab().save(str(output / f"{prefix}-{phase}-confirmation.png"))
                answer = QMessageBox.StandardButton.No if cancel or phase == "open-cancel" else QMessageBox.StandardButton.Yes
                QTest.mouseClick(modal.button(answer), Qt.MouseButton.LeftButton)
                return
            if not isinstance(modal, ProjectMigrationDialog) or modal.busy:
                return
            state["dialog"] = modal
            phase = state["phase"]
            if phase == "start":
                state["phase"] = "inventory"
                modal.load_project(project)
            elif phase == "inventory":
                assert modal.files.topLevelItemCount() > 0, modal.status.text()
                assert modal.selected()
                assert modal.grab().save(str(output / f"{prefix}-selection.png"))
                state["phase"] = "inspect"
                click(modal.review_button)
            elif phase == "inspect":
                assert modal.review is not None, modal.status.text()
                item = next(modal.output.topLevelItem(i) for i in range(modal.output.topLevelItemCount())
                            if modal.output.topLevelItem(i).text(0) == "main.tex")
                modal.output.setCurrentItem(item)
                assert "SHA-256" in modal.preview.toPlainText()
                if kind == "legacy":
                    assert "Manual original source" in modal.preview.toPlainText()
                    assert "documentclass" in modal.preview.toPlainText()
                    assert "customMetadata" in modal.review.unmapped_keys
                modal.target.setText(str(target))
                assert modal.grab().save(str(output / f"{prefix}-review.png"))
                note = next(modal.output.topLevelItem(i) for i in range(modal.output.topLevelItemCount())
                            if modal.output.topLevelItem(i).text(0) == "encoding-note.tex")
                modal.output.setCurrentItem(note)
                assert dict(modal.review.original)["encoding-note.tex"].hex(" ") in modal.preview.toPlainText()
                assert modal.grab().save(str(output / f"{prefix}-non-utf8-review.png"))
                modal.output.setCurrentItem(item)
                state["phase"] = "review-visible"
            elif phase == "review-visible":
                if not observing("review"):
                    state["phase"] = "publish"
                    click(modal.action_button)
            elif phase == "publish" and "publish" in state["confirmations"]:
                if cancel:
                    assert modal.result is None and not target.exists()
                    click(modal.close_button)
                    state["phase"] = "cancelled"
                    return
                assert modal.result is not None, modal.status.text()
                state["result"] = modal.result
                assert modal.opened is None and not window.compile_authorized_roots
                assert modal.grab().save(str(output / f"{prefix}-published.png"))
                state["phase"] = "open-cancel"
                click(modal.open_button)
            elif phase == "open-cancel" and "open-cancel" in state["confirmations"]:
                assert modal.opened is None and target.is_dir()
                assert modal.grab().save(str(output / f"{prefix}-opening-cancelled.png"))
                state["phase"] = "open"
                click(modal.open_button)
            elif phase == "open" and "open" in state["confirmations"]:
                # Successful opening closes the dialog itself. A still-open,
                # idle dialog after its check means the real workflow failed.
                assert modal.opened is not None, modal.status.text()
        except Exception as exc:
            errors.append(repr(exc))
            if modal is not None:
                modal.reject()

    timer.timeout.connect(step)
    timer.start()
    window.migrate_project_action.trigger()
    timer.stop()
    assert not errors, (state["phase"], errors)
    assert state["confirmations"] == (["publish"] if cancel else ["publish", "open-cancel", "open"])
    new = state["dialog"].opened
    assert (new is None) == cancel
    return state["result"], new


def make_legacy(output):
    project = output / "legacy project"
    (project / ".icstex").mkdir(parents=True)
    (project / "figures").mkdir()
    data = legacy_fixture()
    data["legacySideBySideFigures"][0].update(leftCaption="Left synthetic image", rightCaption="Right synthetic image")
    data["customMetadata"] = {"zero": 0, "flag": False}
    data["legacyLatexSnippets"][0]["latex"] = "% retained verbatim\r\n\\unknown{not compiled}\t"
    (project / ".icstex/blocks.json").write_bytes(json.dumps(data, indent=1).replace("\n", "\r\n").encode())
    for name in ("a.png", "b.png"):
        (project / "figures" / name).write_bytes(_png())
    (project / "main.tex").write_bytes(b"% Manual original source\r\n\\unknown{keep}\r\n")
    return project


def run(output, kinds=("multi", "block", "legacy"), *, native=False, observe_ms=0):
    expected_platform = "cocoa" if native else "offscreen"
    if os.environ.get("QT_QPA_PLATFORM") != expected_platform:
        raise SystemExit(f"This probe requires QT_QPA_PLATFORM={expected_platform}; native windows also require --native.")
    if not 0 <= observe_ms <= 10000:
        raise ValueError("Observer pause must be between 0 and 10000 milliseconds")
    app = QApplication.instance() or QApplication([])
    assert app.platformName() == expected_platform
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    output = output.expanduser().resolve()
    output.mkdir(exist_ok=False)
    digest = app_digest()
    evidence = {"app_sha256": digest, "platform": platform.platform(), "python": sys.version,
                "qt_platform": app.platformName(), "qt_version": qVersion(), "pid": os.getpid(),
                "native_explicit": native, "observer_pause_ms": observe_ms,
                "synthetic_only": True, "workflows": []}
    for kind in kinds:
        project = make_legacy(output) if kind == "legacy" else create_project(output, kind).root.parent
        (project / "encoding-note.tex").write_bytes(b"% " + "\u539f\u59cb\u5b57\u8282".encode("gbk") + b"\r\n")
        original = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
        owner = window_for(output, kind + "-owner")
        evidence["ax_selected_children_guard"] = bool(app.property("icstex_ax_selected_children_guard"))
        new = reopened = None
        try:
            owner.project_files.set_project_root(project)
            if kind == "block":
                session = install_block(owner, project)
                # The capture lease intentionally restores pre-existing timers
                # on close. Keep this synthetic owner's autosave deferred, just
                # as window_for does for source tabs, during copy FINAL checks.
                session._save_timer.setInterval(3600000)
                block = session.registry.blocks()[0]
                session.registry.update(block.id, {"content": content_for_text("Independent original model draft")})
                session.notify_model_changed("synthetic-migration-probe")
            else:
                owner.open_file(project / "main.tex")
                owner.current_tab().editor.appendPlainText("% Independent original source draft")
            owner.show()
            if kind == "multi":
                drive(owner, project, output / "cancelled", output, kind, cancel=True, observe_ms=observe_ms)
            result, new = drive(owner, project, output / (kind + "-copy"), output, kind, observe_ms=observe_ms)
            assert all((project / p).read_bytes() == raw for p, raw in original.items())
            copy = read_migration_copy(result.directory)
            assert any(b"Independent original" in raw for _, raw in copy.copy.drafts)
            if kind == "legacy":
                assert copy.copy.info.drafts[0].target is None
                assert all((result.directory / "recovery-evidence/original" / p).read_bytes() == raw
                           for p, raw in original.items())
                raw_block = next(b for b in load_project(result.project_dir)["registry"].blocks() if b.type == "rawLatex")
                assert raw_block.content["trusted"] is False
                assert raw_block.content["latex"] == "% retained verbatim\r\n\\unknown{not compiled}\t"
            assert not new.compile_authorized_roots
            if new.block_session:
                assert not new.block_session._compile_authorized and not new.block_session.has_unsaved_changes
            else:
                assert "Independent original" not in new.current_tab().editor.toPlainText()
            new.resize(1280, 850)
            QTest.qWait(500)
            assert new.grab().save(str(output / f"{kind}-opened.png"))
            expected = {"multi": "Synthetic sample", "block": "Synthetic analysis.", "legacy": "Left synthetic image"}[kind]
            mode = "multi" if kind == "multi" else "block"
            pdf_hash = compile_and_check(new, mode, expected, scan_page=True)
            QTest.qWait(250)
            assert new.grab().save(str(output / f"{kind}-final.png"))
            print(f"OBSERVE {kind} opened FINAL", flush=True)
            QTest.qWait(observe_ms)
            if kind == "legacy":
                text = " ".join(new.pdf_panel._document.getAllText(i).text() for i in range(new.pdf_panel._document.pageCount()))
                assert "Right synthetic image" in text and "not compiled" not in text
            close(new)
            new = None
            reopened = window_for(output, kind + "-reopened")
            reopened.project_files.set_project_root(result.project_dir)
            if mode == "block":
                install_block(reopened, result.project_dir)
            else:
                reopened.open_file(result.project_dir / "main.tex")
            reopened.resize(1280, 850)
            reopened.show()
            reopened_hash = compile_and_check(reopened, mode, expected, scan_page=True)
            QTest.qWait(250)
            assert reopened.grab().save(str(output / f"{kind}-reopened-final.png"))
            print(f"OBSERVE {kind} reopened FINAL", flush=True)
            QTest.qWait(observe_ms)
            assert all((project / p).read_bytes() == raw for p, raw in original.items())
            assert all((result.project_dir / p).read_bytes() == raw for p, raw in copy.copy.files)
            assert owner.block_session.has_unsaved_changes if kind == "block" else owner.current_tab().modified
            evidence["workflows"].append({"kind": kind, "files": len(copy.copy.files), "drafts": len(copy.copy.drafts),
                "originals_unchanged": True, "drafts_not_applied": True, "separate_open_confirmation": True,
                "actual_final_contains": expected, "opened_pdf_sha256": pdf_hash, "reopened_pdf_sha256": reopened_hash,
                "decision_sha256": hashlib.sha256((result.directory / "recovery-evidence/decision.json").read_bytes()).hexdigest()})
        except BaseException:
            if new is not None:
                new.grab().save(str(output / f"{kind}-failure.png"))
                view = new.pdf_panel._view
                bar = view.verticalScrollBar()
                print(json.dumps({"kind": kind, "failure_scroll": [bar.minimum(), bar.value(), bar.maximum(), bar.pageStep()],
                    "viewport": [view.viewport().width(), view.viewport().height()],
                    "zoom": view.zoomFactor()}), flush=True)
            raise
        finally:
            for window in (new, reopened, owner):
                if window is not None:
                    close(window)
    assert app_digest() == digest, "Source changed during verification"
    evidence["limits"] = [
        ("Native Cocoa windows with QTest widget events; physical keyboard, IME and pointer behavior not exercised"
         if native else "Offscreen rendering and QTest widget events only; no native GUI, desktop focus or physical input"),
        "Synthetic paths supplied to actual dialogs; native directory pickers not exercised",
        "Selected-file copy, not proof of complete dependencies or cloud download state",
        "No Windows, full native IME/AX, power-loss, human usability or release acceptance"]
    (output / "result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=("multi", "block", "legacy"), action="append")
    parser.add_argument("--native", action="store_true", help="Explicitly allow Cocoa windows after user authorization")
    parser.add_argument("--observe-ms", type=int, default=0, choices=range(0, 10001), metavar="0..10000")
    args = parser.parse_args()
    run(args.output, args.kind or ("multi", "block", "legacy"), native=args.native, observe_ms=args.observe_ms)
