# ICSTeX Project State

更新时间：2026-09-20（Asia/Taipei）

本文件是当前已验证状态的权威来源；历史证据写入 `PROJECT_LOG.md`，未来计划写入
`docs/ROADMAP.md`，长期约束写入 `docs/DECISION_LOG.md`。

## GitHub Workflow State

- main requires a PR, resolved conversations and squash merge; approvals=0, no bypass,
  force-push or deletion. Actions remains disabled, with no required status checks.
- PR/Issue templates and CONTRIBUTING.md from remote main are preserved. Existing
  cancellation, cache-release and CRLF/privacy fixes are included in this integration.
- Current integration combines accepted local source a5451d8 with main 69ca0b6;
  the previously merged feature head 44eecb8 is an ancestor of the local source.

## Product and Source State

### Beta 4 published: GitHub, production website and signed feed (2026-09-20)

- Integrated accepted local source a5451d8 with remote main 69ca0b6, retaining PR/Issue
  templates, disabled Actions and main's cancellation, cache-reader release, CRLF/save-echo
  and portable redaction fixes. Shared original feature head 44eecb8 is an ancestor of the
  local source; it supplied the content merge base for the squashed main history.
- Published identity is 2.1.0-beta.4 / 210004, macOS arm64 only. PR #4 merged source into
  main at 4ea00ff; PR #5 froze the identical tree into release/2.1 at 79fcd86. Tag
  v2.1.0-beta.4 points to that release commit. Installed local Beta 3 remains unchanged.
- GitHub Release is public (prerelease, not draft), with both DMG/ZIP and six release documents.
  Anonymous ZIP download is 57188923 bytes, SHA256
  170696e77b5eca6b09fefe3bb4cdab95d2c4862c9ebe56589811220e4e01aa6a, identical to the
  signed local artifact. DMG endpoint returns 200/65672242 bytes; GitHub's digest matches
  cfcffab1e0b80f7c78df49fd953d4c4d213ab138a2735862306a9f7ed2821c94.
- Final preflight passed 1843 tests / 321.019s, command 322.704s, exit 0. App digest
  ca778fe504893584d5fe6ece318876062b450268b8f662147832725e40dfebe6 and app+tests
  7a6d2aa5d84295cff71a56731ba45fe3e284707317666a5cdf73e1b3d96aafaf were unchanged.
  Initial integration exposed outdated class-wide PDF loader mocks; current valid-PDF
  fixtures retain the real reader/identity checks and fail-fast modal guard. No assertion relaxed.
- Candidate bundle matches 209 modules/entry and resources; arm64 ad-hoc integrity, ZIP CRC,
  DMG verification and archive signing passed. Executable SHA256:
  7437b0af923d2362d6285aa2ff42ec267d08e1711e424e324aee8887712baf95.
  No Developer ID/notarization claim. Human Keychain authorization completed; archive and
  appcast Ed25519 signatures independently verify against the existing embedded public key.
  Feed digest is 2300e564f8760b2847de848ee68697928df3d0d210314dc3b2bdd482aff3a352.
  Release metadata consistency and all 17 website tests passed. Public HTTPS feed/archive
  were downloaded anonymously and independently reverified; the old embedded feed URL and
  public key are unchanged, and 210004 is greater than installed 210003.
- Vercel production deployment dpl_3rSnXMYS45Ke5Leo1Gc5eT9ZYFdX is READY. Both
  https://ics-tex.vercel.app and the old website-phi-beryl-92.vercel.app alias point there.
  The website visibly shows Beta 4 and correct DMG/ZIP hashes/links. Live release.json and
  appcast bytes match the checked-in files; feed returns HTTP 200/application-xml with
  max-age=0,must-revalidate. Actions remains disabled; there is no Git-triggered site deployment.
- Collaborator's automatic discovery/download/install/restart remains pending actual other-device
  testing. Beta 3 users must opt into automatic checks; startup defers 30 seconds and a recent
  attempt has a 5-minute cooldown. Checks defer during modal dialogs/compilation/export.
  Download and installation still require confirmation. A manual check is a diagnostic fallback,
  not proof of the automatic path. No Windows or Apple-notarized claim.
- Evidence is under the local icstex-beta4-release directory: preflight-final/result.json,
  package-receipt.json, signed-package-receipt.json, public-check/verified.json and build.log.
  Existing Qt/temp-path and libobjc build warnings remain. Old assets, tags and app are preserved.

### 当前安装版：公式导航与显示留白（2026-09-20）

- 用户已确认上一公式导航包功能可用，要求增大符号左右/上下间距并直接替换本机。
  本轮只改 MathEditorWidget 显示：字符额外字距 1.2、结构间隔 4、画布边距 16；
  分式横线两侧各留 5，上下标横向留 5，上下限与运算项留白。上下标按实际测量的小字号
  绘制，大运算符不再重复绘制；嵌套结构的整体高度覆盖全部子项，点选复用绘制布局。
  不改 LaTeX、Undo、编译命令或 PDF 排版，不恢复手写入口/模型。
- 76 项公式/GUI 专项通过，新增文本点选、几何边界、字号、宽上下限与源码保护检查；
  离屏前后图确认间距变化。第一轮 preflight 在发现深层分式上标高度不足后主动中断
  （108.797 秒、退出 130），保留收据；补齐高度与回归后冻结源码。
  最终 preflight 包含 compileall 和完整 1840 项：332.194 秒，命令 333.972 秒、退出 0。
  前后 app `fd584fd58c9b317589a99aad662060821279458bb9aad83f80dced6031642e6c`，
  app+tests `562981f4297cdebc93efada83db4e35f72eeabee725740329d872fd3a4a4650d` 一致。
- 新包 209 个模块/入口、所有资源及三个 raw worker 源文件与源码匹配；arm64、ad-hoc
  deep/strict 签名通过，不声称 Developer ID 或公证。通过既有 InstallationLease 备份
  并替换 `/Applications/ICSTeX.app`，475 个文件和 160 个链接逐项匹配候选。
  新程序 SHA256 为 `0e06c53d4b8ef6e944f9c1468e1b5b490cb5d827f0c20005ec51dab86d2332ab`。
- 旧包完整保留在
  `~/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.3-before-formula-spacing-20260920.app`，
  摘要仍为 `d8c0d3c3...286`，文件/链接与替换前一致。保留 Beta 3/210003 标签与更新器，
  这是本地构建，不修改公开 feed/官网/Release。未升级依赖、启用 CI、提交或推送。
- 原生从正式安装路径打开，并在未保存草稿中观察上下标、分式与求和间距；取消公式后
  源码未应用变换，退出时选择不保存该临时草稿，再打开留在欢迎页。未打开学生文稿、
  保存或编译。原有非无损结构源码回退仍生效，不将本轮称为任意公式转换支持。
  证据根 `~/.codex/visualizations/2026/09/20/icstex-formula-spacing/`：前后图、
  preflight-final-v2/result.json、package-receipt.json、install-receipt.json；原生图见本次工具记录。
  Qt/字体/临时目录异步诊断、旧制品提醒及 libobjc ctypes 构建警告保留。

### 上一公式导航测试包：功能已获用户确认，间距由上节改进（2026-09-20）

- 已从下述有效源码生成独立 arm64 ZIP，位于
  `~/Downloads/ICSTeX-2.1.0-beta.3-formula-20260920-753b785b-macos-arm64.zip`，
  57337682 字节；包含应用、三条公式测试样本和中文验收步骤。不含手写入口或模型。
  界面标签仍为 Beta 3/210003，日期/源码标识用于区分本地包，不是新的公开版本。
- 本次 preflight 完整通过：1835 项/329.458 秒，命令 331.362 秒、退出 0；app
  `753b785b`、app+tests `a54004d6` 前后不变。沿用现有依赖和 PyInstaller spec；原
  Sparkle runtime 暂存目录已不存在，从签名完整的安装版复用相同组件与公开配置，
  未下载 SDK、改变原包或更新源。对应 native 源码没有修改。
- 209 个模块/入口、资源与当前源码匹配，既有打包模块未丢失；新增三个 raw worker
  源文件也逐字节核对。arm64、ad-hoc deep/strict 和 ZIP CRC 检查通过；未做
  Developer ID 签名或 Apple 公证，未把结构核验当作原生公式操作验收。
- 新程序 SHA256：`4d0b5206e8f73fe1de76dff110bfe29db54373ada09d2a4d0d9aa68167a2a46d`；
  ZIP SHA256：`f90f8faeb86e14d8057bea500ad60f74876fb93b2deee93cd6f036dc89243eee`。
  证据根 `~/.codex/visualizations/2026/09/20/icstex-formula-preview-package/`。
  Qt/临时目录诊断、旧制品提醒与 libobjc ctypes 构建警告保留。
- 此阶段只提供本地下载包；后续用户确认功能可用，并授权上节间距优化与安装。
  该 ZIP 保留为导航测试包，不代表当前安装版的间距修复。

### 公式导航与手写撤回基线（2026-09-20）

- 修正 ↑/↓ 在上标、底数、下标之间的方向，支持邻接结构、分子/分母、求和/积分
  上下限以及从内层根式返回外层分式；按显示位置就近放置横向光标。左右退出结构
  使用真实光标边界，不再把节点编号当字符位置；进入结构立即重画光标。
  编辑区显示“光标在：上标/分母”等提示。导航不创建槽位、不改 LaTeX 或 Undo。
- 手写模型未达到可用性门槛，按用户要求撤回“手写公式…”按钮、画板实现与专用测试，
  不保留面向用户的半成品入口。全部手动公式编辑、草稿确认、编译和 PDF 功能保留。
  原有“图片识别…”不变；本轮保留的 OCR 修复包括模型清单验证、指定 Python 建立
  venv、取消后 worker 重启、STARTING 通知顺序、绝对 worker 入口与导入时禁止联网。
  spec 只增加三个小 worker 源文件，不捆绑模型；隔离启动测试不等同新安装包验收。
- 本机既有 pix2tex 可选环境保留在
  `~/Library/Application Support/ICSTeX/optional-tools/pix2tex/`，约 1.4 GB。
  独立 UniMERNet 评测环境与两档权重已清理：删除前目录分配 2699856 KiB（约
  2.6 GiB），路径与仅有 model/model-small/venv 三个子目录均已核实，没有活动评测进程。
  不清理共享缓存、系统 Python、安装包或学生文稿。脚本、样本、结果、版本与摘要保留。
- 当前撤回专项：109 项/2.201 秒、退出 0；compileall 与完整 1835 项回归通过，
  测试 461.291 秒、命令 463.559 秒、退出 0。前后 app 为
  `753b785b804cab09874c815795153480a33aaf8840db64f3e8392770b927225e`，app+tests 为
  `a54004d6f238170877e9c460766531d989b9c2474e60f6405084500ba591b891`，身份一致。
  保留 Qt 字体/离屏、临时目录异步读取及专项的一次模拟 worker 退出期 QProcess 诊断；
  不声称零警告或原生界面验收完成。
- 本轮证据：`~/.codex/visualizations/2026/09/20/icstex-handwriting-withdrawal/`，
  包含撤回前小范围源码快照、清理记录及最终回归收据。原公式导航/图片 OCR 证据仍在
  同日 `icstex-formula-input/`；旧手写流程证据仅表示历史试验，不是当前提供的功能。
- 当前分支 `codex/formula-navigation-handwriting`、HEAD `2d36956`，保留未提交有效工作。
  后续本机安装已包含方向键与留白改进，见顶部；可选 OCR 安装按钮的打包引导仍未验收。

### 已结束的本地手写评测：不采用新后端（2026-09-20）

- M3/16 GiB，官方 UniMERNet Tiny CPU FP32、Tiny MPS FP16、Small CPU FP32，
  单进程/批次 1、CPU 4 线程。Tiny 完整加载 107402740 参数，FP32/FP16 张量为
  409.71/204.85 MiB；Small 为 202454766 参数、772.30 MiB。无裁剪、无按题型激活。
- 官方 MathWriting excerpt 的全部 100 条 human/test 笔迹先冻结 Qt 栅格化输入；
  规范化整式匹配为 6/6/7，另 3 条生成鼠标笔迹为 2/2/1。扩大同系列模型没有使题型
  达到预设门槛。这是本地渲染子集结果，不是模型总体准确率；根号/矩阵样本不足，
  求和/积分无样本，不作能力承诺。关闭编辑器按钮不能减少密集模型的对应权重。
- 热推理中位数为 0.603/0.393/0.901 秒，P95 为 0.856/0.947/1.338 秒；峰值 RSS 为
  1333.92/1052.73/1882.25 MiB。MPS 驱动分配采样峰值 1140.13 MiB，不能与 RSS
  作为独立显存相加。这不是 GUI 端到端延迟。309 次无异常或输出截断，但质量不通过。
- 证据保留于 `~/.codex/visualizations/2026/09/20/icstex-local-model-eval/REPORT.md`，
  `inputs.json`、原始结果与 `scored-results.json`；固定模型 revision/checkpoint 摘要
  和逐图摘要可复核。评测环境已移除，不再下载更大模型、调参、训练或接云服务。

### 已交付本机的快速预览双向定位与源码目标高亮（2026-09-19）

- 源码“定位 PDF”现在接受当前显示且最新的 PREVIEW 或 FINAL；复用原反向定位的
  root/purpose/revision/build-id/viewer 校验，不增加定位系统、依赖或编译。刚打开的
  子文件无需先创建编译管理器；源码标签、文档 revision 与光标在查询后重新核对。
- 窄布局会显露 PDF，再延后一轮布局复核并跳转。过期、同 purpose 的待完成构建、
  缺失文件、越界页码和非有限坐标不导航；源码和 PDF 阅读状态不被无效结果移动。
  单次动作刷新复用 root/文件观察，实际点击重新验证；FINAL 交付规则不改变。
- 用户已验收上一版正向预览定位（app6019e056），随后追加双击 PDF 的目标高亮。
  现在成功反向定位会显露源码，并以淡黄色高亮返回的源码行约 2 秒；移动光标、编辑
  或隐藏编辑器即清除。复用 ExtraSelection 和单次计时器，不选中文字、不改正文/
  撤销记录，保留搜索高亮；打开失败/取消不会高亮其他文件。行级映射不保证逐字对应。
- 正向定位原有回归保留；高亮新增 3 项回归并扩展既有真实预览用例。实际 pdfLaTeX/SyncTeX 编译验证
  子章节、代理图片、0.9/1.25 缩放及窄写作区正向定位到第 2 页，既有反向定位保留；
  没有额外编译或 FINAL 产物，源码字节与光标保持。离屏 Qt 截图已观察实际目标文字。
  高亮截图在两档缩放下均显示正确子文件第 2 行，每张有 10713 个目标背景色像素。
  这些是隔离离屏检查，不替代原生 Mac 操作或学生试用结果。
- 最终本地 preflight 包含 compileall 和完整回归，1823 项/709.960 秒，命令
  715.424 秒、退出 0，前后身份一致。app 为
  `180277afaf1f5111e65271641ed473ed48daa0ec1d3f87e5ceb2f44cab8facf2`，app+tests 为
  `d30da6034a20d16671e8dd672564c27d3f136dd59f3310b1efbd21c03b5ded33`。
  Qt/字体/临时目录异步读取诊断保留，不声称零警告或整体编译性能提升。
- 最新证据根 `/Users/leo.xu/.codex/visualizations/2026/09/19/icstex-sync-highlight/`：
  `preflight-final/result.json`、`visible-result.json`、`source-highlight-1.png`。
  正向定位原证据在同日 `icstex-preview-forward-sync/`，不将其旧源码结果冒充新结果。
  `V1_RELEASE_READINESS.md` 已标为旧阶段快照；D019、导引和路线图同步当前边界。
- 用户已明确确认完整有效源码（含此前未提交依赖），已作本地阶段性提交 `2d36956`，
  分支 `codex/preview-forward-synctex`；不将历史功能全部归属本轮高亮。未运行 CI、推送或
  公开发布；本地分支不等同远端 main，后续集成须按实际差异审查。

### 先前本机安装版：定位高亮（2026-09-19，已备份）

- 用户保存退出后，已通过既有 InstallationLease 排除运行实例/安装器，保留旧包并
  安装 `/Applications/ICSTeX.app`。包含上节高亮、预览正向定位、工程 ZIP 与此前教程。
  仍用 `2.1.0-beta.3 / 210003` 标签，以日期/源码摘要标识本地包，不改公开版本元数据。
- 新包的 208 个模块及入口、全部资源匹配当前源码，未丢失旧包模块；12 个不被 GUI
  引用的既有独立模块仍未打包。arm64、ad-hoc deep/strict 完整性通过，不声称公证。
  程序 SHA-256 为 `d8c0d3c327ebbeb631d40749f7ac6bb7a0349fbf79afff9569aef34f9f9a0286`。
  安装副本的 472 个文件和 160 个软链接逐项匹配候选，更新器及原偏好保留。
- 原生已从正式路径重新打开，欢迎页环境就绪与“定位 PDF”提示已观察；未打开或改写
  学生文稿。本次高亮动作的可见证据是上述离屏真实编译检查，不冒充原生动作验收。
- 旧版完整备份为
  `/Users/leo.xu/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.3-before-synctex-highlight-20260919.app`，
  旧程序摘要 `5e46d205...fda1` 不变，全部备份内容与原件一致。安装/包收据和唯一命名的
  `ICSTeX-2.1.0-beta.3-local-20260919-180277af-macos-arm64.zip` 在本次高亮证据根。
  保留构建的 libobjc ctypes 提醒和 preflight 的旧制品提醒；没有升级依赖或重测更新矩阵。

### 已实现的工程文件导出（2026-09-17）

- “文件 → 导出为工程文件…”整理项目内的源码、图片、CSV/XLSX/DAT 等表格数据、
  BibTeX、本地样式及项目元数据，展示可勾选清单后生成普通 ZIP。解压所得 `project/`
  保留原始相对路径和字节，根目录说明标出真实主文件；不要求 FINAL/PDF 或自动编译。
- 复用既有候选筛选、冻结读取、依赖扫描、CaptureLease 与独占文件发布。未保存草稿/
  外部冲突先处理；取消和输入变化不发布 ZIP，已有目标不覆盖。项目配置等已识别依赖
  被取消勾选时提示。未纳入项目外路径、链接、历史、缓存、脚本和不支持的类型；
  不自动改写绝对路径。缺失/动态引用可显式确认只导出现有文件，提示保留在包内。
- 沿用单文件 64 MiB、总原始输入 256 MiB、2000 文件上限。仅导出本地文件，不上传、
  不收集系统字体/TeX 环境；没有新增依赖或专用导入格式。原 FINAL 提交流程不改变。
- 新增 11 项核心/GUI 回归均由最终完整测试覆盖；原有导出/提交/检查点专项 55 项通过。
  独立真实 Qt 离屏操作已核验清单、成功状态、解压字节与原件不变。移动原目录后，
  解压副本的图片、CSV 表格、子章节、本地样式与 BibTeX 经过真实 pdfLaTeX/latexmk
  编译，PDF 71168 字节，引用输出核对通过。这不是异机 Windows 或原生学生验收。
- compileall 通过；完整回归 1814 项/306.702 秒，命令 308.180 秒、退出 0，身份不变。
  app 为 `5834af3e055fc3f6f174b18c8724dacb58c0ada596104e2a42b5111ab495fd1e`，
  app+tests 为 `decca1518e8b6f36dceae3127ab6773493700f28f56a3c24837c4e164128e689`。
  Qt/字体提示和临时目录异步读取诊断仍保留；没有声称所有历史问题已解决。
- 证据根 `/Users/leo.xu/.codex/visualizations/2026/09/17/icstex-project-archive/`：
  `full-final-v2/result.json`、`roundtrip-final/result.json` 和 `roundtrip-layout/`。
  当时为源码交付；后续 2026-09-19 本机安装版已包含工程 ZIP 功能，见上节。

### 先前本机验收安装版（2026-09-17，已备份）

- `/Applications/ICSTeX.app` 已同步到下述任务导引源码 `003d6540...`，包含此前写作 UI
  和局部精简增量。保留版本标签 `2.1.0-beta.3 / 210003`，以本地日期/源码摘要和
  程序 SHA-256 `5e46d205efcb83ba713a655db04ae2664095f1ae2d04f3a579a3dc9d4ca1fda1`
  区分公开 Beta 3；未修改 GitHub、官网、公开 feed 或 release manifest。
- 规定 preflight 通过：1803 项/312.672 秒，命令 314.326 秒、退出 0，源码前后身份一致。
  既有 PyInstaller/Sparkle 构建核验 205 个模块与入口及所有图片匹配当前源树，未丢失旧包
  模块；沿用原有 13 个独立未打包模块。arm64、ad-hoc、deep/strict 签名完整性通过；
  不声称 Developer ID 或公证。安装副本与候选的 472 个文件和 160 个软链接逐项一致。
- 原生已从正式路径打开（本次观察 PID 89477），确认欢迎页环境就绪、四个教程分页、
  “开始练习（独立副本）”及实际配图；留在第一分页供用户验收。未打开学生文稿或开始
  练习，不把这次启动/配图检查称为完整原生写作验收。
- 旧公开 Beta 3 完整移存至
  `/Users/leo.xu/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.3-before-tutorial-20260917.app`，
  程序摘要仍为 `fa4a83f8...f92ad4`，签名完整性通过。既有偏好和更新 runtime 保留。
- 收据、完整日志及带日期/源码摘要的本地 ZIP 在
  `/Users/leo.xu/.codex/visualizations/2026/09/17/icstex-local-install/`。
  测试 Qt/临时路径诊断、旧制品提醒及构建的系统 libobjc ctypes 提醒保留；普通 diff
  跟随 Qt 软链接产生循环提示，随后使用不跟随软链接的完整清单确认复制一致。

### 已实现的任务导引与新手图文教程

- “帮助 / 欢迎页 → 新手导引”包含四页中文教程与四张真实界面配图，图片仅在打开
  教程时读取，可显式单独打开；没有自动播放或网络图片。配图共 231294 字节。
- “开始练习 / 继续上次练习”使用既有中文模板，在应用数据目录创建独立、不覆盖的
  项目和设置文件；原窗口、草稿及编辑偏好保留。重开时使用当前应用缩放，避免旧练习
  配置改变其他窗口。路径核验保留范围和符号链接保护。
- 顶部导引按真实内容、主动编译动作和当前 root/revision/build-id 的 PDF 状态推进，
  用户看到新标题后再确认。窄窗口提供“显示 PDF”，错误/旧预览不能充当成功；导出
  仍进入既有准备提交流程。普通窗口无导引控制器，收起后停止导引刷新。
- 练习内容可以保存并重新进入；关闭窗口后须重新编译确认当前 PDF。练习仅识别
  单行普通文字标题，不是通用 LaTeX 教程引擎。14 项专项已通过；真实离屏练习已
  验证新标题编译/可见像素、失败保留旧 PDF、光标/滚动和收起/继续。
- 该批完成时 app Python 身份为
  `003d6540a3c01fdad30464de54316cd9b84326387297126784d04ee0697adb32`。
  证据根为 `/Users/leo.xu/.codex/visualizations/2026/09/16/icstex-task-guide/`，
  `capture-delivery/result.json` 记录相同源码与四张图片摘要。
- 最终 compileall / 工具语法检查通过；完整回归 1803 项/718.104 秒，命令 721.288 秒，
  退出 0、前后身份一致。app+tests 为
  `e4ceb8d5ddeb067241dbad4861a30ed7a6dc9e20a6a272db3076d505f6440df0`，
  完整收据在 `full-final/result.json`。Qt 提示及临时目录异步读取诊断仍保留，不称零警告。
- 该源码阶段未提交/推送或部署官网；后续本地打包安装状态见上节。
  离屏检查不是学生试用或原生全流程验收；导出图仅展示准备页，未把截图当成完成交付。
  历史 allWidgets 原生异常未在此任务归因，不宣称根除。

### 已完成的局部精简与一致性优化（本轮保留）

- 本轮以含未提交改动的有效工作树为基准完成两批局部修改。引用检查失败且无报告/
  待执行请求时停止计时器；成功报告和待执行请求仍监控。两种检查共享完整输入身份，
  保留各自导航/素材基准处理；意外异常只记录类型、代码位置，不记录正文或异常原文。
- 批量设置只在最终状态应用各编辑器一次，按 save 标志持久化零次或一次；不隐式编译，
  直接开关和引擎操作的即时响应保留。PDF 基础规则统一为单次 stat 的非空普通文件；
  单次刷新复用 root/文件观察，实际导出继续重新验证，PREVIEW/FINAL 不合并。
- 相同最近记录不重复写入或重建菜单/项目按钮；保留顺序、失效路径、另存为及旧路径
  文本的规范化。环境提示独立更新；向导仅切换引擎时不重设源码、哈希或静态图片。
  原有 UI 设计、模板、保存事务、编译调度和渲染队列均未另行改造。
- compileall 通过；最终完整回归通过 1790 项/310.500 秒，命令 311.987 秒、退出 0，
  前后受测身份一致。app 为
  `c69c53da62ab49bff95ffb1bd5ca3f7dc8c5cc475e6fccd07af6833337d9265a`，app+tests 为
  `24d1b5966fee6a1b1f3899bad93e4da53cc21573405bba24790e2232c5f3a039`。
  Qt 平台/PDF 连接提示与临时目录异步读取诊断仍保留，不称零警告。
- 同源码 `gui-current/` 已观察设置同步、真实保存后控件复用、欢迎页正确最近文件，
  以及引擎切换后仍保留的预览/选择和 Auto 状态。此为隔离 offscreen 检查，非原生
  Mac 或真实学生项目性能验收；未归因旧 allWidgets 原生退出，不声称整体提速。
- 证据和起始小范围快照在
  `/Users/leo.xu/.codex/visualizations/2026/09/16/icstex-local-simplification/`，
  最终完整收据为 `full-final/result.json`。本轮未提交/推送、打包、安装或发布，
  原分支、索引、他人改动和学生文件保留；按本轮边界结束，不自动继续旧功能。

### 已实现的学生写作流程第一批（本轮保留）

- 已实现用途/语言模板选择、九个真实模板首页静态示例、默认折叠源码/高级设置，
  保留原自动引擎选择和不覆盖目录事务；创建与选择模板不启动编译。
- 文档保存状态与当前/过期 PDF 分开显示，自动开关名称对应真实模式；
  错误提供位置、下一步和原始日志，宏包修复先确认精确差异。欢迎页环境紧凑化，
  显式重新检测，最近项目附最近文件/短路径，导引“关闭”本地化。
- 复用现有 Qt 控件、焦点滚动、模板、诊断与 root/revision/build-id 状态；
  未新增依赖、网络、状态系统或编译调度。该批验收时的 app Python 摘要为
  `808efbd743464e3f95e903445981f6f8c6015be314e371871b47652c009afe23`。
- 独立示例已通过实际 GUI 编译入口的中文创建、改标题、保存、更新 PDF 和缺图
  失败保留旧 PDF；`final-ui-v3/` 已观察实际文字渲染。全部为 offscreen，
  不冒充原生 Mac、IME、学生试用或全新电脑验收。单页中文自动预览暖轮中位数
  2219.516 ms，旧版前后对照为 2150.623/2323.857 ms；不宣称加速。
- 最终 compileall 与完整回归通过：1770 项/288.095 秒，命令 289.481 秒、退出 0，
  前后源码身份相同；app+tests 为
  `48c0c7547c5ca6746f4c66a77cc39cc933e4293663316a4bae5ebfb8d878c7bc`。
  完整收据在证据根目录的 `full-regression-final/`；保留 Qt 和临时目录异步读取诊断，
  不称零警告。此前三条旧断言/无效 PDF 夹具已校正并通过受影响专项。
- 首轮完整回归曾在 `QApplication.allWidgets()` 包装器转换路径 SIGABRT，
  原生 malloc 无效释放根因未定；后续专项及详细输出轮未复现，不称已修复。
  保留原始报告和失败日志，不能只依据重跑通过推荐发布。
- 本批仅修改开发源树，未打包、替换本机 Beta 3、提交/推送或公开发布；
  本轮已只读复核安装版仍为 Beta 3，程序摘要 `fa4a83f8...f92ad4` 未变。
  交互式短任务导引、图片重选和学生试用属于后续批次。
  实现与证据入口：`student-writing-first-batch-2026-09-16.md`。

### 已发布 macOS arm64 Beta 3（2026-09-15）

- macOS arm64 Beta 3 线上更新已发布并完成真实 HTTPS 升级验收。版本
  `2.1.0-beta.3 / 210003`，GitHub prerelease id `388996893`，不可变标签
  `v2.1.0-beta.3`指向`81b1672d162de2128374e9cdb9a7c20b00a95110`。
  官网`https://ics-tex.vercel.app`及固定签名 appcast 已部署；当前 production
  `dpl_7P7UsiCcEtNRYbuanZkyy8WJDpba`为 READY、全部域名别名已应用。
  归档和清单均以既有专用 Ed25519 身份签署；未导出私钥，SDK 仍固定 Sparkle 2.9.6。
  两个公开安装包都已匿名下载 HTTP 200，字节数/摘要与本地和 GitHub digest 一致。
  版本、下载摘要及公开验收边界见`BETA3_DELIVERY.md`和`release/BUILD_RECEIPT.json`。
- 安装期保护已实现：所有配置版入口在 GUI 导入前取得共享租约，更新时转换为独占租约，
  临时原生 helper 跨主进程退出持锁，绑定本包准确 Autoupdate 进程及内核开始时间。
  原生验收中主程序退出、helper 被杀时均仍拒绝晚启动；实际安装器被中断后确认其结束，
  旧包完整性通过并冷启动。篡改 feed/归档均被 Sparkle 拒绝。不是自动回滚；未知交接
  需重启 Mac 后验证，损坏包须人工恢复可信完整应用。设计与范围见 D026 和
  `UPDATE_INSTALLATION_GUARD.md`；不把其他登录会话或所有管理员安装布局说成已实测。
- 新包的203个模块及入口、36项资源、启动 hook、arm64 和 deep/strict 签名完整性已核验。
  app Python摘要为`500675e9aa6246deef355bc68a80080d740ad121f6672916ddb4c34595e37a9d`，
  app+tests为`dd4f11148084a95d87b55c16b8d62b10d6e40f2bb26670cbb46040ba02aa34a8`。
  最终 preflight 通过1758项/302.583s，命令304.212s、退出0，前后源码身份一致。
  初轮缺旧版参考制品、测试框架复制及校验脚本的失败记录均保留；未隐藏 Qt/临时目录
  非致命诊断。13个原未打包独立模块继续明确列出，没有添加 Windows 或网络 MCP 服务。
- 关闭本地 fixture 服务后，低序号隔离 bootstrap 通过开启自动检查从正式 HTTPS 源发现
  Beta 3，显式确认下载/安装后自动重启。新进程在任何 UI 重开前已存在，序号210003，
  程序摘要`fa4a83f83829a367c5760ccfe1a3f66776752212d3444fbd59c9b342f8f92ad4`，
  全包文件/软链接与签名候选逐一相同；原生欢迎页及 LaTeX 就绪已观察。
- 本机`/Applications/ICSTeX.app`已从匿名下载的公开 ZIP 完成一次性 bootstrap 安装，
  程序摘要与上述新包相同；发布当日源树同步到同一 app/test 身份，原开发分支和索引保留。
  该公开版本仍不含 2026-09-16 增量；本机应用已由上述 2026-09-17 验收包替换。
  旧 Beta 2 完整备份至
  `/Users/leo.xu/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.2-before-online-beta3-20260915.app`，
  旧程序摘要仍为`19fc3696f337a1024460557742ac711cbaf3284d393daab1cd85585ce4ac80af`。
  新旧包签名检查通过；未强杀用户应用、打开或改写文稿。安装后 Mac 再次锁屏，
  当时未从正式安装路径打开窗口；本次本机启动见上节。自动检查仍默认关闭。
- 证据保留在`/Users/leo.xu/.codex/visualizations/2026/09/15/icstex-online-update/`。
  旧 Beta 1/Beta 2 标签、包、内部 r2 候选和所有备份保持不变；未增加常驻服务、
  修改 Sparkle SDK 或升级虚拟机。Developer ID、公证和 Windows 新版不在本次交付内。

以下为较早源码阶段的记录；版本和线上更新状态以本节上述交付为准。
- 当前Star入口增量已完成源码验证：官网系统下载区共享一条自愿支持提示，复用
  现有repository链接绑定和样式；软件“帮助→在GitHub支持项目（Star）”只在点击后
  打开固定仓库地址。浏览器打开失败只在状态栏提供地址；不弹窗、不查询或提交Star、
  不接登录/令牌/统计，不影响下载、更新或使用。编译与更新逻辑未因本次修改变化。
  网站只改index.html，未改JS/CSS/发布元数据。内置浏览器的隐藏标签页确认链接
  目标、下载独立可用、桌面及390px窄屏显示，控制台未发现error；未点击外部下载或
  Star。标签页、尺寸覆盖和本地服务器已清理。软件菜单已通过动作测试及离屏显示
  检查，截图在`/Users/leo.xu/.codex/visualizations/2026/09/14/icstex-star-entry/help-menu.png`。
  初轮专项的临时菜单包装器引用失败仅修正测试持有方式，该单项通过；产品代码未
  因此更改。compileall通过，一次最终全套通过1742项/293.193s，命令294.761s、退出0，
  前后源码身份一致。日志仍保留Qt提示和临时目录异步读取诊断，不称零警告。
  app摘要为`a8bb8ee66b8ae6d9a28f969df5795d0a05fc4b33687810bb964fe7f84dd05caf`，app+tests为
  `eadecb035cdf6be25dd06a009a4ed83f95be3ec749ac12473030f2f6e5ff5a91`；完整收据在上述
  `icstex-star-entry/full/`。网页HTML摘要为`34e1386608e50acb7716286587d2f39394fe214637c416f6eceb09fe674b6521`。
  该源码任务当时未提交/推送、部署官网或替换本机应用；后续本机交付见本节首项。
- 上一批独立任务为Mac arm64 Beta线上升级的本地准备，尚未激活更新服务。已调整为
  用户开启后启动延后30秒检查、跨快速重启5分钟去重、随后运行期间每天复查；编译、
  PDF导出、模态交互和无窗口时暂缓。手动检查满足该进程启动检查；原生更新器初始化
  失败也登记尝试，避免后续每分钟重试。源码/未配置安装包默认离线，下载与安装确认、
  全窗口保存退出和签名保护不改变。未改编译核心、当前文稿、已有安装版或SDK。
  58项更新专项/1.056s和1项更新窗口检查/0.137s通过；一次最终preflight通过1739项/
  301.196s，命令302.910s、退出0，compileall通过，前后源码身份一致。日志保留Qt
  平台提示与临时目录异步读取诊断，不称零警告。app摘要为
  `ceb2ffd55f012c3b34dd81413f9923bae43612c0331716728b9f2ed1381e7a87`，app+tests为
  `f5994502df672a584b3a4f5ac884368232d0a790a820a33a4e7b6e921b795bcc`。
  回归收据和原始日志在
  `/Users/leo.xu/.codex/visualizations/2026/09/14/icstex-update-preparation-1318/full/`。
  本轮只读核验：GitHub仓库权限返回admin/push，公开Release仍仅Beta1；Vercel原项目
  `prj_BXdZTV6vil9XDBCg2Nh43roEVFsm`可读且域名匹配，最近READY部署为预览、target为空。
  配置中的HTTPS appcast地址返回404；配置字段/当前版本校验通过，不代表更新已上线。
  固定Sparkle2.9.6源码仍明确列出晚启动实例与其他登录会话监视限制，安装全生命周期
  协调未实现。临时协调进程仅为待确认方案；详见`UPDATE_ACTIVATION_PREPARATION.md`。
  没有提前构建必将重做的候选包、改版本、访问私钥、替换应用、提交/推送或部署。
  本机安装程序摘要复核仍为`499d04f091de18f19343c583b3cac13129564344c8656dca028b37b3425a8bf3`，
  因此下述安装版仍不包含本次启动调度增量，也没有公开更新runtime。
- 上一批验收反馈小改：顶部“字数”替换为“控制台”，与底栏和视图菜单共用一个可切换
  QAction，保留原控制台页签和展开偏好，不强制进入字数页/重算。原“编译→字数统计”
  入口保留；插入面板的旧“分段函数”按钮移除，公式编辑器分段结构键不变。
  当前app为`b950dc6022de58439cd0326143933e8ca5c3cd12337f29b596d0f4590a16bd0e`；
  app+tests为`703e2598e986845af1a448b2e2c520842ab6148f9dcb6c8470aa5e26471e6951`。
  25项相关检查/8.731s、原生单项切换检查/1.188s通过；最终preflight通过1730项/
  310.601s，命令312.390s、退出0，compileall通过，前后源码身份一致。原始Qt/临时
  目录诊断仍在日志中。不改变编译或文件事务。新包已安装到`/Applications/ICSTeX.app`，
  程序摘要`499d04f091de18f19343c583b3cac13129564344c8656dca028b37b3425a8bf3`，进程10157。
  201个app模块+入口及36项资源匹配源码，旧包模块集相同；arm64/ad-hoc，新包/安装版/
  备份deep/strict签名通过。旧cf281版完整保留于
  `/Users/leo.xu/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.2-before-console-b950dc60-20260914.app`。
  更新前当前Physics EE显示已保存且编译空闲，正常退出后替换，无强杀/保存/编译操作。
  原主文件ab4179b6未变。新欢迎页已观察到“控制台”及正确说明，停在欢迎页交付；
  未代用户重开桌面文稿，也未触发或操作新的系统权限请求。
  证据目录为任务根下`console-entry-20260914/`及`console-entry-focused-20260914.log`。
- 上一批为用户确认六项视觉痛点后的普通写作UI优化。已缩窄未编译PDF提示区、
  收起整个空控制台、合并源码工具栏/项目状态行、移除重复PDF标题/加载提示；常用
  动作带短标签，自动编译开关随UI缩放，注释改为正体。PDF空状态隐藏1/0及禁用工具条，
  新按钮只委托原正式编译动作；保留编辑字号、展开偏好、分栏/阅读位置和所有编译保护。
  当前app为`cf281f47f998fd7c9b62f80e7360c7f655815d753050456bca77a298b0c25aca`；
  app+tests为`2bb0f8d80c53e4257dee49788e8e3513b500e1e16dafaf6f50f68c8821da6439`。
  62项相关检查/13.704s、29项工作台检查/7.635s通过；最终原生四状态及源码/窗口保护
  通过，100%未编译编辑区1102×750逻辑像素。EE冻结副本自动预览5.590s/暖轮3.073s、
  26页及当前revision像素通过，仅为单轮功能检查，不声称UI带来编译加速。
  最终preflight通过1729项/291.148s，命令292.798s、退出0，compileall通过，前后源码
  身份相同。首轮仅旧布局断言要求空PDF至少360宽而失败；已更新为空状态动作可见/
  正文优先及不重叠断言，专项通过，产品源码未变。与旧安装版相比89个实际打包core模块
  代码对象一致；不将另外未打包模块伪称覆盖。新包已安装到`/Applications/ICSTeX.app`，
  程序摘要`776d175eb8a3e53c3a957ece0cc6cd8c6438d5659dcaded07d5d553cb9a9aea6`。
  arm64/ad-hoc，201个app模块+入口、36项资源匹配；新包/安装包/备份签名检查通过，
  不含公开更新runtime。旧7478版完整备份至
  `/Users/leo.xu/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.2-before-writing-ui-cf281f47-20260914.app`。
  进程6984已启动，欢迎页及带文字的新工具栏已观察。恢复EA曾因新版cdhash触发桌面
  文件夹重新授权而停在openat；未绕过工具对系统授权窗口的限制。用户继续后，tccd于
  14:51:30明确记录DesktopFolder为Allowed (User Consent)，同一进程正常完成打开。
  最新AX和截图确认EA已打开/已保存、编译空闲，新窄PDF提示栏、文字工具栏、正体注释
  及底栏控制台入口实际显示正常，无授权或文件选择对话框。EA摘要a24d90cd与程序摘要
  均未变化；没有重编原稿、重装或重跑测试。UI源码/验证/本机交付已完成，现交用户验收。
  细节/截图入口见`writing-ui-refinement-2026-09-14.md`。
- 上一批用户要求继续彻底处理第2项。已确定复现Qt旧渲染队列导致永久白页，以及迟到
  旧图像进入新PDF缓存的问题；新内容使用独立查看器队列，同字节继续复用。文档由
  PdfPanel最后持有，确保搜索/查看器和渲染线程先退出，文档后释放。保持工具栏、
  搜索模型和文档实例、同root阅读位置/缩放与所有编译保护，不换渲染技术/依赖。
  当前app为`7478cba77fb2f4712c9468b5dda452807934928870c51d62f1802cd7d14a1161`，
  app+tests为`4ff9e4b76e767ecb38dcdac0c7823a6dc28afe280d796b3e90ae67772ca84461`。
  红绿对照、33项相关回归、当前原生刷新/搜索/销毁通过。中间候选和模拟接口失败
  全部保留；不是把重试通过当成根因。最终preflight通过1725项/289.494s，进程291.267s、
  退出0，compileall通过，前后身份相同；原始日志保留Qt提示及临时目录异步诊断。
  同源码EE冻结副本自动预览首轮5.493s/暖轮3.086s，新revision像素、26页、原子保存和
  统计/窗口退出通过；仅作当前功能回归，不声称相对上批又有编译加速。
  本机`/Applications/ICSTeX.app`已更新并启动7478cba7修复源码，程序摘要
  `d79a85f84f1c7b0dd2a30185e335d35a84e61fa81289259b8077cd2d07ff6a1b`，进程68965。
  现有规格新构建，201个app模块+入口、36项资源匹配源码；模块集合与旧包一致，既有
  13个未打包模块继续明确列出，未伪称覆盖。arm64/ad-hoc，安装版/备份deep/strict签名通过。
  旧版完整备份到`/Users/leo.xu/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.2-before-pdf-7478cba7-20260914.app`。
  更新前EA已保存/空闲，正常退出后替换；新版欢迎页/latexmk就绪已观察，EA已仅重新
  打开。AX读取在文件选择后两次超时，未重复Open；截图确认文件已打开、已保存、无对话框，
  PDF为尚未编译而非渲染失败。EA原字节摘要a24d90cd不变，未保存/重编原稿。
  本次可复现的白页/旧渲染结果/销毁缺陷已闭环，不再列作等待重复测试；旧A事件缺失
  证据的事实仍保留，不声称所有历史崩溃或任意损坏PDF都已得到统一归因。
  技术依据、重现步骤与历史事件边界见`pdf-render-lifecycle-verification-2026-09-14.md`。
- 上一批用户将剩余工作缩为1输入卡顿、2 PDF/Qt排查和5本机更新；拼音候选、纯键盘菜单
  及VoiceOver明确延期，不再阻塞本次交付，也不冒充通过。已移除两PDF状态库对已登记
  root的逐键重复解析，并将成员扫描/后台统计合并到停笔500ms后；显式保存/编译仍立即
  校验必要依赖。200子文件/30次原生输入的p95为50.757→13.483ms，最大52.936→14.366ms，
  >50ms从3/30到0/30；p50为7.008→12.207ms，收益限于尾部而非所有样本。
  PDF原生新字节刷新、复用、切root、搜索中清空/重开和关窗通过；另修复reload后
  搜索计数显示不更新，保持阅读位置且显示真实匹配数。旧搜索SIGSEGV与已修正的测试
  夹具生命周期错误核对；原A空白缺少失败PDF/曝光数据，未获得历史根因证明，风险保留。
  当前app为`d8292f5bdd68737e4f34b11e0c244d2a0412957cc43b8632d84c5eca0e04be38`，
  app+tests为`c52f6ca09460a1dd101a3f163e29cbb8cae3c928f94719ef385c9007ce9e2352`。
  证据根下`closeout-125-20260914/`；最终preflight通过1722项/278.153s，命令279.726s、
  退出0，前后身份一致；compileall通过。日志保留Qt提示和临时目录异步诊断，不称零警告。
  EE冻结副本离屏自动预览首轮5.476s/暖轮3.015s，26页和新版本像素、保存/统计及销毁通过；
  这是单轮功能回归，不把与上批不同时间/负载的数据当新加速比。本机已更新至上述d8292f5b源码。
  已使用现有PyInstaller/规格构建新包，未升级依赖；实际包含的201个app模块、入口与36项
  资源符合源码，与旧包的模块集合相同（既有13个未打包源码模块未被偷偷算入覆盖）。
  arm64/ad-hoc、deep/strict签名通过，无公开更新runtime。程序SHA-256为
  `6a8843ffae83540119ebdcf415f8cab97766c357e518589159867e7b3ddcc267`。
  旧8dd版已完整移至`/Users/leo.xu/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.2-before-125-d8292f5b-20260914.app`，
  旧摘要b2757de2不变且签名通过。确认EA文稿已保存/编译空闲后正常退出，无强杀/丢弃/保存操作。
  新安装版已从`/Applications/ICSTeX.app`启动，进程66126；欢迎页/latexmk就绪已观察，
  随后仅重新打开原EA主文件，界面显示已保存/空闲，未改写或重新编译原稿。
  `installed-receipt.json`记录包/源码身份，`installation.md`记录启动边界。1及5完成；
  2的当前原生流程验证通过，但历史A空白因果仍未证明，不将整个Goal冒充全部风险根除。
  不修改学生文本、不升级运行时、不提交/推送/公开发布。详情见PERFORMANCE_UI_PROGRESS。
- 上一批C/D/F的按钮状态补缺：14类主按钮已用现有局部样式补focus/pressed/disabled，
  覆盖提交检查、固定交付、检查点、恢复、迁移、中断写入恢复、Block、引用、历史、
  图片、模板、表格、普通诊断及环境报告。现有primaryButton入口均显式绑定同一状态
  样式；工具栏主按钮与普通主按钮的hover+pressed组合也有独立反馈，使用同色系深棕。
  未新增全局QSS规则；生成函数的字节码/常量在忽略源码行号后与安装版一致。
  14类×五档的70组离屏状态通过，普通状态像素与改前相同、几何不变、无业务点击。
  这些是显式外观状态模拟，不是提交/恢复准备条件通过，也不替代实际确认门槛。
  117项相关流程/28.185s通过；最终15项状态/主题专项/4.878s通过，compileall通过。
  当前app：`614f6a6829ec87206ca586b1af19ca9255afe5bb52e991405e177bba79bb30bc`；
  app+tests：`5dcfda77db9fdb2e6eba5e91a8672313535cc03150ac839f34ef05e92323f96c`。
  完整回归通过：1716项/265.571s，进程266.966s、退出0，前后源码摘要一致，日志及
  收据在`task-button-states-20260914/full/`。原生首轮未取得焦点，
  随后前台工具确认Mac锁屏；原始70组失败保留，不能作为原生通过。用户再次要求继续后
  前台已恢复；在active/exposed前置条件下补跑两项原生检查，6.205s、退出0，70组窗口
  active、focus/pressed/disabled、几何与零业务点击均通过，源码与完整回归身份一致。
  新证据为`task-button-states-20260914/native-unlocked/`，保留原IMK唤醒警告及旧失败。
  未重跑完整回归/性能矩阵。原锁屏停点已解除，Goal仍未完成；真人输入法/键盘等不可
  由这些程序化状态检查替代。用户随后明确要求测试由agent自己执行，不再让用户代跑。
  原人工副本进程47352/会话96673已退出，旧文件保留；已用同一入口的观察模式新建
  `task-button-states-20260914/agent-ime/project/manual-test.tex`，进程61641/会话42291，
  自动编译关闭，候选/提交事件与源文本/落盘状态只写入副本外的本地观察文件。
  入口为`task-button-states-20260914/manual_acceptance.py --output-name agent-ime --observe`。
  用户解锁后，agent已自行完成原生GUI中文/emoji粘贴保存、一次Undo/Redo、包含非BMP
  前缀的公式选择、源码模式草稿隔离及Esc取消，源文本和磁盘均有精确断言；副本已恢复
  初始内容、测试进程正常退出。证据见`agent-ime/result.json`及01–06状态快照。
  真实拼音候选尚未通过：当前按键通道直接提交Latin字符，QInputMethodEvent记录仍为0；
  系统TextEdit对照也相同，不能据此判定ICSTeX缺陷或把粘贴当IME通过。纯键盘菜单入口
  也未获得证据。无需用户代跑，保留当前自动化通道限制；未绕过锁屏或修改输入法配置。
  TextEdit对照仅含zhongwen，曾自动存入其默认iCloud目录；已通过UI移回本地agent-ime，
  旧路径不存在，未涉及论文；不声称云端历史不存在。测试及系统设置窗口均已关闭。
  本轮未更改编译核心、文件事务或安装版；不打包、提交、推送或公开发布。
- 上一批边际评估和欢迎页补缺：用户确认上一批“性能回来了”，随后要求继续尝试快速预览，边际收益不明显时转入
  原Goal的UI计划。本轮未采用新的编译优化：同一固定XDV的压缩1→0中位仅省95.808ms，
  临时PDF从7.35MB增至12.53MB（约71%），26页渲染相同；相对完整链路潜在收益小。
  同源码阶段诊断的暖样本为3042.505ms，代理准备32.629ms、静态检查108.969ms、
  PDF加载7.841ms；这是带计时器的单次诊断，不把相对上批7.03s的差异算作新收益。
  已按约定转入C/F的UI补缺：欢迎页临时收起无项目工具箱，进入写作恢复偏好，欢迎页
  退出不覆盖该偏好；宽窄重排清除旧空列且不再重挂载按钮，保留焦点；欢迎主按钮
  复用已有局部focus/pressed/disabled样式，不新增全局QSS规则。
  当批app：`44f1fdc422378bc7a85f41008d8cc040e498ed957deb085d5d9c901cb69c1c4b`；
  app+tests：`7bc30f4814ffec616e013a75ba3e6312efff822ae8dc073a6d79c199b30fe4a4`。
  72项相关测试/10.829s通过；3项原生检查/3.415s通过，包含两尺寸五档布局/按钮状态，
  偏好恢复及重排焦点。保留Cocoa的IMKCFRunLoopWakeUpReliable警告，不冒充真人IME
  或VoiceOver验收。compileall及完整回归通过：1714项/273.836s，进程275.277s、退出0，
  前后app/app+tests摘要一致；完整日志与收据保留在`preview-next-20260914/full/`。
  没有重跑旧性能矩阵。六个GUI模块与安装版不同，所有core模块代码对象与安装版一致。
  证据在任务根`preview-next-20260914/`，当前安装版仍为下述已验收性能的8dd861b0，
  未自动打包/替换本次UI源码，不提交或推送。历史风险与人工清单仍保留。
- 上一批自动编译修复：用户曾反馈本机 Beta2 自动编译明显变慢，2026-09-14 明确恢复修改；唯一优先指标
  为源码改动事件到最新 PDF 内容可见的完整等待，不再以 UI/局部微基准替代。
  已按用户提供的 Physics EE 主文件建立隔离副本，原件只读。改动保留原子保存、
  root/build/revision、关联草稿、取消、FINAL 原图与正式证据保护。
  当前修复：自动 PREVIEW 不重复强制已有依赖快照；已成功保存的精确字节立即登记，
  避免本机保存被重新识别为外部编辑并重置防抖；后台字数统计让位于自动保存/排队/
  编译和 PDF 首轮显示，显式统计仍可发起；普通 XeLaTeX PREVIEW 使用快速无损压缩，
  FINAL、其他引擎和受限编译不改变。
  同一 EE 副本、原有 800ms 保存防抖/150% 缩放、各 5 次暖预览，源码事件到新版本
  PDF 像素的离屏中位数 9962.086→7034.751ms，减少29.385%；最大值10386.582→7995.616ms。
  新像素标记、build/revision匹配、26页与统计最终完成均有断言；不是compositor精确
  时间或所有项目性能承诺。第一个候选12.001s、第二个9.406s的中位结果原样保留。
  同一XDV交替压缩对照的中位耗时3226.564→945.754ms，26页72dpi渲染像素完全一致，
  临时PDF约增大6.36%；没有修改学生文本或图像内容。
  当批app：`8dd861b0aba3d4d4f06406b65f059613d7de725d568c20663f974e852bdac3f1`；
  app+tests：`b0c61873fe031dd706b0a3ab258df1383615af8bc41d8cc73cecdd0a92286ad3`。
  相关79项回归与新增压缩边界测试通过，compileall通过；原生3次暖预览完整耗时为
  7671.768、6743.804、7282.913ms，当前build/revision/像素和窗口销毁/统计完成均通过。
  首次预览单样本离屏12.025s、原生12.469s，不含在暖样本内，不承诺首次打开只等7s。
  完整preflight通过：1710项测试/638.177s，命令642.471s，退出0，前后源码身份一致；
  完整日志及收据保留在`auto-compile-20260914/preflight/`。新本地Beta2包已构建，
  201个app模块、入口及资源与上述源码相符，arm64/ad-hoc签名deep/strict通过，
  未嵌入公开更新runtime。新程序摘要为
  `b2757de209178d54457a8559f82fe1be7177522c5d0c4ad6e974718ffa881c66`。
  首次安装遇到Mac锁屏且原程序仍运行，已暂停而未强杀。用户明确继续后确认旧进程
  已退出，完成备份/替换/启动；未重跑性能或完整回归。已观察新安装版欢迎页和latexmk
  就绪，进程42486来自`/Applications/ICSTeX.app/Contents/MacOS/ICSTeX`，没有打开文稿。
  构建收据位于`local-install-2.1.0-beta.2-8dd861b0/source-receipt.json`。
  不将本轮通过表述为全部V1或历史风险验收通过。
  证据根为任务目录下`auto-compile-20260914/`。
  已安装`/Applications/ICSTeX.app`为本次8dd861b0修复源码的本地Beta2，程序摘要与新包一致，
  安装版及备份均通过deep/strict签名校验。上一版完整保留于
  `/Users/leo.xu/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.2-before-auto-latency-20260914.app`，
  其程序摘要仍为25207f46acb86fd609d6f5db7f0f47a6788035df999c7f0d3cdac1ae5af87d65。
  上次安装收据`local-install-2.1.0-beta.2-3897ec74/source-receipt.json`保持原身份。
  Beta1备份及既有证据继续保留；历史UI/原生尾部/Qt风险未自动关闭。
  前版状态全文归档到`auto-compile-20260914/project-state-before.md`，历史结果详见
  `PROJECT_LOG.md`和`PERFORMANCE_UI_PROGRESS.md`。用户的本机更新授权仍限定本地
  构建、备份、安装与启动，不授权Git提交、推送、公开更新或发布。
- 当前阶段已按用户于 2026-09-12 明确确认的“Mac 源码阶段性交付”收尾；未完成
  验收留到后续，不再作为本 Goal 的继续执行项。现有 Python 源码已按用户要求启动，
  原生欢迎界面与 LaTeX 环境就绪状态已观察到；不代表真人使用验收全部通过。
  Agent/MCP 受限 Biber 支持延期，普通 GUI 编译策略不变，已知受限启动失败仍保留。
  启动入口及限制见 `docs/MAC_WRITING_HANDOFF.md`。本次完成不等于完整 V1 验收、
  稳定版承诺或打包/替换安装版授权；R2 菜单证据、R3 稳定性风险与发布门槛未豁免。
  其余延期项不自动重开；后续性能/UI工作仅按上述独立任务的明确范围执行。
- 权威工作区：本仓库根目录；Beta 2 源码与下一代开发说明已于 2026-09-10
  同步至 GitHub 的 `release/2.1`，源码提交为 `fef3731`。
  此后 V1 本地开发已完成 M0、M1 只读纵向切片，M2 已实现项目配置、创建/工作区
  和 Block 受保护模型保存/关闭、布局及键盘可达性、属性草稿保护专项；二次编辑器
  目标绑定已通过专项/原生和冻结源码全套；后续图片导入边界修复已通过专项，
  后续真实原生 picker 的取消/导入/冲突及保存重开/FINAL 已通过。用户现已授权源码同步，本地分支改名为
  `codex/v1-development`；源码检查点 `e78c2cd` 已推送并核对远端哈希。
  远端 `release/2.1` 仍为 `f03776e`，未改动发布分支或公开版本。
  同步后的本地继续开发修复公式替换的新输入校验及粘贴注释换行保留，专项与该源码
  完整回归通过。后续来源检查增加有界后台读取与关联 Block 定位，专项通过、
  该源码完整回归通过。普通源码引用健康已通过专项、合成窗口/BibTeX FINAL 与全套。
  最新素材使用检查已通过专项和合成窗口/图片 FINAL；旧磁盘索引断言与暖缓存计数
  修正后完整回归通过。后续合并候选与表格导入保全修复通过专项/真实合成 FINAL，
  该准备源码完整回归通过。后续真实来源修复已接通摘要匹配原始版本、显式映射、
  全部关联表格一次确认/Undo，专项、合成窗口/保存重开/FINAL 与最终源码完整
  回归通过。后续 M4 检查点核心完成选定文件字节采集、独立草稿与恢复到新目录，
  专项、合成重开/FINAL 和最终完整回归通过。后续 GUI 文件选择、实际源/Block
  草稿捕获、审阅并恢复到新目录也已通过专项、真实合成界面/FINAL 与最终全套；
  后续恢复副本审阅、独立窗口继续源码/Block 草稿、首次显式保存保护已通过专项及
  真实合成保存/重开/FINAL，最终源码完整回归也已通过。最新中断写入恢复已通过专项、
  offscreen 与 Cocoa 恢复/重开/FINAL，冻结源码全套也已通过；后续迁移核心已通过专项与
  后台副本/重开/FINAL，该冻结源码全套也已通过；迁移 GUI 已通过专项与离屏端到端，
  其冻结源码完整回归也已通过，恢复前台授权后的三条原生流程通过；后续 M5 固定
  交付已接通普通源码与主/独立 Block 的实际 GUI 入口，专项及四条离屏/原生流程
  通过，该冻结源码完整回归也已通过。后续 Agent/MCP 已补实际构建/内容复核及独占
  导出，专项、实际 stdio 和该源码全套通过；再发现的暖 FINAL 缓存误归属已修复，
  新全套首次在 Qt 样式表处崩溃、同源码诊断复跑通过，但原因仍未查明；
  后续构建时版本标签已接入实际 FINAL/固定报告，专项、三类实际交付/恢复及最终
  全套通过；仅为进程自报的初始版本，不冒充二进制身份或全部辅助工具证明。旧历史审计
  复现的清单路径越界及摘要未校验已完成有界修复；登记归属、受控读取/清理、
  确认后一次 Undo 与显式保存重开/FINAL 已验证。用户再次授权的本批源码已以
  `c521041` 推送至 `codex/v1-development`，远端完整哈希已核对一致；该分支名
  已符合 V1 范围，无需再次改名。最新 GUI 增量已按本轮单次授权以 `1b1f371`
  推送至该开发分支，远端完整哈希核验一致。本次恢复草稿增量已按单次授权以
  `9360f86` 推送至该分支并核对远端完整哈希。分支与文件名已符合范围，无需再次
  改名。本机 HEAD 和远端开发分支现均为 `3bde2b5d25803262dedef89a081ee6ffbe2b6967`
  （本次只读核验）；其后的增量尚未提交。用户已于 2026-09-11 明确恢复前台窗口控制授权，
  可继续隔离合成项目的原生验证，未扩展提交或发布授权。此前恢复原生 r1 发生 Qt Cocoa
  AX 崩溃，限定版本的单属性临时保护后 r2 正常结束；不等于完整辅助功能验收。
  最新 M6 关窗生命周期修复已通过红/绿、扩展回归、原生关窗/交付和最终全套；
  原 Qt 样式表 SIGSEGV 尚未证明与该缺陷同因，仍保留风险。
  这不是完整 V1 或发布验收。活动范围见 `docs/V1_IMPLEMENTATION_PLAN.md`；
  M0–M7/A01–A15 逐项证据与有限本地/外部剩余项见 `docs/V1_ACCEPTANCE_MATRIX.md`。
  签名 appcast 已移至 Git 忽略的本地候选目录，不在网站树或远端提交中。
  响应/预览优化、公式/表格交互和默认离线更新入口已生成并安装本机 macOS 开发
  构建；公开安装制品尚未包含这些后续更新。
- 当前源码版本：`2.1.0-beta.2`；版本来源为 `app/__init__.py`。
  本机已安装上述b950dc60源码的Beta 2本地验收版，公开下载仍为Beta 1；新欢迎页已打开，文稿由用户自行继续。
  原公开更新候选Beta 2 r2已签名并完成隔离双版本替换，
  但安装全生命周期互斥门槛未建立，尚未公开发布。
- 技术栈：Python 3.11+、PySide6、本机 LaTeX distribution、PyInstaller。
- 产品边界：中文优先、本地文件与本地编译优先、不静默上传用户内容、不捆绑
  MacTeX、TeX Live 或 MiKTeX。
- `v2.1.0-beta.1` 已作为公开 GitHub prerelease 发布；`release/2.1` 包含后续网站
  发布态元数据提交，版本制品仍由该标签固定。
- 静态官网现在包含首页、`website/guide/` 使用指南和 `website/about/` 理念页；
  版本与下载展示仍由 `release-manifest → release.json → app.js` 单向驱动。
- 公开发布候选已加入默认拒绝的本地执行边界；旧安装包早于该修复，必须重建。

## Verified Capabilities

- Mac 受限编译已接入独立 OS 沙箱后端：启动前核验实际隔离能力，失败直接拒绝，
  不回退无沙箱执行。真实 LuaLaTeX/BibTeX 已生成中文、公式、引用和参考文献 PDF；
  原件及构建输入证据保持一致。外部读写、源文件写入、链接绕过、联网和无关执行
  被拒绝，既有输出硬链接另由启动前检查拒绝；真实驱动/引擎进程组停止已验证。
  普通 GUI 默认策略不变。限定标准 TeX Live 2025/Mac 本地源码，弃用接口及辅助
  工具/跨版本支持仍有限制；见 `v1-m6-macos-sandbox-integration-2026-09-12.md`。
- 创建/配置/迁移的五个下拉框现在可通过 macOS 当前 Tab 策略到达；Return/Enter
  选择不再隐式确认父对话框，按钮上的明确确认保留。配置目录建议的 Tab 不再插入
  字符，交付/迁移分页栏可用 Tab 和方向键切换。五档专项、原生创建/配置
  100%/150% 和实际普通项目 PDF-only 交付、检查点/独立草稿恢复/新窗口已验证。
  原件和恢复文件摘要一致，草稿保持独立；菜单 AX 与首个 picker 字段校正不冒充
  全程纯键盘。后续独立 Block 分页栏 StrongFocus 修复已过五档红绿和原生
  100%/150% 实际交付入口；150% FINAL/审阅/取消、迁移清单/新副本、检查点/恢复
  控件已验证。迁移确认打开后的独立窗口可见性与 OS/menu 纯键盘证据仍待查。
  见 `docs/v1-m6-recovery-migration-keyboard-verification-2026-09-12.md`；
  较早源码证据保留在 `docs/v1-m6-modal-keyboard-verification-2026-09-12.md`。
- 普通源码公式现在明确转换 Qt UTF-16 与 Python 字符坐标；公式前后及公式内的非 BMP
  字符不会使宏包、替换范围或返回光标错位，源码模式切换包裹符也按 Qt 长度保留光标。
  确认前复用目标版本/选区/项目保护，外部重载或关闭标签会保留公式草稿与预览并拒绝
  应用；直接计划的越界空范围也被拒绝。未知宏、一次 Undo 和旧历史保留，实际取消/
  保存重开/FINAL、专项及冻结全套通过。旧深黑像素检查漏检灰色字形，已有量测及
  空白区域对照修正；200% 离屏 PDF 仍呈像素化，不据此宣称原生缩放/字体/IME 验收。
  见 `docs/v1-m6-formula-coordinates-verification-2026-09-11.md`。
- 普通源码表格对话框在取消、确认取值和异常退出后释放；父窗口关闭时不重复销毁。
  插入片段与补宏包形成一次 Undo，不重置全文或清空此前历史；独立宏包修复也可撤销，
  保留正反选区、非 BMP 字符定位及自动换行。实际模态编辑期间发生外部重载曾使表格
  插入旧位置并拆开 documentclass；现按源码版本、目标/选区及项目状态拒绝确认，
  保留对话框草稿与可复制预览。取消/保存重开/真实 pdfLaTeX FINAL、四条目标拒绝
  红绿及冻结全套通过；仅为离屏产品验证，不替代原生输入法/AX。
  见 `docs/v1-m6-table-insertion-verification-2026-09-11.md`。
- 已确认关闭的源码标签现会在 Qt 事件边界释放编辑器及其高亮/行号子对象，而不只
  移除可见标签。24 次打开/放弃关闭后，保留的编辑器从 25 个降至唯一的活标签；
  取消关闭与命名/未命名保存失败仍保留草稿，其他标签的正文/光标/滚动、原文件
  字节与共享编译器归属通过回归。原五个后台包装器回收已分别观察到更早的主线程
  Qt 销毁，不是新增跨线程原生销毁证据。当时发现的六次取消表格仍保留六个
  TableDialog 已由上述后续修复关闭；原计时器崩溃完整归因仍未关闭。
  见 `docs/v1-m6-tab-disposal-verification-2026-09-11.md`。
- 源码行号栏不再通过 Python 强引用反向拥有编辑器。无外部拥有者的编辑器可在 GUI
  线程及时释放；Qt 父控件仍保留活编辑器，行号宽度与实际绘制不变。基线两条生命周期
  断言失败；待处理高亮事件下后台回收的小复现崩溃，弱引用对照与修复后 20 轮通过。
  原失败的扩展 GUI 命令现 252 项通过，但小复现的原生栈与旧 SIGBUS 不同，不能
  声称全部历史计时器接收者已确定或原生验收完成。
  见 `docs/v1-m6-gutter-lifetime-verification-2026-09-11.md`。
- 文件重命名/移动后的延迟树选择现绑定窗口生命期，并复核捕获的项目 root；
  销毁窗口后不再访问已删除模型，切换项目后不把旧路径选回。两条基线红例与
  17 项路径/生命周期专项通过；正常重命名仍更新选择/最近文件，保留正文视口。
  该源码的扩展 GUI 回归另发原生计时器 SIGBUS，不能把路径回调修复称为稳定性
  验收；后续行号栏引用环修复与未关闭的历史因果边界见上。
  原失败证据见 `docs/v1-m6-deferred-selection-verification-2026-09-11.md`。
- 普通源码现有独立的单调版本号，候选输入/更新/取消不改变只读输入身份；引用、
  素材、提交检查、Word Count 和工具面板缓存均已接入。真实提交、部分提交、选区
  删除、Undo/Redo、屏蔽编辑器通知的重载和后台关联标签修改仍使旧结果失效，
  不在周期检查中复制全文。历史恢复/检查点的更严格 Qt 事务保护未放宽；源码版本
  不是内容摘要，原磁盘摘要/root/build/dependency 保护保留。只读实际控制器、晚到
  回调与缓存复用回归通过；物理输入法仍另验。
  见 `docs/v1-m6-source-identity-verification-2026-09-11.md`。
- 引用面板的检查摘要不再被长时间戳撑宽，完整时间/入口/输入身份保留在可复制详情。
  按钮行可折行，表格文字与路径有完整提示；重复刷新同一行数会正确重建详情和位置。
  工具导航栏可纵向滚动，方向键焦点自动进入视口。五档缩放和正常/最小窗口的离屏
  真实可见区域、只读子文件定位和原文件字节验证通过。后续原生键盘发现引用结果表
  Tab/Shift+Tab 在单元格内循环；两个只读引用表现已改为控件间焦点导航，方向键
  选行保留，两条红例及专项通过。用户后续解锁后已完成引用原生双向导航和
  Space 子文件定位；新发现的焦点在视口外及工具栏顺序问题已修复并复验。
  五档原生定位按钮可见性、九工具 100%/150% 遍历在各自记录的源码通过；
  最终父窗口装配增量另有当前源码 100%/150% 和双向顺序原生复验。
  见 `docs/v1-m6-citation-layout-verification-2026-09-11.md` 与
  `docs/v1-m6-citation-keyboard-verification-2026-09-12.md`，后续记录见
  `docs/v1-m6-native-navigation-verification-2026-09-12.md`。
- 同类焦点陷阱已在另外九个只读表修复：大纲、搜索、图片、素材检查、历史、标签、
  诊断、编译错误和 Block 来源。十个主窗口表的五档双向焦点/方向键选行通过，
  Block 来源仍保留模型与文件。后续仅大纲、搜索、诊断、错误四个只读定位表接入
  控件范围的 Return/Enter，复用已有定位控制器；空选择、重复按键和外部焦点不触发。
  四路实际文件/行号及零保存/编译专项通过；大纲和搜索又有原生 Return 定位证据。
  单条结果空选择时不触发，空格选中后定位已验证并补入提示/指南。后续恢复原生
  控制后，错误 Return→main:3、诊断 Return→child:4 已有原生记录。诊断表原先在
  小窗口被裁切的问题现已修复：展开控制台请求合适高度，诊断内容可滚动到当前
  按钮/单元格，折叠时隐藏内容并保留标题栏。五档专项与 100%/150% 实际键盘、
  折叠/展开通过，无需拖大面板，Return 仍正确定位。未改可编辑表或赋予修复/
  恢复/插入动作新权限；不据此称全部工具/AX 布局通过。见只读表焦点、原生导航、
  四路及 `docs/v1-m6-console-layout-verification-2026-09-12.md`。
- 字数面板现能在跨页返回及反向焦点时显露“刷新”；提交检查的结果/详情可滚动。
  原生复验发现的嵌套文本末行裁切已补充长文本五档红例并修复，外层跟随只读文本
  首尾/内部滚动，不移动文本光标。实际 100%/150% 刷新、结果选行、Home/End 读详情
  和反向导航通过；零下一步/编译，文件与源码不变。Qt 辅助功能表格/文本位置警告
  仍保留，不称完整 AX 验收。见 `docs/v1-m6-reading-console-verification-2026-09-12.md`。
- PDF 更多菜单现跟随按钮禁用状态，并调用受保护的 click，不再直接发出 clicked
  绕过导出/定位等按钮的禁用保护。更多按钮现有明确键盘焦点；原生双向 Tab 和
  页码 1→2 有证据。后续已修复 1080×720 面板重叠和适宽缩放方向/页码漂移，
  几何断言核验兄弟面板/祖先边界，实际 PDF 像素核验缩放方向与比例；普通缩放/
  适宽保持阅读位置，“适合页面”居中显示整页。最终源码原生菜单选择及
  100%/150% 整页可见已复验。组合 AX/截图曾返回旧图，独立截图显示当前画面；
  不将旧图当通过证据。见 `docs/v1-m6-pdf-geometry-verification-2026-09-12.md`。
- 普通源码现区分实际正文变化与输入法候选布局通知，候选更新/取消不再误触发
  自动保存或该正文通知链的编译/PDF 失效；后续周期/缓存身份遗漏已由上面的
  独立源码版本修复，原通知修复本身不作为该路径的完整证据。
  默认 800 ms 保存只取实际正文，保留剩余候选、
  光标/滚动、Undo 和后台标签归属；外部编辑在组合输入期间走原冲突保护，包括
  部分提交已自动保存的情况。Qt 开始替换选区时的实际删除仍通知正文变化，并可
  Undo；不重定义原生输入法语义。当前源码原生默认保存已确认：提交中文后立即继续
  输入时，真实 800 ms 计时器只保存正文，保留候选/光标/Undo；取消候选不重复写盘，
  保存后可撤销/重做。拼音分段选择 `中wen` 实际仍为候选，没有伪称原生组合提交事件。
  后续键盘授权已完成真实外部冲突、默认拒绝覆盖与另存双版本验证；旧额外按键窗口
  不重新标为通过。见 `docs/v1-m6-idle-composition-verification-2026-09-11.md`、
  `docs/v1-m6-native-idle-save-verification-2026-09-11.md` 及
  `docs/v1-m6-native-conflict-formula-verification-2026-09-12.md`。
- UI Scale 的同步字体/样式更新现临时保留活跃控件引用，防止 Python 循环回收在
  Qt 仍遍历原始指针时销毁控件。隔离基线 SIGSEGV、保留引用对照与修复后真实
  StyleChange 子进程构成红/绿；24 次离屏和 6 次 Cocoa 关窗/缩放通过，引用在
  返回后释放，不关闭垃圾回收或长期缓存窗口。旧计时器原因与历史样式崩溃具体
  对象仍未证明，AX 限制不变。见 `docs/v1-m6-style-gc-verification-2026-09-11.md`。
- LuaLaTeX 字体组件的致命日志现能进入错误列表和中文检查面板，折行原因保留，
  不把 Lua 内部行号指向正文，不提供自动正文修复，也不切换引擎或放宽读取策略。
  实际受限编译经离屏主窗口验证，失败状态、源码字节和光标/滚动保持正确。
  本机 TeX Live 2025 的绝对发行版资源读取受 `openin_any=p` 拒绝已被隔离复现；
  同字节合成项目内副本可读、项目外哨兵仍拒绝。诊断完成不等于 LuaLaTeX 兼容通过。
  见 `docs/v1-m6-lualatex-verification-2026-09-11.md`。
- 普通源码保存现绑定标准保存快捷键（macOS Command+S），仍经过已有保存/冲突保护，
  不额外授权编译。真实键盘验证写盘成功且光标/滚动不变；源码与 Block 模式切换只
  激活可见模式的保存动作。普通源码、属性和真实表格委托的拼音提交/撤销/重做/
  第二候选取消及明确应用/保存已有原生证据；Inspector Control+Tab 已改用内容控件
  范围的快捷键路由。唤醒后当前源码的原生双向导航在中文提交/撤销/重做/候选取消前后
  及 100%/150% 均达到应用/别名；焦点可见，明确应用前模型/磁盘不变，键盘应用/
  保存和销毁测试窗口通过。尚不覆盖普通源码默认自动保存、分段提交、引用工具栏和
  全部原生布局。见 `docs/v1-m6-workbench-input-verification-2026-09-11.md`、
  `docs/v1-m6-focus-readiness-verification-2026-09-11.md` 及
  `docs/v1-m6-inspector-native-focus-verification-2026-09-11.md`。
- 可视公式区现已接入输入法：当前结构槽位提供 UTF-16 光标/选区查询，预编辑单独
  绘制且不进入 LaTeX 或 Undo；选区替换一次撤销，连续分段提交分别撤销。
  公式源码/可视模式均在组合输入未完成时阻止应用和模式切换。普通源码、Block 属性
  与真实表格单元格委托已有组合输入/取消/草稿归属的事件级回归。两种公式模式的
  Cocoa 拼音提交、取消、Undo/Redo 和返回计划有原生证据；最终分段 Undo 增量只
  补了事件级验证，不把先前原生记录改标为最终源码。完整 IME/AX/Windows 仍未验收，
  见 `docs/v1-m6-ime-verification-2026-09-11.md`。
- V1 本地工作源码增加“提交检查”：普通源码采用只读后台快照核对保存状态、入口、
  工具路径、实际 FINAL/PDF 输入证据、正式日志、静态资源/引用和字数口径，展示输入身份和原因。
  不因打开或刷新检查而保存、编译或联网；修改、外部事件、切换和关闭会废弃旧结果。
  Block 模式绑定当前 Block 项目，比对模型与磁盘元数据/生成源码，复用同一面板。
  实际 FINAL 绑定 job/revision/purpose/引擎、构建前后输入与 PDF 摘要；Block 结果
  按模型 revision 独立接收一次，不再写入普通源码 PDF 状态。缺少实际证据仍为未知。
  这是开发分支的 M1 只读切片，不是已发布功能；后续 M5 GUI 固定交付见下。
- 确认关闭主窗口现会在事件边界销毁 Qt 子控件，并立即退出缩放登记；取消关闭保留
  草稿和控制器，其他窗口保持可用。既有保存/Block/交付取消保护仍先执行。
  重复 24 次离屏和 6 次 Cocoa 关窗均不再留下已关闭主窗口；这修复了可重复的窗口
  残留问题，不等于已确定先前 Qt 样式表 SIGSEGV 的根因。
  见 `docs/v1-m6-window-lifetime-verification-2026-09-11.md`。
- 依赖路径边界检查改为逐组件比较与父目录深度计数，减少 Python 3.12 反复构造祖先
  路径的成本；仍逐次解析 scope、检查链接/禁止目录/越界，不缓存安全结论。
  200 子文件合成项目的同步成员刷新从约 72–76 ms 降到约 46 ms，计时器延迟约 36 ms；
  子文件保存和共享 root 归属不改为异步。原 M0 输入/字数分发指标及三组原生大图
  PREVIEW/FINAL 复核通过；这些是限定样本，不是任意工程或 Windows 性能承诺。
  见 `docs/v1-m6-response-verification-2026-09-11.md`。
- 工作源码提供“文件 → 项目配置…”：本地声明式配置可编辑、可禁用，包含参考模板、
  引擎/目录建议、可选正文字数目标和静态检查显示选项。不会改正文、创建建议目录、
  切换引擎或自动编译；字数目标与配置身份接入提交检查，关闭选项为不适用而非通过。
  64 KiB 限制、严格版本/字段验证、原子写入和内容 CAS 保留原件与冲突草稿；未知
  配置不允许覆盖。Block 绑定可见项目，配置变化废弃旧检查。这不是完整 M2 工作台。
- 本地项目向导保留中文名称，预览目标目录/模板，允许显式选择引擎及配置；只创建
  新目录，拒绝已有目录/符号链接。失败保留已创建内容并明确提示，不打开为成功项目。
  已有工作区默认保留原窗口，创建和打开不授权编译。全宽工作区状态栏复用既有
  项目/root/save/PDF 状态及导航；子文件不缩小素材/搜索 scope。Block 不借用隐藏
  源码的引擎或操作，干净项目关闭会恢复源码控件及 FINAL。原生普通创建→正式编译
  →检查→PDF 导出→重开已验证；这不是项目恢复或冻结交付验收。
- Block 保存将元数据与受管生成源码按同一模型写入，不授权或启动编译；重开可继续
  显式 FINAL。内容校验、项目锁和有界前后字节记录拒绝外部变化/未知格式覆盖；
  中途失败只回退仍属本次写入的字节，未解决的 pending 记录阻止后续覆盖，不是
  已完成 checkpoint。关闭项目/窗口会先询问保存、放弃或取消，并暂停自动写入。
  保存冲突保留窗口、草稿和外部版本；停止编译不再关闭会话。可见 FINAL 使用后台
  编译器，Source/PDF 归属不混用。原生模型关闭/重开/冲突链已验证。
- 后续 Inspector 属性草稿在内存中按目标和原始内容保留，刷新/切换不会静默丢弃，
  文本保留局部 Undo 和光标；待应用列表可重开已删除对象的草稿。输入不改模型、
  不写盘、不授权编译，自动保存/预览暂停。显式应用或确认的批量应用先校验全部
  原始对象，再形成一次 Undo；变更/删除冲突和较新的重入输入均保留。保存/关闭/
  FINAL 明确处理待应用草稿，只读检查不会误报已保存。布局字段归属于所选容器
  或槽位的父容器，pt 间距按 mm 显示，未编辑字段保留原值和单位。专项与三组
  同源码原生验证及完整回归通过；这不是 M4 崩溃恢复或完整编辑器验收。
- Block 布局/导航按钮可换行，属性/工作区可滚动；窄中央区显式切换编辑器与 PDF，
  宽区并排显示，保持原控件、焦点和 PDF 缩放。首个窗口缩放指标正确注册；加载
  布局属性不再发出编辑命令，所选槽位权重可一次 Undo，保留未编辑的回退字段。
  文本中的 Tab 仍输入制表符，Control+Tab 只移到应用，Control+Shift+Tab 返回别名。
  五档缩放、两种窗口尺寸和 Qt 键盘注入/FINAL 已验证；旧注入不能替代真实
  Control+Tab 的原生复验。高缩放仍需滚动，不是完整 M2。
- 多表格编辑已按明确 Block 绑定，切换保留各自草稿/局部 Undo，未完成的单元格输入
  也进入保存/关闭判断；应用与批量保存先校验原对象，再形成一次全局命令。未编辑
  的 opaque 字段和 False/0 保留，未知/删除对象不回退到第一张表。公式两入口共用
  原对象校验，取消/无编辑不改内容，旧对话框接受结果遇冲突保留草稿、不覆盖新模型。
  原生发现的 Enter 后立即切换/保存重复提交警告已由两项红测试复现并修复；170 项
  专项与四组同源码原生、该源码全套通过。后续图片复制使用项目锁、暂存及独占
  发布，拒绝已观测的内部链接、源变化、部分复制和重名覆盖；拖入绑定实际目标行，
  关闭会话及失败不更新模型。专项及后续真实 picker 取消/导入/链接目录拒绝、Undo/
  保存/重开 GUI 会话/两次 FINAL 通过，实际 PDF 可见所选图片；
  Windows 竞态与不支持独占发布的文件系统仍有明确限制，见图片导入报告。
- 最新本地公式替换与插入均校验新 envelope；歧义分隔符或末尾注释吞掉闭合符时
  不形成编辑计划，保留草稿供 Undo/源码修改。粘贴保留 body 的注释换行和空白；
  无法无损投影的片段保留为原文。未知宏不会仅因未识别而被改写。专项通过；
  后续真实 Cocoa 剪贴板/键盘、局部与正文 Undo/Redo、取消、源码回退及实际 FINAL
  通过；保存/编译保留光标与滚动。另修正非法草稿却提示“公式有效”的错误原因说明，
  专项、同源码原生复验及最终完整回归通过。IME/AX/Windows 不据此通过，见
  `docs/v1-m2-formula-fidelity-verification-2026-09-11.md`。
- Block 的“来源”页现提供主动刷新的只读后台检查、摘要/同内容候选说明和关联
  Block 定位；不再以更新基线摘要冒充数据重新同步。一次最多一个活动检查和一个
  最新请求，取消/记录变化/关闭/销毁废弃晚结果；导航与模型刷新不读来源文件。
  路径、流读取和候选搜索有界，链接/内部文件被排除，超限、歧义或读取不稳定为未知。
  专项和合成项目重开/字节零修改验证通过；完整回归与原生验收分别跟踪于
  `docs/v1-m3-source-status-verification-2026-09-11.md`。这不是技术合并或完整 M3。
- 普通源码“引用 → 检查项目引用（只读）”按当前入口及已打开缓冲区检查受支持的
  静态多文件/BibTeX 声明，区分重复 key、缺失引用、解析未知、使用位置和未使用建议。
  选择定义/使用位置可在内容复核后跳转；编辑、切换、取消、外部事件和关闭废弃旧结果。
  检查不保存、不编译、不联网、不导入/删除文献。原“快捷库”保留约定位置功能，
  读取改用有界严格解码与路径检查，不再当作完整项目健康状态。专项与合成窗口/
  实际 BibTeX FINAL 通过；完整回归与原生缺口见
  `docs/v1-m3-citation-health-verification-2026-09-11.md`。动态、手写、别名及分区
  文献保持未知；不是通用 TeX 解释器或技术修复，也未替换 M1 的独立静态检查。
- 普通源码“图片 → 检查素材使用（只读）”按入口和已打开草稿显示受支持的
  图片/SVG/PDF 静态使用位置、缺失、内容变化、同内容候选及未使用建议。位置数
  不是 TeX 执行次数，动态/歧义/超限仍未知；检查不保存、不编译、不移动或重写引用。
  结果经有界内容复核，编辑/外部事件/取消/关闭废弃旧结果；定位保留 PDF 视口。
  对比基线仅为本窗口上次可读观察，不是持久来源或备份。旧“快捷浏览”改为内存
  元数据缓存，不加载/写入项目索引，也不在键入时扫描旧使用计数。专项与合成窗口/
  实际图片 FINAL 通过；完整和原生边界见
  `docs/v1-m3-material-usage-verification-2026-09-11.md`。技术修复仍未接通。
- 既有三方合并和独立候选对话框现保留输入与同一行其他单元格；两侧结构/顺序
  冲突要求明确整表选择，取消不改输入，选择变化后须更新完整预览再确认。
  “确认候选”不等于应用、保存或推进来源基线，空候选入口不再是可点击的无效按钮。
  CSV/XLSX 适配器超限拒绝截断，保留表头/空行/短表头额外列及正确合并区域；
  XLSX 值与区域来自同一份捕获字节。旧项目不迁移，位置 ID 不代表稳定数据身份。
  专项与独立合成对话框/真实表格 FINAL 已验证；准备工作见
  `docs/v1-m3-merge-import-verification-2026-09-11.md`。
- 来源页另有“比较并合并来源…”真实修复流程：项目内摘要匹配的原始 CSV/XLSX，
  每张表显式声明导入选项/全部列映射和唯一行键；不按位置 ID 假设数据身份。
  全部关联表格均确认后，复核来源字节、对象/草稿身份及现有文件保护，才统一应用
  表格和来源摘要。一次 Undo 还原表格/来源，并找回被纳入的未应用表格草稿；
  取消、来源变化、漏表或未知格式不应用。原始数据不改写，保留不变的未知字段，
  磁盘保存仍使用既有保护路径。CSV 文本保留空白；XLSX 少报尺寸不再隐藏实际行，
  缺少缓存的公式拒绝导入而非视为空单元格。专项与真实合成保存/重开/FINAL 通过，
  最终源码全套通过；原生未验收。取消旧解析后会话仍只允许一个活动读取，拒绝
  尚未结束时重试造成的线程累积。每源 16 MiB、最多 20 张关联表/合计十万格，
  完整 JSON 预览更小的显示上限会限制大表应用。来源原始版本需另行保留，不是
  持久快照或 OS 级外部写者 CAS，见 `docs/v1-m3-source-repair-verification-2026-09-11.md`。
- M4 核心 API 可以显式采集选定文件的原始字节，记录相对路径/摘要，并将调用方
  提供的 UTF-8 草稿独立存放。两遍内容读取和最终身份检查后独占发布；恢复先验证
  全部对象，暂存写入/回读/复核清单，再一次发布为不存在的新目录。原项目不改，
  草稿不自动应用，未知版本/损坏/冲突/取消拒绝。合成普通与 Block 项目恢复字节、
  草稿、重开及独立 FINAL 通过。文件菜单及 History 界面现已接入选定清单和实际
  源码/Block 草稿，采集期间暂停本应用相关写入/自动编译，输入变化废弃当前结果。
  恢复绑定已审阅清单，仅创建新目录；发布先于取消完成时保留并显示结果位置。
  草稿独立保留，恢复目录本身不自动应用、切换项目或编译。后续“审阅恢复副本并
  继续草稿…”核验全部清单字节，并在确认后重新复核，才在独立窗口载入所选草稿。
  源码以一次 Undo 编辑载入；Block 模型和未应用属性分开，实际单元格输入可重开。
  首次显式保存前暂停自动写入，保存只更新恢复副本；原项目与独立草稿文件保留。
  变化/未知格式拒绝载入或覆盖，同目标须择一，Block 状态与源码草稿不能混选。
  已保存副本不再匹配原清单，后续正常打开 project/；换选原草稿须另恢复新副本。
  这不是自动崩溃恢复或完整 M4；详情和平台/断电限制见
  `docs/v1-m4-recovered-drafts-verification-2026-09-11.md`。
- 新增“文件 → 审阅中断 Block 写入并恢复…”：逐个写入目标比较并明确选择前/后/
  当前字节，仅将已知模型和匹配的受管源码恢复到原项目之外的新目录。选定当前文件、
  独立窗口草稿和全部日志/冲突版本分别保留；原项目与 pending 日志不删除、不解锁。
  确认及发布前重读，未知/损坏/变化/不一致选择拒绝；取消不覆盖原件，已发布结果
  保持可见。专项和实际 offscreen/Cocoa 重开/FINAL 已验证，最终冻结源码完整回归通过。
  日志不是完整历史快照，详见 `docs/v1-m4-write-recovery-verification-2026-09-11.md`。
- 新增“文件 → 审阅并迁移到新副本…”：勾选文件、比较原始/候选字节，再确认原目录
  之外的新副本。普通/当前 Block 字节不变；已知旧格式转换并另留全部选定原件，
  未映射字段保留、旧 raw LaTeX 不受信任且不进入 PDF。未知/冲突/缺图不转换。
  副本、草稿和迁移证据全部复核，单独确认后重新检查，才在独立窗口打开；不应用
  草稿或授权编译。旧草稿对应重新生成路径时解除目标绑定，原目标留在报告中。
  对话框关闭恢复原窗口既有自动保存，不代表永久禁用自动保存。专项和普通多文件/
  当前 Block/旧格式三条实际离屏菜单、重开、FINAL 及冻结源码完整回归已验证。
  用户恢复前台授权后，三条同类 Cocoa 流程也已通过；5 次外部 AX 树读取返回，
  进程正常结束，未见新 Python 崩溃报告。保留 IMK/字体警告和完整 IME/AX 缺口，
  见 `docs/v1-m4-migration-gui-verification-2026-09-11.md`。
- 普通源码文本历史按来源派生 bucket 和对象路径，清单绝对路径不授予读写/删除权限；
  恢复核对登记身份、严格 UTF-8、大小与 SHA-256，合法旧 bucket 保持只读。
  新索引最多 40 项，清理仅针对核验过的本 bucket 对象；清理失败可能留下未索引文件。
  确认前后复核编辑器与历史，接受后一次 Undo、未保存、不授权编译；取消/冲突保留
  原草稿，坏历史不会阻断成功的源文件保存。合成窗口恢复、保存重开和 FINAL 已验证；
  单文件文本历史不等同原始字节备份，见 `docs/v1-m4-history-safety-verification-2026-09-11.md`。
- 新增“文件 → 准备提交（PDF / 可选源码与报告）…”；原 PDF 导出、主窗口及独立
  Block 的交付入口共用实际项目绑定的审阅流程，不再直接复制缓存 PDF。保存、FINAL
  和刷新审阅是独立显式动作，沿用源码/Block 草稿和写入保护；打开或审阅不自动保存
  或编译。默认只交付 PDF，源码候选默认不勾选，源码与报告分别选择。M1 结果、
  相对输出路径、字节数/摘要和有界文本/十六进制预览与实际交付共用同一份输出字节。
  相关窗口未保存内容、输入/选项变化、确认后目标变化或磁盘内容变化拒绝交付；
  只发布到项目外不存在的新目录，取消和失败不覆盖旧交付。关闭等待单个工作线程
  收尾，若发布先于取消完成则如实显示结果。单文件、多文件、主/独立 Block 的
  离屏及 Cocoa 保存/FINAL/取消/交付、导出源码独立重编译和检查点恢复编译已验证。
  该 GUI 源码全套已通过；最新共享 FINAL/Agent 增量与未完成项见下一条，不是完整 M5；
  详见 `docs/v1-m5-delivery-gui-verification-2026-09-11.md`。
- Agent/MCP PDF 导出现校验实际 FINAL、当前输入/配置/元数据及 PDF 字节，暂存回读后
  独占发布，拒绝输入变化、未解决写入日志、取消和晚出现的目标。可移植源码包保留
  原 README/manifest、编码和换行，生成说明放在 `.icstex-package/`；过滤已知私密
  名称，拒绝不完整采集和混版。既有 wire/授权/锁及 Python 空暂存目录兼容性保留。
  已知 Block 生成入口的 Auto 使用既有 XeLaTeX 默认，支持保存的局部主题覆盖。
  这不是 GUI 逐文件选择或隐私认证。后续发现暖缓存可重新归属被外部替换的 PDF，
  共享 FINAL 已增加 latexmk `-g` 实际重建，PREVIEW 缓存和禁止项目钩子/shell escape
  保持不变；专项及 pdfLaTeX/XeLaTeX 合成复现、四条 Cocoa 流程通过。新全套发生
  Qt 样式表原生崩溃，同源码诊断复跑通过，但不能视为已修复稳定性问题。
  LuaLaTeX 在本机受限环境初始化失败，不计通过。后续 FINAL 已从本次进程 stdout
  有界采集初始 latexmk/引擎版本，固定审阅报告保存同一记录；不读取旧日志或在导出
  时执行工具。配置路径与实际自报标签分开，缺失/辅助工具/二进制身份仍未知。
  专项、三类真实合成交付/源码重编译/恢复及冻结源码全套通过；不是完整 M5，见
  `docs/v1-m5-tool-versions-verification-2026-09-11.md`。
  详见 `docs/v1-m5-agent-export-verification-2026-09-11.md`。
- Source/PDF 双栏、root-scoped 编译与 freshness、SyncTeX、Word Count、诊断、
  原子保存和正式 PDF 导出。Word Count 的 TeXcount 路径使用 Unicode
  `Ideographic` 属性避免把中文标点计为汉字；本地结构化路径按可见文本连续分词，
  支持 `%TC:ignore`、重复 include、循环保护、脚注和扩展区汉字。
- 源码编辑器的命令补全以弹窗当前高亮项为准；上下键切换后，Enter 或 Tab 不再错误
  插入首项。静态命令目录从 23 个扩展到 68 个高频模板，覆盖文本、结构、引用、数学、
  单位、项目拆分与参考文献命令；`pageref` 复用项目 label 建议，颜色和数学命令接入
  既有缺包诊断。普通源码模式的图片布局支持左右、上下和 2×2 田字排列，每张图可
  独立设置宽度且只按宽度等比缩放；同排总宽度受限，批量图片复制失败会整体回滚。
- 文件工具箱保持每个窗口的 canonical project root，不因打开子文件而缩小范围；显示
  `.tex`、`.bib`、常见图片和目录，支持 `.tex` 双击/拖拽、上下文新窗口与图片安全
  拖入。文件模型仍为只读，项目内重命名/移动经 core 检查越界、重名、符号链接、
  编译占用及 LaTeX 引用；被引用路径 fail closed，不静默改写学生源码。
- 隔离的快速图片预览与原图正式构建链；preview 不得成为正式导出源。
- 当前开发源码的快速预览支持双向 SyncTeX：PDF 双击定位原始 root/child，源码
  “定位 PDF”定位当前显示页。共用 purpose、root、revision、build id 和 viewer 路径
  校验；过期、同 purpose 重建、越界/符号链接/生成文件拒绝导航。正向查询另核对
  源码标签/文档 revision/光标，窄布局显露 PDF 后再次核对；不额外保存或编译。
- GUI Word Count 从不可变编辑器快照后台统计，单窗口只保留一个运行任务和一个最新
  待处理请求；结果校验文档、revision、磁盘依赖和窗口生命期，旧值明确显示待更新。
  手动刷新绕过有界缓存；TeXcount 与结构化分析使用同一份源码快照。
- 外部文本、图片及空闲保存触发自动编译时，统一要求自动编译开关开启且该 root 已获
  会话授权；关闭开关不再因外部文本重载额外排队。
- 项目依赖集合覆盖静态 input/include、BibTeX、图片、本地样式及成功构建的 FLS
  输入，包含未打开与暂时缺失的文件；项目外、内部构建输出和符号链接不授予读取。
  未打开依赖在后台按内容校验并更新相关 root 的 stale 状态，缺失父目录恢复与低频
  复核保留 PollingObserver。编辑器与磁盘冲突时停止自动保存，覆盖须显式确认。
- 工具箱按 dirty domain、可见性与 150 ms 防抖刷新；普通文字编辑不扫描图片目录。
  显式完整刷新和 30 秒复核仍保留，扫描在进入忽略目录前剪枝。
- 编译请求保留原截止时间、最新输入 revision、依赖 generation、引擎和工具链配置；
  单 manager 保持一个运行任务与一个最新待处理请求，FINAL 优先且取消令牌阻止晚启动。
  FLS 输入在 worker 中捕获；延后处理的 Qt started 信号不再借用较新的源码 revision。
- Block 项目控制台、ProjectSession、统一 Undo/保存/编译、表格与布局 Block。
- Formula Editor 2.0、显式提交、危险 LaTeX 过滤、可选本地 pix2tex 识别与人工复核。
- 公式的键盘、结构按钮、Undo/Redo 与 LaTeX 草稿预览同步；源码模式可改变外层
  wrapper。Tab/Shift+Tab 访问结构槽位，Enter 不提交；保留显式确认、revision 校验和
  文档单次 Undo。紧凑键盘不再重复提供确认按钮；矩阵/分段/n 次根式转源码填写。
  结构键采用统一细线与空心槽位，根号、上下标、矩阵和分段图示按相同比例缩放；
  指数和对数图示与实际动作一致，紧凑键不裁切符号。
- 普通表格支持矩形复制/粘贴、清空、导入/尺寸修改的草稿 Undo/Redo、源码预览和
  缩小前确认；空白格不会变成占位文字。Block 表格单元格编辑回写模型，稳定行列 ID，
  整块粘贴/清空一次 Undo，保留 0/False 和 HTML 粘贴。超限输入拒绝而非截断。
- UI Scale 90/100/110/125/150%、响应式欢迎页、标签栏和 PDF 工具栏。
- 当前工作源码提供“软件更新…”入口、默认关闭的启动/每日检查、应用级单例及全部窗口
  保存退出保护。Sparkle/WinSparkle 薄适配器和可选 SDK 构建接入已实现；源码运行
  与默认安装包仍不配置更新源、公钥或原生运行时，不自动联网。Beta 2 arm64
  候选已显式嵌入运行时与公钥，签名 feed 与双版本安装已验证；原生竞态/中断等
  剩余门槛未通过，公开升级尚未开放。
- RapidOCR 本地运行时和 Text Block 链路保留在源码中，但 2.1 Beta 1 用户入口禁用。
- 当前工作源码提供项目绑定、默认只读的 stdio MCP adapter 与配套
  `icstex-control` Skill。官方 MCP SDK 2.x 负责并发请求和同步工具线程卸载；core
  协调器将同项目普通读取限制为 4 路、OCR/网络各 1 路，并用 FIFO 独占队列串行化
  写入、编译和导出。文档/Block 写入继续采用 CAS、跨进程项目锁、原子替换和原始
  字节快照；完整编译/导出临界区持有项目锁，`stop` 可越过队列停止当前并取消本进程
  等待中的编译。11 个工具、授权参数、枚举 schema 与行为注解保持兼容。

## Verification Baseline

当前局部精简验证以本文件首节及 `icstex-local-simplification/full-final/` 收据为准。
学生写作第一批的历史边界见 `student-writing-first-batch-2026-09-16.md`；以下旧记录
不是本轮通过证明。

当前性能/UI D1（2026-09-13）：app SHA-256
`e2e1bc99eae6f0b2029d656847bd6e518505709b99a84dd0bcd28ac671ca1f12`；
app+tests `05d7cad19a30f4dec9bed51380a7b79b6e0afa431fc96f6151f43597c09817b4`。
48项提交检查控制器/呈现/两模式布局/五档键盘专项，10.227秒，OK；最终离屏探针
12状态通过（exec18898退出0），主要动作和选中行完整可见、无重叠，原件保留、
无保存/编译/修复动作、窗口销毁。前后检查项语义相同；技术身份完整，UNKNOWN
不算通过，显示排序不改变动作的原始索引。compileall、工具语法和diff通过。
初始焦点/变宽关闭/空间/选中行裁切失败均保留并有针对性修复；源码栈最小高度的
尝试已撤回。当前原生未验收：前/后两次尝试在活动/暴露前提超时，未进入键盘阶段。
不以离屏结果宣称原生或全仓库通过。细节见PERFORMANCE_UI_PROGRESS。
E1计数优化及17结果等价、交替性能/分配证据保留其原源码身份，不在D1重复测试。
C4原生在此前`b59188f6`完成五档/28状态（exec92376退出0），普通/Block实际FINAL、
固定PDF摘要、草稿/Undo与指示器返回通过，输入保留、窗口销毁；100%/1440×900
正文viewport661px。IMK/既有AX限制与旧失活原因保留。后续E1只改计数核心，
不重标C4的原生源码身份；完整合并、更多尺寸/状态及人工验收仍在F。

此前性能/UI C2（2026-09-12）：app SHA-256
`0bdc1b779745c07db4eee90606d96740abe2746e5f54223fcb6e69ef94c2f823`；
app+tests `c1de1f6c7e8295c2706ef69c581bf99dc0eb33bc204db1a3d1973b31af336b11`。
106项关联扩展 / 34.119秒 / exec14966，有2项旧编译器可见性断言失败，其余通过；
改为验证C1菜单入口恢复后，原两项 / 1.283秒 / OK（exec98748）。未重跑全组，
不声称完整回归全绿。早期65项及后续字体、偏好、无行号错误/Stop专项通过；
compileall、探针语法、diff检查通过。测试/原生均无本轮编译或实际发布。
测量版`7af89d23`离屏27状态（exec73596退出0），原件保留、无回调异常、窗口销毁；
Block150%/1080×720工作区1080×450px，三空辅助面板挤压已改善。后续只补诊断
错误提示与切换前保存显隐顺序，不把旧截图改标为最终源码原生验证。
原生`331a2cb8`仅完成欢迎截图，随后active/exposed均false，前提等待超时退出1
（exec23631），无后续按键，窗口销毁。无法归因锁屏/遮挡/产品；C原生门槛未过。
当前工作与失败记录见PERFORMANCE_UI_PROGRESS；历史PDF/输入尖峰和F仍开放。

此前性能/UI C1（2026-09-12）：app SHA-256
`4ae07f45012f1caebbd29bc298aeed601644966b7d4750e2e7f32fff49f94bd5`；
app+tests `56a420c14045c530ce43a7665fdefed0058baf20c9d66e8f93da9683f320365c`。
源码/窄窗/控制台、PDF、Block、交付及项目保存/导航专项83项 / 20.400秒 / OK，
exec99094退出0。compileall、工具语法、diff检查通过；未运行最终全仓库回归。
三界面离屏探针26状态（exec94622退出0），原件未变，无编译或交付，窗口已销毁。
100% / 1440×900下编辑器647px、正文viewport615px，正式编译按钮34px；不与A
原生460px直接混为同口径对照。Block150%小窗仍被辅助面板挤压；C未验收完成。
扩展测试SIGSEGV已缩小为原B2单独销毁文档的夹具保留Qt搜索引用；两用例红/绿
及最终扩展确认夹具修复，生命周期原断言保留。日志仍有Qt空document连接提示，
不把这次夹具问题解释为历史原生/样式崩溃的根因。细节见PERFORMANCE_UI_PROGRESS。

此前性能/UI B2/B3（2026-09-12）：app SHA-256
`aafb0f45d7d93fa0f05387df324cd213068d96c485e15d5544e9100e54264586`；
app+tests `a91c548787c5e4eba832afb87e3239f638bce7c569ac14f4cdf67277992dc80b`。
核心/PDF/编译专项76项通过；后续视口/搜索/回调与主题/五档布局专项54项通过
（16.118秒，exec43995退出0），最后字宽调整另3项通过（1.733秒，exec28261退出0）。
最终Cocoa搜索r5十个尺寸/缩放状态通过，callback_errors为空，源码/PDF未变、窗口
销毁（exec82570退出0）。早期r1/r2/r4失败保留，不以进程退出0掩盖r2的回调异常。
PDF五轮测量在此前`db320fa6`源码通过（exec49363退出0）：无变化PREVIEW五次均复用，
结束到可见观察中位数16.815ms；FINAL仍约442–462ms，未达到30%实验改善。
最终源码身份/compileall/diff核验通过。更早318项GUI扩展有一项不符合异步路由的
独立渲染夹具失败，已修夹具并通过相关五档专项；不称本批完整仓库回归通过。
证据和原始样本见`PERFORMANCE_UI_PROGRESS.md`。完整合并回归与人工清单仍在F。

此前性能/UI B1（2026-09-12）：app SHA-256
`4d54b93d1116b68e1abad7543a9f8367e94ff69cdd526e2779ac0745aa71a5f3`；
app+tests `c690f4b26d25497d823b4eea1c7b36ae0b940a230c16f68f99c369f57c03e943`。
318项相关集成 / 52.084秒 / OK，exec94597退出0，含双文件外部重载重入的单worker
红绿保护；前一317项及另7项观测器专项保留各自源码。以下测量/原生记录属于此前
`96e270b3ddd0c4bcc0d3fc96c4a5d28242399dfec059bc9441d57bbfa48f2d4f`源码，不改标为新运行。
日志、原始样本和边界集中在`docs/PERFORMANCE_UI_PROGRESS.md`指向的b1目录。
200-child GUI提交p95 3.664ms，计时器延误p95 1.453ms；普通原生输入p95 16.152ms。
新增200-child原生输入p95 33.257ms，但一次79.378ms尖峰仍未解。普通多文件Cocoa
保存/FINAL/固定字节交付、源码与恢复副本重编译通过。终态应用/测试摘要一致，
compileall/工具语法/diff通过；HEAD/空index不变。不是完整仓库回归、全部B验收、
历史Qt崩溃修复或发布推荐。

此前 Mac 沙箱接入（2026-09-12）：app SHA-256
`7009463b6f091f8d58f46fcfee3e08b03b3535fe9d89b0882ac7d3a133e87506`；
app+tests `14093898a54aa926b992b20106c570c1d2f6a5899af2ab35b69c157b1467cbc4`。
本次新增接入专项、真实编译/导出及停止证据见
`docs/v1-m6-macos-sandbox-integration-2026-09-12.md`。单次最终全套 1598 项 /
313.187 秒 / OK，exec 15456 退出 0；日志
`/tmp/icstex-v1-macos-sandbox-full-20260912-r1.log`，SHA-256
`358a6f5f32e1637aea70f004d2467e33e01c3b793d1cd5ecfa29e82aeda1ab95`。
完成后两棵源码摘要不变，compileall/diff 通过；HEAD/空 index 不变，未提交。
所有自有句柄结束，未开原生窗口；保留的 Python 崩溃报告数量仍为十一。

前一迁移窗口激活修复（2026-09-12）：app SHA-256
`4e0720eb707fecce1394a7b5f20868be7ea9bd668ba56b615297c23afa267e54`；
app+tests `ddf709d30299aa185630c6fc56ec290e085245d36651931c5a09425ab28a1d73`。
38 项相关回归（26.809 秒）与 1588 项全套（313.379 秒）通过；exec 32984 退出 0。
日志 `/tmp/icstex-v1-migration-activation-full-20260912-r1.log`，SHA-256
`f39dc4c6aabf1c241fe805785f243193d3d6a0a54b776cbdc86d646f1a44cb96`。
compileall 与 diff 检查通过，完成后两棵源码摘要一致。原生 r2 复现对话框关闭后
旧窗口活动、新副本可见但在后方；不是新窗口丢失。模态 wrapper 退出后显式
raise/activate 已确认的副本，两项专项红绿通过，取消不切换窗口。原生 r3 的
No→Yes 后新窗口可见且活动，焦点位于其 Block 搜索框；源/副本不变、未编译，
exec 96010 退出 0，两个窗口销毁。详见
`docs/v1-m6-migration-window-verification-2026-09-12.md`。较早 da2b8d24 源码原生 r6
退出 0，104 个状态、990 条传播按键记录，无错误/超时/中断；独立 Block 实际
交付入口和 150% FINAL/取消、迁移发布、检查点/恢复控件已观察。两份迁移副本
各 12 文件，5 份原件证据保全，无隐式编译输出；旧归档/恢复文件/独立草稿摘要不变。
独立迁移窗口激活已由后续 r3 关闭，OS/menu 纯键盘仍待查。原生 r5 保留分页焦点失败，较早
r2–r4 保留各自 Return、创建/配置和普通交付/恢复证据，不改标为当前源码。
所有本轮句柄结束、测试窗口关闭，十一份崩溃报告未新增。详见
`docs/v1-m6-recovery-migration-keyboard-verification-2026-09-12.md`。
下列旧专项保留各自源码身份。

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

- 复现 Qt 补全状态分离：弹窗已高亮 `\textit{}` 时，旧
  `QCompleter.currentCompletion()` 仍返回 `\textbf{}`；修复后 Enter/Tab 从 popup
  当前索引读取候选。
- 图片布局覆盖左右、上下和 2×2 田字排列、逐图宽度、行宽上限、等比缩放、资源复制
  回滚及 package 插入；真实 XeLaTeX 2×2 非等宽布局编译通过。
- 默认与 150% UI 缩放的 offscreen 视觉检查通过；150% 下对话框为 934×689，字段和
  浏览按钮无横向裁切，超高内容使用纵向滚动。
- 编辑器/图片 focused suite：146 tests passed。
- `python3 -m compileall -q app tests packaging/install_build_dependencies.py`：通过。
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests`：796 tests passed。
- 未打包、未发布、未推送，也未触发 GitHub Actions。

2026-09-03 高频命令补全扩展验证：

- 静态候选由 23 个扩展为 68 个且 display 唯一；`\text` 前缀在 12 项上限内包含
  `\text{}`、粗体、斜体、颜色、字体族、上下标与 `textcite`，精确 `\text{}` 排首位。
- `\textcolor{}{}` 的 GUI 插入与首参数光标落点通过；原有方向键高亮项插入回归继续
  通过。`pageref` 可按前缀建议已知 label。
- `textcolor`/`colorbox`/`fcolorbox` 缺少 `xcolor`、数学 `text`/`dfrac`/
  `operatorname` 缺少 `amsmath` 时使用既有可应用诊断；已声明 package 时不误报。
- 补全、诊断与 GUI focused suite：142 tests passed。
- `python3 -m compileall -q app tests packaging/install_build_dependencies.py`：通过。
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests`：805 tests passed。
- 未增加依赖、未打包、未发布、未推送，也未触发 GitHub Actions。

2026-09-03 项目文件工具箱验证：

- 文件树 root 稳定性、只读模型、资源过滤、图片 model MIME 拖拽、空白欢迎页与编辑器
  `.tex` 拖拽、当前/独立窗口打开及窗口 registry 清理均有 focused GUI 回归。
- 项目路径规则覆盖越界、重名、符号链接、内部目录、跨文件系统、目录自包含和原子
  rename；引用扫描覆盖 input/include/subfile、图片、BibTeX、Magic Root、样式文件、
  未保存 buffer、注释和可识别动态路径。
- 打开标签、watcher、recent path 与 compile/PDF ownership 在成功移动后重新绑定；
  活动编译和会失效的引用在任何文件变更前被拒绝。
- `python3 -m compileall -q app tests packaging/install_build_dependencies.py`：通过。
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests`：825 tests passed。
- 未增加依赖、未打包、未发布、未推送，也未触发 GitHub Actions。

2026-09-08 响应与编译优化验证：

- `python3 -m compileall -q app tests packaging/install_build_dependencies.py`：通过。
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests`：859 tests passed。
- 覆盖自动编译双重准入、未打开/共享/缺失依赖、同大小同 mtime 修改、关闭后晚回传、
  外部编辑冲突、可见面板合并、排队截止时间、FINAL 优先、stop 与冻结任务配置。
- 合成 4,000 词项目的后台提交约 0.2 ms、完成约 0.1 秒；GUI 定时器额外迟到约
  18 ms，旧同步刷新约 108 ms、迟到约 111 ms。大纲选中时编辑由约 4.09 ms 降至
  约 0.2 ms，15 次连续输入在防抖后刷新一次，且不扫描图片目录。不是引擎提速。
- macOS Cocoa 原生窗口验证两张 24 MP 合成大图：约 93 MB 原图的冷代理准备约
  637 ms，暖校验约 44 ms；preview/final 均显示 2 页且路径隔离。进程退出到可见
  PDF 内容的观测上界分别约 125/324 ms，暖 preview 修改约 30 ms；不等同显示器
  scanout 时间，也不是普通学生项目性能承诺。详细样本与截图见优化验收报告。

该源码已形成本机开发构建并同步至远端分支，不改变公开 2.1.0-beta.1 安装制品状态。

2026-09-08 快速预览反向 SyncTeX 验证：

- `python3 -m compileall -q app tests packaging/install_build_dependencies.py`：通过。
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests`：875 tests passed。
- SyncTeX、preview pipeline 与 PDF panel focused suite：37 tests passed。覆盖预览与
  正式 PDF 路由、相同 revision 的新 build 重载、过期/跨 root、Qt 晚到信号及查询中
  开始重建、缺少工具/数据、项目路径边界和页间隙。
- 真实本地 pdfLaTeX 生成含代理 PNG 的两页快速预览；offscreen 与 macOS Cocoa 原生
  窗口均在 90%/125% PDF 缩放与滚动后，通过双击第二页正文打开原始子文件第 2 行。
  原始源码文本未改动，未生成正式 PDF，原生窗口显示快速预览标识与正确源码落点。
- 未增加依赖、未改变 MCP wire contract，也未提交或推送。本机后续构建/安装状态见下。

2026-09-08 最新本机 macOS 更新验证：

- `QT_QPA_PLATFORM=offscreen bash packaging/preflight.sh`：通过；compileall 与完整
  958 项测试通过（432.518 秒）。测试输出包含欢迎页缩放回调访问已删除 QLabel 的
  非致命异常；不把测试通过等同于该回调不存在问题。
- PyInstaller 从冻结源码生成独立本地构建；版本仍为 `2.1.0-beta.1`，本地构建标识
  `20260908-204029-b002533f`。应用、QtCore 与 Python framework 均为 arm64，
  bundle ID 为 `com.icstex.app`；ad-hoc 深度严格签名检查通过，未执行公证。
- 157 个嵌入应用模块的字节码/常量及 35 项资源与冻结源码一致，另核验 1 个 namespace
  package。包含公式/表格、后台统计、依赖追踪、预览反向 SyncTeX 与更新器入口。
  安装副本与独立构建的递归 checksum/symlink 比较无差异。
- `/Applications/ICSTeX.app` 冷启动、欢迎页和 LaTeX 环境就绪状态已观察；实际安装版
  公式空心结构键、实体键输入、Tab 分母导航、Enter 不提交和取消不改文档通过。
  表格窗口的空白单元格、撤销/重做及矩形操作入口已截图检查，不重复声称完整表格
  功能或项目编译在安装版重新验收。
- 软件更新窗口明确显示未配置更新源与签名公钥；自动检查和检查按钮禁用。包内未
  配置 app-update.json、Sparkle framework 或桥接库；不开放联网升级。
- 旧应用已在替换前退出，完整保留于用户 Application Support 的
  `Install Backups/20260908-204029/`；原始 bundle/可执行文件 inode 与 SHA-256 未变。
  回执含新旧哈希、源码指纹、326 项输入的已核验快照和回退说明。原先打开的学生
  文件前后 SHA-256 一致；临时验证标签已关闭，应用停留在欢迎页。观察期无新增
  ICSTeX 崩溃报告；未改动公开制品、推送或发布。

2026-09-08 公式与表格交互验证：

- 复现并修复：实体键盘输入不刷新公式预览、源码 wrapper 切换无效、表格空白被
  占位文字覆盖、Block 单元格未回写、0/False 隐藏、重复行列 ID 和粘贴逐格 Undo。
- 按用户补充反馈重绘结构键：移除灰色实心占位块，统一圆角、边框和图标线宽，
  对齐根号横线与内容框，并修正 e/10 指数与自定义底数对数的图示。绘制回归覆盖
  空心槽位和 42×40 / 120×40 逻辑像素键内留白；所有分类页均已原生截图检查。
- 必需 compileall 通过；最终 offscreen 完整复跑 912 项通过（245.646 秒），
  原生 Cocoa 专项 9 项通过（1.326 秒）。此前一次全套运行的 1 秒进程树测试没有
  生成 PID 文件，单项和完整复跑均通过，未因此修改编译器逻辑。
- 原生独立窗口验证覆盖 800–1040 像素宽度、Tab 分式输入、Enter 不提交及矩形撤销。
  合成数据截图与报告位于
  `docs/data/editor-interactions-2026-09-08/`，重现入口为 `tools/probe_editor_interactions.py`。
- 本轮 12 个编辑器相关 app 文件的路径/内容 SHA-256 为
  `0ff367e2189d5cd1314fac9a60c282bc899435171e5a7c54e86d90f8cdf9c7b4`，
  范围列于本轮 `PROJECT_LOG.md`。回归期间共享工作树另有 `app_updates`、
  `app_update_controller`、`update_backends`、`update_dialog` 及主窗口接线变更；
  这些并行更新器改动不在本次编辑器验收内，不能沿用本轮全套结果作为其集成验收。
- 本轮没有读取学生文档或运行 OCR；原生窗口已暴露并截图检查，但 System Events
  未能枚举独立 QA 进程窗口，因此不声称已通过 macOS AX 自动化验收。Windows 未实测。
- 编辑器源码验收时未替换本机应用；此后已由上方独立本机更新验证覆盖安装状态。
  既有公开发布制品仍未更新。

2026-09-08 原生更新器源码验证：

- 必需 compileall 通过；最终 offscreen 完整回归 958 项通过（484.198 秒），
  含并行编辑器源码与 46 项更新器专项。真实 MainWindow 合成文档的保存、选择区、
  滚动位置、保留窗口及安装失败后恢复编辑均通过；未使用学生文档。
- macOS Cocoa 真实窗口显示更新入口与源码版不可用状态；100%/150% UI 缩放截图
  已检查，更新库未加载。结果与图片在 `docs/data/app-updates-2026-09-08/`。
- 官方 SDK 归档摘要核验及四目标暂存通过；macOS arm64/x86_64 桥以警告即错误
  编译通过，Windows arm64/x64 DLL 文件架构核验通过。最终固定 feed 委托加入后
  两种 macOS 桥重新编译、所带 Sparkle framework 深度严格签名检查通过；arm64
  桥在正确 Frameworks 布局下加载通过，未初始化原生更新流程或访问更新源。
- 冻结 app Python 树为 170 个文件，路径/内容 SHA-256
  `b002533f20a35533487f6c108c96a49163d05abfc377616a12f16d4cc60a1c7b`。
  默认离线本机构建已由上方独立安装验证覆盖；本更新器源码任务本身没有打包应用、
  替换安装版、签名发布或触发 GitHub Actions。
- Windows 原生调用、配置后的 Sparkle 初始化、真实签名 feed/双版本安装与失败
  恢复均未验收。不声称自动回滚、跨进程安装锁或 Windows feed 元数据签名。
  维护者接入与开放门槛见 `packaging/UPDATES.md`。

2026-09-09 macOS arm64 Beta 签名与原生升级验证：

- 必需 compileall 与最终 packaging preflight 通过；完整 offscreen 回归 965 项
  通过（246.461 秒）。既有 welcome-page/deleted-QLabel 非致命异常仍出现，未修复。
- 版本 `2.1.0-beta.2`、序号 `210002`。维护者已完成钥匙串授权；官方 Sparkle 工具
  签署归档和 appcast 后，以公钥独立验证两者的精确字节均通过。专用私钥保留在本机
  钥匙串，只有公钥进入 `release/updates/macos-arm64-beta.json`；未导出私钥。
- 更新桥与 bundle 最低 macOS 版本为 13.0；本机 arm64 原生运行已测，不代表
  macOS 13 实机验收。ad-hoc 深度严格签名通过；未 Developer ID 签名或公证。
- 原生验收发现并修复 Qt 更新设置窗口遮挡 Sparkle 进度的问题；手动检查隐藏设置，
  活动会话可通过“查看更新进度”重新调出，不重置检查时间或安装状态。增加 3 项
  controller 回归并更新视觉测试；自动检查不重入活动会话。
- 冻结源码生成 r2 候选，归档 SHA-256 为
  `342c0300a6d7dc82d087aaee0703576996666678c01b6b01f163c16574b1061f`，
  长度 56,211,122 bytes。app 211 文件摘要为
  `d48056f79629e13a861d9082751075134f63c854032408c19bb0e695566d5474`。
- 私有 QA bootstrap 210001 通过原生安装器替换为精确的签名 r2 210002，并自动重启；
  完整 bundle checksum/symlink 比较无差异，独立冷启动通过。合成文档保存结果与
  预期 SHA-256 相同，已有合成文档字节未变。测试源仅固定回环地址例外；正式源码
  仍强制 HTTPS，r2 固定正式域名。没有替换主安装版或打开学生文档。
- 原生测试覆盖 HTTP 503、篡改 feed/归档拒绝、无更新、下载取消、全窗口 Save/Cancel、
  未命名 Save As 取消、预先运行的同路径进程拒绝、低磁盘空间和只读安装位置。
  故意无法启动的签名 QA 包未自动回滚；恢复完整可信旧 bundle 后 checksum、签名和
  冷启动通过。不能声称自动回滚或跨版本草稿恢复。
- 发布暂缓：GUI 进程扫描不覆盖主进程退出后的安装生命周期。Sparkle 2.9.6 上游
  终止监视代码仅选择首个进程并明确说明晚启动实例的限制，尚不能建立所需互斥保证；
  这不是已复现安装损坏。晚启动竞态、强制中断与真实公开 HTTPS 分发仍未验收。
- Vercel 原项目预览 `dpl_7KCFhWRVwYtSdbS2WdUyavEFqobJ` 为 READY，只有现有网站
  和缓存配置，没有 appcast；正式部署、GitHub Beta 1 资产与本机主应用未改动。
  详细矩阵见 `docs/beta-update-verification-2026-09-09.md`，当前候选/剩余决策见
  `docs/BETA_ACTIVATION_HANDOFF.md`。源码同步状态见下，不改变这些发布门槛。

2026-09-10 用户授权的源码同步验证：

- 必需 compileall 通过；offscreen 完整回归 965 项通过（196.352 秒），退出码 0。
  既有 `welcome_page.py` 的 deleted-QLabel 异常仍出现，本轮未修复或新增原生验收。
- `git diff --check`、网站元数据和已发布制品一致性检查通过；严格源码版本发布检查
  仍因 Beta 1 manifest 与 Beta 2 源码不一致而正确拒绝，不将旧制品改名为 Beta 2。
- `fef3731` 已推送并通过 `git ls-remote` 核对；使用 `[skip ci]`，查询未见该提交的
  Actions run。Vercel 最新部署身份未改变，GitHub 仍只有 Beta 1 prerelease。
- appcast 移至 `release/updates/candidates/macos-arm64-beta-r2.appcast.xml`，
  移动前后 SHA-256 均为 `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`。
  未打包、安装、签名、部署或发布；下一代开发说明入库不代表 M1–M6 已实现。

2026-09-10 V1 M0 与部分 M1 本地开发验证：

- M0 完成能力差额、合成 single/multi/Block 项目、未保存/外部冲突/缺失资源变体、
  响应基线和回归目标；修正 roadmap 中过时的版本建议。详细账本见
  `docs/V1_IMPLEMENTATION_PLAN.md`，不代表 M1–M6 已完成。
- 必需 compileall 通过；最终 offscreen 完整回归 998 项通过（212.415 秒），退出码 0。
  提交检查/Block 集成/文件监听 focused suite 62 项通过（4.974 秒）。
- 原先欢迎页缩放 lambda 改为 Qt 绑定 slot；重复销毁页面后发出缩放信号的回归通过。
  最终完整测试和原生 probe 没有 deleted-QLabel RuntimeError/RuntimeWarning；不据此
  声称全应用 AX、IME 或原生生命周期验收完成。
- 最终 Cocoa 源码窗口：普通多文件项目真实生成并显示 1 页 FINAL PDF；引用问题
  导航至子文件第 4 行，外部修改废弃旧检查；合成原件恢复后字节一致。
  Block 检查不启动编译器，元数据/模型/生成源码比对通过；真实元数据文件事件清除
  旧结果。两模式检查面板经过 90/100/110/125/150% 缩放检查，Block 底部区域用标签
  共享空间；周围 Block 编辑区仍有高缩放裁切，未视为 M2 验收通过。
- 最终原生验证的 app Python 路径/内容 SHA-256：
  `7af81592d3235997563f6b835511120e26a8291d17302bab20cf96b0af08f140`。
  复现、失败修正与剩余边界见 `docs/v1-m0-m1-verification-2026-09-10.md`。
  本轮没有提交、推送、打包、替换安装版、签名、部署或发布。

2026-09-12 V1 本地工作源码的当前验证：

- 解锁后恢复 Cocoa 原生键盘操作。引用 Tab/选行/Space 子文件定位通过，同时发现
  150% 焦点在视口外、工具栏被跳过及装配顺序错误；焦点滚动、单入口工具栏和
  提前绑定父窗口已修复。r5 保留五档按钮/九工具原生记录，最终源码 r6 另验
  双向工具栏/面板顺序及 100%/150% 定位，原文件不变、零编译、窗口已销毁。
  四类只读表 Return/Enter 的正反专项通过；app 9b2f44f5 的大纲/搜索原生记录保留
  原身份。先前 app 60e50d6f 的错误/诊断定位及 PDF 记录仍保留原身份；该次发现的
  诊断内容裁切已修复。其两个五档专项由 10 条失败断言转绿，269 项扩展
  通过；该源码原生 100%/150% 双向 Tab、选中行滚动、折叠/展开和 Return→child:4
  通过，不拖分隔条。exec 86860 退出 0，文件不变、零编译，窗口销毁。
  先前独立生产 PdfPanel 的原生 200% 合成 PDF 观察清晰可读，未见明显块状像素化；
  只覆盖该 PDF、889×562 视口、DPR 1.0，不证明其他字体/HiDPI、此前离屏原因或
  新的 FINAL。exec 17850 退出 0，PDF 摘要不变、窗口销毁，未改 PDF 渲染器。
  先前字数/提交检查修复又补充跨页返回、工具箱展开与长文本首尾可见性；
  原生 r1 暴露的嵌套裁切经五档十条红断言后修复，r1 不改标为通过。
  该源码原生 r2 的 100%/150% 刷新、结果/详情首尾和反向焦点通过，exec 58087 退出 0，
  原文件/源码缓冲不变、零下一步/编译，窗口已销毁。Qt 表格越界及文本位置警告
  仍记录于收据，不以正常退出解释其原因。
  此前 PDF 布局/缩放/整页居中专项 app SHA-256
  `08de3e1c73ea586268873b99d67a6be3197198e372490033f987b35dc8377663`；
  app+tests `c1bd2ca4016ca6fd4aa09a36eb1a4368e90a89ee2df29b66aed9263168919408`。
  最终专项 16 项（7.271 秒）、扩展 291 项（77.035 秒）通过；冻结全套
  1573 项（231.650 秒）通过，顺序 exec 78234 终态退出 0。
  日志 `/tmp/icstex-v1-pdf-geometry-full-20260912-r2.log`。
  五档 35–60px 面板重叠已由真实边界红例修复；原 visibleRegion 断言不足。
  缩放使用实际 DPI/每页大小，普通缩放与适宽保留阅读点，并在滚动条改变视口后
  补偿位置；翻页、换文档、清空与销毁取消补偿。混合页尺寸的实际红色标记像素、
  首中末页与双向缩放均有回归。中间源码原生 r2 又暴露“适合页面”页底裁切，
  整页边界红例后改为居中；最终源码 r3 原生菜单选择与 100% 第 2 页、150%
  第 3 页完整可见通过（exec 74670 退出 0）。早期 r1/r2 保留自身源码身份；
  组合 AX/截图的旧画面不改标为新状态，独立截图已核对当前状态。文件/源码不变，
  零导出/定位/编译，三个窗口销毁；不推断全部字体/HiDPI/AX 验收。
  终态源码身份匹配，compileall/探针语法/diff、HEAD/空 index、候选 feed 已核对。
  十份旧崩溃报告及此前空焦点 QtTest SIGABRT 共十一份均保留且未新增；全部句柄
  结束。该次源码改动为 PDF 布局与视口，没有 core/PDF 渲染器或权限变更。
  后续原始要求审计与模态键盘专项见本文件当前状态；不再扩展无界覆盖，
  不重启已完成的定位/输入法案例来累计通过数。未提交、推送、打包、替换安装版
  或发布。见原生导航、四路历史及
  `docs/v1-m6-console-layout-verification-2026-09-12.md` 及
  `docs/v1-m6-reading-console-verification-2026-09-12.md` 和
  `docs/v1-m6-pdf-keyboard-verification-2026-09-12.md` 及
  `docs/v1-m6-pdf-geometry-verification-2026-09-12.md`。
- 先前九个额外只读表的 81 条红断言、273 项专项和 1554 项冻结全套保留于
  `docs/v1-m6-readonly-table-focus-verification-2026-09-12.md`，不改为原生验收证据。
- 原生引用检查在 1080×720、100% 复现 Tab/Shift+Tab 表内循环，19 个状态和完整
  只读结果已记录；无文件改动/编译，exec 40699 终态退出 0。两个只读表的焦点
  导航修复后，两条基线红例转绿，46 项专项（3.663 秒）及五档离屏布局/子文件
  定位通过。当时 app SHA-256
  `4f83dd34551c6fcf6fd5912df54b690471dd5fc8678e7ffdf687b6c66f0a217a`；
  app+tests `2f9a46c25b5e594a4c64ca9497f1583ef947dcc5efd80e5732557de9f4aabd14`。
  修复后原生 r3 的首次 CUA 调用返回 Mac 新近锁定，未发送验证按键；仅中断该
  合成探针，exec 94853 终态退出 130，不是原生通过。初次观测工具 tuple 调用
  错误及离屏列表 Return 未定位的失败均保留；最终回归通过 Tab 到定位按钮再
  Space 的明确操作，不声称列表 Return 已验收。见
  `docs/v1-m6-citation-keyboard-verification-2026-09-12.md`。
  最终冻结全套 1552 项（152.832 秒）通过，exec 74555 终态退出 0；日志
  `/tmp/icstex-v1-citation-native-focus-full-20260912-r1.log` SHA-256
  `4a2cd243e9e41ad806066f01f3cad8b01e894c5416a68a445f77740e51a98328`。
  终态 app/app+tests 身份匹配，compileall/探针语法/diff 通过；十份原崩溃报告、
  HEAD/空 index 和候选 feed 不变，全部探针句柄结束。没有提交或发布操作。
- 用户确认键盘可接管后，实际外部文件修改触发冲突并保留正在组合的拼音/本地草稿；
  取消、提交中文、Save 默认 No 和原生另存副本均通过，外部原件与本地中文副本的
  字节各自正确。当前源码公式可视/源码模式均通过分段转换、取消、完整提交、一次
  撤销/重做和 Command+Return 确认；每种模式 20 个实际 IME 事件、7 个状态变化。
  exec 65068/96322/13141 均终态退出 0，三个窗口销毁。保留 IMK 警告和 CUA 关窗后
  观察超时；以进程与销毁报告证明结束，不当作全 AX 验收或实际写入/FINAL 的替代。
  当时源码必需全套 1550 项（169.147 秒）通过，exec 32613 终态退出 0；日志
  `/tmp/icstex-v1-native-conflict-formula-full-20260912-r1.log` SHA-256
  `9f410c6a7829d0f7e874dca166faf2c9bd2db11880c9554bc0413b761fad95a7`。
  compileall/diff 通过，终态 app/app+tests 仍为下列身份，十份崩溃报告、HEAD、空
  index 与候选 feed 均不变。本轮无产品、测试或观测工具源码变化。
  见 `docs/v1-m6-native-conflict-formula-verification-2026-09-12.md`。
  默认 800 ms 原生保存/取消/Undo 的已完成证据仍见
  `docs/v1-m6-native-idle-save-verification-2026-09-11.md`；不把旧中止 r2 重新标为通过。
- 前一公式坐标/目标保护 app SHA-256
  `489657f34516f5bfeee0934b84a26885e217e8ff3ea7cad05f3f1297819d0085`；
  app+tests `136e1892c4de31d04db0de8a2a40e97f7d58877238e90ab0784e161fc31ad59a`。
  基线 7 项中 7 个失败断言/子用例及 1 个已删除编辑器异常；另一个包裹符光标用例
  23/25 失败。最终专项 133 项（5.788 秒）、扩展 277 项（54.319 秒）和必需全套
  1550 项（145.308 秒）通过，顺序 exec 30576 最终退出 0；终态摘要匹配。
  `/tmp/icstex-v1-formula-full-r1.log` SHA-256
  `7d9ecd3fd31f9f9714ce43116423dae07a52021bd7cb6ac382f7e2c9a3c136b1`。
  实际离屏按钮/保存重开/FINAL/外部重载拒绝 r6 通过，exec 19189 退出 0。r1–r5 的
  灰色字形漏计、缩放取景失败保留；修正后公式区域/空白对照为 115/0 像素，已检查
  FINAL 与草稿保留截图。该校验不证明 200% 像素化已解决或原生字体/输入法通过。
  compileall/diff 通过，十份原崩溃报告、HEAD、空 index 与候选 feed 不变；公式专项
  全部句柄结束，该专项无前台操作。随后唤醒后的原生复验见下一条。
  见 `docs/v1-m6-formula-coordinates-verification-2026-09-11.md`。
- 同一 app/app+tests 源码的原生 Inspector 焦点 r2 完成，exec 58955 退出 0；
  12 个真实输入法事件、双向 Apply/Alias 焦点及 100%/150% 中文草稿保全通过。
  一次键盘应用、一次 Command+S，最终 `base 中文`、另一张表不变，无编译器；
  测试窗口已销毁。报告 SHA-256
  `94df0996a30b7b30603d12d533313cf7a532b436e99761b2ea65dfcab4f2e4b0`。
  输入源未切换，缩放仅改临时配置，无新崩溃、Git 或制品变化。
  后续默认保存原生证据见本节首条；R2 原生引用/工具导航及更广布局仍待验。
  见 `docs/v1-m6-inspector-native-focus-verification-2026-09-11.md`。
- 前一轮表格插入/目标保护 app SHA-256
  `61b4578c66fda33f78ddb63952ade35c7069c93e9947cc8fd18fbc318614ec8a`；
  app+tests `f24bcd01113d0398c08c37950abe1e1e66772ac674e1656f7232432737210a0a`。
  目标拒绝四条基线失败；最终专项 14 项（2.020 秒）通过。扩展 268 项（51.853 秒）
  与必需全套 1538 项（142.721 秒）均通过，顺序 exec 94339 最终退出 0。
  `/tmp/icstex-v1-insertion-full-r2.log` SHA-256
  `540b0ae31a2cc48b887c2d5b3fdeab041e93e035f4a16a77c555a668cfb4b832`。
  实际离屏按钮、六次取消、单次撤销与旧历史、保存重开/FINAL 及外部重载拒绝通过，
  exec 67845 退出 0；已检查草稿保留与 FINAL 两张图。终态源码摘要一致，compileall/
  diff 通过，十份原崩溃报告、HEAD、空 index 和候选 feed 不变；全部句柄已结束。
  未操作前台或将离屏通过扩展为原生验收；后续普通公式坐标边界修复见上一条。
  见 `docs/v1-m6-table-insertion-verification-2026-09-11.md`。
- 前一轮关闭标签释放修复 app SHA-256
  `890bbd2c2968cbd5de120a729cccb6bb0951d1f9af5d3a48db8fbcdfcb0fd514`；
  app+tests `39f1a73e8c287e85bf8ef69b47052bdf55bfcaa681064815d31ceb2a72f86f50`。
  基线关闭/放弃两条销毁断言失败，取消断言通过；修复后专项 42 项通过（6.408 秒，
  exec 50604 退出 0）。24 个闭合编辑器从仍有效降至零；存活文档不变。
  扩展 254 项（49.498 秒）及必需冻结全套 1524 项（140.927 秒）均通过，顺序
  exec 57755 的两个子命令与最终工具退出均为 0；日志
  `/tmp/icstex-v1-tab-retention-suite-r1.log`。终态后源码摘要一致，compileall/diff
  通过；HEAD、空 index、候选 feed 不变，十份原崩溃报告未增加，全部句柄已结束。
  独立四夹具/五编辑器及原 131 项前缀的双重观察均确认：Qt 在 GUI 线程销毁，
  后续包装器可在后台回收。不能把此正常现象当作原 SIGBUS 的因果证据。
  该源码另复现六次取消表格后六个对话框仍存活，后续修复与实际插入保护见上一条。
  未重试原锁屏控制通道，未启动原生 QA 窗口；完整原生/历史崩溃归因仍待验。
  见 `docs/v1-m6-tab-disposal-verification-2026-09-11.md`；此前引用环、计时器
  SIGBUS 和路径回调的原始证据保留于各自 receipt，不改标为当前源码原生通过。
- 上一个已通过全套的 M6 只读源码身份修复 app SHA-256
  `c7e9859961795c2ec082583e9a7aad2fc2e0d60e859e614d784e4a5a4e09676f`；
  app+tests `c317ad7e93f462154fff59bbc67185e33279ea3ec6f0f89a9e9ba097e186e4bf`。
  285 项专项通过（38.527 秒，exec 25148，退出 0）；四项基线红例与真实控制器/
  缓存/晚到回调、撤销和屏蔽通知重载验证闭合。冻结全套 1518 项通过（140.039 秒，
  exec 4947，明确退出 0），日志 `/tmp/icstex-v1-source-identity-suite-r1.log`；
  终态后源码摘要一致，compileall/diff 通过。既有七份 Python 崩溃记录未增加；全部本轮
  句柄已结束，HEAD、空 index、候选 feed 不变。
  本轮没有前台/原生 UI 操作；旧源码原生证据保持原身份。
  详见 `docs/v1-m6-source-identity-verification-2026-09-11.md`。R1 周期/缓存错误
  失效已本地修复；下一项是当前源码的 R1/R2 原生焦点/输入法；R3 历史计时器原因/AX、
  R5 受限引擎及平台/真人/发布门槛仍开放，不是完整 V1。
- 前一 M6 工作台原生验收探针补强，应用源码未变；app SHA-256
  `d8175978f5d47186440a6ccd8abb9b785e4b128b301ea2c79cbecf8c6965550b`；
  app+tests `2e01d70c6a5623c75be57997bef61dbb671729111ae61cd90f9b42d39d771584`。
  新增 11 项探针记录回归，9 个误判反例修正后通过；扩展输入法/草稿专项 121 项通过。
  冻结全套 1482 项通过（257.308 秒，exec 20957，明确退出 0），日志
  `/tmp/icstex-v1-workbench-evidence-suite-r1.log`；终态后摘要一致，compileall/diff
  通过，无新 Python 崩溃报告。原生普通编辑器 exec 41820 因锁屏无法输入，
  自行达到 600 秒期限后退出 1 并销毁窗口；原文件不变，不计原生验收通过。
  所有本轮句柄已结束，纠正后的原生采集路径仍待解锁后验证；详见 IME 验证记录。
- 前一 M6 输入法接入及分段 Undo 修复 app SHA-256
  `d8175978f5d47186440a6ccd8abb9b785e4b128b301ea2c79cbecf8c6965550b`；
  app+tests `0e85d64636b7c8fb436b24c4cd02b17de58e2ba64c1d05179cae0923141cc324`。
  109 项输入法/草稿专项及后续 63 项公式/分段 Undo 回归通过。Cocoa 两种公式模式
  的真实拼音/取消/Undo/Redo/Apply 通过（app b6da0987）；最后分段提交边界修复
  的原生扩展仍须补验。第一次完整回归在编译超时用例缺少孙进程 PID 文件，未记通过；
  该项独立复跑通过，未证明时序原因已修复。最终冻结全套 1471 项通过（138.051 秒，
  exec 39883，明确退出 0），日志 `/tmp/icstex-v1-ime-suite-r2.log`；终态后两项摘要
  一致，compileall/diff 通过，无新 Python 崩溃报告，所有句柄/测试窗口已结束。
  详见 `docs/v1-m6-ime-verification-2026-09-11.md`。这不关闭完整 A12 或 M6。
- 前一 M6 路径检查优化 app SHA-256
  `e1bf4fa9720c84cae9bda909da55dd890103f85ec36561f3a3512500e6e647da`；
  app+tests `22fe3ad301b10219aedd3bd6d198b5341c89766c30438f08a23aa3ee4247649c`。
  58 项专项通过；同样本响应/成员刷新及三组 Cocoa 大图冷暖/编辑构建共 15 次可见 PDF
  通过。原生探针首次在最后窗口关闭后的复用中超时，另有探针自身迟到回调错误；
  仅修正探针退出策略与定时器对象归属后复验通过，未改应用退出/渲染策略。
  最终冻结全套 1457 项通过（138.295 秒，exec 88033，明确退出 0），日志
  `/tmp/icstex-v1-m6-response-suite-r1.log`；终态后两项摘要一致，compileall/diff 通过。
  无新 Python 崩溃报告，所有本轮句柄/窗口结束。数值报告位于 `docs/data/v1/m6-*.json`，
  原生截图只在本机留存。下一项是逐项复核 M1–M6/A01–A14，不据此宣布完整 V1。
  详见 `docs/v1-m6-response-verification-2026-09-11.md`。
- 前一公式原生验证及提示修正 app SHA-256
  `e4e978cb79d3321462bbe52d6597195ff1a0da13f93df7273a7d75887a635baf`；
  app+tests `1627c79866b811f38951d7ec5995ea43bfc548067ac88abcec7b95513e6784a3`。
  非法草稿提示有红测试，修正后 138 项专项通过；真实 Cocoa 剪贴板、原生 Undo/Redo、
  Cancel、源码无损回退及实际 pdfLaTeX FINAL 通过，保存/编译不移动光标与滚动。
  原生 exec 90551 退出 0，最终截图显示正确公式及已完成 FINAL，所有窗口销毁。
  最终冻结全套 r2 1455 项通过（142.032 秒，exec 12954，明确退出 0），日志
  `/tmp/icstex-v1-m2-formula-native-followup-suite-r2.log`；终态后摘要一致。
  原 r1 日志已为 1455 / OK，但回收句柄没有返回退出码；保留其证据缺口，不推断退出 0。
  Compileall/diff 通过，无新 Python 崩溃报告。该批句柄已结束；M6 同样本响应/统计及
  PREVIEW/FINAL 工作量的后续复核见上一条。
  详见 `docs/v1-m2-formula-fidelity-verification-2026-09-11.md`。
- 前一构建版本标签 app SHA-256
  `d7d57520c5a1a26044ed70457df5ecc79d839707c8475f6dddf5a954658e3219`；
  app+tests `48066a6e4cbb26176dc0ce213fea8ade3dfaa91235c64d0c31fd154b6ffb38bc`。
  94 项专项与单文件/pdfLaTeX、多文件/BibTeX、Block/XeLaTeX 实际交付/源码重编译/
  检查点恢复通过，原件字节不变。最终冻结全套 1455 项通过（111.922 秒，exec 21755 /
  PID 73377，退出 0）；日志 `/tmp/icstex-v1-m5-tool-versions-suite-r1.log`。
  终态后两项摘要一致，compileall/diff 通过，无新 Python 崩溃报告；本轮未使用前台窗口。
  其后在相同应用/测试源码上补完真实图片 picker 取消/导入/链接拒绝、Undo/Save、
  新 GUI 会话重开/再次 FINAL，exec 79095 退出 0，截图显示正确图片，窗口销毁。
  后续完整回归再次通过 1455 项（139.577 秒，exec 3225 / PID 75313，退出 0），
  日志 `/tmp/icstex-v1-m2-image-import-followup-suite-r1.log`；终态摘要一致，
  无新 Python 崩溃报告。该批句柄已结束；公式真实剪贴板/键盘/Undo 后续结果见上一条。
  详见 `docs/v1-m5-tool-versions-verification-2026-09-11.md`。
- 前一窗口生命周期 app SHA-256
  `2f8d15e03061a54fa7780ec07d8dde7164a661123286bece4d00b13a5f63e16d`；
  app+tests `aa139cd92b649c2669a0a771bc2b099829e86afa3a21dd27ce4aa43b358c2552`。
  关闭后窗口存活有两项红测试，修复后 13 项专项、244 项扩展通过；最终登记/存活
  回归再次通过。原空窗口探针确认 24 个已关闭窗口和 15,275 个控件在 GC 后仍存活；
  显式销毁对照及修复后仅保留当前窗口，不以 RSS 高水位宣称内存已全部归还系统。
  Cocoa 6 次关窗/连续缩放及四类项目交付、源码/恢复副本重编译均通过，窗口已关闭，
  未新增 Python 崩溃报告。原 SIGSEGV 在自然或强制 GC 探针中均未复现，不能宣称同因。
  最终冻结源码完整回归 1446 项通过（113.088 秒，exec 85117 / PID 70795，退出 0），
  日志 `/tmp/icstex-v1-m6-window-lifetime-suite-r1.log`；终态后两项摘要一致，
  compileall/diff 通过。该批测试/原生句柄已结束；后续版本标签证据见上一条。
  详见 `docs/v1-m6-window-lifetime-verification-2026-09-11.md`，完整 M2-M6/发布未完成。
- 前一 Agent/共享 FINAL app SHA-256
  `d0a7012904829a786d3d21aa7950abfda7d4fc441afc9ac440bb9dea494f5ac6`；
  app+tests `85806c1ce44006ed4178d8fc9c3f29706c7c632cdf263f6a82d8b87493283a4e`。
  前一 Agent-only 源码 1443 项全套通过（392.115 秒，exec 44063 / PID 64609，退出 0），
  摘要核对一致。其后共享 FINAL 强制重建修复有红/绿及 130 项专项通过、普通/Block
  实际 stdio MCP、pdfLaTeX/XeLaTeX 暖缓存替换和同大小同 mtime 输入重建证据；
  LuaLaTeX 受限初始化失败，不加 `-g` 仍失败，未改变系统环境或放宽安全策略。
  当前四条 Cocoa 保存/FINAL/审阅/取消/交付与源码、检查点恢复重编译通过，exec 83942 /
  PID 66842 退出 0，窗口已关闭；未做外部 AX 或真实 IME 验收，保留窄 AX 保护警告。
  但新完整回归 exec 51729 / PID 66375 退出 139；崩溃报告
  `Python-2026-09-11-134542.ips` 归属该 offscreen 测试进程，QtWidgets/
  `QApplication.setStyleSheet` 处 SIGSEGV。孤立缩放模块 9 项通过不能关闭缺陷。
  同源码诊断全套 exec 99478 / PID 67357 已结束，1444 项通过（390.908 秒，退出 0），
  开启 PYTHONFAULTHANDLER，日志 `/tmp/icstex-v1-m5-final-cache-suite-r2.log`。
  终态后摘要一致，compileall/diff 通过，未新增崩溃报告；全部测试/原生句柄已关闭。
  首次 SIGSEGV 原因未查明，保留 M6 稳定性缺口，不能用绿重跑冒充修复。
  详见 `docs/v1-m5-agent-export-verification-2026-09-11.md`。M5/完整 V1 未完成。
- 最新 M5 GUI 交付 app SHA-256 为
  `b5bce3681839b945d31aad3852554fff460e0d336a89605ee3f6fc02fd782fcd`；
  app+tests `9deda6dc8270279e5fae9f44e3a5376a6bb8883afcbf0fd53e22f5049c66f7ad`。
  compileall/diff 检查通过；扩展 163 项测试通过（22.113 秒，退出 0，exec 45657
  已结束）。新增红测试复现 PDF 销毁后的两次晚回调，QObject 所有的定时器修复后
  同一测试及 GUI 测试通过；不是 Qt AX 完整修复。实际离屏 r2（exec 29435）与
  Cocoa r1（exec 96488 / PID 58100）均已结束、退出 0，四类项目全部完成实际
  保存/新 FINAL/审阅/取消/交付、逐文件预览字节核对、导出源码和恢复副本重编译。
  一次外部 AX 读取返回，一次超时不计成功；随后核验进程正常结束，前后四份 Python
  崩溃报告清单相同。完整页面版式、IME/AX/Windows/真人和性能验收仍未完成。
  冻结源码完整回归 1421 项通过（718.732 秒，OK / 退出 0）：exec `10341` /
  PID `58091` 已结束、句柄已关闭，nice 10，开始于 `2026-09-11T04:41:19Z`，
  日志 `/tmp/icstex-v1-m5-delivery-gui-suite-r1.log`。终态后两项源码摘要均核对一致，
  compileall/diff 检查再次通过；未在日志发现 Traceback/RuntimeError/失败记录，
  offscreen 插件警告仍保留。原生产品与全套重叠运行，耗时不是性能验收。
  同源码实际 AgentWorkspace 缺口探针也已结束（exec 5817，退出 0）：编译后输入
  变化仍能导出旧 PDF、复制前新出现的目标被覆盖、便携包纳入合成敏感名称、README
  清单不符及混版均复现；退出 0 代表缺陷断言成立，不代表修复。此旧句柄已结束，
  后续 Agent 修复与当前共享 FINAL 回归的状态见最新 Agent 报告。
  详情见 `docs/v1-m5-delivery-gui-verification-2026-09-11.md`。
- 前一 M4 迁移原生补验：当时 app SHA-256 `d4f6e35f`（完整值见下），
  仅调整测试探针和文档，未改 app/tests。Cocoa 产品 r1 的普通多文件、当前 Block、
  已知旧格式均完成实际审阅、默认 No 的独立确认、打开/重开/FINAL；原始字节、
  GBK/CRLF 和独立草稿不变，旧 raw LaTeX 仍不执行。exec `3227` / PID `54017`
  正常结束，退出 0，结果 `/tmp/icstex-v1-migration-native-20260911-r1/result.json`。
  5 次外部 AX 树读取返回，前后 Python 崩溃报告清单相同；IMK mach-port 和字体
  alias 警告保留。专项 21 项通过（10.418 秒，exec 15991，退出 0），默认离屏
  多文件探针 r5 通过（exec 22361，退出 0），三个平台授权拒绝检查通过且未建窗口。
  不等于 native picker、真实 IME、完整 AX/Windows/真人验收，也不补足 M5 新源码
  的完整回归。该原生进程已结束；细节见迁移 GUI 报告的 native follow-up 段。
- 前一 M5 固定交付核心 app SHA-256 为
  `d4f6e35fdbd71f6a1b6eadac7817058e013e50cc47bbd066b2d4e0359524764c`；
  app+tests `89cc72ac67066e7dce6368e948ac1bda5b8b73777b3deb05ca3b0349595f22d3`。
  compileall/diff 检查通过；118 项关联测试通过（22.693 秒，退出 0，exec 28469
  结束）。实际核心产品 r5（exec 62018 结束，退出 0）完成单文件、多文件、Block
  的 FINAL、PDF-only/独立源码和报告、导出源码重编译、检查点恢复及实际 FINAL；
  选定 Block 元数据可重开，原 README/manifest/非 UTF-8 字节和报告摘要核对通过。
  曾发现候选清单漏纳入 README/JSON 的验证缺口，已加强纳入断言后重跑；不存在的
  依赖在最后报告后出现的红测试已修复，写入日志出现也会拒绝。源码/报告独立选择，
  未确认项不算通过；默认只输出 PDF，失败不覆盖已有目录。报告仍明确缺少构建时
  工具二进制版本证据。其后的 GUI/独立 Block 入口验证和当前全套状态见本节开头；
  MCP 便携导出风险尚未关闭，不是 M5 完成。
  详见 `docs/v1-m5-delivery-core-verification-2026-09-11.md`。
- 前一 M4 迁移 GUI/证据复核源码 SHA-256 为
  `d9756e68f9336be479fe4c59ec6955ff0ac0191dad468a42575e6687d34d007f`；
  app+tests 摘要 `67494aa28692d7a3b4473a37b40fcf69a5500ad6ef9a4e344072abe287a3046d`。
  compileall/diff 检查通过，专项 21 项通过（3.931 秒，退出 0），扩展 131 项通过
  （34.606 秒，退出 0）。离屏产品 r4 的普通多文件、当前 Block、已知旧格式三组
  均完成实际菜单/取消/单独打开/重开/正式 PDF 核验，原件字节和独立草稿保留；
  exec 69815/86827/9323 均结束。r1 自动保存夹具隔离问题、r2/r3 图注视口问题
  和诊断属性错误分别留档，断言未弱化，生产自动保存行为未改。
  该冻结源码完整回归 1384 项通过（1208.224 秒，退出 0）：exec `2446` / PID `47068`
  已结束，nice 10，日志 `/tmp/icstex-v1-m4-migration-gui-suite-r1.log`。结束后 app/tests
  摘要核对一致，之后才应用 M5 核心增量；此全套不覆盖后续源码。详细命令和 PDF 哈希见
  `docs/v1-m4-migration-gui-verification-2026-09-11.md`。全程后台，无原生抢焦点操作。
- 前一 M4 迁移核心源码 SHA-256 为
  `363673a32cbfa94e9e4007d82d9fb05d539883df46c8eae101ee8847919f52d2`。
  必需 compileall 与 diff 检查通过；专项 80 项通过（6.073 秒，退出 0），日志
  `/tmp/icstex-v1-m4-migration-core-focused-r2.log`。后台合成普通多文件、当前 Block
  和旧格式三条复制/转换链均实际生成一页 FINAL；选定原件、GBK/CRLF 与独立草稿
  保留，旧格式另留所有原始文件，实际模型加载和 PDF 文字检查通过。旧 LaTeX 片段
  保留原文但仍 trusted=false，不因此进入编译输出；不是旧文档排版一致性验收。
  旧原地 MigrationRunner 已拒绝写入；未知/冲突/缺图/取消/源变化不发布副本。
  完整离屏回归 1371 项通过（1368.580 秒，退出 0）：exec `98240` / PID `42233`
  已结束，日志 `/tmp/icstex-v1-m4-migration-core-suite-r1.log`；启动为 nice 10。
  冻结 app+tests 摘要 `a32315d6dee15f9d0288fd99daacd8c9d9154b12ce529e583f08f24347956430`。
  结束后 app/tests 摘要复核一致。缩放阶段活采样仍处于 QApplication.setStyleSheet，
  不据此宣布性能通过或确定迁移补丁导致慢速。后续 GUI/证据复核增量已开始验证，
  不沿用本次核心源码全套作为新 GUI 验收；后续原生补验另见本节开头。
  详细边界见 `docs/v1-m4-migration-core-verification-2026-09-11.md`。
- 前一 M4 中断写入恢复/临时 AX 保护源码 SHA-256 为
  `bb899c986d4d5adb7fc30c3f618ad948319d7d94567c1c5317b42e57b059b75f`。
  必需 compileall 与 diff 检查通过；最终专项 54 项通过（9.501 秒，退出 0）。
  实际 offscreen r2 与 Cocoa r2 均退出 0：真实写入进程中断后，before/after 两种
  副本分别打开、重开与显式 FINAL，原件/日志和独立草稿保留。Cocoa r2 的 5 次外部
  AX 树读取返回，PID 32853 正常结束，复查未见新 Python 崩溃报告。原生 r1 的
  SIGBUS 留档；保护只在 macOS 26 arm64 / Qt 6.11.1 / cocoa 暂停 selected-children
  枚举，不视为完整 AX 或此前其他 Qt 崩溃修复。
  最终完整回归 1358 项通过（1176.674 秒，退出 0）；exec `36846` / PID `33491`
  已结束，日志 `/tmp/icstex-v1-m4-journal-guard-suite-r1.log`，不得重启已完成运行。
  冻结 app+tests 摘要 `bc83709bd8828fb6dbe4021206bf0a8179ebdbf5af86c56b70ee424e961664d0`
  已在结束后复核一致。全套仍有大量 offscreen 插件提示，耗时不是性能验收通过。
  启动时 load averages 9.55/10.91/10.16，系统 memory free 31%；时间不能单独归因于补丁。
  原生截图 PDF 窄视口只显示部分恢复文本；完整文字由实际 PDF 文档提取校验。
  报告：`docs/v1-m4-write-recovery-verification-2026-09-11.md`。迁移、M5、完整 M6 未完成。
- 同一冻结源码上，M3 Cocoa 引用 r3、素材 r3、来源修复 r2 均退出 0，分别验证
  实际检查/定位/草稿或冲突保全、显式 FINAL 的渲染与文字内容；源码修复另验证
  全部关联表格一次 Undo、保存加载一致及原始 CSV 保留。探针补上等待可见 PDF、
  窄 Block 切到 PDF 页和工作区结束态后截屏；引用早期空白截图、来源修复 r1
  超时退出 1 不作为可见产物验收。来源修复仍有 IMK mach-port 警告；素材的一次
  AX 读取失败，随后进程已正常结束，不能计为 AX 通过。后查没有新的 Python `.ips`。
  详细命令、PDF 摘要和限制见 `docs/v1-m3-native-followup-verification-2026-09-11.md`。
  这些原生探针与全套运行重叠，不作为性能对照。用户随后要求不占用屏幕并曾暂停
  原生验证；现已明确恢复前台授权，新增迁移验证另见本节开头。
- 前一 M4 恢复草稿继续编辑源码 SHA-256 为
  `305fb3dbb5f6f8accfb3ebda55eab249c185b90f0c1787a7a38d79eb3728efbc`。
  必需 compileall 通过；最终专项 13 项通过（7.848 秒，退出 0），集成专项
  92 项通过（10.108 秒，退出 0）。最终完整回归 1338 项通过（1220.539 秒），
  退出 0；exec `70159` / PID `25486` 已结束，结束后摘要未变。日志
  `/tmp/icstex-v1-m4-recovered-drafts-suite-r1.log` 未见测试失败或 Python 异常。
  全套在 UI 缩放阶段较前轮明显变慢，1 秒活采样处于 QApplication 样式表计算；
  未隔离补丁因果或内存泄漏，仍须 M6 性能/生命周期对照，不等同性能验收。
  实际 offscreen 普通/Block r3 已验证审阅确认/取消、载入草稿、Undo/Redo、首次
  显式 Save、关闭重开与独立 FINAL；原项目与独立草稿文件字节不变。恢复审阅、
  Block 待应用输入及重开 PDF 视图截图已检查，PDF 提取包含恢复文本；普通页截图
  仅显示局部，不将它当作完整文字目视验收。早期主题 schema 误拒绝有效覆盖字典
  已修复；产品 r1/r2 因紧凑 PDF 页切换/滚动观察失败，只修正探针，不宣称渲染修复。
  原生 picker/IME/AX/Windows/真人、中断写入与迁移仍未验收；报告见
  `docs/v1-m4-recovered-drafts-verification-2026-09-11.md`。
- 前一 M4 项目检查点 GUI 源码 SHA-256 为
  `11b95515d2cb3984d152de46a2791a3c58ddfd8069e82d4b6e5b90a23464c46d`。
  必需 compileall 通过；最终专项 38 项通过（1.192 秒），完整回归 1325 项通过
  （373.316 秒），退出 0；exec `81933` / PID `21124` 已结束，结束后摘要未变。
  日志 `/tmp/icstex-v1-m4-checkpoint-gui-suite-r2.log` 未见测试失败或 Python 异常。
  实际 offscreen 普通/Block GUI 检查点、确认/取消、审阅恢复及显式重开/FINAL 通过；
  5/8 个文件原始字节含 GBK/CRLF 一致，1/2 份真实 GUI 草稿独立保留。最终 r5
  创建审阅及两份一页 FINAL 截图已检查。原生 picker、IME/AX/Windows/真人和
  草稿恢复继续编辑仍未验收，不将此切片视为完整 M4。早期全套 r1 因最后取消
  竞态修复主动停止（退出 143），不作为最终证据。详细失败记录与边界见 GUI 报告。
- 前一 M4 文本历史保护源码 SHA-256 为
  `b2a8297c88089ac76925a8d55378b50d299694180bb7aa93641a263260392802`。
  必需 compileall 通过；历史专项 33 项通过（1.101 秒），完整回归
  1312 项通过（371.893 秒），退出 0；exec `74919` / PID `15672` 已结束，结束后
  摘要未变。日志 `/tmp/icstex-v1-m4-history-suite-r2.log` 未见测试失败或 Python 异常。
  合成 offscreen r8 验证真实确认/取消、篡改拒绝、键盘 Undo/Redo、单独显式保存、
  重开和可见一页 FINAL；截图与 PDF 文本已核对，不替代原生/Windows 验收。
  前一源码 1311 项通过后增加已知链接打开前拒绝测试，因此采用本次最终全套。
  暂存新文件后差异检查仅提示 `source_status.py` 和 `test_gui_material_usage.py`
  的末尾空行；保留已测试字节。提交范围常见凭据模式扫描无命中，不代表全面安全审计。
  详见 `docs/v1-m4-history-safety-verification-2026-09-11.md`。
- 前一 M4 检查点核心源码 SHA-256 为
  `71ff39885c237665a25cf801947aa20dc58194b489c8ab7283a5a67e7d4ea933`。
  compileall 和 25 项专项通过（0.139 秒，退出 0），实际合成目录检查点/恢复/草稿
  比对、Block 重开及普通/Block FINAL 通过；未操作真实学生数据。
  完整回归 1289 项通过（366.453 秒，退出 0）；exec `1766` / PID `10802` 已结束，
  摘要复核未变。日志 `/tmp/icstex-v1-m4-checkpoint-suite-r2.log` 未见测试失败或
  Python 异常；offscreen/字体警告不作为原生验收。
  旧 r1 为最终暂存目录说明文字修正主动停止，退出 143，不计最终验收。
  `docs/v1-m4-checkpoint-core-verification-2026-09-11.md` 记录源码、故障复现和范围。
- 前一来源修复源码 SHA-256 为
  `aebdfa7b7c9183a6485d1e7934e7c0bbe9452369879dd6e47386adc9dd2fb4cd`。
  compileall/差异检查通过；最终专项 120 项通过（3.018 秒），完整回归 1264 项通过
  （361.082 秒），退出码 0。exec `53595` / PID `7114` 已结束，结束后摘要未变；
  日志 `/tmp/icstex-v1-m3-source-repair-suite-r3.log` 未见失败或 Python 异常。
  真实合成来源流程验证两张关联表、摘要匹配基线、键盘映射、最终取消零应用、
  外部来源变化拒绝、全部表/来源一次 Undo、恢复未应用草稿、保存重开及显式 FINAL。
  一页 PDF 包含 A=12/B=21 与 A=11/B=21，来源原始字节不变。截图发现并修复映射
  行高/宽度问题；取消压力复现并修复旧解析尚未结束时重试启动多个读取线程。
  旧全套 r1 已结束；r2 因源码变化主动停止，退出 143，不计通过。最终证据见
  `docs/v1-m3-source-repair-verification-2026-09-11.md`。原生/大表预览/跨平台与 M4–M6
  尚未完成，本轮不提交、不打包、不替换安装版或发布。
- 前一合并候选/导入修复源码 SHA-256 为
  `39f26a52093da449f06ddf32bf5610808b1e126616298c6a96b3abdb042c6cee`。
  compileall/差异检查通过，合并/导入/模型/渲染/Block GUI/来源/视觉专项 113 项通过
  （4.720 秒），退出码 0。真实合成对话框保留同一行其他值、False、空白和原输入，
  取消不应用；显式 FINAL 的 1 页 PDF 中两张表的表头与全部数据行已核对。
  前一源码全套 1242 项通过（363.395 秒）；随后补齐预览 tableId 和中文取消按钮。
  最终源码全套 1242 项通过（360.894 秒），退出码 0；exec `96245` / PID `1534`
  已结束，源码摘要复核未变。日志 `/tmp/icstex-v1-m3-merge-import-suite-r2.log`
  未见测试失败或 Python 异常；不据此替代原生/IME/AX/Windows/真人验收。
- 前一素材检查源码 SHA-256 为
  `cc506a5a59b3f4e187937ed4283650b53f6b7de817c7f249f7896b3f7e5fa61e`。
  compileall/差异检查通过，素材/引用/依赖/提交检查及内存索引集成 109 项通过
  （9.786 秒），退出码 0。真实合成图片检查、缺失/变化/候选区分、子文件定位、
  草稿覆盖和取消零写入通过；独立显式 FINAL 的 1 页 PDF 已渲染核对。
  首次全套 1223 项有 1 个旧磁盘缓存断言失败；补强内存复用测试后另复现并修正
  暖扫描诊断计数。最终全套 1223 项通过（364.943 秒），退出码 0；exec `96648` /
  PID `96374` 已结束，源码摘要复核未变。日志
  `/tmp/icstex-v1-m3-material-suite-r2.log` 未见测试失败或 Python 异常。产品 r4 包含晚到 watcher
  事件造成的显式重试；五档缩放的按钮可滚动访问，但高缩放文字仍需滚动。
  原生、任意窄屏、IME/AX/Windows/真人与 M6 性能验收未完成。
- 前一引用检查源码 SHA-256 为
  `a12ade12f6d5573f99a03e83f8ef9e3b784538b5c0cfc4cbe520ba0ad9a84baf`。
  compileall 通过，引用 core/GUI/依赖/快捷库专项 36 项通过（1.434 秒）；与原有
  编辑器/提交检查集成 80 项通过（9.495 秒），均退出码 0。合成窗口检查/定位/取消
  不改源码字节、不授权编译；独立显式 BibTeX FINAL 生成 1 页 PDF，四个条目及
  nocite/crossref/字符串拼接输出已核对。五档缩放与受最小尺寸限制的窗口中，按钮
  通过滚动可达；不等于原生/任意窄屏验收。完整 verbose 回归 1200 项通过
  （559.206 秒），退出码 0；exec `33298` / PID `88960` 已结束，结束后摘要未变。
  日志 `/tmp/icstex-v1-m3-citation-suite-r1.log` 未见测试失败或 Python 异常。
  缩放阶段的样本仍在 QApplication stylesheet，进程占用约 2.0 GiB；不据此判定
  新增回归或应用泄漏，M6 性能/原生生命周期验证仍待完成。
- 前一来源检查源码 SHA-256 为
  `6c87ebcf98f88c87f1ae43a89ee79f34310ea69ee45fb4bcee3508fc4765e020`。
  compileall/差异检查通过，来源 core/GUI/Block 集成/编辑器目标专项 82 项通过
  （2.311 秒），退出码 0；完整 verbose 回归 1168 项通过（477.939 秒），退出码 0，
  exec `70944` 已结束，结束后摘要未变；日志 `/tmp/icstex-v1-m3-source-suite-r1.log`。
  未出现 traceback、RuntimeError、RuntimeWarning 或 fatal Python failure。合成四来源项目实际检查、
  关联表格定位、磁盘/模型零修改与重开保留通过，离屏渲染已检查，不替代原生验收。
- 前一公式专项源码 SHA-256 为
  `0c430570de459bea98fd81452a122e3af3a09a24f7f3365c68c0ac0794014ea5`。
  compileall/差异检查通过，公式 core/tree/widget/dialog/Block-target 专项 138 项
  通过（3.669 秒）。完整回归 1140 项通过（563.678 秒），退出码 0，结束后摘要未变；
  日志 `/tmp/icstex-v1-m2-formula-fidelity-suite-r1.log` 未见 Python 异常或失败。
  原生工具报告 Mac 已锁定；需要手动解锁后完成新源码原生验收。
  同源码 offscreen 公式草稿实际生成 FINAL，pdfLaTeX 成功，源码字节未变；PDF
  提取及渲染检查可见 `x + a + b + z`。这不替代原生剪贴板/IME 验收。
- 必需 compileall 与 `git diff --check` 通过；图片导入/二次编辑器/Block/提交检查/UI
  focused suite 182 项通过（15.752 秒）。上一同步检查点的图片源码 SHA-256 为
  `5acfce28d24ebcb2fe9b87ba56cfc9bb9f47d68e7e26d8b452db3affe599cce5`。
  用户授权同步前的完整 verbose offscreen 回归 1134 项通过（872.176 秒），退出码 0；
  日志 `/tmp/icstex-v1-source-sync-20260911-tests-r1.log`。结束后源码摘要未变；
  未出现 Traceback、RuntimeError、RuntimeWarning 或 fatal Python error。
  前一二次编辑器源码完整 1122 项通过（996.164 秒），日志
  `/tmp/icstex-v1-m2-editor-targets-suite-r2.log`。完整测试不替代图片原生或平台验收。
  全套 stylesheet/夹具生命周期耗时问题仍未关闭。
- Cocoa 原生普通源码与 Block 均实际生成、显示 1 页 FINAL PDF；输入、产物、日志
  与当前身份匹配。Block 恰好一次完成通知；PREVIEW 不替换 FINAL，后台 Block 不
  覆盖源码 PDF。元数据变化及手改生成子文件会废弃/拒绝旧证据。
- M1 实际 FINAL 原生源码身份与两模式五档缩放证据见
  `docs/v1-m1-final-evidence-2026-09-10.md`。后续 M2 配置原生验证使用的 app Python
  路径/内容 SHA-256 为 `cc34365cc2dc294c1888bd06321be785a423eadb70c4d6b9821edfc2a5778da4`。
  键盘取消零写入、保存与实际文件事件、目标失败、禁用和外部冲突均通过；原始源码
  字节、已有 FINAL PDF/build id、光标与滚动不变。配置对话框五档缩放与冲突截图
  已查看，报告见 `docs/v1-m2-profile-verification-2026-09-10.md`。
- 前轮完整测试未出现 traceback、RuntimeError 或 RuntimeWarning；不据此替代原生压力验收。
  M2 后续创建/工作区原生源码身份为
  `9d713aa8350aa690ff9b6e516b35cdc78c179f8c7cff83a916fae0a5590a5be9`。
  实际中文项目向导、首次 FINAL、检查、字节一致 PDF 导出及第二窗口重开通过；
  创建/打开不编译，源码字节不变。两模式工作区和向导五档缩放已捕获检查；干净
  Block 关闭恢复普通源码控件与 FINAL。报告见
  `docs/v1-m2-workspace-verification-2026-09-10.md`。
- 先前 Block 保存/关闭切片的 app Python 路径/内容 SHA-256 为
  `4c0b3b607adaec9aea9340c6f8bb25206e10cc99cb9cfd490532bd3864cbcd0d`。
  真实 Cocoa Cancel/Save/Discard、保存后重开、外部冲突拒绝关窗、停止/关闭区分及
  晚回调零写入通过。实际 FINAL 显示 1 页，提取文字包含保存草稿；小样本请求约
  2.450 ms 返回，期间有 97 次 GUI heartbeat，不代表所有项目性能。普通源码 PDF、
  光标与滚动保留。相同源码复跑创建/FINAL/检查/导出/重开也通过。证据见
  `docs/v1-m2-block-close-verification-2026-09-10.md`。
- 前轮布局/键盘专项及同源码关闭、创建/导出复跑的 app Python 路径/内容 SHA-256
  为 `ea723c4ae672e8504fa3213efbc83b228ca22e04ce9e2c0032d377b81e9adcea`。
  90/100/110/125/150% 与 1080×720、1440×900 通过按钮完整滚动可达检查，控件身份
  和模型/文件不变；局部文字 Undo/Redo、键盘应用一次全局命令及实际 FINAL 通过。
  编辑/PDF 切换保留文档和缩放；Source PDF、光标、非零滚动与源码字节保留。
  保存/关闭/重开/外部冲突及中文创建→FINAL→检查→PDF 导出→重开也通过。
  详见 `docs/v1-m2-block-layout-verification-2026-09-10.md`。三个原生日志保留字体别名
  警告，创建流程仍有 table-bounds 警告；无 Python 异常，未发现新增 Python 崩溃报告。
  完整套件比上一轮耗时更长，采样见 Qt 样式表处理，仍需 M6 对照复核。
- 前轮属性草稿及同源码布局/关闭复跑的 app Python 路径/内容 SHA-256 为
  `e675b187e1b02c5b69afd8730d9c53b073e56f7d38fb72eae79859145e43970d`。
  三组 Cocoa 原生运行均退出 0：跨 Block/布局草稿、刷新/计时零写入、只读检查拒绝
  保存态、确认后批量一次 Undo、Save/Cancel/Discard、重开、外部冲突和实际 FINAL
  通过。实际一页 PDF 包含应用后的合成草稿；Source 的 FINAL、光标、非零滚动与
  原始字节保留。最终 150% 草稿、实际 PDF、保存确认及冲突截图已查看；详见
  `docs/v1-m2-property-draft-verification-2026-09-11.md`。字体别名/table-bounds 警告
  仍保留，未发现新 Python 崩溃报告。本轮全套较慢，活采样再次处于 Qt 样式表，
  约 2.1 GB footprint；机器同时有较多 swap 使用，不能仅凭耗时归因于本轮改动。
- 前一二次编辑器源码 SHA-256 为
  `caac75122b49f7a0e283cf1a8203a1beaa62d5d458b9c67ad21eb24abc1b1625`。
  多表格/公式 r5、属性草稿 r6、布局 r8、关闭 r7 四组 Cocoa 原生均退出 0；分别编辑
  两张表、局部/全局 Undo、保存重开、公式真实取消/应用/模拟并发冲突、外部磁盘
  胜出版本保护和实际 FINAL 通过。PDF 可见两张表目标文字及 `x+4`；Source PDF、
  光标、非零滚动和原字节保留。新 delegate 警告已消失，字体别名/table-bounds/
  输入服务警告仍保留；该轮检查未发现新 Python 崩溃报告。该源码全套已通过，详见
  `docs/v1-m2-editor-target-verification-2026-09-11.md`。
  编译前后抽样不是冻结构建；pending 写入证据没有自动恢复流程。
- 后续图片专项通过；早期真实 macOS picker 仅取消后零修改已走通，收到源码同步请求
  后停止该探针。恢复前台授权后 r3 完成真实取消、PNG 导入、链接目录拒绝、Undo/Redo、
  保存与新 GUI 会话重开/两次 FINAL，截图均显示所选绿色合成图片；exec 79095 退出 0，
  窗口已销毁，无新 Python 崩溃报告。键盘重选使 Open 启用，不据此断言原选择问题根因。
  新增拖入测试曾因测试夹具
  提前释放 Qt 借用的 QMimeData 而退出 139；保留该对象后原应用达到预期失败断言，
  修复应用后专项通过。这不解决此前 timer-dispatch 崩溃因果。详见
  `docs/v1-m2-image-import-verification-2026-09-11.md`。
  完整 M2–M6、IME/AX/Windows/真人验收仍未完成，不打包或发布。

## Release Matrix

| 对象 | 状态 | 说明 |
| --- | --- | --- |
| 当前源码 | Beta 3 app/test source matches published tag | 2.1.0-beta.3；app/test摘要与最终验收快照一致，发布源码标签为81b1672；原开发分支HEAD仍为3bde2b5、索引和无关工作树改动保留，不称整个开发分支已推送 |
| Beta 2 macOS arm64 候选 | Historical, local-only | 旧r2候选保留为历史证据；当前线上更新由Beta3替代，不重新激活或覆盖它 |
| 本机 macOS 应用 | Beta 3 updater bootstrap installed | `/Applications/ICSTeX.app`来自匿名下载的公开ZIP，源码/签名一致，旧Beta2已完整备份；最终安装路径的窗口因再次锁屏尚未打开 |
| macOS arm64 DMG/ZIP | Verified, rebuilt | hardened source；ad-hoc signed、未 notarize |
| clean source ZIP | Verified, rebuilt | hardened source；publication hygiene scan passed |
| Windows ARM64 ZIP | Verified beta artifact, rebuilt | Windows-local `C:\w3`；无系统 Python 启动通过 |
| Windows x64 ZIP | Pending | 当前构建机和 Python 均为 ARM64 |
| Windows x64 Setup EXE | Blocked by tools | 需要 x64 构建环境和 Inno Setup |
| Windows TeX acceptance | Blocked by tool | 构建机尚未安装 MiKTeX/TeX Live |
| Static release website | Beta 3 production READY | `ics-tex.vercel.app`及固定签名appcast；下载链接/版本/SHA已实查，保留既有版式，更新联网说明 |
| GitHub repository / Release | Beta 3 published prerelease | `v2.1.0-beta.3`；8个资产；DMG/ZIP匿名下载HTTP 200且摘要一致，旧版本保持不变 |

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

当前范围仍是本地源码实现与验收，不是发布候选推荐。完整要求/证据对应关系见
[V1 验收矩阵](V1_ACCEPTANCE_MATRIX.md)，分层发布状态见
[发布准备清单](V1_RELEASE_READINESS.md)。以下列当前缺口与限制，不重复旧阶段待办。

- 用户于 2026-09-12 再次明确允许接管键盘；其后原生导航、控制台和 PDF 复验已有
  成功控制记录，不再把早先锁定回执当作当前阻塞。本轮收尾审计只在后台读取证据，
  未打开测试窗口。后续原生 QA 仍仅用隔离合成项目，逐轮告知并关闭窗口，
  不触及学生文档/安装版，也不反复尝试解锁。
- M2 图片真实 picker 的取消、导入、错误拒绝、Undo/Save、GUI 会话重开和
  第二次 FINAL 已有源码身份明确的原生证据；不再列为“从未验收”。当前公式坐标、
  目标关闭/重载保护及宏包/正文一次 Undo 也有本地证据。剩余原生输入/导航见 R1/R2，
  真实 Finder 拖拽和真人可用性不由上述结果代替。见
  `v1-m2-image-import-verification-2026-09-11.md` 与
  `v1-m6-formula-coordinates-verification-2026-09-11.md`。
- M3 引用健康、素材使用及来源修复已分别有 Cocoa 合成流程，不再称为“原生未验收”。
  这些是各自旧源码身份下的 Qt 驱动窗口结果，不是当前全部物理键盘/AX 通过。
  后续高缩放引用与工具导航已有有界原生证据，不重列为未执行。
  来源三方修复仍需用户选取摘要匹配的原始版本；
  SourceRecord 没有持久表格基线，不能把推进摘要当作恢复基线或学术真实性证明。
  见 `v1-m3-native-followup-verification-2026-09-11.md`。
- M4 选定字节检查点、独立草稿恢复/继续编辑、中断 Block 写入恢复和已知格式迁移
  均已实现并有各自产品证据；M5 流程还完成交付后新目录恢复/再次编译。不再把整个
  检查点或端到端恢复列为未实现。原生目录 picker、Windows 重解析/锁、真实云占位、
  断电/卷丢失及任意外部写者的 OS 原子性仍未验收。未知格式应拒绝破坏性写入，
  不是要求实现未知格式转换；恢复只到新目录。证据入口见验收矩阵 M4。
- M5 主/独立 GUI 与 Agent 的固定交付链已实现；实际 PDF/选定源码/报告审阅、独立
  外部 TeX 编译、检查点恢复和输出字节核对已有证据，不再列为“完整冻结导出未实现”。
  当前输入/产物绑定仍依赖 FINAL、内容复核与显式未知项，非任意外部写者的 OS 原子
  快照。构建版本为驱动/引擎自报标签；辅助工具、字体及二进制认证保持未知。
  MCP 包接口不等于 GUI 逐文件审阅，名称/内容过滤不证明所有内容无隐私。见
  `v1-m5-delivery-gui-verification-2026-09-11.md`、
  `v1-m5-agent-export-verification-2026-09-11.md` 和
  `v1-m5-tool-versions-verification-2026-09-11.md`。
- R1 本机 Pinyin 的有限场景已完成：默认自动保存/候选保护之外，后续真实外部冲突、
  取消、中文提交、Save 默认拒绝覆盖和原生另存双版本均通过；当前源码公式可视/源码
  模式分段候选、取消、提交、一次撤销/重做及键盘确认也通过。见
  `v1-m6-native-conflict-formula-verification-2026-09-12.md`。未观察到同事件提交/预编辑，
  不冒充所有输入法验收；公式结果为已确认编辑计划，不是新一轮 MainWindow FINAL。
  R2 Inspector 100%/150% 焦点已有其源码身份下的原生证据；解锁后的引用键盘定位、
  焦点滚动及工具导航/缩放也已取得有界原生证据，最终装配增量另验双向顺序和
  100%/150%。四类只读定位表 Return/Enter 已过离屏实际控制器回归，大纲/搜索
  又有实际原生定位记录；恢复控制后的诊断/错误两路已完成 Return 定位，原生
  200% 合成 PDF 样本清晰可读。控制台诊断裁切已由五档专项、扩展/全套及原生
  100%/150% 复验关闭；字数/提交检查的长文本首尾、刷新/结果/详情焦点也已通过
  五档及原生 100%/150% 复验，见 `v1-m6-reading-console-verification-2026-09-12.md`。
  PDF 面板重叠、实际缩放/页码漂移及整页底部裁切已修复，菜单选择和最终源码
  100%/150% 整页可见有原生证据。见 `v1-m6-pdf-geometry-verification-2026-09-12.md`。
  原始要求收尾审计与模态键盘专项已推进：四类焦点/Return 缺陷已修复，创建/profile
  100%/150%、普通交付、检查点与独立草稿恢复已有原生证据。用户已确认解锁，
  本轮原生 r5 复现独立 Block 分页焦点缺陷；一行修复及五档红绿后 r6 通过实际
  100%/150% 交付入口、150% FINAL/审阅/取消、迁移发布和检查点/恢复操作。
  RecoveryDraftDialog 与迁移后 source/open 控件五档遍历通过。随后真实打开 helper
  和离屏 No→Yes 确认/销毁回归证明新窗口仍可见并存活，隐藏窗口对照准确失败；
  原生 r2 随后复现确认后新窗口仍在旧窗口后方，非窗口丢失或销毁。生产模态
  wrapper 在退出后仅对已确认打开的新窗口 raise/activate；取消不切换。
  专项红绿及原生 r3 证明新窗口可见且活动，焦点位于其 Block 搜索框，源/副本
  字节不变、无编译，两个窗口最终销毁。早先锁屏 r1 保留为中断，不计通过。详见
  `v1-m6-migration-window-verification-2026-09-12.md`。NSMenu 按键被 CUA 路由到下层
  Qt 窗口，不据此推断真人菜单失效，也不计纯键盘通过。详见
  `v1-m6-recovery-migration-keyboard-verification-2026-09-12.md`。
  不重建已核验的普通交付/恢复结果；复用保留的合成项目。详见
  `v1-m6-modal-keyboard-verification-2026-09-12.md` 与原始
  `v1-local-closeout-audit-2026-09-12.md`。另见 `v1-m6-console-layout-verification-2026-09-12.md`、
  `v1-m6-citation-keyboard-verification-2026-09-12.md` 及
  `v1-m6-readonly-table-focus-verification-2026-09-12.md`，后续见
  `v1-m6-native-navigation-verification-2026-09-12.md` 及
  `v1-m6-four-route-navigation-verification-2026-09-12.md`。
- R3 已有窗口、样式遍历、行号引用环、关闭标签、表格对话框及延迟回调的有界修复
  与回归。旧 timer-dispatch 接收者和历史样式崩溃具体对象仍未证明；不把不同复现
  强行归为同因，也不通过反复无差别全套测试宣称因果已解决。版本限定的 Cocoa AX
  selected-children 保护仍牺牲该属性枚举，不能算完整 VoiceOver/辅助功能验收。
  原生 IMK/font 警告与旧崩溃报告保留。R4 进程树夹具就绪和反例检测已本地解决。
- R5 已完成获批的本机受限 LuaLaTeX/BibTeX 源码链：共享编译器接入 Mac OS 沙箱，
  原型后的真实驱动/辅助程序/引擎及 stdio 导出有分阶段证据；只有核验通过的隔离
  子进程使用 `openin_any=a`，输出策略 p 与 no-shell-escape 保留。当前源码通过
  字体读取、中文/公式/参考文献 PDF、边界拒绝及驱动/引擎进程组停止；见
  `v1-m6-macos-sandbox-integration-2026-09-12.md` 和 D021。
  后续 Biber 专项已复现当前隔离中的启动失败：已安装 Biber 2.20 的版本命令在
  隔离外成功；隔离内 xcode-select/lipo 执行被拒绝，并需解包后的本机代码。不是
  要求安装 Command Line Tools 的证据；不放开可写临时目录或回退无隔离处理。
  用户已明确延期这项 Agent/MCP Biber 支持；受限准备阶段/只读运行时方案不进入
  当前写作界面交付，也未获实施授权。原诊断见 `v1-m6-macos-biber-boundary-2026-09-12.md`。
  其他安装布局/字体集合、TeX Live 2026、其他 macOS 与发布支持仍未验；
  弃用命令/私有规则不能成为不加限制的发布承诺，失败必须继续拒绝。
  原始 paranoid/safer 失败、上游 2026 输入策略变化、缓存目录并非只读白名单及
  临时原型证据保留在各自收据，不改标为本次源码。未更换依赖或修改系统 TeX。
- R6 已完成原始要求收尾审计及有限缺口交接，不是本地验收通过。当前 app/app+tests
  摘要与最近完整回归一致；重读保留日志和产品报告，并复核三类核心交付/重编译/
  恢复产物、四类 GUI 交付 PDF 及七份报告中的全部输出长度/摘要，均匹配。
  这是历史产物和当前源码身份复核，不是重新运行全套或把旧原生结果改标为新源码。
  R2 菜单证据与 R3 风险仍未关闭；R5 未验范围保留，其中 Biber 已按用户选择延期，
  不阻塞普通写作界面的源码体验交接。外部缺口不能替代仍适用的本机验收。
  D010/D013 保持 Proposed，既有局部实现不自动提升架构决策。
- 性能结论限于记录的合成规模和测量条件。依赖扫描最多 2,000 个输入、单源码
  4 MiB；同步 GUI 扫描与后台统计仍有成本，不承诺任意项目实时响应。大图暖缓存
  继续内容摘要核验；双向 SyncTeX 仅针对当前显示且仍有效的 PREVIEW/FINAL 构建，
  无映射不能保证定位。正向 PREVIEW 是 2026-09-19 源码增量，不自动代表安装版能力。
- MCP 仍绑定单项目，默认只读；同项目可写 GUI/MCP 或多个可写 server 并发不是
  支持拓扑。路径、CAS、项目锁、严格解码与受控文件变更边界不变；不自动重写
  LaTeX 引用、删除或跨项目移动。
- E1 Windows 匹配环境、E2 真实云/存储故障、E3 VoiceOver/学生可用性和 E4 独立
  发布门槛全部保留。现有 Windows 11 虚拟机经只读 CLI 确认正在运行，但 guest
  命令执行被 Parallels 当前版本拒绝（要求 Pro/Business）。CUA 能读取客体画面，
  激活后坐标操作仍报 `noWindowsAvailable`，一次 Ctrl+Escape 后未观察到开始菜单；
  未打开终端，Python/Qt/TeX 当前可用性仍未核验。这不是 Windows 产品测试失败，
  不升级许可或更改 VM 设置来绕过。用户随后明确要求先完成 Mac，虚拟机工作已停止，
  E1 延后至用户重新要求；不视为取消 Windows 支持。历史 ARM64 安装制品不覆盖本轮源码或 x64。
  macOS arm64 Beta 3 的安装互斥、晚启动、中断恢复和公开 HTTPS 升级已独立验收并发布；
  进程扫描仍不是安装锁，人工恢复仍不是自动回滚。其他平台、全部权限布局、Developer ID
  和公证继续作为独立事项。当前制品见 BETA3_DELIVERY 和本节首项，不从旧源码测试推导。
- 当前仍是 Beta 工作源码；OCR 候选需人工核对，重要项目应有外部版本备份。
  Word Count 是可审计的源码级统计，不保证符合任意学校/课程的最终纳入口径。

## Maintenance Rule

只有验证后的事实才写入本文件。命令、哈希和任务过程追加到 `PROJECT_LOG.md`；
尚未接受的设计保留在 roadmap/decision log，不写成当前能力。
