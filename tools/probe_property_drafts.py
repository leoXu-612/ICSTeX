"""Native property-draft lifecycle probe; synthetic projects and isolated settings."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from app.core.blocks.assembly import build_latex_files
from app.core.blocks.project_repository import load_project, save_project
from app.core.blocks.registry import CreateBlockInput
from app.core.blocks.model import content_for_text
from app.core.blocks.layout import Size
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness
from app.core.settings import AppSettings
from app.gui.block_mode import _close_block_project, _install_session, _set_block_mode
from app.gui.blocks.project_session import ProjectSession
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tests.v1_fixtures import create_project
from tools.probe_submission_check import wait_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("ICSTeX V1 Property Draft QA")
    apply_theme(app)
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    report = {"platform": platform.platform(), "python": platform.python_version(),
              "qt_platform": app.platformName(), "app_python_tree_sha256": digest.hexdigest()}

    def choose(action, choices, label):
        remaining = list(choices)
        seen, errors = [], []
        timer = QTimer()
        def answer():
            box = app.activeModalWidget()
            if not isinstance(box, QMessageBox) or box in seen:
                return
            seen.append(box)
            if not remaining:
                errors.append("Unexpected modal: " + box.text())
                box.reject()
                return
            button = box.button(remaining.pop(0))
            if button is None:
                errors.append("Expected button missing: " + box.text())
                box.reject()
                return
            button.setFocus()
            assert box.grab().save(str(output / f"{label}-{len(seen)}.png"))
            QTest.keyClick(button, Qt.Key.Key_Space)
        timer.timeout.connect(answer)
        timer.start(30)
        try:
            result = action()
        finally:
            timer.stop()
        assert not remaining and not errors, (remaining, errors)
        return result

    with TemporaryDirectory(prefix="icstex-property-drafts-qa-") as directory:
        base = Path(directory).resolve()
        source = create_project(base, "single")
        source.root.write_bytes(b"% Synthetic source viewport\n" * 160 + source.root.read_bytes())
        source_bytes = source.root.read_bytes()
        sample = create_project(base, "block")
        state = load_project(sample.root.parent)
        state["layout"] = replace(state["layout"], gap=Size(72.27, "pt"), alignment="middle")
        first = state["registry"].blocks()[0]
        second = state["registry"].create(CreateBlockInput(type="text", alias="second", content=content_for_text("second text")))
        save_project(sample.root.parent, **{key: state[key] for key in ("registry", "layout", "sources", "document_theme")})
        for path, text in build_latex_files(sample.root.parent, **{key: state[key] for key in ("registry", "layout", "document_theme")}).items():
            path.write_text(text)
        before = {p: p.read_bytes() for p in sample.root.parent.rglob("*") if p.is_file()}
        window = MainWindow(settings_store=AppSettings(QSettings(str(base / "qa.ini"), QSettings.Format.IniFormat)))
        try:
            window.auto_compile_action.setChecked(False)
            window.project_files.set_project_root(source.root.parent)
            window.open_file(source.root)
            window.set_engine(LaTeXEngine.PDFLATEX)
            window.resize(1120, 860)
            window.show()
            window.raise_()
            window.activateWindow()
            window.compile_action.trigger()
            wait_for(lambda: window.pdf_state.record_for(source.root).freshness is PdfFreshness.CURRENT)
            source_record = window.pdf_state.record_for(source.root)
            tab = window.current_tab()
            cursor = tab.editor.textCursor()
            cursor.setPosition(1300)
            tab.editor.setTextCursor(cursor)
            tab.editor.verticalScrollBar().setValue(45)
            position, scroll = cursor.position(), tab.editor.verticalScrollBar().value()

            def open_block():
                loaded = load_project(sample.root.parent)
                session = ProjectSession(**{key: loaded[key] for key in ("registry", "layout", "sources", "document_theme", "project_dir")})
                assert _install_session(window, session)
                _set_block_mode(window, True)
                session.selection.select_block(first.id, source="native-property-qa")
                return session, window.block_inspector

            session, inspector = open_block()
            window.raise_()
            window.activateWindow()
            wait_for(lambda: app.activeWindow() is window, seconds=60)
            assert app.activeWindow() is window, app.activeWindow()
            inspector.scroll.ensureWidgetVisible(inspector.content_edit)
            inspector.content_edit.setFocus()
            assert app.focusWidget() is inspector.content_edit, (app.focusWidget(), inspector.content_edit.isEnabled(), inspector.content_edit.isVisible())
            inspector.content_edit.selectAll()
            QTest.keyClicks(inspector.content_edit, "Native property draft")
            session.selection.select_layout_node(session.layout.id, source="native-property-qa")
            assert inspector.layout_gap.value() == 25.4
            inspector.layout_alignment.setCurrentText("bottom")
            document = inspector.content_edit.document()
            session.selection.select_block(second.id, source="native-property-qa")
            session.selection.select_block(first.id, source="native-property-qa")
            assert inspector.content_edit.document() is document
            assert inspector.content_edit.toPlainText() == "Native property draft"
            inspector.refresh()
            QTest.qWait(800)
            assert session.has_unsaved_changes and len(session.editor_drafts) == 2
            assert session.compile_manager is None and session.undo_stack.count() == 0
            assert all(p.read_bytes() == data for p, data in before.items())
            report["switch_refresh_and_timer_preserve_unapplied_draft_without_io"] = True

            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                window.set_ui_scale(scale)
                window.resize(1080, 720)
                QTest.qWait(150)
                for button in (inspector.apply_button, inspector.discard_button):
                    inspector.scroll.ensureWidgetVisible(button)
                    QTest.qWait(30)
                    rect = button.rect()
                    rect.moveTopLeft(button.mapTo(inspector.scroll.viewport(), rect.topLeft()))
                    assert inspector.scroll.viewport().rect().contains(rect), (scale, rect, inspector.scroll.viewport().rect())
                assert inspector.content_edit.document() is document
                assert inspector.content_edit.toPlainText() == "Native property draft"
                assert window.grab().save(str(output / f"draft-{round(scale * 100)}.png"))
            window.readiness.show()
            wait_for(lambda: not window.readiness.is_busy and window.submission_panel.report is not None)
            rules = {item.rule_id: item.status.value for item in window.submission_panel.report.items}
            assert rules["saved"] == "fail" and rules["pdf_current"] != "pass", rules
            assert session.compile_manager is None
            report["read_only_check_rejects_unapplied_draft"] = True
            assert not choose(lambda: _close_block_project(window), [QMessageBox.StandardButton.Cancel], "close-cancel-150")
            assert inspector.content_edit.toPlainText() == "Native property draft"

            window.set_ui_scale(1.0)
            window.resize(1120, 860)
            choose(window.block_save_action.trigger, [QMessageBox.StandardButton.Save], "save-apply")
            assert session.last_save_ok and not session.editor_drafts and session.compile_manager is None
            assert session.undo_stack.count() == 1
            assert session.layout.gap == Size(72.27, "pt") and session.layout.alignment == "bottom"
            report["native_batch_apply_preserves_pt_gap"] = True
            assert load_project(sample.root.parent)["registry"].get(first.id).content["text"] == "Native property draft"
            window.block_compile_action.trigger()
            wait_for(lambda: session.last_result is not None)
            assert session.last_result.ok
            window.block_preview_area.pdf_button.click()
            QTest.qWait(300)
            assert "Native property draft" in window.pdf_panel._document.getAllText(0).text()
            assert window.grab().save(str(output / "actual-final.png"))
            final_bytes = session.last_result.pdf_file.read_bytes()
            (output / "property-final.pdf").write_bytes(final_bytes)
            report["final_sha256"] = hashlib.sha256(final_bytes).hexdigest()
            report["explicit_save_and_visible_final_match_applied_draft"] = True

            inspector.content_edit.setPlainText("Native saved on close")
            assert choose(lambda: _close_block_project(window), [QMessageBox.StandardButton.Save], "close-save-apply")
            assert load_project(sample.root.parent)["registry"].get(first.id).content["text"] == "Native saved on close"
            session, inspector = open_block()
            assert not session.save_error and session.compile_manager is None
            inspector.content_edit.setPlainText("Retained conflicting draft")
            path = sample.root.parent / ".icstex/blocks.json"
            winner = path.read_bytes() + b" \n"
            path.write_bytes(winner)
            choose(window.block_save_action.trigger, [QMessageBox.StandardButton.Save, QMessageBox.StandardButton.Ok], "external-conflict")
            assert not session.last_save_ok and path.read_bytes() == winner
            assert inspector.content_edit.toPlainText() == "Retained conflicting draft"
            assert not choose(lambda: _close_block_project(window), [QMessageBox.StandardButton.Cancel], "conflict-close-cancel")
            assert choose(lambda: _close_block_project(window), [QMessageBox.StandardButton.Discard], "conflict-close-discard")
            QTest.qWait(750)
            assert path.read_bytes() == winner
            assert window.pdf_state.record_for(source.root) == source_record
            assert tab.editor.textCursor().position() == position
            assert tab.editor.verticalScrollBar().value() == scroll
            assert source.root.read_bytes() == source_bytes
            report["close_save_reopen_conflict_and_source_view_preserved"] = True
        finally:
            if window.block_session is not None:
                _close_block_project(window, discard=True)
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            window.close()
            app.processEvents()
    report["limits"] = ["Synthetic Qt keyboard events, not real IME/AX/Windows/human acceptance",
                         "Memory drafts are not M4 process-crash recovery", "No package or installed-app change"]
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
