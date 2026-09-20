"""Native Block narrow/scale/keyboard probe with disposable synthetic projects."""
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

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.blocks.assembly import build_latex_files
from app.core.blocks.layout import Size
from app.core.blocks.project_repository import load_project, save_project
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
    app.setApplicationName("ICSTeX V1 Block Layout QA")
    apply_theme(app)
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    report = {"platform": platform.platform(), "python": platform.python_version(),
              "qt_platform": app.platformName(), "app_python_tree_sha256": digest.hexdigest()}
    with TemporaryDirectory(prefix="icstex-v1-block-layout-qa-") as directory:
        base = Path(directory).resolve()
        source = create_project(base, "single")
        source.root.write_bytes(b"% Synthetic scroll fixture\n" * 160 + source.root.read_bytes())
        source_bytes = source.root.read_bytes()
        block = create_project(base, "block")
        state = load_project(block.root.parent)
        state["layout"] = replace(state["layout"], gap=Size(12.5, "mm"), alignment="middle", fallback={"strategy": "error"})
        save_project(block.root.parent, **{key: state[key] for key in ("registry", "layout", "sources", "document_theme")})
        for path, text in build_latex_files(block.root.parent, **{key: state[key] for key in ("registry", "layout", "document_theme")}).items():
            path.write_text(text)
        original = {p: p.read_bytes() for p in block.root.parent.rglob("*") if p.is_file()}
        window = MainWindow(settings_store=AppSettings(QSettings(str(base / "qa.ini"), QSettings.Format.IniFormat)))
        session = None
        try:
            assert window in app.ui_scale_manager._windows
            window.resize(1120, 860)
            window.auto_compile_action.setChecked(False)
            window.project_files.set_project_root(source.root.parent)
            window.open_file(source.root)
            window.set_engine(LaTeXEngine.PDFLATEX)
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
            source_position = cursor.position()
            source_scroll = tab.editor.verticalScrollBar().value()

            session = ProjectSession(**{key: state[key] for key in ("registry", "layout", "sources", "document_theme", "project_dir")})
            assert _install_session(window, session)
            _set_block_mode(window, True)
            item = session.registry.blocks()[0]
            session.selection.select_block(item.id, source="native-layout-qa")
            inspector = window.block_inspector
            workspace = window.block_workspace
            area = window.block_preview_area
            identities = (id(inspector.content_edit), id(workspace.layout_panel), id(window.pdf_panel), id(window.pdf_panel._view))
            assert session.layout == state["layout"]
            assert session.undo_stack.count() == 0
            samples = []

            def reachable(scroll, button):
                scroll.ensureWidgetVisible(button)
                QTest.qWait(20)
                assert button.isVisible(), button.text()
                rect = button.rect()
                rect.moveTopLeft(button.mapTo(scroll.viewport(), button.rect().topLeft()))
                assert scroll.viewport().rect().contains(rect), (button.text(), rect, scroll.viewport().rect())
                assert button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 12, button.text()

            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                window.set_ui_scale(scale)
                for width, height in ((1080, 720), (1440, 900)):
                    window.resize(width, height)
                    area.editor_button.click()
                    QTest.qWait(180)
                    assert window.width() <= width and window.height() <= height, (scale, window.size())
                    workspace.tabs.setCurrentIndex(0)
                    scroll = workspace.tabs.widget(0)
                    assert scroll.viewport().height() >= 80, (scale, scroll.viewport().size())
                    for button in (workspace.layout_panel.row_button, workspace.layout_panel.grid_button,
                                   workspace.layout_panel.ungroup_button, workspace.layout_panel.undo_button):
                        reachable(scroll, button)
                    reachable(inspector.scroll, inspector.apply_button)
                    workspace.tabs.setCurrentIndex(1)
                    table_scroll = workspace.tabs.widget(1)
                    for button in (workspace.table_editor.undo_button, workspace.table_editor.redo_button,
                                   workspace.table_editor.paste_button, workspace.table_editor.clear_button,
                                   workspace.table_editor.insert_row_button, workspace.table_editor.delete_row_button,
                                   workspace.table_editor.insert_column_button, workspace.table_editor.delete_column_button):
                        reachable(table_scroll, button)
                    workspace.tabs.setCurrentIndex(0)
                    scroll.ensureWidgetVisible(workspace.layout_panel.row_button)
                    name = f"layout-{round(scale * 100)}-{width}.png"
                    assert window.grab().save(str(output / name))
                    samples.append({"scale": scale, "size": [width, height], "compact": area._compact,
                                    "body_height": scroll.viewport().height(), "screenshot": name})
                    assert identities == (id(inspector.content_edit), id(workspace.layout_panel), id(window.pdf_panel), id(window.pdf_panel._view))
                    assert session.layout == state["layout"] and session.undo_stack.count() == 0
                    assert all(path.read_bytes() == data for path, data in original.items())
                    assert session.compile_manager is None
            report["layout_samples"] = samples

            window.set_ui_scale(1.0)
            window.resize(1120, 860)
            area.editor_button.click()
            window.raise_()
            window.activateWindow()
            wait_for(lambda: app.activeWindow() is window, seconds=60)
            assert app.activeWindow() is window, app.activeWindow()
            window.block_nav.controller.rename_block(item.id, "keyboard_qa")
            pending = session.pause_writes()
            global_index = session.undo_stack.index()
            text_before = inspector.content_edit.toPlainText()
            inspector.scroll.ensureWidgetVisible(inspector.content_edit)
            inspector.content_edit.setFocus()
            assert app.focusWidget() is inspector.content_edit, app.focusWidget()
            inspector.content_edit.selectAll()
            QTest.keyClicks(inspector.content_edit, "Native keyboard draft")
            QTest.keyClick(inspector.content_edit, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
            assert inspector.content_edit.toPlainText() == text_before
            QTest.keyClick(inspector.content_edit, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
            assert inspector.content_edit.toPlainText() == "Native keyboard draft", inspector.content_edit.toPlainText()
            assert session.undo_stack.index() == global_index
            QTest.keyClick(inspector.content_edit, Qt.Key.Key_Tab)
            assert inspector.content_edit.toPlainText() == "Native keyboard draft\t"
            QTest.keyClick(inspector.content_edit, Qt.Key.Key_Backspace)
            assert inspector.content_edit.toPlainText() == "Native keyboard draft"
            QTest.keyClick(inspector.content_edit, Qt.Key.Key_Tab, Qt.KeyboardModifier.MetaModifier)
            QTest.qWait(80)
            assert app.focusWidget() is inspector.apply_button, (app.focusWidget(), app.activeWindow(), inspector.apply_button.isVisible())
            QTest.keyClick(inspector.apply_button, Qt.Key.Key_Space)
            assert session.registry.get(item.id).content["text"] == "Native keyboard draft"
            assert session.undo_stack.index() == global_index + 1
            window.block_undo_action.trigger()
            assert session.registry.get(item.id).content["text"] == text_before
            window.block_redo_action.trigger()
            assert session.registry.get(item.id).content["text"] == "Native keyboard draft"
            session.resume_writes(pending)
            window.block_save_action.trigger()
            assert session.last_save_ok, session.save_error
            assert session.compile_manager is None
            report["local_text_undo_redo_and_one_global_apply"] = True

            window.block_compile_action.trigger()
            wait_for(lambda: session.last_result is not None)
            assert session.last_result.ok
            area.pdf_button.click()
            QTest.qWait(500)
            assert window.pdf_panel._view.isVisible()
            assert "Native keyboard draft" in window.pdf_panel._document.getAllText(0).text()
            window.pdf_panel.zoom_by(1.2)
            QTest.qWait(100)
            zoom = window.pdf_panel._view.zoomFactor()
            document = window.pdf_panel._document
            for _ in range(3):
                area.editor_button.click()
                area.pdf_button.click()
                QTest.qWait(30)
            assert window.pdf_panel._document is document
            assert window.pdf_panel._view.zoomFactor() == zoom
            assert window.grab().save(str(output / "final-pdf.png"))
            report["actual_final_and_pdf_toggle_view_preserved"] = True
            _close_block_project(window)
            QTest.qWait(200)
            assert window.pdf_panel.current_pdf == source_record.last_successful_pdf
            assert tab.editor.textCursor().position() == source_position
            assert tab.editor.verticalScrollBar().value() == source_scroll
            assert source.root.read_bytes() == source_bytes
            report["source_cursor_scroll_pdf_and_bytes_preserved"] = True
            report["limits"] = ["Synthetic Qt keyboard events, not system IME or human acceptance",
                "No AX/Windows/installation acceptance", "Unapplied inspector draft lifecycle still requires acceptance"]
        finally:
            if session is not None:
                session.shutdown()
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            window.close()
            app.processEvents()
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
