"""Capture local tutorial illustrations from an owned, actually compiled exercise."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QEvent, QRect, QSettings
from PySide6.QtWidgets import QApplication
from app.core.pdf_state import PdfFreshness
from app.core.settings import AppSettings
from app.core.tutorial import TutorialStep
from app.gui.diagnostics_panel import DiagnosticsPanel
from app.gui.main_window import MainWindow
from app.gui.submission_delivery_dialog import SubmissionDeliveryDialog
from app.gui.theme import apply_theme
from app.gui.tutorial_controller import open_example
from app.gui.user_guide import UserGuideDialog
from tools.bench_pdf_pipeline import source_digest, wait_gui
from tools.pdf_pixel_evidence import interior_ink_pixels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory for the owned exercise and evidence")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    assets = REPO / "app/assets/user-guide"
    assets.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    owner = MainWindow(settings_store=AppSettings(QSettings(str(out / "owner.ini"), QSettings.Format.IniFormat)))
    owner.auto_compile_action.setChecked(False)
    digest = source_digest()
    images = {}

    def capture(widget, name, rect=None):
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        pixmap = widget.grab(rect) if rect is not None else widget.grab()
        target = assets / name
        assert pixmap.save(str(target))
        images[name] = dict(width=pixmap.width(), height=pixmap.height(),
                            sha256=hashlib.sha256(target.read_bytes()).hexdigest())

    with patch("app.gui.tutorial_controller.example_directory", return_value=out / "examples"):
        window = open_example(owner)
        assert window is not None
        controller, tab = window.tutorial, window.current_tab()
        root = controller.root
        window.resize(1080, 850)
        assert not window.compile_authorized_roots
        controller.act()
        assert tab.editor.textCursor().hasSelection()
        app.processEvents()
        capture(tab.editor, "edit-title.png", QRect(0, max(0, tab.editor.cursorRect().y() - 85), 660, 240))
        tab.editor.insertPlainText("我的第一篇文章")
        wait_gui(lambda: controller.step is TutorialStep.COMPILE, timeout=5)
        before = (tab.editor.textCursor().position(), tab.editor.verticalScrollBar().value())
        controller.act()
        wait_gui(lambda: controller.step is TutorialStep.VIEW, timeout=50)
        wait_gui(lambda: "我的第一篇文章" in window.pdf_panel._document.getAllText(0).text())
        assert (tab.editor.textCursor().position(), tab.editor.verticalScrollBar().value()) == before
        app.processEvents()  # Let the new step's longer button label finish layout.
        assert window.grab().save(str(out / "before-show-pdf.png"))
        if not window.pdf_panel.isVisibleTo(window):
            controller.secondary_action()
        assert controller.dock.isVisibleTo(window)
        wait_gui(lambda: window.pdf_panel.isVisibleTo(window))
        wait_gui(lambda: interior_ink_pixels(window.pdf_panel._view.viewport().grab().toImage()) > 100, timeout=10)
        window.resize(1440, 900)
        app.processEvents()
        capture(window.source_preview_area, "write-preview.png", QRect(0, 0, window.source_preview_area.width(), 350))
        controller.act()
        assert controller.step is TutorialStep.DONE
        valid = tab.editor.toPlainText()
        tab.editor.setPlainText(valid.replace("\\end{document}", "\\notacommand\n\\end{document}"))
        wait_gui(lambda: controller.step is TutorialStep.COMPILE, timeout=5)
        controller.act()
        wait_gui(lambda: window.pdf_state.record_for(root).freshness is PdfFreshness.FAILED_STALE, timeout=50)
        wait_gui(lambda: controller.secondary.text() == "查看错误", timeout=5)
        assert controller.step is TutorialStep.COMPILE
        errors = DiagnosticsPanel()
        errors.set_diagnostics(window.diagnostic_panel.diagnostics)
        errors.resize(680, 320)
        errors.show()
        capture(errors, "check-error.png")
        errors.close()
        errors.deleteLater()
        tab.editor.setPlainText(valid)
        controller.refresh()
        controller.act()
        wait_gui(lambda: controller.step is TutorialStep.VIEW, timeout=50)
        delivery = SubmissionDeliveryDialog(window)
        delivery.resize(720, 620)
        delivery.show()
        capture(delivery, "export-pdf.png")
        delivery._close()
        delivery.close()
        delivery.deleteLater()
        guide = UserGuideDialog(window)
        guide.show()
        for index in range(guide.pages.count()):
            guide.pages.setCurrentIndex(index)
            app.processEvents()
            assert guide.grab().save(str(out / f"guide-page-{index + 1}.png"))
        guide.close()
        guide.deleteLater()
        controller.dock.hide()
        assert not controller.active and not controller._timer.isActive()
        assert open_example(owner, root) is window
        wait_gui(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
        for item in window.tabs.values():
            window.documents.cancel_save_timer(item)
            item.modified = item.dirty = False
        window.close()
    owner.close()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert source_digest() == digest
    report = dict(app_sha256=digest, backend=app.platformName(), images=images,
                  real_title_compile_and_pixels=True, failure_retains_old_pdf=True,
                  hide_resume_preserves_window=True, cursor_and_scroll_preserved=True,
                  export_image="prepare page only; no delivery created")
    (out / "result.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
