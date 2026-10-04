"""Source-backed document blocks; pylatexenc owns syntax, never serialization.

Positions are Python string offsets. Unknown syntax stays in its original
slice. Edits require the exact source snapshot; the GUI adds editor/revision
checks and applies one QTextCursor undo transaction. No files or Qt here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

from pylatexenc.latexwalker import (
    LatexCharsNode, LatexCommentNode, LatexEnvironmentNode, LatexMacroNode,
    LatexMathNode, LatexWalkerParseError,
)
from pylatexenc.latex2text import LatexNodes2Text

from app.core.latex_parser import make_walker
from app.core.blocks.latex_escape import LATEX_ESCAPES, escape_latex


HEADINGS = ("part", "chapter", "section", "subsection", "subsubsection", "paragraph", "subparagraph")
KINDS = {"figure": "image", "figure*": "image", "table": "table", "table*": "table",
         "tabular": "table", "tabular*": "table", "tabularx": "table", "longtable": "table",
         "equation": "formula", "equation*": "formula", "align": "formula", "align*": "formula",
         "gather": "formula", "gather*": "formula", "displaymath": "formula",
         "itemize": "list", "enumerate": "list", "description": "list",
         "quote": "text", "quotation": "text"}
# ponytail: bound this experimental outline; larger sources remain editable in
# the normal editor. Incremental parsing can replace this if measured needed.
MAX_STRUCTURE_CHARS = 500_000


@dataclass(frozen=True)
class SourceBlock:
    kind: str
    start: int
    end: int
    title: str
    level: int = -1
    header_end: int = 0
    argument: tuple[int, int] | None = None
    children: tuple["SourceBlock", ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass(frozen=True)
class Structure:
    source: str
    blocks: tuple[SourceBlock, ...]
    body_start: int
    body_end: int
    error: str = ""

    def walk(self):
        for block in self.blocks:
            yield from block.walk()

    def at(self, offset: int) -> SourceBlock | None:
        matches = [block for block in self.walk() if block.start <= offset < block.end]
        return min(matches, key=lambda block: block.end - block.start) if matches else None


@dataclass(frozen=True)
class SourceEdit:
    start: int
    end: int
    text: str


def _caption(node, source: str) -> tuple[str, tuple[int, int] | None]:
    args = getattr(getattr(node, "nodeargd", None), "argnlist", ()) or ()
    group = next((arg for arg in reversed(args) if getattr(arg, "delimiters", None) == ("{", "}")), None)
    if group is None:
        return "", None
    span = group.pos + 1, group.pos + group.len - 1
    return source[span[0]:span[1]], span


def readable_text(text: str) -> str:
    # Presentation only; never write this lossy readable string back to source.
    try:
        # The physical newline after \\\\ is source formatting, not a second break.
        value = LatexNodes2Text().latex_to_text(re.sub(r"(\\\\)[ \t]*\n", r"\1", text[:2000]))
    except (ValueError, RecursionError, LatexWalkerParseError):
        value = text[:2000]
    return re.sub(r"[^\S\n]+", " ", value).strip()


def _summary(text: str) -> str:
    return readable_text(text)[:180]


def plain_fragment(text: str) -> str | None:
    """Decode only reversible plain text; leave formatted LaTeX in code mode."""
    tokens = {value: key for key, value in LATEX_ESCAPES.items()}
    tokens[r"\\"] = "\n"
    tokens[r"\leavevmode{}"] = ""
    pattern = "|".join(re.escape(value) for value in sorted(tokens, key=len, reverse=True))
    parts, position = [], 0
    for match in re.finditer(pattern, text):
        literal = text[position:match.start()]
        if any(char in literal for char in LATEX_ESCAPES):
            return None
        parts.extend((literal, tokens[match.group()]))
        position = match.end()
        if match.group() == r"\\" and text[position:position + 1] == "\n":
            position += 1
    tail = text[position:]
    if any(char in tail for char in LATEX_ESCAPES):
        return None
    parts.append(tail)
    return "".join(parts)


def plain_fragment_source(text: str) -> str:
    """Enter is a visible line break; blank lines remain LaTeX paragraphs."""
    # A leading break needs horizontal mode, including an otherwise empty block.
    return "\n\n".join((r"\leavevmode{}" if "\n" in paragraph and not paragraph.split("\n", 1)[0].strip() else "") +
                       escape_latex(paragraph).replace("\n", "\\\\\n")
                       for paragraph in re.split(r"\n[ \t]*\n", text))


def table_cell_ranges(source: str, block: SourceBlock) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Exact editable cell spans, without regenerating table layout or captions.

    Merged cells, nested environments and comments inside cells are deliberately
    code-only. Empty cells have zero-width spans. Offsets refer to the full source.
    """
    nodes, _, _ = make_walker(source[block.start:block.end], tolerant=False).get_latex_nodes()
    def tables(nodes):
        found = []
        for node in nodes:
            if isinstance(node, LatexEnvironmentNode):
                if node.environmentname in {"tabular", "tabular*", "tabularx", "longtable"}:
                    found.append(node)
                elif node.environmentname in {"table", "table*", "center"}:
                    found.extend(tables(node.nodelist))
        return found
    found = tables(nodes)
    if len(found) != 1 or not found[0].nodelist:
        return ()
    fragment = source[block.start:block.end]
    children = found[0].nodelist
    start = children[0].pos
    rows, cells = [], []
    def cell(end):
        nonlocal start
        value = fragment[start:end]
        left = start + len(value) - len(value.lstrip())
        right = max(left, end - len(value) + len(value.rstrip()))
        cells.append((block.start + left, block.start + right))
    for child in children:
        if isinstance(child, LatexEnvironmentNode) or re.search(
                r"\\(?:multicolumn|multirow|endhead|endfirsthead|endfoot|endlastfoot|cline|cmidrule)\b",
                fragment[child.pos:child.pos + child.len]):
            return ()
        if isinstance(child, LatexCommentNode) or (isinstance(child, LatexMacroNode) and
                child.macroname in {"hline", "toprule", "midrule", "bottomrule"}):
            if fragment[start:child.pos].strip() or cells:
                return ()
            start = child.pos + child.len
        elif getattr(child, "specials_chars", None) == "&":
            cell(child.pos)
            start = child.pos + child.len
        elif isinstance(child, LatexMacroNode) and child.macroname == "\\":
            cell(child.pos)
            rows.append(tuple(cells))
            cells = []
            start = child.pos + child.len
    end = children[-1].pos + children[-1].len
    if cells or fragment[start:end].strip():
        cell(end)
        rows.append(tuple(cells))
    if not rows or len({len(row) for row in rows}) != 1 or sum(map(len, rows)) > 20_000:
        return ()
    return tuple(rows)


def _table_preview(node, source):
    """Readable cells for common tabular only; never a source conversion API."""
    if node.environmentname not in {"tabular", "tabular*", "tabularx", "longtable"}:
        tables = [n for n in node.nodelist if isinstance(n, LatexEnvironmentNode)
                  and n.environmentname in {"tabular", "tabular*", "tabularx", "longtable"}]
        return _table_preview(tables[0], source) if len(tables) == 1 else ()
    rows, cells, content = [], [], []
    for child in node.nodelist:
        if getattr(child, "specials_chars", None) == "&":
            cells.append(_summary("".join(content)))
            content = []
        elif isinstance(child, LatexMacroNode) and child.macroname == "\\":
            cells.append(_summary("".join(content)))
            rows.append(tuple(cells))
            cells, content = [], []
            if len(rows) >= 6:
                break
        elif isinstance(child, LatexMacroNode) and child.macroname in {"hline", "toprule", "midrule", "bottomrule"}:
            continue
        else:
            content.append(source[child.pos:child.pos + child.len])
    if cells or "".join(content).strip():
        rows.append(tuple(cells + [_summary("".join(content))]))
    return tuple(rows) if rows and max(map(len, rows)) <= 6 else ()


def parse_structure(source: str) -> Structure:
    """Parse an immutable snapshot off the GUI thread; reject partial syntax."""
    if len(source) > MAX_STRUCTURE_CHARS:
        return Structure(source, (), 0, len(source), "文件较大，请继续使用源码视图。")
    try:
        nodes, _, _ = make_walker(source, tolerant=False).get_latex_nodes()
    except (LatexWalkerParseError, RecursionError, ValueError):
        return Structure(source, (), 0, len(source), "源码结构尚未闭合，请在源码视图补全括号或环境。")
    documents = [n for n in nodes if isinstance(n, LatexEnvironmentNode) and n.environmentname == "document"]
    if len(documents) > 1:
        return Structure(source, (), 0, len(source), "存在多个 document 环境，请使用源码视图。")
    title = next((n for n in nodes if isinstance(n, LatexMacroNode) and n.macroname == "title"), None)
    if documents:
        document = documents[0]
        body_nodes = document.nodelist
        begin = source.find("}", document.pos) + 1
        closing = re.search(r"\\end\s*\{document\}\s*$", source[document.pos:document.pos + document.len])
        end = document.pos + closing.start() if closing else document.pos + document.len - len(r"\end{document}")
    else:
        body_nodes, begin, end = nodes, 0, len(source)
        title = None
    # LatexWalker does not expand TeX conditionals or category-code changes.
    # Do not offer structural writes when these can alter the apparent tree.
    dynamic = {"else", "fi", "or", "catcode", "csname", "endcsname", "def", "edef", "gdef", "xdef"}
    if any(isinstance(n, LatexMacroNode) and (n.macroname in dynamic or n.macroname.startswith("if"))
           for n in body_nodes) or re.search(r"\\catcode\b", source):
        return Structure(source, (), begin, end, "此文件含条件编译或动态 TeX 语法，请使用源码视图；原文保持不变。")
    flat: list[SourceBlock] = []
    pending: list = []

    def flush():
        if not pending:
            return
        a, b = pending[0].pos, pending[-1].pos + pending[-1].len
        # Blank lines inside macro arguments must not split a movable fragment.
        cuts = [a, b]
        for node in pending:
            if isinstance(node, LatexCharsNode):
                cuts.extend(node.pos + m.end() for m in re.finditer(r"\n[ \t]*\n", node.chars))
        cuts = sorted(set(cuts))
        for lo, hi in zip(cuts, cuts[1:]):
            text = source[lo:hi]
            if text.strip():
                raw = any(isinstance(n, (LatexMacroNode, LatexEnvironmentNode)) and lo <= n.pos < hi
                          and (not isinstance(n, LatexMacroNode) or n.macroname not in
                               {"textbf", "textit", "emph", "cite", "ref", "label", "footnote", "url", "href",
                                "\\", "newline", "par", "leavevmode", "textbackslash", "textasciitilde", "textasciicircum",
                                "#", "$", "%", "&", "_", "{", "}"})
                          for n in pending)
                flat.append(SourceBlock("raw" if raw else "text", lo, hi,
                                        _summary(text) or "自定义 LaTeX"))
        pending.clear()

    for node in body_nodes:
        if isinstance(node, LatexMacroNode) and node.macroname in HEADINGS:
            flush()
            label, argument = _caption(node, source)
            if argument is None:
                pending.append(node)
                continue
            flat.append(SourceBlock("section", node.pos, node.pos + node.len,
                                    _summary(label) or "未命名章节", HEADINGS.index(node.macroname),
                                    node.pos + node.len, argument))
        elif isinstance(node, LatexMathNode) and node.displaytype == "display":
            flush()
            flat.append(SourceBlock("formula", node.pos, node.pos + node.len,
                                    _summary(source[node.pos:node.pos + node.len])))
        elif isinstance(node, LatexEnvironmentNode):
            flush()
            kind = KINDS.get(node.environmentname, "raw")
            if node.environmentname == "center":
                substantive = [n for n in node.nodelist if not isinstance(n, LatexCommentNode)
                               and not (isinstance(n, LatexCharsNode) and not n.chars.strip())]
                if len(substantive) == 1 and isinstance(substantive[0], LatexEnvironmentNode):
                    kind = KINDS.get(substantive[0].environmentname, "raw")
            fragment = source[node.pos:node.pos + node.len]
            flat.append(SourceBlock(kind, node.pos, node.pos + node.len,
                                    _summary(fragment) or node.environmentname,
                                    rows=_table_preview(node, source) if kind == "table" else ()))
        elif isinstance(node, LatexMacroNode) and node.macroname == "maketitle" and documents:
            flush()  # Keep the command, without showing a duplicate title block.
        else:
            pending.append(node)
    flush()

    def nested(index: int, level: int, stop: int):
        items = []
        while index < len(flat):
            item = flat[index]
            if item.kind == "section" and item.level <= level:
                break
            index += 1
            if item.kind == "section":
                children, index = nested(index, item.level, stop)
                item = replace(item, end=flat[index].start if index < len(flat) else stop,
                               children=tuple(children))
            items.append(item)
        return items, index

    blocks, _ = nested(0, -1, end)
    if title is not None:
        label, argument = _caption(title, source)
        if argument is not None:
            blocks.insert(0, SourceBlock("title", title.pos, title.pos + title.len, _summary(label), argument=argument))
    return Structure(source, tuple(blocks), begin, end)


def require_block(snapshot: Structure, current: str, block: SourceBlock) -> None:
    if snapshot.error or current != snapshot.source or block not in tuple(snapshot.walk()):
        raise ValueError("内容已变化，请等待结构更新后再操作。")


def delete_block(snapshot: Structure, current: str, block: SourceBlock) -> SourceEdit:
    """Remove one body block (a section owns its subtree); retain title metadata."""
    require_block(snapshot, current, block)
    if block.kind == "title":
        # maketitle still needs a title declaration; clearing it is a valid title.
        return SourceEdit(*block.argument, "")
    return SourceEdit(block.start, block.end, "")


def replace_block(snapshot: Structure, current: str, block: SourceBlock, text: str) -> SourceEdit:
    require_block(snapshot, current, block)
    start, end = block.argument if block.kind in {"title", "section"} else (block.start, block.end)
    parsed = parse_structure(current[:start] + text + current[end:])
    if parsed.error:
        raise ValueError(parsed.error)
    return SourceEdit(start, end, text)


def move_block(snapshot: Structure, current: str, block: SourceBlock,
               target: SourceBlock, position: str) -> tuple[SourceEdit, ...]:
    """Descending range edits, to be applied as one undo operation.

    Sections own their whole subtree; dropping on a section appends a child.
    Heading levels change locally, body/comments are never reserialized.
    """
    require_block(snapshot, current, block)
    require_block(snapshot, current, target)
    if block.kind == "title" or target.kind == "title":
        raise ValueError("文稿标题不能作为章节拖动。")
    if position not in {"before", "after", "inside"}:
        raise ValueError("无效的放置位置。")
    if block.start <= target.start < block.end:
        raise ValueError("不能把内容放进它自身或子章节。")
    if position == "inside" and target.kind != "section":
        raise ValueError("只有章节可以容纳其他内容块。")
    destination = target.start if position == "before" else target.end
    fragment = current[block.start:block.end]
    if block.kind == "section":
        if target.kind != "section":
            raise ValueError("请将章节放到另一个章节旁边或内部。")
        delta = target.level + (position == "inside") - block.level
        headings = [item for item in block.walk() if item.kind == "section"]
        if any(not 0 <= item.level + delta < len(HEADINGS) for item in headings):
            raise ValueError("章节嵌套层级过深。")
        for item in reversed(headings):
            offset = item.start - block.start
            old = "\\" + HEADINGS[item.level]
            fragment = fragment[:offset] + "\\" + HEADINGS[item.level + delta] + fragment[offset + len(old):]
    fragment = "\n\n" + fragment.strip("\n") + "\n\n"
    edits = tuple(sorted((SourceEdit(block.start, block.end, ""),
                          SourceEdit(destination, destination, fragment)), key=lambda e: e.start, reverse=True))
    candidate = current
    for edit in edits:
        candidate = candidate[:edit.start] + edit.text + candidate[edit.end:]
    if parse_structure(candidate).error:
        raise ValueError("移动后源码结构不完整；原内容保持不变。")
    return edits
