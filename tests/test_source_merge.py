from __future__ import annotations

from unittest import TestCase

from app.core.blocks.source_merge import diff_tables, merge_three_way
from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow


def table(values: dict[str, dict[str, object]]) -> TableData:
    columns = [ColumnSpec(id=column_id, name=column_id, dataType="text") for column_id in ("a", "b", "c")]
    rows = [
        TableRow(
            id=row_id,
            cells={column_id: Cell(kind="text", value=value) for column_id, value in cells.items()},
        )
        for row_id, cells in values.items()
    ]
    return TableData(columns=columns, rows=rows, header_row_count=0)


class ThreeWayMergeTests(TestCase):
    def test_diff_counts(self) -> None:
        base = table({"r1": {"a": "1"}, "r2": {"a": "2"}})
        other = table({"r1": {"a": "1"}, "r2": {"a": "9"}, "r3": {"a": "3"}})
        diff = diff_tables(base, other)
        self.assertEqual(diff, {"added": 1, "removed": 0, "changed": 1})

    def test_remote_only_change_is_accepted(self) -> None:
        base = table({"r1": {"a": "1", "b": "x"}})
        remote = table({"r1": {"a": "2", "b": "x"}})
        local = table({"r1": {"a": "1", "b": "x"}})
        result = merge_three_way(base, remote, local)
        self.assertEqual(result.data.cell("r1", "a").value, "2")
        self.assertEqual(result.summary["conflicts"], 0)

    def test_local_only_change_is_kept(self) -> None:
        base = table({"r1": {"a": "1", "b": "x"}})
        remote = table({"r1": {"a": "1", "b": "x"}})
        local = table({"r1": {"a": "1", "b": "本地"}})
        result = merge_three_way(base, remote, local)
        self.assertEqual(result.data.cell("r1", "b").value, "本地")

    def test_same_cell_changed_both_sides_is_conflict(self) -> None:
        base = table({"r1": {"a": "1"}})
        remote = table({"r1": {"a": "外部"}})
        local = table({"r1": {"a": "本地"}})
        result = merge_three_way(base, remote, local)
        self.assertEqual(len(result.conflicts), 1)
        self.assertEqual(result.data.cell("r1", "a").value, "本地")
        self.assertEqual(result.summary["conflicts"], 1)

    def test_different_cells_merge_without_conflict(self) -> None:
        base = table({"r1": {"a": "1", "b": "x"}})
        remote = table({"r1": {"a": "外部", "b": "x"}})
        local = table({"r1": {"a": "1", "b": "本地"}})
        result = merge_three_way(base, remote, local)
        self.assertEqual(len(result.conflicts), 0)
        self.assertEqual(result.data.cell("r1", "a").value, "外部")
        self.assertEqual(result.data.cell("r1", "b").value, "本地")

    def test_added_rows_from_both_sides_merge(self) -> None:
        base = table({"r1": {"a": "1"}})
        remote = table({"r1": {"a": "1"}, "r_remote": {"a": "R"}})
        local = table({"r1": {"a": "1"}, "r_local": {"a": "L"}})
        result = merge_three_way(base, remote, local)
        self.assertEqual(result.data.cell("r_remote", "a").value, "R")
        self.assertEqual(result.data.cell("r_local", "a").value, "L")
        self.assertEqual(result.summary["added"], 2)
