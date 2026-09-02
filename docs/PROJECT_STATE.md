# ICSTeX Project State

更新时间：2026-09-03（Asia/Taipei）

本文件是当前已验证状态的权威来源；历史证据写入 `PROJECT_LOG.md`，未来计划写入
`docs/ROADMAP.md`，长期约束写入 `docs/DECISION_LOG.md`。

## Product and Source State

- 权威工作区：本仓库根目录；已验证开发线 `codex/icstex-mcp` 已本地合入
  `release/2.1`，尚未推送或重新打包。
- 当前版本：`2.1.0-beta.1`；版本来源为 `app/__init__.py`。
- 技术栈：Python 3.11+、PySide6、本机 LaTeX distribution、PyInstaller。
- 产品边界：中文优先、本地文件与本地编译优先、不静默上传用户内容、不捆绑
  MacTeX、TeX Live 或 MiKTeX。
- `v2.1.0-beta.1` 已作为公开 GitHub prerelease 发布；`release/2.1` 包含后续网站
  发布态元数据提交，版本制品仍由该标签固定。
- 静态官网现在包含首页、`website/guide/` 使用指南和 `website/about/` 理念页；
  版本与下载展示仍由 `release-manifest → release.json → app.js` 单向驱动。
- 公开发布候选已加入默认拒绝的本地执行边界；旧安装包早于该修复，必须重建。

## Verified Capabilities

- Source/PDF 双栏、root-scoped 编译与 freshness、SyncTeX、Word Count、诊断、
  原子保存和正式 PDF 导出。Word Count 的 TeXcount 路径使用 Unicode
  `Ideographic` 属性避免把中文标点计为汉字；本地结构化路径按可见文本连续分词，
  支持 `%TC:ignore`、重复 include、循环保护、脚注和扩展区汉字。
- 源码编辑器的命令补全以弹窗当前高亮项为准；上下键切换后，Enter 或 Tab 不再错误
  插入首项。普通源码模式的图片布局支持左右、上下和 2×2 田字排列，每张图可独立
  设置宽度且只按宽度等比缩放；同排总宽度受限，批量图片复制失败会整体回滚。
- 隔离的快速图片预览与原图正式构建链；preview 不得成为正式导出源。
- Block 项目控制台、ProjectSession、统一 Undo/保存/编译、表格与布局 Block。
- Formula Editor 2.0、显式提交、危险 LaTeX 过滤、可选本地 pix2tex 识别与人工复核。
- UI Scale 90/100/110/125/150%、响应式欢迎页、标签栏和 PDF 工具栏。
- RapidOCR 本地运行时和 Text Block 链路保留在源码中，但 2.1 Beta 1 用户入口禁用。
- 当前工作源码提供项目绑定、默认只读的 stdio MCP adapter 与配套
  `icstex-control` Skill。官方 MCP SDK 2.x 负责并发请求和同步工具线程卸载；core
  协调器将同项目普通读取限制为 4 路、OCR/网络各 1 路，并用 FIFO 独占队列串行化
  写入、编译和导出。文档/Block 写入继续采用 CAS、跨进程项目锁、原子替换和原始
  字节快照；完整编译/导出临界区持有项目锁，`stop` 可越过队列停止当前并取消本进程
  等待中的编译。11 个工具、授权参数、枚举 schema 与行为注解保持兼容。

## Verification Baseline

2026-08-08 安全边界修复后的已发布基线：

- `bash packaging/preflight.sh`：通过。
- `python3 -m compileall -q app tests packaging/install_build_dependencies.py`：通过。
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests`：731 tests passed。
- `bash tools/run_mvp_ci.sh`：72 项模块化子集、716 项完整套件与 Demo 构建通过。
- macOS arm64 打包应用冷启动与 Demo source-to-PDF：已验证。

2026-08-28 MCP 2.x 与安全并发工作源码验证：

- `python3 -m compileall -q app tests packaging/install_build_dependencies.py`：通过。
- 可选 Agent 环境安装 `mcp 2.1.1`；`python3 -m pip check`：通过。
- MCP/并发/编译/安全 focused suite：77 tests passed。
- 真实 stdio current/legacy initialize/list/call 握手：通过；11 个语义工具、行为注解、
  枚举 schema、ICSTeX server version 与预期错误透传均已验证。
- 并发测试覆盖 4 路读取上限、写者优先、FIFO 独占、两个项目并行编译、同项目串行、
  `stop` 越队停止/取消，以及两个 Python 进程竞争同一 CAS 写入。
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests`：779 tests passed，
  包含本机 TeX Live 与 GUI offscreen 回归。
- `icstex-control` 官方 `quick_validate.py` 与 repository/global Skill 内容比较：通过。
- 当前机器的 pix2tex/RapidOCR 隔离 Python 未安装，因此真实 OCR 推理仍未验证。

2026-08-29 Word Count 准确性修复验证：

- GitHub 上游核对覆盖 TeX Live 的 TeXcount、Overleaf 服务端/本地结构化计数实现及
  pylatexenc 自定义解析规则；未引入新依赖或复制第三方代码。
- 真实 TeXcount 3.1.1 验证中文标点、数字和扩展区汉字；TeXcount 与本地结构化路径
  对重复 `input` 的正文/数字分类一致，循环项目不再等待 TeXcount 超时。
- Word Count focused suite：32 tests passed；Word Count、Environment Doctor 与 GUI
  focused suite：156 tests passed。
- `python3 -m compileall -q app tests packaging/install_build_dependencies.py`：通过。
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests`：787 tests passed。

2026-09-03 编辑器补全与普通模式图片布局验证：

- 复现 Qt 补全状态分离：弹窗已高亮 `\\textit{}` 时，旧
  `QCompleter.currentCompletion()` 仍返回 `\\textbf{}`；修复后 Enter/Tab 从 popup
  当前索引读取候选。
- 图片布局覆盖左右、上下和 2×2 田字排列、逐图宽度、行宽上限、等比缩放、资源复制
  回滚及 package 插入；真实 XeLaTeX 2×2 非等宽布局编译通过。
- 默认与 150% UI 缩放的 offscreen 视觉检查通过；150% 下对话框为 934×689，字段和
  浏览按钮无横向裁切，超高内容使用纵向滚动。
- 编辑器/图片 focused suite：146 tests passed。
- `python3 -m compileall -q app tests packaging/install_build_dependencies.py`：通过。
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests`：796 tests passed。
- 未打包、未发布、未推送，也未触发 GitHub Actions。

该源码尚未重新打包或发布，不改变 2.1.0-beta.1 制品状态。

## Release Matrix

| 对象 | 状态 | 说明 |
| --- | --- | --- |
| 当前源码 | Verified, source ahead of packaged release | 2.1.0-beta.1；796 tests passed；已本地合入 `release/2.1`，未打包/推送 |
| macOS arm64 DMG/ZIP | Verified, rebuilt | hardened source；ad-hoc signed、未 notarize |
| clean source ZIP | Verified, rebuilt | hardened source；publication hygiene scan passed |
| Windows ARM64 ZIP | Verified beta artifact, rebuilt | Windows-local `C:\w3`；无系统 Python 启动通过 |
| Windows x64 ZIP | Pending | 当前构建机和 Python 均为 ARM64 |
| Windows x64 Setup EXE | Blocked by tools | 需要 x64 构建环境和 Inno Setup |
| Windows TeX acceptance | Blocked by tool | 构建机尚未安装 MiKTeX/TeX Live |
| Static release website | Public Vercel production deployment | `website-phi-beryl-92.vercel.app`；首页 + Guide + About；production READY，SSO Protection 已关闭；presentation refactor and 12 focused tests verified |
| GitHub repository / Release | Public / published prerelease | `v2.1.0-beta.1`；9 个资产；公开下载端点已匿名验证为 HTTP 200 |

旧的 `dist/ICSTeX-Windows.zip` 未版本化且早于当前源码，不是 2.1.0-beta.1 制品。

## Architecture and Non-Regression Boundaries

- 纯解析、状态、路径、诊断和文本规则留在 `app/core`；PySide6 编排留在 `app/gui`。
- `MainWindow` 保持兼容门面，通过 focused controllers 和 ProjectSession 渐进演进。
- 保存或编译不得移动光标或滚动位置；同文档 PDF reload 应保持 page/zoom/viewport。
- 编译前 flush 当前内容；失败 build 仅能显式保留 stale PDF。
- build id、source revision 和 normalized compile root 决定结果归属；后台结果不得覆盖
  当前无关标签页。
- PREVIEW 与 FINAL 使用独立路径和状态；正式导出只接受当前 revision 的 FINAL PDF。
- 严格解码与同目录原子替换保护用户文件；相对项目路径优先。
- 缺少 Python 或 LaTeX toolchain 时，打包应用必须仍能无阻塞启动并给出明确诊断。

## Current Risks and Immediate Work

- Windows ARM64 ZIP 已在 Windows-local `C:\w3` 从 hardened source ZIP 重建；
  Python 3.12.10 ARM64，移除系统 Python PATH 后的打包应用启动验收通过。
- Windows x64 ZIP/Setup 仍未生成；不能把 ARM64 包改名或宣称为通用 Windows 包。
- 构建机缺少 Inno Setup，因此 x64 Setup EXE 不能在未补齐构建环境时生成。
- Windows 构建机缺少 MiKTeX/TeX Live，因此不能把 source-to-PDF 记为已验证。
- Git 历史已重写；公开远端的提交信息与可达提交内容扫描均无维护者
  `/Users/leo.xu` 路径，当前源码 tree 在重写前后保持一致。
- GitHub Actions 在发布写入期间临时禁用，推送没有运行 CI；发布完成后恢复原配置。
- macOS 仅验证 Apple Silicon，且未 Developer ID 签名或 notarize。
- 2.1 是 Beta；公式 OCR 结果必须人工检查，重要项目仍需外部版本备份。
- 字数统计是可审计的源码级统计，不等同所有课程的提交口径；标题、说明/脚注、公式
  和数字已分层显示，最终纳入范围仍须按对应课程要求判断。
- 多项目并发使用不同名称、不同根目录的 stdio 实例；同一项目同时启动多个可写 MCP
  进程不是受支持拓扑。跨进程锁仍保护写入/编译，但读取一致性与 `stop` 取消只由单个
  server process 内的协调器保证。

公开 Beta 已如实排除 Windows x64/Setup，并保留 Windows ARM64 与 macOS 的既有
限制。后续仍需补齐 Windows x64 构建机、Inno Setup、Windows TeX 验收和 macOS
notarization；在新的 bounded assignment 前不向该 Release 追加产品功能。

## Maintenance Rule

只有验证后的事实才写入本文件。命令、哈希和任务过程追加到 `PROJECT_LOG.md`；
尚未接受的设计保留在 roadmap/decision log，不写成当前能力。
