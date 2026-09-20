"""Owned writing-surface screenshots; no student files or compiler invocation."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QSettings
from PySide6.QtWidgets import QApplication, QToolBar
from shiboken6 import isValid
from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.bench_pdf_pipeline import source_digest, wait_gui
from tools.bench_auto_compile_latency import marker_pixels
from tests.test_pdf_panel import _write_zoom_pdf


def run(output, native):
    output.mkdir(parents=True, exist_ok=False)
    root = output / "writing.tex"
    text = ("% Notes for this section stay readable without competing with the main text.\n" * 8 +
            "\\documentclass{article}\n\\begin{document}\n\\section{A clear writing workspace}\n"
            "Write, revise, and check the result. Keep the editor comfortable while the first preview is prepared.\n"
            "The source remains the authority; a preview is a reading aid, not a replacement for the original.\n"
            "\\[ E = mc^2 \\]\n\\end{document}\n")
    root.write_text(text)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    settings = AppSettings(QSettings(str(output / "settings.ini"), QSettings.Format.IniFormat))
    window = MainWindow(settings_store=settings)
    window.auto_compile_action.setChecked(False)
    window.save_debounce_ms = 3600000
    window.open_file(root)
    window.setWindowTitle("ICSTeX - WRITING UI REVIEW")
    window.resize(1440, 900)
    window.show()
    if native:
        window.raise_()
        window.activateWindow()
        wait_gui(lambda: window.isActiveWindow() and window.windowHandle().isExposed(), timeout=10)
    wait_gui(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
    report = {"app_sha256": source_digest(), "backend": app.platformName(), "states": []}
    try:
        for label, scale, preview in (("empty", 1., False), ("empty-large", 1.5, False), ("preview", 1., True),
                                       ("preview-large", 1.5, True)):
            window.set_ui_scale(scale)
            if preview:
                pdf = output / "preview.pdf"
                _write_zoom_pdf(pdf)
                window.pdf_panel.load_pdf(pdf, logical_key=root)
                window.pdf_panel.set_freshness("合成 PDF · 仅用于界面检查", "neutral")
                window.source_preview_area.select_pdf(True)
                wait_gui(lambda: marker_pixels(window.pdf_panel._view.viewport().grab().toImage(),
                                                (255, 0, 0)) > 100, timeout=5)
            for _ in range(8):
                app.processEvents()
            if native:
                assert window.isActiveWindow() and window.windowHandle().isExposed()
            editor = window.current_tab().editor
            window.grab().save(str(output / (label + ".png")))
            toolbar = window.findChild(QToolBar, "mainToolbar")
            report["states"].append({"case": label, "scale": scale,
                "editor_viewport": [editor.viewport().width(), editor.viewport().height()],
                "bottom_height": window.bottom_panel.height(),
                "bottom_max_height": window.bottom_panel.maximumHeight(),
                "bottom_hint": window.bottom_panel.minimumSizeHint().height(),
                "console_hidden": window.bottom_tabs.isHidden(),
                "splitter_sizes": window.vertical_splitter.sizes(),
                "preview_width": window.pdf_panel_wrapper.width(),
                "toolbar_height": toolbar.height(), "toggle_height": window.auto_compile_toggle.height(),
                "toggle_font": window.auto_compile_toggle.font().pointSizeF()})
        assert root.read_text() == text and not window.compile_authorized_roots
        report["source_unchanged_no_compile"] = True
    finally:
        for tab in window.tabs.values():
            tab.modified = tab.dirty = False
            window.documents.cancel_save_timer(tab)
        window.close()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        report["window_destroyed"] = not isValid(window)
        report["app_sha256_after"] = source_digest()
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    args = parser.parse_args()
    os.environ["QT_QPA_PLATFORM"] = "cocoa" if args.native else "offscreen"
    run(args.output.resolve(), args.native)
