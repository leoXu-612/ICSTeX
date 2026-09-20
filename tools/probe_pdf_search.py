"""Real local FINAL and synthetic Cocoa PDF-search/scale/focus checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtGui import QInputMethodEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid
from app.core.compiler import BuildPurpose
from app.core.latex_tools import LaTeXEngine
from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.bench_pdf_pipeline import source_digest, wait_gui


def run(output, native, scales=(.9, 1., 1.1, 1.25, 1.5)):
    backend = "cocoa" if native else "offscreen"
    if os.environ.get("QT_QPA_PLATFORM") != backend:
        raise ValueError(f"Requires QT_QPA_PLATFORM={backend}")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = output / "main.tex"
    source = ("\\documentclass{ctexart}\n\\begin{document}\n" +
              "\\newpage\n".join(f"Synthetic PDF search page {page}. \\par\n\u4e2d\u6587\u641c\u7d22 {page}.\n" for page in (1, 2, 3)) +
              "\\end{document}\n")
    root.write_text(source, encoding="utf-8")
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    report = {"app_sha256": source_digest(), "backend": backend, "pid": os.getpid(),
              "completed": False, "states": [], "limits": "Synthetic Qt key and IME events, not human IME or OS-menu/VoiceOver acceptance"}
    report["callback_errors"] = []
    previous_hook = sys.excepthook

    def callback_error(kind, value, trace):
        report["callback_errors"].append(f"{kind.__name__}: {value}")
        previous_hook(kind, value, trace)

    sys.excepthook = callback_error
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / "qa.ini"), QSettings.Format.IniFormat)))
    try:
        window.auto_compile_action.setChecked(False)
        window.save_debounce_ms = 3_600_000
        window.open_file(root)
        window.compile.set_engine(LaTeXEngine.XELATEX, compile_after=False)
        window.resize(1440, 900)
        window.setWindowTitle(f"ICSTeX - SYNTHETIC PDF SEARCH - {os.getpid()}")
        window.show()
        window.raise_()
        window.activateWindow()
        if native:
            wait_gui(lambda: window.windowHandle().isExposed() and window.isActiveWindow(), timeout=10)
        window.compile_current(immediate=True, purpose=BuildPurpose.FINAL)
        panel = window.pdf_panel
        wait_gui(lambda: window.compile.final_evidence_for(root) is not None and panel._document.pageCount() == 3, timeout=60)
        wait_gui(lambda: not window.dependencies.is_busy)
        pdf = panel.current_pdf
        original_pdf = pdf.read_bytes()
        editor = window.current_tab().editor
        cursor = editor.textCursor().position()
        for scale in scales:
            window.set_ui_scale(scale)
            for width, height in ((1440, 900), (1080, 720)):
                window.resize(width, height)
                QApplication.processEvents()
                window.activateWindow()
                editor.setFocus()
                wait_gui(lambda: window.isActiveWindow() and editor.hasFocus(), timeout=5)
                search_started = time.perf_counter()
                QTest.keyClick(editor, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
                wait_gui(lambda: panel.pdf_search_edit.hasFocus(), timeout=5)
                # Focus changes synchronously, but Cocoa splitter geometry is
                # delivered on the next event turn. Measure that transition.
                wait_gui(lambda: panel.pdf_search_button.visibleRegion().contains(panel.pdf_search_button.rect())
                         and panel.pdf_search_edit.visibleRegion().contains(panel.pdf_search_edit.rect()), timeout=2)
                search_layout_ms = (time.perf_counter() - search_started) * 1000
                QApplication.sendEvent(panel.pdf_search_edit, QInputMethodEvent("zhong", []))
                before = panel._search_index
                QTest.keyClick(panel.pdf_search_edit, Qt.Key.Key_Return)
                assert panel._search_index == before and panel._search_row.isVisible()
                committed = QInputMethodEvent()
                committed.setCommitString("\u4e2d\u6587")
                QApplication.sendEvent(panel.pdf_search_edit, committed)
                wait_gui(lambda: panel._search_model.count() == 3)
                QTest.keyClick(panel.pdf_search_edit, Qt.Key.Key_Return)
                assert panel._search_index >= 0
                QTest.keyClick(panel.pdf_search_edit, Qt.Key.Key_Tab)
                assert QApplication.focusWidget() is panel.pdf_search_prev_button
                QTest.keyClick(panel.pdf_search_prev_button, Qt.Key.Key_Backtab)
                assert panel.pdf_search_edit.hasFocus()
                wait_gui(lambda: panel.pdf_search_status.fontMetrics().horizontalAdvance(panel.pdf_search_status.text()) <= panel.pdf_search_status.contentsRect().width(), timeout=2)
                for widget in (panel.pdf_search_edit, panel.pdf_search_prev_button, panel.pdf_search_next_button,
                               panel.pdf_search_close_button, panel.pdf_search_status):
                    assert widget.visibleRegion().contains(widget.rect()), widget.objectName()
                assert not panel.pdf_search_close_button.icon().isNull()
                assert panel.pdf_search_status.fontMetrics().horizontalAdvance(panel.pdf_search_status.text()) <= panel.pdf_search_status.contentsRect().width()
                name = f"search-{scale}-{width}.png"
                assert window.grab().save(str(output / name))
                QTest.keyClick(panel.pdf_search_edit, Qt.Key.Key_Escape)
                assert editor.hasFocus() and not panel._search_row.isVisible()
                assert editor.toPlainText() == source and editor.textCursor().position() == cursor
                report["states"].append({"scale": scale, "width": width, "height": height,
                    "chinese_matches": 3, "focus_returned": True, "screenshot": name,
                    "search_layout_observed_ms": search_layout_ms})
        assert root.read_text(encoding="utf-8") == source
        assert pdf.read_bytes() == original_pdf
        report.update(completed=True, original_source_pdf_unchanged=True,
                      pdf_sha256=hashlib.sha256(original_pdf).hexdigest())
    except BaseException as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        report["failure_context"] = {"active": window.isActiveWindow(),
            "exposed": window.windowHandle().isExposed() if window.windowHandle() else None,
            "application_state": QApplication.applicationState().name,
            "search_enabled": window.pdf_panel.search_action.isEnabled(),
            "search_visible": window.pdf_panel._search_row.isVisible(),
            "status_width": window.pdf_panel.pdf_search_status.contentsRect().width(),
            "status_text_width": window.pdf_panel.pdf_search_status.fontMetrics().horizontalAdvance(window.pdf_panel.pdf_search_status.text()),
            "focus_class": type(QApplication.focusWidget()).__name__,
            "source_unchanged": root.read_text(encoding="utf-8") == source}
        window.grab().save(str(output / "failure.png"))
        area = window.source_preview_area
        observations = []
        for delay in (0, 100, 500):
            if delay:
                QTest.qWait(delay)
            observations.append({"delay_ms": delay, "splitter_sizes": area.splitter.sizes(),
                "compact": area._compact, "show_pdf": area._show_pdf,
                "pdf_visible": window.pdf_panel.isVisible(), "pdf_size": [window.pdf_panel.width(), window.pdf_panel.height()],
                "button_visible": window.pdf_panel.pdf_search_button.visibleRegion().contains(window.pdf_panel.pdf_search_button.rect()),
                "search_visible": window.pdf_panel.pdf_search_edit.visibleRegion().contains(window.pdf_panel.pdf_search_edit.rect()),
                "focus_class": type(QApplication.focusWidget()).__name__,
                "active": window.isActiveWindow()})
            window.grab().save(str(output / f"failure-observe-{delay}.png"))
        report["failure_observations"] = observations
        raise
    finally:
        for tab in window.tabs.values():
            window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        window.close()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        report["closed_window_destroyed"] = not isValid(window)
        report["app_hash_matches_after_run"] = source_digest() == report["app_sha256"]
        report["completed"] = report["completed"] and not report["callback_errors"]
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        sys.excepthook = previous_hook
    assert report["completed"] and report["closed_window_destroyed"] and report["app_hash_matches_after_run"], report
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--scales", nargs="+", type=float, choices=(.9, 1., 1.1, 1.25, 1.5),
                        default=(.9, 1., 1.1, 1.25, 1.5))
    args = parser.parse_args()
    run(args.output, args.native, args.scales)
