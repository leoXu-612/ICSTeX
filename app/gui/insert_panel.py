from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.latex_insertions import (
    FigureLayout,
    FigureLayoutItem,
    FigureLayoutSpec,
    FigureSpec,
    HyperlinkSpec,
    TableSpec,
    all_templates,
    figure_layout_snippet,
    parse_delimited,
    parse_tabular,
)


class InsertPanel(QWidget):
    figureRequested = Signal()
    sideBySideFigureRequested = Signal()
    tableRequested = Signal()
    hyperlinkRequested = Signal()
    equationRequested = Signal()
    listRequested = Signal()
    sectionRequested = Signal()
    casesRequested = Signal()
    quoteRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("insertPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        tools = [
            ("插入图片", self.figureRequested),
            ("图片布局", self.sideBySideFigureRequested),
            ("插入表格", self.tableRequested),
            ("超链接", self.hyperlinkRequested),
            ("公式", self.equationRequested),
            ("列表", self.listRequested),
            ("章节标题", self.sectionRequested),
            ("分段函数", self.casesRequested),
            ("引用块", self.quoteRequested),
        ]
        for label, signal in tools:
            button = _tool_button(label)
            button.clicked.connect(signal.emit)
            layout.addWidget(button)
        layout.addStretch()


class TemplatesPanel(QWidget):
    templateRequested = Signal(str)
    saveCurrentRequested = Signal()
    importRequested = Signal()
    exportRequested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("templatesPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.template_combo = QComboBox()
        self.refresh_templates()
        layout.addWidget(self.template_combo)

        create_button = _tool_button("用所选模板新建")
        create_button.setObjectName("primaryButton")
        create_button.clicked.connect(self._emit_create)
        layout.addWidget(create_button)

        export_button = _tool_button("导出所选模板")
        export_button.clicked.connect(self._emit_export)
        layout.addWidget(export_button)

        import_button = _tool_button("导入 .tex 模板")
        import_button.clicked.connect(self.importRequested.emit)
        layout.addWidget(import_button)

        save_button = _tool_button("保存当前为模板")
        save_button.clicked.connect(self.saveCurrentRequested.emit)
        layout.addWidget(save_button)
        layout.addStretch()

    def refresh_templates(self) -> None:
        current_key = self.template_combo.currentData() if hasattr(self, "template_combo") else None
        self.template_combo.clear()
        for template in all_templates():
            self.template_combo.addItem(template.title, template.key)
        if current_key:
            index = self.template_combo.findData(current_key)
            if index >= 0:
                self.template_combo.setCurrentIndex(index)

    def _emit_create(self) -> None:
        key = self.template_combo.currentData()
        if isinstance(key, str):
            self.templateRequested.emit(key)

    def _emit_export(self) -> None:
        key = self.template_combo.currentData()
        if isinstance(key, str):
            self.exportRequested.emit(key)


class FigureDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("插入图片")
        self.image_edit = QLineEdit()
        self.width_spin = _ratio_spinbox(0.8)
        self.caption_edit = QLineEdit()
        self.label_edit = QLineEdit("fig:")
        self.placement_combo = _placement_combo()
        self._build(_file_row(self.image_edit, self._browse_image))

    def values(self) -> FigureSpec:
        return FigureSpec(
            image_path=self.image_edit.text().strip(),
            width=self.width_spin.value(),
            caption=self.caption_edit.text().strip(),
            label=self.label_edit.text().strip(),
            placement=self.placement_combo.currentText(),
        )

    def _build(self, image_row: QWidget) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("图片", image_row)
        form.addRow("宽度", self.width_spin)
        form.addRow("说明文字", self.caption_edit)
        form.addRow("标签", self.label_edit)
        form.addRow("位置", self.placement_combo)
        layout.addLayout(form)
        layout.addWidget(_buttons(self))

    def _browse_image(self) -> None:
        _browse_into(self, self.image_edit)


class FigureLayoutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("插入图片布局")
        self.setMinimumWidth(720)
        self.layout_combo = QComboBox()
        for layout in FigureLayout:
            self.layout_combo.addItem(layout.display_name, layout.value)
        self.image_edits = [QLineEdit() for _ in range(4)]
        self.caption_edits = [QLineEdit() for _ in range(4)]
        self.width_spins = [_ratio_spinbox(0.48) for _ in range(4)]
        self.item_groups: list[QGroupBox] = []
        self.caption_edit = QLineEdit()
        self.label_edit = QLineEdit("fig:")
        self.placement_combo = _placement_combo()
        self.layout_hint = QLabel()
        self.layout_hint.setWordWrap(True)
        self.layout_hint.setObjectName("panelHint")
        self._layout_widths: dict[FigureLayout, tuple[float, ...]] = {
            FigureLayout.HORIZONTAL: (0.48, 0.48, 0.48, 0.48),
            FigureLayout.VERTICAL: (0.80, 0.80, 0.48, 0.48),
            FigureLayout.GRID_2X2: (0.48, 0.48, 0.48, 0.48),
        }
        self._active_layout = FigureLayout.HORIZONTAL
        self._build()
        self.layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        for spin in self.width_spins:
            spin.valueChanged.connect(lambda _value: self._update_layout_hint())
        self._apply_layout(FigureLayout.HORIZONTAL)

    def values(self) -> FigureLayoutSpec:
        layout = self._selected_layout()
        count = 4 if layout is FigureLayout.GRID_2X2 else 2
        return FigureLayoutSpec(
            layout=layout,
            items=tuple(
                FigureLayoutItem(
                    image_path=self.image_edits[index].text().strip(),
                    width=self.width_spins[index].value(),
                    caption=self.caption_edits[index].text().strip(),
                )
                for index in range(count)
            ),
            caption=self.caption_edit.text().strip(),
            label=self.label_edit.text().strip(),
            placement=self.placement_combo.currentText(),
        )

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout_form = QFormLayout()
        layout_form.addRow("排列方式", self.layout_combo)
        layout.addLayout(layout_form)
        layout.addWidget(self.layout_hint)

        self.item_container = QWidget()
        item_grid = QGridLayout(self.item_container)
        item_grid.setContentsMargins(0, 0, 0, 0)
        item_grid.setHorizontalSpacing(10)
        item_grid.setVerticalSpacing(10)
        for index in range(4):
            group = QGroupBox()
            form = QFormLayout(group)
            image_edit = self.image_edits[index]
            form.addRow(
                "图片",
                _file_row(image_edit, lambda edit=image_edit: _browse_into(self, edit)),
            )
            form.addRow("子图说明", self.caption_edits[index])
            form.addRow("宽度", self.width_spins[index])
            item_grid.addWidget(group, index // 2, index % 2)
            self.item_groups.append(group)
        self.item_scroll = QScrollArea()
        self.item_scroll.setWidgetResizable(True)
        self.item_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.item_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.item_scroll.setWidget(self.item_container)
        layout.addWidget(self.item_scroll)

        figure_form = QFormLayout()
        figure_form.addRow("总说明", self.caption_edit)
        figure_form.addRow("标签", self.label_edit)
        figure_form.addRow("位置", self.placement_combo)
        layout.addLayout(figure_form)
        layout.addWidget(_buttons(self))

    def accept(self) -> None:
        try:
            figure_layout_snippet(self.values())
        except ValueError as exc:
            QMessageBox.warning(self, "图片布局不完整", str(exc))
            return
        super().accept()

    def _selected_layout(self) -> FigureLayout:
        return FigureLayout(str(self.layout_combo.currentData()))

    def _on_layout_changed(self, _index: int) -> None:
        self._layout_widths[self._active_layout] = tuple(spin.value() for spin in self.width_spins)
        selected = self._selected_layout()
        for spin, value in zip(self.width_spins, self._layout_widths[selected], strict=True):
            spin.setValue(value)
        self._active_layout = selected
        self._apply_layout(selected)

    def _apply_layout(self, layout: FigureLayout) -> None:
        titles = {
            FigureLayout.HORIZONTAL: ("左图", "右图"),
            FigureLayout.VERTICAL: ("上图", "下图"),
            FigureLayout.GRID_2X2: ("左上", "右上", "左下", "右下"),
        }[layout]
        for index, group in enumerate(self.item_groups):
            visible = index < len(titles)
            group.setVisible(visible)
            if visible:
                group.setTitle(titles[index])
        self.item_container.layout().activate()
        content_width = self.item_container.sizeHint().width()
        content_height = self.item_container.sizeHint().height() + 4
        self.setMinimumWidth(max(720, content_width + 48))
        self.item_scroll.setFixedHeight(min(max(content_height, 170), 300))
        self._update_layout_hint()

    def _update_layout_hint(self) -> None:
        layout = self._selected_layout()
        widths = [spin.value() for spin in self.width_spins]
        if layout is FigureLayout.HORIZONTAL:
            detail = f"本行宽度合计 {widths[0] + widths[1]:.2f} / 1.00。"
        elif layout is FigureLayout.GRID_2X2:
            detail = (
                f"上排 {widths[0] + widths[1]:.2f} / 1.00；"
                f"下排 {widths[2] + widths[3]:.2f} / 1.00。"
            )
        else:
            detail = "上下两图可分别设置宽度。"
        self.layout_hint.setText(
            detail + " 仅调整宽度，图片高度自动按原始比例缩放，不会拉伸变形。"
        )


# Compatibility alias for callers that still use the former two-image name.
SideBySideFigureDialog = FigureLayoutDialog


class TableDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("插入表格")
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 40)
        self.rows_spin.setValue(3)
        self.columns_spin = QSpinBox()
        self.columns_spin.setRange(1, 12)
        self.columns_spin.setValue(3)
        self.alignment_combo = QComboBox()
        self.alignment_combo.addItems(["c", "l", "r"])
        self.booktabs_check = QCheckBox("booktabs")
        self.booktabs_check.setChecked(True)
        self.caption_edit = QLineEdit()
        self.label_edit = QLineEdit("tab:")
        self.placement_combo = _placement_combo()
        self.preview_table = QTableWidget()
        self._build()
        self._resize_table()
        self.rows_spin.valueChanged.connect(lambda _value: self._resize_table())
        self.columns_spin.valueChanged.connect(lambda _value: self._resize_table())

    def values(self) -> TableSpec:
        headers = tuple(self._cell_text(0, column) for column in range(self.columns_spin.value()))
        cells = tuple(
            tuple(self._cell_text(row, column) for column in range(self.columns_spin.value()))
            for row in range(1, self.rows_spin.value() + 1)
        )
        return TableSpec(
            rows=self.rows_spin.value(),
            columns=self.columns_spin.value(),
            alignment=self.alignment_combo.currentText(),
            use_booktabs=self.booktabs_check.isChecked(),
            caption=self.caption_edit.text().strip(),
            label=self.label_edit.text().strip(),
            placement=self.placement_combo.currentText(),
            headers=headers,
            cells=cells,
        )

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("行数", self.rows_spin)
        form.addRow("列数", self.columns_spin)
        form.addRow("对齐", self.alignment_combo)
        form.addRow("样式", self.booktabs_check)
        form.addRow("说明文字", self.caption_edit)
        form.addRow("标签", self.label_edit)
        form.addRow("位置", self.placement_combo)
        layout.addLayout(form)
        import_button = QPushButton("导入现有表格")
        import_button.setToolTip("粘贴已有的 table/tabular LaTeX 代码，反向填入下面的网格。")
        import_button.clicked.connect(self._import_existing)
        layout.addWidget(import_button)
        paste_button = QPushButton("粘贴 CSV / Excel")
        paste_button.setToolTip("从 Excel、Numbers、Google Sheets 复制单元格，或粘贴 CSV，自动填入网格。")
        paste_button.clicked.connect(self._import_delimited)
        layout.addWidget(paste_button)
        self.preview_table.setMinimumSize(460, 220)
        layout.addWidget(self.preview_table)
        layout.addWidget(_buttons(self))

    def _import_existing(self) -> None:
        text, ok = QInputDialog.getMultiLineText(
            self, "导入现有表格", "粘贴 LaTeX 表格代码（table/tabular）：", ""
        )
        if not ok or not text.strip():
            return
        spec = parse_tabular(text)
        if spec is None:
            QMessageBox.information(
                self, "导入现有表格", "没有找到 tabular 环境，请确认粘贴的是表格代码。"
            )
            return
        self.load_spec(spec)

    def _import_delimited(self) -> None:
        text, ok = QInputDialog.getMultiLineText(
            self,
            "粘贴 CSV / Excel",
            "粘贴表格数据（Excel/Numbers/Sheets 单元格或 CSV，第一行作为表头）：",
            "",
        )
        if not ok or not text.strip():
            return
        spec = parse_delimited(text)
        if spec is None:
            QMessageBox.information(
                self, "粘贴 CSV / Excel", "没有解析出表格内容，请确认粘贴的是带分隔符的数据。"
            )
            return
        self.load_spec(spec)

    def load_spec(self, spec: TableSpec) -> None:
        self.rows_spin.setValue(max(1, spec.rows))
        self.columns_spin.setValue(max(1, spec.columns))
        alignment_index = self.alignment_combo.findText(spec.alignment)
        self.alignment_combo.setCurrentIndex(alignment_index if alignment_index >= 0 else 0)
        self.booktabs_check.setChecked(spec.use_booktabs)
        self.caption_edit.setText(spec.caption)
        self.label_edit.setText(spec.label or "tab:")
        placement_index = self.placement_combo.findText(spec.placement)
        if placement_index >= 0:
            self.placement_combo.setCurrentIndex(placement_index)
        self._resize_table()
        columns = self.columns_spin.value()
        for column in range(columns):
            value = spec.headers[column] if column < len(spec.headers) else ""
            self.preview_table.setItem(0, column, QTableWidgetItem(value))
        for row in range(1, self.rows_spin.value() + 1):
            row_cells = spec.cells[row - 1] if row - 1 < len(spec.cells) else ()
            for column in range(columns):
                value = row_cells[column] if column < len(row_cells) else ""
                self.preview_table.setItem(row, column, QTableWidgetItem(value))

    def _resize_table(self) -> None:
        existing = {
            (row, column): self._cell_text(row, column)
            for row in range(self.preview_table.rowCount())
            for column in range(self.preview_table.columnCount())
        }
        rows = self.rows_spin.value() + 1
        columns = self.columns_spin.value()
        self.preview_table.setRowCount(rows)
        self.preview_table.setColumnCount(columns)
        self.preview_table.setVerticalHeaderLabels(["表头", *[f"第 {index} 行" for index in range(1, rows)]])
        self.preview_table.setHorizontalHeaderLabels([f"第 {index} 列" for index in range(1, columns + 1)])
        for row in range(rows):
            for column in range(columns):
                value = existing.get((row, column), "")
                if not value:
                    value = f"Header {column + 1}" if row == 0 else f"Cell {row}-{column + 1}"
                self.preview_table.setItem(row, column, QTableWidgetItem(value))

    def _cell_text(self, row: int, column: int) -> str:
        item = self.preview_table.item(row, column)
        return item.text().strip() if item is not None else ""


class HyperlinkDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("插入超链接")
        self.text_edit = QLineEdit()
        self.url_edit = QLineEdit("https://")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("显示文本", self.text_edit)
        form.addRow("URL", self.url_edit)
        layout.addLayout(form)
        layout.addWidget(_buttons(self))

    def values(self) -> HyperlinkSpec:
        return HyperlinkSpec(text=self.text_edit.text().strip(), url=self.url_edit.text().strip())


def scrollable_panel(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setObjectName("sidebarScroll")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(widget)
    return area


def _tool_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("toolCard")
    button.setMinimumHeight(34)
    return button


def _ratio_spinbox(value: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(0.05, 1.0)
    spin.setSingleStep(0.05)
    spin.setDecimals(2)
    spin.setValue(value)
    spin.setSuffix(r"\textwidth")
    return spin


def _placement_combo() -> QComboBox:
    combo = QComboBox()
    combo.addItems(["htbp", "H", "t", "b", "p"])
    return combo


def _file_row(edit: QLineEdit, browse: Callable[[], None]) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    button = QPushButton("浏览")
    button.clicked.connect(browse)
    layout.addWidget(edit)
    layout.addWidget(button)
    return row


def _browse_into(parent: QWidget, edit: QLineEdit) -> None:
    file_name, _ = QFileDialog.getOpenFileName(
        parent,
        "选择图片",
        str(Path.home()),
        "图片 (*.pdf *.png *.jpg *.jpeg);;所有文件 (*)",
    )
    if file_name:
        edit.setText(file_name)


def _buttons(dialog: QDialog) -> QDialogButtonBox:
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    return buttons
