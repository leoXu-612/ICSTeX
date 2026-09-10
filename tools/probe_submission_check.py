"""Verify M1 in an isolated source window with synthetic files and real TeX.

Run with QT_QPA_PLATFORM=cocoa on macOS for native rendering. Writes only a new
explicit evidence directory and a temporary synthetic project/settings store.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness
from app.core.settings import AppSettings
from app.core.submission_check import CheckStatus
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tests.v1_fixtures import create_project


def wait_for(predicate, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return
        time.sleep(0.005)
    raise RuntimeError("Source GUI verification timed out")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("ICSTeX V1 Source QA")
    apply_theme(app)
    evidence = {"platform": platform.platform(), "python": platform.python_version(),
                "qt_platform": app.platformName(),
                "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                "working_source": True, "scope": "Synthetic source GUI; no installed application or student files"}
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    evidence["app_python_tree_sha256"] = digest.hexdigest()
    with TemporaryDirectory(prefix="icstex-v1-source-qa-") as directory:
        base = Path(directory).resolve()
        sample = create_project(base)
        paths = [p for p in sample.root.parent.rglob("*") if p.is_file()]
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        settings = AppSettings(QSettings(str(base / "qa.ini"), QSettings.Format.IniFormat))
        window = MainWindow(settings_store=settings)
        try:
            window.setWindowTitle("ICSTeX V1 · Synthetic Source QA")
            window.auto_compile_action.setChecked(False)
            window.project_files.set_project_root(sample.root.parent)
            window.open_file(sample.root)
            window.set_engine(LaTeXEngine.PDFLATEX)
            window.resize(1120, 820)
            window.show()
            window.raise_()
            window.activateWindow()
            wait_for(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
            window.compile_action.trigger()
            wait_for(lambda: window.pdf_state.record_for(sample.root).freshness == PdfFreshness.CURRENT)
            wait_for(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
            window.readiness.show()
            wait_for(lambda: not window.readiness.is_busy)
            report = window.submission_panel.report
            if report is None:
                raise AssertionError(window.submission_panel.summary.text())
            statuses = {item.rule_id: item.status.value for item in report.items}
            for rule in ("saved", "root", "resources", "references", "final_build", "pdf_current", "final_log", "word_count"):
                assert statuses[rule] == CheckStatus.PASS.value, (rule, statuses)
            assert statuses["input_coverage"] == CheckStatus.UNKNOWN.value
            evidence["rules"] = statuses
            evidence["input_id"] = report.input_id
            wait_for(lambda: window.pdf_panel._document is not None and window.pdf_panel._document.pageCount() > 0)
            evidence["pdf_pages"] = window.pdf_panel._document.pageCount()
            evidence["source_window_visible"] = window.isVisible()
            assert evidence["source_window_visible"]
            screenshots = []
            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                window.set_ui_scale(scale)
                window.vertical_splitter.setSizes([480, 300])
                app.processEvents()
                panel = window.submission_panel
                for button in (panel.refresh_button, panel.cancel_button, panel.action_button):
                    assert panel.rect().contains(button.geometry()), (scale, button.text())
                name = f"submission-{round(scale * 100)}.png"
                assert window.grab().save(str(output / name))
                screenshots.append(name)
            evidence["scale_screenshots"] = screenshots
            original = sample.draft_path.read_text()
            sample.draft_path.write_text(original + "\\cite{not-found}\n", encoding="utf-8")
            window.signals.external_changed.emit(str(sample.draft_path))
            assert window.submission_panel.report is None
            wait_for(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
            window.readiness.request()
            wait_for(lambda: not window.readiness.is_busy)
            changed = window.submission_panel.report
            assert changed is not None
            index = next(i for i, item in enumerate(changed.items) if item.rule_id == "citation_missing")
            window.readiness.act(index)
            assert window.current_tab().path == sample.draft_path
            evidence["child_navigation_line"] = window.current_tab().editor.textCursor().blockNumber() + 1
            evidence["external_change_invalidated"] = True
            sample.draft_path.write_text(original, encoding="utf-8")
            evidence["original_bytes_restored"] = all(hashlib.sha256(p.read_bytes()).hexdigest() == value
                                                       for p, value in before.items())
            assert evidence["original_bytes_restored"]
            assert window.grab().save(str(output / "child-navigation.png"))
            # The active Block workspace must not inherit the source tab's FINAL.
            from app.core.blocks.project_repository import load_project
            from app.gui.blocks.project_session import ProjectSession
            from app.gui.block_mode import _close_block_project, _install_session, _set_block_mode
            block = create_project(base, "block")
            block_before = {p: p.read_bytes() for p in block.root.parent.rglob("*") if p.is_file()}
            loaded = load_project(block.root.parent)
            session = ProjectSession(**{key: loaded[key] for key in
                                     ("registry", "layout", "sources", "document_theme", "project_dir")})
            _install_session(window, session)
            _set_block_mode(window, True)
            window.readiness.show()
            wait_for(lambda: not window.readiness.is_busy)
            report = window.submission_panel.report
            assert report is not None
            assert all(item.scope == str(block.root) for item in report.items)
            block_rules = {item.rule_id: item.status.value for item in report.items}
            for rule in ("saved", "block_generated", "root", "word_count"):
                assert block_rules[rule] == CheckStatus.PASS.value, (rule, block_rules)
            for rule in ("final_build", "pdf_current"):
                assert block_rules[rule] == CheckStatus.UNKNOWN.value, (rule, block_rules)
            evidence["block_initial_rules"] = block_rules
            assert session.compile_manager is None, "Checking must not initialize a compiler"
            completed = []
            session.compile_finished.connect(completed.append)
            result = session.compile_final()
            assert result is not None and result.ok, result
            assert len(completed) == 1, "A synchronous FINAL must emit completion exactly once"
            assert result.job_key.source_revision == session._revision
            assert result.input_evidence is not None and result.input_evidence.stable, result.input_evidence
            wait_for(lambda: window.pdf_panel._document is not None and window.pdf_panel._document.pageCount() > 0)
            assert window.pdf_panel.current_logical_key == block.root
            evidence["block_pdf_pages"] = window.pdf_panel._document.pageCount()
            evidence["block_pdf_sha256"] = result.input_evidence.pdf.digest
            evidence["block_final_revision"] = result.job_key.source_revision
            evidence["block_final_notifications"] = len(completed)
            window.readiness.show()
            wait_for(lambda: not window.readiness.is_busy)
            report = window.submission_panel.report
            assert report is not None
            block_rules = {item.rule_id: item.status.value for item in report.items}
            for rule in ("saved", "block_generated", "final_build", "pdf_current", "final_log"):
                assert block_rules[rule] == CheckStatus.PASS.value, (rule, block_rules)
            evidence["block_rules"] = block_rules
            block_screens = []
            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                window.set_ui_scale(scale)
                app.processEvents()
                panel = window.submission_panel
                assert panel.isVisible()
                assert panel.report is not None, (scale, panel.summary.text())
                assert panel.width() >= window.width() * 0.7, "Check dock must not be squeezed beside diagnostics"
                for button in (panel.refresh_button, panel.cancel_button, panel.action_button):
                    assert panel.rect().contains(button.geometry()), (scale, button.text())
                name = f"block-submission-{round(scale * 100)}.png"
                assert window.grab().save(str(output / name))
                block_screens.append(name)
            evidence["block_scale_screenshots"] = block_screens
            metadata = block.root.parent / ".icstex/sources.json"
            metadata.write_bytes(block_before[metadata] + b" ")
            wait_for(lambda: window.submission_panel.report is None, seconds=8)
            evidence["block_external_metadata_invalidated"] = True
            metadata.write_bytes(block_before[metadata])
            evidence["block_original_bytes_restored"] = all(p.read_bytes() == data for p, data in block_before.items())
            assert evidence["block_original_bytes_restored"]
            # A changed generated child must not borrow the successful model revision.
            block.draft_path.write_bytes(block_before[block.draft_path] + b"\nExternal synthetic edit.\n")
            window.readiness.request()
            wait_for(lambda: not window.readiness.is_busy)
            changed = window.submission_panel.report
            assert changed is not None
            changed_rules = {item.rule_id: item.status.value for item in changed.items}
            assert changed_rules["final_build"] == CheckStatus.FAIL.value
            assert changed_rules["block_generated"] == CheckStatus.FAIL.value
            evidence["block_changed_input_rejected"] = True
            block.draft_path.write_bytes(block_before[block.draft_path])
            assert all(p.read_bytes() == data for p, data in block_before.items())
            _set_block_mode(window, False)
            assert window.bottom_tabs.indexOf(window.submission_panel) >= 0
            _close_block_project(window)
        finally:
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            window.close()
            app.processEvents()
    (output / "report.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
