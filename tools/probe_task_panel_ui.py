"""D3 isolated Qt widget comparison; no compilation, publication or native claim."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid
from app.core.compiler import BuildPurpose, CompileOutcome
from app.core.latex_outline import scan_outline
from app.core.blocks.layout import LayoutNode, block_slot
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.navigation_dock import BlockNavigationWidget
from app.gui.blocks.diagnostics_dock import BlockDiagnostics
from app.gui.blocks.layout_panel import BlockLayoutPanel
from app.gui.formula_dialog import FormulaDialog
from app.gui.project_panels import OutlinePanel, ReferencesPanel
from app.gui.theme import apply_theme
from app.gui.theme.ui_scale_manager import UiScaleManager
from tests.test_blocks_gui import registry_with_blocks
from tools.bench_pdf_pipeline import source_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication([])
    apply_theme(app)
    app.ui_scale_manager = UiScaleManager(app)
    app.setQuitOnLastWindowClosed(False)
    registry = registry_with_blocks()
    layout = LayoutNode(id="lyt_test", kind="row", children=tuple(block_slot(b.id) for b in registry.blocks()))
    session = ProjectSession(registry=registry, layout=layout)
    original = (layout.to_dict(), [b.to_dict() for b in registry.blocks()])
    outline = OutlinePanel()
    outline.set_outline(scan_outline("\\section{研究背景与问题}\n\\subsection{实验设计与控制变量}\n\\subsubsection{数据处理与不确定度}"))
    references = ReferencesPanel()
    if hasattr(references, "library_path"):
        references.set_references([], library_path=Path("/synthetic-project/bib/references.bib"))
    else:
        references.set_references([])
    formula = FormulaDialog(None, "$x+1$", 0, 5)
    nav = BlockNavigationWidget(session)
    nav.tabs.setCurrentIndex(1)
    slots = BlockLayoutPanel(registry, layout)
    diagnostics = BlockDiagnostics(session)
    diagnostics._on_finished(SimpleNamespace(purpose=BuildPurpose.FINAL, outcome=CompileOutcome.SUCCESS,
                                             duration_seconds=1.25, ok=True))
    widgets = [("outline", outline), ("references", references), ("formula", formula),
               ("block-navigation", nav), ("block-slots", slots), ("block-result", diagnostics)]
    evidence = {"app_sha256": source_digest(), "states": [], "completed": False,
                "limits": "Offscreen widget captures; synthetic labels/result, not actual compilation or native QA"}
    try:
        for scale in (1.0, 1.5):
            app.ui_scale_manager.apply_scale(scale)
            for name, widget in widgets:
                widget.resize(920, 700) if name == "formula" else widget.resize(440, 620)
                widget.show()
                for _ in range(6):
                    app.processEvents()
                if name == "formula" and hasattr(formula.keyboard, "numbers_button"):
                    formula.keyboard.numbers_button.setChecked(False)
                    for _ in range(6):
                        app.processEvents()
                    widget.resize(920, 700)
                    app.processEvents()
                filename = f"{scale}-{name}.png"
                assert widget.grab().save(str(output / filename))
                actions = {"outline": (outline.refresh_button,), "references": (references.check_button, references.insert_button),
                    "formula": (formula._ok_button,), "block-navigation": (nav.add_row_button, nav.add_grid_button),
                    "block-slots": (slots.row_button, slots.grid_button), "block-result": (diagnostics.locate_button,)}[name]
                visible = [button.visibleRegion().contains(button.rect()) for button in actions]
                evidence["states"].append({"name": name, "scale": scale, "image": filename,
                    "size": [widget.width(), widget.height()], "actions_visible": visible})
                assert all(visible), (name, scale, visible)
                if name == "formula":
                    assert widget.height() <= 800
                widget.hide()
        assert (session.layout.to_dict(), [b.to_dict() for b in registry.blocks()]) == original
        assert session.undo_stack.count() == 0 and session.compile_manager is None
        assert formula.visual_edit.latex() == "x+1" and formula._accepted_plan is None
        evidence["model_and_formula_unchanged"] = True
        evidence["completed"] = True
    finally:
        for _, widget in widgets:
            widget.close()
            widget.deleteLater()
        session.shutdown()
        session.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        evidence["widgets_destroyed"] = all(not isValid(w) for _, w in widgets)
        evidence["app_sha256_after"] = source_digest()
        evidence["completed"] &= evidence["widgets_destroyed"] and evidence["app_sha256_after"] == evidence["app_sha256"]
        (output / "result.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    assert evidence["completed"], evidence
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
