from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTabWidget
from PySide6.QtGui import QColor, QImage, QImageWriter

from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.blocks.layout import LayoutNode, block_slot
from app.core.blocks.layout_solver import solve_layout
from app.core.blocks.model import Semantic, content_for_text
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.source_merge import CellChange, MergeResult
from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableEditorModel, TableRow
from app.core.blocks.theme import AppTheme
from app.core.formula_input import FinalTextEditPlan
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from app.gui.blocks.layout_panel import BlockLayoutPanel
from app.gui.blocks.formula_tab import FormulaBlockTab
from app.gui.blocks.merge_dialog import MergeDialog
from app.gui.blocks.project_dialog import BlockProjectDialog
from app.gui.blocks.table_editor import TableEditor
from app.gui.blocks.theme_settings import ThemeSettings


TOOLCHAIN = detect_toolchain()


def app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def registry_with_blocks() -> BlockRegistry:
    registry = BlockRegistry()
    for index, name in enumerate(("apparatus", "results", "model", "analysis")):
        registry.create(
            CreateBlockInput(
                type="text" if index == 3 else "image" if index == 0 else "table",
                alias=name,
                semantic=Semantic(role="figure" if index == 0 else "table" if index == 1 else "text"),
                content=content_for_text(name),
            )
        )
    return registry


class TableEditorTests(TestCase):
    def setUp(self) -> None:
        app()

    def test_edit_and_undo_redo(self) -> None:
        model = TableEditorModel(
            TableData(
                columns=[ColumnSpec(id="c1", name="C1")],
                rows=[TableRow(id="r1", cells={"c1": Cell(kind="text", value="a")})],
                header_row_count=0,
            )
        )
        editor = TableEditor(model)
        editor.model.set_cell("r1", "c1", Cell(kind="number", value=5))
        editor.refresh()
        self.assertEqual(editor.table.item(0, 0).text(), "5")

        editor.undo()
        self.assertEqual(model.data.cell("r1", "c1").value, "a")
        editor.redo()
        self.assertEqual(model.data.cell("r1", "c1").value, 5)

    def test_paste_rectangle_from_clipboard(self) -> None:
        model = TableEditorModel(TableData(columns=[ColumnSpec(id="c1", name="C1"), ColumnSpec(id="c2", name="C2")]))
        editor = TableEditor(model)
        editor.table.setCurrentCell(0, 0)

        editor.paste_clipboard_text("1\t2\n3\t4\n")

        self.assertEqual(model.data.cell("row_001", "c1").value, 1)
        self.assertEqual(model.data.cell("row_001", "c2").value, 2)
        self.assertEqual(model.data.cell("row_002", "c1").value, 3)

    def test_row_column_operations(self) -> None:
        model = TableEditorModel(TableData(columns=[ColumnSpec(id="c1", name="C1")]))
        editor = TableEditor(model)
        editor.insert_row()
        editor.insert_column()
        self.assertEqual(len(model.data.rows), 1)
        self.assertEqual(model.data.column_ids(), ["col_1", "c1"])
        editor.table.setCurrentCell(0, 0)
        editor.delete_column()
        self.assertEqual(model.data.column_ids(), ["c1"])
        editor.delete_row()
        self.assertEqual(model.data.rows, [])

    def test_source_status_label(self) -> None:
        model = TableEditorModel(TableData())
        model.source_state = "changed"  # type: ignore[attr-defined]
        editor = TableEditor(model)
        self.assertEqual(editor.status_label.text(), "源已变化")


class BlockLayoutPanelTests(TestCase):
    def setUp(self) -> None:
        app()

    def test_apply_row_and_undo(self) -> None:
        registry = registry_with_blocks()
        panel = BlockLayoutPanel(registry)
        for index in range(panel.block_list.count()):
            panel.block_list.item(index).setSelected(True)

        panel.apply_row()

        self.assertIsNotNone(panel.layout)
        assert panel.layout is not None
        self.assertEqual(panel.layout.kind, "row")
        self.assertEqual(len(panel.layout.children), 4)
        panel.undo()
        self.assertIsNone(panel.layout)

    def test_inspector_gap_affects_solver(self) -> None:
        registry = registry_with_blocks()
        panel = BlockLayoutPanel(
            registry,
            LayoutNode(id="lyt_row", kind="row", children=(block_slot("blk_x"), block_slot("blk_y"))),
        )
        panel.gap_spin.setValue(8.0)
        solved = solve_layout(panel.layout, 300.0)  # type: ignore[arg-type]
        self.assertAlmostEqual(solved.children[0].widthPt, (300.0 - 8 * 72.27 / 25.4) / 2, places=2)

    def test_slot_drag_reorder_with_undo(self) -> None:
        layout = LayoutNode(id="lyt_row", kind="row", children=(block_slot("blk_a"), block_slot("blk_b")))
        panel = BlockLayoutPanel(registry_with_blocks(), layout)

        panel.move_slot(0, 2)

        self.assertEqual(panel.layout.children[0].blockId, "blk_b")  # type: ignore[union-attr]
        panel.undo()
        self.assertEqual(panel.layout.children[0].blockId, "blk_a")  # type: ignore[union-attr]


class MergeDialogTests(TestCase):
    def setUp(self) -> None:
        app()

    def test_resolve_remote_and_manual(self) -> None:
        result = MergeResult(
            data=TableData(columns=[ColumnSpec(id="a", name="A")], rows=[]),
            conflicts=[
                CellChange("r1", "a", Cell(kind="text", value="base"), Cell(kind="text", value="外部"), Cell(kind="text", value="本地"), conflict=True),
                CellChange("r2", "a", Cell(kind="text", value="base"), Cell(kind="text", value="外部2"), Cell(kind="text", value="本地2"), conflict=True),
            ],
            summary={"conflicts": 2},
        )
        dialog = MergeDialog(result)
        dialog._remote_buttons[0].setChecked(True)
        dialog._manual_edits[1].setText("手动值")

        dialog._resolve()

        self.assertEqual(result.data.cell("r1", "a").value, "外部")
        self.assertEqual(result.data.cell("r2", "a").value, "手动值")


class ThemeSettingsTests(TestCase):
    def setUp(self) -> None:
        app()

    def test_validate_and_save_load(self) -> None:
        settings = ThemeSettings(
            AppTheme(
                id="theme_t",
                name="T",
                tokens={
                    "background": "#ffffff",
                    "surface": "#ffffff",
                    "surfaceElevated": "#ffffff",
                    "foreground": "#000000",
                    "foregroundMuted": "#666666",
                    "border": "#cccccc",
                    "accent": "#123456",
                    "accentForeground": "#ffffff",
                    "selection": "#eeeeee",
                    "success": "#00ff00",
                    "warning": "#ffaa00",
                    "error": "#ff0000",
                    "layoutGuide": "#0000ff",
                },
            )
        )
        self.assertEqual(settings.validate(), [])
        with TemporaryDirectory() as directory:
            path = Path(directory) / "theme.json"
            settings.save(path)
            loaded = ThemeSettings(AppTheme())
            import json

            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["tokens"]["accent"], "#123456")

    def test_invalid_color_flagged(self) -> None:
        settings = ThemeSettings(AppTheme())
        settings.token_edits["accent"].setText("not-a-color")
        self.assertTrue(any("accent" in issue for issue in settings.validate()))


class BlockProjectDialogTests(TestCase):
    def setUp(self) -> None:
        app()

    def test_tabs_exist(self) -> None:
        registry = registry_with_blocks()
        dialog = BlockProjectDialog(registry)
        self.assertEqual(dialog.findChild(QTabWidget).count(), 6)
        dialog.close()

    def test_formula_tab_edits_block_ast(self) -> None:
        registry = BlockRegistry()
        block = registry.create(
            CreateBlockInput(
                type="formula",
                alias="eq",
                semantic=Semantic(role="equation"),
                content=FormulaBlockAdapter().content_for(r"E=mc^2"),
            )
        )
        tab = FormulaBlockTab(registry)
        tab.block_list.item(0).setSelected(True)

        class FakeFormulaDialog:
            class DialogCode:
                Accepted = 1

            def __init__(self, *args, **kwargs) -> None:
                pass

            def exec(self) -> int:
                return 1

            def plan(self):
                return FinalTextEditPlan(
                    start=0,
                    end=0,
                    source_text="",
                    text=r"\(E=\gamma mc^2\)",
                )

        with patch("app.gui.blocks.formula_tab.FormulaDialog", FakeFormulaDialog):
            tab._edit_selected()

        self.assertEqual(registry.get(block.id).content["latexCache"], r"E=\gamma mc^2")

    @skipUnless(TOOLCHAIN.is_compile_ready, "xelatex required")
    def test_preview_builds_pdf_and_syncs_table(self) -> None:
        from app.core.blocks.model import Block, Caption, Semantic, content_for_text
        from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow

        with TemporaryDirectory() as directory:
            project = Path(directory) / "proj"
            (project / "assets" / "images").mkdir(parents=True)
            image = QImage(4, 4, QImage.Format.Format_RGB32)
            image.fill(QColor(200, 200, 200))
            QImageWriter(str(project / "assets" / "images" / "a.png"), b"png").write(image)

            registry = BlockRegistry()
            registry.create(
                CreateBlockInput(
                    type="image",
                    alias="img",
                    semantic=Semantic(role="figure", caption=Caption("装置")),
                    content={"source": "assets/images/a.png"},
                )
            )
            table_block = registry.create(
                CreateBlockInput(
                    type="table",
                    alias="tab",
                    semantic=Semantic(role="table"),
                    content=TableData(
                        columns=[ColumnSpec(id="c1", name="温度", dataType="number")],
                        rows=[TableRow(id="r1", cells={"c1": Cell(kind="number", value=20)})],
                        header_row_count=0,
                    ).to_content_dict(),
                )
            )
            registry.create(
                CreateBlockInput(
                    type="formula",
                    alias="eq",
                    semantic=Semantic(role="equation"),
                    content=FormulaBlockAdapter().content_for(r"E=mc^2"),
                )
            )
            registry.create(
                CreateBlockInput(
                    type="text",
                    alias="txt",
                    semantic=Semantic(role="text"),
                    content=content_for_text("分析"),
                )
            )
            model = TableEditorModel(TableData(columns=[ColumnSpec(id="c1", name="温度", dataType="number")]))
            model.set_cell("r1", "c1", Cell(kind="number", value=30))
            layout = LayoutNode(id="lyt_row", kind="row", children=(block_slot("blk_a"), block_slot("blk_b")))

            dialog = BlockProjectDialog(
                registry,
                layout=layout,
                table_model=model,
                project_dir=project,
            )
            result = dialog._build_pdf_sync()

            self.assertTrue(result.ok, result.combined_output)
            self.assertTrue(result.pdf_file.exists())
            self.assertTrue((project / "main.tex").exists())
            self.assertIn("\\begin{document}", (project / "main.tex").read_text(encoding="utf-8"))
            synced = registry.get(table_block.id).content
            self.assertEqual(synced["rows"][0]["cells"]["c1"]["value"], 30)
            dialog.close()
