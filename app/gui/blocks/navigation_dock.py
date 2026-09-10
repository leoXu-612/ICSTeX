"""Blocks / Layout / Sources navigation dock for the main console."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtGui import QDragEnterEvent, QDropEvent
from app.core.blocks.model import BLOCK_TYPES
from app.core.blocks.asset_import import import_image, is_image_path
from app.core.blocks.source_registry import SourceCheckLimits
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.source_status import SourceStatusController
from app.gui.blocks.workspace_controller import BlockWorkspaceController
from app.gui.insert_panel import scrollable_panel
from app.gui.responsive.helpers import ButtonFlowLayout, configure_tab_bar
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _slot_block_ids(layout) -> set[str]:
    if layout is None:
        return set()
    if not hasattr(layout, "kind"):
        return {layout.blockId} if layout.blockId else set()
    result: set[str] = set()
    for child in layout.children:
        result |= _slot_block_ids(child)
    return result


class BlockNavigationWidget(QWidget):
    """Left-side navigation: Blocks / Layout / Sources tabs."""

    block_selected = Signal(str)
    block_edit_requested = Signal(str)
    slot_selected = Signal(str)
    source_selected = Signal(str)

    def __init__(self, session: ProjectSession, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.controller = BlockWorkspaceController(session)
        self._syncing = False

        # --- Blocks tab ---------------------------------------------------
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索 Block…")
        self.search_edit.textChanged.connect(self._refresh_blocks)
        self.type_filter = QComboBox()
        self.type_filter.addItem("全部类型", None)
        for block_type in BLOCK_TYPES:
            self.type_filter.addItem(block_type, block_type)
        self.type_filter.currentIndexChanged.connect(self._refresh_blocks)

        self.block_list = QListWidget()
        self.block_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.block_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.block_list.setAcceptDrops(True)
        self.block_list.itemSelectionChanged.connect(self._on_block_selection)
        self.block_list.itemDoubleClicked.connect(lambda _item: self._emit_edit())

        new_menu = QMenu(self)
        for block_type in BLOCK_TYPES:
            new_menu.addAction(block_type, lambda _checked=False, t=block_type: self.controller.add_block(t))
        self.new_button = QPushButton("新建 Block")
        self.new_button.setMenu(new_menu)
        self.text_ocr_button = QPushButton("文字识别…")
        self.text_ocr_button.setToolTip("RapidOCR 文字识别暂未纳入 2.1 Beta 1，将在后续 Beta 开放")
        self.text_ocr_button.setEnabled(False)
        self.text_ocr_button.clicked.connect(self._run_text_ocr)
        self.delete_button = QPushButton("删除")
        self.delete_button.clicked.connect(self._delete_selected)
        self.duplicate_button = QPushButton("复制")
        self.duplicate_button.clicked.connect(self._duplicate_selected)
        self.rename_button = QPushButton("重命名")
        self.rename_button.clicked.connect(self._rename_selected)

        blocks_buttons = ButtonFlowLayout()
        for button in (self.new_button, self.text_ocr_button, self.duplicate_button, self.rename_button, self.delete_button):
            blocks_buttons.addWidget(button)

        blocks_tab = QWidget()
        blocks_layout = QVBoxLayout(blocks_tab)
        blocks_layout.addWidget(self.search_edit)
        blocks_layout.addWidget(self.type_filter)
        blocks_layout.addWidget(self.block_list)
        blocks_layout.addLayout(blocks_buttons)

        # --- Layout tab ---------------------------------------------------
        self.layout_tree = QTreeWidget()
        self.layout_tree.setHeaderHidden(True)
        self.layout_tree.itemSelectionChanged.connect(self._on_layout_selection)
        self.add_row_button = QPushButton("新增 Row")
        self.add_row_button.clicked.connect(lambda: self._add_container("row"))
        self.add_grid_button = QPushButton("新增 Grid")
        self.add_grid_button.clicked.connect(lambda: self._add_container("grid"))
        self.delete_node_button = QPushButton("删除容器/槽位")
        self.delete_node_button.clicked.connect(self._delete_layout_node)
        layout_buttons = ButtonFlowLayout()
        for button in (self.add_row_button, self.add_grid_button, self.delete_node_button):
            layout_buttons.addWidget(button)
        layout_tab = QWidget()
        layout_tab_layout = QVBoxLayout(layout_tab)
        layout_tab_layout.addWidget(self.layout_tree)
        layout_tab_layout.addLayout(layout_buttons)

        # --- Sources tab --------------------------------------------------
        self.source_status = SourceStatusController(session, self)
        self.sources_table = QTableWidget(0, 4)
        self.sources_table.setHorizontalHeaderLabels(["来源", "快照状态", "记录路径", "关联 Block"])
        self.sources_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sources_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.sources_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sources_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.sources_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.sources_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.sources_table.cellDoubleClicked.connect(self._on_source_activated)
        self.sources_table.itemSelectionChanged.connect(self._show_source_details)
        self.sources_summary = QLabel()
        self.sources_summary.setWordWrap(True)
        self.refresh_sources_button = QPushButton("刷新状态")
        self.refresh_sources_button.clicked.connect(self.source_status.request)
        self.cancel_sources_button = QPushButton("取消检查")
        self.cancel_sources_button.clicked.connect(self.source_status.cancel)
        sources_buttons = ButtonFlowLayout()
        sources_buttons.addWidget(self.refresh_sources_button)
        sources_buttons.addWidget(self.cancel_sources_button)
        self.repair_source_button = QPushButton("比较并合并来源…")
        self.repair_source_button.clicked.connect(self._repair_source)
        sources_buttons.addWidget(self.repair_source_button)
        self.source_details = QPlainTextEdit()
        self.source_details.setReadOnly(True)
        self.source_details.setMinimumHeight(100)
        self.affected_blocks = QListWidget()
        self.affected_blocks.itemActivated.connect(self._locate_source_block)
        self.locate_source_block_button = QPushButton("定位所选关联 Block")
        self.locate_source_block_button.clicked.connect(self._locate_source_block)
        sources_tab = QWidget()
        sources_layout = QVBoxLayout(sources_tab)
        sources_layout.addWidget(self.sources_summary)
        sources_layout.addWidget(self.sources_table)
        sources_layout.addLayout(sources_buttons)
        sources_layout.addWidget(self.source_details)
        sources_layout.addWidget(QLabel("关联 Block（文件关系不证明数据真实）："))
        sources_layout.addWidget(self.affected_blocks)
        sources_layout.addWidget(self.locate_source_block_button)
        self.source_status.changed.connect(self._refresh_sources)

        self.tabs = QTabWidget()
        self.tabs.addTab(scrollable_panel(blocks_tab), "Blocks")
        self.tabs.addTab(scrollable_panel(layout_tab), "Layout")
        self.tabs.addTab(scrollable_panel(sources_tab), "来源")
        configure_tab_bar(self.tabs)
        outer = QVBoxLayout(self)
        outer.addWidget(self.tabs)

        session.model_changed.connect(lambda _reason: self.refresh())
        session.selection.selection_changed.connect(self._on_session_selection)
        self.refresh()

    def _run_text_ocr(self) -> None:
        from app.gui.text_ocr.text_block_flow import run_text_block_ocr

        run_text_block_ocr(self, self.controller)
        self.refresh()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(
            is_image_path(Path(url.toLocalFile())) for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if self.session._closed or self.session.project_dir is None or not event.mimeData().hasUrls():
            event.ignore()
            return
        project = self.session.project_dir
        point = self.block_list.viewport().mapFrom(self, event.position().toPoint())
        item = self.block_list.itemAt(point)
        block_id = item.data(256) if item is not None else None
        block = self.session.registry.get(block_id) if block_id else None
        target_id = block_id if block is not None and block.type == "image" else None
        accepted = 0
        error = ""
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if not is_image_path(path):
                continue
            block = self.session.registry.get(target_id) if target_id else None
            base = deepcopy(block.to_dict()) if block is not None else None
            if self.session._closed or self.session.project_dir != project or (target_id and base is None):
                error = "原项目或图片对象已变化；未继续导入。"
                break
            try:
                relative = import_image(project, path)
            except (OSError, ValueError) as exc:
                error = f"{path.name} 导入失败，模型未修改：{exc}"
                break
            current = self.session.registry.get(target_id) if target_id else None
            if (self.session._closed or self.session.project_dir != project
                    or (target_id and (current is None or current.to_dict() != base))):
                error = "图片已复制，但原项目或对象已变化；保留导入文件，未覆盖模型。"
                break
            if target_id is not None:
                self.controller.update_block(
                    target_id,
                    {"content": {**base["content"], "source": relative}},
                    text="替换图片",
                )
            else:
                self.controller.add_block("image", alias=path.stem, content={"source": relative})
            accepted += 1
        if accepted:
            event.acceptProposedAction()
        else:
            event.ignore()
        if error and not self.session._closed:
            prefix = f"已导入 {accepted} 张；这些模型修改与素材保留。\n" if accepted else ""
            QMessageBox.warning(self, "图片导入未完成", prefix + error)

    # --- refresh ----------------------------------------------------------
    def refresh(self, *_args: object) -> None:
        self._refresh_blocks()
        self._refresh_layout()
        self._refresh_sources()

    def _refresh_blocks(self, *_args) -> None:
        query = self.search_edit.text().strip().lower()
        filter_type = self.type_filter.currentData()
        used = _slot_block_ids(self.session.layout)
        selected_ids = self._selected_block_ids()
        self.block_list.blockSignals(True)
        self.block_list.clear()
        for block in self.session.registry.blocks():
            if filter_type and block.type != filter_type:
                continue
            if query and query not in block.alias.lower() and query not in block.id.lower():
                continue
            marker = "" if block.id in used else "（未使用）"
            item = QListWidgetItem(f"{block.type}: {block.alias} {marker}")
            item.setData(256, block.id)
            item.setSelected(block.id in selected_ids)
            self.block_list.addItem(item)
        self.block_list.blockSignals(False)

    def _refresh_layout(self) -> None:
        self.layout_tree.blockSignals(True)
        self.layout_tree.clear()
        if self.session.layout is None:
            QTreeWidgetItem(self.layout_tree, ["（空布局）"])
        else:
            self._add_layout_node(None, self.session.layout)
            self.layout_tree.expandAll()
        self.layout_tree.blockSignals(False)

    def _add_layout_node(self, parent: QTreeWidgetItem | None, node) -> QTreeWidgetItem:
        if not hasattr(node, "kind"):
            item = QTreeWidgetItem(parent, [f"槽：{node.blockId}"])
            item.setData(0, 256, ("slot", node.instanceId))
            return item
        item = QTreeWidgetItem(parent, [f"{node.kind}: {node.id}"])
        item.setData(0, 256, ("node", node.id))
        for child in node.children:
            self._add_layout_node(item, child)
        return item

    def _refresh_sources(self) -> None:
        selected = self._selected_source_id()
        self.sources_table.blockSignals(True)
        self.sources_table.setRowCount(0)
        results = self.source_status.results
        usage = {}
        for block in self.session.registry.blocks():
            source_id = block.provenance.sourceId
            usage[source_id] = usage.get(source_id, 0) + 1
        for row, record in enumerate(self.session.sources):
            status = results[row] if row < len(results) else None
            self.sources_table.insertRow(row)
            self.sources_table.setItem(row, 0, QTableWidgetItem(record.sourceId))
            label = self._source_state_label(status.state) if status else "未知 / 待检查"
            self.sources_table.setItem(row, 1, QTableWidgetItem(label))
            self.sources_table.setItem(row, 2, QTableWidgetItem(record.relativePath))
            self.sources_table.setItem(row, 3, QTableWidgetItem(str(usage.get(record.sourceId, 0))))
            if selected == record.sourceId:
                self.sources_table.selectRow(row)
        self.sources_table.blockSignals(False)
        self.sources_summary.setText(self.source_status.message)
        self.cancel_sources_button.setEnabled(self.source_status.is_busy and not self.session._closed)
        self.refresh_sources_button.setEnabled(self.session.project_dir is not None and not self.session._closed)
        self._show_source_details()

    @staticmethod
    def _source_state_label(state):
        return {"ok": "与基线一致", "changed": "内容已变化", "missing": "记录路径缺失",
                "moved": "可能移动 / 同内容候选", "unsafe": "路径不安全", "unknown": "未知"}.get(state, "未知")

    def _selected_source_id(self):
        row = self.sources_table.currentRow()
        item = self.sources_table.item(row, 0)
        return item.text() if item is not None else None

    def _source_blocks(self, source_id):
        return [block for block in self.session.registry.blocks() if block.provenance.sourceId == source_id]

    def _show_source_details(self):
        self.affected_blocks.clear()
        self.locate_source_block_button.setEnabled(False)
        source_id = self._selected_source_id()
        self.repair_source_button.setEnabled(source_id is not None and not self.session._closed)
        index = next((i for i, record in enumerate(self.session.sources) if record.sourceId == source_id), None)
        if index is None:
            self.source_details.setPlainText("选择来源查看记录路径、摘要及关联对象；不会自动同步或修改数据。")
            return
        record = self.session.sources[index]
        results = self.source_status.results
        status = results[index] if index < len(results) else None
        limits = SourceCheckLimits()
        lines = [f"来源：{record.sourceId} ({record.kind})", f"记录路径：{record.relativePath}",
                 f"基线 SHA-256：{record.baseSha256}",
                 f"检查 SHA-256：{status.currentSha256 if status and status.currentSha256 else '未知'}",
                 f"状态：{self._source_state_label(status.state) if status else '待检查'}",
                 status.message if status else self.source_status.message]
        if status and status.relativePath != record.relativePath:
            lines.append(f"同内容候选：{status.relativePath}（未更新记录路径）")
        lines.extend(["仅比较磁盘文件和记录基线，不与表格编辑内容合并；检查记录不是冻结备份。",
                      "缺失候选仅查同扩展名 CSV/XLSX；排除链接、隐藏/内部目录、构建与依赖缓存。",
                      f"上限：{limits.max_records} 条来源、{limits.max_entries} 个目录条目、"
                      f"单文件 {limits.max_file_bytes // (1024 * 1024)} MiB、"
                      f"累计 {limits.max_total_bytes // (1024 * 1024)} MiB；超限或读取失败为未知。"])
        self.source_details.setPlainText("\n".join(lines))
        for block in self._source_blocks(source_id):
            item = QListWidgetItem(f"{block.alias or block.id} · {block.type} · {block.id}")
            item.setData(Qt.ItemDataRole.UserRole, block.id)
            self.affected_blocks.addItem(item)
        if self.affected_blocks.count():
            self.affected_blocks.setCurrentRow(0)
            self.locate_source_block_button.setEnabled(not self.session._closed)

    def _locate_source_block(self, *_args):
        item = self.affected_blocks.currentItem()
        if item is None or self.session._closed:
            return
        block_id = item.data(Qt.ItemDataRole.UserRole)
        block = self.session.registry.get(block_id)
        if block is None or block.provenance.sourceId != self._selected_source_id():
            self._show_source_details()
            return
        self.session.selection.select_block(block_id, source="source-status")
        self.block_selected.emit(block_id)

    def _repair_source(self):
        source_id = self._selected_source_id()
        if source_id is None or self.session._closed:
            return
        from app.gui.blocks.source_repair_dialog import run_source_repair
        if run_source_repair(self, self.session, source_id):
            self.sources_summary.setText("合并已应用到项目；一次全局 Undo 可撤销。保存状态见工作区；原始数据未改写。")

    # --- block actions ----------------------------------------------------
    def _selected_block_ids(self) -> list[str]:
        return [
            self.block_list.item(index).data(256)
            for index in range(self.block_list.count())
            if self.block_list.item(index).isSelected()
        ]

    def _on_block_selection(self) -> None:
        if self._syncing:
            return
        selected = self._selected_block_ids()
        if selected:
            self.session.selection.select_block(selected[0], source="navigation")
            self.block_selected.emit(selected[0])

    def _emit_edit(self) -> None:
        selected = self._selected_block_ids()
        if selected:
            self.block_edit_requested.emit(selected[0])

    def _delete_selected(self) -> None:
        for block_id in list(self._selected_block_ids()):
            try:
                self.controller.delete_block(block_id)
            except ValueError as exc:
                if self.window() is not None:
                    self.window().statusBar().showMessage(str(exc), 4000)

    def _duplicate_selected(self) -> None:
        for block_id in self._selected_block_ids():
            self.controller.duplicate_block(block_id)

    def _rename_selected(self) -> None:
        selected = self._selected_block_ids()
        if not selected:
            return
        block = self.session.registry.get(selected[0])
        if block is None:
            return
        alias, ok = QInputDialog.getText(self, "重命名 Block", "新名称：", text=block.alias)
        if ok and alias.strip():
            self.controller.rename_block(selected[0], alias.strip())

    # --- layout actions ---------------------------------------------------
    def _on_layout_selection(self) -> None:
        if self._syncing or not self.layout_tree.selectedItems():
            return
        item = self.layout_tree.selectedItems()[0]
        kind, identifier = item.data(0, 256)
        if kind == "slot":
            self.session.selection.select_slot(identifier, source="navigation")
            self.slot_selected.emit(identifier)
        else:
            self.session.selection.select_layout_node(identifier, source="navigation")

    def _add_container(self, kind: str) -> None:
        from app.core.blocks.layout import LayoutNode

        current = self.session.layout
        node = LayoutNode(
            id=f"lyt_{kind}",
            kind=kind,
            children=(current,) if current is not None else (),
        )
        self.session.set_layout(node, reason="layout_container_added")

    def _delete_layout_node(self) -> None:
        if not self.layout_tree.selectedItems():
            return
        item = self.layout_tree.selectedItems()[0]
        kind, identifier = item.data(0, 256)
        if self.session.layout is None:
            return
        if identifier == self.session.layout.id and kind == "node":
            self.session.set_layout(None, reason="layout_container_deleted")

    # --- sources ----------------------------------------------------------
    def _on_source_activated(self, row: int, _column: int) -> None:
        item = self.sources_table.item(row, 0)
        if item is None or self.session._closed:
            return
        source_id = item.text()
        self.session.selection.select_source(source_id, source="navigation")
        self.source_selected.emit(source_id)
        self._show_source_details()

    # --- session selection sync -------------------------------------------
    def _on_session_selection(self, context, source: str) -> None:
        if source == "navigation":
            return
        self._syncing = True
        try:
            if context.block_id:
                for index in range(self.block_list.count()):
                    item = self.block_list.item(index)
                    item.setSelected(item.data(256) == context.block_id)
        finally:
            self._syncing = False
