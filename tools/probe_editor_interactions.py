"""Render isolated synthetic editor drafts; never open or modify a document.

Run with QT_QPA_PLATFORM=cocoa for native macOS verification or offscreen for CI.
The optional hold keeps only these QA windows available for accessibility checks.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableEditorModel, TableRow
from app.gui.blocks.table_editor import TableEditor
from app.gui.formula_dialog import FormulaDialog
from app.gui.insert_panel import TableDialog
from app.gui.math_keyboard import CATEGORY_LABELS
from app.gui.theme import apply_theme


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hold-seconds", type=int, default=0)
    parser.add_argument("--keyboard-pages", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setApplicationName("ICSTeX Editor QA")
    apply_theme(app)
    formula = FormulaDialog(None, "", 0, 0, seed_text=r"\(v=\)")
    formula.visual_edit.insert_structure("fraction")
    QTest.keyClicks(formula.visual_edit, "d")
    QTest.keyClick(formula.visual_edit, Qt.Key.Key_Tab)
    QTest.keyClicks(formula.visual_edit, "t")
    QTest.keyClick(formula.visual_edit, Qt.Key.Key_Return)
    assert formula.preview_edit.toPlainText() == r"\(v=\frac{d}{t}\)"
    assert formula.plan() is None
    table = TableDialog()
    table.paste_clipboard_text("Temperature / K\tTime / s\tValue\n273\t0\t1.20\n283\t10\t1.42\n293\t20\t1.65")
    table.caption_edit.setText("Measurement results")
    table.label_edit.setText("tab:results")
    table_before = table.values()
    table.preview_table.selectAll()
    table.clear_selection()
    table.undo()
    assert table.values() == table_before
    block = TableEditor(TableEditorModel(TableData(
        columns=[ColumnSpec(id="reading", name="Reading", dataType="number"),
                 ColumnSpec(id="valid", name="Valid", dataType="boolean")],
        rows=[TableRow(id="custom-a", cells={"reading": Cell(kind="number", value=0), "valid": Cell(kind="boolean", value=False)}),
              TableRow(id="custom-b", cells={"reading": Cell(kind="number", value=2), "valid": Cell(kind="boolean", value=True)})],
    )))
    block.setWindowTitle("ICSTeX Block Table QA")
    block.resize(920, 500)
    report = {"pid": os.getpid(), "platform": app.platformName(), "synthetic_only": True, "windows": {}}
    for name, widget in (("formula", formula), ("table", table), ("block-table", block)):
        widget.show()
        app.processEvents()
        exposed = QTest.qWaitForWindowExposed(widget, 2000)
        app.processEvents()
        path = args.output / f"{name}.png"
        assert widget.grab().save(str(path))
        report["windows"][name] = {"exposed": exposed, "size": [widget.width(), widget.height()], "screenshot": path.name}
    if args.keyboard_pages:
        report["keyboard_pages"] = []
        for category in CATEGORY_LABELS:
            formula.keyboard._switch_category(category)
            app.processEvents()
            path = args.output / f"keyboard-{category}.png"
            assert formula.keyboard.grab().save(str(path))
            report["keyboard_pages"].append(path.name)
        formula.keyboard._switch_category("base")
    formula.source_mode_check.setChecked(True)
    app.processEvents()
    assert formula.grab().save(str(args.output / "formula-source.png"))
    formula.source_mode_check.setChecked(False)
    report["formula_preview"] = formula.preview_edit.toPlainText()
    report["table_zero_preserved"] = table._cell_text(1, 1) == "0"
    report["block_zero_false_visible"] = [block.table.item(0, column).text() for column in range(2)] == ["0", "False"]
    report["unsubmitted"] = formula.plan() is None
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if args.hold_seconds:
        QTimer.singleShot(min(60, max(1, args.hold_seconds)) * 1000, app.quit)
        app.exec()
    for widget in (formula, table, block):
        widget.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
