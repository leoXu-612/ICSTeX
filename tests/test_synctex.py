from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.latex_tools import LaTeXToolchain
from app.core.synctex import (
    SyncPosition,
    _float_or_none,
    _int_or_none,
    _parse_synctex_output,
    pdf_to_source,
    safe_source_position,
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

    def test_reverse_relative_input_uses_original_source_directory(self) -> None:
        root_dir = Path("/project/paper")
        with patch("app.core.synctex._run_synctex", return_value="Input:chapters/body.tex\nLine:7\n"):
            position = pdf_to_source(
                "/project/paper/.icstex/preview/key/build/main.pdf", 1, 10, 20,
                _toolchain("synctex"), source_directory=root_dir,
            )
        self.assertEqual(position, SyncPosition(root_dir / "chapters/body.tex", 7))

    def test_scoped_reverse_lookup_rejects_malformed_line(self) -> None:
        self.assertIsNone(_parse_synctex_output(
            "Input:body.tex\nLine:not-a-line\n", source_directory=Path("/project"),
        ))


class SourceBoundaryTests(TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.scope = self.directory / "project"
        self.scope.mkdir()
        self.source = self.scope / "body.tex"
        self.source.write_text("original source", encoding="utf-8")

    def test_existing_project_source_keeps_line_and_metadata(self) -> None:
        position = SyncPosition(self.source, 7, page=2, x=3, y=4)
        self.assertEqual(safe_source_position(position, self.scope), position)

    def test_unsafe_missing_generated_and_non_source_targets_are_rejected(self) -> None:
        outside = self.directory / "other.tex"
        outside.write_text("outside", encoding="utf-8")
        generated = self.scope / ".icstex" / "generated.tex"
        generated.parent.mkdir()
        generated.write_text("generated", encoding="utf-8")
        image = self.scope / "image.png"
        image.write_bytes(b"not a source")
        directory = self.scope / "directory.tex"
        directory.mkdir()
        for source in (outside, generated, image, directory, self.scope / "missing.tex"):
            with self.subTest(source=source):
                self.assertIsNone(safe_source_position(SyncPosition(source, 1), self.scope))
        self.assertIsNone(safe_source_position(SyncPosition(self.source, 0), self.scope))
        self.assertIsNone(safe_source_position(SyncPosition(self.scope / "invalid\x00.tex", 1), self.scope))

    def test_scoped_parsing_preserves_symlink_for_rejection(self) -> None:
        link = self.scope / "link.tex"
        try:
            link.symlink_to(self.source)
        except OSError as exc:
            self.skipTest(f"Symbolic links unavailable: {exc}")
        position = _parse_synctex_output(
            f"Input:{link}\nLine:1\n", source_directory=self.scope,
        )
        assert position is not None
        self.assertEqual(position.file, link)
        self.assertIsNone(safe_source_position(position, self.scope))
        directory_link = self.scope / "linked"
        directory_link.symlink_to(self.scope, target_is_directory=True)
        self.assertIsNone(safe_source_position(
            SyncPosition(directory_link / "body.tex", 1), self.scope,
        ))


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
