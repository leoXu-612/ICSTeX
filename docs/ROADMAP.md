# ICSTeX Roadmap

更新时间：2026-09-03（Asia/Taipei）

本文件描述产品与技术路线，不是功能愿望清单。每个进入实施的项目都必须
同时满足用户价值、稳定性、可维护性和可验证性要求。

## North Star

ICSTeX 要成为 ICC 学生从“建立写作项目”到“提交可靠成果”的本地科研写作
基础设施。核心成功标准不是功能数量，而是学生能否更少出错、更快定位问题，
并确信最终 PDF 与当前源码一致。

## Priority Rules

新工作按以下顺序判断：

1. 保护学生论文和交付文件不丢失、不被意外覆盖。
2. 保证编译、PDF、字数和引用状态真实可信。
3. 降低 LaTeX 环境、项目结构和错误诊断的学习成本。
4. 支持 IA、EE、实验报告等完整工作流，而不是增加孤立按钮。
5. 在没有明确学生价值时，不引入新的状态、依赖、网络或维护负担。

## Now - Establish a Clean Release Boundary

目标：把已验证源码变成可解释、可复现、跨平台一致的下一版本。

- 建立并执行新的项目状态、路线图、决策和记忆管理规范。
- 冻结已验证的双保真 preview/final、正式导出与图片缩略图 source delta；仅收口
  已确认的编辑阻塞问题、普通模式左右/上下/2×2 图片布局和高频命令补全，不继续
  扩展为自由画布或通用语言服务器。
- 收口项目文件工具箱：稳定项目树根、展示论文与图片资源、支持 `.tex` 拖拽/新窗口、
  图片安全拖入，以及项目内受控重命名和移动；不加入删除或静默引用重写。
- 确认截至 2026-08-01 的 post-0.2.7 source delta 发布版本；推荐 `0.2.8`。
- 同步 `app/__init__.py`、`pyproject.toml`、packaging metadata、README 和 CHANGELOG。
- 重新生成并验证 versioned macOS DMG 与 clean source archive。
- 在 Windows-local path 构建同版本 ZIP/installer，并验证：
  - 无系统 Python 时可启动；
  - UI 报告正确版本；
  - 能检测 MiKTeX 或 TeX Live；
  - 基础 source-to-PDF 流程成功。
- 保持已通过 WEB-001～004 的静态官网及其 Release 数据完整性；任何公开 Pages
  部署仍需维护者明确批准并执行受保护的发布流程。
- 从 2026-08-01 verified source state 起只处理 release blocker。

完成条件：源码、文档、macOS artifact、Windows artifact 和版本号一致，且
`docs/PROJECT_STATE.md` 已记录最终验证状态。

## Next - Submission Readiness

目标：用已有能力组成第一个真正的“科研写作基础设施”纵向工作流。

建议提供一个本地、确定性的提交前检查视图，组合：

- 当前源码是否已保存；
- 最新 compile root 是否成功编译；
- 当前 PDF 是否为最新版本；
- Word Count 数值、目标范围和统计模式；
- 未解析 citation/reference/label；
- 缺失图片、BibTeX 文件和常见 package；
- toolchain、encoding 和 build environment 状态；
- 最终可交付 PDF 路径与生成时间。

实现原则：优先复用 `word_count`、`diagnostics`、`pdf_state`、`paths` 和
Environment Doctor，不另建平行状态系统。

完成条件：学生能够在一个入口判断“这个项目现在是否可以提交”，所有失败项
都有可解释的来源和安全的下一步。

## Next - Project Session Boundary

目标：降低 `MainWindow` 的共享状态复杂度，但不重写稳定 GUI。

- 先定义最小的 project/session state：compile root、open documents、source
  revisions、PDF record、compile manager 和 project profile。
- 一次只迁移一个现有工作流，并保留兼容门面。
- session model 不直接持有 QWidget；Qt signal wiring 继续留在 GUI 层。
- 每次迁移都必须有针对多标签页、root/child 和后台编译的回归测试。

该方向目前是 architecture proposal；开始实施前应在
`docs/DECISION_LOG.md` 中转为 Accepted decision。

## Candidate - Source-First Formula Composer

目标：让学生用二维结构和键盘高效构造公式，同时保持 LaTeX 源码可见、可复制、
可撤销且不被静默改写。

该候选不覆盖 clean release boundary 或 Submission Readiness 的优先级。首个
DeepSeek assignment 只实现纯 core contract；GUI、MathLive/QtWebEngine、package
注入和文档写入必须在后续独立 slice 中评审。

分阶段条件：

1. 纯 Python wrapper/parser/template/edit-plan 规则与异常输入测试通过。
2. 本地可视技术原型通过 macOS/Windows 制品、离线、内存、IME 和许可证检查。
3. 插入/替换是一次 Undo；Cancel 零修改；revision 冲突拒绝覆盖。
4. 未知宏和复杂环境可无损退回源码模式；最终正确性仍由正式编译确认。

长期边界和 promotion gate 见 `docs/DECISION_LOG.md` D013。

## Later - ICC Academic Profiles

目标：以数据驱动方式支持不同学术项目，而不是把学科规则硬编码进 GUI。

候选能力：

- IA、EE、实验报告和课程论文的 project profile；
- 声明式模板、建议目录、字数目标、默认 engine 和 readiness rules；
- 本地 milestone/checklist；
- 可导出的项目健康报告，便于教师或技术支持排查环境问题。

所有 profile 必须可编辑、可禁用，并明确区分“技术检查”和“学术评价”。

## Distribution Improvements

在用户需求和发布资源允许时评估：

- Windows 持续验证环境；
- macOS Developer ID signing / notarization；
- Intel 或 Universal 2 macOS 支持；
- 更清晰的安装和 LaTeX distribution onboarding。

这些工作不能通过降低构建可复现性或隐藏安全警告来完成。

## Explicit Non-Goals

以下方向当前不进入路线图：

- 将 ICSTeX 变成云端编辑器；
- 静默上传论文、日志或引用数据；
- 默认开启 AI 自动改写或自动修改学生正文；
- 在安装包中捆绑完整 MacTeX、TeX Live 或 MiKTeX；
- 直接编辑 PDF 或从 PDF 反向生成 LaTeX；
- 在没有明确扩展需求前建设通用插件系统；
- 为增加功能数量而复制 Overleaf 或大型 IDE 的全部能力。

## Delivered - Agent / Harness MCP Boundary

本地 stdio MCP 已提供项目检查、文档 CAS 读写、搜索/诊断/字数/引用/SyncTeX、
Block CRUD/布局/主题/来源/组装、受限编译、本地 OCR candidate、DOI/arXiv 元数据和
受权目录导出。协议调度复用官方 MCP SDK 2.x；同项目读取有界并发，修改/编译/导出
保持 FIFO 独占，不同项目通过独立命名实例并行。Skill 只描述正确工作流，权限、
路径与并发保护由 core 强制。

后续只在真实工作流缺口出现时增加语义能力；不加入 GUI 遥控、后台 daemon、任意
文件系统访问、Agent 自授权、OCR 自动落盘或通用插件系统。

## Delivered - Guarded Project File Toolbox

文件树以每个窗口的 canonical project root 为稳定边界，展示 `.tex`、`.bib`、常见
图片和子目录。`.tex` 可双击或拖拽打开，并可从上下文菜单进入独立窗口；图片拖拽
复用现有安全导入事务。文件模型保持只读，重命名和移动由项目级控制器检查越界、
重名、符号链接、编译占用及 LaTeX 相对引用后执行。被引用路径 fail closed，不自动
改写论文源码。

## Feature Admission Checklist

进入实现前必须回答：

- 它解决哪个具体学生任务或风险？
- 能否复用现有状态和模块？
- 失败时是否会损坏、误报或泄露用户内容？
- 是否可以用纯规则或本地工具完成？
- 如何验证正确性和非回归？
- 它增加的长期维护成本是否低于用户价值？

无法回答以上问题的功能停留在 idea，不进入 active assignment。
