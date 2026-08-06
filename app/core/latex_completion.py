from __future__ import annotations

from dataclasses import dataclass
import re


COMMAND_RE = re.compile(r"(\\[A-Za-z]*)$")
LABEL_RE = re.compile(r"\\(?:ref|autoref|eqref)\{([^{}\\]*)$")
CITE_RE = re.compile(r"\\(?:cite|citep|citet|parencite|textcite)\{([^{}\\]*)$")


@dataclass(frozen=True)
class CompletionCandidate:
    display: str
    insertion: str
    cursor_offset: int


@dataclass(frozen=True)
class CompletionContext:
    replacement_length: int
    candidates: tuple[CompletionCandidate, ...]


COMMANDS: tuple[CompletionCandidate, ...] = (
    CompletionCandidate("\\begin{}", "\\begin{}", 7),
    CompletionCandidate("\\end{}", "\\end{}", 5),
    CompletionCandidate("\\section{}", "\\section{}", 9),
    CompletionCandidate("\\subsection{}", "\\subsection{}", 12),
    CompletionCandidate("\\subsubsection{}", "\\subsubsection{}", 15),
    CompletionCandidate("\\paragraph{}", "\\paragraph{}", 11),
    CompletionCandidate("\\item", "\\item ", 6),
    CompletionCandidate("\\label{}", "\\label{}", 7),
    CompletionCandidate("\\ref{}", "\\ref{}", 5),
    CompletionCandidate("\\autoref{}", "\\autoref{}", 9),
    CompletionCandidate("\\eqref{}", "\\eqref{}", 7),
    CompletionCandidate("\\cite{}", "\\cite{}", 6),
    CompletionCandidate("\\includegraphics{}", "\\includegraphics{}", 17),
    CompletionCandidate("\\caption{}", "\\caption{}", 9),
    CompletionCandidate("\\usepackage{}", "\\usepackage{}", 12),
    CompletionCandidate("\\textbf{}", "\\textbf{}", 8),
    CompletionCandidate("\\textit{}", "\\textit{}", 8),
    CompletionCandidate("\\emph{}", "\\emph{}", 6),
    CompletionCandidate("\\href{}{}", "\\href{}{}", 6),
    CompletionCandidate("\\url{}", "\\url{}", 5),
    CompletionCandidate("\\frac{}{}", "\\frac{}{}", 6),
    CompletionCandidate("\\sqrt{}", "\\sqrt{}", 6),
    CompletionCandidate("\\centering", "\\centering\n", 11),
)


def completion_context(
    text_before_cursor: str,
    *,
    labels: list[str] | tuple[str, ...] = (),
    citations: list[str] | tuple[str, ...] = (),
) -> CompletionContext | None:
    cite_match = CITE_RE.search(text_before_cursor)
    if cite_match:
        prefix = cite_match.group(1)
        return _dynamic_context(prefix, sorted(set(citations)))

    label_match = LABEL_RE.search(text_before_cursor)
    if label_match:
        prefix = label_match.group(1)
        return _dynamic_context(prefix, sorted(set(labels)))

    command_match = COMMAND_RE.search(text_before_cursor)
    if command_match:
        prefix = command_match.group(1)
        if len(prefix) < 2:
            return None
        candidates = tuple(candidate for candidate in COMMANDS if candidate.display.startswith(prefix))
        if not candidates:
            return None
        return CompletionContext(replacement_length=len(prefix), candidates=candidates[:12])

    return None


def _dynamic_context(prefix: str, values: list[str]) -> CompletionContext | None:
    if not values:
        return None
    candidates = tuple(
        CompletionCandidate(display=value, insertion=value, cursor_offset=len(value))
        for value in values
        if value.startswith(prefix)
    )
    if not candidates:
        return None
    return CompletionContext(replacement_length=len(prefix), candidates=candidates[:12])
