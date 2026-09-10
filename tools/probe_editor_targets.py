"""Native multi-table/formula target probe; disposable synthetic projects only."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox
from app.core.blocks.assembly import build_latex_files
from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.blocks.layout import block_slot
from app.core.blocks.project_repository import load_project, save_project
from app.core.blocks.registry import CreateBlockInput
from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness
from app.core.settings import AppSettings
from app.gui.block_mode import _close_block_project, _install_session, _set_block_mode
from app.gui.blocks.project_session import ProjectSession
from app.gui.formula_dialog import FormulaDialog
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
    app.setApplicationName("ICSTeX V1 Editor Target QA")
    apply_theme(app)
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    report = {"platform": platform.platform(), "python": platform.python_version(),
              "qt_platform": app.platformName(), "app_python_tree_sha256": digest.hexdigest()}

    def modal_action(action, choices, label, formula_text=None, cancel_formula=False, interleave=None):
        remaining, seen, errors = list(choices), [], []
        formula_seen = []
        deadline = time.monotonic() + 30
        timer = QTimer()

        def answer():
            modal = app.activeModalWidget()
            if modal is None or modal in seen:
                return
            seen.append(modal)
            try:
                assert time.monotonic() < deadline, "Modal driver timed out"
                if isinstance(modal, FormulaDialog):
                    formula_seen.append(modal)
                    assert len(formula_seen) == 1 and formula_text is not None
                    modal.source_mode_check.setChecked(True)
                    modal.source_edit.setFocus()
                    modal.source_edit.selectAll()
                    QTest.keyClicks(modal.source_edit, formula_text)
                    assert modal.grab().save(str(output / f"{label}-formula.png"))
                    if interleave is not None:
                        interleave()
                    if cancel_formula:
                        QTest.keyClick(modal.source_edit, Qt.Key.Key_Escape)
                    else:
                        assert modal._ok_button.isEnabled()
                        modal._ok_button.setFocus()
                        QTest.keyClick(modal._ok_button, Qt.Key.Key_Space)
                else:
                    assert isinstance(modal, QMessageBox), type(modal)
                    assert remaining, "Unexpected modal: " + modal.text()
                    button = modal.button(remaining.pop(0))
                    assert button is not None, modal.text()
                    assert modal.grab().save(str(output / f"{label}-{len(seen)}.png"))
                    button.setFocus()
                    QTest.keyClick(button, Qt.Key.Key_Space)
            except Exception as error:
                errors.append(str(error))
                modal.reject()

        timer.timeout.connect(answer)
        timer.start(30)
        try:
            result = action()
        finally:
            timer.stop()
        assert not remaining and not errors, (remaining, errors)
        assert formula_text is None or formula_seen
        return result

    with TemporaryDirectory(prefix="icstex-editor-targets-qa-") as directory:
        base = Path(directory).resolve()
        source = create_project(base, "single")
        source.root.write_bytes(b"% Synthetic source viewport\n" * 160 + source.root.read_bytes())
        source_bytes = source.root.read_bytes()
        sample = create_project(base, "block")
        state = load_project(sample.root.parent)
        registry = state["registry"]
        for alias in ("Table Alpha", "Table Beta"):
            data = TableData(columns=[ColumnSpec(id="value", name="Value"),
                                      ColumnSpec(id="flag", name="Flag", dataType="boolean")],
                rows=[TableRow(id="row", cells={"value": Cell("text", alias),
                                                "flag": Cell("boolean", False)})], header_row_count=0)
            content = data.to_content_dict()
            content["rows"][0]["opaque"] = {"preserve": "row metadata"}
            registry.create(CreateBlockInput(type="table", alias=alias, content=content))
        first, second = [block for block in registry.blocks() if block.type == "table"]
        formula = registry.create(CreateBlockInput(type="formula", alias="Formula",
            content=FormulaBlockAdapter().content_for("x+1")))
        state["layout"] = replace(state["layout"], children=tuple(block_slot(b.id) for b in (first, second, formula)))
        save_project(sample.root.parent, **{key: state[key] for key in ("registry", "layout", "sources", "document_theme")})
        for path, text in build_latex_files(sample.root.parent, **{key: state[key] for key in ("registry", "layout", "document_theme")}).items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
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
                return session, window.block_inspector, window.block_workspace

            session, inspector, workspace = open_block()

            def open_table(block):
                session.selection.select_block(block.id, source="native-editor-target-qa")
                inspector.table_button.click()
                assert session.table_target_id == block.id

            def cell_input(text, commit=True):
                window.block_preview_area.editor_button.click()
                workspace.tabs.setCurrentIndex(1)
                grid = workspace.table_editor.table
                workspace.tabs.widget(1).ensureWidgetVisible(grid)
                grid.setFocus()
                grid.setCurrentCell(0, 0)
                grid.editItem(grid.item(0, 0))
                QTest.qWait(30)
                editor = app.focusWidget()
                assert isinstance(editor, QLineEdit), (editor, grid.isVisible())
                editor.selectAll()
                QTest.keyClicks(editor, text)
                assert session.has_unsaved_changes
                if commit:
                    QTest.keyClick(editor, Qt.Key.Key_Return)
                return editor

            def value(block):
                return session.registry.get(block.id).content["rows"][0]["cells"]["value"]["value"]

            window.raise_()
            window.activateWindow()
            assert window.grab().save(str(output / "before-native-focus.png"))
            # Allow a real desktop click to activate a terminal-launched Cocoa
            # window. Do not fabricate active/focus state with setActiveWindow.
            wait_for(lambda: app.activeWindow() is window, seconds=60)
            assert app.activeWindow() is window, app.activeWindow()
            open_table(first)
            cell_input("First intended", commit=False)
            assert ("table_cell", first.id) in session.editor_drafts
            assert value(first) == first.alias
            open_table(second)
            assert workspace.table_editor.table.item(0, 0).text() == second.alias
            cell_input("Second intended")
            open_table(first)
            assert workspace.table_editor.table.item(0, 0).text() == "First intended"
            workspace.table_editor.undo_button.click()
            assert workspace.table_editor.table.item(0, 0).text() == first.alias
            workspace.table_editor.redo_button.click()
            assert workspace.table_editor.table.item(0, 0).text() == "First intended"
            assert session.undo_stack.count() == 0 and len(session.editor_drafts) == 2
            QTest.qWait(800)
            assert session.compile_manager is None
            assert all(p.read_bytes() == data for p, data in before.items())
            report["two_tables_live_cell_switch_local_undo_no_model_or_io"] = True

            for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                window.set_ui_scale(scale)
                window.resize(1080, 720)
                QTest.qWait(150)
                area = workspace.tabs.widget(1)
                for button in (workspace.table_apply_button, workspace.table_discard_button):
                    area.ensureWidgetVisible(button)
                    QTest.qWait(30)
                    rect = button.rect()
                    rect.moveTopLeft(button.mapTo(area.viewport(), rect.topLeft()))
                    assert area.viewport().rect().contains(rect), (scale, rect)
                assert workspace.table_editor.table.item(0, 0).text() == "First intended"
                assert window.grab().save(str(output / f"table-{round(scale * 100)}.png"))
            report["five_scales_table_draft_actions_reachable"] = True
            window.readiness.show()
            wait_for(lambda: not window.readiness.is_busy and window.submission_panel.report is not None)
            rules = {item.rule_id: item.status.value for item in window.submission_panel.report.items}
            assert rules["saved"] == "fail" and rules["pdf_current"] != "pass", rules
            assert session.compile_manager is None
            assert not modal_action(lambda: _close_block_project(window), [QMessageBox.StandardButton.Cancel], "table-close-cancel")
            assert len(session.editor_drafts) == 2
            window.set_ui_scale(1.0)
            window.resize(1120, 860)
            modal_action(window.block_save_action.trigger, [QMessageBox.StandardButton.Save], "save-two-tables")
            assert session.last_save_ok and not session.editor_drafts and session.compile_manager is None
            assert session.undo_stack.count() == 1
            assert value(first) == "First intended" and value(second) == "Second intended"
            saved = load_project(sample.root.parent)["registry"]
            for block, text in ((first, "First intended"), (second, "Second intended")):
                row = saved.get(block.id).content["rows"][0]
                assert row["cells"]["value"]["value"] == text
                assert row["cells"]["flag"]["value"] is False
                assert row["opaque"] == {"preserve": "row metadata"}
            report["explicit_save_batches_correct_targets_with_false_and_opaque_fields"] = True

            session.selection.select_block(formula.id, source="native-editor-target-qa")
            original = deepcopy(session.registry.get(formula.id).to_dict())
            modal_action(inspector.formula_button.click, [], "formula-cancel", r"\(x+8\)", True)
            assert session.registry.get(formula.id).to_dict() == original
            modal_action(inspector.formula_button.click, [], "formula-accept", r"\(x+4\)")
            assert session.registry.get(formula.id).content["latexCache"] == "x+4"
            assert session.undo_stack.count() == 2
            open_table(second)
            session.undo_stack.undo()
            assert session.registry.get(formula.id).content["latexCache"] == "x+1"
            session.undo_stack.redo()
            assert value(first) == "First intended" and value(second) == "Second intended"
            report["real_formula_cancel_apply_and_global_undo_target_owned"] = True
            window.block_save_action.trigger()
            assert session.last_save_ok
            window.block_compile_action.trigger()
            wait_for(lambda: session.last_result is not None)
            assert session.last_result.ok, session.last_result
            window.block_preview_area.pdf_button.click()
            QTest.qWait(300)
            pdf_text = " ".join(window.pdf_panel._document.getAllText(0).text().split())
            assert "First intended" in pdf_text and "Second intended" in pdf_text, pdf_text
            assert "x+4" in pdf_text.replace(" ", ""), pdf_text
            assert window.grab().save(str(output / "actual-final.png"))
            final_bytes = session.last_result.pdf_file.read_bytes()
            (output / "editor-targets-final.pdf").write_bytes(final_bytes)
            report["final_sha256"] = hashlib.sha256(final_bytes).hexdigest()
            report["visible_final_contains_two_intended_tables_and_formula"] = True
            assert _close_block_project(window)
            session, inspector, workspace = open_block()
            assert session.compile_manager is None and not session.has_unsaved_changes
            assert value(first) == "First intended" and value(second) == "Second intended"

            session.selection.select_block(formula.id, source="native-editor-target-qa")
            def external_model_change():
                session.registry.update(formula.id, {"content": FormulaBlockAdapter().content_for("x+7")})
                session.notify_model_changed("simulated-other-formula-editor")
            modal_action(inspector.formula_button.click, [QMessageBox.StandardButton.Ok], "formula-conflict",
                         r"\(x+9\)", interleave=external_model_change)
            assert session.registry.get(formula.id).content["latexCache"] == "x+7"
            key = ("formula", formula.id)
            assert session.editor_drafts[key].values["latexCache"] == "x+9"
            assert session.undo_stack.count() == 0
            index = next(i for i in range(inspector.draft_list.count()) if inspector.draft_list.itemData(i) == key)
            inspector.draft_list.setCurrentIndex(index)
            inspector.draft_list.activated.emit(index)
            inspector.refresh()
            assert inspector.draft_list.currentData() == key and inspector.formula_info.text() == "x+9"
            modal_action(inspector.pending_discard_button.click, [QMessageBox.StandardButton.Cancel], "draft-discard-cancel")
            assert key in session.editor_drafts
            assert not modal_action(lambda: _close_block_project(window), [QMessageBox.StandardButton.Cancel], "formula-close-cancel")
            assert modal_action(lambda: _close_block_project(window), [QMessageBox.StandardButton.Discard], "formula-close-discard")
            report["simulated_formula_interleaving_retains_both_versions_and_cancel"] = True

            session, inspector, workspace = open_block()
            open_table(second)
            cell_input("Conflicting table draft")
            path = sample.root.parent / ".icstex/blocks.json"
            winner = path.read_bytes() + b" \n"
            path.write_bytes(winner)
            modal_action(window.block_save_action.trigger, [QMessageBox.StandardButton.Save, QMessageBox.StandardButton.Ok], "external-conflict")
            assert not session.last_save_ok and path.read_bytes() == winner
            assert value(second) == "Conflicting table draft" and value(first) == "First intended"
            assert not modal_action(lambda: _close_block_project(window), [QMessageBox.StandardButton.Cancel], "conflict-close-cancel")
            assert modal_action(lambda: _close_block_project(window), [QMessageBox.StandardButton.Discard], "conflict-close-discard")
            QTest.qWait(750)
            assert path.read_bytes() == winner
            assert window.pdf_state.record_for(source.root) == source_record
            assert tab.editor.textCursor().position() == position
            assert tab.editor.verticalScrollBar().value() == scroll
            assert source.root.read_bytes() == source_bytes
            report["external_metadata_conflict_and_source_pdf_view_preserved"] = True
        finally:
            if window.block_session is not None:
                _close_block_project(window, discard=True)
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    report["limits"] = ["Synthetic Qt keyboard events, not IME/AX/Windows/human acceptance",
        "Formula conflict is deliberate model interleaving, not proof of concurrent user behavior",
        "Pending-draft selection used the existing controller signal, not native popup keyboard acceptance",
        "Image picker and asset-copy safety are not covered by this native probe",
        "Memory drafts are not M4 crash recovery; no package or installed-app change"]
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
