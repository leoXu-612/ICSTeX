"""Native local profile edit/check verification using disposable synthetic files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QScrollArea

from app.core.project_profile import PROFILE_PATH, ProjectProfile, load_profile, save_profile
from app.core.settings import AppSettings
from app.core.submission_check import CheckStatus
from app.core.pdf_state import PdfFreshness
from app.gui.main_window import MainWindow
from app.gui.project_profile_dialog import ProjectProfileDialog
from app.gui.theme import apply_theme
from tests.v1_fixtures import create_project
from tools.probe_submission_check import wait_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("ICSTeX V1 Profile QA")
    apply_theme(app)
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    evidence = {"platform": platform.platform(), "python": platform.python_version(),
                "qt_platform": app.platformName(), "app_python_tree_sha256": digest.hexdigest(),
                "scope": "Synthetic native source window; no installed application or student data"}
    with TemporaryDirectory(prefix="icstex-v1-profile-qa-") as directory:
        base = Path(directory).resolve()
        sample = create_project(base)
        root = sample.root.parent
        originals = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        settings = AppSettings(QSettings(str(base / "qa.ini"), QSettings.Format.IniFormat))
        window = MainWindow(settings_store=settings)
        try:
            window.auto_compile_action.setChecked(False)
            window.project_files.set_project_root(root)
            window.open_file(sample.root)
            window.resize(1100, 820)
            window.show()
            window.raise_()
            window.activateWindow()
            wait_for(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy)
            window.compile_action.trigger()
            wait_for(lambda: window.pdf_state.record_for(sample.root).freshness == PdfFreshness.CURRENT)
            wait_for(lambda: window.pdf_panel._document is not None and window.pdf_panel._document.pageCount() > 0)
            final = window.pdf_state.record_for(sample.root)
            pdf = final.last_successful_pdf
            pdf_before = pdf.read_bytes()
            editor = window.current_tab().editor
            cursor_before = editor.textCursor().position()
            scroll_before = editor.verticalScrollBar().value()
            window.readiness.show()
            wait_for(lambda: not window.readiness.is_busy)
            assert window.submission_panel.report is not None

            cancelled = ProjectProfileDialog(root, window)
            cancelled.show()
            cancelled.word_max.setFocus()
            QTest.keyClicks(cancelled.word_max, "99")
            QTest.keyClick(cancelled, Qt.Key.Key_Escape)
            app.processEvents()
            assert not (root / PROFILE_PATH).exists()
            evidence["keyboard_cancel_zero_write"] = True

            dialog = ProjectProfileDialog(root, window)
            dialog.show()
            dialog.word_max.setFocus()
            QTest.keyClicks(dialog.word_max, "5")
            screenshots = []
            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                window.set_ui_scale(scale)
                app.processEvents()
                for kind in (QDialogButtonBox.StandardButton.Save, QDialogButtonBox.StandardButton.Cancel):
                    button = dialog.buttons.button(kind)
                    assert button.isVisible() and dialog.rect().contains(button.mapTo(dialog, button.rect().center()))
                name = f"profile-{round(scale * 100)}.png"
                assert dialog.grab().save(str(output / name))
                screenshots.append(name)
            dialog.findChild(QScrollArea).ensureWidgetVisible(dialog.references)
            app.processEvents()
            assert dialog.grab().save(str(output / "profile-150-lower-fields.png"))
            save = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
            save.setFocus()
            QTest.keyClick(save, Qt.Key.Key_Space)
            app.processEvents()
            assert dialog.saved_snapshot is not None, dialog.error.text()
            assert load_profile(root).profile.word_max == 5
            wait_for(lambda: window.submission_panel.report is None)
            window.readiness.request()
            wait_for(lambda: not window.readiness.is_busy)
            report = window.submission_panel.report
            assert report is not None
            statuses = {item.rule_id: item.status.value for item in report.items}
            assert statuses["word_target"] == CheckStatus.FAIL.value
            assert statuses["final_build"] == CheckStatus.PASS.value
            evidence["profile_rules"] = statuses
            evidence["actual_profile_event_invalidated"] = True
            evidence["scale_screenshots"] = screenshots
            target_index = next(n for n, item in enumerate(report.items) if item.rule_id == "word_target")
            window.submission_panel.tree.setCurrentItem(window.submission_panel.tree.topLevelItem(target_index))
            window.vertical_splitter.setSizes([400, 360])
            app.processEvents()
            assert window.grab().save(str(output / "profile-check.png"))

            conflict = ProjectProfileDialog(root, window)
            conflict.show()
            conflict.word_max.setText("999")
            snapshot = load_profile(root)
            save_profile(root, ProjectProfile(word_max=42), expected=snapshot)
            conflict.accept()
            assert conflict.saved_snapshot is None
            assert conflict.word_max.text() == "999" and load_profile(root).profile.word_max == 42
            conflict.findChild(QScrollArea).ensureWidgetVisible(conflict.word_max)
            app.processEvents()
            assert conflict.grab().save(str(output / "profile-conflict.png"))
            conflict.reject()
            evidence["conflict_preserves_draft_and_external_file"] = True
            disabled = ProjectProfileDialog(root, window)
            disabled.enabled.setChecked(False)
            disabled.accept()
            window.readiness.invalidate()
            window.readiness.request()
            wait_for(lambda: not window.readiness.is_busy)
            report = window.submission_panel.report
            assert next(i for i in report.items if i.rule_id == "word_target").status == CheckStatus.NOT_APPLICABLE
            assert all(path.read_bytes() == content for path, content in originals.items())
            assert pdf.read_bytes() == pdf_before
            assert window.pdf_state.record_for(sample.root).latest_build_id == final.latest_build_id
            assert editor.textCursor().position() == cursor_before
            assert editor.verticalScrollBar().value() == scroll_before
            evidence["source_bytes_and_final_build_unchanged"] = True
            evidence["cursor_scroll_unchanged"] = True
            evidence["pdf_pages"] = window.pdf_panel._document.pageCount()
            evidence["limits"] = ["Not IME or human usability evidence", "Windows not run", "Full M2 workspace and onboarding pending"]
        finally:
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            window.close()
            app.processEvents()
    (output / "report.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
