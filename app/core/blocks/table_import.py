"""Table import adapters (Sprint 3): CSV, clipboard, and XLSX.

All external files are untrusted: spreadsheets are read with cached values
only (formulas are never evaluated, macros are never executed), sizes are
bounded, and third-party reading is wrapped behind adapter boundaries.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from html.parser import HTMLParser
import html as html_lib
import io
from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree

from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow


ENCODINGS = ("utf-8-sig", "utf-8", "gbk", "latin-1")
NUMBER_RE = re.compile(r"^[+-]?(\d+([.]\d*)?|[.]\d+)([eE][+-]?\d+)?$")
DATE_RE = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")
MAX_ROWS = 5000
MAX_COLS = 200

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def detect_encoding(data: bytes) -> str:
    for encoding in ENCODINGS:
        try:
            data.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "latin-1"


def infer_cell(value: object) -> Cell:
    if value is None or value == "":
        return Cell(kind="empty")
    if isinstance(value, bool):
        return Cell(kind="boolean", value=bool(value))
    if isinstance(value, (int, float)):
        return Cell(kind="number", value=value)
    if isinstance(value, (datetime, date)):
        return Cell(kind="date", value=value.isoformat())
    text = str(value).strip()
    if not text:
        return Cell(kind="empty")
    if text.lower() in ("true", "false"):
        return Cell(kind="boolean", value=text.lower() == "true")
    if NUMBER_RE.fullmatch(text):
        return Cell(kind="number", value=_to_number(text))
    match = DATE_RE.fullmatch(text)
    if match:
        return Cell(kind="date", value=f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}")
    return Cell(kind="text", value=text)


def _to_number(text: str) -> object:
    try:
        return int(text)
    except ValueError:
        return float(text)


def column_spec_from_cells(column_id: str, name: str, cells: list[Cell]) -> ColumnSpec:
    kinds = [cell.kind for cell in cells if cell.kind != "empty"]
    if kinds and all(kind == "number" for kind in kinds):
        data_type = "number"
        alignment = "decimal"
    elif kinds and all(kind == "boolean" for kind in kinds):
        data_type = "boolean"
        alignment = "center"
    elif kinds and all(kind == "date" for kind in kinds):
        data_type = "date"
        alignment = "center"
    else:
        data_type = "text"
        alignment = "left"
    return ColumnSpec(id=column_id, name=name, dataType=data_type, alignment=alignment)


def _delimiter(text: str) -> str:
    first = next((line for line in text.splitlines() if line.strip()), "")
    if "\t" in first and first.count("\t") >= first.count(","):
        return "\t"
    return ","


def read_csv_text(text: str, *, header_row: bool = True) -> TableData:
    reader = csv.reader(io.StringIO(text), delimiter=_delimiter(text))
    raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
    return _table_from_grid(raw_rows, header_row=header_row)


def read_csv_bytes(data: bytes, *, header_row: bool = True) -> TableData:
    encoding = detect_encoding(data)
    return read_csv_text(data.decode(encoding), header_row=header_row)


def parse_clipboard(text: str) -> TableData | None:
    if not text.strip():
        return None
    lowered = text.lower()
    if "<table" in lowered:
        rows = _parse_html_table(text)
        if rows:
            return _table_from_grid(rows, header_row=False)
        return None
    return read_csv_text(text, header_row=False)


def _table_from_grid(raw_rows: list[list[str]], *, header_row: bool) -> TableData:
    if not raw_rows:
        return TableData()
    width = max(len(row) for row in raw_rows)
    width = min(width, MAX_COLS)
    if header_row:
        header = [name.strip() or f"Col{index + 1}" for index, name in enumerate(raw_rows[0][:width])]
        header = _unique_names(header)
        body = raw_rows[1:]
    else:
        header = [f"Col{index + 1}" for index in range(width)]
        body = raw_rows
    body = body[:MAX_ROWS]

    columns = [
        ColumnSpec(
            id=f"col_{index + 1}",
            name=name,
            dataType="text",
            alignment="left",
        )
        for index, name in enumerate(header)
    ]
    cells_grid: list[list[Cell]] = []
    for raw in body:
        padded = list(raw[:width])
        while len(padded) < width:
            padded.append("")
        cells_grid.append([infer_cell(cell) for cell in padded])
    for column_index, column in enumerate(columns):
        values = [row[column_index] for row in cells_grid]
        inferred = column_spec_from_cells(column.id, column.name, values)
        columns[column_index] = inferred
    rows = [
        TableRow(
            id=f"row_{index + 1:03d}",
            cells={column.id: cells_grid[index][column_index] for column_index, column in enumerate(columns)},
        )
        for index in range(len(cells_grid))
    ]
    return TableData(columns=columns, rows=rows, header_row_count=1 if header_row else 0)


def _unique_names(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        if name in seen:
            seen[name] += 1
            result.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 0
            result.append(name)
    return result


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_cell = False
        self._current_cell: list[str] = []
        self._current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("td", "th"):
            self._in_cell = True
            self._current_cell = []
        elif tag == "tr":
            self._current_row = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th"):
            self._in_cell = False
            self._current_row.append(" ".join(self._current_cell).strip())
        elif tag == "tr":
            if self._current_row:
                self.rows.append(self._current_row)

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)


def _parse_html_table(text: str) -> list[list[str]]:
    parser = _HTMLTableParser()
    parser.feed(text)
    return parser.rows


class SpreadsheetImportAdapter:
    """Reads XLSX workbooks with cached values only (no formula execution)."""

    def __init__(self, path: Path, *, max_rows: int = MAX_ROWS, max_cols: int = MAX_COLS) -> None:
        import openpyxl

        self._path = Path(path)
        self._workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        self._max_rows = max_rows
        self._max_cols = max_cols

    def sheet_names(self) -> list[str]:
        return list(self._workbook.sheetnames)

    def read_sheet(self, name: str, *, cell_range: str | None = None, header_row: bool = True) -> TableData:
        if name not in self._workbook.sheetnames:
            raise ValueError(f"工作表不存在：{name}")
        sheet = self._workbook[name]
        if cell_range:
            min_col, min_row, max_col, max_row = _parse_range(cell_range)
            max_row = min(max_row, self._max_rows)
            max_col = min(max_col, self._max_cols)
            values = list(
                sheet.iter_rows(
                    min_row=min_row,
                    max_row=max_row,
                    min_col=min_col,
                    max_col=max_col,
                    values_only=True,
                )
            )
            merge_rows = min_row - 1
            merge_cols = min_col - 1
        else:
            max_row = min(sheet.max_row or 0, self._max_rows)
            max_col = min(sheet.max_column or 0, self._max_cols)
            values = list(
                sheet.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col, values_only=True)
            )
            merge_rows = 0
            merge_cols = 0
        merges = [
            [
                r1 - merge_rows,
                r2 - merge_rows,
                c1 - merge_cols,
                c2 - merge_cols,
            ]
            for r1, r2, c1, c2 in _sheet_merges(self._path, name)
        ]
        grid = [[value for value in row] for row in values]
        data = _table_from_cells(grid, header_row=header_row)
        data.merges = merges
        return data


def _parse_range(cell_range: str) -> tuple[int, int, int, int]:
    match = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", cell_range.strip().upper())
    if match is None:
        raise ValueError(f"非法单元格范围：{cell_range}")
    min_col = _column_letters_to_index(match.group(1))
    min_row = int(match.group(2))
    max_col = _column_letters_to_index(match.group(3))
    max_row = int(match.group(4))
    if max_row < min_row or max_col < min_col:
        raise ValueError(f"范围顺序非法：{cell_range}")
    return min_col, min_row, max_col, max_row


def _column_letters_to_index(letters: str) -> int:
    result = 0
    for char in letters:
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result


def _sheet_merges(path: Path, sheet_name: str) -> list[list[int]]:
    """Read mergeCell ranges directly from the worksheet XML (bounded)."""

    with zipfile.ZipFile(path) as archive:
        workbook_xml = archive.read("xl/workbook.xml")
        rels_xml = archive.read("xl/_rels/workbook.xml.rels")
    namespaces = {"m": _MAIN_NS}
    workbook_root = ElementTree.fromstring(workbook_xml)
    relationship_id: str | None = None
    for sheet in workbook_root.findall("m:sheets/m:sheet", namespaces):
        if sheet.get("name") == sheet_name:
            relationship_id = sheet.get(f"{{{_REL_NS}}}id")
            break
    if relationship_id is None:
        return []
    rel_root = ElementTree.fromstring(rels_xml)
    target: str | None = None
    for relationship in rel_root:
        if relationship.get("Id") == relationship_id:
            target = relationship.get("Target")
            break
    if target is None:
        return []
    sheet_path = target.lstrip("/")
    with zipfile.ZipFile(path) as archive:
        sheet_xml = archive.read(sheet_path)
    sheet_root = ElementTree.fromstring(sheet_xml)
    merges: list[list[int]] = []
    for cell in sheet_root.findall(".//m:mergeCell", namespaces):
        parsed = _parse_cell_reference(str(cell.get("ref", "")))
        if parsed is not None:
            merges.append(parsed)
    return merges


def _parse_cell_reference(reference: str) -> list[int] | None:
    match = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", reference)
    if match is None:
        return None
    return [
        _column_letters_to_index(match.group(1)) - 1,
        int(match.group(2)) - 1,
        _column_letters_to_index(match.group(3)) - 1,
        int(match.group(4)) - 1,
    ]


def _table_from_cells(grid: list[list[object]], *, header_row: bool) -> TableData:
    if not grid:
        return TableData()
    width = min(max(len(row) for row in grid), MAX_COLS)
    if header_row:
        names = _unique_names(
            [str(cell).strip() if cell is not None else f"Col{index + 1}" for index, cell in enumerate(grid[0][:width])]
        )
        body = grid[1:]
    else:
        names = [f"Col{index + 1}" for index in range(width)]
        body = grid
    body = body[:MAX_ROWS]
    columns = [ColumnSpec(id=f"col_{index + 1}", name=name) for index, name in enumerate(names)]
    cells_grid: list[list[Cell]] = []
    for raw in body:
        padded = list(raw[:width])
        while len(padded) < width:
            padded.append(None)
        cells_grid.append([infer_cell(cell) for cell in padded])
    for column_index, column in enumerate(columns):
        values = [row[column_index] for row in cells_grid]
        columns[column_index] = column_spec_from_cells(column.id, column.name, values)
    rows = [
        TableRow(
            id=f"row_{index + 1:03d}",
            cells={column.id: cells_grid[index][column_index] for column_index, column in enumerate(columns)},
        )
        for index in range(len(cells_grid))
    ]
    return TableData(columns=columns, rows=rows, header_row_count=1 if header_row else 0)
