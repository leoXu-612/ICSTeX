from __future__ import annotations

import codecs
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
from unittest import TestCase, skipIf
from unittest.mock import patch

from app.core.text_encoding import LatexTextDecodeError, decode_latex_bytes, write_latex_text_atomic


class TextEncodingTests(TestCase):
    def test_plain_utf8_is_default(self) -> None:
        result = decode_latex_bytes("Hello 世界".encode("utf-8"))

        self.assertEqual(result.text, "Hello 世界")
        self.assertEqual(result.encoding, "utf-8")

    def test_utf8_bom_is_preserved_as_encoding_state(self) -> None:
        result = decode_latex_bytes(codecs.BOM_UTF8 + "Hello".encode("utf-8"))

        self.assertEqual(result.text, "Hello")
        self.assertEqual(result.encoding, "utf-8-sig")

    def test_texshop_magic_encoding_is_detected(self) -> None:
        source = "% !TEX encoding = Windows Latin 1\nRésumé".encode("cp1252")

        result = decode_latex_bytes(source)

        self.assertEqual(result.text.splitlines()[-1], "Résumé")
        self.assertEqual(result.encoding, "cp1252")

    def test_inputenc_declaration_is_detected(self) -> None:
        source = "\\usepackage[latin1]{inputenc}\nCrème".encode("iso-8859-1")

        result = decode_latex_bytes(source)

        self.assertIn("Crème", result.text)
        self.assertEqual(result.encoding, "iso8859-1")

    def test_invalid_utf8_is_not_silently_replaced(self) -> None:
        with self.assertRaises(LatexTextDecodeError):
            decode_latex_bytes(b"Paper \x81 text")

    def test_explicit_fallback_encoding_is_strictly_applied(self) -> None:
        source = "中文内容".encode("gb18030")

        result = decode_latex_bytes(source, encoding="gb18030")

        self.assertEqual(result.text, "中文内容")
        self.assertEqual(result.encoding, "gb18030")

    def test_unknown_declared_encoding_is_reported(self) -> None:
        with self.assertRaises(LatexTextDecodeError) as caught:
            decode_latex_bytes(b"% !TEX encoding = MysteryCodec\nHello")

        self.assertEqual(caught.exception.encoding, "MysteryCodec")

    def test_encoding_failure_does_not_truncate_existing_file(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.tex"
            path.write_bytes(b"Original")

            with self.assertRaises(UnicodeEncodeError):
                write_latex_text_atomic(path, "Original\n中文", encoding="cp1252")

            self.assertEqual(path.read_bytes(), b"Original")

    def test_atomic_write_replaces_complete_payload_without_temp_file(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "main.tex"
            path.write_text("Old", encoding="utf-8")

            write_latex_text_atomic(path, "New 世界", encoding="utf-8")

            self.assertEqual(path.read_text(encoding="utf-8"), "New 世界")
            self.assertEqual(list(root.glob(".main.tex.*.tmp")), [])

    def test_atomic_write_preserves_utf8_bom(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "main.tex"

            write_latex_text_atomic(path, "Hello", encoding="utf-8-sig")

            self.assertTrue(path.read_bytes().startswith(codecs.BOM_UTF8))

    def test_replace_failure_preserves_original_and_removes_temp_file(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "main.tex"
            path.write_bytes(b"Original")

            with (
                patch("app.core.text_encoding.os.replace", side_effect=OSError("locked")),
                self.assertRaises(OSError),
            ):
                write_latex_text_atomic(path, "Changed", encoding="utf-8")

            self.assertEqual(path.read_bytes(), b"Original")
            self.assertEqual(list(root.glob(".main.tex.*.tmp")), [])

    @skipIf(os.name == "nt", "POSIX permission bits differ on Windows")
    def test_atomic_write_preserves_file_permissions(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "main.tex"
            path.write_bytes(b"Original")
            path.chmod(0o640)

            write_latex_text_atomic(path, "Changed", encoding="utf-8")

            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)

    @skipIf(os.name == "nt", "Creating symlinks is not generally available on Windows")
    def test_atomic_write_follows_existing_symlink_without_replacing_it(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.tex"
            link = root / "main.tex"
            target.write_bytes(b"Original")
            link.symlink_to(target.name)

            write_latex_text_atomic(link, "Changed", encoding="utf-8")

            self.assertTrue(link.is_symlink())
            self.assertEqual(target.read_text(encoding="utf-8"), "Changed")
