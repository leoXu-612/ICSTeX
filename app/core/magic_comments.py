from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.core.latex_tools import LaTeXEngine


MAGIC_COMMENT_SCAN_LINES = 80

_DIRECTIVE_RE = re.compile(
    r"^\s*%\s*!\s*T[eE]X\s+(?P<key>root|program|ts-program)\s*=\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)
_FIRST_LINE_PROGRAM_RE = re.compile(r"^\s*%&\s*(?P<program>[A-Za-z0-9_-]+)\s*$")


@dataclass(frozen=True)
class MagicComments:
    root: Path | None = None
    program: LaTeXEngine | None = None


def parse_magic_comments(text: str, *, base_dir: str | Path | None = None) -> MagicComments:
    root: Path | None = None
    program: LaTeXEngine | None = None
    base = Path(base_dir).expanduser() if base_dir is not None else None

    for index, line in enumerate(text.splitlines()[:MAGIC_COMMENT_SCAN_LINES]):
        first_line_program = _FIRST_LINE_PROGRAM_RE.match(line) if index == 0 else None
        if first_line_program and program is None:
            program = _engine_from_program(first_line_program.group("program"))
            continue

        match = _DIRECTIVE_RE.match(line)
        if not match:
            continue
        key = match.group("key").lower()
        value = _strip_magic_value(match.group("value"))
        if key == "root" and root is None:
            root = _resolve_root(value, base)
        elif key in {"program", "ts-program"} and program is None:
            program = _engine_from_program(value)

    return MagicComments(root=root, program=program)


def read_magic_comments(path: str | Path) -> MagicComments:
    file_path = Path(path).expanduser()
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return MagicComments()
    return parse_magic_comments(text, base_dir=file_path.parent)


def magic_root_for(path: str | Path, *, must_exist: bool = True) -> Path | None:
    file_path = Path(path).expanduser()
    comments = read_magic_comments(file_path)
    if comments.root is None or comments.root.suffix.lower() != ".tex":
        return None
    root = comments.root.resolve()
    if must_exist and not root.is_file():
        return None
    return root


def magic_engine_for(path: str | Path) -> LaTeXEngine | None:
    return read_magic_comments(path).program


def _strip_magic_value(value: str) -> str:
    clean = value.strip()
    if len(clean) >= 2 and clean[0] == clean[-1] and clean[0] in {"'", '"'}:
        clean = clean[1:-1].strip()
    return clean


def _resolve_root(value: str, base_dir: Path | None) -> Path | None:
    if not value:
        return None
    root = Path(value).expanduser()
    if not root.is_absolute() and base_dir is not None:
        root = base_dir / root
    return root


def _engine_from_program(value: str) -> LaTeXEngine | None:
    program = value.strip().split()[0].lower() if value.strip() else ""
    program = program.replace("_", "-")
    aliases = {
        "pdflatex": LaTeXEngine.PDFLATEX,
        "pdftex": LaTeXEngine.PDFLATEX,
        "xelatex": LaTeXEngine.XELATEX,
        "xetex": LaTeXEngine.XELATEX,
        "lualatex": LaTeXEngine.LUALATEX,
        "luatex": LaTeXEngine.LUALATEX,
        "latexmk": LaTeXEngine.AUTO,
    }
    return aliases.get(program)
