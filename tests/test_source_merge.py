from __future__ import annotations

from copy import deepcopy
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
    def test_result_and_resolution_do_not_mutate_any_input_or_sibling_cell(self):
        from app.core.blocks.source_merge import resolve_merge
        base = table({"r1": {"a": "base", "b": "keep", "c": "base2"}, "r2": {"a": "last"}})
        remote, local = deepcopy(base), deepcopy(base)
        remote.rows[0].cells.update(a=Cell("text", "remote"), c=Cell("number", 0))
        local.rows[0].cells.update(a=Cell("text", "local"), c=Cell("boolean", False))
        before = [value.to_content_dict() for value in (base, remote, local)]
        result = merge_three_way(base, remote, local)
        resolved = resolve_merge(result, ("remote", Cell("text", "  exact  ")))
        self.assertEqual([row.id for row in resolved.data.rows], ["r1", "r2"])
        self.assertEqual(resolved.data.cell("r1", "b").value, "keep")
        self.assertEqual(resolved.data.cell("r1", "a").value, "remote")
        self.assertEqual(resolved.data.cell("r1", "c").value, "  exact  ")
        self.assertEqual(resolved.conflicts, [])
        self.assertEqual(len(result.conflicts), 2)
        resolved.data.rows[1].cells["a"] = Cell("text", "edited result")
        self.assertEqual([value.to_content_dict() for value in (base, remote, local)], before)
        self.assertEqual(result.data.cell("r2", "a").value, "last")

    def test_remote_only_row_deletion_and_metadata_changes_are_retained(self):
        base = table({"r1": {"a": "one"}, "r2": {"a": "two"}})
        base.table_id = "table-identity"
        remote = deepcopy(base)
        remote.rows.pop()
        remote.notes = ["remote note"]
        remote.columns[0] = ColumnSpec("a", "New name", unit="mm")
        result = merge_three_way(base, remote, deepcopy(base))
        self.assertEqual(result.data.to_content_dict(), remote.to_content_dict())
        self.assertEqual(result.data.table_id, "table-identity")
        result.data.notes.append("not shared")
        self.assertEqual(remote.notes, ["remote note"])

    def test_delete_vs_edit_is_explicit_whole_table_conflict(self):
        from app.core.blocks.source_merge import resolve_merge
        base = table({"r1": {"a": "base"}})
        remote = table({})
        local = table({"r1": {"a": "local"}})
        result = merge_three_way(base, remote, local)
        self.assertIsNotNone(result.table_conflict)
        self.assertEqual(result.data.to_content_dict(), local.to_content_dict())
        with self.assertRaises(ValueError):
            resolve_merge(result, ())
        resolved = resolve_merge(result, (), table_choice="remote")
        self.assertEqual(resolved.data.to_content_dict(), remote.to_content_dict())
        self.assertEqual(local.cell("r1", "a").value, "local")

    def test_structure_and_order_changes_do_not_silently_drop_local_edits(self):
        base = table({"r1": {"a": "one"}, "r2": {"a": "two"}})
        for change in ("order", "columns", "notes", "header", "merges"):
            with self.subTest(change=change):
                remote, local = deepcopy(base), deepcopy(base)
                local.rows[0].cells["a"] = Cell("text", "local")
                if change == "order":
                    remote.rows.reverse()
                elif change == "columns":
                    remote.columns[0] = ColumnSpec("a", "renamed")
                elif change == "notes":
                    remote.notes = ["remote"]
                elif change == "header":
                    remote.header_row_count = 1
                else:
                    remote.merges = [[0, 0, 0, 1]]
                result = merge_three_way(base, remote, local)
                self.assertIsNotNone(result.table_conflict)
                self.assertEqual(result.data.to_content_dict(), local.to_content_dict())

    def test_sparse_cell_deletion_is_not_changed_to_explicit_empty(self):
        base = table({"r1": {"a": "one", "b": "keep"}})
        remote, local = deepcopy(base), deepcopy(base)
        del remote.rows[0].cells["a"]
        local.rows[0].cells["b"] = Cell("text", "local")
        result = merge_three_way(base, remote, local)
        self.assertNotIn("a", result.data.rows[0].cells)
        self.assertEqual(result.data.cell("r1", "b").value, "local")

    def test_duplicate_identity_is_rejected_before_merge(self):
        base = table({"r1": {"a": "one"}})
        for field in ("rows", "columns"):
            local = deepcopy(base)
            getattr(local, field).append(getattr(local, field)[0])
            with self.assertRaises(ValueError):
                merge_three_way(base, deepcopy(base), local)

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
