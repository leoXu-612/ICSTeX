"""Three-way merge resolution UI (Sprint 4 GUI milestone)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.source_merge import CellChange, MergeResult
from app.core.blocks.table_model import Cell


class MergeDialog(QDialog):
    """Shows Base/Remote/Local values per conflict and resolves them."""

    def __init__(self, result: MergeResult, parent=None) -> None:
        super().__init__(parent)
        self.result = result
        self.setWindowTitle("同步冲突")
        self._remote_buttons: list[QRadioButton] = []
        self._local_buttons: list[QRadioButton] = []
        self._manual_edits: list[QLineEdit] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"外部变更 {result.summary.get('changed', 0)} 处，冲突 {len(result.conflicts)} 处。"))
        for conflict in result.conflicts:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.addWidget(
                QLabel(f"{conflict.rowId}/{conflict.columnId}  Base={_value(conflict.base)}")
            )
            remote = QRadioButton(f"采用外部：{_value(conflict.remote)}")
            local = QRadioButton(f"采用本地：{_value(conflict.local)}")
            manual = QLineEdit()
            manual.setPlaceholderText("手动输入")
            self._remote_buttons.append(remote)
            self._local_buttons.append(local)
            self._manual_edits.append(manual)
            group = QButtonGroup(self)
            group.addButton(remote)
            group.addButton(local)
            local.setChecked(True)
            row_layout.addWidget(remote)
            row_layout.addWidget(local)
            row_layout.addWidget(manual)
            layout.addWidget(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._resolve)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _resolve(self) -> None:
        for index, conflict in enumerate(self.result.conflicts):
            manual_text = self._manual_edits[index].text().strip()
            if manual_text:
                value = manual_text
                kind = "text"
            elif self._remote_buttons[index].isChecked():
                value = conflict.remote.value
                kind = conflict.remote.kind
            else:
                value = conflict.local.value
                kind = conflict.local.kind
            self.result.data.rows = [
                row
                for row in self.result.data.rows
                if row.id != conflict.rowId or conflict.columnId not in row.cells
            ]
            from app.core.blocks.table_model import TableRow

            self.result.data.rows.append(
                TableRow(id=conflict.rowId, cells={conflict.columnId: Cell(kind=kind, value=value)})
            )
        self.accept()


def _value(cell: Cell) -> str:
    return "" if cell.kind == "empty" else str(cell.value)
