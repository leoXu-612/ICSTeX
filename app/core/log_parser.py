from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


FILE_LINE_RE = re.compile(r"^(?P<file>.+?\.tex):(?P<line>\d+):\s*(?P<message>.+)$")


@dataclass(frozen=True)
class LaTeXError:
    message: str
    file: Path | None = None
    line: int | None = None

    def display(self) -> str:
        location = ""
        if self.file and self.line:
            location = f"{self.file.name}:{self.line}: "
        return f"{location}{self.message}"


def parse_latex_errors(output: str, project_dir: str | Path | None = None) -> list[LaTeXError]:
    errors: list[LaTeXError] = []
    base = Path(project_dir).resolve() if project_dir else None
    lines = output.splitlines()

    for index, line in enumerate(lines):
        file_line = FILE_LINE_RE.match(line.strip())
        if file_line:
            raw_file = Path(file_line.group("file"))
            file_path = raw_file if raw_file.is_absolute() else (base / raw_file if base else raw_file)
            message = _join_wrapped_error_message(file_line.group("message"), lines, index + 1)
            errors.append(
                LaTeXError(
                    message=message,
                    file=file_path,
                    line=int(file_line.group("line")),
                )
            )
            continue

        if line.startswith("!"):
            message = _join_wrapped_error_message(line[1:].strip(), lines, index + 1)
            line_number = _line_number_near(lines, index)
            errors.append(LaTeXError(message=message, line=line_number))

    return _dedupe_errors(errors)


def parse_log_file(log_file: str | Path, project_dir: str | Path | None = None) -> list[LaTeXError]:
    path = Path(log_file)
    if not path.exists():
        return []
    return parse_latex_errors(path.read_text(encoding="utf-8", errors="replace"), project_dir)


def parse_reference_warnings(output: str) -> tuple[LaTeXError, ...]:
    """Common TeX rerun/unresolved-reference warnings; no arbitrary log diagnosis."""
    warnings = []
    for match in re.finditer(r"(?:LaTeX|Package [\w-]+) Warning:\s*([^\n]*(?:\n(?!\s*$|.*Warning:)[^\n]*)?)", output):
        message = " ".join(match.group(1).split())
        if re.search(r"undefined|multiply[- ]defined|Label\(s\) may have changed|Rerun to get cross-references", message, re.I):
            line = re.search(r"on input line (\d+)", message)
            # A log line alone does not identify which included source owns it.
            warnings.append(LaTeXError(message, line=int(line.group(1)) if line else None))
    return tuple(_dedupe_errors(warnings))


def _line_number_near(lines: list[str], index: int) -> int | None:
    for nearby in lines[index : index + 4]:
        match = re.search(r"l\.(\d+)", nearby)
        if match:
            return int(match.group(1))
    return None


def _join_wrapped_error_message(first_fragment: str, lines: list[str], start_index: int) -> str:
    message = first_fragment.strip()
    for line in lines[start_index : start_index + 3]:
        stripped = line.strip()
        if not stripped:
            break
        if FILE_LINE_RE.match(stripped) or stripped.startswith("!") or re.match(r"l\.\d+", stripped):
            break
        if stripped.startswith(("See the", "Type  H", "...", "<", "Package ", "LaTeX Warning:")):
            break
        message = _append_message_fragment(message, stripped)
    return message


def _append_message_fragment(message: str, fragment: str) -> str:
    if not message:
        return fragment
    if message.endswith(("-", " ", "`", "'", ":", "/")):
        return message + fragment
    if fragment and fragment[0] in ".,;:!?)]}'":
        return message + fragment
    if _looks_like_midword_wrap(message, fragment):
        return message + fragment
    return f"{message} {fragment}"


def _looks_like_midword_wrap(message: str, fragment: str) -> bool:
    tail = message[-1:]
    head = fragment[:1]
    return bool(tail and head and tail.isalpha() and head.islower())


def _dedupe_errors(errors: list[LaTeXError]) -> list[LaTeXError]:
    seen: set[tuple[str, str | None, int | None]] = set()
    unique: list[LaTeXError] = []
    for error in errors:
        key = (error.message, str(error.file) if error.file else None, error.line)
        if key not in seen:
            unique.append(error)
            seen.add(key)
    return unique
