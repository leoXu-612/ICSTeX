"""Toolbar, menu, and QAction wiring for ``MainWindow``.

Kept as a free function rather than a mixin so it can be unit-tested with a
plain ``QMainWindow`` stub if needed. The function intentionally mutates the
window in-place; every attribute it assigns is referenced by other parts of
``MainWindow``.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import QComboBox, QToolBar

from app.core.latex_tools import LaTeXEngine
from app.gui.icons import icon
from app.gui.theme import PRIMARY_ACTION_FOCUS_STYLE
from app.gui.theme.ui_scale_manager import SCALE_TIERS, TIER_LABELS
from app.gui.widgets import AutoCompileToggle

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.gui.main_window import MainWindow

REPOSITORY_URL = "https://github.com/leoXu-612/ICSTeX"


def open_project_repository(window: "MainWindow") -> None:
    """Only open the repository after an explicit action; never submit a Star."""
    if not QDesktopServices.openUrl(QUrl(REPOSITORY_URL)):
        window.statusBar().showMessage(f"未能打开浏览器。请手动访问：{REPOSITORY_URL}", 15000)


def checked_action(parent, text: str) -> QAction:
    action = QAction(text, parent)
    action.setCheckable(True)
    action.setChecked(True)
    return action


def auto_compile_tooltip(fast_preview: bool) -> str:
    result = "生成快速预览" if fast_preview else "使用原图正式编译"
    return f"开启后，输入暂停并自动保存后{result}；关闭后只手动编译。"


def auto_compile_label(fast_preview: bool) -> str:
    return "自动快速预览" if fast_preview else "自动正式编译"


def build_actions(window: "MainWindow") -> None:
    """Build toolbar, menus, and per-action shortcuts on ``window``."""
    toolbar = QToolBar("主工具栏")
    toolbar.setObjectName("mainToolbar")
    toolbar.setMovable(False)
    toolbar.setIconSize(QSize(18, 18))
    toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    window.addToolBar(toolbar)

    window.new_project_action = QAction(icon("folder-plus"), "新建项目", window)
    window.project_profile_action = QAction("项目配置…", window)
    window.project_checkpoint_action = QAction("创建项目检查点…", window)
    window.restore_checkpoint_action = QAction("从检查点恢复为新目录…", window)
    window.recovery_drafts_action = QAction("审阅恢复副本并继续草稿…", window)
    window.write_recovery_action = QAction("审阅中断 Block 写入并恢复…", window)
    window.migrate_project_action = QAction("审阅并迁移到新副本…", window)
    window.prepare_submission_action = QAction("准备提交（PDF / 可选源码与报告）…", window)
    window.new_action = QAction(icon("file-plus-2"), "新建文档", window)
    window.open_file_action = QAction(icon("folder-open"), "打开文件", window)
    window.open_folder_action = QAction(icon("folder"), "打开文件夹", window)
    window.toolbox_action = QAction(icon("panel-left"), "工具箱", window)
    window.toolbox_action.setCheckable(True)
    window.save_action = QAction(icon("save"), "保存", window)
    window.save_action.setShortcut(QKeySequence.StandardKey.Save)
    window.save_as_action = QAction(icon("save"), "另存为", window)
    window.export_pdf_action = QAction(icon("save"), "导出 PDF", window)
    window.export_pdf_action.setToolTip("进入准备提交：单独保存和正式编译，核对固定输入后导出到新目录。")
    window.export_project_action = QAction("导出为工程文件…", window)
    window.export_project_action.setToolTip("整理源码、图片、表格和引用库为 ZIP，方便换设备或分享；无需先编译 PDF。")
    reveal_text = "在 Finder 中显示 PDF" if sys.platform == "darwin" else "在文件夹中显示 PDF"
    window.reveal_pdf_action = QAction(icon("folder-open"), reveal_text, window)
    window.pdf_search_action = QAction("搜索 PDF", window)
    window.compile_action = QAction(icon("play", "#ffffff"), "正式编译", window)
    window.compile_action.setToolTip("使用原图生成正式 PDF，适合检查排版和导出前核对；不会改变自动预览设置。")

    window.auto_compile_action = checked_action(window, "自动编译")
    window.auto_compile_action.setText(auto_compile_label(window.preferences.fast_preview))
    window.auto_compile_action.setChecked(window.preferences.auto_compile)
    window.auto_compile_action.setToolTip(auto_compile_tooltip(window.preferences.fast_preview))
    window.auto_compile_toggle = AutoCompileToggle()
    window.auto_compile_toggle.set_mode_text(window.auto_compile_action.text())
    window.auto_compile_toggle.setChecked(window.preferences.auto_compile)
    window.auto_compile_toggle.setToolTip(window.auto_compile_action.toolTip())

    window.stop_compile_action = QAction(icon("square"), "停止编译", window)
    window.stop_compile_action.setEnabled(False)
    window.clean_build_action = QAction(icon("trash-2"), "清理编译缓存", window)
    window.full_rebuild_action = QAction(icon("refresh-cw"), "完整编译", window)
    window.health_check_action = QAction(icon("circle-check"), "检查项目", window)
    window.submission_check_action = QAction("提交检查", window)
    window.submission_check_action.setShortcut(QKeySequence("Ctrl+Shift+J"))
    window.submission_check_action.setToolTip("只读检查保存、FINAL PDF、引用、资源与字数；不自动编译。")
    window.environment_doctor_action = QAction(icon("stethoscope"), "环境医生", window)
    window.feedback_bundle_action = QAction(icon("info"), "复制反馈包", window)
    window.feedback_bundle_action.setToolTip("复制环境、编译与项目诊断摘要，不包含论文正文。")
    window.import_perf_action = QAction("导入性能诊断", window)
    window.import_perf_action.setToolTip("查看最近图片导入事务的编译次数与各阶段耗时。")
    window.block_project_action = QAction("Block 项目（MVP）", window)
    window.block_project_action.setToolTip("打开 Block 模型化排版 MVP 控制台（布局/表格/同步/主题/导出）。")
    window.user_guide_action = QAction(icon("book-open"), "新手导引", window)
    window.console_action = QAction(icon("chevron-up"), "控制台", window)
    window.console_action.setCheckable(True)
    window.console_action.setToolTip("展开控制台：日志、错误、字数和检查")
    window.word_count_action = QAction(icon("calculator"), "字数统计", window)
    window.sync_pdf_action = QAction(icon("refresh-cw"), "同步 PDF", window)
    window.sync_pdf_action.setToolTip("把源码光标定位到当前最新的快速预览或正式 PDF；不会额外编译。")
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
    window.new_window_action.setShortcut(QKeySequence("Ctrl+Shift+N"))
    window.new_window_action.setToolTip("打开独立窗口（Ctrl+Shift+N）")
    for action, caption in ((window.new_project_action, "新建"), (window.open_file_action, "打开"),
                            (window.stop_compile_action, "停止"), (window.word_count_action, "字数"),
                            (window.sync_pdf_action, "定位 PDF")):
        action.setIconText(caption)

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
    toolbar.addAction(window.compile_action)
    toolbar.addAction(window.stop_compile_action)
    window.auto_compile_toolbar_action = toolbar.addWidget(window.auto_compile_toggle)
    window.engine_toolbar_action = toolbar.addWidget(window.engine_selector)
    window.engine_toolbar_action.setVisible(False)
    toolbar.addSeparator()
    for action in (window.toolbox_action, window.console_action, window.sync_pdf_action):
        toolbar.addAction(action)
    compile_button = toolbar.widgetForAction(window.compile_action)
    if compile_button:
        compile_button.setObjectName("primaryAction")
        compile_button.setStyleSheet(PRIMARY_ACTION_FOCUS_STYLE)
        compile_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        compile_button.style().unpolish(compile_button)
        compile_button.style().polish(compile_button)

    file_menu = window.menuBar().addMenu("文件")
    for action in (
        window.new_project_action,
        window.new_action,
        window.open_file_action,
        window.open_folder_action,
        window.project_profile_action,
        window.project_checkpoint_action,
        window.restore_checkpoint_action,
        window.recovery_drafts_action,
        window.write_recovery_action,
        window.migrate_project_action,
        window.prepare_submission_action,
        window.save_action,
        window.save_as_action,
        window.export_pdf_action,
        window.export_project_action,
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
    build_menu.addAction(window.submission_check_action)
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
    view_menu.addAction(window.console_action)
    view_menu.addAction(window.pdf_search_action)
    window.ui_scale_menu = view_menu.addMenu("UI Scale")
    window.ui_scale_actions = {}
    for tier in SCALE_TIERS:
        action = QAction(TIER_LABELS[tier], window)
        action.setCheckable(True)
        action.triggered.connect(lambda _checked=False, selected=tier: window.set_ui_scale(selected))
        window.ui_scale_menu.addAction(action)
        window.ui_scale_actions[tier] = action
    help_menu = window.menuBar().addMenu("帮助")
    help_menu.addAction(window.user_guide_action)
    window.app_update_action = QAction("软件更新…", window)
    window.app_update_action.setMenuRole(QAction.MenuRole.ApplicationSpecificRole)
    from app.gui.app_update_controller import application_updates
    window.app_update_action.triggered.connect(lambda: application_updates().show_dialog(window))
    help_menu.addAction(window.app_update_action)
    help_menu.addAction(window.environment_doctor_action)
    help_menu.addAction(window.feedback_bundle_action)
    help_menu.addAction(window.import_perf_action)
    help_menu.addAction(window.block_project_action)
    help_menu.addSeparator()
    window.support_project_action = QAction("在 GitHub 支持项目（Star）", window)
    window.support_project_action.setMenuRole(QAction.MenuRole.NoRole)
    window.support_project_action.setToolTip("打开 GitHub 仓库后可手动点 Star；完全自愿，不影响使用或更新。")
    window.support_project_action.triggered.connect(lambda: open_project_repository(window))
    help_menu.addAction(window.support_project_action)
    window.update_recent_menu()
