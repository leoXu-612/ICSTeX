# ICSTeX Architecture Decision Log

更新时间：2026-09-03（Asia/Taipei）

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
| D014 | Accepted | 不受信项目采用默认拒绝的本地执行边界 |
| D015 | Accepted | Agent/Harness 通过项目绑定、默认只读的 stdio MCP 操作 ICSTeX |
| D016 | Accepted | MCP 并发复用官方调度，并由项目级协调器保持一致性 |
| D017 | Accepted | 文件工具箱保持只读模型，文件变更经项目级安全控制器执行 |
| D020 | Proposed | 用户开启更新检查，验证完整制品并在保存退出后更新应用 |

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
- 快速预览不开放 SyncTeX 的初始限制已由 D019 的反向定位规则取代；静态规则
  不能覆盖的图片语法继续使用原图。

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

## D014 - Default-Deny Local Execution Boundary

状态：Accepted
确认日期：2026-08-08

**Context**

LaTeX 项目可携带 `latexmk` 配置、Magic Root、原始 LaTeX Block、图片路径和联网
元数据。若打开、预览、导出或清理缓存直接信任这些字段，项目内容可越过用户所选
范围并触发本机代码执行、文件读取或数据泄露。

**Decision**

- 打开项目不启动编译；首次显式编译仅在当前会话授权该 normalized root 的自动预览。
- 所有编译强制忽略项目 `latexmkrc`、关闭 shell escape，并使用有限超时。
- Magic Root、图片和导出源必须保持在用户选择的 canonical project boundary；
  symlink 与非普通文件 fail closed。
- Block 的持久化 `trusted` 字段不等同运行权限；公式从受管 AST 重建，raw LaTeX
  还需要当前会话的显式编译授权。
- DOI/arXiv 仅访问固定 HTTPS metadata endpoint，禁止重定向并限制响应大小。

**Consequences**

- 依赖 `.latexmkrc`、shell escape 或 `minted` 外部进程的项目不在 Beta 安全模式支持范围。
- 单文件 `chapter -> ../main.tex` 仅在 root 实际引用该 child 时自动接受；其他情况
  要求用户打开项目文件夹确认边界。
- 修改执行边界后的所有可执行安装包必须从同一 source commit 重新构建与验证。

## D015 - Project-Scoped Agent and Harness MCP

状态：Accepted
确认日期：2026-08-13

**Context**

Agent 和 Harness 需要操作 ICSTeX 的文档、Block、编译、诊断、识别和导出能力，
但 Skill 只能提供调用说明，无法强制项目边界、权限、并发冲突或执行安全；直接遥控
QWidget 也无法稳定处理未保存缓冲区和后台状态。

**Decision**

- 提供薄的本地 stdio MCP adapter；协议层不 import `app/gui`，语义与安全规则复用
  `app/core`。
- 一个 server process 固定一个 canonical project root；只接受项目相对路径并拒绝
  traversal、symlink 和非普通文件。
- 默认只读；写入、编译、联网、本地识别、raw LaTeX 与外部导入/导出权限只能由
  Harness 在启动时授予，不能由 tool 参数自我确认。
- MCP 编译除 `-norc`、`-no-shell-escape` 和有限超时外，还使用 TeX paranoid
  `openin_any/openout_any=p`，项目入口与输出以工作目录相对路径传入。
- 文档和 Block 变更使用 SHA-256/revision compare-and-swap、跨进程项目锁、原子替换
  与 byte-exact、可校验恢复的 preimage snapshot。
- OCR 只返回 `reviewRequired` candidate；Skill 负责指导调用顺序，不作为权限边界。

**Consequences**

- MCP 不遥控 GUI、不读取未保存 buffer、不提供 GUI Undo/Redo；写入期间同项目 GUI
  必须关闭或只读。
- `mcp` SDK 是可选依赖，桌面应用默认运行时不因此增加协议依赖。
- 未来扩展工具前优先增加现有语义操作，不建设 daemon 或通用插件系统。

## D016 - SDK-Native MCP Dispatch with Project-Level Concurrency

状态：Accepted
确认日期：2026-08-28

**Context**

MCP SDK 1.x 会在 server event loop 内直接执行同步工具；长时间编译会阻塞其他请求，
同根并发编译还可能覆盖活动 manager。把协议调度、线程池和取消协议重新实现在产品
代码中会复制官方 SDK 能力，并扩大长期维护面。

**Decision**

- 可选 Agent 依赖使用官方 MCP SDK 2.x；由 SDK 负责逐请求任务隔离、同步函数线程
  卸载和 legacy client 兼容，不引入独立 FastMCP 框架或以 provisional middleware
  承载正确性。
- 一个 server process 仍只绑定一个 canonical project root。多项目通过不同名称的
  stdio server 实例并行；工具参数不得切换根目录。
- 每个实例最多执行 4 个一致性普通读取；OCR 与显式网络查询各限制为 1 个。写入、
  Block 修改、编译与导出进入写者优先的 FIFO 独占队列，不与项目读取重叠。
- 编译请求在排队前登记，preview/final 的排队与执行共用既有 120/300 秒总期限。
  `stop` 绕过独占队列，停止当前 manager 并取消本进程等待中的编译。
- 编译校验、可选 Block 组装、LaTeX 执行及 artifact 发布全程持有可重入的跨进程
  项目锁；CAS、快照、原子替换、授权与路径校验继续作为权威安全边界。

**Consequences**

- 多个不同项目可并行工作，同项目读取可安全重叠，所有修改保持确定性顺序。
- 同一项目启动多个可写 MCP 进程不是支持拓扑；跨进程锁仍保护修改，但进程内读取
  门控和 `stop` 无法协调另一个 server process。
- 11 个工具、CLI 参数和 wire schema 保持兼容；SDK 的 Python 对象字段迁移为
  snake_case，预期 core 错误显式转换为 `ToolError`，未知异常仍由 SDK 隐藏。

## D017 - Read-Only File Model with Guarded Project Mutations

状态：Accepted
确认日期：2026-09-03

**Context**

文件工具箱原先只显示 `.tex`/`.bib`，打开子文件会把树根缩到子目录，且没有拖拽、
重命名、移动或明确的新窗口入口。直接把 `QFileSystemModel` 改成可写会绕过项目边界、
文件监视器、打开标签、编译 root 和 LaTeX 引用状态。

**Decision**

- 一个窗口保持一个稳定的 canonical project root；打开该项目的子文件不得改变树根，
  从项目外显式拖入的 `.tex` 使用独立窗口。
- `QFileSystemModel` 始终只读，只负责展示 `.tex`、`.bib`、常见图片和目录，并作为
  drag source；所有重命名和移动由纯 core 规则与 focused GUI controller 执行。
- 移动必须保持在项目内、不得覆盖、不得穿过符号链接或 ICSTeX 内部构建目录，并仅在
  同一文件系统内使用原子 rename。
- 操作前扫描 `.tex`、`.sty`、`.cls` 和 `.ltx` 的常见相对引用及打开编辑器的未保存
  内容。任何入站引用、会改变目标的出站引用或可识别的动态引用都 fail closed；界面
  不静默改写学生源码。
- 相关编译必须处于空闲状态；成功移动后更新打开标签、文件监视器、recent path 和
  compile/PDF ownership，旧 root 的构建授权与显示状态不迁移。
- 多窗口是受支持能力，不以性能名义禁用；窗口 registry 在关闭成功后移除对象，
  `Ctrl+Shift+N` 与文件树上下文菜单提供明确入口。

**Consequences**

- 常见未引用文件和目录可安全整理；被 LaTeX 引用的路径需先由用户修改引用，再执行
  移动或重命名。
- 图片拖入编辑器继续复用既有后台复制、冲突命名、相对路径和回滚事务，不增加平行
  导入实现。
- 暂不提供删除、批量重写引用、跨项目移动或后台文件索引；这些能力需要独立决策与
  可回滚事务设计。

## D018 - Bounded Background Analysis and Root-Owned Input Invalidation

状态：Accepted
确认日期：2026-09-08

**Context**

本地实测显示 Word Count 在 GUI 同步运行、键入时完整刷新面板，以及未打开输入
缺少监听。编译 driver 的无变化检查本已使用 latexmk 缓存；引擎替换不是证据支持的
首要优化。

**Decision**

- 自动构建统一要求用户开关和 root 会话授权。静态规则与成功构建 FLS 的输入并集
  负责依赖归属；越界、链接和内部生成路径不授予读取，删除/重建保留可观测性。
- GUI 只捕获编辑器快照和呈现结果；Word Count 后台运行，保留一个运行任务和一个
  最新请求，以 root、revision、磁盘观察与窗口生命期校验结果。缓存有界，旧值明确
  标注 pending，手动请求绕过已完成缓存。
- 面板按 dirty domain、可见性和防抖刷新，扫描先剪枝；显式完整刷新及低频复核继续
  作为可解释的修复路径。外部编辑冲突暂停自动保存，覆盖需明确确认。
- 一个 root 的编译继续串行，FINAL 不被 PREVIEW 降级；请求保留原截止时间与完整
  输入/配置身份，stop/cancel 令牌覆盖晚启动。FLS 在 worker 中捕获，Qt 延迟信号
  不得把旧构建绑定到新 revision。
- 保留 latexmk 中间产物、preview/final 输出隔离、安全参数和严格正式导出；不增加
  runtime 依赖或变更 MCP wire contract。
- 图像缓存继续核验原图与代理内容；真实可见 PDF 内容单独测量，不使用 load 调用
  耗时或 PDF 哈希替代 freshness、SyncTeX 或可见性证据。

**Consequences**

- 常规输入减少主线程阻塞，但不承诺纯 Python 统计或任意大型依赖图已实时化。
- 静态规则不解释任意 TeX 宏；追踪有上限，超限/不可读明确提示，成功 FLS 补充
  动态输入，低频复核补偿可能丢失的文件事件。
- 不改变学生源文件、既有发布制品或已安装应用；真实项目验收与发布另行授权。

## D019 - Preview Reverse SyncTeX Uses the Displayed Build

状态：Accepted
确认日期：2026-09-08
范围：取代 D012 中快速预览不开放反向 SyncTeX 的限制，其余隔离与导出规则不变。

**Decision**

- 图片代理不改写源文件，因此快速预览可复用本地生成的 SyncTeX，直接定位原始
  项目源码；不创建 shadow `.tex`，不引入路径映射清单或第二套定位数据。
- PDF 双击绑定实际显示的 purpose、root、revision、build id 与 viewer 路径，
  并要求对应记录为 CURRENT。查询前后均复核身份；同 purpose 的 worker 已启动但
  Qt 信号尚未处理时也拒绝跳转。另一 purpose 的构建使用独立输出，不自动作废当前 PDF。
- 同 revision 的新 build 仍重载 PDF，保证显示内容与该构建的 SyncTeX 一致，
  同时复用现有 page/zoom/viewport 保留机制。
- 相对输入路径从原始 compile root 目录解释；打开前拒绝项目外、符号链接、内部
  生成目录、非源码、缺失文件和无效行号。PDF 页边空白或页间隙不冒充 PDF 坐标。
- 源码到 PDF 的工具栏动作继续只接受当前 FINAL；正式导出继续只能使用当前
  revision 的原图 FINAL，preview 的可导航性不构成提交资格。

**Consequences**

- 用户可在当前快速预览中双击正文，定位 root 或 child 的原始源码，不改写文本。
- 过期、重建中、缺失工具或无可用 SyncTeX 数据时保持原位置并明确提示；任意 TeX
  宏产生的非源码位置不保证存在一对一映射。
- 不变更引擎、安全编译参数、MCP wire contract、依赖或已发布安装包。

## D020 - Opt-In Update Discovery and Verified Application Replacement

状态：Accepted
确认日期：2026-09-08

**Context**

原有桌面程序没有更新器，开发构建与公开制品共用版本标签。发布侧已具备 GitHub
Release 资产和 manifest 驱动的静态网站，可复用分发入口，但网站普通 JSON
与 SHA-256 不能独立认证可执行更新。多窗口写作和外部编译不允许直接热替换代码。

**Decision**

- 用户显式开启定期检查，下载与重启安装分别受控；默认离线和本地文件边界不变。
- 公开版本、单调发布序号和构建身份分离；dev 构建不混入公开更新渠道。
- macOS 使用 Sparkle，Windows 使用 WinSparkle 与已验收的 EXE 安装器。
  Qt 只负责中文设置、同意状态、调度和全窗口保存退出；原生库拥有 appcast、下载、
  验签和安装流程。不再实施早期自定义签名 JSON/下载器提案，不热加载远程代码。
- 发布信息来自同一已验收记录；先验证完整资产，后发布分平台/架构/渠道 appcast。
  macOS 要求签名 feed 与解压前验签且不放宽失败策略；Windows 要求 Ed25519
  payload 签名，不声称同等 feed 元数据认证，不执行 feed 提供的安装参数。
- 运行时配置和公钥随应用固定；普通源码与未配置包不可更新，默认离线。SDK 固定
  上游版本和摘要；只允许构建时显式嵌入，不从项目或运行时环境加载更新代码。
- 更新前处理全部窗口、草稿和工作进程；更新不修改学生项目、TeX distribution
  或项目格式。恢复路径必须在应用启动失败时仍可使用，不预先承诺自动回滚。

**Consequences and Acceptance Gate**

Velopack 统一跨平台方案因本轮检查到的 macOS 签名验证及失败清理路径而未采用；
证据与版本范围记录在实现说明中。保留两套薄适配器的维护成本，不自建安装引擎。

实施细则和分阶段验收见
[`update-delivery-design-2026-09-08.md`](update-delivery-design-2026-09-08.md)。
各平台须通过签名、唯一制品身份、目标绑定、保存取消、真实安装与失败恢复验证，
才能开放自动安装。客户端源码完成不等于线上升级已启用；本条不授权发布、
创建密钥、替换安装版或触发 GitHub Actions。维护者接入见 `packaging/UPDATES.md`。
