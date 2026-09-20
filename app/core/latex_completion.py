from __future__ import annotations

from dataclasses import dataclass
import re


COMMAND_RE = re.compile(r"(\\[A-Za-z]*)$")
LABEL_RE = re.compile(r"\\(?:ref|pageref|autoref|eqref)\{([^{}\\]*)$")
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


def _template(value: str) -> CompletionCandidate:
    """Build a completion from a template containing one ``|`` cursor marker."""
    if value.count("|") != 1:
        raise ValueError("completion templates require exactly one cursor marker")
    cursor_offset = value.index("|")
    insertion = value.replace("|", "", 1)
    return CompletionCandidate(insertion.rstrip(), insertion, cursor_offset)


COMMANDS: tuple[CompletionCandidate, ...] = (
    # Document structure and project composition.
    _template("\\begin{|}"),
    _template("\\end{|}"),
    _template("\\chapter{|}"),
    _template("\\section{|}"),
    _template("\\subsection{|}"),
    _template("\\subsubsection{|}"),
    _template("\\paragraph{|}"),
    _template("\\subparagraph{|}"),
    _template("\\item |"),
    _template("\\input{|}"),
    _template("\\include{|}"),
    _template("\\includegraphics{|}"),
    _template("\\caption{|}"),
    _template("\\usepackage{|}"),
    # Text and inline formatting. Keep exact \\text first and common variants
    # within the 12-result popup limit for the broad ``\\text`` prefix.
    _template("\\text{|}"),
    _template("\\textbf{|}"),
    _template("\\textit{|}"),
    _template("\\textcolor{|}{}"),
    _template("\\texttt{|}"),
    _template("\\textsc{|}"),
    _template("\\textrm{|}"),
    _template("\\textsf{|}"),
    _template("\\textnormal{|}"),
    _template("\\textsuperscript{|}"),
    _template("\\textsubscript{|}"),
    _template("\\emph{|}"),
    _template("\\underline{|}"),
    _template("\\footnote{|}"),
    _template("\\colorbox{|}{}"),
    _template("\\fcolorbox{|}{}{}"),
    # Labels, citations and links.
    _template("\\label{|}"),
    _template("\\ref{|}"),
    _template("\\pageref{|}"),
    _template("\\autoref{|}"),
    _template("\\eqref{|}"),
    _template("\\cite{|}"),
    _template("\\citep{|}"),
    _template("\\citet{|}"),
    _template("\\parencite{|}"),
    _template("\\textcite{|}"),
    _template("\\href{|}{}"),
    _template("\\url{|}"),
    # Mathematics and scientific notation.
    _template("\\frac{|}{}"),
    _template("\\dfrac{|}{}"),
    _template("\\sqrt{|}"),
    _template("\\sum_{|}^{}"),
    _template("\\prod_{|}^{}"),
    _template("\\int_{|}^{}"),
    _template("\\lim_{|}"),
    _template("\\mathbf{|}"),
    _template("\\mathrm{|}"),
    _template("\\mathit{|}"),
    _template("\\mathcal{|}"),
    _template("\\operatorname{|}"),
    _template("\\qty{|}{}"),
    _template("\\num{|}"),
    _template("\\unit{|}"),
    _template("\\SI{|}{}"),
    _template("\\si{|}"),
    # Bibliography and layout controls.
    _template("\\bibliography{|}"),
    _template("\\bibliographystyle{|}"),
    _template("\\addbibresource{|}"),
    _template("\\printbibliography|"),
    _template("\\centering\n|"),
    _template("\\toprule\n|"),
    _template("\\midrule\n|"),
    _template("\\bottomrule\n|"),
    _template("\\FloatBarrier\n|"),
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
