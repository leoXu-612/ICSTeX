"""Bounded static citation/BibTeX syntax, without expansion or rewriting.

This is not BibTeX/Biber execution, a field-schema validator or a TeX interpreter.
Values remain raw; unsupported syntax makes coverage incomplete.
"""
from bisect import bisect_right
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SyntaxIssue:
    line: int
    message: str


@dataclass(frozen=True)
class CitationUse:
    key: str
    command: str
    line: int


@dataclass(frozen=True)
class CitationScan:
    uses: tuple[CitationUse, ...]
    issues: tuple[SyntaxIssue, ...]
    include_all: bool = False

    @property
    def complete(self):
        return not self.issues


@dataclass(frozen=True)
class BibEntry:
    key: str
    entry_type: str
    line: int
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class BibScan:
    entries: tuple[BibEntry, ...]
    issues: tuple[SyntaxIssue, ...]

    @property
    def complete(self):
        return not self.issues


class _Lines:
    def __init__(self, text):
        self.ends = [match.end() for match in re.finditer(r"\r\n?|\n", text)]

    def at(self, offset):
        return bisect_right(self.ends, offset) + 1


def _space(text, pos):
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def _tex_group(text, pos):
    """Return the index after one braced/bracketed group, or reject it."""
    if pos >= len(text) or text[pos] not in "{[":
        raise ValueError("Expected a braced or optional argument")
    stack = ["}" if text[pos] == "{" else "]"]
    pos += 1
    while pos < len(text):
        char = text[pos]
        if char == "\\":
            pos += 2
            continue
        if char == "{" or (char == "[" and stack[-1] == "]"):
            stack.append("}" if char == "{" else "]")
        elif char == stack[-1]:
            stack.pop()
            if not stack:
                return pos + 1
        pos += 1
    raise ValueError("Unclosed citation or macro argument")


_COMMAND = re.compile(r"\\([A-Za-z@]+|.)")
_BEGIN_ENV = re.compile(r"\s*\{([^{}]+)\}")
_VERBATIM = {"verbatim", "verbatim*", "Verbatim", "lstlisting", "minted", "comment"}
_DEFINITIONS = {"newcommand", "renewcommand", "providecommand", "DeclareRobustCommand",
                "def", "gdef", "edef", "xdef"}
_SINGLES = {"cite", "citep", "citet", "parencite", "textcite", "autocite", "footcite",
            "footcitetext", "smartcite", "supercite", "fullcite", "nocite"}


def mask_tex_noncontent(text: str, *, max_items=10000):
    """Preserve offsets/newlines while masking comments, verbatim and definitions."""
    chars = list(text)
    lines = _Lines(text)
    issues = []

    def blank(start, end):
        for index in range(start, end):
            if chars[index] not in "\r\n":
                chars[index] = " "

    pos = 0
    while pos < len(text):
        if len(issues) >= max_items:
            issues.append(SyntaxIssue(lines.at(pos), "TeX syntax issue limit exceeded"))
            blank(pos, len(text))
            break
        if text[pos] == "%":
            end = pos
            while end < len(text) and text[end] not in "\r\n":
                end += 1
            blank(pos, end)
            pos = end
            continue
        if text[pos] != "\\":
            pos += 1
            continue
        match = _COMMAND.match(text, pos)
        if not match:
            pos += 1
            continue
        command = match.group(1)
        end = match.end()
        try:
            if command == "verb":
                if end < len(text) and text[end] == "*":
                    end += 1
                if end == len(text) or text[end].isspace():
                    raise ValueError("Unresolved inline verbatim delimiter")
                stop = text.find(text[end], end + 1)
                if stop < 0 or "\n" in text[end:stop] or "\r" in text[end:stop]:
                    raise ValueError("Unclosed inline verbatim")
                end = stop + 1
                blank(pos, end)
            elif command == "begin":
                begin = _BEGIN_ENV.match(text, end)
                if begin and begin.group(1) in {"refsection", "refsegment"}:
                    issues.append(SyntaxIssue(lines.at(pos), "Bibliography sections/segments are not resolved"))
                if begin and begin.group(1) in _VERBATIM:
                    token = "\\end{" + begin.group(1) + "}"
                    stop = text.find(token, begin.end())
                    if stop < 0:
                        raise ValueError("Unclosed verbatim/comment environment")
                    end = stop + len(token)
                    blank(pos, end)
            elif command in _DEFINITIONS:
                issues.append(SyntaxIssue(lines.at(pos), "Macro definitions are not expanded"))
                end = _space(text, end)
                if end < len(text) and text[end] == "*":
                    end = _space(text, end + 1)
                if command in {"def", "gdef", "edef", "xdef"}:
                    end = text.find("{", end)
                    if end < 0:
                        raise ValueError("Unresolved macro definition")
                else:
                    if end < len(text) and text[end] == "{":
                        end = _tex_group(text, end)
                    else:
                        name = _COMMAND.match(text, end)
                        if name is None:
                            raise ValueError("Unresolved macro definition")
                        end = name.end()
                    end = _space(text, end)
                    while end < len(text) and text[end] == "[":
                        end = _space(text, _tex_group(text, end))
                end = _tex_group(text, end)
                blank(pos, end)
            elif command in {"csname", "catcode", "includeonly", "let"} or command.startswith("if"):
                issues.append(SyntaxIssue(lines.at(pos), "Conditional/dynamic TeX is not evaluated"))
            elif command in {"bibitem", "newrefsection", "newrefsegment", "DeclareRefcontext", "newrefcontext"}:
                issues.append(SyntaxIssue(lines.at(pos), "Manual/scoped bibliography is not resolved"))
        except ValueError as exc:
            issues.append(SyntaxIssue(lines.at(pos), str(exc)))
            blank(pos, len(text))
            break
        pos = end
    return "".join(chars), tuple(issues)


def scan_citation_uses(text: str, *, max_items=10000) -> CitationScan:
    clean, masking_issues = mask_tex_noncontent(text, max_items=max_items)
    lines = _Lines(clean)
    issues = list(masking_issues)
    uses = []
    include_all = False
    pos = 0
    while match := _COMMAND.search(clean, pos):
        if len(uses) + len(issues) >= max_items:
            issues.append(SyntaxIssue(lines.at(match.start()), "Citation syntax item limit exceeded"))
            break
        command = match.group(1)
        lower = command.lower()
        pos = match.end()
        if lower not in _SINGLES:
            if "cite" in lower:
                issues.append(SyntaxIssue(lines.at(match.start()), f"Unsupported citation command: {command}"))
            continue
        try:
            if pos < len(clean) and clean[pos] == "*":
                pos += 1
            pos = _space(clean, pos)
            while pos < len(clean) and clean[pos] == "[":
                pos = _space(clean, _tex_group(clean, pos))
            if pos >= len(clean) or clean[pos] != "{":
                raise ValueError("Citation keys are not a literal braced argument")
            end = _tex_group(clean, pos)
            value = clean[pos + 1:end - 1]
            pos = end
            keys = [key.strip() for key in value.split(",")]
            if not keys or any(not key or re.search(r"[\s\\{}#\[\]]", key) for key in keys):
                raise ValueError("Dynamic or malformed citation keys")
            for key in keys:
                if key == "*" and lower == "nocite":
                    include_all = True
                elif len(uses) + len(issues) >= max_items:
                    issues.append(SyntaxIssue(lines.at(match.start()), "Citation item limit exceeded"))
                    return CitationScan(tuple(uses), tuple(issues), include_all)
                else:
                    uses.append(CitationUse(key, command, lines.at(match.start())))
        except ValueError as exc:
            issues.append(SyntaxIssue(lines.at(match.start()), str(exc)))
    return CitationScan(tuple(uses), tuple(issues), include_all)


_BARE_VALUE = re.compile(r"[^\s,#{}()\"]+")
_BIB_COMMAND = re.compile(r"@([A-Za-z][\w-]*)\s*")
_BIB_KEY = re.compile(r"[^\s,{}()=]+")
_BIB_FIELD = re.compile(r"[A-Za-z][\w:-]*")


def _bib_atom(text, pos):
    if pos >= len(text):
        raise ValueError("Missing field value")
    char = text[pos]
    if char in '{"':
        quoted = char == '"'
        depth = 0 if quoted else 1
        pos += 1
        while pos < len(text):
            char = text[pos]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth < 0:
                    raise ValueError("Unbalanced braces in quoted value")
                if depth == 0 and not quoted:
                    return pos + 1
            elif char == '"' and quoted and depth == 0:
                return pos + 1
            pos += 1
        raise ValueError("Unclosed field value")
    match = _BARE_VALUE.match(text, pos)
    if match is None:
        raise ValueError("Unparseable field value")
    return match.end()


def _bib_value(text, pos):
    pos = _bib_atom(text, pos)
    pos = _space(text, pos)
    while pos < len(text) and text[pos] == "#":
        pos = _space(text, _bib_atom(text, _space(text, pos + 1)))
    return pos


def parse_bibliography(text: str, *, max_items=10000) -> BibScan:
    """Keep duplicate entry declarations; do not evaluate strings or rewrite bytes.

    BibTeX's percent sign is not a TeX comment marker. Non-entry prose is ignored;
    @comment, @string and @preamble are not bibliography entries.
    """
    lines = _Lines(text)
    entries, issues = [], []
    pos = 0
    field_count = 0
    while match := _BIB_COMMAND.search(text, pos):
        start = match.start()
        entry_type = match.group(1).lower()
        pos = match.end()
        try:
            if pos >= len(text) or text[pos] not in "{(":
                raise ValueError("Expected an entry delimiter")
            opening = pos
            closing = "}" if text[pos] == "{" else ")"
            pos = _space(text, pos + 1)
            if entry_type == "comment":
                # A braced comment is opaque; nested @ does not create entries.
                if closing == "}":
                    pos = _bib_atom(text, opening)
                else:
                    stop = text.find(")", pos)
                    if stop < 0:
                        raise ValueError("Unclosed comment")
                    pos = stop + 1
                continue
            if entry_type == "preamble":
                pos = _bib_value(text, pos)
                if pos >= len(text) or text[pos] != closing:
                    raise ValueError("Unclosed preamble")
                pos += 1
                continue
            key = ""
            if entry_type != "string":
                key_match = _BIB_KEY.match(text, pos)
                if key_match is None:
                    raise ValueError("Missing or malformed Bib key")
                key = key_match.group()
                pos = _space(text, key_match.end())
                if pos >= len(text) or text[pos] != ",":
                    raise ValueError("Expected a comma after Bib key")
                pos = _space(text, pos + 1)
            fields = []
            names = set()
            while pos < len(text) and text[pos] != closing:
                if field_count >= max_items:
                    raise ValueError("Bibliography field limit exceeded")
                field = _BIB_FIELD.match(text, pos)
                if field is None:
                    raise ValueError("Unparseable field name")
                name = field.group().lower()
                if name in names:
                    raise ValueError(f"Repeated field: {name}")
                names.add(name)
                pos = _space(text, field.end())
                if pos >= len(text) or text[pos] != "=":
                    raise ValueError(f"Expected '=' after field {name}")
                value_start = _space(text, pos + 1)
                pos = _bib_value(text, value_start)
                fields.append((name, text[value_start:pos].rstrip()))
                field_count += 1
                if pos < len(text) and text[pos] == ",":
                    pos = _space(text, pos + 1)
                elif pos >= len(text) or text[pos] != closing:
                    raise ValueError("Expected a comma or the entry closing delimiter")
            if pos >= len(text):
                raise ValueError("Unclosed bibliography entry")
            pos += 1
            if entry_type != "string":
                if len(entries) >= max_items:
                    raise ValueError("Bibliography item limit exceeded")
                entries.append(BibEntry(key, entry_type, lines.at(start), tuple(fields)))
        except ValueError as exc:
            issues.append(SyntaxIssue(lines.at(min(pos, len(text))), str(exc)))
            # Do not guess where an unclosed value ends or invent later entries.
            break
    return BibScan(tuple(entries), tuple(issues))


def literal_bib_value(value: str) -> str | None:
    """Resolve only one literal braced/quoted atom for key-to-key relations."""
    value = value.strip()
    if value and value[0] in '{"':
        try:
            if _bib_atom(value, 0) == len(value) and not re.search(r"[\\{}]", value[1:-1]):
                return value[1:-1]
        except ValueError:
            pass
    return None
