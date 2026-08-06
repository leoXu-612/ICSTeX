"""Linked-source refresh comparison and three-way merge (Sprint 4).

Three-way merge follows the task list rules: Base is the last synced
snapshot, Remote is the current external file, Local is the user's edited
table. Unchanged cells are untouched, remote-only changes are accepted,
local-only changes are kept, and a cell changed by both sides is a visible
conflict (local value kept by default).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow


@dataclass(frozen=True)
class CellChange:
    rowId: str
    columnId: str
    base: Cell
    remote: Cell
    local: Cell
    conflict: bool = False


@dataclass(frozen=True)
class MergeResult:
    data: TableData
    changes: list[CellChange] = field(default_factory=list)
    conflicts: list[CellChange] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def diff_tables(base: TableData, other: TableData) -> dict:
    base_rows = {row.id: row for row in base.rows}
    other_rows = {row.id: row for row in other.rows}
    added = len(set(other_rows) - set(base_rows))
    removed = len(set(base_rows) - set(other_rows))
    changed = 0
    for row_id in set(base_rows) & set(other_rows):
        for column_id in set(base.column_ids()) | set(other.column_ids()):
            if _cell_key(base.cell(row_id, column_id)) != _cell_key(other.cell(row_id, column_id)):
                changed += 1
    return {"added": added, "removed": removed, "changed": changed}


def merge_three_way(base: TableData, remote: TableData, local: TableData) -> MergeResult:
    base_rows = {row.id: row for row in base.rows}
    remote_rows = {row.id: row for row in remote.rows}
    local_rows = {row.id: row for row in local.rows}
    row_ids = list(dict.fromkeys([*base_rows, *remote_rows, *local_rows]))
    changes: list[CellChange] = []
    conflicts: list[CellChange] = []
    added = removed = changed = 0
    merged_rows: list[TableRow] = []

    for row_id in row_ids:
        base_row = base_rows.get(row_id)
        remote_row = remote_rows.get(row_id)
        local_row = local_rows.get(row_id)
        if base_row is None:
            if remote_row is not None and local_row is not None:
                merged_rows.append(
                    _merge_row(row_id, TableRow(id=row_id), remote_row, local_row, changes, conflicts)
                )
                added += 1
            elif remote_row is not None:
                merged_rows.append(remote_row)
                added += 1
            elif local_row is not None:
                merged_rows.append(local_row)
                added += 1
            continue
        if remote_row is None and local_row is None:
            removed += 1
            continue
        if remote_row is None:
            merged_rows.append(local_row)
            continue
        if local_row is None:
            merged_rows.append(remote_row)
            continue
        merged = _merge_row(row_id, base_row, remote_row, local_row, changes, conflicts)
        merged_rows.append(merged)
        changed += sum(1 for item in changes if item.rowId == row_id and not item.conflict)

    columns = list(base.columns)
    column_ids = {column.id for column in columns}
    for row in merged_rows:
        for column_id in row.cells:
            if column_id not in column_ids:
                columns.append(
                    ColumnSpec(
                        id=column_id,
                        name=column_id,
                        dataType=_cell_kind(remote_rows, local_rows, row.id, column_id),
                    )
                )
                column_ids.add(column_id)

    data = TableData(
        columns=columns,
        rows=merged_rows,
        header_row_count=base.header_row_count,
        repeat_header=base.repeat_header,
        merges=base.merges,
        notes=base.notes,
    )
    summary = {
        "added": added,
        "removed": removed,
        "changed": max(0, changed),
        "conflicts": len(conflicts),
    }
    return MergeResult(data=data, changes=changes, conflicts=conflicts, summary=summary)


def _merge_row(
    row_id: str,
    base_row: TableRow,
    remote_row: TableRow,
    local_row: TableRow,
    changes: list[CellChange],
    conflicts: list[CellChange],
) -> TableRow:
    cells: dict[str, Cell] = {}
    column_ids = list(dict.fromkeys([*base_row.cells, *remote_row.cells, *local_row.cells]))
    for column_id in column_ids:
        base_cell = base_row.cells.get(column_id, Cell())
        remote_cell = remote_row.cells.get(column_id, Cell())
        local_cell = local_row.cells.get(column_id, Cell())
        if _cell_key(remote_cell) == _cell_key(local_cell):
            cells[column_id] = local_cell
            continue
        if _cell_key(remote_cell) != _cell_key(base_cell) and _cell_key(local_cell) == _cell_key(base_cell):
            cells[column_id] = remote_cell
            changes.append(CellChange(row_id, column_id, base_cell, remote_cell, local_cell))
            continue
        if _cell_key(local_cell) != _cell_key(base_cell) and _cell_key(remote_cell) == _cell_key(base_cell):
            cells[column_id] = local_cell
            continue
        conflict = _cell_key(local_cell) != _cell_key(base_cell) and _cell_key(remote_cell) != _cell_key(base_cell)
        cells[column_id] = local_cell
        changes.append(CellChange(row_id, column_id, base_cell, remote_cell, local_cell, conflict=conflict))
        if conflict:
            conflicts.append(changes[-1])
    return TableRow(id=row_id, cells=cells)


def _cell_key(cell: Cell) -> tuple[str, object]:
    return (cell.kind, repr(cell.value))


def _cell_kind(remote_rows: dict, local_rows: dict, row_id: str, column_id: str) -> str:
    for source in (remote_rows, local_rows):
        row = source.get(row_id)
        if row is not None and column_id in row.cells:
            return row.cells[column_id].kind
    return "text"
