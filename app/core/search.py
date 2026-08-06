from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SearchOptions:
    case_sensitive: bool = False
    whole_word: bool = False


@dataclass(frozen=True)
class SearchMatch:
    start: int
    end: int


def find_matches(text: str, query: str, options: SearchOptions | None = None) -> list[SearchMatch]:
    if not query:
        return []
    opts = options or SearchOptions()
    flags = 0 if opts.case_sensitive else re.IGNORECASE
    pattern = re.escape(query)
    if opts.whole_word:
        pattern = rf"(?<![A-Za-z0-9_]){pattern}(?![A-Za-z0-9_])"
    return [SearchMatch(match.start(), match.end()) for match in re.finditer(pattern, text, flags)]


def replace_all(text: str, query: str, replacement: str, options: SearchOptions | None = None) -> tuple[str, int]:
    matches = find_matches(text, query, options)
    if not matches:
        return text, 0

    pieces: list[str] = []
    cursor = 0
    for match in matches:
        pieces.append(text[cursor : match.start])
        pieces.append(replacement)
        cursor = match.end
    pieces.append(text[cursor:])
    return "".join(pieces), len(matches)
