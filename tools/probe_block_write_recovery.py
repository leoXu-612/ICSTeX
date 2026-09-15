"""Real synthetic interrupted-writer -> review -> new copy -> Block FINAL."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.blocks.project_repository import load_project
from app.core.blocks.project_write import PENDING_PATH
from app.core.project_recovery import read_recovery_copy
from app.gui.block_write_recovery_dialog import BlockWriteRecoveryDialog
from app.gui.theme import apply_theme
from tests.v1_fixtures import create_project
from tools.probe_history_restore import app_digest
from tools.probe_project_checkpoint_gui import close, window_for
from tools.probe_recovered_drafts import compile_and_check, install_block


def drive(window, project, target, side, output, *, cancel=False, observe_ms=0):
    timer = QTimer()
    timer.setInterval(25)
    state = {"phase": "start", "dialog": None, "confirmed": False, "confirm_at": None}
    errors = []
    start = time.monotonic()
    prefix = side + ("-cancel" if cancel else "")
    def step():
        modal = QApplication.activeModalWidget()
        try:
            assert time.monotonic() - start < 60, "Journal recovery UI timed out"
            if isinstance(modal, QMessageBox):
                if state["confirm_at"] is None:
                    state["confirm_at"] = time.monotonic() + observe_ms / 1000
                    print(f"OBSERVE {prefix} confirmation", flush=True)
                if time.monotonic() < state["confirm_at"]:
                    return
                state["confirmed"] = True
                modal.grab().save(str(output / f"{prefix}-confirmation.png"))
                QTest.mouseClick(modal.button(QMessageBox.StandardButton.No if cancel else QMessageBox.StandardButton.Yes),
                                 Qt.MouseButton.LeftButton)
                return
            if not isinstance(modal, BlockWriteRecoveryDialog) or modal.busy:
                return
            state["dialog"] = modal
            if state["phase"] == "start":
                state["phase"] = "loaded"
                modal.load_project(project)
            elif state["phase"] == "loaded":
                assert modal.review is not None, modal.status.text()
                for combo in modal.choices.values():
                    combo.setFocus()
                    QTest.keyClick(combo, Qt.Key.Key_Home)
                    for _ in range(1 if side == "before" else 2):
                        QTest.keyClick(combo, Qt.Key.Key_Down)
                    assert combo.currentData() == side
                item = next(modal.tree.topLevelItem(i) for i in range(modal.tree.topLevelItemCount())
                            if modal.tree.topLevelItem(i).text(1) == "外部版本 / 冲突")
                modal.tree.setCurrentItem(item)
                modal.target.setText(str(target))
                assert "External manual winner." in modal.preview.toPlainText()
                assert modal.grab().save(str(output / f"{prefix}-review.png"))
                state["phase"] = "reviewing"
                state["review_until"] = time.monotonic() + observe_ms / 1000
                print(f"OBSERVE {prefix} review", flush=True)
            elif state["phase"] == "reviewing" and time.monotonic() >= state["review_until"]:
                state["phase"] = "sent"
                QTimer.singleShot(0, lambda: QTest.mouseClick(modal.action_button, Qt.MouseButton.LeftButton))
            elif state["phase"] == "sent" and state["confirmed"]:
                if cancel:
                    assert modal.result is None and not target.exists()
                else:
                    assert modal.result is not None, modal.status.text()
                    assert modal.grab().save(str(output / f"{prefix}-published.png"))
                QTest.mouseClick(modal.close_button, Qt.MouseButton.LeftButton)
        except Exception as exc:
            errors.append(str(exc))
            if modal is not None:
                modal.reject()
    timer.timeout.connect(step)
    timer.start()
    window.write_recovery_action.trigger()
    timer.stop()
    assert not errors and state["confirmed"], (state["phase"], errors)
    return state["dialog"].result


def run(output, observe_ms=0):
    output = output.expanduser().resolve()
    output.mkdir(parents=False, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    digest = app_digest()
    fixture = create_project(output, "block")
    project = fixture.root.parent
    code = "from pathlib import Path; from tests.test_block_write_recovery import interrupted_write; import sys; interrupted_write(Path(sys.argv[1]), terminate=True)"
    process = subprocess.run([sys.executable, "-c", code, str(project)], capture_output=True, timeout=20)
    assert process.returncode == 73, process.stderr.decode()
    fixture.draft_path.write_bytes(b"External manual winner.\r\n")
    original = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    window = window_for(output, "journal-owner")
    window.project_files.set_project_root(project)
    window.open_file(fixture.root)
    window.current_tab().editor.appendPlainText("% Independent unsaved owner draft")
    window.show()
    evidence = {"app_sha256": digest, "platform": platform.platform(), "qt_platform": app.platformName(),
                "ax_selected_children_guard": bool(app.property("icstex_ax_selected_children_guard")),
                "observer_pause_ms": observe_ms,
                "synthetic_only": True, "real_writer_exit": process.returncode, "results": []}
    try:
        drive(window, project, output / "cancelled", "after", output, cancel=True, observe_ms=observe_ms)
        for side in ("before", "after"):
            result = drive(window, project, output / f"{side}-recovered", side, output, observe_ms=observe_ms)
            copy = read_recovery_copy(result.directory)
            assert any(b"Independent unsaved owner draft" in payload for _, payload in copy.drafts)
            expected = "Synthetic analysis." if side == "before" else "Recovered interrupted Block write."
            assert load_project(result.project_dir)["registry"].blocks()[0].content["text"] == expected
            assert not (result.project_dir / PENDING_PATH).exists()
            pdf_hashes = []
            for attempt in ("opened", "reopened"):
                new = window_for(output, f"{side}-{attempt}")
                try:
                    new.resize(1280, 850)
                    new.project_files.set_project_root(result.project_dir)
                    session = install_block(new, result.project_dir)
                    assert not session.has_unsaved_changes and not session._compile_authorized
                    new.show()
                    pdf_hashes.append(compile_and_check(new, "block", expected))
                    QTest.qWait(250)
                    assert new.grab().save(str(output / f"{side}-{attempt}-final.png"))
                    print(f"OBSERVE {side} {attempt} FINAL", flush=True)
                    QTest.qWait(observe_ms)
                finally:
                    close(new)
            assert all((project / path).read_bytes() == payload for path, payload in original.items())
            report_path = result.directory / "recovery-evidence/decision.json"
            evidence["results"].append({"side": side, "drafts_separate": True,
                "original_project_and_journal_unchanged": True, "final_contains": expected,
                "opened_pdf_sha256": pdf_hashes[0], "reopened_pdf_sha256": pdf_hashes[1],
                "decision_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest()})
    finally:
        close(window)
    assert app_digest() == digest
    evidence["limits"] = ["Project/target paths supplied to actual dialogs; native pickers not automated",
        "Journal changed files plus selected current files, not a complete historical snapshot",
        "No power-loss, Windows, IME, AX or human acceptance implied",
        "No original journal cleanup, package, installed-app replacement, Git operation or release"]
    (output / "result.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observe-ms", type=int, default=0, choices=range(0, 10001), metavar="0..10000")
    args = parser.parse_args()
    run(args.output, args.observe_ms)
