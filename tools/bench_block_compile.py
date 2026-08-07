"""Block compile pipeline benchmark (perf/block-compile-pipeline-audit).

Builds synthetic Small/Medium/Large Block projects, then for each operation
measures the pipeline segments directly (save / assemble / latex / pdf
reload) plus one end-to-end auto path.  Output: stdout table + CSV at
docs/data/block-compile-performance-summary.csv.  Uses the real CompileManager
(xelatex) so it needs a local TeX toolchain.
"""
from __future__ import annotations

import os
import statistics
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.core.blocks.layout import LayoutNode, block_slot
from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.blocks.model import content_for_heading, content_for_quote, content_for_text
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow
from app.core.settings import AppSettings
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.workspace_controller import BlockWorkspaceController
from app.gui.pdf_panel import PdfPanel


_FORMULA = FormulaBlockAdapter()
_ONE_PIXEL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0dIDATx\x9cc\xf8\xff\xff?\x00\x05"
    b"\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
)


def make_table(rows: int, cols: int) -> dict:
    return TableData(
        columns=[ColumnSpec(id=f"c{i}", name=f"列{i}", dataType="number") for i in range(cols)],
        rows=[
            TableRow(id=f"r{r}", cells={f"c{c}": Cell(kind="number", value=r * cols + c) for c in range(cols)})
            for r in range(rows)
        ],
        header_row_count=0,
    ).to_content_dict()


def make_project(size: str) -> BlockRegistry:
    registry = BlockRegistry()
    if size == "small":
        counts = {"text": 5, "heading": 2, "formula": 2, "image": 1, "table": 1}
        table_dims = (5, 3)
    elif size == "medium":
        counts = {"text": 25, "heading": 5, "formula": 8, "image": 5, "quote": 4, "list": 3, "table": 1}
        table_dims = (20, 10)
    else:
        counts = {"text": 50, "heading": 10, "formula": 15, "image": 10, "quote": 8, "list": 7, "table": 1}
        table_dims = (100, 50)
    ids: list[str] = []
    for block_type, number in counts.items():
        for index in range(number):
            if block_type == "text":
                content = content_for_text(f"段落 {index}：性能基准文本。")
            elif block_type == "heading":
                content = content_for_heading(f"章节 {index}", level=1 + index % 4)
            elif block_type == "formula":
                content = _FORMULA.content_for(f"x_{{{index}}} = \\sqrt{{a_{{{index}}}}} + \\frac{{1}}{{2}}")
            elif block_type == "image":
                content = {"source": "assets/images/bench.png", "width": "60mm"}
            elif block_type == "quote":
                content = content_for_quote(f"引用 {index}")
            elif block_type == "list":
                content = {"ordered": index % 2 == 0, "items": [f"项 {index}-1", f"项 {index}-2"]}
            else:
                continue
            block = registry.create(
                CreateBlockInput(type=block_type, alias=f"{block_type}_{index}", content=content)
            )
            ids.append(block.id)
    table = registry.create(
        CreateBlockInput(type="table", alias="table_0", content=make_table(*table_dims))
    )
    ids.append(table.id)
    return registry, ids


def build_layout(ids: list[str]) -> LayoutNode:
    half = len(ids) // 2
    left = LayoutNode(id="lyt_row_left", kind="row", children=tuple(block_slot(i) for i in ids[:half]))
    right = LayoutNode(id="lyt_grid_right", kind="grid", columns=2, children=tuple(block_slot(i) for i in ids[half:]))
    return LayoutNode(id="lyt_root", kind="grid", columns=2, children=(left, right))


def wait_for_compile(session: ProjectSession, timeout: float = 120.0) -> float:
    finished = []
    session.compile_finished.connect(finished.append)
    start = time.perf_counter()
    deadline = start + timeout
    while time.perf_counter() < deadline:
        QApplication.processEvents()
        if finished:
            return (time.perf_counter() - start) * 1000.0
        time.sleep(0.02)
    return -1.0


def run() -> None:
    app = QApplication([])
    pdf_panel = PdfPanel()
    rows_out: list[dict] = []
    tmp = TemporaryDirectory()
    base = Path(tmp.name)

    for size in ("small", "medium", "large"):
        registry, ids = make_project(size)
        project = base / f"proj_{size}"
        (project / "assets" / "images").mkdir(parents=True)
        (project / "assets" / "images" / "bench.png").write_bytes(_ONE_PIXEL_PNG)
        session = ProjectSession(registry=registry, layout=build_layout(ids), project_dir=project)
        controller = BlockWorkspaceController(session)

        targets = {
            "text": next(b for b in registry.blocks() if b.type == "text"),
            "formula": next(b for b in registry.blocks() if b.type == "formula"),
            "image": next(b for b in registry.blocks() if b.type == "image"),
            "table": next(b for b in registry.blocks() if b.type == "table"),
        }
        ops = (
            [("text", 10), ("formula", 3), ("table", 2)]
            if size == "large"
            else [("text", 10), ("formula", 5), ("table", 5)]
            if size == "medium"
            else [("text", 10)]
        )

        for op, reps in ops:
            block = targets[op]
            samples = []
            for rep in range(reps):
                if op == "text":
                    patch = {"content": content_for_text(f"修改后的段落文本内容（第 {rep} 次）。")}
                elif op == "formula":
                    patch = {"content": _FORMULA.content_for(f"E_{rep} = \\gamma m c^2")}
                elif op == "table":
                    session.table_model.set_cell("r0", "c0", Cell(kind="number", value=1000 + rep))
                    patch = None
                else:
                    patch = {"content": {**block.content, "width": f"{60 + rep}mm"}}
                t0 = time.perf_counter()
                if patch is not None:
                    controller.update_block(block.id, patch, text=f"bench {op}")
                t_command = (time.perf_counter() - t0) * 1000.0

                t0 = time.perf_counter()
                session.save_now()
                t_save = (time.perf_counter() - t0) * 1000.0

                t0 = time.perf_counter()
                session.assemble_latex()
                t_assemble = (time.perf_counter() - t0) * 1000.0
                stats = session._last_assemble_stats

                t0 = time.perf_counter()
                result = session.compile_final()
                t_latex = (time.perf_counter() - t0) * 1000.0

                t0 = time.perf_counter()
                if result is not None and result.pdf_file is not None and result.pdf_file.exists():
                    pdf_panel.load_pdf(result.pdf_file, logical_key=project / "main.tex")
                t_pdf = (time.perf_counter() - t0) * 1000.0
                samples.append(
                    {
                        "size": size,
                        "op": op,
                        "blocks": len(registry.blocks()),
                        "save_ms": t_save,
                        "assemble_ms": t_assemble,
                        "files_written": stats["written"],
                        "files_unchanged": stats["unchanged"],
                        "latex_ms": t_latex,
                        "pdf_ms": t_pdf,
                    }
                )
            med = lambda key: round(statistics.median(s[key] for s in samples), 1)
            print(
                f"{size:7s} {op:8s} blocks={len(registry.blocks()):4d} "
                f"save={med('save_ms'):7.1f}ms assemble={med('assemble_ms'):7.1f}ms "
                f"written={med('files_written'):4.0f} unchanged={med('files_unchanged'):4.0f} "
                f"latex={med('latex_ms'):8.1f}ms pdf={med('pdf_ms'):7.1f}ms"
            )
            rows_out.extend(samples)

        # end-to-end auto path on the text block (small/medium/large)
        block = targets["text"]
        controller.update_block(block.id, {"content": content_for_text("端到端自动路径文本。")}, text="bench auto")
        t_auto = wait_for_compile(session)
        print(f"{size:7s} auto    total_auto={t_auto:8.1f}ms launches={session._compile_launches}")

    out = Path(__file__).resolve().parents[1] / "docs" / "data"
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "block-compile-performance-summary.csv"
    if rows_out:
        import csv

        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows_out[0].keys()))
            writer.writeheader()
            writer.writerows(rows_out)
        print("CSV ->", csv_path)
    tmp.cleanup()


if __name__ == "__main__":
    run()
