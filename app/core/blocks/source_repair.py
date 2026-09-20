"""Captured source versions and explicit stable-key table projection.

No writes or Qt. A digest-matching original file is required: the current local
table never substitutes for missing source bytes or undocumented import options.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path

from app.core.blocks.property_draft import table_projection
from app.core.blocks.source_registry import SourceCheckCancelled, SourceRecord, resolve_source_path, _signature
from app.core.blocks.table_import import SpreadsheetImportAdapter, infer_cell, read_csv_text
from app.core.blocks.table_model import Cell, TableData, TableRow
from app.core.project_dependencies import _open_safe_input

MAX_REPAIR_SOURCE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class SourceCapture:
    project: Path
    relative_path: str
    payload: bytes
    sha256: str
    signature: tuple


def capture_source(project: Path, relative_path: str, *, expected_sha: str | None = None,
                   max_bytes: int = MAX_REPAIR_SOURCE_BYTES, cancelled=lambda: False) -> SourceCapture:
    if not 0 < max_bytes <= MAX_REPAIR_SOURCE_BYTES:
        raise ValueError("Invalid source capture limit")
    project = project.resolve(strict=True)
    path = resolve_source_path(project, SourceRecord("capture", "", relative_path, ""))
    chunks, size = [], 0
    with _open_safe_input(project, path) as stream:
        before = os.fstat(stream.fileno())
        if before.st_size > max_bytes:
            raise ValueError("Source exceeds the 16 MiB repair capture limit")
        while True:
            if cancelled():
                raise SourceCheckCancelled()
            chunk = stream.read(min(1024 * 1024, max_bytes - size + 1))
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise ValueError("Source grew beyond the repair capture limit")
            chunks.append(chunk)
        after = os.fstat(stream.fileno())
    result = SourceCapture(project, relative_path, b"".join(chunks), "", _signature(after))
    if size != before.st_size or _signature(before) != result.signature or not capture_path_unchanged(result):
        raise OSError("Source changed during capture; no comparison was accepted")
    payload = result.payload
    digest = hashlib.sha256(payload).hexdigest()
    if expected_sha is not None and digest != expected_sha.lower():
        raise ValueError("Selected baseline bytes do not match the recorded SHA-256")
    if cancelled():
        raise SourceCheckCancelled()
    return SourceCapture(project, relative_path, payload, digest, result.signature)


def capture_path_unchanged(capture: SourceCapture) -> bool:
    """Cheap post-hash callback guard, not a substitute for content verification."""
    try:
        path = resolve_source_path(capture.project, SourceRecord("capture", "", capture.relative_path, ""))
        return _signature(path.stat(follow_symlinks=False)) == capture.signature
    except (OSError, ValueError):
        return False


def verify_capture(capture: SourceCapture, *, cancelled=lambda: False) -> bool:
    try:
        current = capture_source(capture.project, capture.relative_path, cancelled=cancelled)
        return current.sha256 == capture.sha256 and current.signature == capture.signature
    except (OSError, ValueError):
        return False


@dataclass(frozen=True)
class ImportOptions:
    encoding: str = "utf-8-sig"
    header_row: bool = True
    sheet: str = ""
    cell_range: str = ""


def parse_source(capture: SourceCapture, options: ImportOptions) -> TableData:
    suffix = Path(capture.relative_path).suffix.lower()
    if suffix == ".csv":
        # Preserve identifiers/whitespace; numeric conversion belongs to the
        # explicitly selected target column type, not an invisible key heuristic.
        data = read_csv_text(capture.payload.decode(options.encoding), header_row=options.header_row,
                             infer_types=False)
    elif suffix == ".xlsx":
        with SpreadsheetImportAdapter.from_bytes(capture.payload, max_bytes=MAX_REPAIR_SOURCE_BYTES) as adapter:
            if not options.sheet:
                raise ValueError("Select an explicit worksheet name")
            data = adapter.read_sheet(options.sheet, cell_range=options.cell_range or None,
                                      header_row=options.header_row)
    else:
        raise ValueError("Only CSV and XLSX sources are supported")
    table_projection(data.to_content_dict())
    return data


@dataclass(frozen=True)
class ColumnMapping:
    local: str
    base: str
    remote: str


def _key(cell: Cell | None):
    if cell is None or cell.kind in {"empty", "latex"} or cell.value in (None, ""):
        raise ValueError("Row keys must be nonempty literal values")
    if isinstance(cell.value, float) and not math.isfinite(cell.value):
        raise ValueError("Row keys must be finite")
    if not isinstance(cell.value, (str, int, float, bool)):
        raise ValueError("Unsupported row key value")
    return json.dumps([cell.kind, type(cell.value).__name__, cell.value], ensure_ascii=False, allow_nan=False)


def _convert(cell: Cell, column):
    if column.dataType == "text":
        return deepcopy(cell)  # Never strip text identifiers or change typed XLSX values.
    if cell.kind == "text":
        inferred = infer_cell(cell.value)
        if inferred.kind not in (column.dataType, "empty"):
            raise ValueError(f"Source value cannot map to target column type: {column.name}")
        return inferred
    if cell.kind not in (column.dataType, "empty"):
        raise ValueError(f"Source type differs from target column type: {column.name}")
    return deepcopy(cell)


def map_source_tables(base: TableData, remote: TableData, local: TableData,
                      mapping: tuple[ColumnMapping, ...], *, key_column: str) -> tuple[TableData, TableData]:
    """Project data onto explicitly confirmed columns and stable keys, never row numbers.

    Target column formatting/notes remain local policy. Every source column must
    be accounted for; schema changes need explicit whole-table comparison instead.
    Numeric/date/bool target types use the existing conversion rule, visibly chosen
    by the target column type; text keys remain exact. Reordering remains visible.
    """
    for data in (base, remote, local):
        table_projection(data.to_content_dict())
        if data.header_row_count > len(data.rows):
            raise ValueError("Header rows are missing; use whole-table comparison")
    for side, data in (("local", local), ("base", base), ("remote", remote)):
        ids = [getattr(item, side) for item in mapping]
        if len(ids) != len(set(ids)) or set(ids) != set(data.column_ids()):
            raise ValueError("Every column needs a unique explicit mapping; no columns may be omitted")
    if key_column not in local.column_ids():
        raise ValueError("Select a mapped stable row key column")
    if any(data.header_row_count != local.header_row_count for data in (base, remote)):
        raise ValueError("Header shapes differ; use whole-table comparison")
    if local.header_row_count > 1:
        raise ValueError("Multiple header rows need whole-table comparison")
    columns = {c.id: c for c in local.columns}
    local_keys = {}
    for row in local.rows[local.header_row_count:]:
        key = _key(row.cells.get(key_column))
        if key in local_keys:
            raise ValueError("Duplicate local row key; cannot infer data identity")
        local_keys[key] = row.id
    known_ids = set(row.id for row in local.rows)
    key_ids = dict(local_keys)

    def project(data, side):
        seen, rows = set(), []
        for index, row in enumerate(data.rows):
            cells = {item.local: (deepcopy(row.cells.get(getattr(item, side), Cell()))
                     if index < data.header_row_count else
                     _convert(row.cells.get(getattr(item, side), Cell()), columns[item.local])) for item in mapping}
            if index < data.header_row_count:
                row_id = local.rows[index].id
            else:
                key = _key(cells.get(key_column))
                if key in seen:
                    raise ValueError(f"Duplicate {side} row key; cannot infer data identity")
                seen.add(key)
                if key not in key_ids:
                    row_id = "srcrow_" + hashlib.sha256(key.encode("utf-8")).hexdigest()
                    if row_id in known_ids:
                        raise ValueError("Generated row identity collides with an existing row")
                    key_ids[key] = row_id
                    known_ids.add(row_id)
                row_id = key_ids[key]
            rows.append(TableRow(row_id, cells))
        result = deepcopy(local)
        result.rows = rows
        result.merges = []
        indices = {data.column_ids().index(getattr(item, side)): local.column_ids().index(item.local)
                   for item in mapping}
        for r1, r2, c1, c2 in data.merges:
            remapped = sorted(indices[index] for index in range(c1, c2 + 1))
            if remapped != list(range(remapped[0], remapped[-1] + 1)):
                raise ValueError("Column mapping splits a merged cell; use whole-table comparison")
            result.merges.append([r1, r2, remapped[0], remapped[-1]])
        table_projection(result.to_content_dict())
        return result

    return project(base, "base"), project(remote, "remote")
