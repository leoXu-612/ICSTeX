from unittest import TestCase

from app.core.latex_completion import COMMANDS, completion_context


class LatexCompletionTests(TestCase):
    def test_command_completion_matches_prefix(self) -> None:
        context = completion_context("\\sec")

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(context.replacement_length, 4)
        self.assertIn("\\section{}", [candidate.display for candidate in context.candidates])

    def test_text_completion_exposes_common_variants_with_exact_text_first(self) -> None:
        context = completion_context("\\text")

        self.assertIsNotNone(context)
        assert context is not None
        displays = [candidate.display for candidate in context.candidates]
        self.assertEqual(displays[0], "\\text{}")
        self.assertIn("\\textbf{}", displays)
        self.assertIn("\\textit{}", displays)
        self.assertIn("\\textcolor{}{}", displays)
        self.assertIn("\\textsuperscript{}", displays)
        self.assertLessEqual(len(displays), 12)

    def test_textcolor_places_cursor_in_color_argument(self) -> None:
        context = completion_context("\\textc")

        self.assertIsNotNone(context)
        assert context is not None
        candidate = next(item for item in context.candidates if item.display == "\\textcolor{}{}")
        self.assertEqual(candidate.insertion, "\\textcolor{}{}")
        self.assertEqual(candidate.cursor_offset, len("\\textcolor{"))

    def test_common_command_categories_are_available(self) -> None:
        displays = {candidate.display for candidate in COMMANDS}

        self.assertTrue(
            {
                "\\chapter{}",
                "\\input{}",
                "\\pageref{}",
                "\\footnote{}",
                "\\operatorname{}",
                "\\qty{}{}",
                "\\addbibresource{}",
            }.issubset(displays)
        )
        self.assertEqual(len(displays), len(COMMANDS))

    def test_existing_trailing_whitespace_templates_keep_clean_labels(self) -> None:
        by_display = {candidate.display: candidate for candidate in COMMANDS}

        self.assertEqual(by_display["\\item"].insertion, "\\item ")
        self.assertEqual(by_display["\\item"].cursor_offset, len("\\item "))
        self.assertEqual(by_display["\\centering"].insertion, "\\centering\n")
        self.assertEqual(by_display["\\centering"].cursor_offset, len("\\centering\n"))

    def test_label_completion_uses_labels_inside_ref(self) -> None:
        context = completion_context("\\ref{sec", labels=["sec:intro", "fig:setup"])

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual([candidate.display for candidate in context.candidates], ["sec:intro"])
        self.assertEqual(context.replacement_length, 3)

    def test_pageref_completion_uses_known_labels(self) -> None:
        context = completion_context("\\pageref{fig", labels=["sec:intro", "fig:setup"])

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual([candidate.display for candidate in context.candidates], ["fig:setup"])

    def test_citation_completion_uses_bib_keys_inside_cite(self) -> None:
        context = completion_context("\\cite{Sto", citations=["CIE2024", "Storm2024"])

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual([candidate.insertion for candidate in context.candidates], ["Storm2024"])
