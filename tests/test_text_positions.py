from unittest import TestCase

from app.core.text_positions import python_index_from_utf16, utf16_length


class TextPositionTests(TestCase):
    def test_ascii_empty_and_multiline_boundaries(self):
        for text in ("", "ASCII", "a\r\nb\n", "\u4e2d\u6587e\u0301"):
            with self.subTest(text=text):
                self.assertEqual(utf16_length(text), len(text))
                for index in range(len(text) + 1):
                    self.assertEqual(python_index_from_utf16(text, index), index)

    def test_non_bmp_boundary_mapping(self):
        text = "A\U0001f600\U0001f680Z"
        self.assertEqual(utf16_length(text), 6)
        for offset, index in ((0, 0), (1, 1), (3, 2), (5, 3), (6, 4)):
            with self.subTest(offset=offset):
                self.assertEqual(python_index_from_utf16(text, offset), index)

    def test_invalid_and_split_surrogate_offsets_are_not_rounded(self):
        for text, positions in (("", (-1, 1)), ("A\U0001f600\U0001f680Z", (-1, 2, 4, 7))):
            for position in positions:
                with self.subTest(text=text, position=position):
                    self.assertIsNone(python_index_from_utf16(text, position))
