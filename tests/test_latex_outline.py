from unittest import TestCase

from app.core.latex_outline import scan_outline


class LatexOutlineTests(TestCase):
    def test_scan_outline_ignores_comments_and_keeps_lines(self) -> None:
        items = scan_outline(
            "\\section{Intro}\n"
            "% \\section{Hidden}\n"
            "\\subsection[Short]{Method \\textbf{Setup}}\n"
        )

        self.assertEqual([item.title for item in items], ["Intro", "Method Setup"])
        self.assertEqual([item.line for item in items], [1, 3])
        self.assertEqual([item.command for item in items], ["section", "subsection"])
