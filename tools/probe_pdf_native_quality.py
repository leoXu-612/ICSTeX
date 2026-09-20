"""Observe an existing, explicitly identified synthetic PDF in the real PdfPanel.

No compilation, source editing, native key synthesis or installed-app changes.
The receipt records observations, not a broad rendering-quality pass predicate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.gui.pdf_panel import PdfPanel
from app.gui.theme import apply_theme
from tools.probe_history_restore import app_digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-pdf", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pdf = args.synthetic_pdf.resolve()
    before = pdf.read_bytes()
    assert hashlib.sha256(before).hexdigest() == args.expected_sha256
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    application = QApplication([])
    assert application.platformName() == "cocoa", "Native observation requires Cocoa"
    application.setQuitOnLastWindowClosed(False)
    apply_theme(application)
    source_hash = app_digest()
    panel = PdfPanel()
    panel.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    panel.setWindowTitle("ICSTeX - Synthetic PDF quality QA")
    panel.resize(900, 650)
    panel.load_pdf(pdf)
    panel.set_freshness("Synthetic PDF inspection; no new FINAL compilation", "warning")
    panel.show()
    states = []
    started = time.monotonic()
    configured = False
    interrupted = False
    timeout = False
    try:
        while isValid(panel):
            application.processEvents()
            if not isValid(panel):
                break
            if panel._document is not None and panel._document.pageCount() > 0:
                if not configured:
                    panel.zoom_by(2.0 / panel._view.zoomFactor())
                    application.processEvents()
                    panel.jump_to_pdf_position(1, 305, 145)
                    configured = True
                    print("READY: synthetic PDF at 200%; inspect with native UI, then close", flush=True)
                view = panel._view
                value = {
                    "seconds": round(time.monotonic() - started, 4),
                    "zoom": view.zoomFactor(),
                    "page": panel.current_page(),
                    "scroll": [view.horizontalScrollBar().value(), view.verticalScrollBar().value()],
                    "viewport": [view.viewport().width(), view.viewport().height()],
                    "device_pixel_ratio": view.devicePixelRatioF(),
                }
                identity = {k: v for k, v in value.items() if k != "seconds"}
                previous = {k: v for k, v in states[-1].items() if k not in {"seconds", "image"}} if states else None
                if identity != previous or (len(states) == 1 and time.monotonic() - started > 2):
                    value["image"] = f"state-{len(states) + 1:03d}.png"
                    assert panel.grab().save(str(output / value["image"]))
                    states.append(value)
                    print(json.dumps(value), flush=True)
            if time.monotonic() - started > 600:
                timeout = True
                break
            time.sleep(0.02)
    except KeyboardInterrupt:
        interrupted = True
    finally:
        if isValid(panel):
            panel.close()
        application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    report = {
        "platform": platform.platform(), "pyside": pyside_version,
        "qt_platform": application.platformName(), "app_sha256": source_hash,
        "app_sha256_after": app_digest(), "pdf_sha256": args.expected_sha256,
        "pdf_unchanged": pdf.read_bytes() == before,
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "states": states, "configured": configured, "timeout": timeout,
        "interrupted": interrupted, "window_destroyed": not isValid(panel),
        "limits": ["Synthetic existing PDF only; no new compilation",
                   "Programmatically configured 200% and location; no native zoom-input claim",
                   "Native screenshots require separate visual review; no broad pass predicate"],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    assert configured and not timeout and not interrupted and report["window_destroyed"]
    assert report["pdf_unchanged"] and report["app_sha256_after"] == source_hash


if __name__ == "__main__":
    main()
