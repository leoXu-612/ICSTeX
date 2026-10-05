from dataclasses import replace
from unittest import TestCase

from app.core.document_structure import parse_structure, table_cell_ranges
from app.core.latex_insertions import TableSpec, table_snippet
from app.core.source_table import change_source_table, read_source_table


class SourceTableTests(TestCase):
    def fixture(self, spec=None):
        return ("\\documentclass{article}\n\\usepackage{booktabs}\n\\begin{document}\nKeep before.\n" +
                table_snippet(spec or TableSpec(caption="Old caption", label="tab:keep")) +
                "\nKeep after.\n\\end{document}\n")

    def block(self, source):
        return next(b for b in parse_structure(source).walk() if b.kind == "table")

    def change(self, source, **changes):
        block = self.block(source)
        model = read_source_table(source, block)
        edits = change_source_table(source, block, replace(model.spec, **changes))
        for edit in sorted(edits, key=lambda e: e.start, reverse=True):
            source = source[:edit.start] + edit.text + source[edit.end:]
        self.assertFalse(parse_structure(source).error)
        return source

    def test_expand_preserves_all_original_cells_and_surrounding_text(self):
        source = self.fixture()
        block = self.block(source)
        result = self.change(source, rows=5, columns=4)
        new_block = self.block(result)
        self.assertEqual(result[:new_block.start], source[:block.start])
        self.assertEqual(result[new_block.end:], source[block.end:])
        model = read_source_table(result, new_block)
        self.assertEqual((model.spec.rows, model.spec.columns), (5, 4))
        self.assertEqual(model.spec.cells[0], ("Cell 1-1", "Cell 1-2", "Cell 1-3", ""))
        self.assertEqual(model.spec.cells[-1], ("", "", "", ""))
        self.assertIn(r"\caption{Old caption}", result)
        self.assertIn(r"\label{tab:keep}", result)

    def test_shrink_retains_top_left_data_and_changes_only_target(self):
        result = self.change(self.fixture(), rows=1, columns=2)
        model = read_source_table(result, self.block(result))
        self.assertEqual(model.spec.headers, ("Header 1", "Header 2"))
        self.assertEqual(model.spec.cells, (("Cell 1-1", "Cell 1-2"),))

    def test_alignment_only_keeps_original_body_bytes(self):
        source = self.fixture()
        model = read_source_table(source, self.block(source))
        result = self.change(source, alignment="r")
        self.assertEqual(result, source[:model.column_span[0]] + "rrr" + source[model.column_span[1]:])

    def test_metadata_add_and_update_preserve_caption_commands_and_position(self):
        source = self.fixture(TableSpec(caption="", label=""))
        result = self.change(source, caption="Measured", label="tab:new", placement="t")
        model = read_source_table(result, self.block(result))
        self.assertEqual((model.spec.caption, model.spec.label, model.spec.placement), ("Measured", "tab:new", "t"))
        self.assertIn("Measured", self.change(result, rows=2))

    def test_packages_are_local_and_join_the_same_plan(self):
        source = self.fixture(TableSpec(use_booktabs=False)).replace("\\usepackage{booktabs}\n", "")
        result = self.change(source, use_booktabs=True, placement="H")
        self.assertEqual(result.count(r"\usepackage{booktabs}"), 1)
        self.assertEqual(result.count(r"\usepackage{float}"), 1)
        self.assertIn(r"\toprule", result)
        fragment = source[self.block(source).start:self.block(source).end]
        with self.assertRaisesRegex(ValueError, "主文件"):
            self.change(fragment, use_booktabs=True)

    def test_comments_and_custom_columns_are_not_silently_rewritten(self):
        for source in [self.fixture().replace(r"\toprule", "% keep me\n\\toprule"),
                       self.fixture().replace("{ccc}", "{p{2cm}cc}")]:
            self.assertIsNone(read_source_table(source, self.block(source)))

    def test_plain_mixed_columns_and_cell_math_are_retained(self):
        source = r"\begin{center}\begin{tabular}{|lc|}A & B \\ $x&y$ & \textbf{keep}\end{tabular}\end{center}"
        model = read_source_table(source, self.block(source))
        self.assertEqual(model.spec.alignment, "mixed")
        result = self.change(source, rows=2, columns=3)
        self.assertIn("{lcc}", result.replace("|", ""))
        self.assertIn(r"\textbf{keep}", result)
        self.assertIn(r"$x&y$", result)
        self.assertNotIn(r"\hline", result)

    def test_identical_spec_has_no_writes(self):
        source = self.fixture()
        block = self.block(source)
        self.assertEqual(change_source_table(source, block, read_source_table(source, block).spec), [])

    def test_clear_and_restore_caption_keeps_label_after_caption(self):
        source = self.fixture()
        cleared = self.change(source, caption="")
        self.assertNotIn(r"\caption{", cleared)
        self.assertIn(r"\label{tab:keep}", cleared)
        restored = self.change(cleared, caption="Restored")
        self.assertLess(restored.index(r"\caption{Restored}"), restored.index(r"\label{tab:keep}"))
        cleared_label = self.change(restored, label="")
        self.assertNotIn(r"\label{", cleared_label)

    def test_commented_documentclass_does_not_authorize_package_in_child(self):
        table = table_snippet(TableSpec(use_booktabs=False))
        source = "% \\documentclass{article}\n" + table
        with self.assertRaisesRegex(ValueError, "主文件"):
            self.change(source, use_booktabs=True)

    def test_partial_cell_formula_returns_no_spec(self):
        source = r"\begin{tabular}{ll}A&B\\ $unfinished & c\end{tabular}"
        from app.core.document_structure import SourceBlock
        self.assertIsNone(read_source_table(source, SourceBlock("table", 0, len(source), "")))
