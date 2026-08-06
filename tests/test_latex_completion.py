from unittest import TestCase

from app.core.latex_completion import completion_context


class LatexCompletionTests(TestCase):
    def test_command_completion_matches_prefix(self) -> None:
        context = completion_context("\\sec")

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(context.replacement_length, 4)
        self.assertIn("\\section{}", [candidate.display for candidate in context.candidates])

    def test_label_completion_uses_labels_inside_ref(self) -> None:
        context = completion_context("\\ref{sec", labels=["sec:intro", "fig:setup"])

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual([candidate.display for candidate in context.candidates], ["sec:intro"])
        self.assertEqual(context.replacement_length, 3)

    def test_citation_completion_uses_bib_keys_inside_cite(self) -> None:
        context = completion_context("\\cite{Sto", citations=["CIE2024", "Storm2024"])

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual([candidate.insertion for candidate in context.candidates], ["Storm2024"])
