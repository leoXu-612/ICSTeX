"""Reusable Block workspace body extracted from ``BlockProjectDialog``.

The widget only renders and interacts; it receives one ``ProjectSession``,
emits selection/edit signals, and routes model changes through the session
(which owns save + the single CompileManager).  It never loads a project,
never writes JSON directly and never starts a compiler by itself.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSignalBlocker, Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QSplitter,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.export_package import export_package
from app.core.blocks.source_merge import MergeResult
from app.gui.blocks.formula_tab import FormulaBlockTab
from app.gui.blocks.layout_panel import BlockLayoutPanel
from app.gui.blocks.merge_dialog import MergeDialog
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.table_editor import TableEditor
from app.gui.blocks.theme_settings import ThemeSettings
from app.gui.responsive.helpers import ButtonFlowLayout, configure_tab_bar
from app.gui.insert_panel import scrollable_panel


class BlockPreviewArea(QWidget):
    """One editor/PDF pair: side by side when wide, explicit tabs when narrow.

    Narrow mode only hides one splitter child; widgets are never recreated or
    reparented by resizing, preserving editor focus and document/view state.
    """

    def __init__(self, editor, pdf):
        super().__init__()
        self.editor, self.pdf = editor, pdf
        self._compact = None
        self._show_pdf = False
        self.switcher = QWidget()
        self.switcher.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(self.switcher)
        row.setContentsMargins(0, 0, 0, 0)
        self.editor_button = QToolButton()
        self.editor_button.setText("编辑 Block")
        self.pdf_button = QToolButton()
        self.pdf_button.setText("查看 PDF")
        for button in (self.editor_button, self.pdf_button):
            button.setCheckable(True)
            row.addWidget(button)
        row.addStretch()
        self.editor_button.clicked.connect(lambda: self.select_pdf(False))
        self.pdf_button.clicked.connect(lambda: self.select_pdf(True))
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(editor)
        self.splitter.addWidget(pdf)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.switcher)
        layout.addWidget(self.splitter)
        self._arrange()

    def select_pdf(self, selected):
        self._show_pdf = selected
        self._arrange()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange) and hasattr(self, "splitter"):
            self._arrange()

    def _arrange(self):
        compact = self.width() < max(720, self.fontMetrics().horizontalAdvance("M") * 60)
        if compact and not self._compact:
            from PySide6.QtWidgets import QApplication
            focus = QApplication.focusWidget()
            if focus is not None and self.pdf.isAncestorOf(focus):
                self._show_pdf = True
            elif focus is not None and self.editor.isAncestorOf(focus):
                self._show_pdf = False
        self._compact = compact
        self.switcher.setVisible(compact)
        self.editor.setVisible(not compact or not self._show_pdf)
        self.pdf.setVisible(not compact or self._show_pdf)
        self.editor_button.setChecked(not self._show_pdf)
        self.pdf_button.setChecked(self._show_pdf)


class BlockWorkspaceWidget(QWidget):
    block_selected = Signal(str)
    layout_selected = Signal(str)
    source_selected = Signal(str)
    edit_requested = Signal(str)
    preview_requested = Signal()

    def __init__(self, session: ProjectSession, *, merge_result: MergeResult | None = None,
                 show_compile_controls: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.merge_result = merge_result
        self._selection_syncing = False
        self._table_refreshing = False
        self._table_view_state = {}
        self._shown_table_id = None
        self._live_cell_target = None

        self.layout_panel = BlockLayoutPanel(session.registry, session.layout)
        self.layout_panel.layoutChanged.connect(self._on_layout_changed)
        self.layout_panel.block_list.itemSelectionChanged.connect(self._on_block_selection_changed)
        self.layout_panel.slot_list.itemSelectionChanged.connect(self._on_slot_selection_changed)
        self.layout_panel.block_list.itemDoubleClicked.connect(lambda _item: self._emit_edit_requested())

        self.table_editor = TableEditor(session.table_model)
        self.table_editor.model_changed.connect(self._on_table_changed)
        self.table_editor.live_cell_changed.connect(self._on_live_cell)
        session.finish_editor_inputs.connect(self.table_editor.commit_pending_edit)
        self.formula_tab = FormulaBlockTab(session.registry, session=session)
        self.theme_settings = ThemeSettings(session.app_theme)

        tabs = QTabWidget(self)
        for widget, label in ((self.layout_panel, "布局"), (self._build_table_tab(), "表格"),
                              (self.formula_tab, "公式"), (self._build_sync_tab(), "同步"),
                              (self.theme_settings, "主题"), (self._build_export_tab(), "导出")):
            tabs.addTab(scrollable_panel(widget), label)
        configure_tab_bar(tabs)
        self.tabs = tabs

        self.preview_label = QLabel("尚未生成 PDF")
        self.preview_label.setWordWrap(True)
        self.preview_button = QPushButton("正式编译")
        self.preview_button.clicked.connect(self.preview_requested)
        self.stop_button = QPushButton("停止编译")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(session.stop_compile)
        preview_row = ButtonFlowLayout()
        preview_row.addWidget(self.preview_button)
        preview_row.addWidget(self.stop_button)

        self.compile_controls = QWidget()
        self.compile_controls.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        controls = QVBoxLayout(self.compile_controls)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addLayout(preview_row)
        controls.addWidget(self.preview_label)
        self.compile_controls.setVisible(show_compile_controls)
        layout = QVBoxLayout(self)
        layout.addWidget(self.compile_controls)
        layout.addWidget(tabs)

        session.compile_finished.connect(self._on_compile_finished)
        session.compile_state_changed.connect(self._compile_controls)
        session.model_changed.connect(self._refresh_model)
        session.editor_drafts_changed.connect(self._refresh_table)
        session.selection.selection_changed.connect(self._on_session_selection)
        self._refresh_table()

    # --- signal sources --------------------------------------------------

    def _refresh_model(self, _reason):
        self.table_editor.commit_pending_edit()
        self.layout_panel.refresh_block_list()
        if self.layout_panel.layout != self.session.layout:
            with QSignalBlocker(self.layout_panel):
                self.layout_panel.apply_layout_state(self.session.layout)
        self._refresh_table()

    def _build_table_tab(self):
        body = QWidget()
        layout = QVBoxLayout(body)
        self.table_selector = QComboBox()
        self.table_selector.setAccessibleName("当前编辑的表格 Block")
        self.table_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.table_selector.setMinimumContentsLength(12)
        self.table_selector.currentIndexChanged.connect(self._choose_table)
        self.table_draft_status = QLabel()
        self.table_draft_status.setWordWrap(True)
        self.table_draft_status.setTextFormat(Qt.TextFormat.PlainText)
        self.table_apply_button = QPushButton("应用此表格草稿")
        self.table_discard_button = QPushButton("放弃此表格草稿…")
        self.table_apply_button.clicked.connect(self._apply_table)
        self.table_discard_button.clicked.connect(self._discard_table)
        buttons = ButtonFlowLayout()
        buttons.addWidget(self.table_apply_button)
        buttons.addWidget(self.table_discard_button)
        layout.addWidget(self.table_selector)
        layout.addWidget(self.table_draft_status)
        layout.addLayout(buttons)
        layout.addWidget(self.table_editor)
        return body

    def _refresh_table(self):
        if self._table_refreshing or self.session._closed:
            return
        if self.table_editor._cell_editor is not None:
            # Live text is a small, session-visible marker. Do not rebuild a
            # full table or replace the delegate on each keystroke.
            self.table_draft_status.setText("正在编辑单元格；输入保留在草稿中，不会自动保存或编译。")
            return
        self._table_refreshing = True
        try:
            target = self.session.table_target_id
            model = self.session.ensure_table_model()
            if model is not self.table_editor.model:
                grid = self.table_editor.table
                if self._shown_table_id is not None:
                    self._table_view_state[self._shown_table_id] = (grid.currentRow(), grid.currentColumn(),
                        grid.horizontalScrollBar().value(), grid.verticalScrollBar().value())
                self.table_editor.model = model
                self.table_editor.refresh()
                row, col, x, y = self._table_view_state.get(target, (0, 0, 0, 0))
                if grid.rowCount() and grid.columnCount():
                    grid.setCurrentCell(max(0, min(row, grid.rowCount() - 1)), max(0, min(col, grid.columnCount() - 1)))
                grid.horizontalScrollBar().setValue(x)
                grid.verticalScrollBar().setValue(y)
            self._shown_table_id = target
            self._table_view_state = {key: value for key, value in self._table_view_state.items()
                if key == target or ("table", key) in self.session.editor_drafts}
            with QSignalBlocker(self.table_selector):
                self.table_selector.clear()
                self.table_selector.addItem("请选择表格", None)
                seen = set()
                for block in self.session.registry.blocks():
                    if block.type == "table":
                        self.table_selector.addItem(block.alias, block.id)
                        seen.add(block.id)
                for draft in self.session.editor_drafts.values():
                    if draft.kind == "table" and draft.target_id not in seen:
                        self.table_selector.addItem(draft.label + "（原对象不可用）", draft.target_id)
                self.table_selector.setCurrentIndex(max(0, self.table_selector.findData(target)))
            pending = ("table", target) in self.session.editor_drafts
            self.table_editor.setEnabled(self.session._table_model_source_valid)
            self.table_draft_status.setText(self.session.table_error or
                ("此表格有未应用草稿；切换会保留，应用后才进入项目模型。" if pending
                 else "此表格与已应用模型一致；单元格和行列编辑先保留为草稿。"))
            self.table_apply_button.setEnabled(pending)
            self.table_discard_button.setEnabled(pending)
        finally:
            self._table_refreshing = False

    def open_table(self, block_id):
        self.table_editor.commit_pending_edit()
        self.session.table_target_id = block_id
        self._refresh_table()
        self.tabs.setCurrentIndex(1)
        cell = self.session.editor_drafts.get(("table_cell", block_id))
        if cell is not None:
            from app.core.blocks.property_draft import draft_conflict
            if (draft_conflict(cell, self.session.registry, self.session.layout)
                    or not self.table_editor.resume_cell_draft(cell.initial, cell.values)):
                self.table_draft_status.setText("恢复单元格的原对象或位置不一致；原草稿仍保留，请在恢复审阅中比较。")

    def _choose_table(self, index):
        target = self.table_selector.itemData(index)
        self.open_table(target)
        if target is not None:
            self.session.selection.select_block(target, source="table-editor")

    def _apply_table(self):
        target = self._shown_table_id
        self.table_editor.commit_pending_edit()
        self.session.apply_editor_drafts((("table", target),))

    def _discard_table(self):
        self.table_editor.commit_pending_edit()
        key = ("table", self.session.table_target_id)
        draft = self.session.editor_drafts.get(key)
        if draft is None:
            return
        choice = QMessageBox.warning(self, "放弃表格草稿", "仅放弃此表格尚未应用的单元格和行列修改；已应用模型与文件不变。",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if choice == QMessageBox.StandardButton.Discard and self.session.editor_drafts.get(key) == draft:
            self.session.discard_editor_draft(key)

    def _compile_controls(self):
        running = bool(self.session.compile_manager and self.session.compile_manager.is_busy)
        self.stop_button.setEnabled(running)

    def _on_layout_changed(self) -> None:
        self.session.set_layout(self.layout_panel.layout, reason="layout_changed")

    def _on_block_selection_changed(self) -> None:
        selected = self.layout_panel.selected_block_ids()
        if selected:
            self.block_selected.emit(selected[0])

    def _on_slot_selection_changed(self) -> None:
        items = self.layout_panel.slot_list.selectedItems()
        if items:
            instance_id = items[0].text().split(" -> ")[0]
            self.layout_selected.emit(instance_id)

    def _emit_edit_requested(self) -> None:
        selected = self.layout_panel.selected_block_ids()
        if selected:
            self.edit_requested.emit(selected[0])

    def _on_table_changed(self) -> None:
        self.session.table_edited(self._shown_table_id, self.table_editor.model)

    def _on_live_cell(self, payload):
        if payload is not None:
            self._live_cell_target = self._shown_table_id
        target = self._live_cell_target
        if target is not None:
            self.session.table_cell_edited(target, payload)
        if payload is None:
            self._live_cell_target = None
            self._refresh_table()

    def _on_session_selection(self, context, source: str) -> None:
        block = self.session.registry.get(context.block_id) if context.block_id else None
        if block is not None and block.type == "table":
            self.table_editor.commit_pending_edit()
            self.session.table_target_id = block.id
            self._refresh_table()
        if source == "workspace" or self._selection_syncing:
            return
        if context.block_id is None:
            return
        self._selection_syncing = True
        try:
            for index in range(self.layout_panel.block_list.count()):
                item = self.layout_panel.block_list.item(index)
                item.setSelected(item.data(256) == context.block_id)
        finally:
            self._selection_syncing = False

    def _on_compile_finished(self, result: object) -> None:
        pdf = getattr(result, "pdf_file", None)
        if pdf is not None and Path(pdf).exists():
            self.preview_label.setText(f"已更新：{Path(pdf).name}")
        elif result is not None and not getattr(result, "ok", False):
            self.preview_label.setText("编译失败：查看日志")

    # --- secondary tabs --------------------------------------------------
    def _build_sync_tab(self) -> QWidget:
        widget = QWidget()
        box = QVBoxLayout(widget)
        count = (len(self.merge_result.conflicts) + int(self.merge_result.table_conflict is not None)) if self.merge_result else 0
        label = QLabel(f"待确认候选：冲突 {count} 处；尚未应用到项目。" if self.merge_result else
                       "尚无绑定来源基线的合并候选；来源状态检查不会修改表格。")
        label.setWordWrap(True)
        box.addWidget(label)
        resolve = QPushButton("预览合并候选…")
        resolve.setEnabled(self.merge_result is not None)

        def open_resolver() -> None:
            if self.merge_result is None:
                return
            dialog = MergeDialog(self.merge_result, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.merge_result = dialog.result
                label.setText("候选已确认；尚未应用到项目、保存或推进来源基线。")

        resolve.clicked.connect(open_resolver)
        box.addWidget(resolve)
        box.addStretch()
        return widget

    def _build_export_tab(self) -> QWidget:
        widget = QWidget()
        box = QVBoxLayout(widget)
        box.addWidget(QLabel(f"项目目录：{self.session.project_dir or '（未指定）'}"))
        button = QPushButton("导出可移植包…")

        def do_export() -> None:
            if self.session.project_dir is None:
                return
            target = QFileDialog.getExistingDirectory(self, "选择导出目标目录")
            if not target:
                return
            result = export_package(self.session.project_dir, Path(target) / (self.session.project_dir.name + "-export"))
            QMessageBox.information(self, "导出完成", f"已导出 {len(result.files)} 个文件。")

        button.clicked.connect(do_export)
        box.addWidget(button)
        box.addStretch()
        return widget
