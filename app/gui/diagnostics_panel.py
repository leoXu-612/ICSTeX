from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.diagnostics import Diagnostic


class DiagnosticsPanel(QWidget):
    refreshRequested = Signal()
    fixRequested = Signal(int)
    jumpRequested = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("diagnosticsPanel")
        self.diagnostics: list[Diagnostic] = []
        self.status_label = QLabel("尚未检查项目")
        self.status_label.setObjectName("panelHint")
        self.refresh_button = QPushButton("检查项目")
        self.fix_button = QPushButton("修复选中")
        self.fix_button.setObjectName("primaryButton")
        self.table = QTableWidget(0, 4)
        self._build()

    def set_diagnostics(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics = diagnostics
        self.table.setRowCount(0)
        for index, diagnostic in enumerate(diagnostics):
            row = self.table.rowCount()
            self.table.insertRow(row)
            severity_item = QTableWidgetItem(diagnostic.severity_label)
            title_item = QTableWidgetItem(diagnostic.title)
            line_item = QTableWidgetItem(str(diagnostic.line or ""))
            message_item = QTableWidgetItem(diagnostic.message)
            for item in (severity_item, title_item, line_item, message_item):
                item.setData(Qt.ItemDataRole.UserRole, index)
                item.setToolTip(diagnostic.raw_message or diagnostic.message)
            self.table.setItem(row, 0, severity_item)
            self.table.setItem(row, 1, title_item)
            self.table.setItem(row, 2, line_item)
            self.table.setItem(row, 3, message_item)
        self.fix_button.setEnabled(any(diagnostic.fix for diagnostic in diagnostics))
        self._update_status()

    def selected_index(self) -> int | None:
        selected = self.table.selectedItems()
        if not selected:
            return None
        value = selected[0].data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(self.status_label)
        header.addStretch()
        header.addWidget(self.refresh_button)
        header.addWidget(self.fix_button)
        layout.addLayout(header)

        self.table.setHorizontalHeaderLabels(["级别", "问题", "行号", "说明"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.fix_button.clicked.connect(self._emit_fix)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._emit_jump())

    def _emit_fix(self) -> None:
        index = self.selected_index()
        if index is not None:
            self.fixRequested.emit(index)

    def _emit_jump(self) -> None:
        index = self.selected_index()
        if index is not None:
            self.jumpRequested.emit(index)

    def _update_status(self) -> None:
        if not self.diagnostics:
            self.status_label.setText("未发现明显问题")
            return
        errors = sum(1 for diagnostic in self.diagnostics if diagnostic.severity == "error")
        warnings = sum(1 for diagnostic in self.diagnostics if diagnostic.severity == "warning")
        infos = len(self.diagnostics) - errors - warnings
        self.status_label.setText(f"{errors} 个错误 | {warnings} 个警告 | {infos} 个提示")
