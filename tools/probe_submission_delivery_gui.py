"""Synthetic actual GUI Save/FINAL -> frozen review -> export -> external compile.

Offscreen by default. --native plus QT_QPA_PLATFORM=cocoa permits native QA.
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
from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.blocks.project_repository import load_project
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from app.core.project_checkpoint import checkpoint_candidates, create_checkpoint, restore_checkpoint
from app.gui.blocks.project_dialog import BlockProjectDialog
from app.gui.submission_delivery_dialog import SubmissionDeliveryDialog
from app.gui.theme import apply_theme
from tests.v1_fixtures import create_project
from tools.probe_history_restore import app_digest
from tools.probe_project_checkpoint_gui import close, window_for
from tools.probe_recovered_drafts import install_block
from tools.probe_submission_delivery import final, pdf_text


def drive(owner, target, output, name, *, source=False, standalone=False, prepare_input=True):
    state = {"phase": "start", "dialog": None, "confirmed": [], "payloads": None}
    failures = []
    timer = QTimer()
    timer.setInterval(25)
    start = time.monotonic()
    journal = []
    click_depth = 0

    def record(event):
        dialog = state["dialog"]
        modal = QApplication.activeModalWidget()
        journal.append({"event": event, "elapsed_ms": round((time.monotonic() - start) * 1000, 3),
            "phase": state["phase"], "click_depth": click_depth,
            "modal": type(modal).__name__ if modal is not None else None,
            "busy": dialog.busy if dialog is not None else None,
            "operation": getattr(dialog, "operation", None),
            "prepared_input": dialog.prepared.report.input_id if dialog is not None and dialog.prepared else None,
            "cancelled": dialog.cancel.is_set() if dialog is not None else None,
            "result": str(dialog.result) if dialog is not None and dialog.result is not None else None,
            "target_exists": target.exists()})

    def click(button):
        nonlocal click_depth
        if state["dialog"].scroller.isAncestorOf(button):
            state["dialog"].scroller.ensureWidgetVisible(button)

        def dispatch():
            nonlocal click_depth
            click_depth += 1
            record("click_enter:" + button.text())
            try:
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            finally:
                record("click_return:" + button.text())
                click_depth -= 1

        QTimer.singleShot(0, button, dispatch)

    def step():
        modal = QApplication.activeModalWidget()
        try:
            assert time.monotonic() - start < 120, (name, state["phase"], "timeout")
            if isinstance(modal, QMessageBox):
                phase = state["phase"]
                assert phase in {"cancel", "publish"}, (phase, modal.text())
                assert modal.defaultButton() == modal.button(QMessageBox.StandardButton.No)
                assert modal.grab().save(str(output / f"{name}-{phase}-confirmation.png"))
                state["confirmed"].append(phase)
                record("confirmation_answer:" + phase)
                answer = QMessageBox.StandardButton.No if phase == "cancel" else QMessageBox.StandardButton.Yes
                QTest.mouseClick(modal.button(answer), Qt.MouseButton.LeftButton)
                return
            # A native question may already be hidden while its caller is
            # still returning through a nested event loop. Answer questions
            # above, but do not advance/assert the next phase until the actual
            # button handler has returned and can launch its publish worker.
            if not isinstance(modal, SubmissionDeliveryDialog) or modal.busy or click_depth:
                return
            state["dialog"] = modal
            phase = state["phase"]
            if phase == "start":
                assert not modal.include_source.isChecked() and not modal.include_report.isChecked()
                assert modal.grab().save(str(output / f"{name}-prepare.png"))
                if prepare_input:
                    state["phase"] = "saved"
                    click(modal.save_button)
                else:
                    # D2 changes delivery UI only. Reuse the real unchanged
                    # FINAL for the second options case instead of rebuilding.
                    state["before_build"] = None
                    state["phase"] = "compiling"
            elif phase == "saved":
                state["before_build"] = modal._snapshot().build_evidence
                state["phase"] = "compiling"
                click(modal.compile_button)
            elif phase == "compiling":
                session = modal.session
                proof = session.final_evidence if session else owner.compile.final_evidence_for(modal.root)
                if proof is None or proof is state["before_build"]:
                    return
                assert proof.inputs.stable and proof.inputs.pdf.digest
                state["phase"] = "settling"
                state["ready_at"] = time.monotonic() + 0.5
            elif phase == "settling" and time.monotonic() >= state["ready_at"]:
                if source:
                    modal.include_report.setChecked(True)
                    state["phase"] = "inventory"
                    modal.include_source.setChecked(True)
                else:
                    state["phase"] = "review"
                    click(modal.review_button)
            elif phase == "inventory":
                assert modal.inventory_loaded, modal.status.text()
                assert not modal.options().source_paths
                modal.select_all()
                paths = set(modal.options().source_paths)
                assert {"README.md", "manifest.json", "encoding-note.tex"}.issubset(paths), paths
                assert not any(".venv" in p or "signing.pem" in p for p in paths)
                assert modal.grab().save(str(output / f"{name}-source-selection.png"))
                state["phase"] = "review"
                click(modal.review_button)
            elif phase == "review":
                assert modal.prepared is not None, modal.status.text()
                state["payloads"] = dict(modal.payloads)
                if not source:
                    assert list(state["payloads"]) == ["main.pdf"]
                else:
                    assert state["payloads"]["source/README.md"] == b"Original user instructions.\r\n"
                    assert str(output).encode() not in state["payloads"]["submission-report.json"]
                modal.target.setText(str(target))
                modal.acknowledge.setChecked(True)
                modal.outputs.setCurrentItem(modal.outputs.topLevelItem(0))
                assert modal.grab().save(str(output / f"{name}-review.png"))
                state["phase"] = "target"
                click(modal.continue_button)
            elif phase == "target":
                assert modal.pages.currentWidget() is modal.target_page
                assert modal.grab().save(str(output / f"{name}-target.png"))
                state["phase"] = "cancel"
                click(modal.action_button)
            elif phase == "cancel" and "cancel" in state["confirmed"]:
                assert modal.result is None and not target.exists()
                state["phase"] = "publish"
                click(modal.action_button)
            elif phase == "publish" and "publish" in state["confirmed"]:
                assert modal.result == target, modal.status.text()
                assert modal.grab().save(str(output / f"{name}-published.png"))
                for path, raw in state["payloads"].items():
                    assert (target / path).read_bytes() == raw
                state["phase"] = "done"
                modal.reject()
        except Exception as exc:
            failures.append(repr(exc))
            record("failure:" + repr(exc))
            if modal is not None:
                modal.grab().save(str(output / f"{name}-failure.png"))
                modal.reject()

    timer.timeout.connect(step)
    timer.start()
    try:
        if standalone:
            owner.workspace.delivery_button.click()
        else:
            owner.prepare_submission_action.trigger()
    finally:
        timer.stop()
        (output / f"{name}-events.json").write_text(json.dumps({
            "phase": state["phase"], "failures": failures, "confirmed": state["confirmed"],
            "events": journal}, indent=2) + "\n", encoding="utf-8")
    assert not failures and state["phase"] == "done", (state["phase"], failures)
    assert state["confirmed"] == ["cancel", "publish"]
    return {"files": len(state["payloads"]), "pdf_sha256": hashlib.sha256((target / "main.pdf").read_bytes()).hexdigest()}


def run(output, *, native=False, kinds=("single", "multi", "block", "standalone"), window_size=None,
        delivery_only=False):
    backend = "cocoa" if native else "offscreen"
    if os.environ.get("QT_QPA_PLATFORM") != backend:
        raise SystemExit(f"Requires QT_QPA_PLATFORM={backend}; native also requires --native")
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    assert app.platformName() == backend
    output = output.expanduser().resolve()
    output.mkdir(exist_ok=False)
    digest, tools = app_digest(), detect_toolchain()
    evidence = {"app_sha256": digest, "platform": platform.platform(), "backend": backend,
                "pid": os.getpid(), "synthetic_only": True, "cases": []}
    for kind in kinds:
        base = output / kind
        base.mkdir()
        sample = create_project(base, "block" if kind == "standalone" else kind)
        project = sample.root.parent
        (project / "README.md").write_bytes(b"Original user instructions.\r\n")
        (project / "manifest.json").write_bytes(b'{"original":true}\r\n')
        (project / "encoding-note.tex").write_bytes(b"% \x81\xff\r\n")
        (project / "signing.pem").write_bytes(b"synthetic nonsecret excluded file")
        original = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
        owner = None
        try:
            if kind == "standalone":
                loaded = load_project(project)
                owner = BlockProjectDialog(registry=loaded["registry"], layout=loaded["layout"],
                    document_theme=loaded["document_theme"], project_dir=project)
            else:
                owner = window_for(output, kind)
                owner.project_files.set_project_root(project)
                if kind == "block":
                    install_block(owner, project)
                else:
                    owner.open_file(sample.root)
                    owner.compile.set_engine(LaTeXEngine.XELATEX, compile_after=False)
            if window_size is not None:
                owner.resize(*window_size)
            owner.setWindowTitle(f"ICSTeX - SYNTHETIC DELIVERY PROBE - {os.getpid()}")
            owner.show()
            bare = drive(owner, output / (kind + "-pdf"), output, kind + "-pdf", standalone=kind == "standalone")
            package = output / (kind + "-package")
            full = drive(owner, package, output, kind + "-package", source=True, standalone=kind == "standalone",
                         prepare_input=not delivery_only)
            expected = "Synthetic analysis." if kind in {"block", "standalone"} else "Synthetic sample"
            assert expected in pdf_text(package / "main.pdf")
            assert all((project / p).read_bytes() == raw for p, raw in original.items())
            if kind in {"block", "standalone"}:
                assert load_project(package / "source")["registry"].blocks()
            if not delivery_only:
                recompiled = final(package / "source/main.tex", tools)
                assert expected in pdf_text(recompiled.pdf_file)
                paths, _ = checkpoint_candidates(project)
                archive = output / (kind + ".icstex-checkpoint")
                create_checkpoint(project, paths, archive)
                restored = restore_checkpoint(archive, output / (kind + "-restored"))
                restored_final = final(restored.project_dir / "main.tex", tools)
                assert expected in pdf_text(restored_final.pdf_file)
            evidence["cases"].append({"kind": kind, "pdf_only": bare, "source_report": full,
                "originals_unchanged": True, "preview_equals_delivered_bytes": True,
                "exported_source_recompiled": not delivery_only, "checkpoint_restored_and_compiled": not delivery_only})
        finally:
            if owner is not None:
                if kind == "standalone":
                    owner.close()
                    owner.deleteLater()
                    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                else:
                    close(owner)
    assert app_digest() == digest
    evidence["limits"] = ["Synthetic GUI/widget events, not human/IME/AX/Windows acceptance",
        "MCP export is verified separately; build-time tool-version proof remains unfinished",
        "Unknown static checks explicitly acknowledged; no academic or complete dependency certification"]
    (output / "result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--kind", choices=("single", "multi", "block", "standalone"), action="append")
    parser.add_argument("--window-size", type=int, nargs=2, metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--delivery-only", action="store_true", help="Reuse real FINAL across options; skip unchanged restore/recompile routes")
    args = parser.parse_args()
    run(args.output, native=args.native, kinds=args.kind or ("single", "multi", "block", "standalone"),
        window_size=args.window_size, delivery_only=args.delivery_only)
