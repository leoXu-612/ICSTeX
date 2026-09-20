# Formula Editor 2.0 实施报告

## Conclusion

ICSTeX 已具备 Formula Editor 2.0 主体（结构化画布、AST 权威、草稿隔离、本地撤销、源码
模式、无损 LaTeX），本轮完成审计与缺口收口，并把可选本地 OCR 的“识别 → 审校 → 一次
命令提交”接入公式编辑流程。

## Architecture Before / After

- Before：`FormulaDialog`（MathEditorWidget 画布 + MathKeyboard + 源码模式）→
  `FormulaBlockAdapter.update_ast` → `UpdateBlockCommand`（已存在）；
- After：新增 `FormulaDraftSession` 语义由对话框草稿承担（Accept 前不动项目）、OCR
  入口“从图片识别…”→ `RecognitionReviewDialog` → 画布种子 → 用户确认 → 原有一次命令提交。

## Formula AST Ownership

`formula_tree.py` 为唯一 AST（MathSequence/Text/Command/Group/Frac/Sqrt/Script/BigOp），
`FormulaBlockAdapter` 负责 `latex_to_ast / render_latex / update_ast`；`latexCache` 可再生。

## Draft / Commit Flow

```text
编辑/OCR 审校 → 对话框草稿（本地 undo）→ 用户“应用”
→ 一次 UpdateFormulaCommand → 1 次 model_changed → 1 次保存 → 1 次防抖编译
取消 → 草稿丢弃，项目不变
```

## Canvas and Cursor Model

`MathEditorWidget`：QPainter 布局盒 + `CursorBoundary(slot,index)`，支持左右/上下/Tab、
鼠标定位、选区、结构插入、撤销/重做。本轮未复制第二套画布。

## Known Limitations

- 显式 PlaceholderNode 与“选中文本后包裹为分式/根号”尚未实现（审计记录，属后续增量）；
- 编辑器/键盘尚未整体接入 UiMetrics 缩放（UI Scale 改动不影响其字号，对话框字号固定）；
- 最近使用/模板持久化未做（记录于审计缺口表）。

## Files Modified

`app/gui/formula_dialog.py`（OCR 入口 + 审校接入）、`app/gui/formula_ocr/`（新）、
`app/core/formula/sanitizer.py`（新）、`app/optional_tools/pix2tex/`（新）、
`docs/formula-editor-current-state-audit.md`（新）。

## Suggested Next Step

PlaceholderNode + 选区包裹 + UiMetrics 联动 + 最近使用/模板设置。
