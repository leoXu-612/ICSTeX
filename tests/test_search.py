from __future__ import annotations

from unittest import TestCase

from app.core.search import SearchOptions, find_matches, replace_all


class SearchTests(TestCase):
    def test_find_matches_case_insensitive_by_default(self) -> None:
        matches = find_matches("Alpha alpha ALPHA", "alpha")

        self.assertEqual([(match.start, match.end) for match in matches], [(0, 5), (6, 11), (12, 17)])

    def test_find_matches_can_match_case_and_whole_words(self) -> None:
        text = "cat catalog Cat cat_1 cat"
        matches = find_matches(text, "cat", SearchOptions(case_sensitive=True, whole_word=True))

        self.assertEqual([(match.start, match.end) for match in matches], [(0, 3), (22, 25)])

    def test_replace_all_returns_new_text_and_count(self) -> None:
        new_text, count = replace_all("one two one", "one", "1")

        self.assertEqual(new_text, "1 two 1")
        self.assertEqual(count, 2)
