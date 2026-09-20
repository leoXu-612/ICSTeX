"""D1 real Qt panel comparison; synthetic unsaved source/Block, no compilation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.core.blocks.project_repository import load_project
from app.core.submission_check import CheckStatus
from app.gui.block_mode import _install_session, _set_block_mode
from app.gui.blocks.project_session import ProjectSession
from app.gui.theme import apply_theme
from tests.v1_fixtures import create_project
from tools.bench_pdf_pipeline import source_digest, wait_gui
from tools.probe_project_checkpoint_gui import close, window_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--redesign", action="store_true")
    args = parser.parse_args()
    os.environ["QT_QPA_PLATFORM"] = "cocoa" if args.native else "offscreen"
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    report = {"completed": False, "app_sha256": source_digest(), "backend": app.platformName(),
              "limits": "Widget captures and Qt-injected keys; not human IME/VoiceOver or release acceptance",
              "states": [], "callback_errors": [], "semantics": {}}
    previous_hook = sys.excepthook

    def error_hook(kind, value, trace):
        report["callback_errors"].append(f"{kind.__name__}: {value}")
        previous_hook(kind, value, trace)

    sys.excepthook = error_hook
    window = None

    def settle():
        for _ in range(8):
            app.processEvents()

    def active():
        if args.native:
            wait_gui(lambda: window.windowHandle().isExposed() and window.isActiveWindow(), timeout=10)
        else:
            window.activateWindow()
            settle()

    def capture(mode, label):
        settle()
        active()
        panel = window.submission_panel
        visible = {name: button.visibleRegion().contains(button.rect()) for name, button in
                   (("refresh", panel.refresh_button), ("cancel", panel.cancel_button), ("next", panel.action_button))}
        selected_visible = None
        if panel.tree.isVisible() and panel.tree.currentItem() is not None:
            selected_visible = panel.tree.viewport().visibleRegion().contains(
                panel.tree.visualItemRect(panel.tree.currentItem()))
        filename = f"{mode}-{label}.png"
        assert window.grab().save(str(output / filename))
        report["states"].append({"mode": mode, "state": label, "image": filename,
            "window": [window.width(), window.height()], "panel": [panel.width(), panel.height()],
            "scale": app.ui_scale_manager.scale, "primary_visible": visible,
            "selected_row_visible": selected_visible})
        if args.redesign:
            assert all(visible.values()), (mode, label, visible)
            assert selected_visible is not False, (mode, label, "Selected row is clipped")
            assert panel.splitter.geometry().bottom() < panel.expand_button.geometry().top(), (mode, label, "Reading area overlaps actions")

    try:
        with TemporaryDirectory(prefix="icstex-d1-panel-") as temporary:
            base = Path(temporary).resolve()
            source, block = create_project(base), create_project(base, "block")
            originals = {p: p.read_bytes() for fixture in (source, block)
                         for p in fixture.root.parent.rglob("*") if p.is_file()}
            report["fixture_sha256"] = hashlib.sha256(b"".join(
                p.relative_to(base).as_posix().encode() + b"\0" + raw
                for p, raw in sorted(originals.items()))).hexdigest()
            window = window_for(output, "qa")
            window.project_files.set_project_root(source.root.parent)
            window.open_file(source.root)
            editor = window.current_tab().editor
            editor.moveCursor(QTextCursor.MoveOperation.End)
            editor.insertPlainText("\n% Synthetic unsaved check fixture.\n")
            window.documents.cancel_save_timer(window.current_tab())
            window.setWindowTitle(f"ICSTeX - SYNTHETIC SUBMISSION PANEL - {os.getpid()}")
            window.show()
            window.raise_()
            window.activateWindow()
            active()
            actions = []
            window.submission_panel.actionRequested.connect(actions.append)
            for mode in ("source", "block"):
                if mode == "block":
                    loaded = load_project(block.root.parent)
                    session = ProjectSession(**{key: loaded[key] for key in
                        ("registry", "layout", "sources", "document_theme", "project_dir")})
                    assert _install_session(window, session)
                    _set_block_mode(window, True)
                    session.selection.select_block(session.registry.blocks()[0].id, source="probe")
                    window.block_inspector.content_edit.insertPlainText("Unapplied synthetic draft. ")
                window.readiness.show()
                wait_gui(lambda: not window.readiness.is_busy and window.submission_panel.report is not None)
                panel = window.submission_panel
                checked = panel.report
                assert any(item.status is CheckStatus.FAIL for item in checked.items)
                assert any(item.status is CheckStatus.UNKNOWN for item in checked.items)
                report["semantics"][mode] = [(item.rule_id, item.status.value, item.reason, item.action)
                                             for item in checked.items]
                source_state = (editor.toPlainText(), editor.textCursor().position())
                for scale, width, height, label in ((1.0, 1440, 900, "wide"), (1.5, 1080, 720, "narrow")):
                    window.set_ui_scale(scale)
                    window.resize(width, height)
                    settle()
                    view_state = (editor.textCursor().position(), editor.verticalScrollBar().value())
                    panel.tree.setFocus()
                    active()
                    row = next(panel.tree.topLevelItem(i) for i in range(panel.tree.topLevelItemCount())
                               if checked.items[panel.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)].status is CheckStatus.UNKNOWN)
                    panel.tree.setCurrentItem(row)
                    panel.detail.setFocus()
                    QTest.keyClick(panel.detail, Qt.Key.Key_End)
                    capture(mode, label)
                    if args.redesign:
                        panel.expand_button.setFocus()
                        QTest.keyClick(panel.expand_button, Qt.Key.Key_Space)
                        capture(mode, label + "-reading")
                        panel.technical_button.setFocus()
                        QTest.keyClick(panel.technical_button, Qt.Key.Key_Space)
                        panel.technical_detail.setFocus()
                        QTest.keyClick(panel.technical_detail, Qt.Key.Key_End)
                        capture(mode, label + "-technical")
                        assert checked.input_id in panel.technical_detail.toPlainText()
                        panel.technical_button.click()
                        panel.expand_button.click()
                    assert (editor.textCursor().position(), editor.verticalScrollBar().value()) == view_state
                assert (editor.toPlainText(), editor.textCursor().position()) == source_state
                assert panel.report is checked
            assert not actions and not window.compile_authorized_roots
            assert window.block_session.compile_manager is None
            assert all(p.read_bytes() == raw for p, raw in originals.items())
            report["originals_unchanged"] = True
            report["no_actions_or_compile"] = True
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if window is not None and isValid(window):
            close(window)
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        report["window_destroyed"] = window is None or not isValid(window)
        report["app_sha256_after"] = source_digest()
        report["completed"] = (not report.get("error") and not report["callback_errors"] and report["window_destroyed"]
                               and report["app_sha256_after"] == report["app_sha256"])
        (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        sys.excepthook = previous_hook
    assert report["completed"], report
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
