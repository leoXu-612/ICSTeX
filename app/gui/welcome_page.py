from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence

from PySide6.QtCore import QSize, Qt, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.gui.assets import app_cover_path
from app.gui.icons import icon
from app.gui.main_window_support import set_dynamic_property
from app.gui.theme import PRIMARY_BUTTON_STATE_STYLE
from app.gui.responsive.helpers import (
    layout_reflow,
    resolve_layout_mode,
    update_button_minimum_size,
)


class WelcomePage(QWidget):
    newProjectRequested = Signal()
    openFileRequested = Signal()
    openFolderRequested = Signal()
    guideRequested = Signal()
    recentProjectRequested = Signal(str)
    environmentRequested = Signal()
    recheckRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("welcomePage")
        self._layout_mode = ""
        self.toolchain_label = QLabel("正在检测 LaTeX 环境...")
        self.toolchain_label.setObjectName("welcomeMuted")
        self.toolchain_label.setWordWrap(True)
        self.recent_list = QVBoxLayout()
        self.recent_list.setSpacing(4)
        self._action_buttons: list[QPushButton] = []
        self._card_widgets: list[QWidget] = []
        self._recent_buttons: list[QPushButton] = []
        self._recent_rows: tuple[tuple[Path, Path | None, str, str], ...] | None = None
        self._build()

    def set_toolchain_status(self, ready: bool, message: str) -> None:
        prefix = "LaTeX 环境就绪" if ready else "LaTeX 环境未就绪"
        self.toolchain_label.setText("LaTeX 环境就绪，可以开始写作" if ready else f"{prefix}：{message}")
        self.toolchain_label.setToolTip(message)
        self.environment_help.setVisible(not ready)
        self.recheck_button.setVisible(not ready)
        self.environment_button.setText("查看环境" if ready else "查看安装指引")
        set_dynamic_property(self.toolchain_label, "state", "ready" if ready else "warning")

    def set_recent_projects(self, paths: Sequence[Path], *, recent_files: Sequence[Path] = ()) -> None:
        """Rebuild only changed captions/targets, including recent names and path text."""
        rows = []
        for path in paths[:6]:
            recent = next((file for file in recent_files if file.is_relative_to(path)), None)
            short_path = str(Path("~") / path.relative_to(Path.home())) if path.is_relative_to(Path.home()) else str(path)
            if len(short_path) > 60:
                short_path = "…/" + "/".join(path.parts[-3:])
            label = path.name + (f" · 最近打开：{recent.name}" if recent else "")
            rows.append((path, recent, label, short_path))
        if tuple(rows) == self._recent_rows:
            return
        self._recent_rows = tuple(rows)
        self._recent_buttons.clear()
        _clear_layout(self.recent_list)
        if not rows:
            label = QLabel("暂无最近项目")
            label.setObjectName("welcomeMuted")
            self.recent_list.addWidget(label)
            return
        for path, recent, label, short_path in rows:
            button = QPushButton(f"{label}\n{short_path}")
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            button.setProperty("projectLabel", label)
            button.setProperty("projectPath", short_path)
            button.setAccessibleName(f"{label}，{path}")
            button.setObjectName("welcomeRecent")
            button.setIcon(icon("folder", size=16))
            button.setIconSize(QSize(16, 16))
            button.setToolTip(f"项目位置：{path}" + (f"\n最近打开：{recent}" if recent else ""))
            button.clicked.connect(lambda _checked=False, item=path: self.recentProjectRequested.emit(str(item)))
            self.recent_list.addWidget(button)
            self._recent_buttons.append(button)
        self._update_recent_labels()

    def _update_recent_labels(self) -> None:
        for button in self._recent_buttons:
            width = max(60, self.width() - 130)
            metrics = button.fontMetrics()
            button.setText("\n".join(metrics.elidedText(button.property(key), Qt.TextElideMode.ElideMiddle, width)
                                     for key in ("projectLabel", "projectPath")))

    def _build(self) -> None:
        content = QWidget()
        content.setObjectName("welcomeContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(18)
        self.cover = QLabel()
        self.cover.setObjectName("welcomeCover")
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.cover)

        title_column = QVBoxLayout()
        title_column.setSpacing(6)
        kicker = QLabel("ICC Student's TeX")
        kicker.setObjectName("welcomeKicker")
        title = QLabel("欢迎使用 ICSTeX")
        title.setObjectName("welcomeTitle")
        subtitle = QLabel("从模板开始，或打开已有 LaTeX 项目。")
        subtitle.setObjectName("welcomeSubtitle")
        subtitle.setWordWrap(True)
        title_column.addStretch()
        title_column.addWidget(kicker)
        title_column.addWidget(title)
        title_column.addWidget(subtitle)
        title_column.addStretch()
        header.addLayout(title_column, 1)
        layout.addLayout(header)

        self.action_grid = QGridLayout()
        self.action_grid.setSpacing(10)
        self.new_project_button = QPushButton("新建项目")
        self.new_project_button.setObjectName("primaryButton")
        self.new_project_button.setStyleSheet(PRIMARY_BUTTON_STATE_STYLE)
        self.open_file_button = QPushButton("打开 .tex")
        self.open_folder_button = QPushButton("打开项目文件夹")
        self.guide_button = QPushButton("新手导引")
        self.new_project_button.setIcon(icon("folder-plus", "#ffffff", 16))
        self.open_file_button.setIcon(icon("folder-open", size=16))
        self.open_folder_button.setIcon(icon("folder", size=16))
        self.guide_button.setIcon(icon("info", size=16))
        self._action_buttons = [
            self.new_project_button,
            self.open_file_button,
            self.open_folder_button,
            self.guide_button,
        ]
        for button in self._action_buttons:
            button.setIconSize(QSize(16, 16))
        layout.addLayout(self.action_grid)

        status_row = QHBoxLayout()
        status_row.addWidget(self.toolchain_label, 1)
        self.environment_button = QPushButton("查看环境")
        self.environment_button.clicked.connect(self.environmentRequested.emit)
        self.recheck_button = QPushButton("重新检测")
        self.recheck_button.clicked.connect(self.recheckRequested.emit)
        status_row.addWidget(self.environment_button)
        status_row.addWidget(self.recheck_button)
        layout.addLayout(status_row)
        self.environment_help = QLabel("可以先创建和编辑项目；生成 PDF 前请安装 LaTeX 工具。安装后点击“重新检测”。")
        self.environment_help.setWordWrap(True)
        self.environment_help.hide()
        self.recheck_button.hide()
        layout.addWidget(self.environment_help)
        recent_box = QFrame()
        recent_box.setObjectName("welcomeBox")
        recent_layout = QVBoxLayout(recent_box)
        recent_layout.setContentsMargins(14, 12, 14, 12)
        recent_title = QLabel("最近项目")
        recent_title.setObjectName("welcomeSectionTitle")
        recent_layout.addWidget(recent_title)
        recent_layout.addLayout(self.recent_list)
        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(12)
        self._card_widgets = [recent_box]
        layout.addLayout(self.cards_grid)
        layout.addStretch()

        self.scroll = QScrollArea()
        self.scroll.setObjectName("welcomeScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.scroll)

        self.new_project_button.clicked.connect(self.newProjectRequested.emit)
        self.open_file_button.clicked.connect(self.openFileRequested.emit)
        self.open_folder_button.clicked.connect(self.openFolderRequested.emit)
        self.guide_button.clicked.connect(self.guideRequested.emit)

        app = QApplication.instance()
        manager = getattr(app, "ui_scale_manager", None)
        if manager is not None:
            manager.scale_changed.connect(self._apply_metrics)
        self._apply_metrics()
        self._apply_layout_mode(resolve_layout_mode(self.contentsRect().width()))

    @Slot()
    def _apply_metrics(self) -> None:
        app = QApplication.instance()
        manager = getattr(app, "ui_scale_manager", None)
        metrics = manager.metrics if manager is not None else None
        from app.gui.theme.ui_metrics import UiMetrics

        metrics = metrics or UiMetrics(1.0)
        self.cover.setFixedSize(metrics.logo_size, metrics.logo_size)
        pixmap = QPixmap(str(app_cover_path()))
        if pixmap.isNull():
            self.cover.setText("ICSTeX")
        else:
            inner = max(8, metrics.logo_size - 6)
            self.cover.setPixmap(
                pixmap.scaled(
                    QSize(inner, inner),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        for button in self._action_buttons:
            update_button_minimum_size(button, metrics)
        self._update_recent_labels()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        mode = resolve_layout_mode(self.contentsRect().width())
        if mode != self._layout_mode:
            self._apply_layout_mode(mode)
        self._update_recent_labels()

    def _apply_layout_mode(self, mode: str) -> None:
        self._layout_mode = mode
        if mode == "wide":
            action_columns = 4
            card_columns = 1
        elif mode == "medium":
            action_columns = 2
            card_columns = 1
        else:
            action_columns = 1
            card_columns = 1
        layout_reflow(self, self.action_grid, self._action_buttons, action_columns)
        layout_reflow(self, self.cards_grid, self._card_widgets, card_columns)


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
