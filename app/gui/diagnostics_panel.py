from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.diagnostics import Diagnostic
from app.gui.insert_panel import scrollable_panel
from app.gui.table_navigation import enable_table_key_activation
from app.gui.theme import PRIMARY_BUTTON_STATE_STYLE
from app.gui.responsive.helpers import ButtonFlowLayout


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
        self.fix_button = QPushButton("查看修复…")
        self.fix_button.setEnabled(False)
        self.fix_button.setObjectName("primaryButton")
        self.fix_button.setStyleSheet(PRIMARY_BUTTON_STATE_STYLE)
        self.table = QTableWidget(0, 4)
        self.jump_button = QPushButton("定位问题")
        self.jump_button.setEnabled(False)
        self.raw_toggle = QPushButton("原始日志")
        self.raw_toggle.setCheckable(True)
        self.raw_view = QPlainTextEdit()
        self.raw_view.setReadOnly(True)
        self.raw_view.setTabChangesFocus(True)
        self.raw_view.setAccessibleName("选中问题的原始日志（只读）")
        self.raw_view.setMaximumHeight(100)
        self.detail_label = QLabel()
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextFormat(Qt.TextFormat.PlainText)
        self._build()
        self._update_selection()

    def set_diagnostics(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics = diagnostics
        self.table.setRowCount(0)
        for index, diagnostic in enumerate(diagnostics):
            row = self.table.rowCount()
            self.table.insertRow(row)
            severity_item = QTableWidgetItem(diagnostic.severity_label)
            title_item = QTableWidgetItem(diagnostic.title)
            location = diagnostic.file.name if diagnostic.file else "当前文档"
            location += f"：{diagnostic.line}" if diagnostic.line else "（位置待确认）"
            line_item = QTableWidgetItem(location)
            message_item = QTableWidgetItem(diagnostic.message)
            for item in (severity_item, title_item, line_item, message_item):
                item.setData(Qt.ItemDataRole.UserRole, index)
                item.setToolTip(diagnostic.message)
            line_item.setToolTip(str(diagnostic.file or "当前文档") + (f"\n第 {diagnostic.line} 行" if diagnostic.line else ""))
            self.table.setItem(row, 0, severity_item)
            self.table.setItem(row, 1, title_item)
            self.table.setItem(row, 2, line_item)
            self.table.setItem(row, 3, message_item)
        if diagnostics:
            self.table.selectRow(0)
        self._update_selection()
        self._update_status()

    def _update_selection(self):
        index = self.selected_index()
        diagnostic = self.diagnostics[index] if index is not None and index < len(self.diagnostics) else None
        self.detail_label.setText(diagnostic.message if diagnostic else "")
        self.detail_label.setVisible(diagnostic is not None)
        self.fix_button.setEnabled(bool(diagnostic and diagnostic.fix))
        self.jump_button.setEnabled(bool(diagnostic and (diagnostic.file or diagnostic.line)))
        raw = diagnostic.raw_message if diagnostic else ""
        self.raw_view.setPlainText(raw or "没有关联原始日志；本地静态检查不等于一次完整编译。")
        self.raw_toggle.setEnabled(bool(raw))
        if not raw:
            self.raw_toggle.setChecked(False)

    def selected_index(self) -> int | None:
        selected = self.table.selectedItems()
        if not selected:
            return None
        value = selected[0].data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        outer.addWidget(self.status_label)
        header = ButtonFlowLayout()
        for button in (self.refresh_button, self.jump_button, self.fix_button, self.raw_toggle):
            header.addWidget(button)
        outer.addLayout(header)

        self.table.setHorizontalHeaderLabels(["级别", "发生了什么", "在哪里", "说明与下一步"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setTabKeyNavigation(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(120)
        layout.addWidget(self.table)
        layout.addWidget(self.detail_label)
        self.raw_view.hide()
        self.raw_toggle.toggled.connect(self.raw_view.setVisible)
        self.table.itemSelectionChanged.connect(self._update_selection)

        self.scroll = scrollable_panel(content)
        self.scroll.setObjectName("diagnosticsScroll")
        outer.addWidget(self.scroll)
        outer.addWidget(self.raw_view)
        self.table.currentCellChanged.connect(self.scroll.queueFocusReveal)

        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.fix_button.clicked.connect(self._emit_fix)
        self.jump_button.clicked.connect(self._emit_jump)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._emit_jump())
        self.table.cellActivated.connect(lambda _row, _column: self._emit_jump())
        enable_table_key_activation(self.table)
        self.table.setToolTip("方向键移动，空格选中当前行，Return/Enter 定位；Tab 切换控件。")

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
