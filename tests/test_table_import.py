from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.blocks.table_import import (
    SpreadsheetImportAdapter,
    parse_clipboard,
    read_csv_bytes,
    read_csv_text,
)


class CsvAdapterTests(TestCase):
    def test_rfc4180_quotes_and_multiline_fields(self) -> None:
        text = 'name,note\n"Alice","line1\nline2"\n"Bob","said ""hi"""\n'
        data = read_csv_text(text)
        self.assertEqual(data.column_ids(), ["col_1", "col_2"])
        self.assertEqual(data.rows[0].cells["col_2"].value, "line1\nline2")
        self.assertEqual(data.rows[1].cells["col_2"].value, 'said "hi"')

    def test_type_inference_and_empty_values(self) -> None:
        text = "温度,备注\n20,基准\n1.5,\n,缺失\n"
        data = read_csv_text(text)
        self.assertEqual(data.columns[0].dataType, "number")
        self.assertEqual(data.columns[1].dataType, "text")
        self.assertEqual(data.cell("row_001", "col_1").value, 20)
        self.assertEqual(data.cell("row_002", "col_2").kind, "empty")

    def test_ragged_rows_are_padded(self) -> None:
        text = "a,b,c\n1,2\n3,4,5,6\n"
        data = read_csv_text(text)
        self.assertEqual(data.rows[0].cells["col_3"].kind, "empty")
        self.assertEqual(data.rows[1].cells["col_3"].value, 5)
        self.assertEqual(data.rows[1].cells["col_3"].kind, "number")

    def test_encoding_detection(self) -> None:
        utf8_bom = "温度\n20\n".encode("utf-8-sig")
        self.assertEqual(read_csv_bytes(utf8_bom).columns[0].name, "温度")
        gbk = "温度\n20\n".encode("gbk")
        self.assertEqual(read_csv_bytes(gbk).columns[0].name, "温度")


class ClipboardAdapterTests(TestCase):
    def test_tsv_rectangle(self) -> None:
        text = "A\tB\n1\t2\n3\t4\n"
        data = parse_clipboard(text)
        assert data is not None
        self.assertEqual(len(data.rows), 3)
        self.assertEqual(data.rows[2].cells["col_2"].value, 4)

    def test_html_table(self) -> None:
        text = "<table><tr><td>1</td><td>2</td></tr><tr><td>3</td><td>4</td></tr></table>"
        data = parse_clipboard(text)
        assert data is not None
        self.assertEqual(len(data.rows), 2)
        self.assertEqual(data.rows[0].cells["col_2"].value, 2)


class SpreadsheetAdapterTests(TestCase):
    def test_multi_sheet_range_header_dates_and_merges(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "book.xlsx"
            import openpyxl

            workbook = openpyxl.Workbook()
            first = workbook.active
            first.title = "Experiment 1"
            first.append(["温度", "反应速率"])
            first.append([20, 1.25])
            first.append([datetime(2024, 1, 2), None])
            first.merge_cells("A1:B1")
            second = workbook.create_sheet("Notes")
            second.append(["x", "y"])
            workbook.save(str(path))

            adapter = SpreadsheetImportAdapter(path)
            self.assertEqual(adapter.sheet_names(), ["Experiment 1", "Notes"])
            data = adapter.read_sheet("Experiment 1")
            self.assertEqual(data.columns[0].name, "温度")
            # 数字与日期混合 -> 保守推断为 text，具体单元格保留各自类型。
            self.assertEqual(data.columns[0].dataType, "text")
            self.assertEqual(data.cell("row_001", "col_1").kind, "number")
            self.assertEqual(data.cell("row_002", "col_1").kind, "date")
            self.assertEqual(len(data.merges), 1)

            ranged = adapter.read_sheet("Experiment 1", cell_range="A1:B2", header_row=True)
            self.assertEqual(len(ranged.rows), 1)
            self.assertEqual(ranged.rows[0].cells["col_2"].value, 1.25)

            notes = adapter.read_sheet("Notes", header_row=False)
            self.assertEqual(notes.rows[0].cells["col_1"].value, "x")

    def test_formula_cells_are_not_executed(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "formula.xlsx"
            import openpyxl

            workbook = openpyxl.Workbook()
            sheet = workbook.active
            sheet["A1"] = 1
            sheet["B1"] = 2
            sheet["C1"] = "=A1+B1"
            workbook.save(str(path))

            data = SpreadsheetImportAdapter(path).read_sheet(workbook.active.title, header_row=False)

            # openpyxl read-only with data_only=True returns no cached value for
            # an uncalculated formula; it must never be evaluated to 3.
            self.assertNotEqual(data.rows[0].cells["col_3"].value, 3)
            self.assertEqual(data.rows[0].cells["col_3"].kind, "empty")

    def test_unsupported_sheet_raises(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "book.xlsx"
            import openpyxl

            workbook = openpyxl.Workbook()
            workbook.save(str(path))
            with self.assertRaises(ValueError):
                SpreadsheetImportAdapter(path).read_sheet("Nope")
