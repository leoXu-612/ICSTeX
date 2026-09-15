"""Observe native PDF controls in the real MainWindow using a Qt-only fixture.

No LaTeX compilation, source edits, exports, native key synthesis or installed
app changes. The explicit QA menu only loads/clears this run's synthetic PDF.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import signal
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QEvent, QObject, QPointF, QSettings, QTimer
from PySide6.QtGui import QPainter, QPdfWriter
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.probe_citation_health import close
from tools.probe_history_restore import app_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(exist_ok=False)
    application = QApplication([])
    assert application.platformName() == "cocoa"
    application.setQuitOnLastWindowClosed(True)
    apply_theme(application)
    pdf = output / "synthetic-three-pages.pdf"
    writer = QPdfWriter(str(pdf))
    writer.setResolution(72)
    writer.setTitle("Synthetic PDF keyboard fixture - no LaTeX compilation")
    painter = QPainter(writer)
    for page in range(1, 4):
        if page > 1:
            writer.newPage()
        painter.drawText(40, 60, f"SYNTHETIC PDF KEYBOARD PAGE {page} OF 3")
        for row in range(1, 15):
            painter.drawText(40, 60 + row * 36, f"Page {page}; read-only navigation line {row}.")
    painter.end()
    del writer
    pdf_bytes = pdf.read_bytes()
    root = output / "main.tex"
    root.write_text("\\documentclass{article}\n\\begin{document}\nSynthetic keyboard fixture.\n\\end{document}\n")
    root_bytes = root.read_bytes()
    source_hash = app_digest()
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / "qa.ini"), QSettings.Format.IniFormat)))
    window.auto_compile_action.setChecked(False)
    window.open_file(root)
    panel = window.pdf_panel
    started = time.monotonic()
    states, actions, keys, compile_starts = [], [], [], []
    errors = []
    interrupted = timed_out = False

    def record_action(name):
        actions.append({"seconds": round(time.monotonic() - started, 4), "name": name})

    def load_fixture():
        assert pdf.read_bytes() == pdf_bytes
        panel.load_pdf(pdf, logical_key=root)
        panel.set_freshness("Synthetic Qt PDF; not a LaTeX build or submission artifact", "warning")
        record_action("fixture_load")

    def clear_fixture():
        panel.clear_pdf()
        record_action("fixture_clear")

    menu = window.menuBar().addMenu("QA 合成 PDF")
    menu.addAction("加载三页合成 PDF", load_fixture)
    menu.addAction("清空合成预览", clear_fixture)
    controls = {"page": panel.page_spin, "zoom-out": panel.zoom_out_button,
                "zoom-in": panel.zoom_in_button, "fit-width": panel.fit_width_button,
                "more": panel._more_button, "previous": panel.prev_page_button,
                "next": panel.next_page_button, "fit-page": panel.fit_page_button,
                "export": panel.export_pdf_button, "reveal": panel.reveal_pdf_button,
                "pdf-view": panel._view}
    for name, control in controls.items():
        if hasattr(control, "clicked"):
            control.clicked.connect(lambda _checked=False, name=name: record_action(name))
    window.signals.started.connect(lambda root, build_id: compile_starts.append([root, build_id]))

    class Observer(QObject):
        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.KeyPress:
                keys.append({"key": event.key(), "modifiers": event.modifiers().value,
                             "target": watched.metaObject().className()})
            return False

    observer = Observer(window)
    application.installEventFilter(observer)

    def geometry(widget):
        rect = widget.rect()
        rect.moveTopLeft(widget.mapTo(window, rect.topLeft()))
        return {"visible": widget.isVisible(), "enabled": widget.isEnabled(),
                "unclipped": widget.visibleRegion().contains(widget.rect()),
                "inside_window": window.rect().contains(rect),
                "rect": [rect.x(), rect.y(), rect.width(), rect.height()]}

    def capture():
        focus = application.focusWidget()
        tab = window.current_tab()
        value = {
            "scale": window.preferences.ui_scale, "window": [window.width(), window.height()],
            "focus_role": next((name for name, control in controls.items() if control is focus), None),
            "focus_class": focus.metaObject().className() if focus else None,
            "controls": {name: geometry(control) for name, control in controls.items()},
            "menu_actions": [{"text": a.text(), "enabled": a.isEnabled()}
                             for a in panel._more_button.menu().actions()],
            "menu_open": panel._more_button.menu().isVisible(),
            "pages": panel._document.pageCount(), "page": panel.current_page(),
            "page_value": panel.page_spin.value(), "page_max": panel.page_spin.maximum(),
            "zoom": panel._view.zoomFactor(), "zoom_mode": panel._view.zoomMode().name,
            "effective_zoom": panel._effective_zoom(panel.current_page() - 1) if panel._document.pageCount() else None,
            "viewport_anchor": panel.pdf_position_for_viewport_point(QPointF(
                panel._view.viewport().width() / 2, panel._view.viewport().height() * .4)),
            "pane_overlap": window.main_splitter.widget(0).geometry().intersects(
                window.main_splitter.widget(1).geometry()),
            "panes": [geometry(window.main_splitter.widget(i)) for i in range(2)],
            "scroll": [panel._view.horizontalScrollBar().value(), panel._view.verticalScrollBar().value()],
            "current_pdf": str(panel.current_pdf) if panel.current_pdf else None,
            "source": tab.editor.toPlainText(), "source_cursor": tab.editor.textCursor().position(),
            "source_scroll": tab.editor.verticalScrollBar().value(),
            "files_unchanged": root.read_bytes() == root_bytes and pdf.read_bytes() == pdf_bytes,
            "compile_authorized": bool(window.compile_authorized_roots),
            "compile_start_count": len(compile_starts), "action_count": len(actions),
        }
        if not states or states[-1]["value"] != value:
            image = f"state-{len(states) + 1:03d}.png"
            assert window.grab().save(str(output / image))
            states.append({"seconds": round(time.monotonic() - started, 4), "image": image, "value": value})
            if value["menu_open"]:
                menu_image = image.replace(".png", "-menu.png")
                assert panel._more_button.menu().grab().save(str(output / menu_image))
                states[-1]["menu_image"] = menu_image
            print(json.dumps(states[-1], ensure_ascii=False), flush=True)
        elif "settled_image" not in states[-1] and time.monotonic() - started - states[-1]["seconds"] >= .25:
            image = states[-1]["image"].replace(".png", "-settled.png")
            assert window.grab().save(str(output / image))
            states[-1]["settled_image"] = image

    def tick():
        nonlocal timed_out
        try:
            capture()
            if time.monotonic() - started > 600:
                timed_out = True
                capture_timer.stop()
                close(window)
        except Exception as exc:
            errors.append({"type": type(exc).__name__, "message": str(exc)})
            capture_timer.stop()
            close(window)

    def interrupt(_signum, _frame):
        nonlocal interrupted
        interrupted = True
        capture_timer.stop()
        close(window)

    # Observe nested QMenu event loops too; the outer processEvents loop alone
    # cannot capture a menu while its synchronous popup is active.
    capture_timer = QTimer(window)
    capture_timer.setInterval(80)
    capture_timer.timeout.connect(tick)
    capture_timer.start()
    signal.signal(signal.SIGINT, interrupt)
    window.resize(1080, 720)
    window.show()
    window.set_toolbox_visible(True)
    window.sidebar_tabs.setCurrentIndex(1)
    window.raise_()
    window.activateWindow()
    print("READY: empty PDF; use QA menu to load fixture, native controls/scale, clear and close", flush=True)
    try:
        application.exec()
    except KeyboardInterrupt:
        interrupted = True
    except Exception as exc:
        errors.append({"type": type(exc).__name__, "message": str(exc)})
    finally:
        if isValid(window):
            close(window)
        application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    report = {"platform": platform.platform(), "pyside": pyside_version,
              "app_sha256": source_hash, "app_sha256_after": app_digest(),
              "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(), "synthetic_only": True,
              "states": states, "keys": keys, "actions": actions, "compile_starts": compile_starts,
              "errors": errors, "interrupted": interrupted, "timeout": timed_out,
              "window_destroyed": not isValid(window),
              "files_unchanged": root.read_bytes() == root_bytes and pdf.read_bytes() == pdf_bytes,
              "limits": ["Qt-generated three-page fixture, not a LaTeX FINAL",
                         "QA menu loading is harness setup, not a product open-PDF workflow",
                         "Native controls/screenshots require review; no broad pass predicate"]}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    assert not errors and not interrupted and not timed_out and report["window_destroyed"]
    assert report["files_unchanged"] and report["app_sha256_after"] == source_hash


if __name__ == "__main__":
    main()
