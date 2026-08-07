"""Block compile pipeline performance regression coverage.

These tests lock the verified optimizations: generated files are written
only when their content changes, one edit launches exactly one LaTeX
process, and Stable LaTeX assembly is deferred off the per-edit hot path.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.blocks.layout import LayoutNode, block_slot
from app.core.blocks.model import content_for_text
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.workspace_controller import BlockWorkspaceController


def _app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def _project() -> tuple[Path, ProjectSession, BlockWorkspaceController, list]:
    _app()
    tmp = TemporaryDirectory()
    project = Path(tmp.name) / "proj"
    registry = BlockRegistry()
    ids = []
    for index in range(3):
        block = registry.create(
            CreateBlockInput(type="text", alias=f"t{index}", content=content_for_text(f"文本 {index}"))
        )
        ids.append(block.id)
    session = ProjectSession(
        registry=registry,
        layout=LayoutNode(id="lyt_row", kind="row", children=tuple(block_slot(i) for i in ids)),
        project_dir=project,
    )
    return tmp, session, BlockWorkspaceController(session), ids


class WriteOnChangeTests(TestCase):
    def test_edit_writes_only_the_changed_generated_file(self) -> None:
        tmp, session, controller, ids = _project()
        try:
            session.assemble_latex()
            blocks_dir = session.project_dir / "blocks"
            before = {path: path.stat().st_mtime_ns for path in blocks_dir.glob("*.tex")}
            main = session.project_dir / "main.tex"
            sty = session.project_dir / "styles" / "icstex-generated.sty"
            before[main] = main.stat().st_mtime_ns
            before[sty] = sty.stat().st_mtime_ns

            time.sleep(0.02)
            controller.update_block(ids[1], {"content": content_for_text("修改后的文本")}, text="edit")
            session.assemble_latex()

            changed = [p for p, mtime in before.items() if p.stat().st_mtime_ns != mtime]
            self.assertEqual(changed, [session.project_dir / "blocks" / f"{ids[1]}.tex"])
        finally:
            tmp.cleanup()

    def test_unchanged_content_is_not_rewritten(self) -> None:
        tmp, session, _controller, _ids = _project()
        try:
            session.assemble_latex()
            paths = [session.project_dir / "main.tex"]
            paths += list((session.project_dir / "blocks").glob("*.tex"))
            paths.append(session.project_dir / "styles" / "icstex-generated.sty")
            mtimes = {p: p.stat().st_mtime_ns for p in paths}
            time.sleep(0.02)
            session.assemble_latex()
            stats = session._last_assemble_stats
            self.assertEqual(stats["written"], 0)
            self.assertEqual(stats["unchanged"], len(paths))
            self.assertEqual({p: p.stat().st_mtime_ns for p in paths}, mtimes)
        finally:
            tmp.cleanup()


class SingleProcessTests(TestCase):
    def test_one_edit_launches_one_latex_process(self) -> None:
        tmp, session, controller, _ids = _project()
        try:
            finished = []
            session.compile_finished.connect(finished.append)
            controller.update_block(_ids[0], {"content": content_for_text("触发一次编译")}, text="edit")
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and not finished:
                QApplication.processEvents()
                time.sleep(0.02)
            self.assertEqual(len(finished), 1)
            self.assertEqual(session._compile_launches, 1)
        finally:
            tmp.cleanup()


class DeferredAssembleTests(TestCase):
    def test_assemble_is_deferred_off_the_edit_path(self) -> None:
        tmp, session, controller, _ids = _project()
        try:
            session.assemble_latex()  # warm state
            session._last_assemble_stats = {}
            controller.update_block(_ids[0], {"content": content_for_text("再改一次")}, text="edit")
            self.assertTrue(session._preview_timer.isActive())
            self.assertEqual(session._last_assemble_stats, {}, "assemble must not run synchronously on edit")
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and not session._last_assemble_stats:
                QApplication.processEvents()
                time.sleep(0.02)
            self.assertGreater(session._last_assemble_stats.get("written", -1), -1)
        finally:
            tmp.cleanup()
