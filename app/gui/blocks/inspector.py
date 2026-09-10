"""Context Inspector dock: edits the selected Block / Layout / Slot."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sys

from PySide6.QtCore import QEvent, QSignalBlocker, Qt
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QFileDialog,
    QPlainTextEdit,
    QPlainTextDocumentLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.asset_import import import_image
from app.core.blocks.model import Block
from app.core.blocks.property_draft import PropertyDraft, draft_conflict, find_layout, layout_gap_mm
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.workspace_controller import BlockWorkspaceController
from app.gui.insert_panel import scrollable_panel


class BlockInspector(QWidget):
    """Shows and edits properties of the currently selected object."""

    def __init__(self, session: ProjectSession, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.controller = BlockWorkspaceController(session)
        self.layout_editor = None
        self.workspace = None
        self._current_block_id: str | None = None
        self._shown_block_id = None
        self._block_template = None
        self._layout_template = None
        self._documents = {}
        self._cursors = {}
        self._loading = False

        self.title = QLabel("未选择")
        self.title.setWordWrap(True)
        self.alias_edit = QLineEdit()
        self.type_label = QLabel("")
        self.content_edit = QPlainTextEdit()
        self._empty_document = QTextDocument(self)
        self._empty_document.setDocumentLayout(QPlainTextDocumentLayout(self._empty_document))
        self.content_edit.setPlaceholderText("内容…")
        self.content_edit.setToolTip("Tab 插入制表符；Control+Tab 移到应用修改；Control+Shift+Tab 回到别名。")
        self.content_edit.installEventFilter(self)
        self.heading_level = QComboBox()
        self.heading_level.addItems(["1", "2", "3", "4"])
        self.image_width = QDoubleSpinBox()
        self.image_width.setRange(0.0, 500.0)
        self.image_width.setSuffix(" mm")
        self.image_height = QDoubleSpinBox()
        self.image_height.setRange(0.0, 500.0)
        self.image_height.setSuffix(" mm")
        self.image_source_label = QLabel("")
        self.image_source_label.setWordWrap(True)
        self.image_replace_button = QPushButton("替换图片…")
        self.image_replace_button.clicked.connect(self._replace_image)
        self.caption_edit = QLineEdit()
        self.apply_button = QPushButton("应用修改")
        self.apply_button.clicked.connect(self._apply_block_edit)
        self.discard_button = QPushButton("放弃此 Block 属性草稿…")
        self.discard_button.clicked.connect(lambda: self._discard("block"))
        self.draft_list = QComboBox()
        self.draft_list.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.draft_list.setMinimumContentsLength(12)
        self.draft_list.activated.connect(self._choose_draft)
        self.draft_status = QLabel()
        self.draft_status.setWordWrap(True)
        self.formula_button = QPushButton("打开完整公式编辑器…")
        self.formula_button.clicked.connect(self._open_formula_editor)
        self.table_button = QPushButton("打开完整表格编辑器")
        self.table_button.clicked.connect(self._open_table_editor)
        self.formula_info = QLabel("")
        self.formula_info.setWordWrap(True)

        self.layout_kind = QLabel("")
        self.layout_gap = QDoubleSpinBox()
        self.layout_gap.setRange(0.0, 100.0)
        self.layout_gap.setSuffix(" mm")
        self.layout_alignment = QComboBox()
        self.layout_alignment.addItems(["top", "middle", "bottom"])
        self.layout_fallback = QComboBox()
        self.layout_fallback.addItems(["stackVertically", "error", "wrapRows", "normalizeWeights", "reduceGap"])
        self.layout_apply = QPushButton("应用布局属性")
        self.layout_apply.clicked.connect(self._apply_layout_edit)
        self.layout_discard = QPushButton("放弃此布局属性草稿…")
        self.layout_discard.clicked.connect(lambda: self._discard("layout"))

        self.form = QFormLayout()
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.form.addRow("类型", self.type_label)
        self.form.addRow("别名", self.alias_edit)
        self.form.addRow("内容", self.content_edit)
        self.form.addRow("标题级别", self.heading_level)
        self.form.addRow("宽度", self.image_width)
        self.form.addRow("高度", self.image_height)
        self.form.addRow("图片源", self.image_source_label)
        self.form.addRow("", self.image_replace_button)
        self.form.addRow("标题", self.caption_edit)
        self.form.addRow("", self.formula_button)
        self.form.addRow("", self.table_button)
        self.form.addRow("", self.formula_info)
        self.form.addRow("容器类型", self.layout_kind)
        self.form.addRow("gap", self.layout_gap)
        self.form.addRow("对齐", self.layout_alignment)
        self.form.addRow("回退", self.layout_fallback)
        self.form.addRow("", self.layout_apply)
        self.form.addRow("", self.layout_discard)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.addWidget(self.title)
        layout.addWidget(self.draft_list)
        layout.addWidget(self.draft_status)
        self.pending_discard_button = QPushButton("放弃列表中所选草稿…")
        self.pending_discard_button.clicked.connect(self._discard_selected_draft)
        layout.addWidget(self.pending_discard_button)
        layout.addLayout(self.form)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.discard_button)
        layout.addStretch()

        self.scroll = scrollable_panel(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.scroll)

        session.selection.selection_changed.connect(self._on_selection)
        session.model_changed.connect(lambda _reason: self.refresh())
        session.editor_drafts_changed.connect(self.refresh)
        for signal in (self.alias_edit.textChanged, self.content_edit.textChanged,
                       self.heading_level.currentTextChanged, self.image_width.valueChanged,
                       self.image_height.valueChanged, self.caption_edit.textChanged):
            signal.connect(self._block_fields_changed)
        for signal in (self.layout_gap.valueChanged, self.layout_alignment.currentTextChanged,
                       self.layout_fallback.currentTextChanged):
            signal.connect(self._layout_fields_changed)
        self.refresh()

    def set_layout_editor(self, panel) -> None:
        self.layout_editor = panel

    def set_workspace(self, workspace) -> None:
        self.workspace = workspace

    def eventFilter(self, watched, event) -> bool:
        # On Cocoa Qt's MetaModifier is the physical Control key. Keep normal
        # Tab/Undo/IME editing intact; this shortcut only moves focus, never applies.
        control = Qt.KeyboardModifier.MetaModifier if sys.platform == "darwin" else Qt.KeyboardModifier.ControlModifier
        if watched is self.content_edit and event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            backward = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            modifiers = event.modifiers() & ~Qt.KeyboardModifier.ShiftModifier
            if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and modifiers == control:
                event.accept()
                if event.type() == QEvent.Type.KeyPress:
                    target = self.alias_edit if backward else self.apply_button
                    self.scroll.ensureWidgetVisible(target)
                    target.setFocus(Qt.FocusReason.ShortcutFocusReason)
                return True
        return super().eventFilter(watched, event)

    # --- selection handling ----------------------------------------------
    def _on_selection(self, context, _source: str) -> None:
        if self._shown_block_id in self._documents:
            self._cursors[self._shown_block_id] = (QTextCursor(self.content_edit.textCursor()),
                                                   self.content_edit.verticalScrollBar().value())
        self._current_block_id = context.block_id
        self.refresh()

    def refresh(self) -> None:
        if self._loading or self.session._closed:
            return
        self._loading = True
        try:
            self._refresh_block()
            self._refresh_layout()
            self._refresh_draft_status()
            for target_id in list(self._documents):
                if target_id != self._current_block_id and ("block", target_id) not in self.session.editor_drafts:
                    self._documents.pop(target_id).deleteLater()
                    self._cursors.pop(target_id, None)
        finally:
            self._loading = False

    def _refresh_block(self) -> None:
        block_id = self._current_block_id
        block = self.session.registry.get(block_id) if block_id else None
        draft = self.session.editor_drafts.get(("block", block_id))
        secondary = next((self.session.editor_drafts[key] for key in
            (("formula", block_id), ("table", block_id)) if key in self.session.editor_drafts), None)
        if draft is not None:
            block = Block.from_dict(deepcopy(draft.base))
        elif block is None and secondary is not None:
            block = Block.from_dict(deepcopy(secondary.base))
        kind = block.type if block is not None else None
        rows = {
            self.type_label: kind is not None, self.alias_edit: kind is not None,
            self.content_edit: kind in {"text", "heading", "quote", "list", "rawLatex"},
            self.heading_level: kind == "heading", self.image_width: kind == "image",
            self.image_height: kind == "image", self.image_source_label: kind == "image",
            self.image_replace_button: kind == "image", self.caption_edit: kind == "image",
            self.formula_button: kind == "formula", self.table_button: kind == "table",
            self.formula_info: kind == "formula",
        }
        for widget, visible in rows.items():
            self.form.setRowVisible(widget, visible)
        self.apply_button.setVisible(kind is not None)
        self.discard_button.setVisible(draft is not None)
        if block is None:
            self._block_template = None
            self._shown_block_id = block_id
            self.content_edit.setDocument(self._empty_document)
            self.title.setText("未选择 Block")
            for widget in (
                self.type_label,
                self.alias_edit,
                self.content_edit,
                self.heading_level,
                self.image_width,
                self.image_height,
                self.image_source_label,
                self.image_replace_button,
                self.caption_edit,
                self.formula_button,
                self.table_button,
                self.formula_info,
            ):
                widget.setEnabled(False)
            return
        self.title.setText(f"{block.type}: {block.alias}")
        if block.type == "formula":
            self.formula_info.setText(str((secondary.values if secondary else block.content).get("latexCache", "")))
        if (self._shown_block_id == block_id and self._block_template is not None
                and (draft is not None or (self._block_template.base == block.to_dict()
                     and self._block_values(block.type) == self._block_template.initial))):
            return
        self.type_label.setText(block.type)
        values = draft.values if draft is not None else {}
        self.alias_edit.setText(values.get("alias", block.alias))
        content = {**(block.content or {}), **{key: value for key, value in values.items() if key != "alias"}}
        self._content_edit_for(block.type, content)
        for widget in (
            self.type_label,
            self.alias_edit,
            self.content_edit,
            self.heading_level,
            self.image_width,
            self.image_height,
            self.image_source_label,
            self.image_replace_button,
            self.caption_edit,
            self.formula_button,
            self.table_button,
            self.formula_info,
        ):
            widget.setEnabled(True)
        self.formula_button.setVisible(block.type == "formula")
        self.table_button.setVisible(block.type == "table")
        self.formula_info.setVisible(block.type == "formula")
        self.image_replace_button.setVisible(block.type == "image")
        self.image_source_label.setVisible(block.type == "image")
        if block.type == "image":
            self.image_source_label.setText(str(content.get("source", "（未设置）")))
        self._shown_block_id = block_id
        initial = self._block_values(block.type)
        self._block_template = draft or PropertyDraft("block", block.id, block.alias,
                                                      deepcopy(block.to_dict()), initial, initial)

    def _content_edit_for(self, block_type: str, content: dict) -> None:
        text = str(content.get("latex" if block_type == "rawLatex" else "text", ""))
        document = self._documents.get(self._current_block_id)
        previous = self.content_edit.textCursor()
        same = self._shown_block_id == self._current_block_id
        if document is None or document.toPlainText() != text:
            old = document
            document = QTextDocument(self)
            document.setDocumentLayout(QPlainTextDocumentLayout(document))
            document.setPlainText(text)
            self._documents[self._current_block_id] = document
            self._cursors.pop(self._current_block_id, None)
            if old is not None:
                old.deleteLater()
        if self.content_edit.document() is not document:
            self.content_edit.setDocument(document)
            saved = self._cursors.get(self._current_block_id)
            if saved is not None and saved[0].document() is document:
                self.content_edit.setTextCursor(saved[0])
                self.content_edit.verticalScrollBar().setValue(saved[1])
            elif same:
                cursor = QTextCursor(document)
                cursor.setPosition(min(previous.position(), document.characterCount() - 1))
                self.content_edit.setTextCursor(cursor)
        self.heading_level.setCurrentText(str(content.get("level", "1")))
        if block_type == "image":
            self.image_width.setValue(float(content.get("widthMm", 0.0) or 0.0))
            self.image_height.setValue(float(content.get("heightMm", 0.0) or 0.0))
            caption = content.get("caption", "") or ""
            self.caption_edit.setText(str(caption))

    def _block_values(self, kind):
        values = {"alias": self.alias_edit.text()}
        if kind in ("text", "heading", "quote", "list", "rawLatex"):
            values["latex" if kind == "rawLatex" else "text"] = self.content_edit.toPlainText()
        if kind == "heading":
            values["level"] = int(self.heading_level.currentText())
        if kind == "image":
            values.update(widthMm=self.image_width.value() or None,
                          heightMm=self.image_height.value() or None, caption=self.caption_edit.text())
        return values

    def _block_fields_changed(self, *_args):
        if not self._loading and self._block_template is not None:
            self.session.set_editor_draft(replace(self._block_template,
                values=self._block_values(self._block_template.base["type"])))

    def _refresh_layout(self) -> None:
        context = self.session.selection.current
        node = find_layout(self.session.layout, context.layout_node_id, context.slot_id)
        target_id = node.id if node is not None else context.layout_node_id
        draft = self.session.editor_drafts.get(("layout", target_id))
        if draft is not None:
            from app.core.blocks.layout import LayoutNode
            node = LayoutNode.from_dict(draft.base)
        selected = node is not None
        for widget in (self.layout_kind, self.layout_gap, self.layout_alignment, self.layout_fallback, self.layout_apply):
            self.form.setRowVisible(widget, selected)
        self.form.setRowVisible(self.layout_discard, draft is not None)
        if not selected:
            self._layout_template = None
            self.layout_kind.setText("（未选择布局对象）")
            return
        self.layout_kind.setText(f"{node.kind} · {node.id}")
        if (self._layout_template is not None and self._layout_template.target_id == node.id
                and (draft is not None or (self._layout_template.base == node.to_dict()
                     and self._layout_values() == self._layout_template.initial))):
            return
        values = draft.values if draft is not None else {
            "gap": layout_gap_mm(node),
            "alignment": node.alignment, "strategy": node.fallback.get("strategy", "stackVertically")}
        self.layout_gap.setValue(values["gap"])
        self.layout_alignment.setCurrentText(values["alignment"])
        self.layout_fallback.setCurrentText(values["strategy"])
        initial = self._layout_values()
        self._layout_template = draft or PropertyDraft("layout", node.id, f"布局 {node.kind}",
                                                       deepcopy(node.to_dict()), initial, initial)

    def _layout_values(self):
        return {"gap": self.layout_gap.value(), "alignment": self.layout_alignment.currentText(),
                "strategy": self.layout_fallback.currentText()}

    def _layout_fields_changed(self, *_args):
        if not self._loading and self._layout_template is not None:
            self.session.set_editor_draft(replace(self._layout_template, values=self._layout_values()))

    def _refresh_draft_status(self):
        current = self.draft_list.currentData()
        with QSignalBlocker(self.draft_list):
            self.draft_list.clear()
            self.draft_list.addItem(f"待应用编辑草稿（{len(self.session.editor_drafts)}）", None)
            names = {"block": "属性", "layout": "布局", "table": "表格", "table_cell": "单元格", "formula": "公式"}
            for draft in self.session.editor_drafts.values():
                self.draft_list.addItem(f"{draft.label} · {names.get(draft.kind, draft.kind)}", draft.key)
            # Tuple userData is an opaque Python QVariant; Qt findData does not
            # compare equal newly-created tuples structurally.
            index = next((i for i in range(self.draft_list.count())
                          if self.draft_list.itemData(i) == current), -1)
            self.draft_list.setCurrentIndex(max(index, 0))
        self.draft_list.setVisible(bool(self.session.editor_drafts))
        self.pending_discard_button.setVisible(self.draft_list.currentData() in self.session.editor_drafts)
        conflicts = [draft_conflict(draft, self.session.registry, self.session.layout)
                     for draft in self.session.editor_drafts.values()]
        message = self.session.editor_draft_error or next((text for text in conflicts if text), "")
        self.draft_status.setText(message or ("编辑草稿保留在本窗口；请应用或放弃，不会自动保存或编译。"
                                             if self.session.editor_drafts else ""))
        self.draft_status.setVisible(bool(self.draft_status.text()))

    def _choose_draft(self, index):
        key = self.draft_list.itemData(index)
        if key is None:
            return
        if key[0] in ("block", "table", "table_cell", "formula"):
            self.session.selection.select_block(key[1], source="inspector-draft")
            if key[0] == "table" and self.workspace is not None:
                self.workspace.open_table(key[1])
        else:
            self.session.selection.select_layout_node(key[1], source="inspector-draft")
        self.refresh()

    def _discard_selected_draft(self):
        key = self.draft_list.currentData()
        draft = self.session.editor_drafts.get(key)
        if draft is None:
            return
        choice = QMessageBox.warning(self, "放弃编辑草稿", f"仅放弃“{draft.label}”尚未应用的修改；已应用模型和文件不变。",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if choice == QMessageBox.StandardButton.Discard and self.session.editor_drafts.get(key) == draft:
            self.session.discard_editor_draft(key)

    def _discard(self, kind):
        template = self._block_template if kind == "block" else self._layout_template
        if template is None or template.key not in self.session.editor_drafts:
            return
        draft = self.session.editor_drafts[template.key]
        choice = QMessageBox.warning(self, "放弃属性草稿", "仅放弃此对象尚未应用的属性草稿；已应用模型和磁盘文件不变。",
                                     QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Cancel)
        if choice != QMessageBox.StandardButton.Discard or self.session.editor_drafts.get(template.key) != draft:
            return
        if kind == "block":
            self._block_template = None
        else:
            self._layout_template = None
        self.session.discard_editor_draft(template.key)

    # --- apply actions ----------------------------------------------------
    def _apply_block_edit(self) -> None:
        self.session.apply_editor_drafts((("block", self._current_block_id),))

    def _open_formula_editor(self) -> None:
        from app.gui.blocks.formula_edit import edit_formula_block
        edit_formula_block(self, self.session, self._current_block_id)

    def _open_table_editor(self) -> None:
        if self.workspace is not None:
            self.workspace.open_table(self._current_block_id)

    def _replace_image(self) -> None:
        block_id = self._current_block_id
        block = self.session.registry.get(block_id) if block_id else None
        if block is None or self.session.project_dir is None or self.session._closed:
            return
        base = deepcopy(block.to_dict())
        project = self.session.project_dir
        file_name, _ = QFileDialog.getOpenFileName(self, "替换图片", str(Path.home()), "图片 (*.png *.jpg *.jpeg *.gif *.pdf *.svg *.bmp)")
        if not file_name or self.session._closed:
            return
        current = self.session.registry.get(block_id)
        if current is None or current.to_dict() != base or self.session.project_dir != project:
            QMessageBox.warning(self, "图片未替换", "选择期间原对象已变化或删除；未复制图片，也未覆盖模型。")
            return
        try:
            relative = import_image(project, Path(file_name))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "图片未替换", f"导入失败，模型未修改：{exc}")
            return
        current = self.session.registry.get(block_id)
        if self.session._closed:
            return
        if current is None or current.to_dict() != base or self.session.project_dir != project:
            QMessageBox.warning(self, "图片未替换", "图片已复制，但原对象已变化；保留导入文件，未覆盖模型。")
            return
        self.controller.update_block(
            block_id,
            {"content": {**base["content"], "source": relative}},
            text="替换图片",
        )

    def _apply_layout_edit(self) -> None:
        if self._layout_template is not None:
            self.session.apply_editor_drafts((self._layout_template.key,))
