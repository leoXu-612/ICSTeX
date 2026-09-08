from __future__ import annotations

from unittest import TestCase

from app.core.blocks.model import Block, Semantic, content_for_text
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.store import BlockStore
from app.core.blocks.table_model import (
    Cell,
    ColumnSpec,
    TableData,
    TableEditorModel,
    TableRow,
)


class TableDataTests(TestCase):
    def test_batch_is_atomic_and_rolls_back_on_error(self):
        model = TableEditorModel(TableData(columns=[ColumnSpec(id="c", name="C")]))
        with self.assertRaises(ValueError):
            with model.batch_edit():
                model.insert_row(0, "r")
                model.set_cell("r", "missing", Cell(kind="number", value=1))
        self.assertEqual(model.data.rows, [])
        self.assertFalse(model.can_undo)

    def test_batch_paste_and_noop_history(self):
        model = TableEditorModel(TableData(columns=[ColumnSpec(id="c", name="C")]))
        with model.batch_edit():
            model.set_cell("r1", "c", Cell(kind="number", value=1))
            model.set_cell("r2", "c", Cell(kind="number", value=2))
        model.undo()
        self.assertEqual(model.data.rows, [])
        self.assertFalse(model.can_undo)
        with model.batch_edit():
            pass
        self.assertTrue(model.can_redo)
        model.redo()
        self.assertEqual(len(model.data.rows), 2)

    def test_duplicate_identity_is_rejected_without_history_change(self):
        model = TableEditorModel(TableData(columns=[ColumnSpec(id="c", name="C")], rows=[TableRow(id="r")]))
        with self.assertRaises(ValueError):
            model.insert_row(0, "r")
        with self.assertRaises(ValueError):
            model.insert_column(0, ColumnSpec(id="c", name="C"))
        self.assertFalse(model.can_undo)

    def test_row_and_column_changes_preserve_merge_coordinates(self):
        model = TableEditorModel(TableData(columns=[ColumnSpec(id="a", name="A"), ColumnSpec(id="b", name="B")],
                                           rows=[TableRow(id="r1"), TableRow(id="r2")], merges=[[0, 1, 0, 1]]))
        model.insert_row(0, "r0")
        self.assertEqual(model.merges(), [[1, 2, 0, 1]])
        model.insert_column(1, ColumnSpec(id="c", name="C"))
        self.assertEqual(model.merges(), [[1, 2, 0, 2]])
        model.delete_row("r1")
        self.assertEqual(model.merges(), [[1, 1, 0, 2]])
        model.delete_row("r2")
        self.assertEqual(model.merges(), [])

    def test_content_round_trip_through_block_store(self) -> None:
        data = TableData(
            columns=[
                ColumnSpec(id="col_t", name="温度", dataType="number", unit=r"\celsius", alignment="decimal"),
                ColumnSpec(id="col_n", name="备注", dataType="text"),
            ],
            rows=[],
        )
        data.rows.append(
            TableRow(
                id="row_001",
                cells={"col_t": Cell(kind="number", value=20), "col_n": Cell(kind="text", value="基准组")},
            )
        )
        registry = BlockRegistry()
        block = registry.create(
            CreateBlockInput(
                type="table",
                alias="results",
                semantic=Semantic(role="table", label="tab:results"),
                content=data.to_content_dict(),
            )
        )

        restored = TableData.from_content_dict(block.content)

        self.assertEqual(restored.column_ids(), ["col_t", "col_n"])
        self.assertEqual(restored.cell("row_001", "col_t").value, 20)
        self.assertEqual(restored.rows[0].cells["col_n"].kind, "text")

    def test_merge_overlap_rejected(self) -> None:
        model = TableEditorModel(
            TableData(
                columns=[ColumnSpec(id="c1", name="C1"), ColumnSpec(id="c2", name="C2")],
                rows=[],
            )
        )
        model.merge([0, 1, 0, 0])
        with self.assertRaises(ValueError):
            model.merge([0, 1, 0, 0])
        self.assertEqual(len(model.merges()), 1)

    def test_edit_operations_undo_redo(self) -> None:
        model = TableEditorModel(
            TableData(columns=[ColumnSpec(id="c1", name="C1")], rows=[])
        )
        model.insert_row(0, "row_001")
        model.set_cell("row_001", "c1", Cell(kind="number", value=1))
        model.insert_column(1, ColumnSpec(id="c2", name="C2"))

        self.assertEqual(model.data.column_ids(), ["c1", "c2"])
        model.undo()
        self.assertEqual(model.data.column_ids(), ["c1"])
        model.undo()
        self.assertEqual(model.data.cell("row_001", "c1").kind, "empty")
        model.redo()
        self.assertEqual(model.data.cell("row_001", "c1").value, 1)

    def test_validation_flags_bad_column_and_merge(self) -> None:
        data = TableData(
            columns=[ColumnSpec(id="c1", name="C1", dataType="number")],
            rows=[],
        )
        data.rows.append(
            TableRow(
                id="r1",
                cells={"missing": Cell(kind="text", value="x")},
            )
        )
        data.merges = [[0, 5, 0, 0], [1, 3, 0, 0]]
        issues = data.validate()
        self.assertTrue(any("不存在的列" in issue for issue in issues))
        self.assertTrue(any("重叠" in issue for issue in issues))

    def test_numeric_column_text_warning(self) -> None:
        data = TableData(columns=[ColumnSpec(id="c1", name="C1", dataType="number")], rows=[])
        data.rows.append(
            TableRow(
                id="r1",
                cells={"c1": Cell(kind="text", value="abc")},
            )
        )
        self.assertTrue(any("不可解析文本" in issue for issue in data.validate()))
