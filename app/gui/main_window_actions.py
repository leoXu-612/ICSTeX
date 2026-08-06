"""Toolbar, menu, and QAction wiring for ``MainWindow``.

Kept as a free function rather than a mixin so it can be unit-tested with a
plain ``QMainWindow`` stub if needed. The function intentionally mutates the
window in-place; every attribute it assigns is referenced by other parts of
``MainWindow``.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QComboBox, QToolBar

from app.core.latex_tools import LaTeXEngine
from app.gui.icons import icon
from app.gui.widgets import AutoCompileToggle

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.gui.main_window import MainWindow


def checked_action(parent, text: str) -> QAction:
    action = QAction(text, parent)
    action.setCheckable(True)
    action.setChecked(True)
    return action


def auto_compile_tooltip(fast_preview: bool) -> str:
    result = "生成快速预览" if fast_preview else "使用原图正式编译"
    return f"开启后，输入暂停并自动保存后{result}；关闭后只手动编译。"


def build_actions(window: "MainWindow") -> None:
    """Build toolbar, menus, and per-action shortcuts on ``window``."""
    toolbar = QToolBar("主工具栏")
    toolbar.setObjectName("mainToolbar")
    toolbar.setMovable(False)
    toolbar.setIconSize(QSize(18, 18))
    toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    window.addToolBar(toolbar)

    window.new_project_action = QAction(icon("folder-plus"), "新建项目", window)
    window.new_action = QAction(icon("file-plus-2"), "新建文档", window)
    window.open_file_action = QAction(icon("folder-open"), "打开文件", window)
    window.open_folder_action = QAction(icon("folder"), "打开文件夹", window)
    window.toolbox_action = QAction(icon("panel-left"), "工具箱", window)
    window.toolbox_action.setCheckable(True)
    window.save_action = QAction(icon("save"), "保存", window)
    window.save_as_action = QAction(icon("save"), "另存为", window)
    window.export_pdf_action = QAction(icon("save"), "导出 PDF", window)
    window.export_pdf_action.setToolTip("若当前仅有快速预览，将先用原图正式编译再导出。")
    reveal_text = "在 Finder 中显示 PDF" if sys.platform == "darwin" else "在文件夹中显示 PDF"
    window.reveal_pdf_action = QAction(icon("folder-open"), reveal_text, window)
    window.compile_action = QAction(icon("play", "#ffffff"), "编译", window)
    window.compile_action.setToolTip("使用原图执行正式编译。")

    window.auto_compile_action = checked_action(window, "自动编译")
    window.auto_compile_action.setChecked(window.preferences.auto_compile)
    window.auto_compile_action.setToolTip(auto_compile_tooltip(window.preferences.fast_preview))
    window.auto_compile_toggle = AutoCompileToggle()
    window.auto_compile_toggle.setChecked(window.preferences.auto_compile)
    window.auto_compile_toggle.setToolTip(window.auto_compile_action.toolTip())

    window.stop_compile_action = QAction(icon("square"), "停止编译", window)
    window.stop_compile_action.setEnabled(False)
    window.clean_build_action = QAction(icon("trash-2"), "清理编译缓存", window)
    window.full_rebuild_action = QAction(icon("refresh-cw"), "完整编译", window)
    window.health_check_action = QAction(icon("circle-check"), "检查项目", window)
    window.environment_doctor_action = QAction(icon("stethoscope"), "环境医生", window)
    window.feedback_bundle_action = QAction(icon("info"), "复制反馈包", window)
    window.feedback_bundle_action.setToolTip("复制环境、编译与项目诊断摘要，不包含论文正文。")
    window.import_perf_action = QAction("导入性能诊断", window)
    window.import_perf_action.setToolTip("查看最近图片导入事务的编译次数与各阶段耗时。")
    window.user_guide_action = QAction(icon("book-open"), "新手导引", window)
    window.word_count_action = QAction(icon("calculator"), "字数统计", window)
    window.sync_pdf_action = QAction(icon("refresh-cw"), "同步 PDF", window)
    window.new_window_action = QAction(icon("panels-top-left"), "新窗口", window)
    window.settings_action = QAction(icon("settings"), "设置", window)
    window.find_action = QAction("查找", window)
    window.replace_action = QAction("查找替换", window)
    window.formula_composer_action = QAction("编辑公式", window)
    window.formula_composer_action.setToolTip(
        "选中完整公式（$…$、\\(…\\)、\\[…\\]、equation 或 equation*）后打开公式编辑器。"
    )
    window.find_action.setShortcut(QKeySequence.StandardKey.Find)
    window.replace_action.setShortcut(QKeySequence("Ctrl+H"))
    window.settings_action.setShortcut(QKeySequence("Ctrl+,"))

    window.engine_selector = QComboBox()
    window.engine_selector.setObjectName("engineSelector")
    window.engine_selector.setAccessibleName("编译器")
    for engine in LaTeXEngine:
        window.engine_selector.addItem(engine.display_name, engine.value)
    engine_index = window.engine_selector.findData(window.current_engine.value)
    window.engine_selector.setCurrentIndex(max(engine_index, 0))

    for action in (window.new_project_action, window.open_file_action, window.save_action):
        toolbar.addAction(action)
    toolbar.addSeparator()
    toolbar.addAction(window.toolbox_action)
    toolbar.addSeparator()
    toolbar.addAction(window.compile_action)
    toolbar.addAction(window.stop_compile_action)
    toolbar.addWidget(window.auto_compile_toggle)
    toolbar.addWidget(window.engine_selector)
    toolbar.addSeparator()
    for action in (window.health_check_action, window.word_count_action, window.sync_pdf_action):
        toolbar.addAction(action)
    compile_button = toolbar.widgetForAction(window.compile_action)
    if compile_button:
        compile_button.setObjectName("primaryAction")
        compile_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        compile_button.style().unpolish(compile_button)
        compile_button.style().polish(compile_button)

    file_menu = window.menuBar().addMenu("文件")
    for action in (
        window.new_project_action,
        window.new_action,
        window.open_file_action,
        window.open_folder_action,
        window.save_action,
        window.save_as_action,
        window.export_pdf_action,
        window.reveal_pdf_action,
        window.new_window_action,
    ):
        file_menu.addAction(action)
    window.recent_menu = file_menu.addMenu("最近打开")
    file_menu.addSeparator()
    file_menu.addAction(window.settings_action)

    build_menu = window.menuBar().addMenu("编译")
    build_menu.addAction(window.compile_action)
    build_menu.addAction(window.stop_compile_action)
    build_menu.addAction(window.clean_build_action)
    build_menu.addAction(window.full_rebuild_action)
    build_menu.addAction(window.health_check_action)
    build_menu.addAction(window.environment_doctor_action)
    build_menu.addSeparator()
    build_menu.addAction(window.auto_compile_action)
    build_menu.addAction(window.word_count_action)
    build_menu.addAction(window.sync_pdf_action)
    window.engine_actions = {}
    engine_menu = build_menu.addMenu("编译器")
    for engine in LaTeXEngine:
        action = QAction(engine.display_name, window)
        action.setCheckable(True)
        action.setChecked(engine == window.current_engine)
        action.triggered.connect(lambda _checked=False, selected=engine: window.set_engine(selected))
        engine_menu.addAction(action)
        window.engine_actions[engine] = action

    window.auto_item_action = checked_action(window, "自动 \\item")
    window.auto_environment_action = checked_action(window, "自动补全环境")
    window.auto_pairs_action = checked_action(window, "自动配对括号")
    window.snippets_action = checked_action(window, "代码片段")
    window.auto_item_action.setChecked(window.preferences.auto_item)
    window.auto_environment_action.setChecked(window.preferences.auto_environment)
    window.auto_pairs_action.setChecked(window.preferences.auto_pairs)
    window.snippets_action.setChecked(window.preferences.snippets)

    edit_menu = window.menuBar().addMenu("编辑")
    edit_menu.addAction(window.find_action)
    edit_menu.addAction(window.replace_action)
    edit_menu.addSeparator()
    edit_menu.addAction(window.formula_composer_action)
    edit_menu.addSeparator()
    for action in (
        window.auto_item_action,
        window.auto_environment_action,
        window.auto_pairs_action,
        window.snippets_action,
    ):
        edit_menu.addAction(action)
    edit_menu.addSeparator()
    edit_menu.addAction(window.settings_action)
    view_menu = window.menuBar().addMenu("视图")
    view_menu.addAction(window.toolbox_action)
    help_menu = window.menuBar().addMenu("帮助")
    help_menu.addAction(window.user_guide_action)
    help_menu.addAction(window.environment_doctor_action)
    help_menu.addAction(window.feedback_bundle_action)
    help_menu.addAction(window.import_perf_action)
    window.update_recent_menu()
