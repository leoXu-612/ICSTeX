"""Bounded native PDF reload/search/clear/disposal check on owned fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QEvent, QMarginsF, QObject, Qt
from PySide6.QtGui import QColor, QPainter, QPdfWriter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.core.pdf_identity import capture_pdf_identity
from app.gui.pdf_panel import PdfPanel
from app.gui.theme import apply_theme
from tools.bench_auto_compile_latency import marker_pixels
from tools.bench_pdf_pipeline import source_digest, wait_gui


class PaintCounter(QObject):
    count = 0

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Paint:
            self.count += 1
        return False


def make_pdf(path, rgb, word):
    writer = QPdfWriter(str(path))
    writer.setResolution(72)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    painter = QPainter(writer)
    for page in range(3):
        if page:
            writer.newPage()
        painter.drawText(40, 60, f"ICSTeX reload check: {word} page {page + 1}")
        painter.fillRect(80, 90, 160, 100, QColor(*rgb))
    painter.end()
    del writer


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication([])
    assert app.platformName() == "cocoa"
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    before_hash = source_digest()
    report = {"app_sha256": before_hash, "pid": os.getpid(), "completed": False, "states": [],
              "limits": "Owned synthetic PDFs; natural Paint then widget pixels, not compositor timing or proof of historical crash causality"}
    red, blue = (234, 18, 142), (17, 219, 153)
    first, second, replacement = (output / name for name in ("first.pdf", "second.pdf", "replacement.pdf"))
    make_pdf(first, red, "alpha")
    make_pdf(second, blue, "beta")
    initial = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (first, second)}
    panel = PdfPanel()
    panel.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    panel.setWindowTitle(f"ICSTeX - PDF reload lifecycle - {os.getpid()}")
    panel.resize(900, 650)
    counter = PaintCounter(panel)
    panel._view.viewport().installEventFilter(counter)
    panel.viewChanged.connect(lambda view: view.viewport().installEventFilter(counter))
    panel.show()
    panel.raise_()
    panel.activateWindow()

    def loaded(name, path, rgb, key, query):
        assert panel.isActiveWindow() and panel.windowHandle().isExposed()
        paints, started = counter.count, time.perf_counter()
        panel.load_pdf(path, logical_key=key, content_identity=capture_pdf_identity(path, output))
        wait_gui(lambda: counter.count > paints, timeout=5)
        wait_gui(lambda: marker_pixels(panel._view.viewport().grab().toImage(), rgb) > 100, timeout=5)
        pixel_ms = (time.perf_counter() - started) * 1000
        assert panel.current_pdf == path and panel.current_logical_key == key
        assert panel._document.pageCount() == 3
        panel.show_pdf_search()
        panel.pdf_search_edit.setText(query)
        wait_gui(lambda: panel._search_model.count() == 3, timeout=5)
        assert panel.pdf_search_status.text().endswith("/3"), panel.pdf_search_status.text()
        image = name + ".png"
        panel.grab().save(str(output / image))
        report["states"].append({"case": name, "pages": 3, "search_matches": 3,
            "load_to_pixel_upper_bound_ms": pixel_ms, "image": image})

    try:
        wait_gui(lambda: panel.isActiveWindow() and panel.windowHandle().isExposed(), timeout=10)
        root = output / "first.tex"
        loaded("initial", first, red, root, "reload check")
        panel.zoom_by(1.2)
        panel.jump_to_page(2)
        QTest.qWait(160)
        before = panel._capture_state()
        panel.load_pdf(first, logical_key=root, content_identity=capture_pdf_identity(first, output))
        assert panel.last_load_reused and panel._capture_state() == before
        assert panel._search_model.count() == 3
        report["states"].append({"case": "unchanged_reuse", "view_and_query_preserved": True})
        make_pdf(replacement, blue, "beta")
        replacement.replace(first)
        loaded("same_path_new_bytes", first, blue, root, "reload check")
        QTest.qWait(160)
        assert panel._capture_state() == before, (before, panel._capture_state())
        loaded("other_root", second, blue, output / "second.tex", "beta")
        for cycle in range(6):
            panel.pdf_search_edit.setText("pending-search-" + str(cycle))
            panel.clear_pdf()
            assert panel._document.pageCount() == 0 and panel.current_pdf is None
            assert not panel.pdf_search_edit.text() and panel._search_model.count() == 0
            loaded(f"clear_reload_{cycle}", second, blue, output / "second.tex", "beta")
        panel.pdf_search_edit.setText("pending-at-close")
        report["completed"] = True
    except BaseException as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        if isValid(panel):
            panel.grab().save(str(output / "failure.png"))
        raise
    finally:
        if isValid(panel):
            panel.close()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QTest.qWait(200)
        report["destroyed"] = not isValid(panel)
        report["app_sha256_after"] = source_digest()
        report["second_pdf_unchanged"] = hashlib.sha256(second.read_bytes()).hexdigest() == initial[second.name]
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    assert report["completed"] and report["destroyed"] and report["second_pdf_unchanged"]
    assert report["app_sha256_after"] == before_hash
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output.resolve())
