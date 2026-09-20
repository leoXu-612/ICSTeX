"""Construct the MainWindow's central widget tree: sidebar dock, splitters,
source/PDF panes, bottom log/error/wordcount/diagnostics tabs, and status bar.

Same shape as ``main_window_actions.build_actions``: mutates the host window in
place rather than returning anything. Every attribute it assigns is referenced
elsewhere by ``MainWindow`` instance methods.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Slot
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

from app.core.project_file_ops import PROJECT_FILE_FILTERS
from app.gui.diagnostics_panel import DiagnosticsPanel
from app.gui.submission_check_panel import SubmissionCheckPanel
from app.gui.find_replace import FindReplaceBar
from app.gui.icons import icon
from app.gui.insert_panel import InsertPanel, TemplatesPanel, scrollable_panel
from app.gui.main_window_actions import auto_compile_tooltip, auto_compile_label, build_actions
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
from app.gui.responsive.helpers import configure_tab_bar
from app.gui.responsive.editor_pdf_area import EditorPdfArea
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
    window.status_auto_label = QLabel(auto_compile_label(window.preferences.fast_preview) if window.preferences.auto_compile else "手动编译")
    window.status_auto_label.setObjectName("statusPill")
    window.status_auto_label.setToolTip(auto_compile_tooltip(window.preferences.fast_preview))
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
    window.model.setNameFilters(list(PROJECT_FILE_FILTERS))
    window.model.setNameFilterDisables(False)
    window.model.setReadOnly(True)
    home_index = window.model.setRootPath(str(Path.home()))

    window.tree = QTreeView()
    window.tree.setModel(window.model)
    window.tree.setRootIndex(home_index)
    window.tree.setAccessibleName("项目文件")
    window.tree.setHeaderHidden(True)
    window.tree.setAlternatingRowColors(True)
    window.tree.setUniformRowHeights(True)
    window.tree.setAnimated(False)
    window.tree.setDragEnabled(True)
    window.tree.setAcceptDrops(False)
    window.tree.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
    window.tree.setDefaultDropAction(Qt.DropAction.CopyAction)
    window.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.tree.setToolTip("双击打开 .tex；右键可在新窗口打开、重命名或移动；图片可拖入编辑器。")
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

    sidebar = ToolboxNavigation(window)
    sidebar.setMinimumWidth(320)
    sidebar.addTab(window.tree, "文件", "files", SIDEBAR_TAB_TIPS[0])
    sidebar.addTab(window.outline_panel, "大纲", "list-tree", SIDEBAR_TAB_TIPS[1])
    sidebar.addTab(window.search_panel, "搜索", "search", SIDEBAR_TAB_TIPS[2])
    sidebar.addTab(scrollable_panel(window.images_panel), "图片", "image", SIDEBAR_TAB_TIPS[3])
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
    configure_tab_bar(window.editor_tabs)

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
    window.pdf_panel = PdfPanel(search_action=window.pdf_search_action)
    window.pdf_panel.compileRequested.connect(lambda: (
        window.block_compile_action if window.block_mode_action.isChecked()
        and window.block_session is not None else window.compile_action).trigger())


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
    source_panel = window._source_body
    pdf_panel = QWidget()
    pdf_layout = QVBoxLayout(pdf_panel)
    pdf_layout.setContentsMargins(0, 0, 0, 0)
    pdf_layout.addWidget(window.pdf_panel)
    # Use content-derived minimum hints: fixed 430 + 360 widths overlap when
    # the toolbox is open in the supported 1080px window.
    window.pdf_panel_wrapper = pdf_panel

    area = EditorPdfArea(source_panel, pdf_panel, editor_label="编辑源码",
                         compact_width=960, compact_columns=90, wide_sizes=(790, 650))
    splitter = area.splitter
    splitter.setChildrenCollapsible(False)
    splitter.setHandleWidth(8)
    splitter.setStretchFactor(0, 55)
    splitter.setStretchFactor(1, 45)
    window.main_splitter = splitter
    window.source_preview_area = area
    area.set_preview_available(False)
    window.pdf_panel.availabilityChanged.connect(area.set_preview_available)
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
    table.setTabKeyNavigation(False)
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
    window.word_count_view.refreshRequested.connect(lambda: window.update_word_count(force=True))
    window.word_count_labels = window.word_count_view.labels
    window.word_count_meta = window.word_count_view.meta_label
    window.word_count_button = window.word_count_view.refresh_button
    window.word_count_panel = wrap_word_count_in_scroll(window.word_count_view)


class _ConsoleTabs(QTabWidget):
    """Keep an expanded console usable after tab/scale/window changes."""

    def __init__(self) -> None:
        super().__init__()
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.timeout.connect(self._reveal_content)
        self.currentChanged.connect(self._queue_layout)

    @Slot()
    def _queue_layout(self) -> None:
        self._layout_timer.start(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._queue_layout()

    @Slot()
    def _reveal_content(self) -> None:
        if not self.isVisible():
            return
        panel = self.parentWidget()
        splitter = panel.parentWidget() if panel is not None else None
        if not isinstance(splitter, QSplitter) or splitter.count() != 2:
            return
        sizes = splitter.sizes()
        needed = panel.minimumSizeHint().height()
        if sizes[1] < needed:
            splitter.setSizes([max(1, sum(sizes) - needed), needed])


def _install_bottom_tabs(window: "MainWindow") -> None:
    tabs = _ConsoleTabs()
    tabs.setObjectName("bottomTabs")
    configure_tab_bar(tabs)
    tabs.addTab(window.log_view, "日志")
    tabs.addTab(window.error_table, "错误")
    tabs.addTab(window.word_count_panel, "字数")
    window.diagnostic_panel = DiagnosticsPanel()
    tabs.addTab(window.diagnostic_panel, "检查")
    window.submission_panel = SubmissionCheckPanel()
    tabs.addTab(window.submission_panel, "提交检查")
    window.bottom_tabs = tabs


def _install_vertical_splitter(window: "MainWindow") -> None:
    collapse_button = QToolButton()
    collapse_button.setObjectName("consoleToggle")
    collapse_button.setDefaultAction(window.console_action)
    collapse_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    window.bottom_collapse_button = collapse_button
    window.statusBar().insertPermanentWidget(0, collapse_button)
    window.bottom_panel = QWidget()
    window.bottom_panel.setObjectName("panel")
    console_layout = QVBoxLayout(window.bottom_panel)
    console_layout.setContentsMargins(0, 0, 0, 0)
    console_layout.addWidget(window.bottom_tabs)
    splitter = QSplitter(Qt.Orientation.Vertical)
    splitter.setObjectName("verticalSplitter")
    splitter.setChildrenCollapsible(True)
    splitter.setHandleWidth(8)
    splitter.addWidget(window.source_preview_area)
    splitter.addWidget(window.bottom_panel)
    splitter.setCollapsible(0, False)
    splitter.setCollapsible(1, False)
    splitter.setStretchFactor(0, 5)
    splitter.setStretchFactor(1, 1)
    splitter.setSizes([690, 210])
    window.vertical_splitter = splitter
    window._bottom_panel_expanded_height = 210
    window.console_action.triggered.connect(lambda: _toggle_bottom_panel(window))
    window.bottom_tabs.currentChanged.connect(lambda _index: show_console(window))
    collapsed = window.app_settings.settings.value("window/console_collapsed", True, type=bool)
    _set_bottom_panel_collapsed(window, collapsed)
    window.setCentralWidget(splitter)


def _toggle_bottom_panel(window: "MainWindow") -> None:
    collapsed = not window.bottom_tabs.isHidden()
    window.source_panels.set_console(not collapsed)
    window.app_settings.settings.setValue("window/console_collapsed", collapsed)


def show_console(window: "MainWindow", page=None, *, error_notice=False) -> None:
    """Reveal requested diagnostics without focusing them or saving a preference."""
    if hasattr(window, "block_mode_action") and window.block_mode_action.isChecked():
        return
    if hasattr(window, "source_panels"):
        window.source_panels.set_console(True, page=page, error_notice=error_notice)
        return
    if page is not None:
        window.bottom_tabs.setCurrentWidget(page)
    _set_bottom_panel_collapsed(window, False)


def reveal_workspace_widget(window: "MainWindow", widget: QWidget) -> None:
    area = (window.block_preview_area if window.block_mode_action.isChecked()
            and window.block_session is not None else window.source_preview_area)
    if widget is area.pdf or area.pdf.isAncestorOf(widget):
        area.select_pdf(True)
    elif widget is area.editor or area.editor.isAncestorOf(widget):
        area.select_pdf(False)


def _set_bottom_panel_collapsed(window: "MainWindow", collapsed: bool) -> None:
    sizes = window.vertical_splitter.sizes()
    if len(sizes) != 2:
        return
    window.console_action.setChecked(not collapsed)
    window.console_action.setIcon(icon("chevron-up" if collapsed else "chevron-down", size=16))
    window.console_action.setToolTip(("展开" if collapsed else "收起") + "控制台：日志、错误、字数和检查")
    total = sum(sizes)
    if collapsed:
        if not window.bottom_tabs.isHidden():
            window._bottom_panel_expanded_height = max(120, sizes[1])
        window.bottom_tabs.hide()
        window.bottom_panel.hide()
        window.vertical_splitter.setSizes([max(1, total), 0])
    else:
        if not window.bottom_tabs.isHidden():
            return
        window.bottom_panel.setMaximumHeight(16777215)
        window.bottom_panel.show()
        window.bottom_tabs.show()
        restored = min(max(120, window._bottom_panel_expanded_height), max(120, total // 2))
        window.vertical_splitter.setSizes([max(1, total - restored), restored])
