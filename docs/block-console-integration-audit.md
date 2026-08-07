# Block 模块与主控制台集成 - Phase 0 审计

> 分支：`feature/block-console-integration`（基于 `feature/modular-layout-mvp` 9ee1c22）
> 基线：621 tests OK（2026-08-07 本地冻结）
> 依据：`<HOME>/Downloads/ICSTeX_Block模块与主控制台集成执行方案.md`

## 1. 现有组件图

```text
MainWindow（facade，app/gui/main_window.py，1104 行）
├── build_ui(main_window_layout.py)：侧栏 ToolboxNavigation（9 标签）、
│   源码|PDF 主分割器、底部编译控制台（日志/错误/字数/检查）
├── build_actions(main_window_actions.py)：工具栏+文件/编译/编辑/视图/帮助菜单
├── connect_signals(main_window_signals.py)
├── 控制器
│   ├── CompileController（compile_controller.py，598 行）：per-root CompileManager
│   ├── DocumentLifecycle / EditorTabManager / PdfExportController
│   ├── InsertionActions / ProjectPanelController / PreferencesController
│   └── DiagnosticsPanel / PdfPanel / WordCountView
└── BlockProjectDialog（app/gui/blocks/project_dialog.py，209 行）
    ├── BlockLayoutPanel（布局，本地 _undo 列表）
    ├── TableEditor（TableEditorModel 投影）
    ├── FormulaBlockTab（公式 AST/latexCache）
    ├── MergeDialog（三方合并）
    ├── ThemeSettings（AppTheme）
    ├── 同步/导出标签
    └── 自有 CompileManager + QTimer 预览（_build_pdf_sync）

app/core/blocks：model / schema / registry / store / ids / migration /
layout / layout_solver / layout_renderer / block_renderer / table_model /
table_import / table_strategy / table_renderer / source_registry /
source_merge / theme / theme_renderer / source_map / export_package /
formula_adapter / demo / project_io
```

## 2. 状态所有权表（现状）

| 状态 | 当前所有者 | 集成后目标所有者 |
|---|---|---|
| BlockRegistry | BlockProjectDialog 构造入参（菜单路径由 load_block_project 加载） | ProjectSession（唯一） |
| LayoutNode | BlockLayoutPanel.layout（含本地 _undo 深拷贝栈） | ProjectSession.layout + 全局 QUndoStack |
| TableEditorModel | BlockProjectDialog 构造入参 | ProjectSession（表格 Block 数据） |
| SourceRegistry（SourceRecord 列表） | demo 构建器 / project_io（仅加载） | ProjectSession + repository |
| DocumentTheme / AppTheme | BlockProjectDialog 构造入参 | ProjectSession |
| CompileManager（Block 侧） | BlockProjectDialog._preview_manager（唯一重复入口） | ProjectSession.compile_manager（唯一） |
| CompileManager（源码侧） | CompileController.compile_managers（per-root） | 保持不变 |
| PdfState / PreviewState / displayed_pdfs | MainWindow | 保持不变（Block 编译结果注册进同一 pdf_state） |
| 选择状态 | 各面板各自（无统一 SelectionManager） | SelectionManager |
| Undo/Redo | BlockLayoutPanel._undo / TableEditorModel 各自 | 全局 QUndoStack |

## 3. 编译入口清单

| 位置 | 调用 | 说明 |
|---|---|---|
| document_lifecycle.py:109 | tab.manager.compile_async(purpose) | 编辑器空闲快速预览 |
| document_lifecycle.py:250 | tab.manager.schedule_compile("外部修改", purpose) | 外部文件变更 |
| compile_controller.py:100-102 | compile_async / schedule_compile | 手动编译/自动编译 |
| compile_controller.py:539 | manager.schedule_compile("图片资源修改", purpose) | 图片资源变更 |
| pdf_export_controller.py:192 | manager.compile_async(FINAL) | 导出 PDF 前正式编译 |
| **blocks/project_dialog.py:196-201** | 自有 CompileManager.compile_now | **重复入口，需并入 ProjectSession** |

## 4. 保存 / JSON 写入入口清单

| 位置 | 写入内容 | 说明 |
|---|---|---|
| blocks/project_dialog.py:_build_pdf_sync | blocks/*.tex、main.tex、styles/icstex-generated.sty | Stable LaTeX 生成（确定性） |
| blocks/project_dialog.py:_sync_table_to_registry | 表格 Block content | 保存前回写 |
| app/core/blocks/store.py:BlockStore.save | .icstex/blocks.json（原子） | 现有原子保存 |
| app/core/blocks/demo.py | 完整项目目录（blocks/layouts/sources/theme） | demo 构建器 |
| app/core/blocks/project_io.py:load_block_project | 只读加载 | 无保存路径 |

**缺口**：没有统一的 Project 保存入口（registry+layout+sources+theme 一次原子保存）；
所有写入口需收敛到 ProjectSession/repository。

## 5. 计划修改文件清单

新增：
- `app/core/blocks/project_repository.py`：统一加载/原子保存
- `app/gui/blocks/project_session.py`：ProjectSession（模型+保存+编译路由）
- `app/gui/blocks/workspace_widget.py`：BlockWorkspaceWidget（六标签主体提取）
- `app/gui/blocks/workspace_controller.py`：BlockWorkspaceController
- `app/gui/blocks/selection.py`：SelectionContext + SelectionManager
- `app/gui/blocks/commands.py`：QUndoCommand 系列
- `app/gui/blocks/navigation_dock.py`：Blocks/Layout/Sources 导航
- `app/gui/blocks/inspector.py`：上下文 Inspector
- `app/gui/blocks/diagnostics_dock.py`：编译诊断

修改：
- `app/gui/blocks/project_dialog.py`：改为轻量包装器（共享 Session）
- `app/gui/main_window.py` / `main_window_layout.py` / `main_window_actions.py` /
  `main_window_signals.py`：嵌入 Dock、工作区模式、共享 PDF 面板
- `app/core/blocks/project_io.py`：委托 repository（兼容保留）
- 测试：`tests/test_blocks_gui.py` 扩展 + 新增 `tests/test_block_console_integration.py`

## 6. 禁止事项核对

- 不修改六套 Schema（保持 1.0.0）；
- 不重写 LayoutSolver / Stable LaTeX Renderer / CompileManager；
- 不新增第二个 PDF 预览系统（Block 结果注册进 MainWindow 既有 PdfPanel）；
- 旧 BlockProjectDialog 入口保留为共享 Session 包装器。
