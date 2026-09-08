"""Small Chinese-first settings surface; native updaters own their progress UI."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout)

from app import __version__


class AppUpdateDialog(QDialog):
    check_requested = Signal()
    automatic_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("软件更新")
        self.setObjectName("appUpdateDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.resize(480, 300)
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)
        self.title = QLabel("ICSTeX 软件更新")
        font = self.title.font()
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        self.title.setFont(font)
        layout.addWidget(self.title)
        self.version = QLabel(f"当前版本：{__version__}")
        layout.addWidget(self.version)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setAccessibleName("更新状态")
        layout.addWidget(self.status)
        self.automatic = QCheckBox("每天自动检查更新（仅在 ICSTeX 运行时）")
        self.automatic.toggled.connect(self.automatic_changed)
        layout.addWidget(self.automatic)
        self.privacy = QLabel(
            "检查会访问更新服务器，下载会访问发布资源所在服务。"
            "不发送论文、项目路径、日志或设备标识。下载和安装需要另行确认；"
            "更新前会检查全部窗口并保存文档。"
        )
        self.privacy.setWordWrap(True)
        layout.addWidget(self.privacy)
        self.source = QLabel()
        self.source.setTextFormat(Qt.TextFormat.PlainText)
        self.source.setWordWrap(True)
        layout.addWidget(self.source)
        layout.addStretch(1)
        row = QHBoxLayout()
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.close)
        row.addWidget(self.close_button)
        row.addStretch(1)
        self.check_button = QPushButton("检查更新")
        self.check_button.setObjectName("primaryAction")
        self.check_button.clicked.connect(self.check_requested)
        row.addWidget(self.check_button)
        layout.addLayout(row)

    def set_state(self, *, available: bool, automatic: bool,
                  message: str, source: str = "", channel: str = "") -> None:
        self.status.setText(message)
        self.check_button.setEnabled(available)
        self.automatic.setEnabled(available)
        self.automatic.blockSignals(True)
        self.automatic.setChecked(automatic if available else False)
        self.automatic.blockSignals(False)
        self.version.setText(f"当前版本：{__version__}" + (f"  ·  {channel}" if channel else ""))
        self.source.setText(source)
        self.source.setVisible(bool(source))
