"""Cocoa image-picker QA. Answer the three real pickers with the desktop tool.

First cancel, then choose the printed source twice; dismiss the final error.
All data/settings are synthetic and disposable. No installed app is changed.
"""
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

from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.core.blocks.assembly import build_latex_files
from app.core.blocks.layout import block_slot
from app.core.blocks.project_repository import load_project, save_project
from app.core.blocks.registry import CreateBlockInput
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
    app.setApplicationName("ICSTeX V1 Image Import QA")
    apply_theme(app)
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    report = {"platform": platform.platform(), "python": platform.python_version(),
              "qt_platform": app.platformName(), "app_python_tree_sha256": digest.hexdigest()}

    with TemporaryDirectory(prefix="icstex-image-picker-qa-") as directory:
        base = Path(directory).resolve()
        fixture = create_project(base, "block")
        project = fixture.root.parent
        assets = project / "assets/images"
        assets.mkdir(parents=True)
        original, chosen = assets / "original.png", base / "Chosen synthetic image.png"
        for path, color in ((original, "#2468A0"), (chosen, "#27A35A")):
            pixels = QImage(120, 60, QImage.Format.Format_RGB32)
            pixels.fill(QColor(color))
            assert pixels.save(str(path))
        original_bytes, chosen_bytes = original.read_bytes(), chosen.read_bytes()
        state = load_project(project)
        block = state["registry"].create(CreateBlockInput(type="image", alias="Synthetic diagram",
            content={"source": "assets/images/original.png"}))
        state["layout"] = replace(state["layout"], children=state["layout"].children + (block_slot(block.id),))
        save_project(project, **{key: state[key] for key in ("registry", "layout", "sources", "document_theme")})
        for path, text in build_latex_files(project, **{key: state[key] for key in ("registry", "layout", "document_theme")}).items():
            path.write_text(text, encoding="utf-8")
        before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
        loaded = load_project(project)
        session = ProjectSession(**{key: loaded[key] for key in ("registry", "layout", "sources", "document_theme", "project_dir")})
        window = MainWindow(settings_store=AppSettings(QSettings(str(base / "qa.ini"), QSettings.Format.IniFormat)))
        try:
            window.auto_compile_action.setChecked(False)
            assert _install_session(window, session)
            _set_block_mode(window, True)
            window.resize(1120, 860)
            window.show()
            window.raise_()
            window.activateWindow()
            # No synthetic keyboard input is sent before the real native picker;
            # the desktop tool verifies and operates that modal directly.
            session.selection.select_block(block.id, source="native-image-qa")
            inspector = window.block_inspector
            inspector.scroll.ensureWidgetVisible(inspector.image_replace_button)
            print(json.dumps({"stage": "cancel_picker", "chosen_file": str(chosen)}), flush=True)
            inspector.image_replace_button.click()
            assert session.registry.get(block.id).content["source"] == "assets/images/original.png"
            assert session.undo_stack.count() == 0 and not session.has_unsaved_changes
            assert {p: p.read_bytes() for p in before} == before
            assert list(assets.iterdir()) == [original]
            report["real_picker_cancel_has_no_model_or_file_changes"] = True

            print(json.dumps({"stage": "choose_image", "chosen_file": str(chosen)}), flush=True)
            inspector.image_replace_button.click()
            imported = session.registry.get(block.id).content["source"]
            assert imported == "assets/images/Chosen synthetic image.png", imported
            assert (project / imported).read_bytes() == chosen_bytes
            assert original.read_bytes() == original_bytes and chosen.read_bytes() == chosen_bytes
            assert session.undo_stack.count() == 1 and session.compile_manager is None
            session.undo_stack.undo()
            assert session.registry.get(block.id).content["source"] == "assets/images/original.png"
            session.undo_stack.redo()
            assert session.registry.get(block.id).content["source"] == imported
            window.block_save_action.trigger()
            assert session.last_save_ok and session.compile_manager is None
            assert load_project(project)["registry"].get(block.id).content["source"] == imported
            window.block_compile_action.trigger()
            wait_for(lambda: session.last_result is not None)
            assert session.last_result.ok, session.last_result
            window.block_preview_area.pdf_button.click()
            QTest.qWait(300)
            assert window.grab().save(str(output / "actual-image-final.png"))
            final = session.last_result.pdf_file.read_bytes()
            (output / "image-import-final.pdf").write_bytes(final)
            report["final_sha256"] = hashlib.sha256(final).hexdigest()
            report["real_picker_import_undo_save_readback_and_final"] = True

            retained = project / "assets/retained-images"
            outside = base / "outside"
            outside.mkdir()
            assets.rename(retained)
            assets.symlink_to(outside, target_is_directory=True)
            snapshot = session.registry.get(block.id).to_dict()
            undo_count = session.undo_stack.count()
            try:
                print(json.dumps({"stage": "choose_again_expect_link_error", "chosen_file": str(chosen)}), flush=True)
                inspector.image_replace_button.click()
                assert session.registry.get(block.id).to_dict() == snapshot
                assert session.undo_stack.count() == undo_count
                assert list(outside.iterdir()) == []
                assert (retained / "original.png").read_bytes() == original_bytes
                assert (retained / chosen.name).read_bytes() == chosen_bytes
                assert chosen.read_bytes() == chosen_bytes
                report["real_picker_link_error_preserves_model_source_and_outside_directory"] = True
            finally:
                assets.unlink()
                retained.rename(assets)
            assert _close_block_project(window)
            reopened = load_project(project)
            assert reopened["registry"].get(block.id).content["source"] == imported
            report["saved_project_reopens_with_the_selected_image"] = True
        finally:
            if window.block_session is not None:
                _close_block_project(window, discard=True)
            for tab in window.tabs.values():
                window.documents.cancel_save_timer(tab)
                tab.modified = tab.dirty = False
            window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    report["limits"] = ["No native Finder drag, IME, AX stress, Windows or human acceptance",
        "POSIX exclusive publication requires a supporting filesystem; unsupported publication fails closed",
        "Source metadata change detection is not an externally locked or cryptographically frozen copy",
        "No installation, packaging, signing or publication"]
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
