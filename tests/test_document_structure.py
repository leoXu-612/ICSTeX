from dataclasses import replace
from unittest import TestCase

from app.core.document_structure import (
    MAX_STRUCTURE_CHARS, delete_block, move_block, parse_structure, replace_block,
    plain_fragment, plain_fragment_source, readable_text, table_cell_ranges,
)


SAMPLE = r"""% original comment
\documentclass{ctexart}
\newcommand{\custom}[1]{\textbf{#1}}
\title{标题😀}
\begin{document}
\maketitle
\section{方法}
原始文字😀。

第二段保留 \custom{特殊宏}。
\subsection*{数据}
\begin{center}
\begin{tabular}{ll}a & b \\ c & d\end{tabular}
\end{center}
\[ E=mc^2 \]
\section{结论}
结论文字。
\end{document}
% trailing original
"""


def apply(source, edits):
    for edit in edits:
        source = source[:edit.start] + edit.text + source[edit.end:]
    return source


class DocumentStructureTests(TestCase):
    def test_structure_preserves_source_and_real_ranges(self):
        doc = parse_structure(SAMPLE)
        self.assertFalse(doc.error)
        self.assertEqual(doc.source, SAMPLE)
        self.assertEqual([b.kind for b in doc.blocks], ["title", "section", "section"])
        section = doc.blocks[1]
        self.assertEqual(section.title, "方法")
        sub = next(b for b in section.children if b.kind == "section")
        self.assertEqual(sub.title, "数据")
        self.assertEqual([b.kind for b in sub.children], ["table", "formula"])
        formula = sub.children[1]
        self.assertEqual(SAMPLE[formula.start:formula.end], r"\[ E=mc^2 \]")
        self.assertIs(doc.at(formula.start + 4), formula)

    def test_rename_only_changes_title_argument(self):
        doc = parse_structure(SAMPLE)
        block = doc.blocks[0]
        edit = replace_block(doc, SAMPLE, block, "改名😀")
        result = apply(SAMPLE, [edit])
        self.assertEqual(result, SAMPLE.replace("标题😀", "改名😀"))

    def test_move_section_preserves_subtree_comments_and_preamble(self):
        doc = parse_structure(SAMPLE)
        result = apply(SAMPLE, move_block(doc, SAMPLE, doc.blocks[1], doc.blocks[2], "after"))
        self.assertLess(result.index(r"\section{结论}"), result.index(r"\section{方法}"))
        self.assertIn(r"\subsection*{数据}", result)
        self.assertIn(r"\custom{特殊宏}", result)
        self.assertEqual(result[:doc.body_start], SAMPLE[:doc.body_start])
        self.assertTrue(result.endswith("\\end{document}\n% trailing original\n"))

    def test_nest_updates_only_heading_commands(self):
        doc = parse_structure(SAMPLE)
        result = apply(SAMPLE, move_block(doc, SAMPLE, doc.blocks[1], doc.blocks[2], "inside"))
        self.assertIn(r"\subsection{方法}", result)
        self.assertIn(r"\subsubsection*{数据}", result)
        self.assertIn(r"\newcommand{\custom}[1]{\textbf{#1}}", result)
        self.assertEqual(parse_structure(result).blocks[1].children[-1].title, "方法")

    def test_move_formula_to_section(self):
        doc = parse_structure(SAMPLE)
        formula = next(b for b in doc.walk() if b.kind == "formula")
        result = apply(SAMPLE, move_block(doc, SAMPLE, formula, doc.blocks[-1], "inside"))
        self.assertEqual(result.count("E=mc^2"), 1)
        self.assertGreater(result.index("E=mc^2"), result.index(r"\section{结论}"))

    def test_reject_own_subtree_and_invalid_parent(self):
        doc = parse_structure(SAMPLE)
        formula = next(b for b in doc.walk() if b.kind == "formula")
        for source, target in [(doc.blocks[1], formula), (formula, formula), (doc.blocks[0], doc.blocks[1])]:
            with self.assertRaises(ValueError):
                move_block(doc, SAMPLE, source, target, "inside")

    def test_stale_snapshot_and_forged_range_are_rejected(self):
        doc = parse_structure(SAMPLE)
        with self.assertRaises(ValueError):
            replace_block(doc, SAMPLE + "new", doc.blocks[0], "x")
        with self.assertRaises(ValueError):
            replace_block(doc, SAMPLE, replace(doc.blocks[0], start=0), "x")

    def test_incomplete_input_does_not_authorize_edits(self):
        for text in [r"\section{未完成", r"\begin{figure}text", r"\[ x", "{" * 2000]:
            with self.subTest(text=text[:20]):
                self.assertTrue(parse_structure(text).error)

    def test_unknown_environment_is_one_raw_block(self):
        text = r"\begin{custom}\section{not a real section}\special{stuff}\end{custom}"
        doc = parse_structure(text)
        self.assertEqual(len(doc.blocks), 1)
        self.assertEqual(doc.blocks[0].kind, "raw")
        self.assertEqual(doc.source, text)

    def test_blank_lines_in_arguments_do_not_split_blocks(self):
        text = "\\custom{line one\n\nline two}\n\nnext paragraph"
        doc = parse_structure(text)
        self.assertEqual(len(doc.blocks), 2)
        self.assertIn("line two}", text[doc.blocks[0].start:doc.blocks[0].end])

    def test_fragment_and_empty_document(self):
        self.assertFalse(parse_structure("").error)
        self.assertEqual(parse_structure("").body_end, 0)
        doc = parse_structure(r"\section{Child}hello")
        self.assertEqual(doc.blocks[0].title, "Child")
        self.assertEqual(doc.blocks[0].children[0].title, "hello")

    def test_size_ceiling_is_explicit_not_partial_success(self):
        doc = parse_structure("x" * (MAX_STRUCTURE_CHARS + 1))
        self.assertTrue(doc.error)
        self.assertFalse(doc.blocks)

    def test_dynamic_tex_stays_source_only(self):
        for text in [r"\iftrue\section{X}\fi", r"\catcode`\%=12"]:
            self.assertTrue(parse_structure(text).error)

    def test_table_preview_is_readable_without_rewriting_source(self):
        doc = parse_structure(SAMPLE)
        block = next(b for b in doc.walk() if b.kind == "table")
        self.assertEqual(block.rows, (("a", "b"), ("c", "d")))
        self.assertEqual(doc.source, SAMPLE)

    def test_delete_section_owns_subtree_but_not_following_section(self):
        doc = parse_structure(SAMPLE)
        result = apply(SAMPLE, [delete_block(doc, SAMPLE, doc.blocks[1])])
        self.assertNotIn("方法", result)
        self.assertNotIn("E=mc", result)
        self.assertIn(r"\section{结论}", result)
        self.assertEqual(result[:doc.body_start], SAMPLE[:doc.body_start])
        self.assertFalse(parse_structure(result).error)
        with self.assertRaises(ValueError):
            delete_block(doc, SAMPLE + "new", doc.blocks[1])

    def test_clearing_title_keeps_maketitle_valid(self):
        doc = parse_structure(SAMPLE)
        result = apply(SAMPLE, [delete_block(doc, SAMPLE, doc.blocks[0])])
        self.assertIn(r"\title{}", result)
        self.assertIn(r"\maketitle", result)

    def test_plain_text_roundtrip_and_visible_line_breaks(self):
        text = "第一行😀\n第二行 & 50%\n\n另起一段 #$_{}~^\\"
        encoded = plain_fragment_source(text)
        self.assertIn("\\\\\n", encoded)
        self.assertEqual(plain_fragment(encoded), text)
        self.assertIn("第一行😀\n", readable_text(encoded))
        self.assertEqual(parse_structure(encoded).blocks[0].kind, "text")
        self.assertIn(r"\textbackslash{}", encoded)
        self.assertNotIn(r"\textbackslash\{", encoded)
        self.assertIsNone(plain_fragment(r"Hello \textbf{bold}"))
        self.assertIsNone(plain_fragment(r"$x+1$"))
        for leading in ("\n", "\n文字", "\n\n\n文字", " \n文字"):
            encoded = plain_fragment_source(leading)
            self.assertIn(r"\leavevmode{}", encoded)
            self.assertEqual(plain_fragment(encoded), leading)

    def test_table_spans_preserve_caption_rules_comments_and_empty_cells(self):
        text = r"""\begin{table}
\caption{Keep me}\label{tab:keep}
\begin{tabular}{ll}
% keep this comment
\toprule
A & B \\
\midrule
 & $x+1$ \\
\bottomrule
\end{tabular}
\end{table}"""
        doc = parse_structure(text)
        spans = table_cell_ranges(text, doc.blocks[0])
        self.assertEqual([[text[a:b] for a, b in row] for row in spans], [["A", "B"], ["", "$x+1$"]])
        start, end = spans[1][0]
        result = text[:start] + "123" + text[end:]
        self.assertEqual(result.replace("123", "", 1), text)
        self.assertFalse(parse_structure(result).error)

    def test_complex_or_ragged_table_is_not_flattened(self):
        for body in [r"\multicolumn{2}{c}{joined} \\", r"a & b \\ c & d & e",
                     "a %inside cell\n & b", r"a & \begin{tabular}{l}b\end{tabular}"]:
            text = r"\begin{tabular}{ll}" + body + r"\end{tabular}"
            self.assertEqual(table_cell_ranges(text, parse_structure(text).blocks[0]), ())
