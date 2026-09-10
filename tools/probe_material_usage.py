"""Read-only material UI checks and an explicit real image FINAL on synthetic data.

Offscreen renders are not native keyboard/IME/AX acceptance. A new --output
directory holds all evidence, fixture files and isolated settings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness
from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.probe_submission_check import wait_for


def image(path, color):
    pixels = QImage(120, 60, QImage.Format.Format_RGB32)
    pixels.fill(QColor(color))
    assert pixels.save(str(path))


def snapshot(project):
    return {path.relative_to(project).as_posix(): path.read_bytes()
            for path in project.rglob("*") if path.is_file() and ".latex_build" not in path.parts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("ICSTeX Material Usage QA")
    apply_theme(app)
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    evidence = {"platform": platform.platform(), "python": platform.python_version(),
                "qt_platform": app.platformName(), "app_python_tree_sha256": digest.hexdigest()}
    project = output / "synthetic-project"
    (project / "figures").mkdir(parents=True)
    (project / "chapters").mkdir()
    root, child = project / "main.tex", project / "chapters/child.tex"
    root.write_text("\\documentclass{article}\n\\usepackage{graphicx}\n\\graphicspath{{figures/}}\n"
                    "\\begin{document}\n\\input{chapters/child}\n\\end{document}\n")
    child.write_text("% !TeX root = ../main.tex\nSynthetic images:\n" +
                     "\n".join(f"{name}: \\includegraphics[width=1cm]{{{name}.png}}\\par" for name in
                               ("used", "changed", "moved", "missing")) + "\n")
    for name, color in (("used", "#2468A0"), ("changed", "#AA5522"), ("moved", "#22AA55"),
                        ("missing", "#6655AA"), ("unused", "#AAAA22")):
        image(project / f"figures/{name}.png", color)
    initial = snapshot(project)
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / "qa.ini"), QSettings.Format.IniFormat)))
    evidence["refresh_attempts"] = []
    try:
        window.auto_compile_action.setChecked(False)
        window.save_debounce_ms = 3600000
        window.project_files.set_project_root(project)
        window.open_file(root)
        window.compile.set_engine(LaTeXEngine.PDFLATEX, compile_after=False)
        window.resize(1120, 820)
        window.show()
        window.set_toolbox_visible(True)
        window.sidebar_tabs.setCurrentIndex(3)
        panel = window.images_panel
        wait_for(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)

        def inspect():
            # A real queued filesystem event may invalidate a just-finished
            # check. Retry explicitly only after observing that invalidation.
            for attempt in range(1, 5):
                panel.check_button.click()
                wait_for(lambda: not window.materials.is_busy)
                QTest.qWait(600)
                report = panel.material_report
                if report is not None and report.stable:
                    evidence["refresh_attempts"].append(attempt)
                    return report
            raise AssertionError(panel.check_status.text())

        started = time.perf_counter()
        report = inspect()
        evidence["five_asset_check_ms"] = round((time.perf_counter() - started) * 1000, 2)
        assert report.complete, report.items
        assert sum(item.rule == "asset_present" for item in report.items) == 4
        assert sum(item.rule == "asset_unused" for item in report.items) == 1
        assert snapshot(project) == initial
        assert not window.compile_authorized_roots
        assert not (project / ".icstex/asset-index.json").exists()
        evidence["initial_check_no_source_asset_or_cache_writes"] = True

        window.compile_action.trigger()
        wait_for(lambda: window.pdf_state.record_for(root).freshness == PdfFreshness.CURRENT)
        wait_for(lambda: window.pdf_panel._document is not None and window.pdf_panel._document.pageCount() > 0)
        record = window.pdf_state.record_for(root)
        build_id = record.latest_build_id
        payload = record.last_successful_pdf.read_bytes()
        (output / "material-final.pdf").write_bytes(payload)
        evidence["explicit_final_pdf_sha256"] = hashlib.sha256(payload).hexdigest()
        evidence["explicit_final_pdf_pages"] = window.pdf_panel._document.pageCount()
        after_final = snapshot(project)
        assert all(after_final.get(path) == raw for path, raw in initial.items())
        extra_files = sorted(after_final.keys() - initial.keys())
        assert all(path.startswith(".icstex/history/") for path in extra_files), extra_files
        evidence["explicit_compile_created_existing_history_records"] = extra_files

        changed, moved, missing = (project / f"figures/{name}.png" for name in ("changed", "moved", "missing"))
        image(changed, "#CC4422")
        relocated = project / "figures/relocated.png"
        moved.rename(relocated)
        missing.unlink()
        for path in (changed, moved, missing, relocated):
            window.signals.external_changed.emit(str(path))
        QTest.qWait(1200)  # Let the real watcher/dependency queue observe fixture mutations.
        before_check = snapshot(project)
        report = inspect()
        assert report.complete, report.items
        expected = {"asset_changed", "asset_candidate", "asset_missing", "asset_unused", "asset_present"}
        assert expected <= {item.rule for item in report.items}, report.items
        evidence["rules_after_external_changes"] = [
            {"rule": item.rule, "status": item.status, "label": item.label,
             "locations": [f"{loc.path.relative_to(project)}:{loc.line}" for loc in item.locations],
             "candidates": [str(path.relative_to(project)) for path in item.candidates]} for item in report.items]
        assert snapshot(project) == before_check
        assert record.latest_build_id == build_id
        assert record.freshness == PdfFreshness.DIRTY
        evidence["checking_did_not_recompile_stale_pdf"] = True
        row = next(i for i, item in enumerate(report.items) if item.rule == "asset_changed")
        panel.health_table.selectRow(row)
        assert "本窗口上次可读记录" in panel.check_detail.toPlainText()
        scroll = window.sidebar_tabs.widget(3)
        evidence["scale_and_size_checks"] = []
        for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
            window.set_ui_scale(scale)
            for width, height in ((1120, 820), (880, 640)):
                window.resize(width, height)
                window.set_toolbox_visible(True)
                app.processEvents()
                assert panel.isVisible()
                for button in (panel.check_refresh_button, panel.check_cancel_button, panel.check_locate_button):
                    scroll.ensureWidgetVisible(button)
                    app.processEvents()
                    assert scroll.viewport().rect().contains(button.mapTo(scroll.viewport(), button.rect().center()))
                evidence["scale_and_size_checks"].append([scale, width, height, window.width(), window.height()])
            scroll.verticalScrollBar().setValue(0)
            app.processEvents()
            assert window.grab().save(str(output / f"material-controls-{round(scale * 100)}.png"))
            scroll.ensureWidgetVisible(panel.check_detail)
            app.processEvents()
            assert window.grab().save(str(output / f"material-detail-{round(scale * 100)}.png"))
        window.set_ui_scale(1.0)
        window.resize(1120, 820)
        QTest.qWait(200)
        pdf_view = window.pdf_panel._capture_state()
        panel.check_locate_button.click()
        assert window.current_tab().path == child
        assert window.current_tab().editor.textCursor().blockNumber() + 1 == 4
        QTest.qWait(200)
        window.materials.reconcile()
        assert panel.material_report is report
        assert window.pdf_panel._capture_state() == pdf_view
        evidence["changed_asset_navigation_preserves_pdf_view"] = "chapters/child.tex:4"
        draft = window.current_tab()
        draft.editor.setPlainText("% !TeX root = ../main.tex\nNo image uses in this unsaved draft.\n")
        window.editor_tabs.setCurrentWidget(window._tab_for_path(root).editor)
        report = inspect()
        assert report.complete
        assert not any(item.rule == "asset_missing" for item in report.items)
        assert snapshot(project) == before_check
        evidence["unsaved_child_replaces_disk_usage_without_saving"] = True
        panel.check_refresh_button.click()
        panel.check_cancel_button.click()
        wait_for(lambda: not window.materials.is_busy)
        assert panel.material_report is None
        assert snapshot(project) == before_check
        evidence["cancel_no_source_asset_or_cache_writes"] = True
    finally:
        for tab in window.tabs.values():
            window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    evidence["limits"] = ["Supported static image/PDF/SVG locations, not arbitrary TeX execution or image validity",
                           "In-memory previous readable observations are not persistent provenance or backups",
                           "Offscreen and synthetic events are not native IME/AX/Windows/human acceptance",
                           "No package, installed-app replacement, upload, commit or release"]
    (output / "report.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
