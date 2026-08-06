from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from pylatexenc.latexwalker import LatexWalkerParseError

from app.core.latex_insertions import existing_packages, package_update
from app.core.latex_parser import make_walker
from app.core.latex_tools import LaTeXToolchain
from app.core.log_parser import LaTeXError
from app.core.project_tools import (
    BIB_KEY_RE,
    BEGIN_DOCUMENT,
    CITE_RE,
    END_DOCUMENT,
    LABEL_RE,
    REF_RE,
    duplicate_labels,
    scan_labels,
    scan_citations,
)


SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

SEVERITY_LABELS = {
    SEVERITY_ERROR: "错误",
    SEVERITY_WARNING: "警告",
    SEVERITY_INFO: "提示",
}

GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}")
PACKAGE_FILE_RE = re.compile(r"(?:LaTeX Error:\s*)?File [`']([^`']+)[`'] not found", re.I)
ENVIRONMENT_RE = re.compile(r"Environment\s+([A-Za-z*]+)\s+undefined", re.I)
CONTROL_SEQUENCE_RE = re.compile(r"\\[A-Za-z@]+")

_UNCLOSED_RE = re.compile(r"was expecting \\end\{([^}]+)\}")
_EXTRA_END_RE = re.compile(r"Unexpected closing environment: '([^']+)'")
_MISMATCH_RE = re.compile(r"Unexpected mismatching closing environment: '([^']+)', was expecting '([^']+)'")

PACKAGE_RULES: tuple[tuple[str, re.Pattern[str], str, str], ...] = (
    ("graphicx", re.compile(r"\\includegraphics\b"), "缺少 graphicx", "插入图片需要 graphicx package。"),
    ("amsmath", re.compile(r"\\(?:begin\{(?:align|align\*|equation\*|gather|multline)\}|eqref\b)"), "缺少 amsmath", "公式环境或 eqref 通常需要 amsmath package。"),
    ("hyperref", re.compile(r"\\(?:href|url|autoref)\b"), "缺少 hyperref", "超链接、URL 或 autoref 通常需要 hyperref package。"),
    ("booktabs", re.compile(r"\\(?:toprule|midrule|bottomrule)\b"), "缺少 booktabs", "专业表格线需要 booktabs package。"),
    ("siunitx", re.compile(r"\\(?:SI|si|qty|num|unit)\b"), "缺少 siunitx", "数字、单位和科学计量格式通常需要 siunitx package。"),
    ("subcaption", re.compile(r"\\(?:begin\{subfigure\}|subcaptionbox\b)"), "缺少 subcaption", "并排子图通常需要 subcaption package。"),
    ("float", re.compile(r"\\begin\{(?:figure|table)\}\[H\]"), "缺少 float", "[H] 固定浮动体位置需要 float package。"),
    ("placeins", re.compile(r"\\FloatBarrier\b"), "缺少 placeins", "FloatBarrier 需要 placeins package。"),
)

COMMAND_PACKAGE_HINTS = {
    "\\includegraphics": "graphicx",
    "\\href": "hyperref",
    "\\url": "hyperref",
    "\\autoref": "hyperref",
    "\\eqref": "amsmath",
    "\\toprule": "booktabs",
    "\\midrule": "booktabs",
    "\\bottomrule": "booktabs",
    "\\SI": "siunitx",
    "\\si": "siunitx",
    "\\qty": "siunitx",
    "\\num": "siunitx",
    "\\unit": "siunitx",
    "\\FloatBarrier": "placeins",
}


@dataclass(frozen=True)
class FixSuggestion:
    title: str
    packages: tuple[str, ...] = ()


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    title: str
    message: str
    file: Path | None = None
    line: int | None = None
    raw_message: str = ""
    fix: FixSuggestion | None = None

    @property
    def severity_label(self) -> str:
        return SEVERITY_LABELS.get(self.severity, self.severity)


def analyze_project(
    text: str,
    *,
    root_file: Path | None,
    bib_text: str = "",
    toolchain: LaTeXToolchain | None = None,
    log_errors: list[LaTeXError] | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    if root_file is None:
        diagnostics.append(
            Diagnostic(
                severity=SEVERITY_WARNING,
                title="文档尚未保存",
                message="请先保存 .tex 文件，这样图片路径、BibTeX 和编译缓存才能稳定工作。",
            )
        )

    if toolchain is not None and not toolchain.is_compile_ready:
        diagnostics.append(
            Diagnostic(
                severity=SEVERITY_ERROR,
                title="未找到 LaTeX 编译器",
                message=toolchain.missing_compile_message,
            )
        )

    for error in log_errors or []:
        diagnostics.append(explain_latex_error(error, root_file=root_file))

    diagnostics.extend(package_diagnostics(text, root_file=root_file))
    diagnostics.extend(structure_diagnostics(text, root_file=root_file))
    diagnostics.extend(reference_diagnostics(text, bib_text, root_file=root_file))
    diagnostics.extend(image_diagnostics(text, root_file=root_file))

    return _dedupe_diagnostics(diagnostics)


def explain_latex_error(error: LaTeXError, *, root_file: Path | None = None) -> Diagnostic:
    raw = error.message.strip()
    lower = raw.lower()
    file = error.file or root_file

    if "undefined control sequence" in lower:
        command = _extract_command(raw)
        package = COMMAND_PACKAGE_HINTS.get(command or "")
        fix = _package_fix(package) if package else None
        if package and command:
            return Diagnostic(
                severity=SEVERITY_ERROR,
                title="缺少 package 或命令不可用",
                message=f"{command} 通常需要 \\usepackage{{{package}}}。也请检查命令拼写是否正确。",
                file=file,
                line=error.line,
                raw_message=raw,
                fix=fix,
            )
        return Diagnostic(
            severity=SEVERITY_ERROR,
            title="LaTeX 不认识这个命令",
            message="某个命令未定义。请检查命令拼写，或确认导言区已经加入对应 package。",
            file=file,
            line=error.line,
            raw_message=raw,
        )

    file_match = PACKAGE_FILE_RE.search(raw)
    if file_match:
        missing = file_match.group(1)
        package = Path(missing).stem if missing.endswith(".sty") else ""
        known = package if package in _known_packages() else ""
        return Diagnostic(
            severity=SEVERITY_ERROR,
            title="找不到文件或 package",
            message=f"LaTeX 找不到 {missing}。如果这是 package，请确认已安装；如果是图片或输入文件，请检查路径。",
            file=file,
            line=error.line,
            raw_message=raw,
            fix=_package_fix(known) if known else None,
        )

    env_match = ENVIRONMENT_RE.search(raw)
    if env_match:
        package = "amsmath" if env_match.group(1).lower().rstrip("*") in {"align", "gather", "multline"} else ""
        return Diagnostic(
            severity=SEVERITY_ERROR,
            title="环境不可用",
            message=f"{env_match.group(1)} 环境未定义。请检查环境名，或加入对应 package。",
            file=file,
            line=error.line,
            raw_message=raw,
            fix=_package_fix(package) if package else None,
        )

    if "missing" in lower and "}" in raw:
        return Diagnostic(
            severity=SEVERITY_ERROR,
            title="可能缺少右花括号",
            message="LaTeX 认为某处少了 }。请检查这一行附近的命令参数、caption、label 或公式。",
            file=file,
            line=error.line,
            raw_message=raw,
        )

    if "extra }" in lower or "too many }" in lower:
        return Diagnostic(
            severity=SEVERITY_ERROR,
            title="可能多了右花括号",
            message="LaTeX 认为某处多了 }。请检查这一行附近是否有成对括号写重复。",
            file=file,
            line=error.line,
            raw_message=raw,
        )

    if "ended by" in lower or "environment" in lower and "ended" in lower:
        return Diagnostic(
            severity=SEVERITY_ERROR,
            title="环境开始和结束不匹配",
            message="请检查 \\begin{...} 和 \\end{...} 是否成对，环境名是否一致。",
            file=file,
            line=error.line,
            raw_message=raw,
        )

    return Diagnostic(
        severity=SEVERITY_ERROR,
        title="LaTeX 编译错误",
        message=raw or "编译器返回了错误。请查看原始日志获得更多信息。",
        file=file,
        line=error.line,
        raw_message=raw,
    )


def package_diagnostics(text: str, *, root_file: Path | None = None) -> list[Diagnostic]:
    existing = existing_packages(text)
    diagnostics: list[Diagnostic] = []
    for package, pattern, title, message in PACKAGE_RULES:
        if package in existing:
            continue
        match = pattern.search(text)
        if not match:
            continue
        diagnostics.append(
            Diagnostic(
                severity=SEVERITY_WARNING,
                title=title,
                message=message,
                file=root_file,
                line=_line_for_offset(text, match.start()),
                fix=_package_fix(package),
            )
        )
    return diagnostics


def reference_diagnostics(text: str, bib_text: str, *, root_file: Path | None = None) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    duplicates = duplicate_labels(text)
    for label in sorted(duplicates):
        line = _line_for_regex_value(text, LABEL_RE, label)
        diagnostics.append(
            Diagnostic(
                severity=SEVERITY_ERROR,
                title="重复 label",
                message=f"{label} 被定义了多次。请保证每个 \\label{{...}} 都唯一。",
                file=root_file,
                line=line,
            )
        )

    defined_labels = {label.name for label in scan_labels(text)}
    for ref, line in _regex_values_with_lines(text, REF_RE):
        if ref not in defined_labels:
            diagnostics.append(
                Diagnostic(
                    severity=SEVERITY_WARNING,
                    title="未定义 ref",
                    message=f"{ref} 没有对应的 \\label{{{ref}}}。",
                    file=root_file,
                    line=line,
                )
            )

    defined_bib = {match.group(1).strip() for match in BIB_KEY_RE.finditer(bib_text)}
    for cite, line in _citation_values_with_lines(text):
        if cite not in defined_bib:
            diagnostics.append(
                Diagnostic(
                    severity=SEVERITY_WARNING,
                    title="未定义 citation",
                    message=f"{cite} 没有对应的 BibTeX 条目。请在引用面板添加它，或检查 key 拼写。",
                    file=root_file,
                    line=line,
                )
            )
    return diagnostics


def image_diagnostics(text: str, *, root_file: Path | None = None) -> list[Diagnostic]:
    if root_file is None:
        return []
    diagnostics: list[Diagnostic] = []
    for match in GRAPHICS_RE.finditer(text):
        raw_path = match.group(1).strip()
        if _image_exists(root_file.parent, raw_path):
            continue
        diagnostics.append(
            Diagnostic(
                severity=SEVERITY_ERROR,
                title="找不到图片文件",
                message=f"图片路径 {raw_path} 无法在当前项目中找到。请确认图片已复制到项目文件夹，并使用相对路径。",
                file=root_file,
                line=_line_for_offset(text, match.start()),
                raw_message=raw_path,
            )
        )
    return diagnostics


def structure_diagnostics(text: str, *, root_file: Path | None = None) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if "\\documentclass" not in text:
        diagnostics.append(
            Diagnostic(
                severity=SEVERITY_WARNING,
                title="缺少 documentclass",
                message="文档通常需要以 \\documentclass{...} 声明类型，例如 article、report 或 exam。",
                file=root_file,
                line=1,
            )
        )

    if BEGIN_DOCUMENT not in text:
        diagnostics.append(
            Diagnostic(
                severity=SEVERITY_ERROR,
                title="缺少正文开始标记",
                message="请加入 \\begin{document}，LaTeX 需要它来区分导言区和正文。",
                file=root_file,
                line=1,
            )
        )
    if END_DOCUMENT not in text:
        diagnostics.append(
            Diagnostic(
                severity=SEVERITY_ERROR,
                title="缺少正文结束标记",
                message="请在文档末尾加入 \\end{document}。",
                file=root_file,
                line=max(1, text.count("\n") + 1),
            )
        )

    diagnostics.extend(_environment_balance_diagnostics(text, root_file=root_file))

    if scan_citations(text) and not re.search(r"\\(?:bibliography|addbibresource|printbibliography)\b", text):
        diagnostics.append(
            Diagnostic(
                severity=SEVERITY_WARNING,
                title="引用可能不会输出",
                message="文中使用了 citation，但没有找到 bibliography/addbibresource/printbibliography。请确认参考文献会被输出。",
                file=root_file,
                line=_line_for_offset(text, next(CITE_RE.finditer(text)).start()) if CITE_RE.search(text) else None,
            )
        )
    return diagnostics


def apply_fix(text: str, fix: FixSuggestion) -> str:
    if not fix.packages:
        return text
    return package_update(text, fix.packages).text


def _package_fix(package: str | None) -> FixSuggestion | None:
    if not package:
        return None
    return FixSuggestion(title=f"加入 \\usepackage{{{package}}}", packages=(package,))


def _known_packages() -> set[str]:
    return {package for package, _pattern, _title, _message in PACKAGE_RULES}


def _extract_command(message: str) -> str | None:
    match = CONTROL_SEQUENCE_RE.search(message)
    return match.group(0) if match else None


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _regex_values_with_lines(text: str, pattern: re.Pattern[str]) -> list[tuple[str, int]]:
    values: list[tuple[str, int]] = []
    for match in pattern.finditer(text):
        values.append((match.group(1), _line_for_offset(text, match.start())))
    return values


def _citation_values_with_lines(text: str) -> list[tuple[str, int]]:
    citations: list[tuple[str, int]] = []
    for match in CITE_RE.finditer(text):
        line = _line_for_offset(text, match.start())
        citations.extend((key.strip(), line) for key in match.group(1).split(",") if key.strip())
    return citations


def _environment_balance_diagnostics(text: str, *, root_file: Path | None) -> list[Diagnostic]:
    """Detect unmatched ``\\begin``/``\\end`` pairs using a strict pylatexenc walker.

    The walker stops at the first imbalance and raises
    ``LatexWalkerParseError`` carrying the kind, position, and (for closings)
    the expected/actual environment name. We translate that into a single
    diagnostic. Returning one well-located diagnostic is intentional — earlier
    versions reported cascading false positives that all stemmed from one real
    error.
    """
    try:
        make_walker(text, tolerant=False).get_latex_nodes()
        return []
    except LatexWalkerParseError as exc:
        diagnostic = _translate_balance_error(text, exc, root_file)
        return [diagnostic] if diagnostic is not None else []


def _translate_balance_error(
    text: str,
    exc: LatexWalkerParseError,
    root_file: Path | None,
) -> Diagnostic | None:
    msg = (exc.msg or "").strip()
    err_pos = int(getattr(exc, "pos", 0) or 0)
    err_line = int(getattr(exc, "lineno", 0) or 0) or _line_for_offset(text, err_pos)

    mismatch = _MISMATCH_RE.search(msg)
    if mismatch:
        closed, expected = mismatch.group(1), mismatch.group(2)
        # A "mismatched" close where the supposedly-mismatched env was never
        # opened is really an extra \end — fall through to that branch.
        if _find_begin_line_before(text, err_pos, closed) is not None:
            open_line = _find_begin_line_before(text, err_pos, expected)
            location = f"第 {open_line} 行" if open_line else "前面"
            return Diagnostic(
                severity=SEVERITY_ERROR,
                title="环境嵌套不匹配",
                message=f"这里结束了 {closed}，但最近打开的是 {expected}（{location}）。",
                file=root_file,
                line=err_line,
                raw_message=msg,
            )
        return Diagnostic(
            severity=SEVERITY_ERROR,
            title="多余的 end 环境",
            message=f"\\end{{{closed}}} 没有对应的 \\begin{{{closed}}}。",
            file=root_file,
            line=err_line,
            raw_message=msg,
        )

    unclosed = _UNCLOSED_RE.search(msg)
    if unclosed:
        env_name = unclosed.group(1)
        open_line = _find_begin_line_before(text, err_pos, env_name)
        return Diagnostic(
            severity=SEVERITY_ERROR,
            title="环境没有结束",
            message=f"\\begin{{{env_name}}} 没有对应的 \\end{{{env_name}}}。",
            file=root_file,
            line=open_line or err_line,
            raw_message=msg,
        )

    extra = _EXTRA_END_RE.search(msg)
    if extra:
        env_name = extra.group(1)
        return Diagnostic(
            severity=SEVERITY_ERROR,
            title="多余的 end 环境",
            message=f"\\end{{{env_name}}} 没有对应的 \\begin{{{env_name}}}。",
            file=root_file,
            line=err_line,
            raw_message=msg,
        )

    if not msg:
        return None
    return Diagnostic(
        severity=SEVERITY_ERROR,
        title="环境平衡错误",
        message=msg,
        file=root_file,
        line=err_line,
        raw_message=msg,
    )


_BEGIN_TEMPLATE = re.compile(r"\\begin\{")


def _find_begin_line_before(text: str, pos: int, env_name: str) -> int | None:
    """Return the line of the last ``\\begin{env_name}`` strictly before ``pos``.

    Uses the same parser to skip comments/verbatim regions so we don't latch onto
    fake ``\\begin{X}`` strings hidden inside opaque content.
    """
    try:
        nodes, _, _ = make_walker(text[:pos]).get_latex_nodes()
    except Exception:  # pragma: no cover - belt and braces
        nodes = []

    candidate_pos: int | None = None

    def visit(node_list) -> None:
        nonlocal candidate_pos
        for node in node_list:
            # LatexEnvironmentNode is matched, so by definition it wouldn't be
            # the unclosed one. But its children might contain a hanging \begin
            # that the tolerant parse swallowed; recurse through it.
            children = getattr(node, "nodelist", None)
            if children:
                visit(children)
            env_attr = getattr(node, "environmentname", None)
            if env_attr == env_name:
                candidate_pos = node.pos

    visit(nodes)

    if candidate_pos is None:
        # Fallback: scan raw text for a literal \begin{env_name}.
        marker = f"\\begin{{{env_name}}}"
        idx = text.rfind(marker, 0, pos)
        if idx < 0:
            return None
        candidate_pos = idx

    return text.count("\n", 0, candidate_pos) + 1


def _line_for_regex_value(text: str, pattern: re.Pattern[str], value: str) -> int | None:
    for match in pattern.finditer(text):
        if match.group(1) == value:
            return _line_for_offset(text, match.start())
    return None


def _image_exists(project_dir: Path, raw_path: str) -> bool:
    if raw_path.startswith(("http://", "https://")):
        return True
    path = Path(raw_path).expanduser()
    candidates: list[Path]
    if path.is_absolute():
        candidates = [path]
    else:
        candidates = [project_dir / path]
    if path.suffix:
        return any(candidate.exists() for candidate in candidates)
    suffixes = (".pdf", ".png", ".jpg", ".jpeg")
    return any(candidate.exists() or any(candidate.with_suffix(suffix).exists() for suffix in suffixes) for candidate in candidates)


def _dedupe_diagnostics(diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    seen: set[tuple[str, str, str, str | None, int | None, tuple[str, ...]]] = set()
    unique: list[Diagnostic] = []
    for diagnostic in diagnostics:
        key = (
            diagnostic.severity,
            diagnostic.title,
            diagnostic.message,
            str(diagnostic.file) if diagnostic.file else None,
            diagnostic.line,
            diagnostic.fix.packages if diagnostic.fix else (),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(diagnostic)
    return unique
