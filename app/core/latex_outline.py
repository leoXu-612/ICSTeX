from __future__ import annotations

from dataclasses import dataclass
import re


SECTION_LEVELS = {
    "part": 0,
    "chapter": 1,
    "section": 2,
    "subsection": 3,
    "subsubsection": 4,
    "paragraph": 5,
    "subparagraph": 6,
}

SECTION_RE = re.compile(
    r"\\(?P<command>part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?"
    r"(?:\[[^\]]*\])?\{(?P<title>.*)\}"
)


@dataclass(frozen=True)
class OutlineItem:
    title: str
    command: str
    line: int
    level: int


def scan_outline(text: str) -> list[OutlineItem]:
    items: list[OutlineItem] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        clean = _strip_comment(line)
        for match in SECTION_RE.finditer(clean):
            command = match.group("command")
            title = _clean_title(match.group("title"))
            items.append(
                OutlineItem(
                    title=title or "(无标题)",
                    command=command,
                    line=line_number,
                    level=SECTION_LEVELS[command],
                )
            )
    return items


def _clean_title(title: str) -> str:
    title = re.sub(r"\\(?:textbf|textit|emph)\{([^{}]*)\}", r"\1", title)
    title = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?", "", title)
    return re.sub(r"\s+", " ", title).strip()


def _strip_comment(line: str) -> str:
    escaped = False
    for index, char in enumerate(line):
        if char == "\\":
            escaped = not escaped
            continue
        if char == "%" and not escaped:
            return line[:index]
        escaped = False
    return line
