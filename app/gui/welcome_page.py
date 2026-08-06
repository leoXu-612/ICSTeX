from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.gui.assets import app_cover_path
from app.gui.icons import icon
from app.gui.main_window_support import set_dynamic_property


class WelcomePage(QWidget):
    newProjectRequested = Signal()
    openFileRequested = Signal()
    openFolderRequested = Signal()
    guideRequested = Signal()
    recentProjectRequested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("welcomePage")
        self.toolchain_label = QLabel("正在检测 LaTeX 环境...")
        self.toolchain_label.setObjectName("welcomeMuted")
        self.toolchain_label.setWordWrap(True)
        self.recent_list = QVBoxLayout()
        self._build()

    def set_toolchain_status(self, ready: bool, message: str) -> None:
        prefix = "LaTeX 环境就绪" if ready else "LaTeX 环境未就绪"
        self.toolchain_label.setText(f"{prefix}：{message}")
        set_dynamic_property(self.toolchain_label, "state", "ready" if ready else "warning")

    def set_recent_projects(self, paths: list[Path]) -> None:
        _clear_layout(self.recent_list)
        if not paths:
            label = QLabel("暂无最近项目")
            label.setObjectName("welcomeMuted")
            self.recent_list.addWidget(label)
            return
        for path in paths[:6]:
            button = QPushButton(path.name)
            button.setObjectName("welcomeRecent")
            button.setIcon(icon("folder", size=16))
            button.setIconSize(QSize(16, 16))
            button.setToolTip(str(path))
            button.clicked.connect(lambda _checked=False, item=path: self.recentProjectRequested.emit(str(item)))
            self.recent_list.addWidget(button)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(18)
        cover = QLabel()
        cover.setObjectName("welcomeCover")
        cover.setFixedSize(88, 88)
        cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(app_cover_path()))
        if pixmap.isNull():
            cover.setText("ICSTeX")
        else:
            cover.setPixmap(
                pixmap.scaled(
                    QSize(82, 82),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        header.addWidget(cover)

        title_column = QVBoxLayout()
        title_column.setSpacing(6)
        kicker = QLabel("ICC Student's TeX")
        kicker.setObjectName("welcomeKicker")
        title = QLabel("欢迎使用 ICSTeX")
        title.setObjectName("welcomeTitle")
        subtitle = QLabel("从模板开始，或打开已有 LaTeX 项目。")
        subtitle.setObjectName("welcomeSubtitle")
        title_column.addStretch()
        title_column.addWidget(kicker)
        title_column.addWidget(title)
        title_column.addWidget(subtitle)
        title_column.addStretch()
        header.addLayout(title_column, 1)
        layout.addLayout(header)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.new_project_button = QPushButton("新建 IA 项目")
        self.new_project_button.setObjectName("primaryButton")
        self.open_file_button = QPushButton("打开 .tex")
        self.open_folder_button = QPushButton("打开项目文件夹")
        self.guide_button = QPushButton("新手导引")
        self.new_project_button.setIcon(icon("folder-plus", "#ffffff", 16))
        self.open_file_button.setIcon(icon("folder-open", size=16))
        self.open_folder_button.setIcon(icon("folder", size=16))
        self.guide_button.setIcon(icon("info", size=16))
        for button in (self.new_project_button, self.open_file_button, self.open_folder_button, self.guide_button):
            button.setIconSize(QSize(16, 16))
            button.setMinimumHeight(32)
            action_row.addWidget(button)
        action_row.addStretch()
        layout.addLayout(action_row)

        status_box = QFrame()
        status_box.setObjectName("welcomeBox")
        status_layout = QVBoxLayout(status_box)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_title = QLabel("当前环境")
        status_title.setObjectName("welcomeSectionTitle")
        status_layout.addWidget(status_title)
        status_layout.addWidget(self.toolchain_label)
        recent_box = QFrame()
        recent_box.setObjectName("welcomeBox")
        recent_layout = QVBoxLayout(recent_box)
        recent_layout.setContentsMargins(14, 12, 14, 12)
        recent_title = QLabel("最近项目")
        recent_title.setObjectName("welcomeSectionTitle")
        recent_layout.addWidget(recent_title)
        recent_layout.addLayout(self.recent_list)
        content_row = QHBoxLayout()
        content_row.setSpacing(12)
        status_box.setMinimumWidth(280)
        content_row.addWidget(status_box, 1)
        content_row.addWidget(recent_box, 2)
        layout.addLayout(content_row)
        layout.addStretch()

        self.new_project_button.clicked.connect(self.newProjectRequested.emit)
        self.open_file_button.clicked.connect(self.openFileRequested.emit)
        self.open_folder_button.clicked.connect(self.openFolderRequested.emit)
        self.guide_button.clicked.connect(self.guideRequested.emit)


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.deleteLater()
