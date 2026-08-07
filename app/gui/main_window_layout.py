"""Construct the MainWindow's central widget tree: sidebar dock, splitters,
source/PDF panes, bottom log/error/wordcount/diagnostics tabs, and status bar.

Same shape as ``main_window_actions.build_actions``: mutates the host window in
place rather than returning anything. Every attribute it assigns is referenced
elsewhere by ``MainWindow`` instance methods.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QFileSystemModel,
    QHeaderView,
    QLabel,
    QProgressBar,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from app.gui.diagnostics_panel import DiagnosticsPanel
from app.gui.find_replace import FindReplaceBar
from app.gui.icons import icon
from app.gui.insert_panel import InsertPanel, TemplatesPanel, scrollable_panel
from app.gui.main_window_actions import build_actions
from app.gui.block_mode import install_block_mode
from app.gui.main_window_support import make_panel, set_dynamic_property
from app.gui.pdf_panel import PdfPanel
from app.gui.project_panels import (
    HistoryPanel,
    ImagesPanel,
    LabelsPanel,
    OutlinePanel,
    ProjectSearchPanel,
    ReferencesPanel,
)
from app.gui.theme import log_font
from app.gui.toolbox_navigation import ToolboxNavigation
from app.gui.welcome_page import WelcomePage
from app.gui.word_count_view import WordCountView, wrap_in_scroll as wrap_word_count_in_scroll

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.gui.main_window import MainWindow


SIDEBAR_TAB_TIPS = (
    "项目文件",
    "章节大纲",
    "全项目搜索",
    "图片资源",
    "版本历史",
    "插入工具",
    "文档模板",
    "BibTeX 引用",
    "LaTeX 标签",
)


def build_ui(window: "MainWindow") -> None:
    _install_status_bar(window)
    build_actions(window)
    _install_file_tree(window)
    _install_sidebar(window)
    _install_source_pane(window)
    _install_pdf_pane(window)
    _install_toolbox_dock(window)
    _install_main_splitter(window)
    _install_log_and_errors(window)
    _install_word_count_panel(window)
    _install_bottom_tabs(window)
    _install_vertical_splitter(window)
    install_block_mode(window)


# --- subsections ----------------------------------------------------------

def _install_status_bar(window: "MainWindow") -> None:
    status_bar = QStatusBar(window)
    status_bar.setSizeGripEnabled(False)
    window.setStatusBar(status_bar)
    window.compile_progress = QProgressBar()
    window.compile_progress.setObjectName("compileProgress")
    window.compile_progress.setRange(0, 0)
    window.compile_progress.setFixedWidth(100)
    window.compile_progress.hide()
    window.status_engine_label = QLabel(window.current_engine.display_name)
    window.status_engine_label.setObjectName("statusPill")
    window.status_auto_label = QLabel("自动编译" if window.preferences.auto_compile else "手动编译")
    window.status_auto_label.setObjectName("statusPill")
    set_dynamic_property(window.status_auto_label, "state", "active" if window.preferences.auto_compile else "idle")
    window.compile_time_label = QLabel("空闲")
    window.compile_time_label.setObjectName("compileTimer")
    status_bar.addPermanentWidget(window.status_engine_label)
    status_bar.addPermanentWidget(window.status_auto_label)
    status_bar.addPermanentWidget(window.compile_progress)
    status_bar.addPermanentWidget(window.compile_time_label)
    window.compile_timer = QTimer(window)
    window.compile_timer.setInterval(100)
    window.compile_timer.timeout.connect(window.update_compile_timer)


def _install_file_tree(window: "MainWindow") -> None:
    window.model = QFileSystemModel(window)
    window.model.setNameFilters(["*.tex", "*.bib"])
    window.model.setNameFilterDisables(False)
    home_index = window.model.setRootPath(str(Path.home()))

    window.tree = QTreeView()
    window.tree.setModel(window.model)
    window.tree.setRootIndex(home_index)
    window.tree.setAccessibleName("项目文件")
    window.tree.setHeaderHidden(True)
    window.tree.setAlternatingRowColors(True)
    window.tree.setUniformRowHeights(True)
    window.tree.setAnimated(False)
    for column in range(1, window.model.columnCount()):
        window.tree.hideColumn(column)


def _install_sidebar(window: "MainWindow") -> None:
    window.insert_panel = InsertPanel()
    window.templates_panel = TemplatesPanel()
    window.outline_panel = OutlinePanel()
    window.search_panel = ProjectSearchPanel()
    window.images_panel = ImagesPanel()
    window.history_panel = HistoryPanel()
    window.references_panel = ReferencesPanel()
    window.labels_panel = LabelsPanel()

    sidebar = ToolboxNavigation()
    sidebar.setMinimumWidth(320)
    sidebar.addTab(window.tree, "文件", "files", SIDEBAR_TAB_TIPS[0])
    sidebar.addTab(window.outline_panel, "大纲", "list-tree", SIDEBAR_TAB_TIPS[1])
    sidebar.addTab(window.search_panel, "搜索", "search", SIDEBAR_TAB_TIPS[2])
    sidebar.addTab(window.images_panel, "图片", "image", SIDEBAR_TAB_TIPS[3])
    sidebar.addTab(window.history_panel, "历史", "history", SIDEBAR_TAB_TIPS[4])
    sidebar.addTab(
        scrollable_panel(window.insert_panel), "插入", "square-plus", SIDEBAR_TAB_TIPS[5], section_break=True
    )
    sidebar.addTab(scrollable_panel(window.templates_panel), "模板", "layout-template", SIDEBAR_TAB_TIPS[6])
    sidebar.addTab(scrollable_panel(window.references_panel), "引用", "book-open", SIDEBAR_TAB_TIPS[7])
    sidebar.addTab(scrollable_panel(window.labels_panel), "标签", "tag", SIDEBAR_TAB_TIPS[8])
    sidebar.finish()
    for index, tip in enumerate(SIDEBAR_TAB_TIPS):
        sidebar.setTabToolTip(index, tip)
    window.sidebar_tabs = sidebar
    window.toolbox_navigation = sidebar


def _install_source_pane(window: "MainWindow") -> None:
    window.editor_tabs = QTabWidget()
    window.editor_tabs.setObjectName("sourceTabs")
    window.editor_tabs.setTabsClosable(True)
    window.editor_tabs.setDocumentMode(True)

    window.find_replace_bar = FindReplaceBar()
    window.welcome_page = WelcomePage()
    window.source_stack = QStackedWidget()
    window.source_stack.addWidget(window.welcome_page)
    window.source_stack.addWidget(window.editor_tabs)

    source_body = QWidget()
    source_body.setObjectName("sourceBody")
    source_layout = QVBoxLayout(source_body)
    source_layout.setContentsMargins(0, 0, 0, 0)
    source_layout.setSpacing(0)
    source_layout.addWidget(window.find_replace_bar)
    source_layout.addWidget(window.source_stack)
    window._source_body = source_body  # used by _install_main_splitter


def _install_pdf_pane(window: "MainWindow") -> None:
    window.pdf_panel = PdfPanel()


def _install_toolbox_dock(window: "MainWindow") -> None:
    dock = QDockWidget("工具箱", window)
    dock.setObjectName("toolboxDock")
    dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
    dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
    dock.setMinimumWidth(320)
    dock.setWidget(window.sidebar_tabs)
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
    dock.hide()
    window.toolbox_dock = dock
    dock.resize(340, dock.height())


def _install_main_splitter(window: "MainWindow") -> None:
    source_panel = make_panel("源码", window._source_body, "实时编译")
    source_panel.setMinimumWidth(430)
    pdf_panel = make_panel("PDF 预览", window.pdf_panel, "双击同步源码")
    pdf_panel.setMinimumWidth(360)
    window.pdf_panel_wrapper = pdf_panel

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setChildrenCollapsible(False)
    splitter.setHandleWidth(8)
    splitter.addWidget(source_panel)
    splitter.addWidget(pdf_panel)
    splitter.setStretchFactor(0, 55)
    splitter.setStretchFactor(1, 45)
    splitter.setSizes([790, 650])
    window.main_splitter = splitter
    del window._source_body


def _install_log_and_errors(window: "MainWindow") -> None:
    window.log_view = QTextEdit()
    window.log_view.setReadOnly(True)
    window.log_view.setFont(log_font())
    window._install_log_bridge()

    table = QTableWidget(0, 3)
    table.setHorizontalHeaderLabels(["文件", "行号", "信息"])
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(30)
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    window.error_table = table


def _install_word_count_panel(window: "MainWindow") -> None:
    window.word_count_view = WordCountView()
    window.word_count_view.refreshRequested.connect(window.update_word_count)
    window.word_count_labels = window.word_count_view.labels
    window.word_count_meta = window.word_count_view.meta_label
    window.word_count_button = window.word_count_view.refresh_button
    window.word_count_panel = wrap_word_count_in_scroll(window.word_count_view)


def _install_bottom_tabs(window: "MainWindow") -> None:
    tabs = QTabWidget()
    tabs.setObjectName("bottomTabs")
    tabs.addTab(window.log_view, "日志")
    tabs.addTab(window.error_table, "错误")
    tabs.addTab(window.word_count_panel, "字数")
    window.diagnostic_panel = DiagnosticsPanel()
    tabs.addTab(window.diagnostic_panel, "检查")
    window.bottom_tabs = tabs


def _install_vertical_splitter(window: "MainWindow") -> None:
    collapse_button = QToolButton()
    collapse_button.setObjectName("panelHeaderButton")
    collapse_button.setIcon(icon("chevron-down", size=16))
    collapse_button.setToolTip("收起编译控制台")
    collapse_button.setFixedSize(26, 26)
    window.bottom_collapse_button = collapse_button
    window.bottom_panel = make_panel(
        "编译控制台",
        window.bottom_tabs,
        "日志、错误、统计",
        actions=[collapse_button],
    )
    window.bottom_panel.setMinimumHeight(36)
    splitter = QSplitter(Qt.Orientation.Vertical)
    splitter.setObjectName("verticalSplitter")
    splitter.setChildrenCollapsible(True)
    splitter.setHandleWidth(8)
    splitter.addWidget(window.main_splitter)
    splitter.addWidget(window.bottom_panel)
    splitter.setCollapsible(0, False)
    splitter.setCollapsible(1, False)
    splitter.setStretchFactor(0, 5)
    splitter.setStretchFactor(1, 1)
    splitter.setSizes([690, 210])
    window.vertical_splitter = splitter
    window._bottom_panel_expanded_height = 210
    collapse_button.clicked.connect(lambda: _toggle_bottom_panel(window))
    window.setCentralWidget(splitter)


def _toggle_bottom_panel(window: "MainWindow") -> None:
    sizes = window.vertical_splitter.sizes()
    if len(sizes) != 2:
        return
    total = max(sum(sizes), window.height())
    if sizes[1] > 44:
        window._bottom_panel_expanded_height = max(120, sizes[1])
        window.vertical_splitter.setSizes([max(1, total - 36), 36])
        window.bottom_collapse_button.setIcon(icon("chevron-up", size=16))
        window.bottom_collapse_button.setToolTip("展开编译控制台")
    else:
        restored = min(max(120, window._bottom_panel_expanded_height), max(120, total // 2))
        window.vertical_splitter.setSizes([max(1, total - restored), restored])
        window.bottom_collapse_button.setIcon(icon("chevron-down", size=16))
        window.bottom_collapse_button.setToolTip("收起编译控制台")
