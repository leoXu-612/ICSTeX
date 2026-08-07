"""Formula composer dialog with a WYSIWYG visual math editor.

The dialog edits an isolated formula draft and never touches the editor.
Visual mode renders the formula as math structures (fraction, root, scripts,
operators) with structured cursor movement; a LaTeX source mode is available
for advanced edits and for constructs the visual editor cannot express. LaTeX
text remains the only source of truth, and the accepted result is returned as
a ``FinalTextEditPlan`` for the caller to apply.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication, QFileDialog
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
    change_formula_mode,
    final_edit_plan,
    recognize_formula,
    render_formula,
)
from app.gui.math_editor_widget import MathEditorWidget
from app.gui.math_keyboard import MathKeyboard
from app.core.formula.sanitizer import sanitize_formula_latex
from app.gui.formula_ocr.image_input import image_from_clipboard, image_from_file, preprocess, save_temp
from app.gui.formula_ocr.review_dialog import RecognitionReviewDialog
from app.optional_tools.pix2tex.protocol import RecognitionRequest

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.core.formula_input import FinalTextEditPlan


MODE_ORDER: tuple[tuple[str, FormulaMode], ...] = (
    ("$...$", FormulaMode.INLINE_DOLLAR),
    (r"\(...\)", FormulaMode.INLINE_PAREN),
    (r"\[...\]", FormulaMode.DISPLAY_BRACKET),
    ("equation", FormulaMode.EQUATION),
    ("equation*", FormulaMode.EQUATION_STAR),
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
        self.setMinimumWidth(700)
        self.resize(980, 780)
        self._document_text = document_text
        self._start = start
        self._end = end
        self._template_cursor: int | None = 0 if start == end else None
        self._template_packages: tuple[str, ...] = ()
        self._applying_change = False
        self._accepted_plan: FinalTextEditPlan | None = None

        seed = seed_text if seed_text is not None else document_text[start:end]
        envelope = recognize_formula(seed)
        self._seed_body = envelope.body if envelope is not None else seed

        self.visual_edit = MathEditorWidget()
        self.visual_edit.set_latex(self._seed_body)
        self.source_edit = QPlainTextEdit()
        self.source_edit.setPlainText(seed)
        self.source_edit.setStyleSheet(
            "font-family: 'SF Mono', Menlo, monospace; font-size: 14px;"
        )
        self.editor_stack = QStackedWidget()
        self.editor_stack.addWidget(self.visual_edit)
        self.editor_stack.addWidget(self.source_edit)

        self.ocr_button = QPushButton("从图片识别…")
        self.ocr_button.setToolTip("使用可选本地 pix2tex 识别公式图片（需先安装）。")
        self.ocr_button.clicked.connect(self._run_ocr)
        self.multi_ocr_button = QPushButton("多行拆分识别…")
        self.multi_ocr_button.setToolTip("把多行公式图拆成单行分别识别，再组合为 aligned 环境。")
        self.multi_ocr_button.clicked.connect(self._run_multi_ocr)
        self.ocr_status_label = QLabel("")
        self._ocr_request_id: str | None = None
        self._ocr_image_path: Path | None = None

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
        self.status_label.setWordWrap(True)
        self.plan_label = QLabel()
        self.plan_label.setWordWrap(True)
        self.plan_label.setStyleSheet(
            "background: #eef6ff; border: 1px solid #9cc3e5; padding: 6px;"
            "font-family: 'SF Mono', Menlo, monospace;"
        )

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("可视化编辑数学公式；LaTeX 源码是唯一真值，取消不会修改文档。")
        )
        layout.addWidget(self.editor_stack, stretch=1)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("公式模式："))
        mode_row.addWidget(self.mode_combo)
        mode_row.addWidget(self.source_mode_check)
        mode_row.addStretch()
        mode_row.addWidget(self.ocr_button)
        mode_row.addWidget(self.multi_ocr_button)
        mode_row.addWidget(self.ocr_status_label)
        layout.addLayout(mode_row)

        self.keyboard = MathKeyboard()
        self.keyboard.actionRequested.connect(self._on_keyboard_action)
        layout.addWidget(self.keyboard)

        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("将应用到编辑器："))
        layout.addWidget(self.plan_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("应用")
        if cancel_button is not None:
            cancel_button.setText("取消")
        buttons.accepted.connect(self._on_apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.visual_edit.set_latex(self._seed_body)
        self.source_edit.textChanged.connect(self._on_source_text_changed)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.source_mode_check.toggled.connect(self._on_source_mode_toggled)
        self._refresh()

    def _run_ocr(self) -> None:
        manager, image = self._prepare_ocr()
        if manager is None or image is None:
            return
        temp = save_temp(preprocess(image))
        self._ocr_image_path = temp
        self._ocr_request_id = f"ocr-{uuid.uuid4().hex[:12]}"
        manager.recognition_finished.connect(self._on_ocr_result)
        manager.recognition_failed.connect(self._on_ocr_failed)
        manager.recognize(RecognitionRequest(request_id=self._ocr_request_id, image_path=temp), session_id="formula-dialog")
        self.ocr_status_label.setText("识别中…")

    def _run_multi_ocr(self) -> None:
        manager, image = self._prepare_ocr()
        if manager is None or image is None:
            return
        from app.gui.formula_ocr.multi_line_dialog import MultiLineOcrDialog

        self.ocr_status_label.setText("识别中…")
        QApplication.processEvents()
        dialog = MultiLineOcrDialog(None, image=image, manager=manager, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            latex = dialog.result_latex()
            if latex:
                self.visual_edit.set_latex(latex)
                self.editor_stack.setCurrentWidget(self.visual_edit)
                self.source_mode_check.setChecked(False)
        self.ocr_status_label.setText("")

    def _prepare_ocr(self):
        app = QApplication.instance()
        manager = getattr(app, "ocr_manager", None)
        if manager is None:
            from app.optional_tools.pix2tex.manager import OcrManager

            manager = OcrManager(app)
            app.ocr_manager = manager
        if manager.status() in ("NOT_INSTALLED", "MODEL_MISSING"):
            QMessageBox.information(self, "公式识别", "pix2tex 未安装或模型缺失。")
            return None, None
        image = image_from_clipboard()
        if image is None:
            file_name, _ = QFileDialog.getOpenFileName(self, "选择公式图片", "", "图片 (*.png *.jpg *.jpeg *.webp)")
            if not file_name:
                return None, None
            image = image_from_file(Path(file_name))
        if image is None:
            QMessageBox.warning(self, "公式识别", "无法读取图片。")
            return None, None
        return manager, image

    def _on_ocr_result(self, payload) -> None:
        request_id, _session_id, result = payload
        if request_id != self._ocr_request_id:
            return
        self.ocr_status_label.setText("")
        sanitize = sanitize_formula_latex(result.latex)
        if self._ocr_image_path is None:
            return
        review = RecognitionReviewDialog(self._ocr_image_path, result.latex, sanitize, self)
        if review.exec() == QDialog.DialogCode.Accepted:
            latex = review.confirmed_latex()
            if latex:
                self.visual_edit.set_latex(latex)
                self.editor_stack.setCurrentWidget(self.visual_edit)
                self.source_mode_check.setChecked(False)

    def _on_ocr_failed(self, request_id: str, code: str, message: str) -> None:
        if request_id and request_id != self._ocr_request_id:
            return
        self.ocr_status_label.setText("")
        QMessageBox.warning(self, "公式识别失败", f"{code}：{message}")

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
        self._template_cursor = None
        self._template_packages = ()
        self._refresh()

    def _on_source_mode_toggled(self, checked: bool) -> None:
        self.keyboard.setEnabled(not checked)
        if checked:
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
                self._refresh()
                return
            self.visual_edit.set_latex(envelope.body)
        self.editor_stack.setCurrentIndex(1 if checked else 0)
        self._refresh()

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
        elif action == "delete":
            editor.delete_backspace()
        elif action == "apply":
            self._on_apply()
            return
        self._sync_source_from_visual()
        self._refresh()
        editor.setFocus()

    def _sync_source_from_visual(self) -> None:
        mode = MODE_ORDER[self.mode_combo.currentIndex()][1]
        self.source_edit.setPlainText(
            render_formula(FormulaDraft(mode=mode, body=self.visual_edit.latex()))
        )

    def _replace_source_text(self, text: str) -> None:
        self._applying_change = True
        try:
            self.source_edit.setPlainText(text)
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
        if draft is None:
            self.status_label.setText(
                "源码不是完整公式（需要 $…$、\\(…\\)、\\[…\\]、equation 或 equation*）。"
            )
            self.plan_label.setText("（无有效编辑计划）")
            return

        plan = self.build_plan()
        if plan is None:
            self.status_label.setText("公式有效，但无法确认编辑器中的原选区；请在文档中重新选择。")
            self.plan_label.setText("（无有效编辑计划）")
            return
        if self.source_mode_check.isChecked():
            self.status_label.setText("源码模式：直接编辑 LaTeX；正文仅按你的操作变换。")
        else:
            self.status_label.setText(
                "可视化模式：输入 / 生成分式，^ 上标，_ 下标，\\alpha 转为 α，可直接粘贴 LaTeX。"
            )
        package_text = "、".join(plan.packages) if plan.packages else "无"
        if plan.start == plan.end:
            self.plan_label.setText(
                f"在位置 [{plan.start}] 插入：\n{plan.text}\n所需 package：{package_text}"
            )
        else:
            self.plan_label.setText(
                f"替换 [{plan.start}:{plan.end}]：\n{plan.text}\n所需 package：{package_text}"
            )

    def _on_apply(self) -> None:
        plan = self.build_plan()
        if plan is None:
            QMessageBox.warning(
                self,
                "编辑公式",
                "当前不是完整公式，或无法确认原选区；请修正后应用或取消。",
            )
            return
        self._accepted_plan = plan
        self.accept()
