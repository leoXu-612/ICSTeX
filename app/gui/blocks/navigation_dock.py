"""Blocks / Layout / Sources navigation dock for the main console."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QDragEnterEvent, QDropEvent
from app.core.blocks.model import BLOCK_TYPES
from app.core.blocks.asset_import import import_image, is_image_path
from app.core.blocks.source_registry import SourceRecord, check_source
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.workspace_controller import BlockWorkspaceController
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
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
        self.search_edit.textChanged.connect(self.refresh)
        self.type_filter = QComboBox()
        self.type_filter.addItem("全部类型", None)
        for block_type in BLOCK_TYPES:
            self.type_filter.addItem(block_type, block_type)
        self.type_filter.currentIndexChanged.connect(self.refresh)

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

        blocks_buttons = QHBoxLayout()
        for button in (self.new_button, self.text_ocr_button, self.duplicate_button, self.rename_button, self.delete_button):
            blocks_buttons.addWidget(button)
        blocks_buttons.addStretch()

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
        layout_buttons = QHBoxLayout()
        for button in (self.add_row_button, self.add_grid_button, self.delete_node_button):
            layout_buttons.addWidget(button)
        layout_buttons.addStretch()
        layout_tab = QWidget()
        layout_tab_layout = QVBoxLayout(layout_tab)
        layout_tab_layout.addWidget(self.layout_tree)
        layout_tab_layout.addLayout(layout_buttons)

        # --- Sources tab --------------------------------------------------
        self.sources_table = QTableWidget(0, 3)
        self.sources_table.setHorizontalHeaderLabels(["源", "状态", "相对路径"])
        self.sources_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sources_table.cellDoubleClicked.connect(self._on_source_activated)
        self.refresh_sources_button = QPushButton("刷新状态")
        self.refresh_sources_button.clicked.connect(self.refresh)
        self.resync_button = QPushButton("重新同步")
        self.resync_button.clicked.connect(self._resync_selected_source)
        sources_buttons = QHBoxLayout()
        sources_buttons.addWidget(self.refresh_sources_button)
        sources_buttons.addWidget(self.resync_button)
        sources_buttons.addStretch()
        sources_tab = QWidget()
        sources_layout = QVBoxLayout(sources_tab)
        sources_layout.addWidget(self.sources_table)
        sources_layout.addLayout(sources_buttons)

        self.tabs = QTabWidget()
        self.tabs.addTab(blocks_tab, "Blocks")
        self.tabs.addTab(layout_tab, "Layout")
        self.tabs.addTab(sources_tab, "Sources")
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
        if self.session.project_dir is None or not event.mimeData().hasUrls():
            event.ignore()
            return
        accepted = False
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if not is_image_path(path):
                continue
            relative = import_image(self.session.project_dir, path)
            item = self.block_list.itemAt(event.position().toPoint())
            block_id = item.data(256) if item is not None else None
            block = self.session.registry.get(block_id) if block_id else None
            if block is not None and block.type == "image":
                self.controller.update_block(
                    block.id,
                    {"content": {**block.content, "source": relative}},
                    text="替换图片",
                )
            else:
                self.controller.add_block("image", alias=path.stem, content={"source": relative})
            accepted = True
        if accepted:
            event.acceptProposedAction()
        else:
            event.ignore()

    # --- refresh ----------------------------------------------------------
    def refresh(self, *_args: object) -> None:
        self._refresh_blocks()
        self._refresh_layout()
        self._refresh_sources()

    def _refresh_blocks(self) -> None:
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
        self.sources_table.setRowCount(0)
        if self.session.project_dir is None:
            return
        for record in self.session.sources:
            status = check_source(self.session.project_dir, record)
            row = self.sources_table.rowCount()
            self.sources_table.insertRow(row)
            self.sources_table.setItem(row, 0, QTableWidgetItem(record.sourceId))
            self.sources_table.setItem(row, 1, QTableWidgetItem(status.state))
            self.sources_table.setItem(row, 2, QTableWidgetItem(status.relativePath))

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
        source_id = self.sources_table.item(row, 0).text()
        self.session.selection.select_source(source_id, source="navigation")
        self.source_selected.emit(source_id)

    def _resync_selected_source(self) -> None:
        if self.session.project_dir is None:
            return
        selected = self.sources_table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        source_id = self.sources_table.item(row, 0).text()
        record = next((s for s in self.session.sources if s.sourceId == source_id), None)
        if record is None:
            return
        from app.core.blocks.source_registry import hash_file, resolve_source_path

        try:
            path = resolve_source_path(self.session.project_dir, record)
        except ValueError:
            return
        if not path.is_file():
            return
        updated = SourceRecord(
            sourceId=record.sourceId,
            kind=record.kind,
            relativePath=record.relativePath,
            baseSha256=hash_file(path),
            createdAt=record.createdAt,
        )
        self.session.sources = [updated if s.sourceId == source_id else s for s in self.session.sources]
        self.session.request_save("source_resynced")
        self.refresh()

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
