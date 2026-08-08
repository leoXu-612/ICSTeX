"""AppTheme settings page (Sprint 5 GUI milestone)."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.schema import validate_theme
from app.core.blocks.theme import APP_THEME_TOKENS, AppTheme


class ThemeSettings(QWidget):
    """Edits and validates an AppTheme; persists to a JSON file."""

    def __init__(self, theme: AppTheme | None = None, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme or AppTheme(id="theme_custom", name="Custom")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["light", "dark", "system"])
        self.token_edits: dict[str, QLineEdit] = {}
        self.preview_label = QLabel("预览")
        self.preview_label.setMinimumHeight(48)
        self.status_label = QLabel("")
        self.save_button = QPushButton("保存主题")
        self.save_button.clicked.connect(self._on_save)

        form = QFormLayout()
        form.addRow("模式", self.mode_combo)
        for token in APP_THEME_TOKENS:
            edit = QLineEdit()
            edit.setText(str(self._theme.tokens.get(token, "")))
            self.token_edits[token] = edit
            form.addRow(token, edit)
        typography = self._theme.typography
        self.ui_size_spin = QSpinBox()
        self.ui_size_spin.setRange(10, 20)
        self.ui_size_spin.setValue(int(typography.get("uiSizePx", 14)))
        self.code_size_spin = QSpinBox()
        self.code_size_spin.setRange(9, 16)
        self.code_size_spin.setValue(int(typography.get("codeSizePx", 12)))
        form.addRow("UI 字号", self.ui_size_spin)
        form.addRow("代码字号", self.code_size_spin)
        self.translucent_check = QCheckBox("半透明侧栏")
        self.reduced_motion_combo = QComboBox()
        self.reduced_motion_combo.addItems(["system", "always", "never"])
        form.addRow("减少动态效果", self.reduced_motion_combo)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.save_button)
        self._refresh_preview()

    def build_theme(self) -> AppTheme:
        tokens = {token: edit.text().strip() for token, edit in self.token_edits.items()}
        effects = {
            "translucentSidebar": self.translucent_check.isChecked(),
            "reducedMotion": self.reduced_motion_combo.currentText(),
        }
        typography = {
            "uiFont": self._theme.typography.get("uiFont", "system-ui"),
            "codeFont": self._theme.typography.get("codeFont", "SF Mono"),
            "uiSizePx": self.ui_size_spin.value(),
            "codeSizePx": self.code_size_spin.value(),
        }
        return AppTheme(
            schemaVersion=self._theme.schemaVersion,
            id=self._theme.id,
            name=self._theme.name,
            mode=self.mode_combo.currentText(),
            tokens=tokens,
            typography=typography,
            effects=effects,
        )

    def validate(self) -> list[str]:
        issues = validate_theme(self.build_theme().to_dict())
        for token, edit in self.token_edits.items():
            value = edit.text().strip()
            if value and not (value.startswith("#") and len(value) in (4, 7)):
                issues.append(f"token {token} 应为 #RGB 或 #RRGGBB 颜色")
        return issues

    def save(self, path: Path) -> None:
        issues = self.validate()
        if issues:
            raise ValueError("主题校验失败：" + "; ".join(issues[:3]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.build_theme().to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _on_save(self) -> None:
        issues = self.validate()
        if issues:
            self.status_label.setText("校验失败：" + "; ".join(issues[:2]))
            return
        self._theme = self.build_theme()
        self._refresh_preview()
        self.status_label.setText("主题已更新。")

    def _refresh_preview(self) -> None:
        theme = self.build_theme()
        self.preview_label.setStyleSheet(
            f"background: {theme.tokens.get('background', '#ffffff')};"
            f"color: {theme.tokens.get('foreground', '#000000')};"
            "border: 1px solid #cccccc; padding: 8px;"
        )
