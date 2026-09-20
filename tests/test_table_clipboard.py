from unittest import TestCase

from app.core.table_clipboard import format_grid, parse_grid


class TableClipboardTests(TestCase):
    def test_empty_cells_and_rows_keep_their_coordinates(self):
        self.assertEqual(parse_grid("a\t\nc\td\n\t\ne\tf\n", max_rows=4, max_columns=2),
                         [["a", ""], ["c", "d"], ["", ""], ["e", "f"]])

    def test_quotes_and_newlines_round_trip(self):
        rows = [["a\tb", 'c"d'], ["line 1\nline 2", ""]]
        self.assertEqual(parse_grid(format_grid(rows), max_rows=2, max_columns=2), rows)

    def test_oversize_paste_is_rejected_not_truncated(self):
        for text in ("a\tb\tc", "a\nb\nc"):
            with self.assertRaises(ValueError):
                parse_grid(text, max_rows=2, max_columns=2)

    def test_invalid_quotes_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_grid('"unclosed', max_rows=2, max_columns=2)

    def test_plain_single_cell_is_supported(self):
        self.assertEqual(parse_grid("0", max_rows=1, max_columns=1), [["0"]])
