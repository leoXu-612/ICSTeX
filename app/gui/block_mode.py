"""Block workspace integration into the main console.

Adds the Block navigation/inspector/diagnostics docks, a central Block
workspace page, and one shared ``ProjectSession``.  The PDF panel is a single
widget re-parented between the source page and the Block page. Block compiles
use the session's manager and independent result identity; they do not mutate
the ordinary-source PDF store.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QMessageBox,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.project_repository import load_project
from app.core.compiler import BuildPurpose
from app.core.project_dependencies import safe_project_input
from app.core.paths import normalize_path
from app.gui.blocks.diagnostics_dock import BlockDiagnostics
from app.gui.blocks.inspector import BlockInspector
from app.gui.blocks.navigation_dock import BlockNavigationWidget
from app.gui.blocks import profile
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.close_guard import compile_block_session, confirm_block_close, save_block_session
from app.gui.blocks.workspace_widget import BlockWorkspaceWidget, BlockPreviewArea
from app.gui.main_window_support import make_panel


def install_block_mode(window) -> None:
    """Wire docks, actions and the central Block page onto ``window``."""
    window.block_session = None
    window.block_nav_dock = QDockWidget("Block 导航", window)
    window.block_nav_dock.setObjectName("blockNavDock")
    window.block_nav_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, window.block_nav_dock)
    window.block_nav_dock.hide()

    window.block_inspector_dock = QDockWidget("Block 属性", window)
    window.block_inspector_dock.setObjectName("blockInspectorDock")
    window.block_inspector_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, window.block_inspector_dock)
    window.block_inspector_dock.hide()

    window.block_diagnostics_dock = QDockWidget("Block 诊断", window)
    window.block_diagnostics_dock.setObjectName("blockDiagnosticsDock")
    window.block_diagnostics_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, window.block_diagnostics_dock)
    window.block_diagnostics_dock.hide()

    window.block_central_stack = QStackedWidget(window)
    window.block_central_stack.addWidget(window.vertical_splitter)
    window.setCentralWidget(window.block_central_stack)
    window.block_page: QWidget | None = None
    window.block_pdf_wrapper = None

    window.open_block_project_action = QAction("打开 Block 项目到工作区…", window)
    window.open_block_project_action.triggered.connect(lambda: _open_block_project(window))
    window.close_block_project_action = QAction("关闭 Block 项目", window)
    window.close_block_project_action.triggered.connect(lambda: _close_block_project(window))
    window.block_save_action = QAction("保存 Block 项目", window)
    window.block_save_action.setShortcut("Ctrl+S")
    window.block_save_action.triggered.connect(lambda: save_block_session(window, window.block_session))
    window.block_save_action.setEnabled(False)
    window.block_compile_action = QAction("正式编译 Block 项目", window)
    window.block_compile_action.setShortcut("Ctrl+Return")
    window.block_compile_action.triggered.connect(lambda: compile_block_session(window, window.block_session))
    window.block_compile_action.setEnabled(False)
    window.block_stop_action = QAction("停止 Block 编译", window)
    window.block_stop_action.triggered.connect(lambda: window.block_session.stop_compile() if window.block_session else None)
    window.block_stop_action.setEnabled(False)
    toolbar = window.findChild(QToolBar, "mainToolbar")
    for action, source in ((window.block_save_action, window.save_action),
                           (window.block_compile_action, window.compile_action),
                           (window.block_stop_action, window.stop_compile_action)):
        action.setIcon(source.icon())
        action.setVisible(False)
        toolbar.insertAction(source, action)
    compile_button = toolbar.widgetForAction(window.block_compile_action)
    compile_button.setObjectName("primaryAction")
    compile_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    window.block_mode_action = QAction("Block 模式", window)
    window.block_mode_action.setCheckable(True)
    window.block_mode_action.triggered.connect(lambda checked: _set_block_mode(window, checked))
    window.block_undo_action = QAction("撤销 Block 操作", window)
    window.block_undo_action.setShortcut("Ctrl+Shift+Z")
    window.block_undo_action.triggered.connect(lambda: _undo_block(window))
    window.block_redo_action = QAction("重做 Block 操作", window)
    window.block_redo_action.setShortcut("Ctrl+Shift+Y")
    window.block_redo_action.triggered.connect(lambda: _redo_block(window))

    block_menu = window.menuBar().addMenu("Block")
    block_menu.addAction(window.open_block_project_action)
    block_menu.addAction(window.close_block_project_action)
    block_menu.addAction(window.block_save_action)
    block_menu.addAction(window.block_compile_action)
    block_menu.addAction(window.block_stop_action)
    block_menu.addSeparator()
    block_menu.addAction(window.block_mode_action)
    block_menu.addSeparator()
    block_menu.addAction(window.block_undo_action)
    block_menu.addAction(window.block_redo_action)

    window.block_undo_action.setEnabled(False)
    window.block_redo_action.setEnabled(False)
    window.close_block_project_action.setEnabled(False)
    window.block_mode_action.setEnabled(False)


def _open_block_project(window) -> None:
    directory = QFileDialog.getExistingDirectory(window, "选择 Block 项目目录")
    if not directory:
        return
    try:
        loaded = load_project(Path(directory))
        session = ProjectSession(**{key: loaded[key] for key in
            ("registry", "layout", "sources", "document_theme", "project_dir")})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        QMessageBox.warning(window, "Block 项目未打开", f"文件保留，无法安全读取项目：{exc}")
        return
    if _install_session(window, session):
        _set_block_mode(window, True)
    else:
        session.shutdown()


def _install_session(window, session: ProjectSession) -> bool:
    if not _close_block_project(window):
        return False
    window.block_session = session
    session.model_changed.connect(window.readiness.invalidate)
    session.save_completed.connect(window.readiness.invalidate)
    session.save_state_changed.connect(window.readiness.invalidate)
    session.save_state_changed.connect(lambda: sync_block_pdf(window))
    session.compile_requested.connect(window.readiness.invalidate)
    session.compile_finished.connect(window.readiness.invalidate)
    session.compile_state_changed.connect(window.readiness.invalidate)
    session.model_changed.connect(lambda _reason: sync_block_pdf(window))
    session.compile_state_changed.connect(lambda: sync_block_pdf(window))

    workspace = BlockWorkspaceWidget(session, show_compile_controls=False)
    window.block_workspace = workspace
    # Route layout edits (row/grid/reorder/inspector props) through the
    # session's global QUndoStack so Block-menu undo/redo covers them too.
    workspace.layout_panel.command_stack = session.undo_stack
    workspace.preview_requested.connect(lambda: compile_block_session(window, session))
    workspace.edit_requested.connect(lambda block_id: _open_block_editor(window, block_id))
    workspace.block_selected.connect(lambda block_id: session.selection.select_block(block_id, source="workspace"))
    workspace.layout_selected.connect(lambda slot_id: session.selection.select_slot(slot_id, source="workspace"))

    nav = BlockNavigationWidget(session)
    window.block_nav = nav
    nav.block_edit_requested.connect(lambda block_id: _open_block_editor(window, block_id))
    window.block_nav_dock.setWidget(nav)

    inspector = BlockInspector(session)
    inspector.set_layout_editor(workspace.layout_panel)
    inspector.set_workspace(workspace)
    window.block_inspector = inspector
    window.block_inspector_dock.setWidget(inspector)

    diagnostics = BlockDiagnostics(session)
    window.block_diagnostics = diagnostics
    window.block_diagnostics_dock.setWidget(diagnostics)
    diagnostics.error_seen.connect(lambda: window.block_diagnostics_dock.show())

    session.compile_finished.connect(lambda result: _on_block_compile_finished(window, result))
    session.undo_stack.indexChanged.connect(lambda _index: _sync_block_undo_actions(window))
    _sync_block_undo_actions(window)

    # Central page: workspace + the shared PDF panel.
    pdf_panel = _detach_pdf_panel(window)
    window.block_pdf_wrapper = make_panel("Block PDF 预览", pdf_panel, "与源码页共享同一 PDF 面板")
    window.block_preview_area = BlockPreviewArea(workspace, window.block_pdf_wrapper)
    page = QWidget()
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.addWidget(window.block_preview_area)
    window.block_page = page
    window._block_layout_initialized = False
    window.block_central_stack.addWidget(page)

    window.close_block_project_action.setEnabled(True)
    window.block_mode_action.setEnabled(True)
    return True


def _open_block_editor(window, block_id: str) -> None:
    session = window.block_session
    if session is None:
        return
    block = session.registry.get(block_id)
    if block is None:
        return
    session.selection.select_block(block_id, source="central_editor")
    workspace = window.block_workspace
    tab_index = {"table": 1, "formula": 2}.get(block.type, 0)
    workspace.tabs.setCurrentIndex(tab_index)


def _on_block_compile_finished(window, result) -> None:
    if window.block_session is None:
        return
    profile.log("DIAGNOSTICS_STARTED")
    profile.log("DIAGNOSTICS_FINISHED")
    if result.ok:
        window.append_log(f"Block PDF 输出：{result.pdf_file}")
    else:
        window.append_log(f"Block 编译失败：{result.outcome.value}")
    sync_block_pdf(window)


def sync_block_pdf(window) -> None:
    """Do not publish Block results into the ordinary-source PDF/export store."""
    session = window.block_session
    if session is None or not window.block_mode_action.isChecked():
        return
    busy = bool(session.compile_manager and session.compile_manager.is_busy)
    window.block_compile_action.setEnabled(session.project_dir is not None and not busy)
    window.block_stop_action.setEnabled(busy)
    result = session.last_result
    root = session.project_dir / "main.tex" if session.project_dir else None
    job = result.job_key if result else None
    current = bool(job and result.ok and job.root_file == root and job.source_revision == session._revision
                   and safe_project_input(session.project_dir, result.pdf_file, allow_internal=True))
    if current:
        marker = (id(session), result.build_id)
        if getattr(window, "_displayed_block_build", None) != marker or window.pdf_panel.current_pdf != result.pdf_file:
            window.pdf_panel.load_pdf(result.pdf_file, logical_key=root)
            window._displayed_block_build = marker
        purpose = "FINAL" if result.purpose is BuildPurpose.FINAL else "快速预览"
        window.pdf_panel.set_freshness(f"Block {purpose} 已生成 · 提交前请核对输入证据", "neutral")
        if session.editor_drafts:
            window.pdf_panel.set_freshness(f"Block {purpose} 仅对应已应用模型 · 不含待应用编辑草稿", "warning")
    else:
        window.pdf_panel.clear_pdf()
        window._displayed_block_build = None
        window.pdf_panel.set_freshness("Block 暂无当前模型的可用 PDF · 请正式编译", "warning")
    if session.final_is_running:
        window.pdf_panel.set_freshness("Block FINAL 编译中 · 旧显示不可作为当前提交", "neutral")
    # Until M5 provides Block delivery guards, never route these to a hidden source tab.
    for action in (window.export_pdf_action, window.reveal_pdf_action, window.sync_pdf_action):
        action.setEnabled(False)
    window.pdf_panel.export_pdf_button.setEnabled(False)
    window.pdf_panel.reveal_pdf_button.setEnabled(False)


def _set_block_mode(window, active: bool) -> None:
    window.block_mode_action.setChecked(active)
    window.readiness.mode_changed()
    window.block_nav_dock.setVisible(active)
    window.block_inspector_dock.setVisible(active)
    window.block_diagnostics_dock.setVisible(active)
    if active and not getattr(window, "_block_layout_initialized", False):
        from app.gui.theme.ui_metrics import UiMetrics
        from app.gui.theme.ui_scale_manager import refresh_window_metrics
        manager = getattr(QApplication.instance(), "ui_scale_manager", None)
        metrics = manager.metrics if manager is not None else UiMetrics()
        refresh_window_metrics(window, metrics)
        window.resizeDocks([window.block_nav_dock, window.block_inspector_dock],
                           [metrics.dock_min_width, metrics.inspector_min_width], Qt.Orientation.Horizontal)
        window.resizeDocks([window.block_diagnostics_dock], [round(140 * metrics.scale)], Qt.Orientation.Vertical)
        window._block_layout_initialized = True
    window.engine_toolbar_action.setVisible(not active)
    window.stop_compile_action.setVisible(not active)
    window.auto_compile_toolbar_action.setVisible(not active)
    window.auto_compile_action.setEnabled(not active)
    window.block_save_action.setEnabled(active and window.block_session is not None)
    for action in (window.block_save_action, window.block_compile_action, window.block_stop_action):
        action.setVisible(active)
    window.save_action.setVisible(not active)
    window.compile_action.setVisible(not active)
    if not active:
        window.block_compile_action.setEnabled(False)
        window.block_stop_action.setEnabled(False)
    for action in window.engine_actions.values():
        action.setEnabled(not active)
    if window.block_central_stack.count() > 1:
        window.block_central_stack.setCurrentIndex(1 if active else 0)
    if window.block_session is not None:
        if active:
            _move_pdf_to(window, window.block_pdf_wrapper)
        else:
            _move_pdf_to(window, window.pdf_panel_wrapper)
    if active:
        sync_block_pdf(window)
    else:
        window._sync_pdf_panel_to_active_root()
    window.update_document_view_state()
    if active:
        window.stop_compile_action.setEnabled(False)
    if hasattr(window, "workspace"):
        window.workspace.refresh()


def _detach_pdf_panel(window):
    panel = window.pdf_panel
    parent = panel.parentWidget()
    if parent is not None and parent.layout() is not None:
        parent.layout().removeWidget(panel)
    return panel


def _move_pdf_to(window, wrapper) -> None:
    if wrapper is None:
        return
    panel = _detach_pdf_panel(window)
    wrapper.layout().addWidget(panel)


def _undo_block(window) -> None:
    if window.block_session is not None:
        window.block_session.undo_stack.undo()


def _redo_block(window) -> None:
    if window.block_session is not None:
        window.block_session.undo_stack.redo()


def _sync_block_undo_actions(window) -> None:
    session = window.block_session
    if session is None:
        window.block_undo_action.setEnabled(False)
        window.block_redo_action.setEnabled(False)
        return
    window.block_undo_action.setEnabled(session.undo_stack.canUndo())
    window.block_redo_action.setEnabled(session.undo_stack.canRedo())


def _close_block_project(window, *, discard: bool = False) -> bool:
    """discard is for an already-confirmed choice (and synthetic test cleanup)."""
    session = window.block_session
    if session is not None:
        if not discard and not confirm_block_close(window, session):
            return False
        session.shutdown()
        for signal in (session.model_changed, session.save_completed, session.compile_requested,
                       session.compile_state_changed, session.save_state_changed):
            signal.disconnect(window.readiness.invalidate)
        try:
            session.undo_stack.indexChanged.disconnect()
        except (RuntimeError, TypeError):
            pass
        try:
            session.compile_finished.disconnect()
        except (RuntimeError, TypeError):
            pass
        window.block_session = None
        window.block_mode_action.setChecked(False)
        window.readiness.mode_changed()
        window.block_undo_action.setEnabled(False)
        window.block_redo_action.setEnabled(False)
        window.block_mode_action.setEnabled(False)
        window.close_block_project_action.setEnabled(False)
    if window.block_page is not None:
        window.block_central_stack.removeWidget(window.block_page)
        window.block_page.deleteLater()
        window.block_page = None
    for dock in (window.block_nav_dock, window.block_inspector_dock, window.block_diagnostics_dock):
        dock.setWidget(None)
        dock.hide()
    if window.block_pdf_wrapper is not None:
        _move_pdf_to(window, window.pdf_panel_wrapper)
        window.block_pdf_wrapper = None
    if window.block_central_stack.count() > 1:
        window.block_central_stack.setCurrentIndex(0)
    _set_block_mode(window, False)
    return True
