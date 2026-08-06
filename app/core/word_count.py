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
)

from app.core.latex_parser import make_walker
from app.core.latex_tools import LaTeXToolchain, detect_toolchain
from app.core.paths import (
    included_tex_files_with_positions_from_text,
    normalize_path,
    resolve_included_tex_path,
    strip_latex_comments,
)
from app.core.process_env import latex_subprocess_env
from app.core.text_encoding import LatexTextDecodeError, decode_latex_bytes


CJK_RANGES = "\u3400-\u4dbf\u4e00-\u9fff"
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
    if not analysis.sources:
        details = analysis.warnings[0] if analysis.warnings else "File could not be read."
        return _empty_result("fallback", details, warnings=analysis.warnings)

    tools = toolchain or detect_toolchain()
    if tools.texcount:
        result = _count_project_with_texcount(root, overrides, analysis, tools.texcount)
        if result is not None:
            return result
        return _result_from_breakdown(
            analysis.breakdown,
            source="fallback",
            warnings=(*analysis.warnings, _texcount_failed_warning()),
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
                "-chinese",
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
    return "未找到 texcount，已使用 Python 简化统计。"


def _texcount_failed_warning() -> str:
    return "texcount 调用失败，已自动降级为 Python 简化统计。"


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
        "body_words", "body_numbers",
        "header_words", "header_numbers",
        "caption_words", "caption_numbers",
        "math_inline", "math_display",
        "visual_segments",
    )

    def __init__(self, source_text: str, source_label: str | None = None) -> None:
        self.source_text = source_text
        self.source_label = source_label
        self.body_words = 0
        self.body_numbers = 0
        self.header_words = 0
        self.header_numbers = 0
        self.caption_words = 0
        self.caption_numbers = 0
        self.math_inline = 0
        self.math_display = 0
        self.visual_segments: list[WordCountSegment] = []

    def add_chars(self, chars: str, category: str) -> None:
        words = len(WORD_RE.findall(chars))
        numbers = len(NUMBER_RE.findall(chars))
        if category == "header":
            self.header_words += words
            self.header_numbers += numbers
            visual_category = "headers"
        elif category == "caption":
            self.caption_words += words
            self.caption_numbers += numbers
            visual_category = "captions"
        else:
            self.body_words += words
            self.body_numbers += numbers
            visual_category = "effective"
        self.add_text_segments(chars, visual_category)

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


def _analyze_project(root: Path, overrides: dict[Path, str]) -> _ProjectAnalysis:
    seen: set[Path] = set()
    sources: list[_ProjectText] = []
    warnings: list[str] = []
    shadow_required_sources: list[Path] = []

    def visit(path: Path, initial_in_document: bool | None) -> None:
        normalized = normalize_path(path)
        if len(seen) >= 200:
            if "项目包含超过 200 个 TeX 文件，彩色预览已停止继续展开。" not in warnings:
                warnings.append("项目包含超过 200 个 TeX 文件，彩色预览已停止继续展开。")
            return
        if normalized in seen:
            warnings.append(f"重复或循环引用只在彩色预览中显示一次：{_source_label(normalized, root)}。")
            return
        seen.add(normalized)
        text = overrides.get(normalized)
        if text is None:
            try:
                data = normalized.read_bytes()
            except OSError:
                warnings.append(f"无法读取引用文件：{_source_label(normalized, root)}。")
                if normalized != root:
                    shadow_required_sources.append(normalized)
                    sources.append(_ProjectText(normalized, "", initial_in_document))
                return
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
        clean_text = strip_latex_comments(text)
        begin_document = clean_text.find("\\begin{document}")
        end_document = clean_text.find("\\end{document}")
        inherited_context = True if initial_in_document is None else initial_in_document
        for child, position in included_tex_files_with_positions_from_text(normalized, text):
            child_in_document = inherited_context
            if begin_document >= 0:
                child_in_document = position > begin_document and (
                    end_document < 0 or position < end_document
                )
            visit(child, child_in_document)

    visit(root, None)
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
    accum = _Accum(text, source_label)
    nodes = _parse_nodes(text)
    if "\\begin{document}" in text:
        in_document = False
    elif initial_in_document is None:
        in_document = True
    else:
        in_document = initial_in_document
    _walk(nodes, accum, in_document=in_document, category="body")
    return _TextBreakdown(
        body_words=accum.body_words,
        header_words=accum.header_words,
        caption_words=accum.caption_words,
        body_numbers=accum.body_numbers,
        header_numbers=accum.header_numbers,
        caption_numbers=accum.caption_numbers,
        math_inline=accum.math_inline,
        math_display=accum.math_display,
        visual_segments=tuple(accum.visual_segments),
    )


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
                    accum.math_display += 1
                    accum.add_math_segment(node, "math_display")
            elif env_name in VERBATIM_ENV_NAMES or env_name in BIBLIOGRAPHY_ENV_NAMES:
                continue  # verbatim / bibliography list: not counted as body text
            else:
                _walk(node.nodelist, accum, in_document=in_document, category=category)
        elif isinstance(node, LatexMathNode):
            if not in_document:
                continue
            if getattr(node, "displaytype", None) == "inline":
                accum.math_inline += 1
                accum.add_math_segment(node, "math_inline")
            else:
                accum.math_display += 1
                accum.add_math_segment(node, "math_display")
        elif isinstance(node, LatexGroupNode):
            _walk(node.nodelist, accum, in_document=in_document, category=category)


def _walk_macro(
    node: LatexMacroNode,
    accum: _Accum,
    *,
    in_document: bool,
    category: str,
) -> None:
    name = node.macroname
    if name in NON_TEXT_COMMANDS:
        return
    if name == "href":
        _walk_href_args(node, accum, in_document=in_document, category=category)
        return
    if name in HEADER_COMMANDS:
        _walk_first_group_arg(node, accum, in_document=in_document, target_category="header")
        return
    if name in CAPTION_COMMANDS:
        # caption: 1 group arg; captionof: take last group arg (the actual caption text)
        if name == "captionof":
            _walk_last_group_arg(node, accum, in_document=in_document, target_category="caption")
        else:
            _walk_first_group_arg(node, accum, in_document=in_document, target_category="caption")
        return
    # Any other macro: walk its arg groups so e.g. \textbf{Bold} or unknown macros still count.
    for arg in _arg_iter(node):
        if isinstance(arg, LatexGroupNode):
            _walk(arg.nodelist, accum, in_document=in_document, category=category)
        elif isinstance(arg, LatexCharsNode):
            if category in ("header", "caption") or in_document:
                accum.add_chars(arg.chars, category)


def _walk_href_args(node, accum, *, in_document, category):
    """Use only the second group arg (the display text), matching the regex behaviour."""
    groups = [arg for arg in _arg_iter(node) if isinstance(arg, LatexGroupNode)]
    if len(groups) >= 2:
        _walk(groups[1].nodelist, accum, in_document=in_document, category=category)
    elif groups:
        _walk(groups[0].nodelist, accum, in_document=in_document, category=category)


def _walk_first_group_arg(node, accum, *, in_document, target_category):
    for arg in _arg_iter(node):
        if isinstance(arg, LatexGroupNode):
            _walk(arg.nodelist, accum, in_document=in_document, category=target_category)
            return


def _walk_last_group_arg(node, accum, *, in_document, target_category):
    last = None
    for arg in _arg_iter(node):
        if isinstance(arg, LatexGroupNode):
            last = arg
    if last is not None:
        _walk(last.nodelist, accum, in_document=in_document, category=target_category)


def _arg_iter(node: LatexMacroNode):
    if node.nodeargd is None:
        return ()
    return tuple(arg for arg in (node.nodeargd.argnlist or []) if arg is not None)


def _texcount_dir(path: Path) -> str:
    value = str(path)
    if not value.endswith(("/", "\\")):
        value += "/"
    return value
