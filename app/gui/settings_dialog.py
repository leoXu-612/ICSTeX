from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.latex_tools import LaTeXEngine
from app.core.settings import AppPreferences


class SettingsDialog(QDialog):
    def __init__(self, preferences: AppPreferences, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.engine_combo = QComboBox()
        for engine in LaTeXEngine:
            self.engine_combo.addItem(engine.display_name, engine.value)
        index = self.engine_combo.findData(preferences.default_engine.value)
        self.engine_combo.setCurrentIndex(max(index, 0))

        self.auto_compile_check = QCheckBox("开启自动编译")
        self.auto_compile_check.setChecked(preferences.auto_compile)
        self.fast_preview_check = QCheckBox("自动编译使用快速图片预览")
        self.fast_preview_check.setToolTip("仅预览使用本地代理图；手动编译和导出始终使用原图。")
        self.fast_preview_check.setChecked(preferences.fast_preview)
        self.save_debounce_spin = _spin(200, 5000, preferences.save_debounce_ms, 100, " ms")
        self.compile_debounce_spin = _spin(300, 10000, preferences.compile_debounce_ms, 100, " ms")
        self.font_size_spin = _spin(9, 28, preferences.editor_font_size, 1, " pt")
        self.auto_item_check = QCheckBox("自动续写 \\item")
        self.auto_item_check.setChecked(preferences.auto_item)
        self.auto_environment_check = QCheckBox("自动补全 \\begin / \\end")
        self.auto_environment_check.setChecked(preferences.auto_environment)
        self.auto_pairs_check = QCheckBox("自动配对括号")
        self.auto_pairs_check.setChecked(preferences.auto_pairs)
        self.snippets_check = QCheckBox("启用 snippets")
        self.snippets_check.setChecked(preferences.snippets)
        self.soft_wrap_check = QCheckBox("源码自动换行")
        self.soft_wrap_check.setToolTip("长行接近源码窗口边缘时自动折行，避免左右拖动查看代码。")
        self.soft_wrap_check.setChecked(preferences.soft_wrap)
        self._ocr_mgr = None
        self._build()

    def values(self) -> AppPreferences:
        return AppPreferences(
            default_engine=LaTeXEngine(str(self.engine_combo.currentData())),
            auto_compile=self.auto_compile_check.isChecked(),
            fast_preview=self.fast_preview_check.isChecked(),
            save_debounce_ms=self.save_debounce_spin.value(),
            compile_debounce_ms=self.compile_debounce_spin.value(),
            editor_font_size=self.font_size_spin.value(),
            auto_item=self.auto_item_check.isChecked(),
            auto_environment=self.auto_environment_check.isChecked(),
            auto_pairs=self.auto_pairs_check.isChecked(),
            snippets=self.snippets_check.isChecked(),
            soft_wrap=self.soft_wrap_check.isChecked(),
        )

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("默认编译器", self.engine_combo)
        form.addRow("自动编译", self.auto_compile_check)
        form.addRow("快速预览", self.fast_preview_check)
        form.addRow("自动保存延迟", self.save_debounce_spin)
        form.addRow("自动编译延迟", self.compile_debounce_spin)
        form.addRow("编辑器字号", self.font_size_spin)
        form.addRow("列表辅助", self.auto_item_check)
        form.addRow("环境补全", self.auto_environment_check)
        form.addRow("括号配对", self.auto_pairs_check)
        form.addRow("代码片段", self.snippets_check)
        form.addRow("自动换行", self.soft_wrap_check)
        layout.addLayout(form)

        self.ocr_status = QLabel("公式识别 (pix2tex)：检测中…")
        self.ocr_status.setWordWrap(True)
        self.ocr_install_button = QPushButton("安装（约 1.2GB 依赖 + 116MB 模型）")
        self.ocr_remove_button = QPushButton("移除")
        self.ocr_install_button.clicked.connect(self._ocr_install)
        self.ocr_remove_button.clicked.connect(self._ocr_remove)
        ocr_row = QHBoxLayout()
        ocr_row.addWidget(self.ocr_install_button)
        ocr_row.addWidget(self.ocr_remove_button)
        ocr_row.addStretch()
        layout.addWidget(QLabel("可选本地工具（不影响核心功能）："))
        layout.addWidget(self.ocr_status)
        layout.addLayout(ocr_row)
        license_label = QLabel("模型权重许可 CC BY-NC-SA；仅本地使用，不随项目/导出包分发。")
        license_label.setWordWrap(True)
        layout.addWidget(license_label)
        self._refresh_ocr_status()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _get_ocr_manager(self):
        if self._ocr_mgr is None:
            from app.optional_tools.pix2tex.manager import OcrManager

            self._ocr_mgr = OcrManager(self)
            self._ocr_mgr.status_changed.connect(lambda _state: self._refresh_ocr_status())
            self._ocr_mgr.install_finished.connect(lambda _ok, _state: self._refresh_ocr_status())
        return self._ocr_mgr

    def _refresh_ocr_status(self) -> None:
        manager = self._get_ocr_manager()
        self.ocr_status.setText(f"公式识别 (pix2tex)：{manager.status() if manager else '未安装'}")

    def _ocr_install(self) -> None:
        self._get_ocr_manager().install(with_models=True)
        self.ocr_status.setText("公式识别 (pix2tex)：安装中…")

    def _ocr_remove(self) -> None:
        self._get_ocr_manager().remove()
        self.ocr_status.setText("公式识别 (pix2tex)：移除中…")


def _spin(low: int, high: int, value: int, step: int, suffix: str) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(low, high)
    spin.setValue(value)
    spin.setSingleStep(step)
    spin.setSuffix(suffix)
    return spin
