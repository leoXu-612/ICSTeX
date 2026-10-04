"""Shared, compact table specifications for insertion and source-backed editing."""
from contextlib import ExitStack

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGridLayout, QLabel, QLineEdit,
    QSpinBox, QToolButton, QVBoxLayout, QWidget,
)


class TableOptions(QWidget):
    changed = Signal()
    fields = ("rows_spin", "columns_spin", "alignment_combo", "booktabs_check",
              "caption_edit", "label_edit", "placement_combo")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tableOptions")
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 40)
        self.rows_spin.setValue(3)
        self.rows_spin.setKeyboardTracking(False)
        self.rows_spin.setAccessibleName("表格数据行数")
        self.columns_spin = QSpinBox()
        self.columns_spin.setRange(1, 12)
        self.columns_spin.setValue(3)
        self.columns_spin.setKeyboardTracking(False)
        self.columns_spin.setAccessibleName("表格列数")
        self.alignment_combo = QComboBox()
        for label, value in (("居中", "c"), ("左对齐", "l"), ("右对齐", "r")):
            self.alignment_combo.addItem(label, value)
        self.alignment_combo.setAccessibleName("表格列对齐")
        self.booktabs_check = QCheckBox("三线表")
        self.booktabs_check.setToolTip("使用 booktabs 三线表；关闭后使用普通表格线。")
        self.booktabs_check.setChecked(True)
        self.caption_edit = QLineEdit()
        self.caption_edit.setPlaceholderText("可选，例如：实验测量结果")
        self.label_edit = QLineEdit("tab:")
        self.label_edit.setPlaceholderText("例如 tab:results")
        self.placement_combo = QComboBox()
        self.placement_combo.addItems(["htbp", "H", "t", "b", "p"])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        specs = QGridLayout()
        specs.setHorizontalSpacing(8)
        specs.setVerticalSpacing(6)
        for column, (label, widget) in enumerate((("数据行", self.rows_spin), ("列", self.columns_spin),
                                                 ("对齐", self.alignment_combo))):
            specs.addWidget(QLabel(label), 0, column * 2)
            specs.addWidget(widget, 0, column * 2 + 1)
        specs.addWidget(self.booktabs_check, 1, 0, 1, 2)
        specs.setColumnStretch(6, 1)
        self.details_button = QToolButton()
        self.details_button.setText("题注与标签 ▸")
        self.details_button.setCheckable(True)
        specs.addWidget(self.details_button, 1, 2, 1, 4)
        layout.addLayout(specs)
        self.details = QWidget()
        form = QFormLayout(self.details)
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("题注", self.caption_edit)
        form.addRow("标签", self.label_edit)
        form.addRow("浮动位置", self.placement_combo)
        layout.addWidget(self.details)
        self.details.hide()
        self.details_button.toggled.connect(self.details.setVisible)
        self.details_button.toggled.connect(lambda opened: self.details_button.setText(
            "题注与标签 ▾" if opened else "题注与标签 ▸"))
        for signal in (self.rows_spin.valueChanged, self.columns_spin.valueChanged,
                       self.alignment_combo.currentIndexChanged, self.booktabs_check.toggled,
                       self.caption_edit.textEdited, self.label_edit.textEdited,
                       self.placement_combo.currentIndexChanged):
            signal.connect(lambda *_: self.changed.emit())

    def load(self, spec):
        """Synchronize without writes/signals or resetting an unchanged text caret."""
        with ExitStack() as stack:
            for name in self.fields:
                stack.enter_context(QSignalBlocker(getattr(self, name)))
            self.rows_spin.setValue(spec.rows)
            self.columns_spin.setValue(spec.columns)
            if self.alignment_combo.findData(spec.alignment) < 0:
                self.alignment_combo.addItem("保留各列对齐", spec.alignment)
            self.alignment_combo.setCurrentIndex(self.alignment_combo.findData(spec.alignment))
            self.booktabs_check.setChecked(spec.use_booktabs)
            for edit, value in ((self.caption_edit, spec.caption), (self.label_edit, spec.label)):
                if edit.text() != value:
                    edit.setText(value)
            if self.placement_combo.findText(spec.placement) < 0:
                self.placement_combo.addItem(spec.placement)
            self.placement_combo.setCurrentIndex(self.placement_combo.findText(spec.placement))

    def changes(self):
        return dict(rows=self.rows_spin.value(), columns=self.columns_spin.value(),
                    alignment=self.alignment_combo.currentData(), use_booktabs=self.booktabs_check.isChecked(),
                    caption=self.caption_edit.text(), label=self.label_edit.text(),
                    placement=self.placement_combo.currentText())
