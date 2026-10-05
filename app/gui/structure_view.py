"""Native, source-backed structure view. No second document or save path."""
from __future__ import annotations

import html
from bisect import bisect_right
import re
import threading
from pathlib import Path
from traceback import extract_tb

from PySide6.QtCore import QEvent, QObject, QRectF, QSignalBlocker, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QMessageBox,
    QLabel, QMenu, QSizePolicy, QStackedWidget, QStyle, QStyledItemDelegate,
    QTabBar, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)
from shiboken6 import isValid

from app.core.document_structure import (
    HEADINGS, SourceBlock, SourceEdit, Structure, delete_block, move_block, parse_structure,
)
from app.core.logging_config import get_logger
from app.core.text_positions import python_index_from_utf16, utf16_length
from app.gui.icons import icon
from app.gui.source_block_editor import SourceBlockEditor
from app.gui.theme import COLOR_ACCENT, COLOR_SELECTED, COLOR_TEXT, ui_font, heading_font


logger = get_logger(__name__)
ROLE = Qt.ItemDataRole.UserRole
LABELS = {"title": "文稿标题", "section": "章节", "text": "正文", "formula": "公式",
          "table": "表格", "image": "图片", "list": "列表", "raw": "自定义 LaTeX"}


class StructureBreadcrumb(QLabel):
    """Read-only path chips. Elision affects painting, never the accessible path."""
    def __init__(self):
        super().__init__()
        self._parts = ()
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setObjectName("structureBreadcrumb")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.set_path(("当前文件",))

    def text(self):
        return " › ".join(self._parts)

    def set_path(self, parts):
        parts = tuple(parts)
        if parts == self._parts:
            return
        self._parts = parts
        # Keep QLabel's native static-text interface even though chips are painted.
        super().setText(self.text())
        self.setToolTip(self.text())
        self.setAccessibleName("文稿路径：" + self.text())
        self.update()

    def sizeHint(self):
        return QSize(260, self.fontMetrics().height() + 12)

    def minimumSizeHint(self):
        return QSize(0, self.sizeHint().height())

    def _visible_parts(self):
        metrics = self.fontMetrics()
        labels = list(self._parts)
        available = max(0, self.width())
        gap = metrics.horizontalAdvance("›") + 12
        def width():
            return sum(min(140, metrics.horizontalAdvance(s) + 16) for s in labels) + gap * (len(labels) - 1)
        if len(labels) > 3 and width() > available:
            labels = [labels[0], "…", *labels[-2:]]
        while len(labels) > 2 and width() > available:
            labels.pop(1)
        last_width = min(available, metrics.horizontalAdvance(labels[-1]) + 16)
        if len(labels) > 1 and available - last_width - gap < 35:
            labels = [labels[-1]]
        remaining = max(0, available - last_width - gap * (len(labels) - 1))
        per_parent = remaining // max(1, len(labels) - 1)
        result = []
        for index, label in enumerate(labels):
            limit = last_width if index == len(labels) - 1 else min(140, per_parent)
            visible = metrics.elidedText(label, Qt.TextElideMode.ElideMiddle, max(0, limit - 16))
            result.append((visible, min(limit, metrics.horizontalAdvance(visible) + 16)))
        return result, gap

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self.rect())
        parts, gap = self._visible_parts()
        x = 0
        for index, (label, width) in enumerate(parts):
            current = index == len(parts) - 1
            rect = QRectF(x, 2, max(0, width - 1), max(0, self.height() - 4))
            painter.setPen(QColor(COLOR_ACCENT if current else "#d9ddd8"))
            painter.setBrush(QColor(COLOR_SELECTED if current else "#f0f2ef"))
            painter.drawRoundedRect(rect, 5, 5)
            painter.setPen(QColor(COLOR_ACCENT if current else COLOR_TEXT))
            painter.drawText(rect.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignCenter, label)
            x += width
            if not current:
                painter.setPen(QColor("#68726b"))
                painter.drawText(QRectF(x, 0, gap, self.height()), Qt.AlignmentFlag.AlignCenter, "›")
                x += gap


class _Signals(QObject):
    parsed = Signal(object, object)


def _parse_worker(key, source, signals, closed):
    """No GUI access; late results are accepted only by the current snapshot key."""
    try:
        snapshot = parse_structure(source)
    except Exception as exc:
        frame = extract_tb(exc.__traceback__)[-1]
        logger.error("Structure parse failed (%s) at %s:%d", type(exc).__name__,
                     Path(frame.filename).name, frame.lineno)
        snapshot = Structure(source, (), 0, len(source), "结构读取未完成，请继续使用源码视图。")
    if not closed.is_set():
        try:
            signals.parsed.emit(key, snapshot)
        except RuntimeError:
            # Window destruction can race this emit. Do not hide live failures.
            if not closed.is_set():
                logger.error("Structure result receiver was unexpectedly destroyed")


class _BlockDelegate(QStyledItemDelegate):
    """Render only visible rows; avoid a QWidget/editor for every paragraph."""
    def _document(self, index, width):
        block = index.data(ROLE)
        doc = QTextDocument()
        doc.setDefaultFont(ui_font(12))
        title = html.escape(block.title).replace("\n", "<br>") if block else ""
        if block and block.kind in {"title", "section"}:
            doc.setDefaultFont(heading_font())
            size = 17 if block.kind == "title" else max(13, 16 - max(0, block.level - 2))
            markup = f'<div style="font-size:{size}pt;font-weight:600;color:{COLOR_TEXT}">{title}</div>'
        elif block and block.kind == "formula":
            title = re.sub(r"\^([a-zA-Z0-9])", r"<sup>\1</sup>", title)
            markup = (f'<div style="font-size:10pt;color:#59615d">公式</div>'
                      f'<p align="center" style="font-size:18pt">{title}</p>')
        elif block and block.kind == "table" and block.rows:
            rows = "".join("<tr>" + "".join('<td style="padding:5px;border-bottom:1px solid #dcdcd7">'
                                          + html.escape(cell) + "</td>" for cell in row) + "</tr>"
                           for row in block.rows)
            markup = '<div style="font-size:10pt;color:#59615d">表格</div><table width="100%" cellspacing="0">' + rows + "</table>"
        else:
            label = "" if block and block.kind == "text" else (
                f'<div style="font-size:10pt;color:#59615d">{LABELS.get(block.kind, "内容")}</div>' if block else "")
            markup = label + f'<div style="color:{COLOR_TEXT};line-height:140%">{title}</div>'
        doc.setHtml(markup)
        doc.setTextWidth(max(80, width - 38))
        return doc

    def sizeHint(self, option, index):
        tree = self.parent()
        depth, parent = 1, index.parent()
        while parent.isValid():
            depth += 1
            parent = parent.parent()
        width = max(100, tree.viewport().width() - tree.indentation() * depth - 24)
        doc = self._document(index, width)
        return QSize(width, max(42, int(doc.size().height()) + 18))

    def paint(self, painter, option, index):
        painter.save()
        painter.setClipRect(option.rect, Qt.ClipOperation.IntersectClip)
        rect = option.rect.adjusted(3, 3, -5, -3)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            painter.setPen(QColor(COLOR_ACCENT))
            painter.setBrush(QColor(COLOR_SELECTED))
            painter.drawRoundedRect(rect, 6, 6)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, QColor("#f6f6f4"))
        icon("grip-vertical", "#777d78", 14).paint(painter, rect.x() + 4, rect.y() + 14, 14, 14)
        doc = self._document(index, option.rect.width())
        painter.translate(rect.x() + 24, rect.y() + 10)
        doc.drawContents(painter)
        painter.restore()


class StructureTree(QTreeWidget):
    moveRequested = Signal(object, object, str)
    editRequested = Signal()
    codeRequested = Signal()
    deleteRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("documentStructureTree")
        self.setAccessibleName("文稿结构")
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setIndentation(22)
        self.setRootIsDecorated(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDropIndicatorShown(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setAnimated(False)
        self.setItemDelegate(_BlockDelegate(self))
        self.setStyleSheet("QTreeWidget { border: 0; background: #fcfcfb; padding: 12px; }"
                           "QTreeWidget::item { border: 0; }")
        self.setToolTip("拖到章节中可嵌套；拖到边缘可排序。双击编辑，Return 查看源码。")
        self.itemDoubleClicked.connect(lambda *_: self.editRequested.emit())
        self._drag_block = self._drag_key = None

    def drawBranches(self, painter, rect, index):
        """Continuous ancestry guides retain Qt's familiar disclosure triangles."""
        painter.save()
        painter.setPen(QPen(QColor("#a3b3a8"), 1.5))
        parent = index.parent()
        x = rect.right() - self.indentation() // 2
        if parent.isValid():
            painter.drawLine(x - self.indentation(), rect.center().y(), x - 3, rect.center().y())
        while parent.isValid():
            x -= self.indentation()
            painter.drawLine(x, rect.top(), x, rect.bottom())
            parent = parent.parent()
        painter.restore()
        super().drawBranches(painter, rect, index)

    def startDrag(self, actions):
        item = self.currentItem()
        self._drag_block = item.data(0, ROLE) if item else None
        self._drag_key = item.data(0, ROLE + 1) if item else None
        try:
            super().startDrag(actions)
        finally:
            self._drag_block = self._drag_key = None

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.codeRequested.emit()
            event.accept()
        elif event.key() == Qt.Key.Key_F2:
            self.editRequested.emit()
            event.accept()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.deleteRequested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def dropEvent(self, event):
        target = self.itemAt(event.position().toPoint())
        if (event.source() is not self or self._drag_block is None or target is None
                or target.data(0, ROLE + 1) != self._drag_key):
            event.ignore()
            return
        position = {QAbstractItemView.DropIndicatorPosition.AboveItem: "before",
                    QAbstractItemView.DropIndicatorPosition.BelowItem: "after",
                    QAbstractItemView.DropIndicatorPosition.OnItem: "inside"}.get(self.dropIndicatorPosition())
        # Never let Qt mutate a separate tree model: source edits are authoritative.
        event.ignore()
        if position:
            self.moveRequested.emit(self._drag_block, target.data(0, ROLE), position)


class StructureController(QObject):
    """One active-file view over existing tabs, documents and their undo stack."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.active = False
        self.snapshot: Structure | None = None
        self._snapshot_key = None
        self._rendered_key = None
        self._editor = None
        self._running = None
        self._closed = threading.Event()
        self.destroyed.connect(self._closed.set)
        self._signals = _Signals()
        self._signals.parsed.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(220)
        self._timer.timeout.connect(self.request_parse)
        self._items = {}
        self._selection_offset = 0
        self._preview_state = None
        self._preview_identity = None
        self.local_preview = False
        self._console_refresh_pending = False
        window.installEventFilter(self)
        window.console_button.parentWidget().installEventFilter(self)
        self.page = QWidget()
        self.page.setObjectName("sourceStructurePage")
        layout = QVBoxLayout(self.page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._tabs_row = QHBoxLayout()
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.currentChanged.connect(window.editor_tabs.setCurrentIndex)
        self.tabs.tabCloseRequested.connect(window.close_tab)
        self._tabs_row.addWidget(self.tabs, 1)
        self.mode_widget = QWidget()
        mode_row = QHBoxLayout(self.mode_widget)
        mode_row.setContentsMargins(4, 0, 4, 0)
        mode_row.setSpacing(0)
        self.structure_button = self._button("结构", lambda: self.set_active(True), checkable=True)
        self.code_button = self._button("源码", lambda: self.set_active(False), checkable=True)
        mode_row.addWidget(self.structure_button)
        mode_row.addWidget(self.code_button)
        window.editor_tabs.setCornerWidget(self.mode_widget, Qt.Corner.TopRightCorner)
        window.source_title.hide()
        with QSignalBlocker(self.code_button):
            self.code_button.setChecked(True)
        layout.addLayout(self._tabs_row)
        context_row = QHBoxLayout()
        context_row.setContentsMargins(14, 5, 10, 5)
        self.breadcrumb = StructureBreadcrumb()
        context_row.addWidget(self.breadcrumb, 1)
        self.edit_button = self._button("编辑内容", self.edit_selected)
        self.code_edit_button = self._button("编辑代码", self.show_selected_source)
        self.delete_button = self._button("删除块", self.delete_selected)
        self.delete_button.setToolTip("删除所选块；章节会连同内部内容删除。可用撤销恢复。")
        self.add_button = QToolButton()
        self.add_button.setText("添加块")
        self.add_button.setIcon(icon("square-plus"))
        self.add_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.add_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.add_button)
        for name, kind in (("章节", "section"), ("小节", "subsection"), ("正文", "text"),
                           ("公式", "formula"), ("图片…", "image"), ("表格…", "table"),
                           ("列表", "list"), ("自定义 LaTeX", "raw")):
            menu.addAction(name, lambda kind=kind: self.add_block(kind))
        self.add_button.setMenu(menu)
        for button in (self.edit_button, self.code_edit_button, self.delete_button, self.add_button):
            context_row.addWidget(button)
        layout.addLayout(context_row)
        self.hint = QLabel("拖动排序或嵌套；双击编辑内容，Return 查看源码。")
        self.hint.setObjectName("panelHint")
        self.hint.setWordWrap(True)
        self.hint.setContentsMargins(14, 4, 12, 6)
        layout.addWidget(self.hint)
        self.tree = StructureTree()
        self.tree.itemSelectionChanged.connect(self._selected)
        self.tree.moveRequested.connect(self.move)
        self.tree.editRequested.connect(self.edit_selected)
        self.tree.codeRequested.connect(self.show_selected_source)
        self.tree.deleteRequested.connect(self.delete_selected)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.tree)
        self.local_editor = SourceBlockEditor(self)
        self.content_stack.addWidget(self.local_editor)
        layout.addWidget(self.content_stack, 1)
        window.source_stack.addWidget(self.page)
        # Window-scoped routing still uses the exact source document's undo history.
        self.undo = QShortcut(QKeySequence.StandardKey.Undo, self.page)
        self.redo = QShortcut(QKeySequence.StandardKey.Redo, self.page)
        self.undo.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.redo.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.undo.activated.connect(self.undo_source)
        self.redo.activated.connect(lambda: self.undo_source(redo=True))
        self._install_preview_scope()

    def eventFilter(self, watched, event):
        if (event.type() in {QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest,
                            QEvent.Type.FontChange, QEvent.Type.StyleChange}
                and not self._closed.is_set() and not self._console_refresh_pending):
            self._console_refresh_pending = True
            QTimer.singleShot(0, self, self._sync_console_entry)
        return False

    def _sync_console_entry(self):
        self._console_refresh_pending = False
        if self._closed.is_set() or not self.window.isVisible():
            return
        main = self.window.console_button
        visible = main.isVisibleTo(self.window) and main.visibleRegion().contains(main.rect())
        # Qt can overflow the last toolbar action at large font scales. Keep
        # one visible fallback, never a duplicate control in the wide layout.
        fallback = bool(self.window.current_tab() and not self.window.block_mode_action.isChecked() and not visible)
        self.window.bottom_collapse_button.setVisible(fallback)

    @staticmethod
    def _button(text, callback, *, checkable=False):
        button = QToolButton()
        button.setText(text)
        button.setObjectName("workspaceViewButton")
        button.setCheckable(checkable)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if checkable:
            # Native accessibility Toggle changes checked state, not clicked.
            # State reconciliation below blocks signals and keeps one selected.
            button.toggled.connect(lambda _checked: callback())
        else:
            button.clicked.connect(callback)
        return button

    def _install_preview_scope(self):
        panel = self.window.pdf_panel
        self.preview_header = QWidget()
        row = QHBoxLayout(self.preview_header)
        row.setContentsMargins(12, 5, 8, 5)
        label = QLabel("PDF 预览")
        label.setFont(ui_font(12))
        row.addWidget(label, 1)
        self.local_button = self._button("当前块", lambda: self.set_local_preview(True), checkable=True)
        self.global_button = self._button("整篇", lambda: self.set_local_preview(False), checkable=True)
        with QSignalBlocker(self.global_button):
            self.global_button.setChecked(True)
        self.local_button.setToolTip("在当前整篇 PDF 中定位并聚焦所选块；不单独编译或改变导出。")
        row.addWidget(self.local_button)
        row.addWidget(self.global_button)
        panel.layout().insertWidget(0, self.preview_header)
        self.preview_header.hide()

    def current_changed(self, *_):
        if self._closed.is_set():
            return
        tab = self.window.current_tab()
        if self.window.block_mode_action.isChecked():
            self.set_local_preview(False)
        editor = tab.editor if tab else None
        if editor is not self._editor:
            self.leave_local_editor()
            if self._editor is not None and isValid(self._editor):
                self._editor.sourceTextChanged.disconnect(self._changed)
            self._editor = editor
            self.snapshot = None
            self._snapshot_key = None
            self._rendered_key = None
            self.tree.clear()
            self._items.clear()
            if editor is not None:
                editor.sourceTextChanged.connect(self._changed)
            self.set_local_preview(False)
        self.sync_view()
        if self.active:
            self._changed()

    def sync_view(self):
        tab = self.window.current_tab()
        allowed = bool(tab and not self.window.block_mode_action.isChecked())
        self.mode_widget.setVisible(allowed)
        self.preview_header.setVisible(allowed)
        self.local_button.setEnabled(allowed and self.snapshot is not None and not self.snapshot.error)
        if self.active and allowed:
            self._tabs_row.addWidget(self.mode_widget)
            self.mode_widget.show()
            self.window.source_stack.setCurrentWidget(self.page)
            self.tabs.blockSignals(True)
            while self.tabs.count() > self.window.editor_tabs.count():
                self.tabs.removeTab(self.tabs.count() - 1)
            for index in range(self.window.editor_tabs.count()):
                if index >= self.tabs.count():
                    self.tabs.addTab(self.window.editor_tabs.tabText(index))
                else:
                    self.tabs.setTabText(index, self.window.editor_tabs.tabText(index))
                self.tabs.setTabToolTip(index, self.window.editor_tabs.tabToolTip(index))
            self.tabs.setCurrentIndex(self.window.editor_tabs.currentIndex())
            self.tabs.blockSignals(False)
        elif allowed:
            self.window.editor_tabs.setCornerWidget(self.mode_widget, Qt.Corner.TopRightCorner)
            self.mode_widget.show()
            self.window.source_stack.setCurrentWidget(self.window.editor_tabs)
        with QSignalBlocker(self.structure_button), QSignalBlocker(self.code_button):
            self.structure_button.setChecked(self.active)
            self.code_button.setChecked(not self.active)

    def set_active(self, active: bool):
        if not active:
            self.leave_local_editor()
        if active and self._editor:
            text, cursor = self._editor.toPlainText(), self._editor.textCursor()
            offset = python_index_from_utf16(text, cursor.selectionStart()) or 0
            # A caret just after a closing delimiter still belongs to the
            # formula/title the user just typed, not the enclosing chapter.
            if not cursor.hasSelection() and offset and text[offset - 1] in "}]$":
                offset -= 1
            self._selection_offset = offset
        self.active = active
        self.sync_view()
        if active:
            self.current_changed()
        else:
            self._timer.stop()
            if self._editor:
                self._editor.setFocus()

    def _key(self):
        tab = self.window.current_tab()
        return ((id(self._editor), self._editor.source_revision, tab.path,
                 self.window.selected_project_scope) if self._editor and tab else None)

    def _changed(self):
        if self._closed.is_set():
            return
        if self.local_editor.key is not None and not self.local_editor.writing:
            # Undo, reload or an external edit invalidates the exact range binding.
            self.leave_local_editor()
        self.edit_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.local_button.setEnabled(False)
        self.tree.setDragEnabled(False)
        self.tree.setAcceptDrops(False)
        if self.active and self._editor is not None and not self.window.block_mode_action.isChecked():
            self.hint.setText("正在更新结构…")
            self._timer.start()

    def request_parse(self):
        if (self._closed.is_set() or not self.active or self._editor is None or self._running is not None
                or self.window.block_mode_action.isChecked()):
            return
        key = self._key()
        if key == self._snapshot_key:
            if self._rendered_key != key:
                self._populate()
            if self.snapshot:
                selected = self.snapshot.at(self._selection_offset)
                if selected and selected.start in self._items:
                    self.tree.setCurrentItem(self._items[selected.start])
            self._enable_edits()
            return
        source = self._editor.toPlainText()
        self._running = key
        threading.Thread(target=_parse_worker, args=(key, source, self._signals, self._closed), daemon=True).start()

    @Slot(object, object)
    def _finished(self, key, snapshot):
        if self._closed.is_set() or key != self._running:
            return
        self._running = None
        if key != self._key():
            if self.active:
                self.request_parse()
            return
        self.snapshot, self._snapshot_key = snapshot, key
        if self.active:
            self._populate()
        self._enable_edits()

    def _enable_edits(self):
        valid = bool(self.snapshot and not self.snapshot.error and self._key() == self._snapshot_key)
        editing = self.local_editor.key is not None
        self.edit_button.setVisible(not editing)
        self.add_button.setVisible(not editing)
        self.delete_button.setVisible(not editing)
        self.edit_button.setEnabled(valid)
        self.add_button.setEnabled(valid)
        self.delete_button.setEnabled(valid and self.selected_block() is not None)
        self.code_edit_button.setEnabled(editing or (valid and self.selected_block() is not None))
        self.local_button.setEnabled(valid)
        self.tree.setDragEnabled(valid)
        self.tree.setAcceptDrops(valid)
        self.hint.setText(self.snapshot.error if self.snapshot and self.snapshot.error else
                          "正在编辑当前块；保存与编译沿用同一份文稿。" if editing else
                          "竖线连接同一章节内的内容。拖动排序或嵌套；双击编辑；Delete 删除。")

    def _populate(self):
        self._rendered_key = self._snapshot_key
        self.tree.blockSignals(True)
        scroll = self.tree.verticalScrollBar().value()
        collapsed = {item.data(0, ROLE).start for item in self._items.values()
                     if item.childCount() and not item.isExpanded()}
        self.tree.clear()
        self._items.clear()
        newlines = [index for index, char in enumerate(self.snapshot.source) if char == "\n"]
        def add(blocks, parent):
            for block in blocks:
                item = QTreeWidgetItem(parent, [block.title])
                item.setData(0, ROLE, block)
                item.setData(0, ROLE + 1, self._snapshot_key)
                item.setToolTip(0, f"{LABELS[block.kind]} · 源码第 {bisect_right(newlines, block.start - 1) + 1} 行")
                flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                if block.kind != "title":
                    flags |= Qt.ItemFlag.ItemIsDragEnabled
                if block.kind == "section":
                    flags |= Qt.ItemFlag.ItemIsDropEnabled
                item.setFlags(flags)
                self._items[block.start] = item
                add(block.children, item)
                item.setExpanded(block.start not in collapsed)
        add(self.snapshot.blocks, self.tree)
        selected = self.snapshot.at(self._selection_offset)
        if selected and selected.start in self._items:
            self.tree.setCurrentItem(self._items[selected.start])
        self.tree.verticalScrollBar().setValue(scroll)
        self.tree.blockSignals(False)
        self._selected()

    def selected_block(self):
        item = self.tree.currentItem()
        return item.data(0, ROLE) if item else None

    def _selected(self):
        block = self.selected_block()
        tab = self.window.current_tab()
        filename = tab.path.name if tab and tab.path else "未命名文稿"
        parts = [filename]
        if block:
            self._selection_offset = block.start
            self.delete_button.setText("清空标题" if block.kind == "title" else "删除块")
            item, sections = self.tree.currentItem(), []
            while item:
                entry = item.data(0, ROLE)
                if entry.kind == "section":
                    sections.insert(0, entry.title.replace("\n", " ") or "未命名章节")
                item = item.parent()
            parts.extend((*sections, LABELS[block.kind]))
        self.breadcrumb.set_path(parts)
        self.code_edit_button.setEnabled(block is not None)
        self.delete_button.setEnabled(block is not None and self._key() == self._snapshot_key)
        if self.local_preview and block and self.local_editor.key is None:
            self.focus_pdf()

    def _current_source(self):
        tab = self.window.current_tab()
        if (tab is None or tab.editor is not self._editor or self._key() != self._snapshot_key
                or self.snapshot is None or self.snapshot.error):
            if self.active:
                self._timer.start(0)
            raise ValueError("内容已变化，请等待结构更新后再操作。")
        return self._writable_source()

    def _writable_source(self):
        tab = self.window.current_tab()
        if tab is None or tab.editor is not self._editor:
            raise ValueError("当前文件已切换，未应用旧修改。")
        if self._editor.isReadOnly() or tab.external_conflict or id(tab) in self.window.documents.checkpoint_tabs:
            raise ValueError("当前文稿只读或有外部冲突，请先在源码视图处理。")
        return self._editor.toPlainText()

    def _apply(self, edits, *, source, key):
        if self._key() != key or self._current_source() != source:
            raise ValueError("内容已变化，未应用旧修改。")
        self.apply_local_edits(edits, source=source, key=key)

    def apply_local_edits(self, edits, *, source, key):
        """Synchronous GUI-only write, guarded independently of the async outline."""
        if self._closed.is_set() or self._key() != key or self._writable_source() != source:
            raise ValueError("内容已变化，未应用旧修改。")
        cursor = QTextCursor(self._editor.document())
        cursor.beginEditBlock()
        for edit in sorted(edits, key=lambda e: e.start, reverse=True):
            cursor.setPosition(utf16_length(source[:edit.start]))
            cursor.setPosition(utf16_length(source[:edit.end]), QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(edit.text)
        cursor.endEditBlock()
        self._timer.start(220 if self.local_editor.writing else 0)

    def leave_local_editor(self):
        self.local_editor.key = None
        self.content_stack.setCurrentWidget(self.tree)
        self._enable_edits()

    def undo_source(self, *, redo=False):
        if self._editor is not None and not self._editor.isReadOnly():
            self.leave_local_editor()
            (self._editor.redo if redo else self._editor.undo)()

    def _notice(self, exc):
        self.hint.setText(str(exc))
        self.window.statusBar().showMessage(str(exc), 5000)

    def move(self, block, target, position):
        try:
            source = self._current_source()
            edits = move_block(self.snapshot, source, block, target, position)
            self._selection_offset = target.start
            self._apply(edits, source=source, key=self._key())
        except ValueError as exc:
            self._notice(exc)

    def select_source(self, block):
        source = self._current_source()
        cursor = QTextCursor(self._editor.document())
        end = block.header_end if block.kind == "section" else block.end
        cursor.setPosition(utf16_length(source[:block.start]))
        cursor.setPosition(utf16_length(source[:end]), QTextCursor.MoveMode.KeepAnchor)
        self._editor.setTextCursor(cursor)

    def show_selected_source(self):
        if self.local_editor.key is not None:
            start, end = self.local_editor.ranges[0]
            source = self._editor.toPlainText()
            cursor = QTextCursor(self._editor.document())
            cursor.setPosition(utf16_length(source[:start]))
            cursor.setPosition(utf16_length(source[:end]), QTextCursor.MoveMode.KeepAnchor)
            self._editor.setTextCursor(cursor)
            self.set_active(False)
            self._editor.flash_source_range(cursor)
            self._editor.ensureCursorVisible()
            return
        block = self.selected_block()
        if block is None:
            return
        try:
            self.select_source(block)
            self.set_active(False)
            self._editor.flash_source_range(self._editor.textCursor())
            self._editor.ensureCursorVisible()
        except ValueError as exc:
            self._notice(exc)

    def edit_selected(self):
        block = self.selected_block()
        if block is None:
            return
        try:
            source = self._current_source()
            self.set_local_preview(True)
            self.local_editor.bind(source, block, self._key())
            self.content_stack.setCurrentWidget(self.local_editor)
            self.local_editor.inputs.currentWidget().setFocus()
            self._enable_edits()
        except ValueError as exc:
            self._notice(exc)

    def delete_selected(self):
        block = self.selected_block()
        if block is None or self.local_editor.key is not None:
            return
        try:
            source, key, snapshot = self._current_source(), self._key(), self.snapshot
            if block.children:
                box = QMessageBox(QMessageBox.Icon.Question, "删除章节",
                                  f"删除“{block.title}”及其内部 {sum(1 for _ in block.walk()) - 1} 个内容块？\n可用撤销恢复。",
                                  parent=self.window)
                remove = box.addButton("删除章节及内容", QMessageBox.ButtonRole.DestructiveRole)
                box.addButton("保留", QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() is not remove:
                    return
            edit = delete_block(snapshot, source, block)
            self._selection_offset = edit.start
            self._apply([edit], source=source, key=key)
            self.window.statusBar().showMessage("已清空文稿标题，可撤销。" if block.kind == "title" else "已删除内容块，可撤销。", 4000)
        except ValueError as exc:
            self._notice(exc)

    def add_block(self, kind):
        try:
            source = self._current_source()
            key = self._key()
            selected = self.selected_block()
            position = selected.end if selected and selected.kind != "title" else self.snapshot.body_end
            snippets = {"section": "\\section{新章节}\n", "subsection": "\\subsection{新小节}\n",
                        "text": "在这里写正文。\n", "formula": "\\[\nE = mc^2\n\\]\n",
                        "list": "\\begin{itemize}\n\\item 列表内容\n\\end{itemize}\n",
                        "raw": "% 自定义 LaTeX\n"}
            if kind in {"image", "table"}:
                cursor = self._editor.textCursor()
                cursor.setPosition(utf16_length(source[:position]))
                self._editor.setTextCursor(cursor)
                (self.window.insert_figure if kind == "image" else self.window.insert_table)()
                return
            snippet = "\n\n" + snippets[kind] + "\n"
            if kind == "subsection" and selected and selected.kind == "section":
                command = HEADINGS[min(selected.level + 1, len(HEADINGS) - 1)]
                snippet = f"\n\n\\{command}{{新小节}}\n\n"
            self._selection_offset = position + 2
            self._apply([SourceEdit(position, position, snippet)], source=source, key=key)
        except (KeyError, ValueError) as exc:
            self._notice(exc)

    def _context_menu(self, point):
        item = self.tree.itemAt(point)
        if item is None:
            return
        self.tree.setCurrentItem(item)
        menu = QMenu(self.tree)
        menu.addAction("编辑内容", self.edit_selected)
        menu.addAction("编辑代码", self.show_selected_source)
        menu.addAction("定位 PDF", self.focus_pdf)
        menu.addAction("清空标题" if item.data(0, ROLE).kind == "title" else "删除块", self.delete_selected)
        # Keyboard-accessible equivalents for nesting/sorting by drag-and-drop.
        parent = item.parent() or self.tree.invisibleRootItem()
        index = parent.indexOfChild(item)
        block, key = item.data(0, ROLE), self._snapshot_key
        def move_to(target, position):
            if self._key() == key:
                self.move(block, target, position)
            else:
                self._notice("内容已变化，请重新选择后操作。")
        if index > 0:
            previous = parent.child(index - 1).data(0, ROLE)
            menu.addAction("上移", lambda: move_to(previous, "before"))
            if previous.kind == "section":
                menu.addAction("缩进到上一章节", lambda: move_to(previous, "inside"))
        if index + 1 < parent.childCount():
            following = parent.child(index + 1).data(0, ROLE)
            menu.addAction("下移", lambda: move_to(following, "after"))
        if item.parent() and item.parent().data(0, ROLE).kind == "section":
            outer = item.parent().data(0, ROLE)
            menu.addAction("移出当前章节", lambda: move_to(outer, "after"))
        menu.exec(self.tree.viewport().mapToGlobal(point))

    def set_local_preview(self, active):
        panel = self.window.pdf_panel
        was_local = self.local_preview
        entering = active and not was_local
        if entering:
            self._preview_state = panel._capture_state()
            self._preview_identity = self.window._current_synctex_pdf()
        self.local_preview = active
        with QSignalBlocker(self.local_button), QSignalBlocker(self.global_button):
            self.local_button.setChecked(active)
            self.global_button.setChecked(not active)
        if active:
            if entering and self.window._current_synctex_pdf() is not None and self.selected_block() is not None:
                panel.zoom_by(1.6)
            self.focus_pdf()
        elif (self._preview_state is not None and self._preview_identity is not None
              and self._preview_identity == self.window._current_synctex_pdf()):
            panel._restore_state_later(self._preview_state)
        elif not active and was_local and panel._has_pages:
            # An edit may make the old PDF stale without replacing its pixels.
            # Leaving local focus is a view change, never a freshness claim.
            panel.fit_width()
        if not active:
            self._preview_state = self._preview_identity = None

    def focus_pdf(self):
        block = self.selected_block()
        if not block:
            self.window.statusBar().showMessage("请先在结构视图中选择一个内容块。", 4000)
            return
        try:
            if self.window._current_synctex_pdf() is None or not self.window.toolchain.synctex:
                raise ValueError("当前块需要最新 PDF 和 SyncTeX；请先更新预览。")
            self.select_source(block)
            self.window.sync_current_source_to_pdf()
            self.local_button.setToolTip("当前块在整篇 PDF 中定位聚焦；最终分页与导出仍以整篇为准。")
        except ValueError as exc:
            self._notice(exc)

    def shutdown(self):
        self._closed.set()
        self._timer.stop()
        self.local_editor.key = None
