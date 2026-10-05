"""Bounded specification edits for ordinary source tables; no Qt or file writes.

Cell text stays raw LaTeX. Reuse the insertion renderer only for recognized
tabular bodies. Comments/custom row rules/complex columns remain cell-only,
not silently normalized. Everything outside edited ranges is retained.
"""
from dataclasses import dataclass, replace
import re

from pylatexenc.latexwalker import LatexEnvironmentNode, LatexMacroNode, LatexWalkerParseError

from app.core.document_structure import SourceBlock, SourceEdit, table_cell_ranges
from app.core.latex_insertions import TableSpec, existing_packages, package_update, table_snippet
from app.core.latex_parser import make_walker


@dataclass(frozen=True)
class SourceTable:
    spec: TableSpec
    column_span: tuple[int, int]
    body_span: tuple[int, int]
    caption_span: tuple[int, int] | None
    label_span: tuple[int, int] | None
    placement_span: tuple[int, int] | None
    placement_insert: int | None
    metadata_insert: int | None
    has_rules: bool
    caption_command: tuple[int, int] | None
    label_command: tuple[int, int] | None


def read_source_table(source: str, block: SourceBlock) -> SourceTable | None:
    """Return a supported, rectangular table with exact full-source positions."""
    try:
        cells = table_cell_ranges(source, block)
    except (LatexWalkerParseError, RecursionError, ValueError):
        return None
    if not cells or not 2 <= len(cells) <= 41 or not 1 <= len(cells[0]) <= 12:
        return None
    fragment = source[block.start:block.end]
    nodes, _, _ = make_walker(fragment, tolerant=False).get_latex_nodes()
    found = []
    def visit(items, outer=None):
        for node in items:
            if not isinstance(node, LatexEnvironmentNode):
                continue
            if node.environmentname == "tabular":
                found.append((node, outer))
            elif node.environmentname in {"center", "table", "table*"}:
                visit(node.nodelist, node if node.environmentname.startswith("table") else outer)
    visit(nodes)
    if len(found) != 1:
        return None
    table, outer = found[0]
    def argument(node, delimiters=("{", "}")):
        args = getattr(getattr(node, "nodeargd", None), "argnlist", ()) or ()
        arg = next((a for a in reversed(args) if getattr(a, "delimiters", None) == delimiters), None)
        return (block.start + arg.pos + 1, block.start + arg.pos + arg.len - 1) if arg else None
    columns = argument(table)
    if columns is None:
        return None
    definition = source[slice(*columns)]
    letters = re.findall("[lcr]", definition)
    if not re.fullmatch(r"[lcr|\s]+", definition) or len(letters) != len(cells[0]):
        return None
    body = (block.start + table.nodelist[0].pos,
            block.start + table.nodelist[-1].pos + table.nodelist[-1].len)
    remainder = source[slice(*body)]
    for start, end in reversed([span for row in cells for span in row]):
        remainder = remainder[:start - body[0]] + remainder[end - body[0]:]
    # Only the generated/simple delimiters and rules may be regenerated.
    remainder = re.sub(r"\\(?:toprule|midrule|bottomrule|hline)\b", "", remainder)
    if remainder.replace("\\\\", "").replace("&", "").strip():
        return None
    caption = label = placement = placement_insert = metadata_insert = None
    caption_command = label_command = None
    if outer:
        metadata_nodes = list(outer.nodelist)
        for child in outer.nodelist:
            if isinstance(child, LatexEnvironmentNode) and child.environmentname == "center":
                metadata_nodes.extend(child.nodelist)
        for name in ("caption", "label"):
            matches = [n for n in metadata_nodes if isinstance(n, LatexMacroNode) and n.macroname == name]
            if len(matches) > 1:
                return None
            span = argument(matches[0]) if matches else None
            command = (block.start + matches[0].pos, block.start + matches[0].pos + matches[0].len) if matches else None
            if name == "caption":
                caption = span
                caption_command = command
            else:
                label = span
                label_command = command
        placement = argument(outer, ("[", "]"))
        begin = re.match(r"\\begin\s*\{[^}]+\}", fragment[outer.pos:])
        closing = re.search(r"\\end\s*\{[^}]+\}\s*$", fragment[outer.pos:outer.pos + outer.len])
        if not begin or not closing:
            return None
        placement_insert = block.start + outer.pos + begin.end()
        metadata_insert = block.start + outer.pos + closing.start()
    raw = tuple(tuple(source[a:b] for a, b in row) for row in cells)
    spec = TableSpec(rows=len(raw) - 1, columns=len(letters),
                     alignment=letters[0] if len(set(letters)) == 1 else "mixed",
                     use_booktabs=bool(re.search(r"\\toprule\b", source[slice(*body)])),
                     caption=source[slice(*caption)] if caption else "",
                     label=source[slice(*label)] if label else "",
                     placement=source[slice(*placement)] if placement else "htbp",
                     headers=raw[0], cells=raw[1:])
    return SourceTable(spec, columns, body, caption, label, placement, placement_insert,
                       metadata_insert, bool(re.search(r"\\(?:toprule|hline)\b", source[slice(*body)])),
                       caption_command, label_command)


def change_source_table(source: str, block: SourceBlock, requested: TableSpec) -> list[SourceEdit]:
    """Plan one undoable edit; caller confirms removal and guards revision/owner."""
    model = read_source_table(source, block)
    if model is None:
        raise ValueError("此表含复杂列格式、注释或自定义行规则；仍可改单元格，规格请用局部代码修改。")
    old = model.spec
    if not 1 <= requested.rows <= 40 or not 1 <= requested.columns <= 12:
        raise ValueError("表格支持 1–40 行数据、1–12 列。")
    if requested.alignment not in {"l", "c", "r", "mixed"}:
        raise ValueError("请选择有效的列对齐。")
    if not re.fullmatch(r"[\w:./-]*", requested.label):
        raise ValueError("标签可使用文字、数字、冒号、下划线、短横线和路径分隔符。")
    if requested.placement not in {"htbp", "H", "t", "b", "p", old.placement}:
        raise ValueError("请选择有效的浮动位置。")
    edits = []
    def patch(span, value):
        if source[slice(*span)] != value:
            edits.append(SourceEdit(*span, value))
    if (requested.rows, requested.columns, requested.use_booktabs) != (old.rows, old.columns, old.use_booktabs):
        rows = (old.headers, *old.cells)
        resized = tuple(tuple(rows[r][c] if r < len(rows) and c < len(rows[r]) else ""
                              for c in range(requested.columns)) for r in range(requested.rows + 1))
        generated = table_snippet(replace(requested, headers=resized[0], cells=resized[1:], caption="", label=""))
        generated_block = SourceBlock("table", 0, len(generated), "")
        generated_model = read_source_table(generated, generated_block)
        body = generated[slice(*generated_model.body_span)]
        if not model.has_rules and not requested.use_booktabs:
            # Renderer-owned rules only, not user cell macros containing this text.
            body = re.sub(r"(?m)^\s*\\hline[ \t]*$", "", body)
        patch(model.body_span, body)
    if (requested.columns, requested.alignment, requested.use_booktabs) != (old.columns, old.alignment, old.use_booktabs):
        definition = source[slice(*model.column_span)]
        if requested.alignment != "mixed":
            definition = re.sub("[lcr]", requested.alignment, definition)
        matches = list(re.finditer("[lcr]", definition))
        suffix = definition[matches[-1].end():]
        if requested.columns < len(matches):
            definition = definition[:matches[requested.columns - 1].end()] + suffix
        elif requested.columns > len(matches):
            separator = definition[matches[-2].end():matches[-1].start()] if len(matches) > 1 else ""
            definition = definition[:matches[-1].end()] + (separator + matches[-1].group()) * (requested.columns - len(matches)) + suffix
        if requested.use_booktabs != old.use_booktabs:
            letters = re.findall("[lcr]", definition)
            definition = "".join(letters) if requested.use_booktabs else "|" + "|".join(letters) + "|"
        patch(model.column_span, definition)
    additions = []
    for field, span in (("caption", model.caption_span), ("label", model.label_span)):
        value = getattr(requested, field)
        if value == getattr(old, field):
            continue
        if model.metadata_insert is None:
            raise ValueError("此表没有 table 浮动环境；题注与浮动设置请在代码中处理。")
        if span and not value:
            patch(getattr(model, field + "_command"), "")
        elif span:
            patch(span, value)
        elif value:
            command = "\\" + field + "{" + value + "}\n"
            if field == "caption" and model.label_command is not None:
                # A label must follow its caption to bind the table counter.
                position = model.label_command[0]
                edits.append(SourceEdit(position, position, command))
            else:
                additions.append(command)
    if additions:
        edits.append(SourceEdit(model.metadata_insert, model.metadata_insert, "".join(additions)))
    if requested.placement != old.placement:
        if model.placement_insert is None:
            raise ValueError("此表没有 table 浮动环境。")
        if model.placement_span:
            patch(model.placement_span, requested.placement)
        else:
            edits.append(SourceEdit(model.placement_insert, model.placement_insert, "[" + requested.placement + "]"))
    packages = []
    if requested.use_booktabs and not old.use_booktabs:
        packages.append("booktabs")
    if requested.placement == "H" and old.placement != "H":
        packages.append("float")
    missing = tuple(p for p in packages if p not in existing_packages(source))
    if missing:
        if not re.search(r"(?m)^[ \t]*\\documentclass(?:\[.*?\])?\s*\{", source):
            raise ValueError("请先在主文件加入宏包：" + ", ".join(missing) + "；未修改此子文件。")
        update = package_update(source, missing)
        edits.append(SourceEdit(update.insert_position, update.insert_position, update.inserted_text))
    return edits
