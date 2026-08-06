from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.core.latex_tools import LaTeXToolchain
from app.core.synctex import (
    SyncPosition,
    _float_or_none,
    _int_or_none,
    _parse_synctex_output,
    pdf_to_source,
    source_to_pdf,
)


def _toolchain(synctex: str | None) -> LaTeXToolchain:
    return LaTeXToolchain(latexmk=None, pdflatex=None, synctex=synctex)


class ParseOutputTests(TestCase):
    def test_view_style_output(self) -> None:
        output = "Page:3\nx:120.5\ny:640\nbefore stuff\n"
        position = _parse_synctex_output(
            output, fallback_file=Path("/tmp/main.tex"), fallback_line=12
        )
        assert position is not None
        self.assertEqual(position.page, 3)
        self.assertEqual(position.x, 120.5)
        self.assertEqual(position.y, 640.0)
        # No line/file in view output, so falls back.
        self.assertEqual(position.line, 12)
        self.assertEqual(position.file, Path("/tmp/main.tex").resolve())

    def test_edit_style_output(self) -> None:
        output = "Input:/home/u/main.tex\nLine:42\nColumn:-1\n"
        position = _parse_synctex_output(output)
        assert position is not None
        self.assertEqual(position.line, 42)
        self.assertEqual(position.file, Path("/home/u/main.tex").expanduser().resolve())

    def test_missing_file_without_fallback_returns_none(self) -> None:
        self.assertIsNone(_parse_synctex_output("Line:7\n"))

    def test_missing_line_without_fallback_returns_none(self) -> None:
        self.assertIsNone(_parse_synctex_output("Input:/home/u/main.tex\n"))

    def test_fallback_line_used_when_line_unparseable(self) -> None:
        position = _parse_synctex_output(
            "Input:/home/u/main.tex\nLine:notanumber\n", fallback_line=9
        )
        assert position is not None
        self.assertEqual(position.line, 9)


class HelperTests(TestCase):
    def test_int_or_none(self) -> None:
        self.assertIsNone(_int_or_none(None))
        self.assertIsNone(_int_or_none(""))
        self.assertEqual(_int_or_none("page 3 of 5"), 3)
        self.assertEqual(_int_or_none("-12pt"), -12)

    def test_float_or_none(self) -> None:
        self.assertIsNone(_float_or_none(None))
        self.assertEqual(_float_or_none("120.5px"), 120.5)
        self.assertEqual(_float_or_none("-3"), -3.0)


class InvocationTests(TestCase):
    def test_source_to_pdf_builds_view_args(self) -> None:
        captured: dict[str, list[str]] = {}

        class FakeProcess:
            stdout = "Page:2\nx:1\ny:2\n"

        def fake_run(cmd, *args, **kwargs):
            captured["cmd"] = cmd
            return FakeProcess()

        with patch("app.core.synctex.subprocess.run", side_effect=fake_run):
            position = source_to_pdf(
                "/tmp/main.tex", 15, "/tmp/main.pdf", _toolchain("/usr/bin/synctex")
            )

        assert position is not None
        self.assertEqual(position.page, 2)
        self.assertEqual(
            captured["cmd"],
            ["/usr/bin/synctex", "view", "-i", "15:1:/tmp/main.tex", "-o", "/tmp/main.pdf"],
        )

    def test_source_to_pdf_without_synctex_returns_none(self) -> None:
        self.assertIsNone(
            source_to_pdf("/tmp/main.tex", 1, "/tmp/main.pdf", _toolchain(None))
        )

    def test_pdf_to_source_without_synctex_returns_none(self) -> None:
        self.assertIsNone(pdf_to_source("/tmp/main.pdf", 1, 0.0, 0.0, _toolchain(None)))
