from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from pylatexenc.latexwalker import (
    LatexCharsNode,
    LatexCommentNode,
    LatexEnvironmentNode,
    LatexGroupNode,
    LatexMacroNode,
    LatexMathNode,
    LatexNode,
    LatexSpecialsNode,
)

from app.core.latex_parser import make_walker
from app.core.file_observation import FileSignature, file_signature
from app.core.latex_tools import LaTeXToolchain, detect_toolchain
from app.core.paths import (
    included_tex_files_with_positions_from_text,
    normalize_path,
    resolve_included_tex_path,
    strip_latex_comments,
)
from app.core.process_env import latex_subprocess_env
from app.core.text_encoding import LatexTextDecodeError, decode_latex_bytes


# Match Unicode ideographs rather than the broader ``Han`` script property.
# TeXcount's ``-chinese`` preset uses ``Han``, whose script extensions also
# contain punctuation such as U+3002 IDEOGRAPHIC FULL STOP and U+3001 IDEOGRAPHIC
# COMMA.  Those marks must not become words.  Keep the Python fallback aligned
# with TeXcount's narrower ``Ideographic`` property, including supplementary
# CJK extension and compatibility planes.
CJK_RANGES = (
    "\u3007"
    "\u3400-\u4dbf"
    "\u4e00-\u9fff"
    "\uf900-\ufaff"
    "\U00020000-\U0002ee5f"
    "\U0002f800-\U0002fa1f"
    "\U00030000-\U000323af"
)
NON_CJK_LETTER = rf"[^\W\d_{CJK_RANGES}]"
WORD_PATTERN = rf"(?:{NON_CJK_LETTER}+(?:[-'’]{NON_CJK_LETTER}+)*|[{CJK_RANGES}])"
WORD_RE = re.compile(WORD_PATTERN, re.UNICODE)
NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?(?:\d+(?:[.,]\d+)*)(?:[eE][-+]?\d+)?%?(?![A-Za-z])")
TOKEN_RE = re.compile(
    r"(?P<number>(?<![A-Za-z])[-+]?(?:\d+(?:[.,]\d+)*)(?:[eE][-+]?\d+)?%?(?![A-Za-z]))"
    rf"|(?P<word>{WORD_PATTERN})",
    re.UNICODE,
)
INCLUDE_TARGET_RE = re.compile(r"(?P<prefix>\\(?:input|include|subfile)\s*\{)(?P<target>[^}]+)(?P<suffix>\})")
TEXCOUNT_MARKER = "ICSTEX_WORDCOUNT"
TEXCOUNT_TEMPLATE = f"{TEXCOUNT_MARKER}\t{{1}}\t{{2}}\t{{3}}\t{{4}}\t{{5}}\t{{6}}\t{{7}}\t{{SUM}}\n"
TEXCOUNT_SUM_WEIGHTS = "-sum=1,1,1,0,0,0,0"
TEXCOUNT_LOGOGRAMS = "-logograms=Ideographic"
TC_COMMENT_RE = re.compile(r"^%*[ \t]*TC:[ \t]*(ignore|endignore)\b", re.IGNORECASE)

HEADER_COMMANDS = {
    "title",
    "part",
    "chapter",
    "section",
    "subsection",
    "subsubsection",
    "paragraph",
    "subparagraph",
}
CAPTION_COMMANDS = {"caption", "captionof"}
NOTE_COMMANDS = {"endnote", "footnote", "footnotetext", "marginpar", "thanks"}
NON_TEXT_COMMANDS = {
    "addbibresource",
    "autocite",
    "autoref",
    "bibliography",
    "bibliographystyle",
    "cite",
    "citealp",
    "citealt",
    "citep",
    "citet",
    "documentclass",
    "eqref",
    "include",
    "includegraphics",
    "input",
    "label",
    "pageref",
    "parencite",
    "ref",
    "textcite",
    "url",
    "usepackage",
}
BOUNDARY_COMMANDS = {
    "autocite",
    "autoref",
    "cite",
    "citealp",
    "citealt",
    "citep",
    "citet",
    "eqref",
    "include",
    "includegraphics",
    "input",
    "pageref",
    "parencite",
    "ref",
    "subfile",
    "textcite",
    "url",
}
BOUNDARY_SYMBOL_COMMANDS = {
    " ", "#", "$", "%", "&", "P", "S",
    ",", ":", ";", "!",
    "enspace", "hfill", "hspace", "ldots", "negthinspace", "quad", "qquad",
    "slash", "textbackslash", "textemdash", "textendash", "thinspace", "vspace",
}
TRANSPARENT_SYMBOL_COMMANDS = {"_", "{", "}"}
FORMATTING_COMMANDS = {
    "emph",
    "enquote",
    "mbox",
    "textbf",
    "textit",
    "textmd",
    "textnormal",
    "textrm",
    "textsc",
    "textsf",
    "textsl",
    "textsubscript",
    "textsuperscript",
    "texttt",
    "textup",
    "underline",
}
ACCENT_COMMANDS = {
    "'", "`", '"', "^", "~", ".", "=",
    "H", "b", "c", "d", "k", "r", "t", "u", "v",
}
TEXT_COMMAND_REPLACEMENTS = {
    "AA": "Å",
    "AE": "Æ",
    "DH": "Ð",
    "DJ": "Đ",
    "L": "Ł",
    "LaTeX": "LaTeX",
    "NG": "Ŋ",
    "O": "Ø",
    "OE": "Œ",
    "SS": "SS",
    "TH": "Þ",
    "TeX": "TeX",
    "aa": "å",
    "ae": "æ",
    "dh": "ð",
    "dj": "đ",
    "i": "ı",
    "j": "ȷ",
    "l": "ł",
    "ng": "ŋ",
    "o": "ø",
    "oe": "œ",
    "ss": "ß",
    "th": "þ",
}
DISPLAY_MATH_ENV_NAMES = {
    "equation", "equation*",
    "align", "align*", "alignat", "alignat*",
    "gather", "gather*", "multline", "multline*",
    "displaymath",
    "eqnarray", "eqnarray*",
}
VERBATIM_ENV_NAMES = {"verbatim", "verbatim*", "lstlisting", "minted", "Verbatim"}
# texcount already excludes the bibliography list; mirror that in the fallback so a
# manually-written \begin{thebibliography} block is not counted as body text.
BIBLIOGRAPHY_ENV_NAMES = {"thebibliography"}


@dataclass(frozen=True)
class WordCountSegment:
    text: str
    category: str
    source: str | None = None


@dataclass(frozen=True)
class WordCountResult:
    total_words: int
    effective_words: int
    header_words: int
    caption_words: int
    math_inline: int
    math_display: int
    numbers: int
    source: str
    details: str = ""
    warnings: tuple[str, ...] = ()
    visual_segments: tuple[WordCountSegment, ...] = ()

    @property
    def words(self) -> int:
        return self.total_words

    @property
    def formulas(self) -> int:
        return self.math_inline + self.math_display


@dataclass(frozen=True)
class _TextBreakdown:
    body_words: int
    header_words: int
    caption_words: int
    body_numbers: int
    header_numbers: int
    caption_numbers: int
    math_inline: int
    math_display: int
    visual_segments: tuple[WordCountSegment, ...] = ()

    @property
    def numbers(self) -> int:
        return self.body_numbers + self.header_numbers + self.caption_numbers

    @property
    def total_words(self) -> int:
        return self.body_words + self.header_words + self.caption_words + self.numbers


@dataclass(frozen=True)
class _ProjectText:
    path: Path
    text: str
    initial_in_document: bool | None


@dataclass(frozen=True)
class _ProjectAnalysis:
    breakdown: _TextBreakdown
    sources: tuple[_ProjectText, ...]
    warnings: tuple[str, ...] = ()
    # True when direct texcount input would differ from the decoded project
    # analyzed for the preview. The shadow tree normalizes supported encodings
    # and replaces unreadable child sources with empty UTF-8 placeholders.
    needs_utf8_shadow: bool = False
    texcount_safe: bool = True


@dataclass(frozen=True)
class WordCountSnapshot:
    result: WordCountResult
    disk_signatures: tuple[tuple[Path, FileSignature], ...] = ()
    stable: bool = True

    def is_current(self) -> bool:
        return self.stable and all(file_signature(path) == value for path, value in self.disk_signatures)


def count_words(path: str | Path, toolchain: LaTeXToolchain | None = None) -> WordCountResult:
    tex_file = Path(path)
    return count_project(tex_file, toolchain=toolchain)


def count_project(
    root_path: str | Path,
    source_overrides: dict[Path, str] | None = None,
    toolchain: LaTeXToolchain | None = None,
) -> WordCountResult:
    """Count a root project without writing editor buffers into user files."""
    root = normalize_path(root_path)
    overrides = {
        normalize_path(path): text
        for path, text in (source_overrides or {}).items()
    }
    analysis = _analyze_project(root, overrides)
    return _count_project_analysis(root, overrides, analysis, toolchain)


def count_project_snapshot(
    root_path: str | Path,
    source_overrides: dict[Path, str],
    toolchain: LaTeXToolchain,
) -> WordCountSnapshot:
    """Count immutable buffers and reject disk dependencies changed during work.

    TeXcount consumes the same isolated shadow sources as the structured
    analysis rather than rereading live files, even for a child-only editor.
    This envelope is internal; WordCountResult and MCP fields stay unchanged.
    """
    root = normalize_path(root_path)
    overrides = {normalize_path(path): text for path, text in source_overrides.items()}
    observed: dict[Path, FileSignature] = {}
    unstable: list[Path] = []
    analysis = _analyze_project(root, overrides, observed=observed, unstable=unstable)
    # Force the snapshot/shadow route even if only a child buffer was open.
    captured = {source.path: source.text for source in analysis.sources}
    result = _count_project_analysis(root, captured, analysis, toolchain)
    snapshot = WordCountSnapshot(result, tuple(observed.items()), not unstable)
    return snapshot


def _count_project_analysis(
    root: Path, overrides: dict[Path, str], analysis: _ProjectAnalysis,
    toolchain: LaTeXToolchain | None,
) -> WordCountResult:
    if not analysis.sources:
        details = analysis.warnings[0] if analysis.warnings else "File could not be read."
        return _empty_result("fallback", details, warnings=analysis.warnings)

    tools = toolchain or detect_toolchain()
    if tools.texcount and analysis.texcount_safe:
        result = _count_project_with_texcount(root, overrides, analysis, tools.texcount)
        if result is not None:
            return result
        return _result_from_breakdown(
            analysis.breakdown,
            source="fallback",
            warnings=(*analysis.warnings, _texcount_failed_warning()),
        )
    if tools.texcount:
        return _result_from_breakdown(
            analysis.breakdown,
            source="fallback",
            warnings=(*analysis.warnings, _texcount_unsafe_project_warning()),
        )
    return _result_from_breakdown(
        analysis.breakdown,
        source="fallback",
        warnings=(*analysis.warnings, _texcount_missing_warning()),
    )


def count_text(
    text: str,
    source_path: str | Path | None = None,
    toolchain: LaTeXToolchain | None = None,
) -> WordCountResult:
    tools = toolchain or detect_toolchain()
    source = Path(source_path) if source_path is not None else None
    if tools.texcount:
        result = _count_text_with_texcount(text, source, tools.texcount)
        if result is not None:
            return result
        return _count_fallback_text(text, source="fallback", warnings=(_texcount_failed_warning(),))
    return _count_fallback_text(text, source="fallback", warnings=(_texcount_missing_warning(),))


def _count_file_with_texcount(
    tex_file: Path,
    text: str,
    executable: str,
    *,
    supplemental: _TextBreakdown | None = None,
    warnings: tuple[str, ...] = (),
) -> WordCountResult | None:
    return _run_texcount(
        [str(tex_file)],
        executable,
        text=text,
        cwd=tex_file.parent,
        source="texcount",
        supplemental=supplemental,
        warnings=warnings,
    )


def _count_text_with_texcount(text: str, source_path: Path | None, executable: str) -> WordCountResult | None:
    cwd = source_path.parent if source_path is not None else None
    args: list[str] = []
    if cwd is not None:
        args.append(f"-dir={_texcount_dir(cwd)}")
    args.append("-")
    return _run_texcount(args, executable, text=text, cwd=cwd, source="texcount live buffer", stdin=text)


def _count_project_with_texcount(
    root: Path,
    overrides: dict[Path, str],
    analysis: _ProjectAnalysis,
    executable: str,
) -> WordCountResult | None:
    root_text = next((source.text for source in analysis.sources if source.path == root), None)
    if root_text is None:
        return None
    if not overrides and not analysis.needs_utf8_shadow:
        return _count_file_with_texcount(
            root,
            root_text,
            executable,
            supplemental=analysis.breakdown,
            warnings=analysis.warnings,
        )

    try:
        with TemporaryDirectory(prefix="icstex-wordcount-") as directory:
            shadow_root = _write_shadow_project(Path(directory), root, analysis.sources)
            return _count_file_with_texcount(
                shadow_root,
                root_text,
                executable,
                supplemental=analysis.breakdown,
                warnings=analysis.warnings,
            )
    except (OSError, ValueError):
        return None


def _write_shadow_project(directory: Path, root: Path, sources: tuple[_ProjectText, ...]) -> Path:
    try:
        common_parent = Path(os.path.commonpath([str(source.path.parent) for source in sources]))
        mapped = {
            source.path: directory / source.path.relative_to(common_parent)
            for source in sources
        }
    except ValueError:
        # Windows absolute includes may cross drive letters. Direct include
        # targets are rewritten below, so a deterministic flat mapping is safe.
        mapped = {
            source.path: directory / f"source-{index:03d}" / source.path.name
            for index, source in enumerate(sources)
        }
    for source in sources:
        target = mapped[source.path]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_rewrite_shadow_includes(source, mapped), encoding="utf-8")
    return mapped[root]


def _rewrite_shadow_includes(source: _ProjectText, mapped: dict[Path, Path]) -> str:
    def replace(match: re.Match[str]) -> str:
        included = resolve_included_tex_path(source.path, match.group("target"))
        shadow = mapped.get(included) if included is not None else None
        if shadow is None:
            return match.group(0)
        return f'{match.group("prefix")}{shadow.as_posix()}{match.group("suffix")}'

    return INCLUDE_TARGET_RE.sub(replace, source.text)


def _run_texcount(
    target_args: list[str],
    executable: str,
    *,
    text: str,
    cwd: Path | None,
    source: str,
    stdin: str | None = None,
    supplemental: _TextBreakdown | None = None,
    warnings: tuple[str, ...] = (),
) -> WordCountResult | None:
    try:
        process = subprocess.run(
            [
                executable,
                "-merge",
                "-utf8",
                TEXCOUNT_LOGOGRAMS,
                TEXCOUNT_SUM_WEIGHTS,
                f"-template={TEXCOUNT_TEMPLATE}",
                *target_args,
            ],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=latex_subprocess_env(),
            cwd=str(cwd) if cwd is not None else None,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if process.returncode != 0:
        return None
    values = _parse_texcount_output(process.stdout)
    if values is None:
        return None

    supplemental = supplemental or _analyze_latex_text(text)
    text_words, header_words, caption_words, _headers, _floats, math_inline, math_display, _sum = values
    effective_words = max(0, text_words - supplemental.body_numbers)
    header_text_words = max(0, header_words - supplemental.header_numbers)
    caption_text_words = max(0, caption_words - supplemental.caption_numbers)
    total_words = effective_words + header_text_words + caption_text_words + supplemental.numbers
    details = "\n".join(part for part in (process.stdout.strip(), process.stderr.strip()) if part)
    return WordCountResult(
        total_words=total_words,
        effective_words=effective_words,
        header_words=header_text_words,
        caption_words=caption_text_words,
        math_inline=math_inline,
        math_display=math_display,
        numbers=supplemental.numbers,
        source=source,
        details=details,
        warnings=warnings,
        visual_segments=supplemental.visual_segments,
    )


def _parse_texcount_output(stdout: str) -> tuple[int, int, int, int, int, int, int, int] | None:
    for line in stdout.splitlines():
        if not line.startswith(f"{TEXCOUNT_MARKER}\t"):
            continue
        parts = line.split("\t")
        if len(parts) < 9:
            return None
        try:
            return tuple(int(value.strip()) for value in parts[1:9])  # type: ignore[return-value]
        except ValueError:
            return None
    return None


def _count_fallback_text(text: str, source: str, warnings: tuple[str, ...] = ()) -> WordCountResult:
    breakdown = _analyze_latex_text(text)
    return _result_from_breakdown(breakdown, source=source, warnings=warnings)


def _result_from_breakdown(
    breakdown: _TextBreakdown,
    *,
    source: str,
    warnings: tuple[str, ...] = (),
) -> WordCountResult:
    return WordCountResult(
        total_words=breakdown.total_words,
        effective_words=breakdown.body_words,
        header_words=breakdown.header_words,
        caption_words=breakdown.caption_words,
        math_inline=breakdown.math_inline,
        math_display=breakdown.math_display,
        numbers=breakdown.numbers,
        source=source,
        warnings=warnings,
        visual_segments=breakdown.visual_segments,
    )


def _texcount_missing_warning() -> str:
    return "未找到 TeXcount，已使用 ICSTeX 本地结构化统计；结果可能与 TeXcount 不同。"


def _texcount_failed_warning() -> str:
    return "TeXcount 调用失败，已自动降级为 ICSTeX 本地结构化统计。"


def _texcount_unsafe_project_warning() -> str:
    return "项目存在循环引用或展开超限，已跳过 TeXcount 以避免递归卡住。"


def _empty_result(
    source: str,
    details: str = "",
    *,
    warnings: tuple[str, ...] = (),
) -> WordCountResult:
    return WordCountResult(
        total_words=0,
        effective_words=0,
        header_words=0,
        caption_words=0,
        math_inline=0,
        math_display=0,
        numbers=0,
        source=source,
        details=details,
        warnings=warnings,
    )


# --- pylatexenc-based fallback -------------------------------------------


class _Accum:
    __slots__ = (
        "source_text",
        "source_label",
        "text_parts",
        "math_inline", "math_display",
        "visual_segments",
    )

    def __init__(self, source_text: str, source_label: str | None = None) -> None:
        self.source_text = source_text
        self.source_label = source_label
        self.text_parts: dict[str, list[str]] = {
            "body": [],
            "header": [],
            "caption": [],
        }
        self.math_inline = 0
        self.math_display = 0
        self.visual_segments: list[WordCountSegment] = []

    def add_chars(self, chars: str, category: str) -> None:
        self.text_parts[category].append(chars)
        if category == "header":
            visual_category = "headers"
        elif category == "caption":
            visual_category = "captions"
        else:
            visual_category = "effective"
        self.add_text_segments(chars, visual_category)

    def add_boundary(self, category: str) -> None:
        parts = self.text_parts[category]
        if parts and not parts[-1].endswith((" ", "\t", "\r", "\n")):
            parts.append(" ")
            if category == "header":
                visual_category = "headers"
            elif category == "caption":
                visual_category = "captions"
            else:
                visual_category = "effective"
            self.add_segment(" ", visual_category)

    def category_text(self, category: str) -> str:
        return "".join(self.text_parts[category])

    def add_text_segments(self, chars: str, category: str) -> None:
        if not chars:
            return
        cursor = 0
        for match in TOKEN_RE.finditer(chars):
            if match.start() > cursor:
                self.add_segment(chars[cursor : match.start()], category)
            token_category = "numbers" if match.group("number") else category
            self.add_segment(match.group(0), token_category)
            cursor = match.end()
        if cursor < len(chars):
            self.add_segment(chars[cursor:], category)

    def add_math_segment(self, node: LatexNode, category: str) -> None:
        text = self.source_text[node.pos : node.pos + node.len].strip()
        self.add_segment(text or "[formula]", category)

    def add_segment(self, text: str, category: str) -> None:
        if not text:
            return
        if (
            self.visual_segments
            and self.visual_segments[-1].category == category
            and self.visual_segments[-1].source == self.source_label
        ):
            previous = self.visual_segments[-1]
            self.visual_segments[-1] = WordCountSegment(previous.text + text, category, self.source_label)
            return
        self.visual_segments.append(WordCountSegment(text, category, self.source_label))


def _analyze_project(
    root: Path, overrides: dict[Path, str], *,
    observed: dict[Path, FileSignature] | None = None,
    unstable: list[Path] | None = None,
) -> _ProjectAnalysis:
    sources: list[_ProjectText] = []
    warnings: list[str] = []
    shadow_required_sources: list[Path] = []
    texcount_safe = True

    def visit(
        path: Path,
        initial_in_document: bool | None,
        ancestors: tuple[Path, ...],
    ) -> None:
        nonlocal texcount_safe
        normalized = normalize_path(path)
        if len(sources) >= 200:
            texcount_safe = False
            limit_warning = "项目引用展开超过 200 次，字数统计已停止继续展开。"
            if limit_warning not in warnings:
                warnings.append(limit_warning)
            return
        if normalized in ancestors:
            texcount_safe = False
            warnings.append(f"检测到循环引用，已停止继续展开：{_source_label(normalized, root)}。")
            return
        text = overrides.get(normalized)
        if text is None:
            before = file_signature(normalized) if observed is not None else None
            if observed is not None:
                if normalized in observed and observed[normalized] != before and unstable is not None:
                    unstable.append(normalized)
                observed.setdefault(normalized, before)
            try:
                data = normalized.read_bytes()
            except OSError:
                warnings.append(f"无法读取引用文件：{_source_label(normalized, root)}。")
                if normalized != root:
                    shadow_required_sources.append(normalized)
                    sources.append(_ProjectText(normalized, "", initial_in_document))
                return
            if observed is not None and file_signature(normalized) != before and unstable is not None:
                unstable.append(normalized)
            try:
                decoded = decode_latex_bytes(data)
                text = decoded.text
                if decoded.encoding != "utf-8":
                    shadow_required_sources.append(normalized)
            except LatexTextDecodeError as exc:
                warnings.append(
                    f"无法按 {exc.encoding} 解码引用文件：{_source_label(normalized, root)}；"
                    "请先在编辑器中打开并选择正确编码。"
                )
                if normalized != root:
                    shadow_required_sources.append(normalized)
                    sources.append(_ProjectText(normalized, "", initial_in_document))
                return
        sources.append(_ProjectText(normalized, text, initial_in_document))
        dependency_text = _mask_texcount_ignored_regions(text)
        clean_text = strip_latex_comments(dependency_text)
        begin_document = clean_text.find("\\begin{document}")
        end_document = clean_text.find("\\end{document}")
        inherited_context = True if initial_in_document is None else initial_in_document
        for child, position in included_tex_files_with_positions_from_text(normalized, dependency_text):
            child_in_document = inherited_context
            if begin_document >= 0:
                child_in_document = position > begin_document and (
                    end_document < 0 or position < end_document
                )
            visit(child, child_in_document, (*ancestors, normalized))

    visit(root, None, ())
    breakdowns = tuple(
        _analyze_latex_text(
            source.text,
            source_label=_source_label(source.path, root),
            initial_in_document=source.initial_in_document,
        )
        for source in sources
    )
    return _ProjectAnalysis(
        breakdown=_merge_breakdowns(breakdowns),
        sources=tuple(sources),
        warnings=tuple(dict.fromkeys(warnings)),
        needs_utf8_shadow=bool(shadow_required_sources),
        texcount_safe=texcount_safe,
    )


def _source_label(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root.parent).as_posix()
    except ValueError:
        return path.name


def _merge_breakdowns(breakdowns: tuple[_TextBreakdown, ...]) -> _TextBreakdown:
    return _TextBreakdown(
        body_words=sum(item.body_words for item in breakdowns),
        header_words=sum(item.header_words for item in breakdowns),
        caption_words=sum(item.caption_words for item in breakdowns),
        body_numbers=sum(item.body_numbers for item in breakdowns),
        header_numbers=sum(item.header_numbers for item in breakdowns),
        caption_numbers=sum(item.caption_numbers for item in breakdowns),
        math_inline=sum(item.math_inline for item in breakdowns),
        math_display=sum(item.math_display for item in breakdowns),
        visual_segments=tuple(segment for item in breakdowns for segment in item.visual_segments),
    )


def _analyze_latex_text(
    text: str,
    source_label: str | None = None,
    initial_in_document: bool | None = None,
) -> _TextBreakdown:
    text = _mask_texcount_ignored_regions(text)
    accum = _Accum(text, source_label)
    nodes = _parse_nodes(text)
    if "\\begin{document}" in text:
        in_document = False
    elif initial_in_document is None:
        in_document = True
    else:
        in_document = initial_in_document
    _walk(nodes, accum, in_document=in_document, category="body")
    body_text = accum.category_text("body")
    header_text = accum.category_text("header")
    caption_text = accum.category_text("caption")
    return _TextBreakdown(
        body_words=len(WORD_RE.findall(body_text)),
        header_words=len(WORD_RE.findall(header_text)),
        caption_words=len(WORD_RE.findall(caption_text)),
        body_numbers=len(NUMBER_RE.findall(body_text)),
        header_numbers=len(NUMBER_RE.findall(header_text)),
        caption_numbers=len(NUMBER_RE.findall(caption_text)),
        math_inline=accum.math_inline,
        math_display=accum.math_display,
        visual_segments=tuple(accum.visual_segments),
    )


def _mask_texcount_ignored_regions(text: str) -> str:
    """Mask standard ``%TC:ignore`` regions without changing source offsets."""
    if "tc:" not in text.lower():
        return text
    nodes = _parse_nodes(text)
    directives: list[tuple[LatexCommentNode, str]] = []
    for node in _descendant_nodes(nodes):
        if not isinstance(node, LatexCommentNode):
            continue
        directive = TC_COMMENT_RE.match(node.comment)
        if directive is not None:
            directives.append((node, directive.group(1).lower()))

    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for node, command in sorted(directives, key=lambda item: item[0].pos):
        if command == "ignore" and start is None:
            start = node.pos
        elif command == "endignore" and start is not None:
            ranges.append((start, node.pos + node.len))
            start = None
    if start is not None:
        ranges.append((start, len(text)))
    if not ranges:
        return text

    masked = list(text)
    for first, last in ranges:
        for index in range(first, last):
            if masked[index] not in "\r\n":
                masked[index] = " "
    return "".join(masked)


def _descendant_nodes(nodes: list[LatexNode]):
    for node in nodes:
        yield node
        if isinstance(node, (LatexEnvironmentNode, LatexGroupNode)):
            yield from _descendant_nodes(node.nodelist)
        elif isinstance(node, LatexMacroNode):
            for arg in _arg_iter(node):
                if isinstance(arg, LatexGroupNode):
                    yield from _descendant_nodes(arg.nodelist)


def _parse_nodes(text: str) -> list[LatexNode]:
    walker = make_walker(text)
    nodes, _, _ = walker.get_latex_nodes()
    return nodes


def _walk(
    nodes: list[LatexNode],
    accum: _Accum,
    *,
    in_document: bool,
    category: str,
) -> None:
    for node in nodes:
        if isinstance(node, LatexCommentNode):
            continue
        if isinstance(node, LatexCharsNode):
            if category in ("header", "caption") or in_document:
                accum.add_chars(node.chars, category)
        elif isinstance(node, LatexMacroNode):
            _walk_macro(node, accum, in_document=in_document, category=category)
        elif isinstance(node, LatexEnvironmentNode):
            env_name = node.environmentname
            if env_name == "document":
                _walk(node.nodelist, accum, in_document=True, category=category)
            elif env_name in DISPLAY_MATH_ENV_NAMES:
                if in_document:
                    accum.add_boundary(category)
                    accum.math_display += 1
                    accum.add_math_segment(node, "math_display")
                    accum.add_boundary(category)
            elif env_name in VERBATIM_ENV_NAMES or env_name in BIBLIOGRAPHY_ENV_NAMES:
                accum.add_boundary(category)
                continue  # verbatim / bibliography list: not counted as body text
            else:
                accum.add_boundary(category)
                _walk(node.nodelist, accum, in_document=in_document, category=category)
                accum.add_boundary(category)
        elif isinstance(node, LatexMathNode):
            if not in_document:
                continue
            accum.add_boundary(category)
            if getattr(node, "displaytype", None) == "inline":
                accum.math_inline += 1
                accum.add_math_segment(node, "math_inline")
            else:
                accum.math_display += 1
                accum.add_math_segment(node, "math_display")
            accum.add_boundary(category)
        elif isinstance(node, LatexGroupNode):
            _walk(node.nodelist, accum, in_document=in_document, category=category)
        elif isinstance(node, LatexSpecialsNode):
            if category in ("header", "caption") or in_document:
                if node.specials_chars in {"~", "&"}:
                    accum.add_chars(" ", category)


def _walk_macro(
    node: LatexMacroNode,
    accum: _Accum,
    *,
    in_document: bool,
    category: str,
) -> None:
    name = node.macroname
    if name in NON_TEXT_COMMANDS:
        if name in BOUNDARY_COMMANDS:
            accum.add_boundary(category)
        return
    if name in {"verb", "lstinline"}:
        accum.add_boundary(category)
        return
    if name in {"\\", "linebreak", "newline", "par", "item"}:
        accum.add_boundary(category)
        return
    if name in BOUNDARY_SYMBOL_COMMANDS:
        accum.add_boundary(category)
        return
    if name in TRANSPARENT_SYMBOL_COMMANDS:
        return
    if name == "href":
        _walk_href_args(node, accum, in_document=in_document, category=category)
        return
    if name in HEADER_COMMANDS:
        accum.add_boundary(category)
        _walk_last_group_arg(node, accum, in_document=in_document, target_category="header")
        accum.add_boundary(category)
        return
    if name in CAPTION_COMMANDS:
        accum.add_boundary(category)
        # Ignore optional short captions and captionof's object type; the last
        # group is the text rendered with the figure/table.
        _walk_last_group_arg(node, accum, in_document=in_document, target_category="caption")
        accum.add_boundary(category)
        return
    if name in NOTE_COMMANDS:
        accum.add_boundary(category)
        _walk_last_group_arg(node, accum, in_document=in_document, target_category="caption")
        accum.add_boundary(category)
        return
    if name in TEXT_COMMAND_REPLACEMENTS:
        if category in ("header", "caption") or in_document:
            accum.add_chars(TEXT_COMMAND_REPLACEMENTS[name], category)
        return
    if name in ACCENT_COMMANDS or name in FORMATTING_COMMANDS:
        for arg in _arg_iter(node):
            if isinstance(arg, LatexGroupNode):
                _walk(arg.nodelist, accum, in_document=in_document, category=category)
            elif isinstance(arg, LatexCharsNode):
                if category in ("header", "caption") or in_document:
                    accum.add_chars(arg.chars, category)
        return
    # Unknown semantic macros are ambiguous. Count visible-looking arguments,
    # but keep boundaries so metadata arguments cannot merge neighbouring words.
    for arg in _arg_iter(node):
        if isinstance(arg, LatexGroupNode):
            accum.add_boundary(category)
            _walk(arg.nodelist, accum, in_document=in_document, category=category)
            accum.add_boundary(category)
        elif isinstance(arg, LatexCharsNode):
            if category in ("header", "caption") or in_document:
                accum.add_boundary(category)
                accum.add_chars(arg.chars, category)
                accum.add_boundary(category)


def _walk_href_args(node, accum, *, in_document, category):
    """Use only the second group arg (the display text), matching the regex behaviour."""
    groups = [arg for arg in _arg_iter(node) if isinstance(arg, LatexGroupNode)]
    if len(groups) >= 2:
        _walk(groups[1].nodelist, accum, in_document=in_document, category=category)
    elif groups:
        _walk(groups[0].nodelist, accum, in_document=in_document, category=category)


def _walk_last_group_arg(node, accum, *, in_document, target_category):
    last = None
    for arg in _arg_iter(node):
        if isinstance(arg, LatexGroupNode):
            last = arg
    if last is not None:
        accum.add_boundary(target_category)
        _walk(last.nodelist, accum, in_document=in_document, category=target_category)
        accum.add_boundary(target_category)


def _arg_iter(node: LatexMacroNode):
    if node.nodeargd is None:
        return ()
    return tuple(arg for arg in (node.nodeargd.argnlist or []) if arg is not None)


def _texcount_dir(path: Path) -> str:
    value = str(path)
    if not value.endswith(("/", "\\")):
        value += "/"
    return value
