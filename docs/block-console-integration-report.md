# Block 模块与主控制台集成 - 最终实施报告

> 分支：`feature/block-console-integration`
> 基线：621 tests OK（Phase 0 冻结）→ 643 tests OK（集成完成）
> 依据：`<HOME>/Downloads/ICSTeX_Block模块与主控制台集成执行方案.md`

## 1. 根因与现状分析

问题：Block 能力全部承载在独立 `BlockProjectDialog` 中，与主控制台界面/控制层割裂——用户需在
主窗口与独立窗口间切换，Dialog 自带第二个 `CompileManager` 与本地撤销栈，无法形成连续工作流，
并有重复项目状态与重复编译入口的风险。

详见 [block-console-integration-audit.md](block-console-integration-audit.md)（组件图、状态所有权表、
编译/保存入口清单）。

## 2. 修改前架构图（摘要）

```text
MainWindow ──菜单──▶ BlockProjectDialog（自有 Registry + 自有 CompileManager + 本地 undo）
                        ├── BlockLayoutPanel（本地 _undo）
                        ├── TableEditor / FormulaBlockTab / MergeDialog / ThemeSettings
                        └── _build_pdf_sync（直接写 blocks/*.tex、main.tex、.sty）
```

## 3. 修改后架构图

```text
MainWindow
├── ProjectSession（唯一）：registry / layout / sources / document_theme / app_theme /
│   table_model / 唯一 CompileManager / 全局 QUndoStack / SelectionManager
├── Block 导航 Dock（Blocks / Layout / Sources）
├── Block 属性 Dock（Inspector）
├── Block 诊断 Dock（Diagnostics）
├── 中央 Block 工作区页（BlockWorkspaceWidget + 共享 PdfPanel）
└── Block 菜单（打开/关闭项目、Block 模式、撤销/重做）

BlockProjectDialog → 轻量包装器（同一 ProjectSession，无第二状态/编译器）
```

## 4. ProjectSession 设计

`app/gui/blocks/project_session.py`：单一项目状态对象。

- 持有：`registry`、`layout`、`sources`、`document_theme`、`app_theme`、`table_model`、
  `compile_manager`（唯一）、`undo_stack`、`selection`、`project_dir`；
- 信号：`model_changed / save_requested / save_completed / compile_requested / compile_finished`；
- 路由：`notify_model_changed(reason)` → 1 次保存请求 + 1 次防抖编译请求；
- 保存：`request_save`（500ms 防抖）→ `save_now`（`project_repository.save_project` 原子写入）；
- 编译：`request_preview`（`compile_manager.schedule_compile(PREVIEW)` 防抖/单进程）、
  `compile_final`（同步 FINAL，300s 超时）；
- Stable LaTeX 由 `assemble_latex()` 确定性生成（复用原渲染链，输出语义不变）。

## 5. BlockWorkspaceWidget / Controller 设计

- `workspace_widget.py`：从 Dialog 提取的六标签主体（布局/表格/公式/同步/主题/导出）+ 预览行；
  只渲染与交互，发出 `block_selected / layout_selected / source_selected / edit_requested /
  preview_requested`，不加载项目、不写 JSON、不启动编译器。
- `workspace_controller.py`：`add_block / delete_block / duplicate_block / rename_block /
  update_block / assign_block_to_slot`，全部 push 到 `session.undo_stack`；删除前检查引用。

## 6. SelectionManager 设计

`selection.py`：`SelectionContext(block_id, layout_node_id, slot_id, source_id)` +
`SelectionManager`。同一 context 重复选择不重复发信号（防循环）；接收方带 `source` 标签更新
自身高亮而不回播。导航/工作区/Inspector/诊断共享同一 `session.selection`。

## 7. Undo Command 清单

`commands.py`（均为 `QUndoCommand`，push 时立即 redo，undo 可完整回退）：

- `AddBlockCommand` / `DeleteBlockCommand`（含 Layout 槽位移除与恢复）/ `DuplicateBlockCommand`
- `RenameBlockCommand` / `UpdateBlockCommand`（快照回退）
- `AssignBlockToSlotCommand`（槽位换块）
- `ChangeLayoutCommand`（Row/Grid/排序/属性，经布局面板统一应用）
- `UpdateTableCommand`（表格数据快照）

## 8. 保存与编译事件流

```text
用户操作 → Command.redo → 模型更新（registry/layout/table）
        → ProjectSession.notify_model_changed
        → request_save（500ms 合并）→ project_repository 原子写入
        → request_preview（CompileManager 700ms 防抖，单进程 PREVIEW）
        → assemble_latex（确定性）→ 编译 → 结果登记 pdf_state → 共享 PdfPanel 刷新
```

一次编辑的目标计数：**1 次模型更新、1 次合并保存、1 次防抖编译、1 次 PDF 刷新**
（由 `test_model_change_routes_to_one_save_and_one_preview`、
`test_inspector_edit_undo_redo_single_compile_request` 覆盖）。

## 9. 修改文件列表

新增：`app/core/blocks/project_repository.py`、`app/core/blocks/asset_import.py`、
`app/gui/blocks/project_session.py`、`workspace_widget.py`、`workspace_controller.py`、
`commands.py`、`selection.py`、`navigation_dock.py`、`inspector.py`、`diagnostics_dock.py`、
`app/gui/block_mode.py`、`tests/test_block_console_integration.py`、
`docs/block-console-integration-audit.md`。

修改：`project_dialog.py`（轻量包装器）、`layout_panel.py`（可选全局命令栈 + 列表刷新）、
`table_editor.py`（model_changed 信号）、`formula_tab.py`（session 命令路由）、
`main_window.py`（窗口状态持久化）、`main_window_layout.py`（Block 模式安装 + PDF 包装引用）、
`registry.py`（restore）、`source_registry.py`（SourceRecord 序列化）。

## 10. 删除/合并的重复入口

- `BlockProjectDialog._preview_manager`（自有 CompileManager）→ 并入 `ProjectSession.compile_manager`；
- `BlockLayoutPanel._undo` 本地栈 → 可选路由到全局 `QUndoStack`；
- `TableEditorModel` 撤销栈保留（表格内部），行/列级操作进入 `UpdateTableCommand`；
- Dialog 不再直接写 `blocks/*.tex / main.tex / .sty`（由 session.assemble_latex 统一生成）。

## 11. 自动化测试结果

- 全套件 **643 tests OK**（本地，2026-08-07）；
- 新增 22 项集成测试：仓库往返/原子性、会话单例身份、模型变更路由、保存防抖、表格模型初始化、
  控制器增删改查+撤销重做、布局引用删除与恢复、删除保护、Dialog 共享会话、选择循环防护、
  Schema 1.0.0 不变、Stable LaTeX 确定性、MainWindow 会话共享、跨面板选择同步、
  Inspector 编辑撤销/重做单次编译请求、模式切换共享 PDF 面板、Dock 状态持久化、
  多项目生命周期、图片资产导入、导航拖拽建图；
- `tools/run_mvp_ci.sh` 本地 CI 模拟全绿（compileall + ubuntu 子集 + 全套件 + demo 构建）；
- 导出包空目录编译由既有 `test_demo` 覆盖并通过。

## 12. 手动验收记录（步骤）

1. 运行 `python3 -m app`；
2. 菜单 **Block → 打开 Block 项目到工作区…** → 选择 `demo/`；
3. 左侧出现 Blocks/Layout/Sources 导航，右侧属性、下方诊断 Dock 显示；
4. 在 Blocks 页新建 Text Block → 拖入布局槽位（布局页）→ 改内容/权重 → 生成 PDF；
5. 公式/表格 Block 双击 → 中央打开对应编辑器修改 → 撤销/重做验证；
6. 把图片拖到 Blocks 空白处 → 自动建 Image Block；拖到已有图片块 → 替换源；
7. 制造 LaTeX 错误 → 诊断页点击“定位错误 Block” → 左侧高亮并打开编辑器；
8. 关闭应用再启动 → Dock 布局恢复；导出可移植包 → 空目录编译。

## 13. Schema 与 Stable LaTeX 兼容性证明

- 六套 Schema `$id` 均为 `/1.0.0`，`SCHEMA_VERSION == "1.0.0"`（测试锁定）；
- Stable LaTeX 仍由 `assemble_latex` 复用 `render_block / render_layout / solve_layout /
  render_document_theme_sty` 生成，`% ICSTEX:BEGIN/END` 机器注释与 source map 保留；
- 相同输入两次生成字节一致（测试锁定）；demo 与导出包编译通过。

## 14. 已知限制

- 布局树“新增容器”仅做嵌套/清空操作，尚未实现容器间任意嵌套拖拽；块排序为视觉顺序；
- Sources 页支持状态/重新同步/定位，三方合并冲突 UI 仍走 MergeDialog（独立入口）；
- Block 预览编译为异步防抖（与主编辑器一致），同步“生成并编译 PDF”保留 300s 超时；
- 窗口状态持久化在关闭时写入 AppSettings（仅 UI 状态，不写项目数据）；
- MainWindow 仍是 facade，Block 集成逻辑集中在 `block_mode.py`，未塞入 MainWindow。

## 15. 下一阶段建议

1. 布局树嵌套拖拽与像素级画布（明确不在本轮范围）；
2. Sources 页接入三方合并流程与冲突内联解决；
3. 图片资源统一 `AssetImportService` 扩展（替换时保留旧资源回收策略）；
4. 将 Block 模式注册为工作区预设（写作/Block/数据），接入 `saveState` 预设切换；
5. 恢复 GitHub 计费后重跑远端 CI（ubuntu golden + macOS 全套件）。
