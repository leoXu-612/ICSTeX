"""Build stdout is a self-reported version source, never binary attestation."""
from unittest import TestCase

from app.core.build_tool_versions import capture_tool_versions, MAX_BANNER_CHARS
from app.core.latex_tools import LaTeXEngine


PDF = "This is pdfTeX, Version 3.141592653-2.6-1.40.27 (TeX Live 2025) (preloaded format=pdflatex)"
XE = "This is XeTeX, Version 3.141592653-2.6-0.999997 (TeX Live 2025) (preloaded format=xelatex)"
DRIVER = "Rc files read:\n  NONE\nLatexmk: This is Latexmk, John Collins, 27 Dec. 2024. Version 4.86a.\n"


def wrapped(banner=PDF, command="pdflatex"):
    return DRIVER + f"Latexmk: applying rule '{command}'...\n------------\nRunning '{command} -no-shell-escape main.tex'\n------------\n{banner}\nentering extended mode\n(./main.tex\n"


class BuildToolVersionTests(TestCase):
    def test_latexmk_first_engine_banner_is_bound_to_selected_engine(self):
        for engine, command, banner, program in (
            (LaTeXEngine.AUTO, "pdflatex", PDF, "pdfTeX"),
            (LaTeXEngine.PDFLATEX, "pdflatex", PDF, "pdfTeX"),
            (LaTeXEngine.XELATEX, "xelatex", XE, "XeTeX"),
            (LaTeXEngine.LUALATEX, "lualatex", "This is LuaHBTeX, Version 1.22.0 (TeX Live 2025)", "LuaHBTeX"),
        ):
            with self.subTest(engine=engine):
                value = capture_tool_versions(wrapped(banner, command), engine, via_latexmk=True)
                self.assertEqual(value.driver.version, "4.86a")
                self.assertEqual(value.engine.program, program)
                self.assertEqual(value.engine.distribution, "TeX Live 2025")
                self.assertFalse(value.truncated)

    def test_direct_engine_does_not_invent_driver(self):
        value = capture_tool_versions(PDF + "\n(./main.tex", LaTeXEngine.PDFLATEX, via_latexmk=False)
        self.assertIsNone(value.driver)
        self.assertEqual(value.engine.version, "3.141592653-2.6-1.40.27")
        self.assertIsNone(capture_tool_versions(XE, LaTeXEngine.PDFLATEX, via_latexmk=False).engine)

    def test_missing_or_document_body_banners_remain_unknown(self):
        for stdout in ("", "(./main.tex\n" + PDF, "wrapper warning\n" + PDF):
            with self.subTest(stdout=stdout):
                self.assertIsNone(capture_tool_versions(stdout, LaTeXEngine.AUTO, via_latexmk=False).engine)
        for stdout in (DRIVER + PDF, wrapped("unrecognized banner") + PDF,
                       wrapped(XE), wrapped(PDF, "xelatex")):
            with self.subTest(stdout=stdout):
                self.assertIsNone(capture_tool_versions(stdout, LaTeXEngine.AUTO, via_latexmk=True).engine)

    def test_later_document_output_never_replaces_first_banner(self):
        value = capture_tool_versions(wrapped() + wrapped(XE, "xelatex"), LaTeXEngine.AUTO, via_latexmk=True)
        self.assertEqual(value.engine.program, "pdfTeX")
        self.assertEqual(value.driver.version, "4.86a")

    def test_capture_is_bounded_and_truncated_banner_is_not_accepted(self):
        text = "x" * MAX_BANNER_CHARS + wrapped()
        value = capture_tool_versions(text, LaTeXEngine.AUTO, via_latexmk=True)
        self.assertTrue(value.truncated)
        self.assertIsNone(value.driver)
        self.assertIsNone(value.engine)
        prefix = "\n" * (MAX_BANNER_CHARS - 5)
        self.assertIsNone(capture_tool_versions(prefix + PDF, LaTeXEngine.AUTO, via_latexmk=False).engine)

    def test_only_safe_tokens_not_banner_paths_are_retained(self):
        value = capture_tool_versions(PDF + " /Users/private/student-name\n", LaTeXEngine.AUTO, via_latexmk=False)
        self.assertNotIn("private", repr(value))
        self.assertEqual(value.engine.distribution, "TeX Live 2025")
        for version in ("/Users/private", "1.2/private", "1" * 100):
            text = "This is pdfTeX, Version " + version
            self.assertIsNone(capture_tool_versions(text, LaTeXEngine.AUTO, via_latexmk=False).engine)
