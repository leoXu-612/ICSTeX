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
from app.core.blocks.theme import AppTheme, DocumentTheme
from app.core.blocks.project_io import load_block_project
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

    def test_layout_projection_does_not_change_loaded_properties(self):
        from app.core.blocks.layout import Size
        original = LayoutNode(id="layout_loaded", kind="row", gap=Size(12.5, "mm"),
                              alignment="middle", fallback={"strategy": "error", "custom": "retained"})
        panel = BlockLayoutPanel(BlockRegistry(), original)
        self.assertEqual(panel.layout, original)
        changes = []
        panel.layoutChanged.connect(lambda: changes.append(True))
        panel._sync_inspector()
        self.assertEqual(panel.layout, original)
        self.assertEqual(changes, [])
        panel.close()

    def test_direct_cell_edit_updates_model_and_zero_false_are_visible(self):
        model = TableEditorModel(TableData(columns=[ColumnSpec(id="c", name="Value")], rows=[
            TableRow(id="custom", cells={"c": Cell(kind="number", value=0)}),
            TableRow(id="other", cells={"c": Cell(kind="boolean", value=False)}),
        ]))
        editor = TableEditor(model)
        self.assertEqual(editor.table.item(0, 0).text(), "0")
        self.assertEqual(editor.table.item(1, 0).text(), "False")
        changed = []
        editor.model_changed.connect(lambda: changed.append(True))
        editor.table.item(0, 0).setText("7")
        self.assertEqual(model.data.cell("custom", "c").value, 7)
        self.assertEqual(len(changed), 1)
        editor.undo()
        self.assertEqual(model.data.cell("custom", "c").value, 0)
        editor.close()

    def test_paste_targets_actual_row_ids_and_is_one_undo(self):
        model = TableEditorModel(TableData(columns=[ColumnSpec(id="c", name="Value")], rows=[
            TableRow(id="z", cells={"c": Cell(kind="text", value="first")}),
            TableRow(id="a", cells={"c": Cell(kind="text", value="second")}),
        ]))
        editor = TableEditor(model)
        before = model.data.to_content_dict()
        editor.table.setCurrentCell(1, 0)
        editor.paste_clipboard_text("1\t2\n3\t4")
        self.assertEqual(model.data.cell("a", "c").value, 1)
        self.assertEqual(model.data.cell("z", "c").value, "first")
        self.assertEqual(len(model.data.rows), 3)
        self.assertEqual(len(model.data.columns), 2)
        editor.undo()
        self.assertEqual(model.data.to_content_dict(), before)
        editor.redo()
        self.assertEqual(model.data.cell("a", "c").value, 1)
        editor.close()

    def test_repeated_row_and_column_insertions_keep_unique_ids(self):
        model = TableEditorModel(TableData(columns=[ColumnSpec(id="col_1", name="A")], rows=[
            TableRow(id="row_001"), TableRow(id="row_003")]))
        editor = TableEditor(model)
        editor.insert_row()
        editor.insert_row()
        editor.insert_column()
        editor.insert_column()
        self.assertEqual(len({row.id for row in model.data.rows}), 4)
        self.assertEqual(len(set(model.data.column_ids())), 3)
        editor.close()

    def test_block_table_paste_limit_keeps_data_and_history(self):
        model = TableEditorModel(TableData())
        editor = TableEditor(model)
        editor.paste_clipboard_text("\t".join(["x"] * 201))
        self.assertEqual(model.data.columns, [])
        self.assertFalse(model.can_undo)
        self.assertIn("未粘贴", editor.detail_label.text())
        editor.close()

    def test_block_table_keeps_html_paste_support(self):
        model = TableEditorModel(TableData())
        editor = TableEditor(model)
        editor.paste_clipboard_text("<table><tr><td>0</td><td></td></tr><tr><td>2</td><td>3</td></tr></table>")
        self.assertEqual(editor.table.item(0, 0).text(), "0")
        self.assertEqual(editor.table.item(0, 1).text(), "")
        self.assertEqual(editor.table.item(1, 1).text(), "3")
        editor.undo()
        self.assertEqual(model.data.rows, [])
        editor.close()

    def test_clear_rectangle_restores_with_one_undo(self):
        model = TableEditorModel(TableData())
        editor = TableEditor(model)
        editor.paste_clipboard_text("1\t2\n3\t4")
        before = model.data.to_content_dict()
        editor.table.selectAll()
        editor.clear_selection()
        self.assertEqual(model.data.rows[0].cells[model.data.columns[0].id].kind, "empty")
        editor.undo()
        self.assertEqual(model.data.to_content_dict(), before)
        editor.close()

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

    def test_slot_weight_edits_selected_slot_once_and_preserves_selection(self):
        from dataclasses import replace
        from PySide6.QtGui import QUndoStack
        first = replace(block_slot("blk_a"), weight=2.5, minWidthPt=17)
        second = replace(block_slot("blk_b"), weight=4)
        original = LayoutNode(id="weights", children=(first, second))
        panel = BlockLayoutPanel(registry_with_blocks(), original)
        panel.command_stack = QUndoStack(panel)
        self.assertFalse(panel.weight_spin.isEnabled())
        panel.slot_list.setCurrentRow(0)
        self.assertEqual(panel.weight_spin.value(), 2.5)
        self.assertEqual(panel.command_stack.count(), 0)
        panel.weight_spin.setValue(3.5)
        self.assertEqual(panel.layout.children, (replace(first, weight=3.5), second))
        self.assertEqual(panel.slot_list.currentRow(), 0)
        self.assertEqual(panel.command_stack.count(), 1)
        panel.undo()
        self.assertEqual(panel.layout, original)
        self.assertEqual(panel.weight_spin.value(), 2.5)
        panel.close()

    def test_edit_gap_preserves_unedited_fallback_properties(self):
        original = LayoutNode(id="fallback", fallback={"strategy": "error", "custom": "keep"})
        panel = BlockLayoutPanel(registry_with_blocks(), original)
        panel.gap_spin.setValue(8)
        self.assertEqual(panel.layout.fallback, original.fallback)
        panel.close()

    def test_inspector_control_tab_moves_focus_without_applying_or_losing_tab_input(self):
        import sys
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from app.gui.blocks.inspector import BlockInspector
        from app.gui.blocks.project_session import ProjectSession
        registry = registry_with_blocks()
        block = next(block for block in registry.blocks() if block.type == "text")
        session = ProjectSession(registry=registry)
        inspector = BlockInspector(session)
        try:
            session.selection.select_block(block.id, source="keyboard-test")
            inspector.resize(500, 500)
            inspector.show()
            inspector.activateWindow()
            inspector.content_edit.setFocus()
            inspector.content_edit.selectAll()
            QTest.keyClicks(inspector.content_edit, "draft")
            QTest.keyClick(inspector.content_edit, Qt.Key.Key_Tab)
            self.assertEqual(inspector.content_edit.toPlainText(), "draft\t")
            control = Qt.KeyboardModifier.MetaModifier if sys.platform == "darwin" else Qt.KeyboardModifier.ControlModifier
            QTest.keyClick(inspector.content_edit, Qt.Key.Key_Tab, control | Qt.KeyboardModifier.ShiftModifier)
            app().processEvents()
            self.assertIs(app().focusWidget(), inspector.alias_edit)
            inspector.content_edit.setFocus()
            QTest.keyClick(inspector.content_edit, Qt.Key.Key_Tab, control)
            self.assertIs(app().focusWidget(), inspector.apply_button)
            self.assertEqual(inspector.content_edit.toPlainText(), "draft\t")
            self.assertEqual(registry.get(block.id), block)
            self.assertEqual(session.undo_stack.count(), 0)
        finally:
            session.shutdown()
            inspector.close()

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

    def test_incomplete_preview_cannot_be_confirmed(self):
        from PySide6.QtWidgets import QDialogButtonBox
        result = MergeResult(TableData(columns=[ColumnSpec("a", "A")],
                            rows=[TableRow("r", {"a": Cell("text", "x" * 300000)})]))
        dialog = MergeDialog(result)
        self.assertFalse(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
        self.assertIsNone(dialog._candidate)
        self.assertIn("无法完整显示", dialog.status.text())
        dialog.reject()
        dialog.deleteLater()

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
        dialog.preview_button.click()
        dialog._resolve()

        self.assertEqual(dialog.result.data.cell("r1", "a").value, "外部")
        self.assertEqual(dialog.result.data.cell("r2", "a").value, "手动值")
        self.assertEqual(result.data.rows, [])
        self.assertEqual(len(result.conflicts), 2)
        dialog.deleteLater()

    def test_same_row_conflicts_preserve_siblings_order_inputs_and_exact_manual_text(self):
        from app.core.blocks.source_merge import merge_three_way
        from tests.test_source_merge import table
        base = table({"r1": {"a": "a", "b": "untouched", "c": "c"}, "r2": {"a": "last"}})
        remote = table({"r1": {"a": "remote", "b": "untouched", "c": "remote2"}, "r2": {"a": "last"}})
        local = table({"r1": {"a": "local", "b": "untouched", "c": "local2"}, "r2": {"a": "last"}})
        result = merge_three_way(base, remote, local)
        before = result.data.to_content_dict()
        dialog = MergeDialog(result)
        dialog._remote_buttons[0].setChecked(True)
        dialog._manual_edits[1].setText("  exact  ")
        dialog._resolve()
        self.assertEqual(dialog.result.data.to_content_dict(), before)
        dialog.preview_button.click()
        dialog._resolve()
        self.assertEqual([row.id for row in dialog.result.data.rows], ["r1", "r2"])
        self.assertEqual(dialog.result.data.cell("r1", "b").value, "untouched")
        self.assertEqual(dialog.result.data.cell("r1", "c").value, "  exact  ")
        self.assertEqual(result.data.to_content_dict(), before)
        dialog.deleteLater()

    def test_cancel_preserves_inputs_and_whole_table_choice_is_visible(self):
        from app.core.blocks.source_merge import merge_three_way
        from tests.test_source_merge import table
        base = table({"r1": {"a": "base"}})
        local = table({"r1": {"a": "local"}})
        remote = table({})
        base.table_id, local.table_id, remote.table_id = "base-id", "local-id", "remote-id"
        result = merge_three_way(base, remote, local)
        dialog = MergeDialog(result)
        self.assertEqual(dialog.preview_tabs.count(), 4)
        self.assertIn('"tableId": "base-id"', dialog.preview_tabs.widget(1).toPlainText())
        self.assertIn('"tableId": "remote-id"', dialog.preview_tabs.widget(2).toPlainText())
        self.assertIn('"tableId": "local-id"', dialog.preview_tabs.widget(3).toPlainText())
        dialog.table_remote_button.setChecked(True)
        dialog.preview_button.click()
        dialog.reject()
        self.assertEqual(dialog.result.data.to_content_dict(), local.to_content_dict())
        self.assertEqual(result.data.to_content_dict(), local.to_content_dict())
        dialog.deleteLater()


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
        dialog.session.shutdown()  # Explicit cleanup of the synthetic unsaved model.
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
    def test_preview_builds_pdf_after_explicit_table_draft_application(self) -> None:
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
            self.assertIsNone(dialog._build_pdf_sync())
            self.assertEqual(registry.get(table_block.id).content["rows"][0]["cells"]["c1"]["value"], 20)
            self.assertTrue(dialog.session.apply_editor_drafts((("table", table_block.id),)))
            result = dialog._build_pdf_sync()

            self.assertTrue(result.ok, result.combined_output)
            self.assertTrue(result.pdf_file.exists())
            self.assertTrue((project / "main.tex").exists())
            self.assertIn("\\begin{document}", (project / "main.tex").read_text(encoding="utf-8"))
            synced = registry.get(table_block.id).content
            self.assertEqual(synced["rows"][0]["cells"]["c1"]["value"], 30)
            dialog.close()

    def test_dialog_opens_with_loaded_document_theme(self) -> None:
        # load_block_project() supplies a DocumentTheme; passing the load
        # result straight into the dialog must not crash the AppTheme-only
        # ThemeSettings tab, and the preview PDF must honor the loaded theme.
        with TemporaryDirectory() as directory:
            project = Path(directory) / "proj"
            (project / "assets" / "images").mkdir(parents=True)
            registry = BlockRegistry()
            block = registry.create(
                CreateBlockInput(
                    type="text",
                    alias="txt",
                    semantic=Semantic(role="text"),
                    content=content_for_text("验收文本"),
                )
            )
            layout = LayoutNode(id="lyt_row", kind="row", children=(block_slot(block.id),))
            loaded_document_theme = DocumentTheme(
                id="doc_loaded",
                name="Loaded",
                page={"size": "letter", "orientation": "portrait", "columns": 1, "margin": {"leftMm": 30, "rightMm": 25, "topMm": 25, "bottomMm": 25}},
                typography={"textFamily": "", "mathFamily": "", "monoFamily": "", "baseSizePt": 11, "lineSpacing": 1.15},
                tables={"preset": "booktabs"},
                layout={"blockGapPt": 10},
            )
            dialog = BlockProjectDialog(
                registry,
                layout=layout,
                theme=loaded_document_theme,
                document_theme=loaded_document_theme,
                project_dir=project,
            )
            self.assertIs(dialog.document_theme, loaded_document_theme)
            self.assertEqual(dialog.findChild(QTabWidget).count(), 6)
            result = dialog._build_pdf_sync()
            self.assertTrue(result.ok, getattr(result, "combined_output", ""))
            sty = (project / "styles" / "icstex-generated.sty").read_text(encoding="utf-8")
            self.assertIn("letterpaper", sty)
            dialog.close()
