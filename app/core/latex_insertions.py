from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
import io
import os
from pathlib import Path
import re
import unicodedata

from app.core.text_encoding import write_latex_text_atomic


FIGURE_PACKAGES = ("graphicx",)
SIDE_BY_SIDE_FIGURE_PACKAGES = ("graphicx", "caption", "subcaption")
TABLE_PACKAGES = ("array", "booktabs")
HYPERLINK_PACKAGES = ("hyperref",)

PACKAGE_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^{}]+)\}")
DOCUMENTCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{[^{}]+\}")
BEGIN_DOCUMENT = "\\begin{document}"
CUSTOM_TEMPLATE_PREFIX = "custom:"
CUSTOM_TEMPLATE_HEADER = "% ICSTeX template:"


@dataclass(frozen=True)
class FigureSpec:
    image_path: str
    width: float = 0.8
    caption: str = ""
    label: str = ""
    placement: str = "htbp"


@dataclass(frozen=True)
class SideBySideFigureSpec:
    left_image_path: str
    right_image_path: str
    left_caption: str = ""
    right_caption: str = ""
    caption: str = ""
    label: str = ""
    width: float = 0.48
    placement: str = "htbp"


class FigureLayout(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    GRID_2X2 = "grid_2x2"

    @property
    def display_name(self) -> str:
        return {
            FigureLayout.HORIZONTAL: "左右拼接",
            FigureLayout.VERTICAL: "上下拼接",
            FigureLayout.GRID_2X2: "田字拼接（2×2）",
        }[self]


@dataclass(frozen=True)
class FigureLayoutItem:
    image_path: str
    width: float = 0.48
    caption: str = ""


@dataclass(frozen=True)
class FigureLayoutSpec:
    layout: FigureLayout = FigureLayout.HORIZONTAL
    items: tuple[FigureLayoutItem, ...] = ()
    caption: str = ""
    label: str = ""
    placement: str = "htbp"


@dataclass(frozen=True)
class TableSpec:
    rows: int = 3
    columns: int = 3
    alignment: str = "c"
    use_booktabs: bool = True
    caption: str = ""
    label: str = ""
    placement: str = "htbp"
    headers: tuple[str, ...] = ()
    cells: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class HyperlinkSpec:
    text: str
    url: str


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    title: str
    filename: str
    text: str


@dataclass(frozen=True)
class PackageUpdate:
    text: str
    insert_position: int
    inserted_text: str


def figure_snippet(spec: FigureSpec) -> str:
    lines = [
        f"\\begin{{figure}}[{spec.placement}]",
        "  \\centering",
        f"  \\includegraphics[width={_ratio(spec.width)}\\textwidth]{{{spec.image_path}}}",
    ]
    if spec.caption:
        lines.append(f"  \\caption{{{spec.caption}}}")
    if spec.label:
        lines.append(f"  \\label{{{spec.label}}}")
    lines.append("\\end{figure}")
    return "\n".join(lines)


def side_by_side_figure_snippet(spec: SideBySideFigureSpec) -> str:
    return figure_layout_snippet(
        FigureLayoutSpec(
            layout=FigureLayout.HORIZONTAL,
            items=(
                FigureLayoutItem(spec.left_image_path, spec.width, spec.left_caption),
                FigureLayoutItem(spec.right_image_path, spec.width, spec.right_caption),
            ),
            caption=spec.caption,
            label=spec.label,
            placement=spec.placement,
        )
    )


def figure_layout_snippet(spec: FigureLayoutSpec) -> str:
    layout = FigureLayout(spec.layout)
    expected = 4 if layout is FigureLayout.GRID_2X2 else 2
    if len(spec.items) != expected:
        raise ValueError(f"{layout.display_name}需要选择 {expected} 张图片。")
    for item in spec.items:
        if not item.image_path.strip():
            raise ValueError("图片路径不能为空。")
        if not 0.05 <= float(item.width) <= 1.0:
            raise ValueError("单张图片宽度必须在 0.05 到 1.0 之间。")

    rows = _figure_layout_rows(layout, spec.items)
    for row in rows:
        if len(row) > 1 and sum(float(item.width) for item in row) > 1.000001:
            raise ValueError("同一行图片宽度合计不能超过 1.0\\textwidth。")

    lines = [
        f"\\begin{{figure}}[{spec.placement}]",
        "  \\centering",
    ]
    for row_index, row in enumerate(rows):
        for item_index, item in enumerate(row):
            lines.extend(_subfigure_lines(item, suppress_trailing_space=item_index < len(row) - 1))
            if item_index < len(row) - 1:
                lines.append("  \\hfill")
        if row_index < len(rows) - 1:
            lines.append("  \\par\\medskip")
    if spec.caption:
        lines.append(f"  \\caption{{{spec.caption}}}")
    if spec.label:
        lines.append(f"  \\label{{{spec.label}}}")
    lines.append("\\end{figure}")
    return "\n".join(lines)


def _figure_layout_rows(
    layout: FigureLayout,
    items: tuple[FigureLayoutItem, ...],
) -> tuple[tuple[FigureLayoutItem, ...], ...]:
    if layout is FigureLayout.HORIZONTAL:
        return (items,)
    if layout is FigureLayout.VERTICAL:
        return tuple((item,) for item in items)
    return (items[:2], items[2:])


def _subfigure_lines(item: FigureLayoutItem, *, suppress_trailing_space: bool) -> list[str]:
    lines = [
        f"  \\begin{{subfigure}}{{{_ratio(item.width)}\\textwidth}}",
        "    \\centering",
        f"    \\includegraphics[width=\\linewidth]{{{item.image_path}}}",
    ]
    if item.caption:
        lines.append(f"    \\caption{{{item.caption}}}")
    ending = "  \\end{subfigure}%" if suppress_trailing_space else "  \\end{subfigure}"
    lines.append(ending)
    return lines


def table_snippet(spec: TableSpec) -> str:
    rows = max(1, int(spec.rows))
    columns = max(1, int(spec.columns))
    alignment = spec.alignment if spec.alignment in {"l", "c", "r"} else "c"
    column_spec = alignment * columns if spec.use_booktabs else "|" + "|".join(alignment for _ in range(columns)) + "|"
    header_values = _table_row_values(spec.headers, columns, lambda index: f"Header {index}")
    body_values = [
        _table_row_values(spec.cells[row - 1] if row - 1 < len(spec.cells) else (), columns, lambda column, row=row: f"Cell {row}-{column}")
        for row in range(1, rows + 1)
    ]
    header = " & ".join(header_values) + r" \\"
    body = [" & ".join(row_values) + r" \\" for row_values in body_values]

    lines = [
        f"\\begin{{table}}[{spec.placement}]",
        "  \\centering",
        f"  \\begin{{tabular}}{{{column_spec}}}",
    ]
    if spec.use_booktabs:
        lines.extend(["    \\toprule", f"    {header}", "    \\midrule"])
        lines.extend(f"    {line}" for line in body)
        lines.append("    \\bottomrule")
    else:
        lines.extend(["    \\hline", f"    {header}", "    \\hline"])
        lines.extend(f"    {line}" for line in body)
        lines.append("    \\hline")
    lines.append("  \\end{tabular}")
    if spec.caption:
        lines.append(f"  \\caption{{{spec.caption}}}")
    if spec.label:
        lines.append(f"  \\label{{{spec.label}}}")
    lines.append("\\end{table}")
    return "\n".join(lines)


def parse_tabular(text: str) -> TableSpec | None:
    """Reverse-parse a LaTeX table/tabular block into a TableSpec for the editor.

    Best-effort: handles what table_snippet() produces (booktabs or \\hline) plus
    simple hand-written tabulars. The first body row becomes the header row.

    ponytail: ignores \\multicolumn, nested tabulars, and & inside braces; splits
    rows on \\\\ and cells on &. Upgrade to a brace-aware tokenizer only if real
    student tables start tripping on it.
    """
    tabular = re.search(
        r"\\begin\{tabular\}\s*(?:\[[^\]]*\])?\s*(\{)", text
    )
    if tabular is None:
        return None
    column_spec, body_start = _braced_arg(text, tabular.start(1))
    end = text.find(r"\end{tabular}", body_start)
    if end == -1:
        return None
    body = text[body_start:end]

    columns = _count_columns(column_spec)
    alignment = next((char for char in column_spec if char in {"l", "c", "r"}), "c")
    use_booktabs = "\\toprule" in body

    rows = _tabular_rows(body)
    if not rows:
        return None
    columns = max(columns, max(len(row) for row in rows))
    headers = tuple(rows[0])
    cells = tuple(tuple(row) for row in rows[1:])

    return TableSpec(
        rows=max(1, len(cells)) if cells else 1,
        columns=max(1, columns),
        alignment=alignment,
        use_booktabs=use_booktabs,
        caption=_braced_value(text, "caption"),
        label=_braced_value(text, "label"),
        placement=_table_placement(text),
        headers=headers,
        cells=cells,
    )


def parse_delimited(text: str) -> TableSpec | None:
    """Parse pasted CSV / Excel (tab-separated) data into a TableSpec.

    Excel, Google Sheets, and Numbers all copy as tab-separated; plain .csv uses
    commas. We pick tab if any line contains one, else comma. First row becomes
    the header. Cell text is kept verbatim (no LaTeX escaping), consistent with
    table_snippet()/parse_tabular(); the user edits in the grid afterwards.

    ponytail: delimiter sniff is just tab-vs-comma. Add full csv.Sniffer only if
    semicolon/pipe exports show up in real student data.
    """
    stripped = text.strip("\n")
    if not stripped.strip():
        return None
    delimiter = "\t" if "\t" in stripped else ","
    reader = csv.reader(io.StringIO(stripped), delimiter=delimiter)
    rows = [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return None
    columns = max(len(row) for row in rows)
    headers = tuple(rows[0])
    cells = tuple(tuple(row) for row in rows[1:])
    return TableSpec(
        rows=max(1, len(cells)) if cells else 1,
        columns=max(1, columns),
        headers=headers,
        cells=cells,
    )


RULE_COMMANDS = ("\\toprule", "\\midrule", "\\bottomrule", "\\hline")


def _tabular_rows(body: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_row in body.split(r"\\"):
        row = raw_row
        for command in RULE_COMMANDS:
            row = row.replace(command, " ")
        # Drop trailing optional row-spacing like [2pt] left over after a split.
        row = re.sub(r"^\s*\[[^\]]*\]", "", row).strip()
        if not row:
            continue
        rows.append([cell.strip() for cell in row.split("&")])
    return rows


def _count_columns(column_spec: str) -> int:
    spec = column_spec.replace("|", "")
    count = 0
    index = 0
    while index < len(spec):
        char = spec[index]
        if char in {"p", "m", "b"} and index + 1 < len(spec) and spec[index + 1] == "{":
            _, index = _braced_arg(spec, index + 1)
            count += 1
            continue
        if char.isalpha():
            count += 1
        index += 1
    return count


def _braced_arg(text: str, open_index: int) -> tuple[str, int]:
    """Return (inner_text, index_after_closing_brace) for a balanced { } group."""
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[open_index + 1 : index], index + 1
    return text[open_index + 1 :], len(text)


def _braced_value(text: str, command: str) -> str:
    match = re.search(r"\\" + command + r"\s*\{", text)
    if match is None:
        return ""
    return _braced_arg(text, match.end() - 1)[0].strip()


def _table_placement(text: str) -> str:
    match = re.search(r"\\begin\{table\}\s*\[([^\]]*)\]", text)
    return match.group(1).strip() if match else "htbp"


def _table_row_values(values: tuple[str, ...], columns: int, fallback) -> list[str]:  # type: ignore[no-untyped-def]
    row: list[str] = []
    for index in range(1, columns + 1):
        value = values[index - 1].strip() if index - 1 < len(values) else ""
        row.append(value or fallback(index))
    return row


def hyperlink_snippet(spec: HyperlinkSpec) -> str:
    return f"\\href{{{spec.url}}}{{{spec.text}}}"


def existing_packages(text: str) -> set[str]:
    preamble = text.split(BEGIN_DOCUMENT, 1)[0]
    packages: set[str] = set()
    for match in PACKAGE_RE.finditer(preamble):
        packages.update(part.strip() for part in match.group(1).split(",") if part.strip())
    return packages


def package_update(text: str, packages: tuple[str, ...] | list[str]) -> PackageUpdate:
    existing = existing_packages(text)
    missing = [package for package in packages if package not in existing]
    if not missing:
        return PackageUpdate(text=text, insert_position=0, inserted_text="")

    insert_position = package_insert_position(text)
    inserted_text = "".join(f"\\usepackage{{{package}}}\n" for package in missing)
    return PackageUpdate(
        text=text[:insert_position] + inserted_text + text[insert_position:],
        insert_position=insert_position,
        inserted_text=inserted_text,
    )


def ensure_packages(text: str, packages: tuple[str, ...] | list[str]) -> str:
    return package_update(text, packages).text


def package_insert_position(text: str) -> int:
    begin_index = text.find(BEGIN_DOCUMENT)
    preamble_end = begin_index if begin_index >= 0 else len(text)
    preamble = text[:preamble_end]

    matches = list(PACKAGE_RE.finditer(preamble))
    if matches:
        return _end_of_line(text, matches[-1].end())

    match = DOCUMENTCLASS_RE.search(preamble)
    if match:
        return _end_of_line(text, match.end())

    return 0


def sanitize_asset_filename(filename: str) -> str:
    path = Path(filename)
    normalized_stem = unicodedata.normalize("NFKD", path.stem).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized_stem).strip("._-")
    suffix = re.sub(r"[^A-Za-z0-9.]+", "", path.suffix).lower()
    if not stem:
        stem = "image"
    return f"{stem}{suffix}"


def unique_asset_path(directory: Path, filename: str) -> Path:
    safe_name = sanitize_asset_filename(filename)
    candidate = directory / safe_name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 1
    while True:
        candidate = directory / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def latex_relative_path(tex_file: Path, asset_file: Path) -> str:
    relative = os.path.relpath(asset_file, tex_file.parent)
    return Path(relative).as_posix()


def custom_template_dir() -> Path:
    return Path.home() / ".icstex" / "templates"


def template_for_key(key: str, custom_dir: Path | None = None) -> TemplateSpec:
    if key.startswith(CUSTOM_TEMPLATE_PREFIX):
        template = _custom_template_for_key(key, custom_dir or custom_template_dir())
        if template is not None:
            return template
    try:
        return TEMPLATES[key]
    except KeyError as exc:
        raise ValueError(f"未知模板：{key}") from exc


def all_templates(custom_dir: Path | None = None) -> tuple[TemplateSpec, ...]:
    return (*TEMPLATES.values(), *custom_templates(custom_dir or custom_template_dir()))


def custom_templates(directory: Path | None = None) -> tuple[TemplateSpec, ...]:
    directory = directory or custom_template_dir()
    try:
        files = sorted(directory.glob("*.tex"))
    except OSError:
        return ()
    templates: list[TemplateSpec] = []
    for file in files:
        try:
            text = file.read_text(encoding="utf-8")
        except OSError:
            continue
        title = _template_title_from_text(text) or _title_from_filename(file)
        templates.append(
            TemplateSpec(
                key=f"{CUSTOM_TEMPLATE_PREFIX}{file.stem}",
                title=f"{title}（个人）",
                filename=file.name,
                text=text,
            )
        )
    return tuple(templates)


def save_custom_template(title: str, text: str, directory: Path | None = None) -> TemplateSpec:
    clean_title = title.strip() or "Untitled Template"
    directory = directory or custom_template_dir()
    directory.mkdir(parents=True, exist_ok=True)
    filename = _unique_template_filename(directory, clean_title)
    stored_text = text if text.startswith(CUSTOM_TEMPLATE_HEADER) else f"{CUSTOM_TEMPLATE_HEADER} {clean_title}\n{text}"
    path = directory / filename
    write_latex_text_atomic(path, stored_text, encoding="utf-8")
    return TemplateSpec(
        key=f"{CUSTOM_TEMPLATE_PREFIX}{path.stem}",
        title=f"{clean_title}（个人）",
        filename=path.name,
        text=stored_text,
    )


def import_custom_template(source: Path, title: str | None = None, directory: Path | None = None) -> TemplateSpec:
    if source.suffix.lower() != ".tex":
        raise ValueError("只能导入 .tex 模板文件。")
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise ValueError("模板文件需要使用 UTF-8 编码。") from exc
    return save_custom_template(title or _template_title_from_text(text) or source.stem, text, directory)


def export_template(key: str, target: Path, directory: Path | None = None) -> Path:
    template = template_for_key(key, directory)
    if target.suffix.lower() != ".tex":
        target = target.with_suffix(".tex")
    target.parent.mkdir(parents=True, exist_ok=True)
    write_latex_text_atomic(target, template.text, encoding="utf-8")
    return target


def _ratio(value: float) -> str:
    bounded = min(max(float(value), 0.05), 1.0)
    return f"{bounded:.2f}".rstrip("0").rstrip(".")


def _end_of_line(text: str, position: int) -> int:
    newline = text.find("\n", position)
    return len(text) if newline == -1 else newline + 1


def _custom_template_for_key(key: str, directory: Path) -> TemplateSpec | None:
    stem = key.removeprefix(CUSTOM_TEMPLATE_PREFIX)
    if not stem or "/" in stem or "\\" in stem:
        return None
    path = directory / f"{stem}.tex"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    title = _template_title_from_text(text) or _title_from_filename(path)
    return TemplateSpec(key=key, title=f"{title}（个人）", filename=path.name, text=text)


def _template_title_from_text(text: str) -> str:
    first_line = text.splitlines()[0].strip() if text.splitlines() else ""
    if first_line.startswith(CUSTOM_TEMPLATE_HEADER):
        return first_line.removeprefix(CUSTOM_TEMPLATE_HEADER).strip() or "Untitled Template"
    match = re.search(r"\\title\{([^{}]+)\}", text)
    return match.group(1).strip() if match else ""


def _title_from_filename(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip().title() or "Untitled Template"


def _unique_template_filename(directory: Path, title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized).strip("._-") or "template"
    candidate = directory / f"{stem}.tex"
    index = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{index}.tex"
        index += 1
    return candidate.name


_COMMON_PACKAGES = """\\usepackage[margin=1in]{geometry}
\\usepackage{graphicx}
\\usepackage{caption}
\\usepackage{subcaption}
\\usepackage{booktabs}
\\usepackage{amsmath}
\\usepackage{siunitx}
\\usepackage{hyperref}
"""


TEMPLATES: dict[str, TemplateSpec] = {
    "blank_article": TemplateSpec(
        key="blank_article",
        title="空白文章",
        filename="Blank_Article.tex",
        text=(
            "\\documentclass{article}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage{graphicx}\n"
            "\\usepackage{hyperref}\n\n"
            "\\title{Untitled}\n"
            "\\author{}\n"
            "\\date{\\today}\n\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            "\\section{Introduction}\n\n"
            "\\end{document}\n"
        ),
    ),
    "ib_ia_report": TemplateSpec(
        key="ib_ia_report",
        title="IB/IA 报告",
        filename="IB_IA_Report.tex",
        text=(
            "\\documentclass[12pt]{article}\n"
            f"{_COMMON_PACKAGES}\n"
            "\\title{Internal Assessment}\n"
            "\\author{}\n"
            "\\date{\\today}\n\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            "\\section{Research Question}\n\n"
            "\\section{Background}\n\n"
            "\\section{Method}\n\n"
            "\\section{Data Processing}\n\n"
            "\\section{Conclusion}\n\n"
            "\\section{Evaluation}\n\n"
            "\\end{document}\n"
        ),
    ),
    "lab_report": TemplateSpec(
        key="lab_report",
        title="实验报告",
        filename="Lab_Report.tex",
        text=(
            "\\documentclass[12pt]{article}\n"
            f"{_COMMON_PACKAGES}\n"
            "\\title{Lab Report}\n"
            "\\author{}\n"
            "\\date{\\today}\n\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            "\\section{Aim}\n\n"
            "\\section{Apparatus}\n\n"
            "\\section{Procedure}\n\n"
            "\\section{Results}\n\n"
            "\\section{Analysis}\n\n"
            "\\section{Conclusion}\n\n"
            "\\end{document}\n"
        ),
    ),
    "coursework_essay": TemplateSpec(
        key="coursework_essay",
        title="课程论文",
        filename="Coursework_Essay.tex",
        text=(
            "\\documentclass[12pt]{article}\n"
            "\\usepackage[margin=1in]{geometry}\n"
            "\\usepackage{amsmath}\n"
            "\\usepackage{graphicx}\n"
            "\\usepackage{hyperref}\n\n"
            "\\title{Coursework Essay}\n"
            "\\author{}\n"
            "\\date{\\today}\n\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            "\\section{Introduction}\n\n"
            "\\section{Argument}\n\n"
            "\\section{Conclusion}\n\n"
            "\\end{document}\n"
        ),
    ),
    "extended_essay": TemplateSpec(
        key="extended_essay",
        title="Extended Essay",
        filename="Extended_Essay.tex",
        text=(
            "\\documentclass[12pt]{article}\n"
            f"{_COMMON_PACKAGES}\n"
            "\\title{Extended Essay}\n"
            "\\author{}\n"
            "\\date{\\today}\n\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            "\\begin{abstract}\n"
            "Write a short overview of the research question, method, and conclusion.\n"
            "\\end{abstract}\n\n"
            "\\tableofcontents\n"
            "\\newpage\n\n"
            "\\section{Introduction}\n\n"
            "\\section{Investigation}\n\n"
            "\\section{Analysis}\n\n"
            "\\section{Conclusion}\n\n"
            "\\section{References}\n\n"
            "\\end{document}\n"
        ),
    ),
    "physics_ia": TemplateSpec(
        key="physics_ia",
        title="Physics IA",
        filename="Physics_IA.tex",
        text=(
            "\\documentclass[12pt]{article}\n"
            f"{_COMMON_PACKAGES}"
            "\\usepackage{float}\n"
            "\\title{Physics Internal Assessment}\n"
            "\\author{}\n"
            "\\date{\\today}\n\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            "\\section{Research Question}\n\n"
            "\\section{Background Theory}\n\n"
            "\\section{Variables}\n\n"
            "\\section{Method}\n\n"
            "\\section{Raw Data}\n\n"
            "\\section{Processed Data}\n\n"
            "\\section{Uncertainty Analysis}\n\n"
            "\\section{Conclusion and Evaluation}\n\n"
            "\\end{document}\n"
        ),
    ),
    "math_ia": TemplateSpec(
        key="math_ia",
        title="Math IA",
        filename="Math_IA.tex",
        text=(
            "\\documentclass[12pt]{article}\n"
            f"{_COMMON_PACKAGES}"
            "\\usepackage{amssymb}\n"
            "\\title{Mathematics Internal Assessment}\n"
            "\\author{}\n"
            "\\date{\\today}\n\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            "\\section{Introduction}\n\n"
            "\\section{Rationale and Aim}\n\n"
            "\\section{Mathematical Exploration}\n\n"
            "\\section{Interpretation}\n\n"
            "\\section{Reflection and Conclusion}\n\n"
            "\\end{document}\n"
        ),
    ),
    "chemistry_lab": TemplateSpec(
        key="chemistry_lab",
        title="化学实验报告",
        filename="Chemistry_Lab_Report.tex",
        text=(
            "\\documentclass[12pt]{article}\n"
            f"{_COMMON_PACKAGES}"
            "\\usepackage[version=4]{mhchem}\n"
            "\\title{Chemistry Lab Report}\n"
            "\\author{}\n"
            "\\date{\\today}\n\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            "\\section{Aim}\n\n"
            "\\section{Hypothesis}\n\n"
            "\\section{Materials}\n\n"
            "\\section{Procedure}\n\n"
            "\\section{Data and Observations}\n\n"
            "\\section{Calculations}\n\n"
            "\\section{Evaluation}\n\n"
            "\\end{document}\n"
        ),
    ),
    "chinese_xelatex_article": TemplateSpec(
        key="chinese_xelatex_article",
        title="中文 XeLaTeX 文章",
        filename="Chinese_XeLaTeX_Article.tex",
        text=(
            "% !TEX program = xelatex\n"
            "\\documentclass[12pt]{ctexart}\n"
            "\\usepackage[margin=1in]{geometry}\n"
            "\\usepackage{graphicx}\n"
            "\\usepackage{booktabs}\n"
            "\\usepackage{amsmath}\n"
            "\\usepackage{hyperref}\n\n"
            "\\title{中文论文标题}\n"
            "\\author{}\n"
            "\\date{\\today}\n\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            "\\section{引言}\n\n"
            "\\section{正文}\n\n"
            "\\section{结论}\n\n"
            "\\end{document}\n"
        ),
    ),
}
