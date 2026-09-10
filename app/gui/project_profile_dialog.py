"""Explicit local profile editing; no source conversion or implicit compilation."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QScrollArea, QVBoxLayout, QWidget)

from app.core.latex_insertions import all_templates
from app.core.latex_tools import LaTeXEngine
from app.core.project_profile import ProjectProfile, load_profile, profile_bytes, save_profile


class ProjectProfileDialog(QDialog):
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = root
        self.snapshot = load_profile(root)
        self.saved_snapshot = None
        self.setWindowTitle("项目配置")
        self.resize(570, 580)
        profile = self.snapshot.profile or ProjectProfile()
        layout = QVBoxLayout(self)
        heading = QLabel(f"当前项目：{root.name}\n仅保存本地配置；不会改正文、创建建议目录或自动编译。")
        heading.setTextFormat(Qt.TextFormat.PlainText)
        heading.setWordWrap(True)
        layout.addWidget(heading)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        form = QFormLayout(body)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.enabled = QCheckBox("使用此项目配置（禁用会保留填写内容）")
        self.enabled.setChecked(profile.enabled)
        form.addRow(self.enabled)
        self.template = QComboBox()
        self.template.addItem("不指定", "")
        for template in all_templates():
            self.template.addItem(template.title, template.key)
        if self.template.findData(profile.template) < 0:
            self.template.addItem(f"本机未找到：{profile.template}", profile.template)
        self.template.setCurrentIndex(self.template.findData(profile.template))
        form.addRow("参考模板（不替换正文）", self.template)
        self.engine = QComboBox()
        self.engine.addItem("不指定", "")
        for engine in LaTeXEngine:
            self.engine.addItem(engine.display_name, engine.value)
        self.engine.setCurrentIndex(self.engine.findData(profile.engine))
        form.addRow("建议编译引擎", self.engine)
        note = QLabel("只比较实际编译引擎，不覆盖源码中的 Magic Comment；切换引擎请使用编译菜单。")
        note.setWordWrap(True)
        form.addRow(note)
        self.directories = QPlainTextEdit("\n".join(profile.directories))
        self.directories.setMaximumHeight(100)
        self.directories.setAccessibleName("目录建议，每行一个项目相对路径")
        form.addRow("目录建议（每行一个）", self.directories)
        self.word_min = QLineEdit("" if profile.word_min is None else str(profile.word_min))
        self.word_max = QLineEdit("" if profile.word_max is None else str(profile.word_max))
        for edit in (self.word_min, self.word_max):
            edit.setPlaceholderText("留空表示不设置；不是课程默认要求")
        form.addRow("正文字数下限", self.word_min)
        form.addRow("正文字数上限", self.word_max)
        self.resources = QCheckBox("显示静态资源检查")
        self.resources.setChecked(profile.check_resources)
        self.references = QCheckBox("显示静态引用与标签检查")
        self.references.setChecked(profile.check_references)
        form.addRow(self.resources)
        form.addRow(self.references)
        policy = QLabel("关闭的选项显示“不适用”，不算通过。保存、输入身份、FINAL 和 PDF 安全检查始终保留。")
        policy.setWordWrap(True)
        form.addRow(policy)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        self.error = QLabel(self.snapshot.error or ("配置读取中发生变化，请取消后重开。" if not self.snapshot.stable else ""))
        self.error.setTextFormat(Qt.TextFormat.PlainText)
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存配置")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        layout.addWidget(self.buttons)
        if self.snapshot.error or not self.snapshot.stable:
            body.setEnabled(False)
            self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def values(self):
        def target(edit):
            value = edit.text().strip()
            if value and not value.isdecimal():
                raise ValueError("字数目标请填写非负整数，或留空。")
            return int(value) if value else None
        profile = replace(self.snapshot.profile or ProjectProfile(),
                          enabled=self.enabled.isChecked(), template=str(self.template.currentData()),
                          engine=str(self.engine.currentData()),
                          directories=tuple(line.strip() for line in self.directories.toPlainText().splitlines() if line.strip()),
                          word_min=target(self.word_min), word_max=target(self.word_max),
                          check_resources=self.resources.isChecked(), check_references=self.references.isChecked())
        profile_bytes(profile)
        return profile

    def accept(self):
        try:
            self.saved_snapshot = save_profile(self.root, self.values(), expected=self.snapshot)
        except (OSError, ValueError) as exc:
            self.error.setText(f"未保存，草稿仍保留。{exc}")
            return
        super().accept()


def show_project_profile(window):
    _, scope, _, _, _, _ = window.readiness._context()
    if scope is None:
        QMessageBox.information(window, "项目配置", "请先打开或创建本地项目。未命名草稿仍可继续编辑。")
        return
    dialog = ProjectProfileDialog(scope, window)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        window.readiness.invalidate()
        window.statusBar().showMessage("项目配置已保存；提交检查需手动刷新。正文和编译状态未改变。", 6000)
