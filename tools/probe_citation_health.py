"""Synthetic citation-panel and real FINAL probe; no installed app/user files.

Offscreen captures demonstrate layout and product wiring, not native acceptance.
Pass a fresh --output directory; settings and synthetic projects stay inside it.
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
from PySide6.QtWidgets import QApplication
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness
from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.probe_submission_check import wait_for


def close(window):
    for tab in window.tabs.values():
        window.documents.cancel_save_timer(tab)
        tab.modified = tab.dirty = False
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("ICSTeX Citation QA")
    apply_theme(app)
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    evidence = {"platform": platform.platform(), "python": platform.python_version(),
                "qt_platform": app.platformName(), "app_python_tree_sha256": digest.hexdigest()}
    project = output / "synthetic-project"
    (project / "chapters").mkdir(parents=True)
    (project / "literature").mkdir()
    root, child, bib, extra = (project / "main.tex", project / "chapters/child.tex",
                              project / "literature/catalog.bib", project / "extra.bib")
    root.write_text("\\documentclass{article}\n\\begin{document}\n\\input{chapters/child}\n"
                    "\\bibliographystyle{plain}\n\\bibliography{literature/catalog,extra}\n\\end{document}\n")
    child.write_text("% !TeX root = ../main.tex\nSynthetic \\cite[see]{Known,Missing}.\n")
    bib.write_text("@article{Known,title={Synthetic}}\n@book{Duplicate,title={First}}\n")
    extra.write_text("@book{Duplicate,title={Second}}\n@book{Unused,title={Unused}}\n")
    before = {path: path.read_bytes() for path in (root, child, bib, extra)}
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / "qa.ini"), QSettings.Format.IniFormat)))
    try:
        window.auto_compile_action.setChecked(False)
        window.save_debounce_ms = 3600000
        window.project_files.set_project_root(project)
        window.open_file(root)
        window.resize(1120, 820)
        window.show()
        window.set_toolbox_visible(True)
        window.sidebar_tabs.setCurrentIndex(7)
        panel = window.references_panel
        wait_for(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
        started = time.perf_counter()
        panel.check_button.click()
        wait_for(lambda: not window.citations.is_busy)
        report = panel.citation_report
        assert report is not None and report.complete and report.stable, panel.check_status.text()
        evidence["small_project_check_ms"] = round((time.perf_counter() - started) * 1000, 2)
        evidence["rules"] = [{"rule": item.rule, "status": item.status, "key": item.key,
                              "locations": [f"{loc.path.relative_to(project)}:{loc.line}" for loc in item.locations]}
                             for item in report.items]
        assert any(item.rule == "key_duplicate" and item.status == "fail" for item in report.items)
        assert any(item.rule == "entry_unused" and item.key == "Unused" for item in report.items)
        row = next(i for i, item in enumerate(report.items) if item.rule == "citation_missing")
        panel.health_table.selectRow(row)
        assert "已读取的文献库" in panel.check_detail.toPlainText()
        scroll = window.sidebar_tabs.widget(7)
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
                    center = button.mapTo(scroll.viewport(), button.rect().center())
                    assert scroll.viewport().rect().contains(center), (scale, width, button.text(), center)
                evidence["scale_and_size_checks"].append([scale, width, height, window.width(), window.height()])
            scroll.ensureWidgetVisible(panel.health_table)
            app.processEvents()
            assert window.grab().save(str(output / f"citation-{round(scale * 100)}.png"))
            scroll.verticalScrollBar().setValue(0)
            app.processEvents()
            assert window.grab().save(str(output / f"citation-controls-{round(scale * 100)}.png"))
        window.set_ui_scale(1.0)
        window.resize(1120, 820)
        panel.check_locations.setCurrentRow(0)
        panel.check_locate_button.click()
        assert window.current_tab().path == child
        assert window.current_tab().editor.textCursor().blockNumber() == 1
        app.processEvents()
        window.citations.reconcile()
        assert panel.citation_report is report
        evidence["missing_citation_navigation"] = "chapters/child.tex:2"
        window.open_file(extra)
        draft = window.current_tab()
        draft.editor.setPlainText("@book{Missing,title={Unsaved draft}}\n@book{Unused,title={Unused}}")
        window.editor_tabs.setCurrentWidget(window._tab_for_path(root).editor)
        panel.check_refresh_button.click()
        wait_for(lambda: not window.citations.is_busy)
        report = panel.citation_report
        assert report is not None and report.complete
        assert not any(item.rule in {"citation_missing", "key_duplicate"} for item in report.items)
        assert extra.read_bytes() == before[extra]
        evidence["bib_draft_checked_without_saving"] = True
        panel.check_refresh_button.click()
        panel.check_cancel_button.click()
        wait_for(lambda: not window.citations.is_busy)
        assert panel.citation_report is None
        assert all(path.read_bytes() == payload for path, payload in before.items())
        assert not window.compile_authorized_roots
        evidence["check_navigation_cancel_zero_source_byte_changes"] = True
        evidence["checking_did_not_authorize_compile"] = True
    finally:
        close(window)

    # This separate synthetic scenario explicitly compiles a legal bibliography.
    # The read-only check above never invokes this action itself.
    final_dir = output / "synthetic-final"
    final_dir.mkdir()
    final_root, final_bib = final_dir / "main.tex", final_dir / "catalog.bib"
    final_root.write_text("\\documentclass{article}\n\\begin{document}\n"
                          "Synthetic citation \\cite{Known,Child}.\\nocite{*}\n"
                          "\\bibliographystyle{plain}\n\\bibliography{catalog}\n\\end{document}\n")
    final_bib.write_text('@string{venue = "Synthetic Journal"}\n'
                         '@article{Known,author={Jane Doe},title={100\\% original},journal=venue,year=2026,month="1~" # jan}\n'
                         '@inproceedings{Child,author={A. Author},title={Child title},crossref="Parent"}\n'
                         '@proceedings{Parent,editor={B. Editor},title={Parent title},booktitle={Parent title},year=2026,publisher={Synthetic Press}}\n'
                         '@book{Unused,author={C. Author},title={Preserved by nocite},year=2026,publisher={Synthetic Press}}\n')
    final_before = {path: path.read_bytes() for path in (final_root, final_bib)}
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / "final-qa.ini"), QSettings.Format.IniFormat)))
    try:
        window.auto_compile_action.setChecked(False)
        window.project_files.set_project_root(final_dir)
        window.open_file(final_root)
        window.compile.set_engine(LaTeXEngine.PDFLATEX, compile_after=False)
        window.show()
        wait_for(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
        window.references_panel.check_button.click()
        wait_for(lambda: not window.citations.is_busy)
        report = window.references_panel.citation_report
        assert report is not None and report.complete, window.references_panel.check_status.text()
        assert not any(item.status in {"fail", "unknown", "suggestion"} for item in report.items), report.items
        assert not window.compile_authorized_roots
        window.compile_action.trigger()
        wait_for(lambda: window.pdf_state.record_for(final_root).freshness == PdfFreshness.CURRENT)
        wait_for(lambda: window.pdf_panel._document is not None and window.pdf_panel._document.pageCount() > 0)
        pdfs = list((final_dir / ".latex_build").rglob("main.pdf"))
        assert len(pdfs) == 1, pdfs
        payload = pdfs[0].read_bytes()
        (output / "citation-final.pdf").write_bytes(payload)
        evidence["final_pdf_sha256"] = hashlib.sha256(payload).hexdigest()
        evidence["final_pdf_pages"] = window.pdf_panel._document.pageCount()
        evidence["bibtex_logs"] = [str(path.relative_to(output)) for path in final_dir.rglob("*.blg")]
        assert evidence["bibtex_logs"], "Require actual BibTeX execution, not only a successful TeX PDF"
        assert all(path.read_bytes() == original for path, original in final_before.items())
        evidence["real_final_preserved_source_bytes"] = True
        assert window.grab().save(str(output / "citation-final-window.png"))
    finally:
        close(window)
    evidence["limits"] = ["Static syntax, no arbitrary macro, manual bibliography, alias or section expansion",
                           "Synthetic offscreen checks are not native keyboard/IME/AX or Windows acceptance",
                           "No packaging, installation, signing, network lookup or release"]
    (output / "report.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
