"""Formula composer dialog for exact formula selections (DS-001 GUI slice).

LaTeX text stays the only source of truth. The dialog edits an isolated
formula draft and never touches the editor: template and mode operations are
pure transformations through ``app.core.formula_input``, and the accepted
result is returned as a ``FinalTextEditPlan`` for the caller to apply.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
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

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.core.formula_input import FinalTextEditPlan


MODE_ORDER: tuple[tuple[str, FormulaMode], ...] = (
    ("$...$", FormulaMode.INLINE_DOLLAR),
    (r"\(...\)", FormulaMode.INLINE_PAREN),
    (r"\[...\]", FormulaMode.DISPLAY_BRACKET),
    ("equation", FormulaMode.EQUATION),
    ("equation*", FormulaMode.EQUATION_STAR),
)

TEMPLATE_ORDER: tuple[tuple[str, str], ...] = (
    ("分数", "fraction"),
    ("根式", "sqrt"),
    ("上标", "superscript"),
    ("下标", "subscript"),
    ("求和", "sum"),
    ("积分", "integral"),
    ("α", "greek_alpha"),
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
        self.setMinimumWidth(560)
        self._document_text = document_text
        self._start = start
        self._end = end
        self._template_cursor: int | None = 0 if start == end else None
        self._template_packages: tuple[str, ...] = ()
        self._applying_change = False
        self._accepted_plan: FinalTextEditPlan | None = None

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlainText(
            seed_text if seed_text is not None else document_text[start:end]
        )
        self.text_edit.setStyleSheet(
            "font-family: 'SF Mono', Menlo, monospace; font-size: 14px;"
        )

        self.mode_combo = QComboBox()
        for label, mode in MODE_ORDER:
            self.mode_combo.addItem(label, mode.value)

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
            QLabel("LaTeX 源码是唯一真值；正文在模式不变时逐字节保留，取消不会修改文档。")
        )
        layout.addWidget(self.text_edit, stretch=1)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("公式模式："))
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        template_row = QHBoxLayout()
        for label, key in TEMPLATE_ORDER:
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, k=key: self._apply_template_clicked(k))
            template_row.addWidget(button)
        layout.addLayout(template_row)

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

        self.text_edit.textChanged.connect(self._on_text_changed)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._refresh()

    def plan(self) -> "FinalTextEditPlan | None":
        """The accepted edit plan, or None when the dialog was not accepted."""

        return self._accepted_plan

    def apply_template(self, key: str) -> bool:
        """Apply a deterministic template to the current draft. Returns False
        when the current text is not a complete formula or the template cannot
        safely apply (for example, superscript on an empty body)."""

        envelope = recognize_formula(self.text_edit.toPlainText())
        if envelope is None:
            return False
        result = apply_formula_template(
            FormulaDraft(mode=envelope.mode, body=envelope.body), key
        )
        if result is None:
            return False
        self._template_cursor = result.cursor_offset
        self._template_packages = result.packages
        self._replace_draft_text(render_formula(result.draft))
        return True

    def set_mode(self, mode: FormulaMode) -> bool:
        """Regenerate only the outer wrapper for the current draft. Returns
        False when the current text is not a complete formula."""

        envelope = recognize_formula(self.text_edit.toPlainText())
        if envelope is None:
            return False
        draft = change_formula_mode(
            FormulaDraft(mode=envelope.mode, body=envelope.body), mode
        )
        self._replace_draft_text(render_formula(draft))
        return True

    def current_draft(self) -> FormulaDraft | None:
        envelope = recognize_formula(self.text_edit.toPlainText())
        if envelope is None:
            return None
        return FormulaDraft(mode=envelope.mode, body=envelope.body)

    def build_plan(self) -> "FinalTextEditPlan | None":
        """Build the final text edit plan for the current draft.

        Returns None when the current text is not a complete formula or the
        original editor selection can no longer be confirmed. This is pure
        planning: nothing is applied and the editor is never touched.
        """

        envelope = recognize_formula(self.text_edit.toPlainText())
        if envelope is None:
            return None
        draft = FormulaDraft(mode=envelope.mode, body=envelope.body)
        return final_edit_plan(
            self._document_text,
            self._start,
            self._end,
            draft,
            body_cursor_offset=self._template_cursor,
            packages=self._template_packages,
        )

    # ------------------------------------------------------------------

    def _apply_template_clicked(self, key: str) -> None:
        if not self.apply_template(key):
            QMessageBox.information(
                self,
                "编辑公式",
                "当前不是完整公式，或该模板对当前内容不可用；正文不会被猜测改写。",
            )

    def _on_mode_changed(self, _index: int) -> None:
        if self._applying_change:
            return
        mode = MODE_ORDER[self.mode_combo.currentIndex()][1]
        if not self.set_mode(mode):
            self._refresh()

    def _on_text_changed(self) -> None:
        if not self._applying_change:
            # Manual edits invalidate the template cursor/packages hint.
            self._template_cursor = None
            self._template_packages = ()
        self._refresh()

    def _replace_draft_text(self, text: str) -> None:
        self._applying_change = True
        try:
            self.text_edit.setPlainText(text)
        finally:
            self._applying_change = False
        self._refresh()

    def _refresh(self) -> None:
        text = self.text_edit.toPlainText()
        envelope = recognize_formula(text)

        self.mode_combo.blockSignals(True)
        if envelope is not None:
            index = next(
                (i for i, (_label, mode) in enumerate(MODE_ORDER) if mode is envelope.mode),
                0,
            )
            self.mode_combo.setCurrentIndex(index)
        self.mode_combo.blockSignals(False)

        if envelope is None:
            self.status_label.setText(
                "当前不是完整公式（需要 $…$、\\(…\\)、\\[…\\]、equation 或 equation*）；"
                "模板与模式切换暂不可用，正文不会被动改写。"
            )
            self.plan_label.setText("（无有效编辑计划）")
            return

        plan = self.build_plan()
        if plan is None:
            self.status_label.setText("公式有效，但无法确认编辑器中的原选区；请在文档中重新选择。")
            self.plan_label.setText("（无有效编辑计划）")
            return
        self.status_label.setText("公式有效；正文逐字节保留，仅按你的操作变换。")
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
