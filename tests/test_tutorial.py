from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.tutorial import INITIAL_TITLE, TutorialStep, create_example, existing_example, title_span, tutorial_step


class TutorialRulesTests(TestCase):
    def test_creation_is_a_new_existing_template_project_and_never_overwrites(self):
        with TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            first = create_example(base)
            self.assertIn(INITIAL_TITLE, first.read_text())
            first.write_text("owned edited exercise")
            second = create_example(base)
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_text(), "owned edited exercise")
            self.assertEqual(existing_example(base, str(first)), first)
            self.assertTrue((second.parent / "bib/references.bib").is_file())

    def test_resuming_rejects_outside_missing_and_symlink_paths(self):
        with TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            base = home / "tutorials"
            root = create_example(base)
            outside = home / "main.tex"
            outside.write_text("original student fixture")
            self.assertIsNone(existing_example(base, str(outside)))
            self.assertIsNone(existing_example(base, None))
            root.unlink()
            self.assertIsNone(existing_example(base, str(root)))
            root.symlink_to(outside)
            self.assertIsNone(existing_example(base, str(root)))
            self.assertEqual(outside.read_text(), "original student fixture")

    def test_progress_requires_an_edit_manual_attempt_and_current_pdf(self):
        def stage(text, manual=True, current=True, seen=True):
            return tutorial_step(text, manual_requested=manual, current_pdf=current, acknowledged=seen)
        self.assertEqual(stage(""), TutorialStep.EDIT)
        self.assertEqual(stage("% \\title{Different}"), TutorialStep.EDIT)
        self.assertEqual(stage("\\title{" + INITIAL_TITLE + "}"), TutorialStep.EDIT)
        self.assertEqual(stage("\\title{}"), TutorialStep.EDIT)
        source = "\\title{My first page}"
        self.assertEqual(stage(source, manual=False), TutorialStep.COMPILE)
        self.assertEqual(stage(source, current=False), TutorialStep.COMPILE)
        self.assertEqual(stage(source, seen=False), TutorialStep.VIEW)
        self.assertEqual(stage(source), TutorialStep.DONE)

    def test_title_selection_returns_exact_python_boundaries(self):
        source = "% \U0001f600\n\\title{A title}\n"
        start, end = title_span(source)
        self.assertEqual(source[start:end], "A title")
