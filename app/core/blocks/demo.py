"""Comprehensive demo project builder (Sprint 6).

Builds the mandatory 2x2 demo: apparatus image, linked Excel table with a
local patch, theory formula, analysis text with cross-references, a 45:55
grid, a document theme, compiled PDF, and a portable export package. The
builder only uses the block core; no GUI involved.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import shutil
import struct
import zlib

from pathlib import Path

from app.core.blocks.block_renderer import render_block, required_packages_for_block
from app.core.blocks.export_package import export_package
from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.blocks.layout import LayoutNode, Size, block_slot
from app.core.blocks.layout_renderer import render_layout
from app.core.blocks.layout_solver import solve_layout
from app.core.blocks.model import (
    Block,
    Caption,
    Provenance,
    Semantic,
    content_for_text,
)
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.source_registry import SourceRecord, hash_file
from app.core.blocks.table_import import SpreadsheetImportAdapter
from app.core.blocks.table_model import Cell, TableData, TableRow
from app.core.blocks.theme import DocumentTheme
from app.core.blocks.theme_renderer import render_document_theme_sty
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain


@dataclass(frozen=True)
class DemoResult:
    project_dir: Path
    main_tex: Path
    pdf: Path
    registry: BlockRegistry


def build_demo(project_dir: Path) -> DemoResult:
    project = Path(project_dir).expanduser().resolve()
    figures = project / "assets" / "images"
    figures.mkdir(parents=True, exist_ok=True)
    data_dir = project / "data" / "snapshots"
    data_dir.mkdir(parents=True, exist_ok=True)
    (figures / "apparatus.png").write_bytes(_tiny_png())

    workbook = _write_workbook(data_dir / "results.xlsx")
    imported = SpreadsheetImportAdapter(data_dir / "results.xlsx").read_sheet(
        "Experiment 1",
        header_row=True,
    )
    # Local patch: mark one note cell.
    imported.rows[-1].cells["col_note"] = Cell(kind="text", value="已排除异常值")
    table_content = imported.to_content_dict()

    adapter = FormulaBlockAdapter()
    registry = BlockRegistry()
    image_block = registry.create(
        CreateBlockInput(
            type="image",
            alias="apparatus",
            semantic=Semantic(role="figure", label="fig:apparatus", caption=Caption("实验装置")),
            content={"source": "assets/images/apparatus.png", "width": None},
            provenance=Provenance(kind="created"),
        )
    )
    table_block = registry.create(
        CreateBlockInput(
            type="table",
            alias="results",
            semantic=Semantic(role="table", label="tab:results", caption=Caption("不同温度下的反应速率")),
            content=table_content,
            provenance=Provenance(kind="linked", sourceId="src_results_excel"),
        )
    )
    formula_block = registry.create(
        CreateBlockInput(
            type="formula",
            alias="rate-model",
            semantic=Semantic(role="equation", label="eq:rate-model"),
            content=adapter.content_for(r"r = k[A] e^{-E_a/RT}"),
            provenance=Provenance(kind="created"),
        )
    )
    text_block = registry.create(
        CreateBlockInput(
            type="rawLatex",
            alias="analysis",
            semantic=Semantic(role="text"),
            content={
                "latex": (
                    "结果分析：实验装置见图 \\ref{fig:apparatus}，数据见表 \\ref{tab:results}，"
                    "理论模型见公式 \\ref{eq:rate-model}。"
                ),
                "trusted": True,
            },
            provenance=Provenance(kind="created"),
        )
    )

    layout = LayoutNode(
        id="lyt_demo_grid",
        kind="grid",
        columns=1,
        gap=Size(value=8, unit="mm"),
        fallback={"strategy": "stackVertically"},
        children=(
            LayoutNode(
                id="lyt_row_top",
                kind="row",
                gap=Size(value=8, unit="mm"),
                fallback={"strategy": "stackVertically"},
                children=(block_slot(image_block.id, weight=45, min_width_pt=120), block_slot(table_block.id, weight=55, min_width_pt=140)),
            ),
            LayoutNode(
                id="lyt_row_bottom",
                kind="row",
                gap=Size(value=8, unit="mm"),
                fallback={"strategy": "stackVertically"},
                children=(block_slot(formula_block.id, weight=45, min_width_pt=120), block_slot(text_block.id, weight=55, min_width_pt=140)),
            ),
        ),
    )

    blocks_dir = project / "blocks"
    blocks_dir.mkdir(exist_ok=True)
    block_latex: dict[str, str] = {}
    for block in registry.blocks():
        (blocks_dir / f"{block.id}.tex").write_text(
            render_block(block, in_box=True),
            encoding="utf-8",
        )
        block_latex[block.id] = f"\\input{{blocks/{block.id}.tex}}\n"

    theme = DocumentTheme(
        id="doc_academic_clean",
        name="Academic Clean",
        page={"size": "a4", "orientation": "portrait", "columns": 1, "margin": {"topMm": 25, "rightMm": 25, "bottomMm": 25, "leftMm": 30}},
        typography={"textFamily": "", "mathFamily": "", "monoFamily": "", "baseSizePt": 11, "lineSpacing": 1.15},
        headings={"section": {"weight": 600, "spaceBeforePt": 16, "spaceAfterPt": 7}},
        figures={"captionPosition": "bottom", "captionSize": "small", "alignment": "center"},
        tables={"preset": "booktabs", "verticalRules": False, "headerWeight": 600, "cellPaddingPt": 4},
        layout={"blockGapPt": 10, "gridGapPt": 12},
    )
    styles = project / "styles"
    styles.mkdir(exist_ok=True)
    (styles / "icstex-generated.sty").write_text(render_document_theme_sty(theme), encoding="utf-8")

    solved = solve_layout(layout, 426.0)
    body = render_layout(solved, block_latex)
    packages = sorted(
        {package for block in registry.blocks() for package in required_packages_for_block(block, in_box=True)}
    )
    main = project / "main.tex"
    main.write_text(
        "\\documentclass{ctexart}\n"
        "\\title{温度对反应速率的影响}\n"
        + "".join(f"\\usepackage{{{package}}}\n" for package in packages)
        + "\\input{styles/icstex-generated.sty}\n"
        + "\\graphicspath{{assets/images/}}\n"
        + "\\begin{document}\n"
        + "\\maketitle\n"
        + body
        + "\\end{document}\n",
        encoding="utf-8",
    )

    (project / "icstex.project.json").write_text(
        json.dumps(
            {
                "projectSchemaVersion": "1.0.0",
                "minimumAppVersion": "0.9.0",
                "blockSchemaVersion": "1.0.0",
                "layoutSchemaVersion": "1.0.0",
                "themeSchemaVersion": "1.0.0",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    metadata = project / ".icstex"
    metadata.mkdir(exist_ok=True)
    (metadata / "blocks.json").write_text(
        json.dumps({"format": "icstex-blocks", "schemaVersion": "1.0.0", "blocks": [b.to_dict() for b in registry.blocks()]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (metadata / "layouts.json").write_text(
        json.dumps({"schemaVersion": "1.0.0", "layouts": [layout.to_dict()]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    source_record = SourceRecord(
        sourceId="src_results_excel",
        kind="xlsx",
        relativePath="data/snapshots/results.xlsx",
        baseSha256=hash_file(data_dir / "results.xlsx"),
    )
    (metadata / "sources.json").write_text(
        json.dumps(
            {"sources": [{"sourceId": s.sourceId, "kind": s.kind, "relativePath": s.relativePath, "baseSha256": s.baseSha256} for s in (source_record,)]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    output = project / "output"
    output.mkdir(exist_ok=True)
    toolchain = detect_toolchain()
    result = CompileManager(main, toolchain=toolchain, engine=LaTeXEngine.XELATEX).compile_now(
        BuildPurpose.FINAL, timeout_seconds=300
    )
    if result is None or not result.ok or result.pdf_file is None:
        raise RuntimeError("Demo 编译失败：" + (result.combined_output if result else "无结果"))
    pdf = output / "demo.pdf"
    shutil.copy2(result.pdf_file, pdf)
    return DemoResult(project_dir=project, main_tex=main, pdf=pdf, registry=registry)


def _write_workbook(path: Path) -> None:
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Experiment 1"
    sheet.append(["温度", "反应速率", "备注"])
    sheet.append([20, 1.25, "基准组"])
    sheet.append([30, 1.87, "重复测量三次"])
    sheet.append([40, 2.64, "第三次实验"])
    workbook.save(str(path))


def _tiny_png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xcc\xcc\xcc" * 4 for _ in range(4))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
