# ICSTeX Architecture Decision Log

更新时间：2026-08-06（Asia/Taipei）

本文件记录已经接受或明确提出的长期技术决策。它是 append-oriented 的决策
记录，不保存任务过程。需要改变既有决策时，新增一条 Superseding decision，
不要直接删除原决定。

状态定义：

- **Accepted**：当前必须遵守。
- **Proposed**：允许讨论和验证，尚未授权大规模实现。
- **Superseded**：已被后续 decision 取代，保留历史原因。

## Decision Index

| ID | 状态 | 决策 |
| --- | --- | --- |
| D001 | Accepted | ICSTeX 是本地科研写作基础设施，不是通用云编辑器 |
| D002 | Accepted | LaTeX distribution 保持外部依赖 |
| D003 | Accepted | 纯规则放入 `app/core`，PySide6 编排放入 `app/gui` |
| D004 | Accepted | 编译和 PDF freshness 按 normalized compile root 隔离 |
| D005 | Accepted | 用户文档写入必须严格解码并采用原子替换 |
| D006 | Accepted | 默认离线；网络操作必须由用户显式触发 |
| D007 | Accepted | 稳定模块只做渐进式演进，不进行大规模重写 |
| D008 | Accepted | 发布制品必须版本化，并与实际源码状态一致 |
| D009 | Accepted | 项目记忆按状态、计划、决策、历史和任务分层 |
| D010 | Proposed | 引入不依赖 QWidget 的 project/session state seam |
| D011 | Accepted | 界面、编辑内容和强调标题使用不同的字体角色 |
| D012 | Accepted | 自动预览与原图正式输出采用隔离的双保真构建链 |
| D013 | Proposed | 可视公式编辑保持 LaTeX 源码唯一真值并采用显式提交 |

## D001 - Local Research Writing Infrastructure

状态：Accepted  
确认日期：2026-07-14

**Context**

现有产品已经覆盖编译、PDF、Word Count、引用、诊断、模板和项目工具。继续按
“普通 LaTeX 编辑器”增加功能会导致范围膨胀，无法形成 ICC 学生工作流价值。

**Decision**

ICSTeX 定位为面向 ICC 学生的本地科研写作基础设施。中文优先、学生友好、
隐私和本地编译是产品原则。优先交付完整任务结果，例如“可以可靠提交”，而非
零散编辑器功能。

**Consequences**

- 功能必须映射到 IA、EE、实验报告或课程论文中的真实任务。
- 不以复制云编辑器、IDE 或 AI 写作产品为路线图。
- UI 保持轻量、中性和清晰，不用视觉复杂度掩盖状态。

## D002 - External LaTeX Distribution

状态：Accepted  
来源：既有架构与 packaging 约束

**Decision**

ICSTeX 不捆绑 MacTeX、TeX Live 或 MiKTeX。应用检测本机的 `latexmk`、
`pdflatex`、`xelatex`、`lualatex`、`texcount`、`synctex`、`bibtex` 和
`biber`。

**Consequences**

- 安装包更小，许可证和更新边界更清晰。
- Environment Doctor 与首次使用指引属于核心产品能力。
- 缺少 toolchain 时应提供温和状态提示；只有用户触发相关操作时给出直接指导。

## D003 - Core Rules and GUI Orchestration

状态：Accepted  
来源：既有架构约束

**Decision**

解析、路径、状态机、诊断、编译规则和文本转换尽量放入 `app/core`；QWidget、
signal wiring、dialog 和视觉状态留在 `app/gui`。`MainWindow` 作为门面，具体
流程逐步委托给 focused controllers。

**Consequences**

- 新的纯规则必须能在无 GUI 的单元测试中验证。
- `app/core` 不应反向 import `app/gui`。
- Qt-backed settings 等现有例外不应扩散；需要跨界面复用时再引入小型 adapter。

## D004 - Root-Scoped Build and PDF State

状态：Accepted  
来源：0.2.5-0.2.7 reliability work

**Decision**

编译管理器和 PDF freshness 以 normalized compile root 为 key。root 与通过
magic comment、`\input`、`\include` 或 `\subfile` 关联的 child documents
共享同一 build sequence。revision 与 build id 是状态依据，不使用文件 mtime
推断 freshness。

**Consequences**

- 后台 build 不能修改当前无关标签页的 PDF 或状态栏。
- 失败 build 可保留上次成功 PDF，但必须标为 stale。
- export/reveal/SyncTeX 只能使用当前 root 的有效记录。
- clean cache、Save-As、external reload 和 history restore 必须正确 invalidates
  或 dirty 对应 root state。

## D005 - File Safety Before Convenience

状态：Accepted  
来源：既有编码与导出约束

**Decision**

LaTeX 源文件严格解码；无法可靠识别时要求用户选择 encoding。保存、图片复制和
PDF 导出使用目标目录中的临时文件与 `os.replace`。未经明确要求不修改用户论文
内容。

**Consequences**

- 编码失败不得截断原文件。
- 操作失败不得留下看似有效的部分文件。
- 所有自动修复必须限定在可解释、可逆的技术变更范围内。

## D006 - Offline by Default, Explicit Network Consent

状态：Accepted  
来源：既有隐私原则与 reference import 行为

**Decision**

应用默认离线。DOI/arXiv metadata 获取仅在用户显式勾选联网选项后执行，并只
发送用户输入的 identifier。不得静默上传正文、引用库、PDF、日志或截图，也不
默认增加网络或 AI 行为。

**Consequences**

- 离线 fallback 必须可用并明确标识结果质量。
- 新的 network capability 必须说明发送内容、目标、失败行为和用户控制。

## D007 - Incremental Evolution

状态：Accepted  
来源：长期维护原则

**Decision**

不为追求架构整齐而重写已经验证的编译、PDF、文件 watcher 或编辑器流程。重构
以小型 seam、focused controller 和回归测试推进。

**Consequences**

- 每个重构 slice 应保持行为等价，并有明确回退边界。
- 不在同一任务混合大规模重构、产品功能和 release packaging。

## D008 - Versioned and Truthful Artifacts

状态：Accepted  
来源：0.2.7 release 与 2026-07-13 source delta

**Decision**

分发 versioned artifact，不通过改名旧 ZIP 或静默覆盖既有版本代表新源码。
macOS DMG、source archive、Windows ZIP/installer、版本元数据和用户文档必须
对应同一 source state。

**Consequences**

- 现有 0.2.7 artifacts 继续作为已验证历史制品，不声称包含 post-0.2.7 delta。
- Windows build 必须来自 Windows-local path 并在那里完成启动和 toolchain 验证。
- signing、architecture 和 notarization 状态必须如实描述。

## D009 - Layered Project Memory

状态：Accepted  
确认日期：2026-07-14

**Decision**

项目知识按当前状态、路线图、长期决策、任务 brief、持久提醒和历史日志分层。
每个事实只指定一个权威文件，其余文件使用链接，不复制易漂移的版本、测试数量
或 release 状态。

**Consequences**

- 文件职责和写入流程由 `docs/MEMORY_MANAGEMENT.md` 定义。
- `MEMORY.md` 不再保存精确测试数或当前 artifact 状态。
- `PROJECT_LOG.md` 保持 append-only；历史事实不为追求当前一致性而改写。

## D010 - Project Session State Seam

状态：Proposed  
提出日期：2026-07-14

**Context**

`MainWindow` 仍持有 open tabs、compile managers、PDF store、dependency cache、
toolchain 和 preference 状态。focused controllers 已降低方法复杂度，但继续增加
跨项目工作流会放大隐式耦合。

**Proposal**

在不重写 GUI 的前提下，逐步引入不依赖 QWidget 的 project/session model，
集中表达 compile root、document revisions、PDF state 和 compile manager ownership。

**Acceptance Gate**

只有在 Submission Readiness 或另一个真实纵向功能证明现有状态边界不足，并且
存在多标签页/root-child 回归测试时，才将本决策转为 Accepted。

## D011 - Role-Based Typography

状态：Accepted  
确认日期：2026-07-14

**Context**

全局使用思源宋体与 SF Mono 能强化学术和代码气质，但小字号菜单、按钮和状态栏
的清晰度、空间效率与视觉一致性较差。编辑内容与普通控件的阅读任务并不相同。

**Decision**

- 菜单、工具栏、按钮、状态栏和普通说明使用平台无衬线字体：macOS 优先
  SF Pro/PingFang SC，Windows 优先 Segoe UI/Microsoft YaHei。
- 源码编辑器、日志和代码式预览使用 SF Mono 与思源宋体的混合字体栈。
- 较大的欢迎页、对话框和空状态标题使用无衬线英文配思源宋体中文。
- 字体从本机已安装 family 中按顺序解析，不把第三方字体打包进应用。

**Consequences**

- 不再把编辑器字体全局应用到所有 QWidget。
- 新增或修改主题时必须维持三种字体角色，并通过字形解析与 GUI smoke test 验证。
- 缺少首选字体时允许使用明确的跨平台 fallback，不能导致不可读或异常粗体。

## D012 - Isolated Preview and Final Build Paths

状态：Accepted  
确认日期：2026-08-01

**Context**

LaTeX 必须从 compile root 处理完整文档，无法可靠地把任意正文片段独立编译。
高像素图片会同时增加引擎读取、PDF 写入和 GUI 重载成本；把源文件拆成 shadow
units 会破坏宏、计数器、引用、布局和 SyncTeX 语义。

**Decision**

- 自动编译可生成低保真快速预览；手动编译和导出始终生成原图正式 PDF。
- 快速预览只通过 process-local `TEXINPUTS` 注入同扩展名的项目内 PNG/JPEG
  代理图，不复制或改写 `.tex`、`.sty`、`.cls`。
- preview 使用 `.icstex/preview/<root-key>/` 下独立的 build、assets、manifest
  和 `PreviewStateStore`；canonical 继续使用 `.latex_build` 与 `PdfStateStore`。
- FINAL 在调度队列中优先于 PREVIEW。导出必须 flush 同 root 文档，并只接受
  source revision 一致的 FINAL 成功结果；不得复制 preview 或 stale PDF。
- 代理无法安全解析或生成时回退原图；删除图片时清除旧代理，避免掩盖真实错误。
- 代理缩放必须同步调整物理像素密度，使无显式 width/height 的图片保持与原图
  相同的 LaTeX natural size；可静态定位但不可代理的资产仍必须进入 watcher。

**Consequences**

- 持续编辑和 PDF reload 可利用较小代理；首次生成代理仍有一次性成本。
- UI 必须明确标识快速预览和原图回退，preview 不得冒充可提交结果。
- clean cache、root 切换、外部图片 watcher、build id 和 revision guard 必须同时
  覆盖两套状态，但两者不得互相发布 artifact。
- 当前快速预览不开放 SyncTeX；静态规则不能覆盖的图片语法继续使用原图。

## D013 - Source-First Visual Formula Composer

状态：Proposed  
提出日期：2026-08-06

**Context**

当前“公式”入口只插入固定 `equation` 骨架。可视公式输入可以降低初学者构造
分式、根式、上下标和运算符的门槛，但任意 LaTeX 公式的含义可能依赖自定义宏、
package、注释和文档上下文，无法保证通用可视 AST 与原始源码无损往返。

**Proposal**

- LaTeX 文本是唯一权威状态；可视控件只是可替换的编辑投影。
- wrapper 解析、模板变换、package 推导和文本 edit plan 位于 `app/core`，不得
  依赖 QWidget、网络、文件写入或编译状态。
- GUI 只编辑隔离的 formula draft；用户显式确认前不得修改正文或 preamble。
- 提交必须验证 document revision，并把 package 更新与公式替换合并为一次 Undo。
- 无法安全识别的宏、环境或选区必须原样保留并退回源码模式，不得猜测或静默
  canonicalize 公式正文。
- 即时可视渲染不代表正式 LaTeX 正确性；完整本地编译仍是最终依据。
- MathLive、QtWebEngine 或其他渲染技术必须本地离线使用。是否进入默认产品取决
  于 macOS/Windows 打包、内存、许可证、输入法、剪贴板和无网络验证结果。

**Acceptance Gate**

1. 先完成纯 core contract 与恶意/异常输入测试，不接入 GUI。
2. 0.2.8 clean release boundary 已完成，或 maintainer 明确授权提前开发。
3. 独立技术原型证明第三方可视层不会上传内容，且制品与运行成本可接受。
4. 插入、替换、取消、Undo、revision conflict 和未知宏回退均有 focused GUI tests。
5. 通过 Codex architecture/reliability review 后，再将本决策转为 Accepted。

**Consequences**

- 不把正文编辑器改造成通用 WYSIWYG，也不直接移植其他应用的完整编辑器。
- 第一阶段可以独立验证纯文本规则，降低 UI 和打包依赖带来的返工风险。
- visual surface 可以替换或降级，而不会改变用户 `.tex` 文件的权威地位。
