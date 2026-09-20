"""C's three real Qt slices, with disposable inputs.

Offscreen is the default; --native opts into one owned Cocoa test window.
Widget captures and injected keys are not human IME or release acceptance.
--final uses actual local FINAL builds and read-only fixed review, never publishing.
Without it the delivery slice is the unreviewed preparation state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QEvent, QObject, QSettings, QTimer, Qt
from PySide6.QtGui import QInputMethodEvent, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolBar
from shiboken6 import isValid

from app.core.blocks.project_repository import load_project
from app.core.compiler import BuildPurpose
from app.core.latex_tools import LaTeXEngine
from app.core.settings import AppSettings
from app.gui.block_mode import _close_block_project, _install_session, _set_block_mode
from app.gui.blocks.project_session import ProjectSession
from app.gui.main_window import MainWindow
from app.gui.submission_delivery_dialog import SubmissionDeliveryDialog
from app.gui.formula_dialog import FormulaDialog
from app.gui.theme import apply_theme
from tests.v1_fixtures import create_project
from tools.bench_pdf_pipeline import source_digest, wait_gui
from tools.pdf_pixel_evidence import interior_ink_pixels


class WindowEvents(QObject):
    """Owned-window events; optional process-name-only focus diagnostics."""

    def __init__(self, window, report):
        super().__init__(window)
        self.window, self.report = window, report
        window.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.WindowActivate,
                            QEvent.Type.WindowDeactivate, QEvent.Type.WindowStateChange):
            if isValid(self.window):
                self.report["window_events"].append({"time": time.monotonic(),
                    "phase": self.report.get("phase"), "event": event.type().name,
                    "visible": self.window.isVisible(), "hidden": self.window.isHidden(),
                    "minimized": self.window.isMinimized(), "active": self.window.isActiveWindow()})
                if (event.type() == QEvent.Type.WindowDeactivate
                        and self.report.get("foreground_diagnostic")):
                    try:
                        result = subprocess.run(["osascript", "-e",
                            'tell application "System Events" to get name of application processes whose frontmost is true'],
                            capture_output=True, text=True, timeout=2, check=False)
                        self.report["window_events"][-1]["foreground_process"] = {
                            "exit_code": result.returncode, "name": result.stdout.strip(),
                            "error": result.stderr.strip()}
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        self.report["window_events"][-1]["foreground_read_error"] = str(exc)
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--full-matrix", action="store_true", help="Four F sizes plus formula drafts at all scale tiers")
    parser.add_argument("--block-only", action="store_true", help="Only remaining Block matrix; omit already recorded source/dialog checks")
    parser.add_argument("--observe-target-pdf", action="store_true", help="Observe the Block 100%/1440 PDF without changing its view")
    parser.add_argument("--foreground-diagnostic", action="store_true", help="On Cocoa deactivation, read foreground process names only; not for performance measurements")
    parser.add_argument("--scales", nargs="+", type=float, choices=(0.9, 1.0, 1.1, 1.25, 1.5),
                        default=(0.9, 1.0, 1.1, 1.25, 1.5))
    args = parser.parse_args()
    sizes = ((1080, 720), (1366, 768), (1440, 900), (1920, 1080)) if args.full_matrix else ((1440, 900), (1080, 720))
    output = args.output.resolve()
    backend = "cocoa" if args.native else "offscreen"
    os.environ["QT_QPA_PLATFORM"] = backend
    output.mkdir(parents=True, exist_ok=False)
    report = {"completed": False, "app_sha256": source_digest(), "qt_platform": backend,
              "evidence_boundary": "Qt widget captures and injected keys; no human IME or release acceptance",
              "actual_final_requested": args.final,
              "block_only": args.block_only,
              "foreground_diagnostic": args.native and args.foreground_diagnostic,
              "scales": args.scales,
              "requested_sizes": sizes,
              "states": [], "callback_errors": [], "window_events": [], "application_events": []}
    original_hook = sys.excepthook

    def error_hook(kind, value, traceback):
        report["callback_errors"].append(f"{kind.__name__}: {value}")
        original_hook(kind, value, traceback)

    sys.excepthook = error_hook
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    assert app.platformName() == backend
    app.applicationStateChanged.connect(lambda state: report["application_events"].append(
        {"time": time.monotonic(), "phase": report.get("phase"), "state": state.name}))
    window = dialog = None

    def settle():
        for _ in range(6):
            app.processEvents()

    def check_active(widget):
        if args.native:
            wait_gui(lambda: widget.windowHandle().isExposed() and widget.isActiveWindow(), timeout=10)
        else:
            # Offscreen has no window manager to reactivate the owner after
            # a modal closes. Establish that prerequisite before injected keys.
            widget.activateWindow()
            settle()
            assert widget.isActiveWindow()

    def capture(label, widget, scale, width, height=None):
        settle()
        check_active(widget)
        name = f"{label}-{scale:g}-{width}.png"
        assert widget.grab().save(str(output / name))
        state = {"slice": label, "scale": scale, "width": widget.width(),
                 "height": widget.height(), "screenshot": name}
        if height is not None:
            state["requested_size"] = [width, height]
            state["fits_requested_size"] = widget.width() <= width and widget.height() <= height
        if label == "source":
            editor = window.current_tab().editor
            state.update(editor_height=editor.height(), viewport_height=editor.viewport().height(),
                         console_collapsed=window.bottom_tabs.isHidden(),
                         compact=window.source_preview_area._compact)
            if scale == 1.0 and width == 1440:
                assert state["viewport_height"] >= 600, state
        elif label == "block":
            state.update(workspace_width=window.block_workspace.width(),
                         workspace_height=window.block_workspace.height(),
                         auxiliary_panels=[key for key, dock in window.block_panels.docks.items()
                                           if dock.isVisible()])
            if window.block_panels._compact:
                assert len(state["auxiliary_panels"]) <= 1, state
        report["states"].append(state)
        if height is not None:
            assert state["fits_requested_size"], state
        if label in ("source", "block"):
            action = window.compile_action if label == "source" else window.block_compile_action
            button = window.findChild(QToolBar, "mainToolbar").widgetForAction(action)
            state["compile_action_visible"] = button.visibleRegion().contains(button.rect())
            assert state["compile_action_visible"], state
        if label == "formula":
            from PySide6.QtWidgets import QDialogButtonBox
            box = dialog.findChild(QDialogButtonBox)
            state["actions_visible"] = [box.button(kind).visibleRegion().contains(box.button(kind).rect())
                for kind in (QDialogButtonBox.StandardButton.Ok, QDialogButtonBox.StandardButton.Cancel)]
            assert all(state["actions_visible"]), state
        if args.observe_target_pdf and label == "block" and scale == 1.0 and width == 1440:
            panel = window.pdf_panel
            view = panel._view
            samples = []
            started = time.perf_counter()
            for index, delay in enumerate((0, 100, 300, 600)):
                if delay:
                    QTest.qWait(delay)
                pixels = view.viewport().grab().toImage()
                ink = interior_ink_pixels(pixels)
                filename = f"block-1-1440-pdf-observation-{index}.png"
                assert window.grab().save(str(output / filename))
                samples.append({"elapsed_ms": (time.perf_counter() - started) * 1000,
                    "interior_ink_pixels": ink, "zoom": view.zoomFactor(),
                    "scroll": [view.horizontalScrollBar().value(), view.verticalScrollBar().value()],
                    "viewport": [view.viewport().width(), view.viewport().height()],
                    "page": panel.current_page(), "image": filename})
            report["target_pdf_observation"] = {"samples": samples,
                "document_text": panel._document.getAllText(0).text(),
                "limits": "All interior RGB pixels below200, outer20px excluded; white single-page fixture only, not compositor/native acceptance"}
            assert "Synthetic analysis." in report["target_pdf_observation"]["document_text"]
            assert any(sample["interior_ink_pixels"] > 0 for sample in samples), "No fixture ink observed"
            assert samples[-1]["viewport"] == samples[-2]["viewport"], "Target viewport did not settle"

    try:
        with TemporaryDirectory(prefix="icstex-c-layout-") as temporary:
            base = Path(temporary).resolve()
            source = create_project(base)
            block = create_project(base, "block")
            originals = {p: p.read_bytes() for fixture in (source, block)
                         for p in fixture.root.parent.rglob("*") if p.is_file()}
            settings = AppSettings(QSettings(str(base / "ui.ini"), QSettings.Format.IniFormat))
            window = MainWindow(settings_store=settings)
            events = WindowEvents(window, report)
            window.setWindowTitle(f"ICSTeX - SYNTHETIC WORKBENCH LAYOUT - {os.getpid()}")
            window.auto_compile_action.setChecked(False)
            window.save_debounce_ms = 3600000
            report["phase"] = "welcome"
            window.show()
            if args.native:
                window.raise_()
                window.activateWindow()
            capture("welcome", window, 1.0, 1440)
            assert not window.pdf_panel_wrapper.isVisible()
            assert not window.bottom_panel.isVisible()
            report["phase"] = "open source"
            window.project_files.set_project_root(source.root.parent)
            window.open_file(source.root)
            wait_gui(lambda: not window.dependencies.is_busy)
            editor = window.current_tab().editor
            before = editor.toPlainText()
            editor.moveCursor(QTextCursor.MoveOperation.End)
            editor.setFocus()
            if not args.block_only:
                report["phase"] = "source keyboard"
                check_active(window)
                QTest.keyClick(editor, Qt.Key.Key_X)
                QTest.keyClick(editor, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
                assert editor.toPlainText() == before
                if args.final:
                    report["phase"] = "source FINAL"
                    results = []
                    window.signals.finished.connect(results.append)
                    window.compile.set_engine(LaTeXEngine.XELATEX, compile_after=False)
                    window.compile_action.trigger()
                    wait_gui(lambda: bool(results))
                    result = results[-1]
                    assert result.ok and result.purpose is BuildPurpose.FINAL and result.root_file == source.root, result
                    wait_gui(lambda: window.pdf_panel._document.pageCount() > 0)
                    assert window.pdf_panel.current_pdf == result.pdf_file
                    report["source_final"] = {"pages": window.pdf_panel._document.pageCount(),
                        "pdf_sha256": hashlib.sha256(result.pdf_file.read_bytes()).hexdigest(),
                        "build_id": result.build_id, "indicator": window.compile_time_label.text()}
                report["phase"] = "source layout"
                for scale in args.scales:
                    window.set_ui_scale(scale)
                    for width, height in sizes:
                        window.resize(width, height)
                        capture("source", window, scale, width, height)
                window.resize(1080, 720)
                window.workspace.details.show()
                capture("source-status", window, args.scales[-1], 1080)
                assert window.workspace.details.toPlainText() == window.workspace.details.full_text
                window.workspace.details.hide()
                report["source_undo_kept_original"] = True
                report["compile_button_height_100"] = None
                window.set_ui_scale(1.0)
                settle()
                toolbar = window.findChild(QToolBar, "mainToolbar")
                report["compile_button_height_100"] = toolbar.widgetForAction(window.compile_action).height()
                dialog = SubmissionDeliveryDialog(window)
                report["phase"] = "delivery"
                dialog.show()
                if args.final:
                    dialog.inspect()
                    wait_gui(lambda: not dialog.busy)
                    assert dialog.prepared is not None, dialog.status.text()
                    fixed_pdf = next(payload for name, payload in dialog.payloads if name.endswith(".pdf"))
                    assert hashlib.sha256(fixed_pdf).hexdigest() == report["source_final"]["pdf_sha256"]
                    report["fixed_review"] = {"input_id": dialog.report.input_id,
                                               "pdf_sha256": hashlib.sha256(fixed_pdf).hexdigest()}
                for scale in args.scales:
                    window.set_ui_scale(scale)
                    for width, height in sizes if args.full_matrix else ((900, 640),):
                        dialog.resize(width, height)
                        for position in (0, dialog.scroller.verticalScrollBar().maximum()):
                            dialog.scroller.verticalScrollBar().setValue(position)
                            settle()
                            for button in (dialog.continue_button if args.final else dialog.review_button, dialog.close_button):
                                assert button.visibleRegion().contains(button.rect()), (scale, button.text())
                        capture("delivery-review" if args.final else "delivery-prepare", dialog, scale, width, height)
                    assert (dialog.prepared is not None) == args.final
                    assert dialog.result is None and not dialog.busy
                check_active(dialog)
                if args.final:
                    frozen = dialog.prepared
                    dialog.acknowledge.setChecked(True)
                    dialog.continue_button.click()
                    assert dialog.pages.currentWidget() is dialog.target_page
                    first, second = dialog.target, dialog.target_button
                else:
                    first, second = dialog.pdf_name, dialog.include_source
                first.setFocus()
                QTest.keyClick(first, Qt.Key.Key_Tab)
                assert app.focusWidget() is second
                QTest.keyClick(second, Qt.Key.Key_Backtab)
                assert app.focusWidget() is first
                if args.final:
                    assert dialog.prepared is frozen
                report["delivery_keyboard_preserved_review"] = True
                dialog.reject()
                dialog.deleteLater()
                settle()
                dialog = None
                if args.full_matrix:
                    report["phase"] = "formula dimensions"
                    dialog = FormulaDialog(window, "$x+1$", 0, 5)
                    dialog.visual_edit.insert_text("y")
                    draft = dialog.visual_edit.latex()
                    formula_errors = []
                    def inspect_formula():
                        try:
                            for scale in args.scales:
                                window.set_ui_scale(scale)
                                for width, height in sizes:
                                    dialog.resize(width, height)
                                    capture("formula", dialog, scale, width, height)
                                    assert dialog.visual_edit.latex() == draft and dialog._accepted_plan is None
                            dialog.visual_edit.undo()
                            assert dialog.visual_edit.latex() == "x+1"
                            report["formula_draft_undo_preserved"] = True
                        except BaseException as exc:
                            formula_errors.append(exc)
                        finally:
                            dialog.reject()
                    # Match InsertionActions' modal lifecycle; modeless show()
                    # does not restore the Cocoa owner on close.
                    QTimer.singleShot(0, dialog, inspect_formula)
                    dialog.exec()
                    if formula_errors:
                        raise formula_errors[0]
                    dialog.deleteLater()
                    settle()
                    dialog = None
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            loaded = load_project(block.root.parent)
            session = ProjectSession(**{key: loaded[key] for key in
                ("registry", "layout", "sources", "document_theme", "project_dir")})
            assert _install_session(window, session)
            _set_block_mode(window, True)
            window.block_workspace.tabs.tabBar().setFocus()
            report["phase"] = "Block"
            if args.final:
                window.block_compile_action.trigger()
                wait_gui(lambda: session.last_result is not None and not session.final_is_running)
                assert session.last_result.ok, session.last_result
                assert session.last_result.purpose is BuildPurpose.FINAL
                wait_gui(lambda: window.pdf_panel._document.pageCount() > 0)
                assert window.pdf_panel.current_pdf == session.last_result.pdf_file
                report["block_final"] = {"pages": window.pdf_panel._document.pageCount(),
                    "pdf_sha256": hashlib.sha256(session.last_result.pdf_file.read_bytes()).hexdigest(),
                    "indicator": window.compile_time_label.text()}
                assert "Block" in window.compile_time_label.text()
                assert f"{session.last_result.duration_seconds:.2f}s" in window.compile_time_label.text()
                assert window.status_auto_label.isHidden()
            for scale in args.scales:
                window.set_ui_scale(scale)
                for width, height in sizes:
                    window.resize(width, height)
                    capture("block", window, scale, width, height)
            # Explicit text editing uses the same inspector document. Resize
            # during synthetic composition, then undo without applying/saving.
            report["phase"] = "Block keyboard"
            check_active(window)
            window.block_nav.block_edit_requested.emit(session.registry.blocks()[0].id)
            editor = window.block_inspector.content_edit
            block_text = editor.toPlainText()
            editor.moveCursor(QTextCursor.MoveOperation.End)
            QTest.keyClick(editor, Qt.Key.Key_X)
            QApplication.sendEvent(editor, QInputMethodEvent("zhong", []))
            window.resize(1100, 740)
            settle()
            assert app.focusWidget() is editor and editor.isVisible()
            window.block_diagnostics.error_seen.emit()
            settle()
            assert app.focusWidget() is editor and editor.isVisible()
            QApplication.sendEvent(editor, QInputMethodEvent("", []))
            QTest.keyClick(editor, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
            assert editor.toPlainText() == block_text and not session.editor_drafts
            report["block_draft_focus_undo_preserved"] = True
            capture("block-edit", window, args.scales[-1], 1100)
            if args.final and not args.block_only:
                _set_block_mode(window, False)
                assert window.compile_time_label.text() == report["source_final"]["indicator"]
                assert not window.status_auto_label.isHidden()
                report["source_indicator_restored"] = True
            assert all(path.read_bytes() == data for path, data in originals.items())
            if not args.final:
                assert not window.compile_authorized_roots
                assert session.last_result is None
            report["original_files_unchanged"] = True
            report["no_delivery"] = True
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        focus = app.focusWidget()
        report["failure_context"] = {"focus_type": type(focus).__name__ if focus else None,
            "focus_name": focus.objectName() if focus else None,
            "window_active": window.isActiveWindow() if window and isValid(window) else None,
            "application_state": app.applicationState().name,
            "window_visible": window.isVisible() if window and isValid(window) else None,
            "window_hidden": window.isHidden() if window and isValid(window) else None,
            "window_minimized": window.isMinimized() if window and isValid(window) else None,
            "window_exposed": window.windowHandle().isExposed()
                if window and isValid(window) and window.windowHandle() else None}
        raise
    finally:
        if dialog is not None and isValid(dialog):
            dialog.reject()
            dialog.deleteLater()
        if window is not None and isValid(window):
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            _close_block_project(window, discard=True)
            window.close()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        report["window_destroyed"] = window is None or not isValid(window)
        report["app_sha256_after"] = source_digest()
        report["completed"] = (not report.get("error") and not report["callback_errors"]
            and report["window_destroyed"] and report["app_sha256_after"] == report["app_sha256"])
        (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        sys.excepthook = original_hook
    assert report["completed"], report
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
