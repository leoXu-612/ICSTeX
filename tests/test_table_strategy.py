from __future__ import annotations

from unittest import TestCase

from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow
from app.core.blocks.table_strategy import select_strategy


def short_table() -> TableData:
    return TableData(
        columns=[
            ColumnSpec(id="col_t", name="温度", dataType="number", unit=r"\celsius"),
            ColumnSpec(id="col_n", name="备注", dataType="text"),
        ],
        rows=[
            TableRow(id="row_001", cells={"col_t": Cell(kind="number", value=20), "col_n": Cell(kind="text", value="基准组")}),
        ],
        header_row_count=1,
    )


class TableStrategyTests(TestCase):
    def test_short_table_uses_booktabs_tabular(self) -> None:
        strategy = select_strategy(short_table())
        self.assertEqual(strategy.strategy, "tabular")
        self.assertTrue(strategy.needs_siunitx)
        self.assertEqual(strategy.column_layouts[0].mode, "siunitx")
        self.assertEqual(strategy.column_layouts[0].format, "2.0")
        self.assertEqual(strategy.column_layouts[1].mode, "content")

    def test_long_text_column_uses_tabularx(self) -> None:
        table = short_table()
        table.rows[0].cells["col_n"] = Cell(kind="text", value="x" * 60)
        strategy = select_strategy(table)
        self.assertEqual(strategy.strategy, "tabularx")
        self.assertEqual(strategy.column_layouts[1].mode, "flex")

    def test_allow_page_break_uses_longtable(self) -> None:
        strategy = select_strategy(short_table(), allow_page_break=True)
        self.assertEqual(strategy.strategy, "longtable")

    def test_longtable_in_box_is_blocking(self) -> None:
        strategy = select_strategy(short_table(), allow_page_break=True, in_box=True)
        self.assertTrue(any("ICSTEX_TABLE_LONGTABLE_BOXED" in issue for issue in strategy.issues))

    def test_longtable_with_long_text_uses_p_columns(self) -> None:
        table = short_table()
        table.rows[0].cells["col_n"] = Cell(kind="text", value="y" * 50)
        strategy = select_strategy(table, allow_page_break=True)
        self.assertEqual(strategy.column_layouts[1].mode, "p")

    def test_wide_table_reports_warning(self) -> None:
        table = short_table()
        table.rows[0].cells["col_n"] = Cell(kind="text", value="z" * 120)
        strategy = select_strategy(table, available_width_pt=80.0)
        self.assertTrue(any("ICSTEX_TABLE_WIDE" in issue for issue in strategy.issues))
