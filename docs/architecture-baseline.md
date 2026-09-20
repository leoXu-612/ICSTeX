# ICSTeX 架构审计基线（Modular Layout MVP Sprint 1）

审计时间：2026-08-07。本文件是对应 `deep-research-report.md` 的
“仓库审计”交付物，记录当前架构、可复用接口、风险与基线测试，供后续
Block 化改造决策使用。只记录已核实事实，不含路线图规划。

## 1. 技术栈与运行方式

- 语言/运行时：Python 3.12（要求 >=3.11），`python3 -m app` 启动。
- GUI：PySide6（QMainWindow 门面 + focused controllers）。
- 依赖：`PySide6`、`watchdog`、`pylatexenc`（`requirements.txt`）。
- LaTeX 编译：外部 `latexmk`/`pdflatex` 等（本机 TeX Live 2025），
  `app/core/latex_tools.py` 检测 toolchain；不捆绑发行版（D002）。
- 仓库：当前非逐文件跟踪的 git 仓库（有 initial commit 与 feature 分支）；
  权威根目录即本仓库根目录（当前工作目录）。

## 2. 分层与模块地图

### core（纯规则，无 Qt）

| 模块 | 职责 |
| --- | --- |
| `compiler.py` | 编译调度、防抖合并、单进程保证、PREVIEW/FINAL 双目的、preview 代理注入 |
| `pdf_state.py` / `preview_state.py` | 正式/预览 PDF freshness，按 compile root 隔离 |
| `formula_input.py` / `formula_tree.py` | 公式 envelope 识别、结构化数学树 AST、无损 LaTeX 解析/导出 |
| `latex_insertions.py` | 图片/表格/公式等片段生成与 package 管理 |
| `image_assets.py` / `asset_index.py` | 图片原子复制、增量资源索引（size/mtime 缓存） |
| `image_proxy_cache.py`（gui） | 快速预览代理图（TEXINPUTS 注入） |
| `file_watcher.py` | 仅监听打开的 .tex；过滤构建产物与 `.icstex` |
| `import_metrics.py` | 拖拽导入事务的阶段耗时与编译计数诊断 |
| `text_encoding.py` | 严格解码、同目录原子替换 |
| `word_count.py` / `diagnostics.py` / `project_tools.py` | 字数、项目检查、引用工具 |

### gui（PySide6 编排）

| 模块 | 职责 |
| --- | --- |
| `main_window.py` | 应用门面，兼容层，跨控制器共享状态 |
| `compile_controller.py` | 编译生命周期、预览/正式选择、清理安全校验 |
| `pdf_export_controller.py` | 仅 FINAL PDF 导出（revision 绑定、原子、时间戳刷新） |
| `document_lifecycle.py` | 保存防抖、历史快照、外部变更 |
| `insertion_actions.py` / `drop_import_worker.py` | 内容插入与后台图片复制事务 |
| `formula_dialog.py` / `math_editor_widget.py` / `math_keyboard.py` | 可视化公式编辑器（结构化光标、键盘、粘贴） |
| `project_panel_controller.py` / `project_panels.py` | 侧栏面板与增量图片索引 |

## 3. 数据流与持久化现状

- 文档数据权威形式：**普通 .tex 文本**；无结构化 Block/中间表示。
- 持久化：用户文档即 .tex（原子保存）；偏好设置 `.icstex`/settings ini；
  资源索引 `.icstex/asset-index.json`；历史快照按 tab 保存。
- 编辑→PDF：编辑器文本 → 防抖保存 → CompileManager（PREVIEW 或 FINAL）
  → `.icstex/preview/` 或 `.latex_build/` → PDF 面板展示；导出仅接受 FINAL。
- 公式：对话框内 `MathEditorWidget` 编辑结构化数学树，应用时序列化为
  LaTeX 文本写回 .tex；**没有持久化的公式 AST 中间表示**。

## 4. 可复用接口（Block 化改造输入）

- 公式 AST：`app/core/formula_tree.py` 的 `parse_math_latex/latex_of`，
  无损子集解析 + 未知命令原样保留——可直接作为公式 Block 的受管 AST 后端。
- 表格导入：`latex_insertions.parse_delimited`（CSV/TSV）已有基础解析；
  无 XLSX 适配器。
- 图片资源：`image_assets.scan/ImageAsset`、`asset_index.AssetIndex`，
  可复用为 Block 资源引用层。
- 编译/预览：`CompileManager`（调度、取消、双目的）+ `PdfStateStore`，
  可复用为 Block 项目的编译 worker。
- 校验基础设施：`diagnostics.py` 的中文解释/定位模式可扩展为 Block 校验错误中心。

## 5. 风险与缺口（相对 Modular Layout MVP）

| 风险/缺口 | 影响 | 备注 |
| --- | --- | --- |
| 无结构化文档中间表示 | Block/布局/主题改造需新建数据层 | 本 MVP Sprint 1 目标 |
| 公式 AST 不持久化 | 重开项目后只能从 LaTeX 反向解析 | 需 FormulaBlock adapter + 存储 |
| 无 JSON Schema 校验设施 | 新格式缺少机器可验证协议 | `jsonschema` 4.26 已在环境，需入依赖 |
| 表格仅片段生成 | 无 Table 数据模型/链接源/合并 | Sprint 3–4 范围 |
| 文档主题不存在 | 排版规则硬编码在模板/插入片段 | Sprint 5 范围 |
| .tex 单文件权威 | Block 引用/标签唯一性无注册表 | Registry 需新建 |
| 并排图片为固定插入类型 | 与通用 Row 布局冲突 | 需迁移器（本 Sprint） |
| 迁移与备份策略未定义 | 老项目改造有数据风险 | 本 Sprint 迁移框架 |

## 6. 基线测试（审计时全量通过）

```bash
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
# 495 tests passed（含公式编辑器、编译/预览、拖拽导入、导出时间戳等）
```

公式编辑器与编译相关测试在审计时保持通过，作为后续改造的回归基线。
