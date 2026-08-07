"""Block workspace integration into the main console.

Adds the Block navigation/inspector/diagnostics docks, a central Block
workspace page, and one shared ``ProjectSession``.  The PDF panel is a single
widget re-parented between the source page and the Block page, so there is
never a second preview system; all Block compiles go through the session's
single CompileManager and the result is registered in the main PDF state.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.project_repository import load_project
from app.core.paths import normalize_path
from app.gui.blocks.diagnostics_dock import BlockDiagnostics
from app.gui.blocks.inspector import BlockInspector
from app.gui.blocks.navigation_dock import BlockNavigationWidget
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.workspace_widget import BlockWorkspaceWidget
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
    loaded = load_project(Path(directory))
    session = ProjectSession(
        registry=loaded["registry"],
        layout=loaded["layout"],
        sources=loaded["sources"],
        document_theme=loaded["document_theme"],
        project_dir=loaded["project_dir"],
    )
    _install_session(window, session)
    _set_block_mode(window, True)


def _install_session(window, session: ProjectSession) -> None:
    _close_block_project(window)
    window.block_session = session

    workspace = BlockWorkspaceWidget(session)
    window.block_workspace = workspace
    workspace.preview_requested.connect(lambda: session.compile_final())
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

    session.compile_finished.connect(lambda result: _on_block_compile_finished(window, result))
    session.undo_stack.indexChanged.connect(lambda _index: _sync_block_undo_actions(window))
    _sync_block_undo_actions(window)

    # Central page: workspace + the shared PDF panel.
    pdf_panel = _detach_pdf_panel(window)
    window.block_pdf_wrapper = make_panel("Block PDF 预览", pdf_panel, "与源码页共享同一 PDF 面板")
    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(workspace)
    splitter.addWidget(window.block_pdf_wrapper)
    splitter.setStretchFactor(0, 60)
    splitter.setStretchFactor(1, 40)
    page = QWidget()
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.addWidget(splitter)
    window.block_page = page
    window.block_central_stack.addWidget(page)

    window.close_block_project_action.setEnabled(True)
    window.block_mode_action.setEnabled(True)


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
    root = normalize_path(result.root_file)
    if getattr(result, "ok", False) and getattr(result, "pdf_file", None) is not None:
        window.pdf_state.finish_build(
            root,
            result.build_id,
            result.outcome,
            pdf_file=result.pdf_file if result.ok else None,
            duration_seconds=result.duration_seconds,
            engine="XeLaTeX",
        )
        window.pdf_panel.load_pdf(result.pdf_file, logical_key=root)
        window.append_log(f"Block PDF 输出：{result.pdf_file}")
    else:
        window.pdf_state.finish_build(
            root,
            result.build_id,
            result.outcome,
            pdf_file=None,
            duration_seconds=result.duration_seconds,
            engine="XeLaTeX",
        )
        window.append_log(f"Block 编译失败：{result.outcome.value}")
    window._update_pdf_action_state()


def _set_block_mode(window, active: bool) -> None:
    window.block_mode_action.setChecked(active)
    window.block_nav_dock.setVisible(active)
    window.block_inspector_dock.setVisible(active)
    window.block_diagnostics_dock.setVisible(active)
    if window.block_central_stack.count() > 1:
        window.block_central_stack.setCurrentIndex(1 if active else 0)
    if window.block_session is not None:
        if active:
            _move_pdf_to(window, window.block_pdf_wrapper)
        else:
            _move_pdf_to(window, window.pdf_panel_wrapper)


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


def _close_block_project(window) -> None:
    session = window.block_session
    if session is not None:
        session.stop_compile()
        try:
            session.undo_stack.indexChanged.disconnect()
        except (RuntimeError, TypeError):
            pass
        try:
            session.compile_finished.disconnect()
        except (RuntimeError, TypeError):
            pass
        window.block_session = None
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
