"""Main-console integration tests for the Block workspace (Phases 1-2)."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTabWidget

from app.core.blocks.layout import LayoutNode, block_slot
from app.core.blocks.model import content_for_text
from app.core.blocks.project_repository import load_project, save_project
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.schema import SCHEMA_VERSION
from app.core.blocks.source_registry import SourceRecord
from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow
from app.core.blocks.theme import AppTheme, DocumentTheme
from app.gui.blocks.commands import DeleteBlockCommand
from app.gui.blocks.project_dialog import BlockProjectDialog
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.selection import SelectionContext, SelectionManager
from app.gui.blocks.workspace_controller import BlockWorkspaceController
from app.gui.blocks.workspace_widget import BlockWorkspaceWidget


def app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def _registry_with_two_blocks() -> BlockRegistry:
    registry = BlockRegistry()
    registry.create(CreateBlockInput(type="text", alias="txt_a", content=content_for_text("A")))
    registry.create(CreateBlockInput(type="text", alias="txt_b", content=content_for_text("B")))
    return registry


class ProjectRepositoryTests(TestCase):
    def test_round_trip_preserves_all_state(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "proj"
            registry = _registry_with_two_blocks()
            layout = LayoutNode(
                id="lyt_row",
                kind="row",
                children=(block_slot(registry.blocks()[0].id), block_slot(registry.blocks()[1].id)),
            )
            sources = [SourceRecord(sourceId="src_1", kind="xlsx", relativePath="data/a.xlsx", baseSha256="abc")]
            theme = DocumentTheme(
                id="doc_round",
                name="Round",
                page={"size": "letter", "orientation": "portrait", "columns": 1, "margin": {"leftMm": 30, "rightMm": 25, "topMm": 25, "bottomMm": 25}},
                typography={"textFamily": "", "mathFamily": "", "monoFamily": "", "baseSizePt": 11, "lineSpacing": 1.15},
                tables={"preset": "booktabs"},
                layout={"blockGapPt": 10},
            )

            written = save_project(project, registry=registry, layout=layout, sources=sources, document_theme=theme)

            self.assertEqual(len(written), 4)
            loaded = load_project(project)
            self.assertEqual([b.alias for b in loaded["registry"].blocks()], ["txt_a", "txt_b"])
            self.assertIsNotNone(loaded["layout"])
            assert loaded["layout"] is not None
            self.assertEqual(loaded["layout"].children[0].blockId, registry.blocks()[0].id)
            self.assertEqual([s.sourceId for s in loaded["sources"]], ["src_1"])
            self.assertEqual(loaded["document_theme"].id, "doc_round")

    def test_save_is_atomic_and_never_corrupts(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "proj"
            registry = _registry_with_two_blocks()
            save_project(project, registry=registry, layout=None, sources=[])
            before = (project / ".icstex" / "blocks.json").read_bytes()

            # A failing theme write (invalid object) must not clobber blocks.json.
            with self.assertRaises(AttributeError):
                save_project(project, registry=registry, layout=None, sources=[], document_theme=object())  # type: ignore[arg-type]

            self.assertEqual((project / ".icstex" / "blocks.json").read_bytes(), before)


class ProjectSessionTests(TestCase):
    def test_single_state_identity(self) -> None:
        registry = _registry_with_two_blocks()
        session = ProjectSession(registry=registry)
        core = session.core_objects()
        self.assertIs(core["registry"], registry)
        self.assertIs(core["undo_stack"], session.undo_stack)
        self.assertIs(core["selection"], session.selection)
        self.assertIs(core["table_model"], session.table_model)

    def test_model_change_routes_to_one_save_and_one_preview(self) -> None:
        app()
        session = ProjectSession(project_dir=None)
        events: list[str] = []
        session.save_requested.connect(lambda reason: events.append(f"save:{reason}"))
        session.compile_requested.connect(lambda reason: events.append(f"compile:{reason}"))
        session.model_changed.connect(lambda reason: events.append(f"model:{reason}"))

        session.notify_model_changed("block_updated")

        self.assertEqual(events.count("model:block_updated"), 1)
        self.assertEqual(events.count("save:block_updated"), 1)
        self.assertEqual(events.count("compile:block_updated"), 1)
        # No project dir -> no actual save timer or compile process.
        self.assertFalse(session._save_timer.isActive())

    def test_save_debounce_merges_bursts(self) -> None:
        app()
        with TemporaryDirectory() as directory:
            session = ProjectSession(project_dir=Path(directory))
            completed: list[str] = []
            session.save_completed.connect(completed.append)
            for _ in range(5):
                session.request_save("burst")
            self.assertTrue(session._save_timer.isActive())
            session.save_now()
            self.assertEqual(completed, ["burst"])
            self.assertTrue((Path(directory) / ".icstex" / "blocks.json").exists())

    def test_table_model_initialized_from_table_block(self) -> None:
        registry = BlockRegistry()
        registry.create(
            CreateBlockInput(
                type="table",
                alias="tab",
                content=TableData(
                    columns=[ColumnSpec(id="c1", name="温度", dataType="number")],
                    rows=[TableRow(id="r1", cells={"c1": Cell(kind="number", value=20)})],
                    header_row_count=0,
                ).to_content_dict(),
            )
        )
        session = ProjectSession(registry=registry)
        self.assertEqual(len(session.table_model.data.columns), 1)
        self.assertEqual(session.table_model.data.rows[0].cells["c1"].value, 20)


class WorkspaceControllerTests(TestCase):
    def setUp(self) -> None:
        app()
        self.session = ProjectSession(registry=_registry_with_two_blocks())
        self.workspace = BlockWorkspaceWidget(self.session)
        self.controller = BlockWorkspaceController(self.session, self.workspace)

    def test_add_delete_duplicate_rename_update_undo_redo(self) -> None:
        controller = self.controller
        session = self.session

        block_id = controller.add_block("heading", alias="标题")
        self.assertEqual(session.registry.get(block_id).type, "heading")

        controller.rename_block(block_id, "新标题")
        self.assertEqual(session.registry.get(block_id).alias, "新标题")

        controller.update_block(block_id, {"content": {"text": "正文", "level": 2}}, text="修改标题")
        self.assertEqual(session.registry.get(block_id).content, {"text": "正文", "level": 2})

        controller.duplicate_block(block_id)
        copies = [b for b in session.registry.blocks() if b.alias == "新标题 副本"]
        self.assertEqual(len(copies), 1)

        session.undo_stack.undo()  # duplicate
        session.undo_stack.undo()  # update
        session.undo_stack.undo()  # rename
        self.assertEqual(session.registry.get(block_id).alias, "标题")

        session.undo_stack.redo()
        self.assertEqual(session.registry.get(block_id).alias, "新标题")

        controller.delete_block(block_id)
        self.assertIsNone(session.registry.get(block_id))
        session.undo_stack.undo()
        self.assertIsNotNone(session.registry.get(block_id))

    def test_delete_layout_referenced_block_removes_slot_and_undo_restores(self) -> None:
        session = self.session
        registry = session.registry
        first, second = registry.blocks()[0], registry.blocks()[1]
        layout = LayoutNode(
            id="lyt_row",
            kind="row",
            children=(block_slot(first.id), block_slot(second.id)),
        )
        session.layout = layout

        session.undo_stack.push(DeleteBlockCommand(session, first.id))

        self.assertIsNone(registry.get(first.id))
        assert session.layout is not None
        self.assertEqual([child.blockId for child in session.layout.children], [second.id])

        session.undo_stack.undo()
        self.assertIsNotNone(registry.get(first.id))
        self.assertEqual({child.blockId for child in session.layout.children}, {first.id, second.id})

    def test_referenced_block_delete_is_rejected(self) -> None:
        session = self.session
        registry = session.registry
        target = registry.blocks()[0]
        referrer = registry.blocks()[1]
        from app.core.blocks.model import BlockReference

        registry.update(referrer.id, {"references": [BlockReference(targetBlockId=target.id, kind="cross-reference")]})
        with self.assertRaises(ValueError):
            self.controller.delete_block(target.id)


class DialogWrapperTests(TestCase):
    def test_dialog_shares_session_objects(self) -> None:
        app()
        session = ProjectSession(registry=_registry_with_two_blocks())
        dialog = BlockProjectDialog(session=session)
        self.assertIs(dialog.session, session)
        self.assertIs(dialog.registry, session.registry)
        self.assertIs(dialog.workspace.session, session)
        self.assertEqual(dialog.findChild(QTabWidget).count(), 6)
        dialog.close()

    def test_legacy_dialog_signature_builds_one_session(self) -> None:
        app()
        registry = _registry_with_two_blocks()
        dialog = BlockProjectDialog(registry)
        self.assertIs(dialog.session.registry, registry)
        self.assertIs(dialog.layout_panel.registry, registry)
        dialog.close()


class SelectionManagerTests(TestCase):
    def test_loop_guard_no_duplicate_emissions(self) -> None:
        app()
        manager = SelectionManager()
        seen: list[tuple[SelectionContext, str]] = []
        manager.selection_changed.connect(lambda context, source: seen.append((context, source)))

        manager.select_block("b1", source="browser")
        manager.select_block("b1", source="browser")  # no change -> no emit
        manager.select_block("b1", source="inspector")  # same context, new source -> no emit
        manager.select_block("b2", source="browser")

        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0][0].block_id, "b1")
        self.assertEqual(seen[1][0].block_id, "b2")


class SchemaStabilityTests(TestCase):
    def test_six_schemas_stay_1_0_0(self) -> None:
        import re

        from app.core.blocks import schema as schema_module

        ids = re.findall(r'"\$id":\s*"([^"]+)"', schema_module.__doc__ or "")
        source = Path(schema_module.__file__).read_text(encoding="utf-8")
        ids = re.findall(r'"\$id":\s*"([^"]+)"', source)
        self.assertEqual(len(ids), 6)
        for schema_id in ids:
            self.assertTrue(schema_id.endswith("/1.0.0"), schema_id)
        self.assertEqual(SCHEMA_VERSION, "1.0.0")


class StableLatexTests(TestCase):
    def test_assembly_is_deterministic(self) -> None:
        app()
        with TemporaryDirectory() as directory:
            project = Path(directory) / "proj"
            registry = _registry_with_two_blocks()
            session = ProjectSession(registry=registry, project_dir=project)
            session.layout = LayoutNode(
                id="lyt_row",
                kind="row",
                children=(block_slot(registry.blocks()[0].id), block_slot(registry.blocks()[1].id)),
            )
            first = session.assemble_latex()
            second = session.assemble_latex()
            self.assertIsNotNone(first)
            self.assertEqual(first.read_text(encoding="utf-8"), second.read_text(encoding="utf-8"))
