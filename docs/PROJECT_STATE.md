# ICSTeX Project State

更新时间：2026-08-01（Asia/Taipei）

本文件是 ICSTeX **当前已验证状态**的权威来源。它记录现在成立的事实，
不记录任务经过；完成历史写入 `PROJECT_LOG.md`，长期决策写入
`docs/DECISION_LOG.md`，未来计划写入 `docs/ROADMAP.md`。

## Product Identity

ICSTeX 是面向 ICC 学生的本地科研写作基础设施，而不只是一个普通
LaTeX 编辑器。它应帮助学生可靠地创建、检查、编译和交付 IA、EE、
实验报告、课程论文等学术项目。

产品边界：

- 中文优先、学生友好，同时保留 LaTeX、BibTeX、SyncTeX、PDF、
  Word Count 等必要技术术语。
- 本地文件和本地编译优先；不静默上传 `.tex`、`.bib`、PDF、日志或截图。
- 优先使用确定性的本地规则和工具，不以云端编辑器或 AI 自动改写为默认方向。
- 不代替用户修改论文正文，除非用户明确要求。

## Current Source State

- 权威工作区：`<HOME>/Desktop/Codex/ICS-Project-/ICSTeX`
- 版本元数据：`0.2.7`
- 技术栈：Python 3.11+、PySide6、本机 LaTeX distribution、PyInstaller
- 当前源码包含已验证的 post-0.2.7 UI、PDF 状态、字体与快速预览改进。
- 字体按角色分离：常规 UI 使用系统无衬线字体，编辑器和日志使用 SF Mono
  配思源宋体，较大的强调标题使用系统无衬线英文配思源宋体中文。
- 这些源码改进尚未进入任何现有 0.2.7 DMG、source ZIP 或 Windows artifact。
- 自动编译默认生成隔离的快速预览：静态、项目内 PNG/JPEG 可使用本地代理图；
  手动编译与导出始终使用原图正式构建。
- 快速预览与正式 PDF 使用独立 build directory、freshness state 和 build purpose；
  正式导出只接受与当前 source revision 一致的 canonical PDF。
- 图片侧栏在解码阶段生成 44×44 缩略图并使用有界缓存，不再全尺寸解码原图。
- 下一次发布前必须显式选择新版本；当前建议使用 `0.2.8`，不要静默覆盖
  已验证的 0.2.7 制品。

## Verification Baseline

当前源码基线已于 2026-08-01 在快速预览实现后重新验证：

- `python3 -m compileall -q app tests packaging/install_build_dependencies.py`：通过
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests`：372 tests passed
- `QT_QPA_PLATFORM=offscreen python3 -m app`：冷启动 smoke 通过
- 本机真实 TeX Live 2025 `latexmk`：preview/final 均成功，`.fls` 分别读取
  代理图与项目原图；静态 `\graphicspath` 已覆盖，带/不带 DPI 的 PNG 及 JPEG
  自然尺寸与正式输出一致，EXIF 方向保持与正式 LaTeX 输出一致

最近一次 packaging/UI acceptance 仍来自 2026-07-13 的 accepted source delta：

- `bash packaging/preflight.sh`：通过
- 本地真实 `latexmk` 的 source-to-PDF UI acceptance：通过
- GUI offscreen smoke coverage：1440x900、1280x720、1100x720

精确测试数量只在本文件维护。历史日志中的较旧数量属于当时的真实结果，
不应回写或改写。

## Release Matrix

| 对象 | 状态 | 说明 |
| --- | --- | --- |
| 当前源码 | Verified, not packaged | 版本元数据仍是 0.2.7，但包含后续 UI/font/preview delta |
| `dist/ICSTeX-0.2.7.dmg` | Verified historical release | Apple Silicon arm64、ad-hoc signed、未 notarize；不含最新 delta |
| `dist/ICSTeX-Source-0.2.7.zip` | Verified transfer input | 不含最新 delta；只适用于原始 0.2.7 Windows rebuild |
| Windows 0.2.7 binary/installer | Pending | 必须在 Windows-local path 构建并做启动、版本和 TeX 检测验证 |
| 下一版 matching artifacts | Not started | 选择版本后重新生成 macOS DMG、source ZIP 和 Windows artifacts |

## Architecture Map

### Core and domain rules

- `app/core/compiler.py`：编译调度、队列、停止、结果分类和 build id。
- `app/core/pdf_state.py`：按 normalized compile root 隔离的 PDF freshness 状态机。
- `app/core/preview_state.py`：与正式 PDF 隔离的快速预览 freshness 状态机。
- `app/core/compile_feedback.py`：编译结果到中文 UI feedback 的统一映射。
- `app/core/paths.py`：root 推断、依赖闭包、build path 和路径归一化。
- `app/core/word_count.py`：项目级 `texcount`、透明 fallback 和来源标注。
- `app/core/diagnostics.py`：项目检查、错误解释和安全修复规则。
- `app/core/text_encoding.py`：严格解码和同目录原子保存。
- `app/core/project_tools.py`：项目初始化、引用和 BibTeX 工具。

### GUI orchestration

- `app/gui/main_window.py`：应用门面与共享 UI 状态协调。
- `app/gui/compile_controller.py`：save/build/result/PDF 生命周期。
- `app/gui/image_proxy_cache.py`：图片引用发现、代理缓存、原子发布和安全回退。
- `app/gui/pdf_export_controller.py`：原图正式编译、revision guard 与原子 PDF 导出。
- `app/gui/document_lifecycle.py`：保存 debounce、外部更新和历史快照。
- `app/gui/editor_tab_manager.py`：标签页生命周期。
- `app/gui/project_panel_controller.py`：项目面板数据协调。
- `app/gui/preferences_controller.py`：设置和可用状态同步。
- `app/gui/pdf_panel.py`：PDF 显示、搜索、位置保持和 SyncTeX。
- `app/gui/theme.py`：亮色主题、可访问对比度和跨平台字体角色解析。

当前方向是保持 `MainWindow` 为门面，并渐进地把具体流程放入 focused
controllers；不进行一次性 GUI 重写。

## Stable Capabilities

- Source/PDF 双栏、manual/auto compile、engine 选择、停止、clean 和 rebuild。
- 自动快速预览、原图手动编译和“先正式编译再导出”的双保真构建链。
- 多文件 root 推断与 `% !TEX root` / `% !TEX program` 支持。
- PDF 搜索、位置保持和 source/PDF SyncTeX。
- 项目级 Word Count，明确区分 `texcount` 与 Python fallback。
- 严格编码检测、原子保存、历史快照和外部文件 watcher。
- 图表/公式/列表插入、图片 drag-and-drop、模板、引用、标签、outline 和搜索。
- 项目诊断、中文错误解释、Environment Doctor 和 privacy-safe feedback bundle。
- macOS/Windows packaging scaffolding。

## Durable Non-Regression Boundaries

- 保存、自动编译和外部 reload 不得移动 source cursor/scroll。
- PDF reload 尽可能保持页码、缩放和 viewport。
- 编译前必须 flush 当前编辑内容。
- 失败编译保留上次成功 PDF，但必须显式标记 stale。
- PDF freshness、导出和 reveal 必须按 compile root 隔离。
- 后台标签页结果不得覆盖当前标签页的 PDF 或编译指示器。
- Word Count 不得静默从 `texcount` 降级。
- 没有 LaTeX toolchain 时启动不得出现阻塞 modal。
- toolbar 与 menu 的 auto/manual 状态必须同步并持久化。
- toolbar controls 保持清晰、浅色和可用状态明确，避免继承不可读的系统按钮样式。
- 用户停止必须由显式状态判断，不能依赖平台相关 return code。
- 写文件与导出必须避免留下截断或部分文件。
- 快速预览不得写入 canonical `.latex_build`，不得更新正式 PDF state，也不得
  成为导出源；FINAL 在 debounce 与运行中队列里不可被 PREVIEW 降级。
- 同一 root 的 preview/final PDF 切换必须保留 PDF page、zoom 和 viewport。

## Current Risks and Limits

- 当前源码与已发布 0.2.7 artifacts 已分离，下一次发布需要明确版本边界。
- Windows matching artifact 尚未完成真实机器验证。
- macOS artifact 仅 arm64、ad-hoc signed、未 notarize。
- `MainWindow` 仍持有较多跨控制器共享状态，后续应小步建立可测试的
  project/session state seam。
- 项目当前不是 Git repository；变更追踪仍依赖备份、日志和 SHA-256 索引。
- 复杂 SyncTeX 映射仍可能不精确。
- 首次代理生成包含一次图片解码、缩放与写盘，冷预览不保证快于冷正式编译；
  收益主要来自持续编辑、较小的后续 PDF 写入和预览重载。
- 代理当前覆盖静态、项目内、非 dot-relative 的 PNG/JPG/JPEG 引用以及常见静态
  `\graphicspath`；动态宏、绝对路径、`./`/`../` 和其他格式安全回退原图，
  但可静态定位的项目内资产仍纳入 watcher。
- 停止、清缓存或 root 切换最多等待编译 worker 1.5 秒；未退出时清缓存会拒绝
  删除，退役 manager 的晚到信号不会重新发布状态或 watcher。
- 快速预览暂不开放 SyncTeX；需要源码/PDF 定位时先执行正式编译。
- 直接编辑 PDF 或从 PDF 反向转换为 LaTeX 不在产品范围内。

## Immediate Decision Needed

在继续增加产品功能前，应恢复 release boundary：

1. 确认截至 2026-08-01 的 post-0.2.7 source delta 是否作为 0.2.8 发布。
2. 同步版本元数据和用户文档。
3. 重新构建 macOS DMG 与 clean source archive。
4. 从 Windows-local path 构建并验证同版本 artifact。

## Maintenance Rule

只有在事实已经验证后才更新本文件。任务过程、命令输出和旧 hash 写入
`PROJECT_LOG.md`；尚未接受的设计不写入本文件。
