# 公式系统现状审计（Phase 1）

> 分支：`feature/formula-editor-local-ocr`
> 依据：`ICSTeX_Formula_Editor_2.0与pix2tex本地公式识别工程指导.md` Phase 1

## 1. 结论

ICSTeX 已具备一套完整的结构化公式编辑器 2.0 主体：**Formula AST 是权威状态**、
编辑器为 QPainter 结构化画布（非字符串编辑）、草稿隔离、本地撤销/重做、源码模式与
无损 LaTeX 往返均已实现并有测试。真实缺口是：显式 PlaceholderNode、选区包裹插入、
最近使用/模板设置持久化、编辑器与 UI Scale 联动，以及 pix2tex 本地 OCR（全新）。

## 2. 十个审计问题逐项回答

1. **AST 是否已经是权威状态？** 是。`FormulaBlockAdapter.content_for/update_ast` 以
   `ast` 为权威字段，`latexCache` 由 `latex_of(parse(...))` 可再生（
   [formula_adapter.py](../app/core/blocks/formula_adapter.py)）；编辑器改动导出 LaTeX 后
   经 AST 写回。
2. **当前公式编辑器是否直接编辑字符串？** 否。`MathEditorWidget` 渲染表达式树并做结构化
   编辑（光标/选区/结构插入），源码只是独立视图；最终 LaTeX 由 `latex_of` 生成。
3. **哪些节点已支持？** `Text / Command / MathSequence / Group / Frac / Sqrt / Script(上下标) /
   BigOp(∑/∫/lim/∏)` + 符号命令表（alpha…）与无损 raw 文本保留
   （[formula_tree.py](../app/core/formula_tree.py)）。**缺显式 PlaceholderNode**（空槽以空框渲染）。
4. **光标如何存储？** `CursorBoundary`（slot + index），支持左右/上下/Tab 结构化移动与鼠标定位
   （[math_editor_widget.py](../app/gui/math_editor_widget.py)）。
5. **是否已有本地撤销栈？** 是。编辑器内 `_undo/_redo` 快照栈；对话框草稿在 Accept 前不影响项目。
6. **是否每次按键都会修改项目模型？** 否。`FormulaDialog` 在隔离草稿上编辑，Accept 才返回
   `FinalTextEditPlan`；Block 路径在确认后 push 一个 `UpdateBlockCommand`。
7. **是否每次按键都会请求 PDF 编译？** 否。编辑期间不触发项目编译；Apply 后经
   `ProjectSession.notify_model_changed` 产生一次防抖保存 + 一次防抖预览编译。
8. **Formula Block 如何写回？** `formula_tab._edit_selected` → `FormulaDialog` → 解析 → 
   `adapter.update_ast(latex_to_ast(body))` → `UpdateBlockCommand`（有会话时）或
   `registry.update`（兼容路径）。
9. **无法解析的 LaTeX 如何保留？** 无损解析器把未知命令/环境保留为 raw 文本节点，
   `latex_of(parse(text)) == text` 逐字节成立；源码模式可继续修改，不丢内容。
10. **当前测试覆盖哪些结构？** `test_formula_tree / test_math_editor_widget /
    test_math_keyboard / test_formula_adapter / test_formula_input` 共 34 项，
    覆盖解析/序列化/往返、结构插入、光标移动、撤销、键盘、Block 适配。

## 3. 缺口清单（与工单对照）

| 缺口 | 工单位置 | 处理 |
| --- | --- | --- |
| PlaceholderNode 显式节点 | §7.2 | 本轮补（空槽渲染 + Tab 导航已存在，补节点语义） |
| 选区包裹插入（选中 x+1 后点 √/分式） | §10.2 | 本轮补 |
| 最近使用/模板 AppSettings 持久化 | §11.3 | 本轮补（`formulaEditor` 设置键） |
| 编辑器/键盘与 UiMetrics 联动 | §11.2 | 本轮补基础（字体/间距按 scale） |
| pix2tex 本地 OCR Sidecar | §6/15–17 | 本轮实现（可选、隔离、无 torch 进 GUI） |
| FormulaLatexSanitizer | §19 | 本轮实现（core，纯函数） |
| Recognition Review Panel | §20 | 本轮实现 |
| OCR 提交 → 一次命令 | §21 | 复用 UpdateFormulaCommand/AddBlockCommand |

## 4. 复用决策

- 不新建第二套 Formula AST：复用 `formula_tree` 与 `FormulaBlockAdapter`；
- 不新建第二套编辑器：扩展现有 `MathEditorWidget`（选区包裹、占位语义）；
- OCR 作为全新可选 Sidecar 接入，核心环境零依赖。
