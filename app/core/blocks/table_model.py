"""Table content model and local edit operations (Sprint 3).

Data and styling are separate: the model stores rows/columns/cell values,
types, units, header and merge relations; layout/theme decisions live in the
table Block's style override, never here.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from dataclasses import dataclass, field


TABLE_VERSION = "1.0.0"
DATA_TYPES: tuple[str, ...] = ("number", "text", "date", "boolean", "latex", "empty")


@dataclass(frozen=True)
class ColumnSpec:
    id: str
    name: str
    dataType: str = "text"
    unit: str | None = None
    alignment: str = "left"
    nullable: bool = True


@dataclass(frozen=True)
class Cell:
    kind: str = "empty"
    value: object = None


@dataclass(frozen=True)
class TableRow:
    id: str
    cells: dict[str, Cell] = field(default_factory=dict)


class TableData:
    """Rows and columns with header/merge relations; style-free."""

    def __init__(
        self,
        *,
        columns: list[ColumnSpec] | None = None,
        rows: list[TableRow] | None = None,
        header_row_count: int = 1,
        repeat_header: bool = True,
        merges: list[list[int]] | None = None,
        notes: list[str] | None = None,
        table_id: str = "",
    ) -> None:
        self.columns: list[ColumnSpec] = list(columns or [])
        self.rows: list[TableRow] = list(rows or [])
        self.header_row_count = max(0, int(header_row_count))
        self.repeat_header = bool(repeat_header)
        self.merges: list[list[int]] = list(merges or [])  # [r1, r2, c1, c2]
        self.notes: list[str] = list(notes or [])
        self.table_id = table_id

    # --- serialization ----------------------------------------------------

    def to_content_dict(self) -> dict:
        return {
            "tableVersion": TABLE_VERSION,
            "columns": [
                {
                    "id": column.id,
                    "name": column.name,
                    "dataType": column.dataType,
                    "unit": column.unit,
                    "alignment": column.alignment,
                    "nullable": column.nullable,
                }
                for column in self.columns
            ],
            "rows": [
                {
                    "id": row.id,
                    "cells": {
                        column_id: {"kind": cell.kind, "value": cell.value}
                        for column_id, cell in row.cells.items()
                    },
                }
                for row in self.rows
            ],
            "header": {
                "rowCount": self.header_row_count,
                "repeatOnPageBreak": self.repeat_header,
            },
            "merges": [list(merge) for merge in self.merges],
            "notes": list(self.notes),
        }

    @classmethod
    def from_content_dict(cls, data: dict) -> "TableData":
        columns = [
            ColumnSpec(
                id=raw["id"],
                name=raw.get("name", raw["id"]),
                dataType=raw.get("dataType", "text"),
                unit=raw.get("unit"),
                alignment=raw.get("alignment", "left"),
                nullable=raw.get("nullable", True),
            )
            for raw in data.get("columns", [])
        ]
        rows = [
            TableRow(
                id=raw.get("id", f"row_{index}"),
                cells={
                    column_id: Cell(kind=cell.get("kind", "empty"), value=cell.get("value"))
                    for column_id, cell in raw.get("cells", {}).items()
                },
            )
            for index, raw in enumerate(data.get("rows", []))
        ]
        header = data.get("header", {}) or {}
        return cls(
            columns=columns,
            rows=rows,
            header_row_count=header.get("rowCount", 1),
            repeat_header=header.get("repeatOnPageBreak", True),
            merges=data.get("merges", []),
            notes=data.get("notes", []),
        )

    # --- queries ----------------------------------------------------------

    def column_ids(self) -> list[str]:
        return [column.id for column in self.columns]

    def cell(self, row_id: str, column_id: str) -> Cell:
        row = next((row for row in self.rows if row.id == row_id), None)
        if row is None:
            return Cell()
        return row.cells.get(column_id, Cell())

    # --- validation -------------------------------------------------------

    def validate(self) -> list[str]:
        issues: list[str] = []
        column_ids = set(self.column_ids())
        for row in self.rows:
            for column_id in row.cells:
                if column_id not in column_ids:
                    issues.append(f"行 {row.id} 引用了不存在的列 {column_id}")
        for merge in self.merges:
            r1, r2, c1, c2 = merge
            if not (0 <= r1 <= r2 < max(1, len(self.rows)) and 0 <= c1 <= c2 < max(1, len(self.columns))):
                issues.append(f"合并区域越界：{merge}")
        for index_a, a in enumerate(self.merges):
            for b in self.merges[index_a + 1 :]:
                if _rectangles_overlap(a, b):
                    issues.append(f"合并区域重叠：{a} 与 {b}")
        for column_index, column in enumerate(self.columns):
            if column.dataType == "number":
                for row in self.rows:
                    cell = row.cells.get(column.id)
                    if cell is not None and cell.kind == "text":
                        issues.append(f"数值列 {column.name} 包含不可解析文本：{cell.value!r}")
        return issues


class TableEditorModel:
    """Local edit operations with undo/redo (snapshot stack)."""

    def __init__(self, data: TableData) -> None:
        self.data = data
        self._undo: list[TableData] = []
        self._redo: list[TableData] = []
        self._batch_depth = 0

    def _snapshot(self) -> TableData:
        return deepcopy(self.data)

    def _push(self) -> None:
        if self._batch_depth:
            return
        self._undo.append(self._snapshot())
        if len(self._undo) > 200:
            self._undo.pop(0)
        self._redo.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @contextmanager
    def batch_edit(self):
        """A rectangle or multi-row operation is one atomic history entry."""
        outer = self._batch_depth == 0
        before = self._snapshot() if outer else None
        self._batch_depth += 1
        try:
            yield
        except Exception:
            if outer:
                self.data = before
            raise
        else:
            if outer and before.to_content_dict() != self.data.to_content_dict():
                self._undo.append(before)
                self._undo = self._undo[-200:]
                self._redo.clear()
        finally:
            self._batch_depth -= 1

    def next_row_id(self) -> str:
        existing = {row.id for row in self.data.rows}
        index = 1
        while f"row_{index:03d}" in existing:
            index += 1
        return f"row_{index:03d}"

    def next_column_id(self) -> str:
        existing = set(self.data.column_ids())
        index = 1
        while f"col_{index}" in existing:
            index += 1
        return f"col_{index}"

    def set_cell(self, row_id: str, column_id: str, cell: Cell) -> None:
        if column_id not in self.data.column_ids():
            raise ValueError("Unknown table column.")
        if self.data.cell(row_id, column_id) == cell and any(row.id == row_id for row in self.data.rows):
            return
        self._push()
        row = next((row for row in self.data.rows if row.id == row_id), None)
        if row is None:
            row = TableRow(id=row_id)
            self.data.rows.append(row)
        row.cells[column_id] = cell

    def insert_row(self, index: int, row_id: str) -> None:
        if any(row.id == row_id for row in self.data.rows):
            raise ValueError("Duplicate table row id.")
        index = max(0, min(index, len(self.data.rows)))
        self._push()
        self.data.rows.insert(index, TableRow(id=row_id))
        self._shift_merges(0, index, 1)

    def delete_row(self, row_id: str) -> None:
        index = next((index for index, row in enumerate(self.data.rows) if row.id == row_id), None)
        if index is None:
            return
        self._push()
        self.data.rows = [row for row in self.data.rows if row.id != row_id]
        self._shift_merges(0, index, -1)

    def insert_column(self, index: int, spec: ColumnSpec) -> None:
        if spec.id in self.data.column_ids():
            raise ValueError("Duplicate table column id.")
        index = max(0, min(index, len(self.data.columns)))
        self._push()
        self.data.columns.insert(index, spec)
        self._shift_merges(2, index, 1)

    def delete_column(self, column_id: str) -> None:
        if column_id not in self.data.column_ids():
            return
        index = self.data.column_ids().index(column_id)
        self._push()
        self.data.columns = [column for column in self.data.columns if column.id != column_id]
        for row in self.data.rows:
            row.cells.pop(column_id, None)
        self._shift_merges(2, index, -1)

    def _shift_merges(self, axis: int, index: int, delta: int) -> None:
        adjusted = []
        for original in self.data.merges:
            merge = list(original)
            start, end = merge[axis:axis + 2]
            if delta < 0 and start == end == index:
                continue
            if index < start or (delta > 0 and index == start):
                merge[axis] += delta
                merge[axis + 1] += delta
            elif index <= end:
                merge[axis + 1] += delta
            adjusted.append(merge)
        self.data.merges = adjusted

    def merge(self, rectangle: list[int]) -> None:
        self._push()
        for existing in self.merges():
            if _rectangles_overlap(existing, rectangle):
                raise ValueError(f"合并区域与现有区域重叠：{rectangle}")
        self.data.merges.append(list(rectangle))

    def unmerge(self, rectangle: list[int]) -> None:
        self._push()
        self.data.merges = [merge for merge in self.data.merges if merge != list(rectangle)]

    def merges(self) -> list[list[int]]:
        return [list(merge) for merge in self.data.merges]

    def undo(self) -> None:
        if not self._undo:
            return
        self._redo.append(self._snapshot())
        self.data = self._undo.pop()

    def redo(self) -> None:
        if not self._redo:
            return
        self._undo.append(self._snapshot())
        self.data = self._redo.pop()


def _rectangles_overlap(a: list[int], b: list[int]) -> bool:
    ar1, ar2, ac1, ac2 = a
    br1, br2, bc1, bc2 = b
    return not (ar2 < br1 or br2 < ar1 or ac2 < bc1 or bc2 < ac1)
