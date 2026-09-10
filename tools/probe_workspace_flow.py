"""Native synthetic create / FINAL / check / PDF export / reopen workflow.

No installed app, student files or external release operation. The PDF chooser
uses an explicit temporary destination; it is not human file-dialog evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from app.core.pdf_state import PdfFreshness
from app.core.settings import AppSettings
from app.core.submission_check import CheckStatus
from app.gui.main_window import MainWindow
from app.gui.project_panels import ProjectWizardDialog
from app.gui.theme import apply_theme
from tools.probe_submission_check import wait_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("ICSTeX V1 Workspace QA")
    apply_theme(app)
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    evidence = {"platform": platform.platform(), "python": platform.python_version(),
                "qt_platform": app.platformName(), "app_python_tree_sha256": digest.hexdigest()}
    with TemporaryDirectory(prefix="icstex-v1-workspace-qa-") as directory:
        base = Path(directory).resolve()
        settings = AppSettings(QSettings(str(base / "qa.ini"), QSettings.Format.IniFormat))
        window = MainWindow(settings_store=settings)
        second = None
        errors = []
        try:
            window.auto_compile_action.setChecked(False)
            window.resize(1120, 860)
            window.show()
            window.raise_()
            window.activateWindow()
            def create():
                dialog = app.activeModalWidget()
                try:
                    assert isinstance(dialog, ProjectWizardDialog)
                    dialog.parent_edit.setText(str(base))
                    dialog.name_edit.setText("\u4e2d\u6587 \u65b0\u9879\u76ee")
                    dialog.template_combo.setCurrentIndex(dialog.template_combo.findData("chinese_xelatex_article"))
                    dialog.open_new_window.setChecked(False)
                    app.processEvents()
                    assert dialog.grab().save(str(output / "create-project.png"))
                    for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                        window.set_ui_scale(scale)
                        QTest.qWait(120)
                        assert dialog.grab().save(str(output / f"create-project-{round(scale * 100)}.png"))
                    window.set_ui_scale(1.0)
                    button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
                    button.setFocus()
                    QTest.keyClick(button, Qt.Key.Key_Space)
                    assert dialog.created_project is not None, dialog.error.text()
                except BaseException as exc:
                    errors.append(str(exc))
                    if dialog:
                        dialog.reject()
            QTimer.singleShot(200, create)
            window.new_project_action.trigger()
            assert not errors, errors
            tab = window.current_tab()
            assert tab is not None and tab.path is not None
            root = tab.path
            evidence["project_name"] = root.parent.name
            originals = {p: p.read_bytes() for p in root.parent.rglob("*") if p.is_file()}
            assert not window.compile_authorized_roots
            assert window.pdf_state.record_for(root).freshness is PdfFreshness.UNCOMPILED
            evidence["creation_did_not_compile"] = True
            window.workspace.refresh()
            evidence["initial_summary"] = window.workspace.details.full_text
            window.compile_action.trigger()
            wait_for(lambda: window.pdf_state.record_for(root).freshness in {
                PdfFreshness.CURRENT, PdfFreshness.FAILED_NO_PDF, PdfFreshness.FAILED_STALE})
            record = window.pdf_state.record_for(root)
            assert record.freshness is PdfFreshness.CURRENT, window.log_view.toPlainText()[-6000:]
            wait_for(lambda: window.pdf_panel._document is not None and window.pdf_panel._document.pageCount() > 0)
            window.workspace.refresh()
            assert window.workspace.next_button.defaultAction() is window.submission_check_action
            window.workspace.next_button.click()
            wait_for(lambda: not window.readiness.is_busy)
            report = window.submission_panel.report
            assert report is not None, window.submission_panel.summary.text()
            rules = {item.rule_id: item.status.value for item in report.items}
            for rule in ("saved", "root", "toolchain", "final_build", "pdf_current", "final_log"):
                assert rules[rule] == CheckStatus.PASS.value, (rule, rules)
            evidence["rules"] = rules
            window.workspace.refresh()
            assert window.workspace.next_button.defaultAction() is window.export_pdf_action
            exported = base / "verified-final.pdf"
            with patch("app.gui.main_window.QFileDialog.getSaveFileName", return_value=(str(exported), "PDF (*.pdf)")):
                window.workspace.next_button.click()
            wait_for(exported.is_file)
            assert exported.read_bytes() == record.last_successful_pdf.read_bytes()
            assert all(path.read_bytes() == payload for path, payload in originals.items())
            evidence["export_sha256"] = hashlib.sha256(exported.read_bytes()).hexdigest()
            evidence["pdf_pages"] = window.pdf_panel._document.pageCount()
            evidence["source_bytes_unchanged"] = True
            screenshots = []
            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                window.set_ui_scale(scale)
                QTest.qWait(200)
                bar = window.workspace.bar
                for button in (window.workspace.next_button, window.workspace.navigation):
                    assert bar.rect().contains(button.mapTo(bar, button.rect().center()))
                name = f"workspace-{round(scale * 100)}.png"
                assert window.grab().save(str(output / name))
                screenshots.append(name)
            evidence["scale_screenshots"] = screenshots
            second = window.spawn_window()
            second.project_files.set_project_root(root.parent)
            second.open_file(root)
            assert second.current_tab().editor.toPlainText() == root.read_text()
            assert not second.compile_authorized_roots
            evidence["reopen_did_not_compile"] = True
            from app.core.blocks.project_repository import load_project
            from app.gui.blocks.project_session import ProjectSession
            from app.gui.block_mode import _close_block_project, _install_session, _set_block_mode
            from tests.v1_fixtures import create_project
            block = create_project(base, "block")
            block_before = {p: p.read_bytes() for p in block.root.parent.rglob("*") if p.is_file()}
            loaded = load_project(block.root.parent)
            session = ProjectSession(**{key: loaded[key] for key in
                                     ("registry", "layout", "sources", "document_theme", "project_dir")})
            window.set_ui_scale(1.0)
            _install_session(window, session)
            _set_block_mode(window, True)
            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                window.set_ui_scale(scale)
                QTest.qWait(150)
                window.workspace.refresh()
                assert window.engine_selector.isHidden()
                assert "XeLaTeX" in window.workspace.details.full_text
                assert window.workspace.next_button.defaultAction() is window.block_compile_action
                assert session.compile_manager is None
                assert window.grab().save(str(output / f"block-workspace-{round(scale * 100)}.png"))
            assert block_before == {p: p.read_bytes() for p in block_before}
            _close_block_project(window)
            QTest.qWait(200)
            assert window.block_session is None
            assert not window.engine_selector.isHidden()
            assert window.save_action.isEnabled() and window.compile_action.isEnabled()
            assert window.pdf_panel.current_pdf == record.last_successful_pdf
            assert all(path.read_bytes() == payload for path, payload in originals.items())
            evidence["block_header_no_compile_or_write"] = True
            evidence["clean_block_close_restores_source_controls_and_final"] = True
            evidence["limits"] = ["M4 recovery not implemented here", "Block layout/close workflow pending", "Not IME/AX/Windows/human evidence"]
        finally:
            for item in (second, window):
                if item is not None:
                    for tab in item.tabs.values():
                        item.documents.cancel_save_timer(tab)
                        tab.modified = tab.dirty = False
                    item.close()
            app.processEvents()
    (output / "report.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
