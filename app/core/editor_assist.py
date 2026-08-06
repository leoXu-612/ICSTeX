from __future__ import annotations

from dataclasses import dataclass
import re


LIST_ENVIRONMENTS = {"itemize", "enumerate", "description"}
INDENT = "  "

BEGIN_RE = re.compile(r"\\begin\{([^{}]+)\}")
END_RE = re.compile(r"\\end\{([^{}]+)\}")
ITEM_RE = re.compile(r"^(?P<indent>\s*)\\item(?:\[[^\]]*\])?(?P<body>\s*.*)$")
TRIGGER_RE = re.compile(r"([A-Za-z]+)$")


@dataclass(frozen=True)
class EnterAssist:
    replacement: str
    replace_current_line: bool = False


@dataclass(frozen=True)
class EnvironmentCompletion:
    env_name: str
    insertion: str
    cursor_offset: int


@dataclass(frozen=True)
class Snippet:
    trigger: str
    text: str
    cursor_offset: int


SNIPPETS = {
    "fig": (
        "\\begin{figure}[htbp]\n"
        "  \\centering\n"
        "  \\includegraphics[width=0.8\\textwidth]{|}\n"
        "  \\caption{}\n"
        "  \\label{fig:}\n"
        "\\end{figure}"
    ),
    "tab": (
        "\\begin{table}[htbp]\n"
        "  \\centering\n"
        "  \\begin{tabular}{|}\n"
        "  \\end{tabular}\n"
        "  \\caption{}\n"
        "  \\label{tab:}\n"
        "\\end{table}"
    ),
    "eq": "\\begin{equation}\n  |\n\\end{equation}",
    "itm": "\\begin{itemize}\n  \\item |\n\\end{itemize}",
}


def active_environments(text: str) -> list[str]:
    stack: list[str] = []
    for line in text.splitlines():
        clean = strip_latex_comment(line)
        events: list[tuple[int, str, str]] = []
        events.extend((match.start(), "begin", match.group(1)) for match in BEGIN_RE.finditer(clean))
        events.extend((match.start(), "end", match.group(1)) for match in END_RE.finditer(clean))
        for _position, kind, env_name in sorted(events, key=lambda item: item[0]):
            if kind == "begin":
                stack.append(env_name)
            else:
                _pop_environment(stack, env_name)
    return stack


def is_in_list_environment(text_before_cursor: str) -> bool:
    return any(env in LIST_ENVIRONMENTS for env in active_environments(text_before_cursor))


def enter_assist(text_before_cursor: str, indent_unit: str = INDENT) -> EnterAssist | None:
    line = current_line(text_before_cursor)
    item = ITEM_RE.match(line)
    if item and is_in_list_environment(text_before_cursor):
        indent = item.group("indent")
        body = item.group("body").strip()
        if not body:
            return EnterAssist(replacement=_decrease_indent(indent, indent_unit), replace_current_line=True)
        return EnterAssist(replacement=f"\n{indent}\\item ")

    if line_opens_environment(line):
        return EnterAssist(replacement=f"\n{leading_whitespace(line)}{indent_unit}")

    if line_closes_environment(line):
        return EnterAssist(replacement=f"\n{_decrease_indent(leading_whitespace(line), indent_unit)}")

    return None


def environment_completion_for_line(line: str, indent_unit: str = INDENT) -> EnvironmentCompletion | None:
    clean = strip_latex_comment(line)
    match = re.search(r"^(?P<indent>\s*)\\begin\{(?P<env>[^{}]+)\}\s*$", clean)
    if not match:
        return None
    env_name = match.group("env")
    indent = match.group("indent")
    inner_indent = indent + indent_unit
    insertion = f"\n{inner_indent}\n{indent}\\end{{{env_name}}}"
    return EnvironmentCompletion(
        env_name=env_name,
        insertion=insertion,
        cursor_offset=len(f"\n{inner_indent}"),
    )


def snippet_for_trigger(trigger: str) -> Snippet | None:
    template = SNIPPETS.get(trigger)
    if not template:
        return None
    marker_index = template.find("|")
    if marker_index == -1:
        return Snippet(trigger=trigger, text=template, cursor_offset=len(template))
    return Snippet(
        trigger=trigger,
        text=template.replace("|", "", 1),
        cursor_offset=marker_index,
    )


def trigger_before_cursor(text_before_cursor: str) -> str | None:
    match = TRIGGER_RE.search(current_line(text_before_cursor))
    return match.group(1) if match else None


def current_line(text_before_cursor: str) -> str:
    return text_before_cursor.rsplit("\n", 1)[-1]


def leading_whitespace(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def line_opens_environment(line: str) -> bool:
    clean = strip_latex_comment(line)
    return bool(BEGIN_RE.search(clean)) and not bool(END_RE.search(clean))


def line_closes_environment(line: str) -> bool:
    clean = strip_latex_comment(line)
    return bool(re.match(r"^\s*\\end\{[^{}]+}\s*$", clean))


def strip_latex_comment(line: str) -> str:
    escaped = False
    for index, char in enumerate(line):
        if char == "\\":
            escaped = not escaped
            continue
        if char == "%" and not escaped:
            return line[:index]
        escaped = False
    return line


def _pop_environment(stack: list[str], env_name: str) -> None:
    for index in range(len(stack) - 1, -1, -1):
        if stack[index] == env_name:
            del stack[index:]
            return


def _decrease_indent(indent: str, indent_unit: str) -> str:
    if indent.endswith(indent_unit):
        return indent[: -len(indent_unit)]
    return indent[:-2] if len(indent) >= 2 else ""
