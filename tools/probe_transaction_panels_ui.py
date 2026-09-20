"""D3 local review-dialog comparison using real synthetic files and drafts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication
from shiboken6 import isValid
from app.core.project_checkpoint import DraftInput, create_checkpoint, restore_checkpoint
from app.gui.project_recovery_dialog import RecoveryDraftDialog
from app.gui.theme import apply_theme
from tests.test_project_checkpoint_gui import ProjectCheckpointGuiTests
from tests.test_project_migration_gui import ProjectMigrationGuiTests
from tests.test_block_write_recovery_gui import BlockWriteRecoveryGuiTests
from tools.bench_pdf_pipeline import source_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-fixed-actions", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    report = {"completed": False, "app_sha256": source_digest(), "states": [],
              "limits": "Synthetic offscreen review; no actual student files, compilation or native acceptance"}

    def capture(name, dialog, primary, close):
        for scale, width, height in ((1.0, 900, 640), (1.5, 760, 620)):
            app.ui_scale_manager.apply_scale(scale)
            dialog.resize(width, height)
            dialog.show()
            for _ in range(8):
                app.processEvents()
            positions = (0, dialog.scroller.verticalScrollBar().maximum()) if hasattr(dialog, "scroller") else (0,)
            for index, position in enumerate(positions):
                if hasattr(dialog, "scroller"):
                    dialog.scroller.verticalScrollBar().setValue(position)
                    app.processEvents()
                actions = {button.text(): button.visibleRegion().contains(button.rect()) for button in (primary, close)}
                image = f"{name}-{scale}-{index}.png"
                assert dialog.grab().save(str(output / image))
                report["states"].append({"name": name, "image": image, "scale": scale,
                    "requested_size": [width, height], "actual_size": [dialog.width(), dialog.height()],
                    "actions_visible": actions})
                if args.require_fixed_actions:
                    assert all(actions.values()), (name, scale, actions)
                    assert dialog.width() <= width and dialog.height() <= height, (name, scale, dialog.size())
            dialog.hide()

    for case_type in (ProjectCheckpointGuiTests, ProjectMigrationGuiTests, BlockWriteRecoveryGuiTests):
        case = case_type()
        case.setUpClass()
        case.setUp()
        original = {p: p.read_bytes() for p in case.project.rglob("*") if p.is_file()}
        try:
            if case_type is ProjectCheckpointGuiTests:
                case.tab.editor.appendPlainText("% Unapplied synthetic window draft")
                created = case.dialog()
                created.tree.setCurrentItem(created.tree.topLevelItem(created.tree.topLevelItemCount() - 1))
                capture("checkpoint", created, created.action_button, created.close_button)
                created.reject()
                archive = case.home / "fixture.icstex-checkpoint"
                create_checkpoint(case.project, (case.source.name,), archive,
                    drafts=(DraftInput("synthetic", "source-text", case.source.name, b"Independent synthetic draft"),))
                restored = case.dialog(restore=True)
                restored.load_archive(archive)
                case.wait(lambda: not restored.busy)
                assert restored.info is not None
                restored.tree.setCurrentItem(restored.tree.topLevelItem(restored.tree.topLevelItemCount() - 1))
                capture("restore", restored, restored.action_button, restored.close_button)
                restored.reject()
                copy = restore_checkpoint(archive, case.home / "recovery-fixture")
                drafts = RecoveryDraftDialog(case.window, copy.directory)
                case.dialogs.append(drafts)
                case.wait(lambda: not drafts.busy)
                assert drafts.copy is not None
                drafts.tree.setCurrentItem(drafts.tree.topLevelItem(0))
                capture("drafts", drafts, drafts.apply_button, drafts.close_button)
            else:
                case.load(side=None) if case_type is BlockWriteRecoveryGuiTests else case.load()
                dialog = case.dialog
                tree = dialog.tree if case_type is BlockWriteRecoveryGuiTests else dialog.output
                tree.setCurrentItem(tree.topLevelItem(0))
                name = "interrupted" if case_type is BlockWriteRecoveryGuiTests else "migration"
                capture(name, dialog, dialog.action_button, dialog.close_button)
                if case_type is ProjectMigrationGuiTests:
                    case.publish()
                    capture("migration-published", dialog, dialog.open_button, dialog.close_button)
                    report["migration_result_files"] = [(p.relative_to(dialog.result.directory).as_posix(),
                        hashlib.sha256(p.read_bytes()).hexdigest()) for p in dialog.result.directory.rglob("*") if p.is_file()]
            assert all(p.read_bytes() == raw for p, raw in original.items())
            assert not case.window.compile_authorized_roots
            report.setdefault("originals_retained", []).append(case_type.__name__)
        finally:
            case.doCleanups()
            assert not isValid(case.window), case_type.__name__
    report["app_sha256_after"] = source_digest()
    report["completed"] = report["app_sha256_after"] == report["app_sha256"]
    (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    assert report["completed"], report
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
