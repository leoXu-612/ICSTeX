from unittest import TestCase

from app.core.citation_syntax import parse_bibliography, scan_citation_uses


class CitationSyntaxTests(TestCase):
    def test_optional_arguments_stars_case_and_multiple_keys_have_lines(self):
        text = "Text\n\\cite*[see][p. {3}]{Known,Missing}\n\\Textcite{Other}\n"
        result = scan_citation_uses(text)
        self.assertEqual([(use.key, use.line) for use in result.uses], [("Known", 2), ("Missing", 2), ("Other", 3)])
        self.assertTrue(result.complete)

    def test_comments_inline_and_block_verbatim_are_not_citations(self):
        result = scan_citation_uses(
            "% \\cite{Comment}\n\\verb|\\cite{Inline}|\n"
            "\\begin{verbatim}\n\\cite{Block}\n\\end{verbatim}\n\\cite{Real}\n")
        self.assertEqual([(use.key, use.line) for use in result.uses], [("Real", 6)])

    def test_nocite_all_is_not_a_missing_star(self):
        result = scan_citation_uses(r"\nocite{*}\nocite{Manual}")
        self.assertTrue(result.include_all)
        self.assertEqual([use.key for use in result.uses], ["Manual"])

    def test_definitions_dynamic_and_unsupported_multi_cites_are_unknown(self):
        for text in (r"\newcommand{\mycite}[1]{\cite{#1}}",
                     r"\def\mycite#1{\cite{#1}}", r"\cite{\computed}",
                     r"\cites{One}{Two}", r"\cite[not closed{Key}"):
            with self.subTest(text=text):
                result = scan_citation_uses(text)
                self.assertFalse(result.complete)
                self.assertTrue(result.issues)
                self.assertEqual(result.uses, ())

    def test_bib_keeps_duplicates_and_accepts_legal_expressions(self):
        text = ('@STRING( WGA = "World Gnus" )\n'
                '@preamble{"\\newcommand{\\noop}[1]{}" # " "}\n'
                '@article{Same, title={First {Nested}}, month="1~" # jan, year=2026}\n'
                '@book(Same, title=1967 # WGA, author="Kurt G{\\\"o}del")\n')
        result = parse_bibliography(text)
        self.assertEqual([(entry.key, entry.line) for entry in result.entries], [("Same", 3), ("Same", 4)])
        self.assertTrue(result.complete, result.issues)
        self.assertEqual(dict(result.entries[1].fields)["title"], "1967 # WGA")

    def test_bib_percent_is_not_tex_comment_and_comment_command_is_skipped(self):
        text = ("@comment{  A comment with {nested} braces and @book{NotAnEntry,x={X}}}\n"
                "% @article{Actual, title={100% original}}\n")
        result = parse_bibliography(text)
        self.assertTrue(result.complete, result.issues)
        self.assertEqual([entry.key for entry in result.entries], ["Actual"])
        self.assertIn("100% original", dict(result.entries[0].fields)["title"])

    def test_bib_malformed_field_duplicate_field_and_unclosed_value_report_unknown(self):
        for body in ("title {No equal}", "title={A},title={B}", "title={Unclosed"):
            with self.subTest(body=body):
                result = parse_bibliography("@article{Key," + body + "}")
                self.assertFalse(result.complete)
                self.assertTrue(result.issues)

    def test_parser_limits_never_silently_pass(self):
        result = parse_bibliography("@article{A,title={A}}\n@article{B,title={B}}", max_items=1)
        self.assertFalse(result.complete)
        self.assertLessEqual(len(result.entries), 1)
        result = scan_citation_uses(r"\cite{A,B,C}", max_items=2)
        self.assertFalse(result.complete)
        self.assertLessEqual(len(result.uses), 2)

    def test_many_unknown_commands_and_fields_are_bounded(self):
        result = scan_citation_uses(r"\weirdcite{K}" * 20, max_items=2)
        self.assertFalse(result.complete)
        self.assertLessEqual(len(result.issues), 3)
        result = parse_bibliography("@article{A,title={T},author={A},year={2026}}", max_items=2)
        self.assertFalse(result.complete)
        self.assertIn("field limit", result.issues[0].message)
