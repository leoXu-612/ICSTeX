"""Formula composer dialog with a WYSIWYG visual math editor.

The dialog edits an isolated formula draft and never touches the editor.
Visual mode renders the formula as math structures (fraction, root, scripts,
operators) with structured cursor movement; a LaTeX source mode is available
for advanced edits and for constructs the visual editor cannot express. LaTeX
text remains the only source of truth, and the accepted result is returned as
a ``FinalTextEditPlan`` for the caller to apply.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
)

from app.core.formula_input import (
    FormulaDraft,
    FormulaMode,
    apply_formula_template,
    final_edit_plan,
    recognize_formula,
    render_formula,
)
from app.gui.formula_ocr import DIALOG_OPEN_DEBOUNCE_SECONDS
from app.gui.math_editor_widget import MathEditorWidget
from app.gui.math_keyboard import MathKeyboard

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.core.formula_input import FinalTextEditPlan


MODE_ORDER: tuple[tuple[str, FormulaMode], ...] = (
    ("行内 · $…$", FormulaMode.INLINE_DOLLAR),
    (r"行内 · \(…\)", FormulaMode.INLINE_PAREN),
    (r"独立 · \[…\]", FormulaMode.DISPLAY_BRACKET),
    ("独立编号 · equation", FormulaMode.EQUATION),
    ("独立不编号 · equation*", FormulaMode.EQUATION_STAR),
)

class FormulaDialog(QDialog):
    """Edit an exact formula selection as a draft; returns an edit plan."""

    def __init__(
        self,
        parent,
        document_text: str,
        start: int,
        end: int,
        seed_text: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑公式")
        self.setMinimumWidth(800)
        self.resize(920, 700)
        self._document_text = document_text
        self._start = start
        self._end = end
        self._template_cursor: int | None = 0 if start == end else None
        self._template_packages: tuple[str, ...] = ()
        self._applying_change = False
        self._accepted_plan: FinalTextEditPlan | None = None
        self._submitted = False
        self._ocr_open = False
        self._ocr_ts = 0.0

        seed = seed_text if seed_text is not None else document_text[start:end]
        envelope = recognize_formula(seed)
        self._seed_body = envelope.body if envelope is not None else seed

        self.visual_edit = MathEditorWidget()
        self.visual_edit.set_latex(self._seed_body)
        self.source_edit = QPlainTextEdit()
        self.source_edit.setAccessibleName("公式 LaTeX 源码")
        self.source_edit.setPlainText(seed)
        self.source_edit.setStyleSheet(
            "font-family: 'SF Mono', Menlo, monospace; font-size: 14px; padding: 6px;"
        )
        self.editor_stack = QStackedWidget()
        self.editor_stack.addWidget(self.visual_edit)
        self.editor_stack.addWidget(self.source_edit)

        self.ocr_button = QPushButton("图片识别…")
        self.ocr_button.setToolTip("打开批量图片识别窗口（队列 + 进度条；逐张可精调）。")
        self.ocr_button.clicked.connect(self._open_batch_ocr)
        self.ocr_status_label = QLabel("")

        self.source_mode_check = QCheckBox("源码模式")
        self.source_mode_check.setToolTip(
            "可视化模式编辑数学结构；源码模式直接修改 LaTeX（含复杂结构）。"
        )

        self.mode_combo = QComboBox()
        for label, mode in MODE_ORDER:
            self.mode_combo.addItem(label, mode.value)
        seed_mode = envelope.mode if envelope is not None else MODE_ORDER[0][1]
        seed_index = next(
            (i for i, (_label, candidate) in enumerate(MODE_ORDER) if candidate is seed_mode),
            0,
        )
        self.mode_combo.setCurrentIndex(seed_index)

        self.status_label = QLabel()
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        self.plan_label = QLabel()
        self.plan_label.setWordWrap(True)
        self.plan_label.setTextFormat(Qt.TextFormat.PlainText)
        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setAccessibleName("将应用的 LaTeX")
        self.preview_edit.setFixedHeight(68)
        self.preview_edit.setStyleSheet(self.source_edit.styleSheet())

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("可视化编辑数学公式；LaTeX 源码是唯一真值，取消不会修改文档。")
        )

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("公式模式："))
        mode_row.addWidget(self.mode_combo)
        mode_row.addWidget(self.source_mode_check)
        mode_row.addStretch()
        self.undo_button = QPushButton("撤销")
        self.redo_button = QPushButton("重做")
        self.undo_button.clicked.connect(lambda: self._active_editor().undo())
        self.redo_button.clicked.connect(lambda: self._active_editor().redo())
        mode_row.addWidget(self.undo_button)
        mode_row.addWidget(self.redo_button)
        mode_row.addWidget(self.ocr_button)
        mode_row.addWidget(self.ocr_status_label)
        layout.addLayout(mode_row)
        layout.addWidget(self.editor_stack, stretch=1)

        self.keyboard = MathKeyboard()
        self.keyboard.actionRequested.connect(self._on_keyboard_action)
        layout.addWidget(self.keyboard)

        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("LaTeX 预览（确认后写入，最终效果以本地编译为准）"))
        layout.addWidget(self.preview_edit)
        layout.addWidget(self.plan_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("插入公式" if start == end else "替换公式")
            ok_button.setObjectName("primaryButton")
            ok_button.setAutoDefault(False)
            ok_button.setDefault(False)
        if cancel_button is not None:
            cancel_button.setText("取消")
        self._ok_button = ok_button
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
        self.apply_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.apply_shortcut.activated.connect(self._on_apply)
        if ok_button is not None:
            ok_button.setToolTip("确认写入文档 · " + self.apply_shortcut.key().toString(QKeySequence.SequenceFormat.NativeText))
        buttons.accepted.connect(self._on_apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Do not normalize a seed that the visual projection cannot round-trip.
        if self.visual_edit.latex() != self._seed_body:
            self.source_mode_check.setChecked(True)
            self.editor_stack.setCurrentWidget(self.source_edit)
            self.keyboard.setEnabled(False)
            self.keyboard.hide()
        self.visual_edit.latexChanged.connect(self._on_visual_text_changed)
        self.visual_edit.stateChanged.connect(self._refresh)
        self.source_edit.textChanged.connect(self._on_source_text_changed)
        self.source_edit.undoAvailable.connect(lambda _available: self._refresh())
        self.source_edit.redoAvailable.connect(lambda _available: self._refresh())
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.source_mode_check.toggled.connect(self._on_source_mode_toggled)
        self._refresh()
        self._active_editor().setFocus()

    def _active_editor(self):
        return self.source_edit if self.source_mode_check.isChecked() else self.visual_edit

    def _open_batch_ocr(self) -> None:
        if self._ocr_open or time.monotonic() - self._ocr_ts < DIALOG_OPEN_DEBOUNCE_SECONDS:
            return
        self._ocr_open = True
        self.ocr_button.setEnabled(False)
        try:
            self._open_batch_ocr_impl()
        finally:
            self._ocr_open = False
            self._ocr_ts = time.monotonic()
            self.ocr_button.setEnabled(True)

    def _open_batch_ocr_impl(self) -> None:
        manager = self._get_ocr_manager()
        if manager is None:
            return
        from app.gui.formula_ocr.batch_dialog import BatchRecognitionDialog

        dialog = BatchRecognitionDialog(manager, self)
        self.ocr_status_label.setText("识别中…")
        QApplication.processEvents()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            latex = dialog.combined_latex()
            if latex:
                self._seed_editor_latex(latex)
        self.ocr_status_label.setText("")

    def _get_ocr_manager(self):
        app = QApplication.instance()
        manager = getattr(app, "ocr_manager", None)
        if manager is None:
            from app.optional_tools.pix2tex.manager import OcrManager

            manager = OcrManager(app)
            app.ocr_manager = manager
        if manager.status() in ("NOT_INSTALLED", "MODEL_MISSING"):
            QMessageBox.information(self, "公式识别", "pix2tex 未安装或模型缺失。")
            return None
        return manager

    def _seed_editor_latex(self, latex: str) -> None:
        """Seed both source and visual editor without the mode toggle
        re-parsing the previous source over the new formula."""
        with QSignalBlocker(self.visual_edit), QSignalBlocker(self.source_edit), QSignalBlocker(self.source_mode_check):
            self.source_edit.setPlainText(f"\\({latex}\\)")
            self.visual_edit.set_latex(latex)
            source_mode = self.visual_edit.latex() != latex
            self.source_mode_check.setChecked(source_mode)
        self.mode_combo.setCurrentIndex(1)
        self.editor_stack.setCurrentIndex(1 if source_mode else 0)
        self.keyboard.setEnabled(not source_mode)
        self.keyboard.setVisible(not source_mode)
        self._refresh()


    def plan(self) -> "FinalTextEditPlan | None":
        """The accepted edit plan, or None when the dialog was not accepted."""

        return self._accepted_plan

    def apply_template(self, key: str) -> bool:
        """Insert a structure (visual mode) or transform source text."""

        if not self.source_mode_check.isChecked():
            if key not in ("fraction", "sqrt", "superscript", "subscript", "sum", "integral", "greek_alpha"):
                return False
            self.visual_edit.insert_structure(key)
            self._sync_source_from_visual()
            self._refresh()
            return True

        envelope = recognize_formula(self.source_edit.toPlainText())
        if envelope is None:
            return False
        result = apply_formula_template(
            FormulaDraft(mode=envelope.mode, body=envelope.body), key
        )
        if result is None:
            return False
        self._template_cursor = result.cursor_offset
        self._template_packages = result.packages
        self._replace_source_text(render_formula(result.draft))
        return True

    def set_mode(self, mode: FormulaMode) -> bool:
        """Regenerate only the outer wrapper for the current draft."""

        index = next(
            (i for i, (_label, candidate) in enumerate(MODE_ORDER) if candidate is mode),
            -1,
        )
        if index < 0:
            return False
        if self.source_mode_check.isChecked():
            envelope = recognize_formula(self.source_edit.toPlainText())
            if envelope is None:
                return False
            if envelope.mode is not mode:
                self._replace_source_text(render_formula(FormulaDraft(mode=mode, body=envelope.body)))
        with QSignalBlocker(self.mode_combo):
            self.mode_combo.setCurrentIndex(index)
        self._refresh()
        return True

    def current_draft(self) -> FormulaDraft | None:
        if self.source_mode_check.isChecked():
            envelope = recognize_formula(self.source_edit.toPlainText())
            if envelope is None:
                return None
            return FormulaDraft(mode=envelope.mode, body=envelope.body)
        mode = MODE_ORDER[self.mode_combo.currentIndex()][1]
        return FormulaDraft(mode=mode, body=self.visual_edit.latex())

    def build_plan(self) -> "FinalTextEditPlan | None":
        """Build the final text edit plan for the current draft.

        Returns None when the current text is not a complete formula or the
        original editor selection can no longer be confirmed. This is pure
        planning: nothing is applied and the editor is never touched.
        """

        draft = self.current_draft()
        if draft is None:
            return None
        return final_edit_plan(
            self._document_text,
            self._start,
            self._end,
            draft,
            body_cursor_offset=self._template_cursor,
            packages=self._template_packages,
        )

    # ------------------------------------------------------------------

    def _on_mode_changed(self, _index: int) -> None:
        if self._applying_change:
            return
        mode = MODE_ORDER[self.mode_combo.currentIndex()][1]
        if not self.set_mode(mode):
            self._refresh()

    def _on_source_text_changed(self) -> None:
        if self._applying_change:
            return
        self._template_cursor = None
        self._template_packages = ()
        self._refresh()

    def _on_visual_text_changed(self, _text: str) -> None:
        if self._applying_change or self.source_mode_check.isChecked():
            return
        self._template_cursor = None
        self._template_packages = ()
        self._sync_source_from_visual()

    def _on_source_mode_toggled(self, checked: bool) -> None:
        self.keyboard.setEnabled(not checked)
        self.keyboard.setVisible(not checked)
        if checked:
            self.visual_edit.commit_pending_command()
            self._sync_source_from_visual()
        else:
            text = self.source_edit.toPlainText()
            envelope = recognize_formula(text)
            if envelope is None:
                QMessageBox.warning(
                    self,
                    "编辑公式",
                    "源码不是完整公式（需要 $…$、\\(…\\)、\\[…\\]、equation 或 equation*）；"
                    "已在源码模式保留原文，请修正后再切换。",
                )
                self.source_mode_check.blockSignals(True)
                self.source_mode_check.setChecked(True)
                self.source_mode_check.blockSignals(False)
                self.keyboard.setEnabled(False)
                self.keyboard.hide()
                self._refresh()
                return
            if self.visual_edit.latex() != envelope.body:
                with QSignalBlocker(self.visual_edit):
                    self.visual_edit.set_latex(envelope.body)
            if self.visual_edit.latex() != envelope.body:
                with QSignalBlocker(self.source_mode_check):
                    self.source_mode_check.setChecked(True)
                self.keyboard.setEnabled(False)
                self.keyboard.hide()
                self.status_label.setText("此公式包含无法无损转换的结构；已保留源码，请继续在源码模式编辑。")
                return
        self.editor_stack.setCurrentIndex(1 if checked else 0)
        self._refresh()
        self._active_editor().setFocus()

    def _on_keyboard_action(self, action: str) -> None:
        if self.source_mode_check.isChecked():
            return
        editor = self.visual_edit
        if action.startswith("text:"):
            editor.type_key(action[5:])
        elif action.startswith("command:"):
            editor.insert_command(action[8:])
        elif action.startswith("structure:"):
            editor.insert_structure(action[10:])
        elif action == "cursor:left":
            editor.cursor_left()
        elif action == "cursor:right":
            editor.cursor_right()
        elif action == "cursor:tab":
            editor.cursor_tab()
        elif action == "delete":
            editor.delete_backspace()
        elif action == "apply":
            self._on_apply()
            return
        self._sync_source_from_visual()
        self._refresh()
        if action in ("structure:matrix", "structure:cases", "structure:nth_root"):
            self.source_mode_check.setChecked(True)
            self.status_label.setText("已插入结构；请在源码模式填写矩阵、分段条件或根指数。")
            self.source_edit.setFocus()
            return
        editor.setFocus()

    def _sync_source_from_visual(self) -> None:
        mode = MODE_ORDER[self.mode_combo.currentIndex()][1]
        text = render_formula(FormulaDraft(mode=mode, body=self.visual_edit.latex()))
        with QSignalBlocker(self.source_edit):
            if self.source_edit.toPlainText() != text:
                self.source_edit.setPlainText(text)
        self._refresh()

    def _replace_source_text(self, text: str) -> None:
        self._applying_change = True
        try:
            cursor = self.source_edit.textCursor()
            position = cursor.position()
            cursor.beginEditBlock()
            cursor.select(cursor.SelectionType.Document)
            cursor.insertText(text)
            cursor.endEditBlock()
            cursor.setPosition(min(position, len(text)))
            self.source_edit.setTextCursor(cursor)
        finally:
            self._applying_change = False
        self._refresh()

    def _refresh(self) -> None:
        self.mode_combo.blockSignals(True)
        if self.source_mode_check.isChecked():
            envelope = recognize_formula(self.source_edit.toPlainText())
            if envelope is not None:
                index = next(
                    (i for i, (_label, mode) in enumerate(MODE_ORDER) if mode is envelope.mode),
                    0,
                )
                self.mode_combo.setCurrentIndex(index)
        self.mode_combo.blockSignals(False)

        draft = self.current_draft()
        source_mode = self.source_mode_check.isChecked()
        self.undo_button.setEnabled(self.source_edit.document().isUndoAvailable() if source_mode else self.visual_edit.can_undo)
        self.redo_button.setEnabled(self.source_edit.document().isRedoAvailable() if source_mode else self.visual_edit.can_redo)
        plan = self.build_plan() if draft is not None else None
        self._ok_button.setEnabled(plan is not None and not self._submitted)
        preview = plan.text if plan is not None else ""
        if self.preview_edit.toPlainText() != preview:
            self.preview_edit.setPlainText(preview)
        if draft is None:
            self.status_label.setText(
                "源码不是完整公式（需要 $…$、\\(…\\)、\\[…\\]、equation 或 equation*）。"
            )
            self.plan_label.setText("（无有效编辑计划）")
            return

        if plan is None:
            self.status_label.setText("公式有效，但无法确认编辑器中的原选区；请在文档中重新选择。")
            self.plan_label.setText("（无有效编辑计划）")
            return
        if self.source_mode_check.isChecked():
            self.status_label.setText("源码模式：直接编辑 LaTeX；正文仅按你的操作变换。")
        else:
            self.status_label.setText(
                (f"正在输入 {self.visual_edit.pending_command} · 空格或 Enter 转换为符号" if self.visual_edit.pending_command else
                 "可视编辑 · / 分式 · ^ 上标 · _ 下标 · Tab / Shift+Tab 切换结构 · 可粘贴 LaTeX")
            )
        package_text = "、".join(plan.packages) if plan.packages else "无"
        if plan.start == plan.end:
            self.plan_label.setText(
                f"插入新公式 · 所需 package：{package_text} · 取消不会修改文档"
            )
        else:
            self.plan_label.setText(
                f"替换所选公式 · 所需 package：{package_text} · 可在文档中一次撤销"
            )

    def _on_apply(self) -> None:
        if self._submitted:
            return
        if not self.source_mode_check.isChecked():
            self.visual_edit.commit_pending_command()
        plan = self.build_plan()
        if plan is None:
            QMessageBox.warning(
                self,
                "编辑公式",
                "当前不是完整公式，或无法确认原选区；请修正后应用或取消。",
            )
            return
        self._submitted = True
        if self._ok_button is not None:
            self._ok_button.setEnabled(False)
        self._accepted_plan = plan
        self.accept()
