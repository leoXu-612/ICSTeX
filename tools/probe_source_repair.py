"""Disposable source-repair UI, one Undo, saved reopen and actual Block FINAL.

Uses actual modal dialogs and worker reads; no source-repair methods are mocked.
Only synthetic data under a fresh --output directory is modified.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QEvent, QPoint, QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox, QScrollArea
from app.core.blocks.layout import LayoutNode, block_slot
from app.core.blocks.model import Provenance
from app.core.blocks.project_repository import load_project
from app.core.blocks.property_draft import PropertyDraft, table_projection
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.source_registry import SourceRecord
from app.core.blocks.table_import import read_csv_text
from app.core.settings import AppSettings
from app.gui.block_mode import _install_session, _set_block_mode
from app.gui.blocks.merge_dialog import MergeDialog
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.source_repair_dialog import SourceTableMappingDialog, SourceVersionDialog
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from tools.probe_submission_check import wait_for


def drive_repair(application, window, output, *, cancel_final=False, mutate_final=None):
    """Operate the real navigation button and subsequent modal widgets."""
    seen, errors, captures = set(), [], []
    started = time.monotonic()
    timer = QTimer()
    timer.setInterval(15)

    def click(button):
        if not button.isEnabled():
            raise AssertionError(f"Control disabled: {button.text()}")
        QTimer.singleShot(0, lambda: QTest.mouseClick(button, Qt.MouseButton.LeftButton,
                                                   pos=QPoint(10, button.height() // 2)))

    def step():
        dialog = application.activeModalWidget()
        if dialog is None:
            return
        try:
            if time.monotonic() - started > 30:
                raise AssertionError("Repair workflow exceeded probe deadline")
            if isinstance(dialog, QMessageBox):
                errors.append(dialog.text())
                dialog.accept()
            elif isinstance(dialog, SourceVersionDialog) and (id(dialog), "version") not in seen:
                seen.add((id(dialog), "version"))
                QTest.keyClicks(dialog.baseline_path, "base.csv")
                click(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok))
            elif isinstance(dialog, SourceTableMappingDialog):
                if (id(dialog), "load") not in seen:
                    seen.add((id(dialog), "load"))
                    scroll = dialog.findChild(QScrollArea)
                    scroll.ensureWidgetVisible(dialog.load_button)
                    click(dialog.load_button)
                elif dialog.parsed is not None and (id(dialog), "mapping") not in seen:
                    seen.add((id(dialog), "mapping"))
                    for row, column in enumerate(dialog.local.columns):
                        for side in (1, 2):
                            combo = dialog.mapping.cellWidget(row, side)
                            dialog.findChild(QScrollArea).ensureWidgetVisible(combo)
                            combo.setFocus()
                            QTest.keyClick(combo, Qt.Key.Key_Home)
                            for _ in range(combo.findData(column.id)):
                                QTest.keyClick(combo, Qt.Key.Key_Down)
                            assert combo.currentData() == column.id
                    dialog.findChild(QScrollArea).ensureWidgetVisible(dialog.mapping)
                    application.processEvents()
                    path = output / f"mapping-{len(captures)}.png"
                    assert dialog.grab().save(str(path))
                    captures.append(path.name)
                    click(dialog.preview_button)
            elif isinstance(dialog, MergeDialog) and (id(dialog), "merge") not in seen:
                seen.add((id(dialog), "merge"))
                # Explicitly retain the local conflicting value; remote-only B
                # should still update. Both targets must pass their own preview.
                dialog.preview_button.click()
                assert dialog._candidate is not None
                path = output / f"candidate-{len(captures)}.png"
                assert dialog.grab().save(str(path))
                captures.append(path.name)
                click(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok))
            elif dialog.windowTitle().startswith("最终确认") and (id(dialog), "final") not in seen:
                seen.add((id(dialog), "final"))
                assert dialog.grab().save(str(output / "final-confirmation.png"))
                if mutate_final:
                    mutate_final()
                button = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel
                                                                  if cancel_final else QDialogButtonBox.StandardButton.Ok)
                click(button)
        except Exception as exc:
            errors.append(repr(exc))
            dialog.reject()

    timer.timeout.connect(step)
    timer.start()
    nav = window.block_nav
    nav.tabs.setCurrentIndex(2)
    nav.sources_table.selectRow(0)
    try:
        nav.repair_source_button.click()
    finally:
        timer.stop()
    return {"errors": errors, "captures": captures, "elapsed_ms": round((time.monotonic() - started) * 1000, 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    report = {"app_python_tree_sha256": digest.hexdigest(), "platform": platform.platform(),
              "python": platform.python_version(), "qt_platform": app.platformName()}
    project = output / "synthetic-project"
    project.mkdir()
    original = b"Key,Value,Note\nA,10,original\nB,20,second\n"
    current = b"Key,Value,Note\nA,11,original\nB,21,second\n"
    (project / "base.csv").write_bytes(original)
    (project / "data.csv").write_bytes(current)
    record = SourceRecord("synthetic_source", "csv", "data.csv", hashlib.sha256(original).hexdigest())
    registry = BlockRegistry()
    tables = [registry.create(CreateBlockInput(type="table", alias=f"Synthetic table {i + 1}",
              provenance=Provenance("imported", record.sourceId), content=read_csv_text(original.decode()).to_content_dict()))
              for i in range(2)]
    layout = LayoutNode(id="lyt_column", kind="column", children=tuple(block_slot(block.id) for block in tables))
    session = ProjectSession(registry=registry, layout=layout, sources=[record], project_dir=project)
    session.save_now()
    assert session.last_save_ok, session.save_error
    first = tables[0]
    initial = table_projection(first.content)
    values = deepcopy(initial)
    values["rows"][1]["cells"]["col_2"]["value"] = 12
    session.set_editor_draft(PropertyDraft("table", first.id, first.alias, deepcopy(first.to_dict()), initial, values))
    original_models = {block.id: deepcopy(block.content) for block in tables}
    original_files = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    window = MainWindow(settings_store=AppSettings(QSettings(str(output / "qa.ini"), QSettings.Format.IniFormat)))
    try:
        window.auto_compile_action.setChecked(False)
        assert _install_session(window, session)
        _set_block_mode(window, True)
        window.resize(1200, 850)
        window.show()
        app.processEvents()
        cancelled_dir = output / "cancelled"
        cancelled_dir.mkdir()
        report["cancel"] = drive_repair(app, window, cancelled_dir, cancel_final=True)
        assert not report["cancel"]["errors"], report["cancel"]
        assert session.undo_stack.count() == 0
        assert {block.id: block.content for block in tables} == original_models
        assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == original_files
        assert session.editor_drafts[("table", first.id)].values == values
        conflict_dir = output / "external-conflict"
        conflict_dir.mkdir()
        report["external_conflict"] = drive_repair(app, window, conflict_dir,
            mutate_final=lambda: (project / "data.csv").write_bytes(current.replace(b"21", b"22")))
        assert report["external_conflict"]["errors"], report["external_conflict"]
        assert session.undo_stack.count() == 0
        assert {block.id: block.content for block in tables} == original_models
        (project / "data.csv").write_bytes(current)
        applied_dir = output / "applied"
        applied_dir.mkdir()
        report["apply"] = drive_repair(app, window, applied_dir)
        assert not report["apply"]["errors"], report["apply"]
        assert session.undo_stack.count() == 1
        assert session.sources[0].baseSha256 == hashlib.sha256(current).hexdigest()
        assert not session.editor_drafts
        assert tables[0].content["rows"][1]["cells"]["col_2"]["value"] == 12
        assert tables[1].content["rows"][1]["cells"]["col_2"]["value"] == 11
        assert all(b.content["rows"][2]["cells"]["col_2"]["value"] == 21 for b in tables)
        session.undo_stack.undo()
        assert {b.id: b.content for b in tables} == original_models
        assert session.sources == [record]
        assert session.editor_drafts[("table", first.id)].values == values
        session.undo_stack.redo()
        session.save_now()
        assert session.last_save_ok, session.save_error
        saved = load_project(project)
        assert saved["sources"] == session.sources
        assert {b.id: b.content for b in saved["registry"].blocks()} == {b.id: b.content for b in tables}
        assert not session._compile_authorized and session.compile_manager is None
        session.request_final()
        wait_for(lambda: session.final_evidence is not None and not session.final_is_running)
        wait_for(lambda: window.pdf_panel._document is not None and window.pdf_panel._document.pageCount() > 0)
        assert session.last_result.ok, session.last_result
        pdf = session.final_evidence.pdf_file.read_bytes()
        (output / "source-repair-final.pdf").write_bytes(pdf)
        report["final_pdf_sha256"] = hashlib.sha256(pdf).hexdigest()
        report["final_pdf_pages"] = window.pdf_panel._document.pageCount()
        assert window.grab().save(str(output / "source-repair-final-window.png"))
        assert (project / "base.csv").read_bytes() == original
        assert (project / "data.csv").read_bytes() == current
        report["one_undo_restores_models_source_record_and_draft"] = True
        report["saved_reload_matches_and_original_data_unchanged"] = True
    finally:
        session.shutdown()
        session.editor_drafts.clear()
        session._dirty = False
        window.close()
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    report["limits"] = ["Synthetic offscreen events, not native IME/AX/Windows or student usability acceptance",
                        "Baseline byte storage is not persistent; original source versions must be retained separately",
                        "No package, installed application, Git or release mutation"]
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
