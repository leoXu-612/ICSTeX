from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from app.gui.bib_helpers import bib_text_for_tab


class BibReadHelperTests(TestCase):
    def test_conventional_shortcut_read_rejects_links_and_oversize_input(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as external:
            scope = Path(directory).resolve()
            tab = SimpleNamespace(path=scope / "main.tex")
            bib = scope / "references.bib"
            bib.write_text("@book{Local,title={Synthetic}}")
            self.assertIn("Local", bib_text_for_tab(tab))
            bib.unlink()
            secret = Path(external) / "secret.bib"
            secret.write_text("@book{Outside,title={Synthetic}}")
            bib.symlink_to(secret)
            self.assertEqual(bib_text_for_tab(tab), "")
            bib.unlink()
            with bib.open("wb") as stream:
                stream.truncate(4 * 1024 * 1024 + 1)
            self.assertEqual(bib_text_for_tab(tab), "")

    def test_strict_decode_does_not_invent_replacement_characters(self):
        with TemporaryDirectory() as directory:
            scope = Path(directory).resolve()
            bib = scope / "references.bib"
            bib.write_bytes(b"\xff\x80\xff")
            self.assertEqual(bib_text_for_tab(SimpleNamespace(path=scope / "main.tex")), "")
