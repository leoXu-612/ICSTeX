"""Compare bare Qt PDF page modes at bounded view sizes, using a known synthetic PDF."""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QEvent
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6 import __version__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-pdf", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.synthetic_pdf.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.sha256
    args.output.mkdir(parents=True, exist_ok=False)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    doc = QPdfDocument(app)
    doc.load(str(args.synthetic_pdf.resolve()))
    assert doc.pageCount() == 1
    box = doc.getAllText(0).boundingRectangle()
    report = {"pyside": __version__, "pdf_sha256": args.sha256,
              "page_points": [doc.pagePointSize(0).width(), doc.pagePointSize(0).height()],
              "text_bounds": [box.x(), box.y(), box.width(), box.height()], "states": [],
              "limits": "Bare offscreen Qt; not ICSTeX native or general renderer acceptance"}
    for mode in (QPdfView.PageMode.MultiPage, QPdfView.PageMode.SinglePage):
        for width in (420, 620):
            view = QPdfView()
            view.setDocument(doc)
            view.setPageMode(mode)
            view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            view.resize(width, 600)
            view.show()
            QTest.qWait(500)
            image = view.viewport().grab().toImage()
            dark = sum(1 for y in range(20, image.height() - 20, 2) for x in range(20, image.width() - 20, 2)
                       if (c := image.pixelColor(x, y)).red() < 90 and c.green() < 90 and c.blue() < 90)
            name = f"{mode.name}-{width}.png"
            image.save(str(args.output / name))
            report["states"].append({"mode": mode.name, "requested_width": width,
                "viewport": [image.width(), image.height()], "dark_samples": dark, "image": name})
            view.close()
            view.deleteLater()
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert args.synthetic_pdf.read_bytes() == raw
    (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
