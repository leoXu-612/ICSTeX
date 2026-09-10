"""Linked-source refresh comparison and three-way merge (Sprint 4).

Three-way merge follows the task list rules: Base is the last synced
snapshot, Remote is the current external file, Local is the user's edited
table. Unchanged cells are untouched, remote-only changes are accepted,
local-only changes are kept, and a cell changed by both sides is a visible
conflict (local value kept by default).
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from app.core.blocks.table_model import Cell, TableData, TableRow


@dataclass(frozen=True)
class CellChange:
    rowId: str
    columnId: str
    base: Cell | None
    remote: Cell | None
    local: Cell | None
    conflict: bool = False


@dataclass(frozen=True)
class TableConflict:
    """Structural changes require an explicit whole-table choice, not guessed IDs."""

    base: TableData
    remote: TableData
    local: TableData


@dataclass(frozen=True)
class MergeResult:
    data: TableData
    changes: list[CellChange] = field(default_factory=list)
    conflicts: list[CellChange] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    table_conflict: TableConflict | None = None


def diff_tables(base: TableData, other: TableData) -> dict:
    _validate_ids(base)
    _validate_ids(other)
    base_rows = {row.id: row for row in base.rows}
    other_rows = {row.id: row for row in other.rows}
    added = len(set(other_rows) - set(base_rows))
    removed = len(set(base_rows) - set(other_rows))
    changed = 0
    for row_id in set(base_rows) & set(other_rows):
        for column_id in set(base.column_ids()) | set(other.column_ids()):
            if _cell_key(base_rows[row_id].cells.get(column_id)) != _cell_key(other_rows[row_id].cells.get(column_id)):
                changed += 1
    return {"added": added, "removed": removed, "changed": changed}


def merge_three_way(base: TableData, remote: TableData, local: TableData) -> MergeResult:
    for data in (base, remote, local):
        _validate_ids(data)
    summary = diff_tables(base, remote)
    # Preserve the complete chosen model, including table identity and metadata.
    # Inputs and candidate results never share mutable rows/cells/notes/merges.
    if _same_table(remote, local) or _same_table(remote, base):
        return MergeResult(deepcopy(local), summary=dict(summary, conflicts=0))
    if _same_table(local, base):
        return MergeResult(deepcopy(remote), summary=dict(summary, conflicts=0))
    if not _compatible_structure(base, remote, local):
        return MergeResult(deepcopy(local), summary=dict(summary, conflicts=1),
                           table_conflict=TableConflict(deepcopy(base), deepcopy(remote), deepcopy(local)))
    base, remote, local = deepcopy((base, remote, local))
    base_rows = {row.id: row for row in base.rows}
    remote_rows = {row.id: row for row in remote.rows}
    local_rows = {row.id: row for row in local.rows}
    row_ids = list(dict.fromkeys([*base_rows, *remote_rows, *local_rows]))
    changes: list[CellChange] = []
    conflicts: list[CellChange] = []
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
            elif remote_row is not None:
                merged_rows.append(remote_row)
            elif local_row is not None:
                merged_rows.append(local_row)
            continue
        # Existing rows are present on both sides under _compatible_structure.
        merged = _merge_row(row_id, base_row, remote_row, local_row, changes, conflicts)
        merged_rows.append(merged)

    data = deepcopy(local)
    data.rows = merged_rows
    summary = dict(diff_tables(base, data), conflicts=len(conflicts))
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
        base_cell = base_row.cells.get(column_id)
        remote_cell = remote_row.cells.get(column_id)
        local_cell = local_row.cells.get(column_id)
        if _cell_key(remote_cell) == _cell_key(local_cell):
            if local_cell is not None:
                cells[column_id] = local_cell
            continue
        if _cell_key(remote_cell) != _cell_key(base_cell) and _cell_key(local_cell) == _cell_key(base_cell):
            if remote_cell is not None:
                cells[column_id] = remote_cell
            changes.append(CellChange(row_id, column_id, base_cell, remote_cell, local_cell))
            continue
        if _cell_key(local_cell) != _cell_key(base_cell) and _cell_key(remote_cell) == _cell_key(base_cell):
            if local_cell is not None:
                cells[column_id] = local_cell
            continue
        conflict = _cell_key(local_cell) != _cell_key(base_cell) and _cell_key(remote_cell) != _cell_key(base_cell)
        if local_cell is not None:
            cells[column_id] = local_cell
        changes.append(CellChange(row_id, column_id, base_cell, remote_cell, local_cell, conflict=conflict))
        if conflict:
            conflicts.append(changes[-1])
    return TableRow(id=row_id, cells=cells)


def _cell_key(cell: Cell | None) -> tuple | None:
    return None if cell is None else (cell.kind, type(cell.value), repr(cell.value))


def _validate_ids(data: TableData) -> None:
    if len({row.id for row in data.rows}) != len(data.rows) or len(set(data.column_ids())) != len(data.columns):
        raise ValueError("Duplicate table row or column identity; merge refused.")
    columns = set(data.column_ids())
    if any(set(row.cells) - columns for row in data.rows):
        raise ValueError("Unknown cell column; merge refused.")


def _same_table(left: TableData, right: TableData) -> bool:
    return left.table_id == right.table_id and repr(left.to_content_dict()) == repr(right.to_content_dict())


def _compatible_structure(base, remote, local):
    def metadata(data):
        payload = data.to_content_dict()
        del payload["rows"]
        return data.table_id, payload

    if metadata(base) != metadata(remote) or metadata(base) != metadata(local):
        return False
    base_ids = [row.id for row in base.rows]
    # Only independent appended rows have an unambiguous existing-coordinate
    # interpretation. Deletions, insertions and reorders are shown as a conflict.
    return all([row.id for row in data.rows][:len(base_ids)] == base_ids for data in (remote, local))


def resolve_merge(result: MergeResult, choices: tuple[str | Cell, ...], *, table_choice: str | None = None) -> MergeResult:
    """Build an independent candidate; never apply to a session or mutate inputs."""
    if result.table_conflict is not None:
        if choices or table_choice not in {"remote", "local"}:
            raise ValueError("An explicit whole-table choice is required.")
        data = deepcopy(getattr(result.table_conflict, table_choice))
    else:
        if table_choice is not None or len(choices) != len(result.conflicts):
            raise ValueError("Every cell conflict needs exactly one choice.")
        data = deepcopy(result.data)
        _validate_ids(data)
        rows = {row.id: row for row in data.rows}
        targets = set()
        for conflict, choice in zip(result.conflicts, choices):
            target = (conflict.rowId, conflict.columnId)
            if target in targets or conflict.columnId not in data.column_ids():
                raise ValueError("Ambiguous conflict target; resolution refused.")
            targets.add(target)
            if isinstance(choice, Cell):
                cell = deepcopy(choice)
            elif choice in {"remote", "local"}:
                cell = deepcopy(getattr(conflict, choice))
            else:
                raise ValueError("Unknown conflict choice.")
            row = rows.get(conflict.rowId)
            if row is None:
                row = rows[conflict.rowId] = TableRow(conflict.rowId)
                data.rows.append(row)
            if cell is None:
                row.cells.pop(conflict.columnId, None)
            else:
                row.cells[conflict.columnId] = cell
    return MergeResult(data, deepcopy(result.changes), summary=dict(result.summary, conflicts=0))
