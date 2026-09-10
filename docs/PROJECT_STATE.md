# ICSTeX Project State

更新时间：2026-09-09（Asia/Taipei）

本文件是当前已验证状态的权威来源；历史证据写入 `PROJECT_LOG.md`，未来计划写入
`docs/ROADMAP.md`，长期约束写入 `docs/DECISION_LOG.md`。

## Product and Source State

- 权威工作区：本仓库根目录；此前产品源码已同步至 GitHub 的 `release/2.1`。
  当前本地正在准备 Beta 2 macOS arm64 更新通道，新增变更尚未提交或推送。
  响应/预览优化、公式/表格交互和默认离线更新入口已生成并安装本机 macOS 开发
  构建；公开安装制品尚未包含这些后续更新。
- 当前源码版本：`2.1.0-beta.2`；版本来源为 `app/__init__.py`。
  已安装应用与公开下载仍为 Beta 1；Beta 2 r2 已签名并完成隔离双版本替换，
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
- 当前快速预览可双击 PDF 正文，通过 SyncTeX 定位原始 root/child 源码。查询前后
  校验实际显示的 purpose、root、revision、build id 和路径；过期、同 purpose 重建、
  越界/符号链接/生成文件均拒绝导航。源码到 PDF 的工具栏入口仍要求当前正式 PDF。
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
- 当前工作源码提供“软件更新…”入口、默认关闭的每日检查、应用级单例及全部窗口
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
  `docs/BETA_ACTIVATION_HANDOFF.md`。当前变更未提交/推送，不触发 GitHub Actions。

## Release Matrix

| 对象 | 状态 | 说明 |
| --- | --- | --- |
| 当前源码 | Beta 2 signed local candidate | 2.1.0-beta.2；新增变更未提交/推送；此前产品源码 `39e315e` 已同步，公开激活仍受验收门槛限制 |
| Beta 2 macOS arm64 候选 | Signed and replaced in QA; activation held | `dist/ICSTeX-2.1.0-beta.2-macos-arm64-candidate-r2/`；序号 210002；签名、真实替换和冷启动通过，原生安装互斥门槛未建立 |
| 本机 macOS 应用 | Latest local development build installed | `/Applications/ICSTeX.app`；20260908-204029-b002533f；包含响应/预览优化、公式/表格更新及默认离线更新入口；旧应用已保留 |
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

- macOS arm64 Beta 的签名与隔离双版本替换已验证，发布暂缓于晚启动实例/安装全生命周期
  互斥门槛；需要先决定其有界实现路径，再完成原生竞态/中断和公开 HTTPS 分发验证。
  首个带更新器版本仍须人工引导安装；不把 GUI 占用扫描当作安装锁。普通网站 JSON
  不是更新 feed，现有 Windows ZIP 不直接进行原地更新。
- Windows ARM64 ZIP 已在 Windows-local `C:\w3` 从 hardened source ZIP 重建；
  Python 3.12.10 ARM64，移除系统 Python PATH 后的打包应用启动验收通过。
- Windows x64 ZIP/Setup 仍未生成；不能把 ARM64 包改名或宣称为通用 Windows 包。
- 构建机缺少 Inno Setup，因此 x64 Setup EXE 不能在未补齐构建环境时生成。
- Windows 构建机缺少 MiKTeX/TeX Live，因此不能把 source-to-PDF 记为已验证。
- 本轮源码同步保留既有提交历史，不使用强制推送。增量对象检查未发现私钥、常见
  访问令牌或实际维护者目录路径；不据此宣称全历史或全面安全审计通过。
- 原始 PDF 性能截图含本机临时路径和编译日志，仅留本地；公开 JSON 测量数据与
  复现脚本保留。此次提交采用 `[skip ci]`，未改变工作流或仓库设置；GitHub 未生成
  产品源码提交对应的 Actions run。
- macOS 仅验证 Apple Silicon，且未 Developer ID 签名或 notarize。
- 2.1 是 Beta；公式 OCR 结果必须人工检查，重要项目仍需外部版本备份。
- 字数统计是可审计的源码级统计，不等同所有课程的提交口径；标题、说明/脚注、公式
  和数字已分层显示，最终纳入范围仍须按对应课程要求判断。
- 多项目并发使用不同名称、不同根目录的 stdio 实例；同一项目同时启动多个可写 MCP
  进程不是受支持拓扑。跨进程锁仍保护写入/编译，但读取一致性与 `stop` 取消只由单个
  server process 内的协调器保证。
- 文件工具箱暂不自动重写 LaTeX 引用；被引用资源需先修改引用再移动。删除、跨项目
  移动和批量引用重写仍不在当前能力范围。
- 依赖追踪是有界的静态规则与成功 FLS 的并集，不解释任意 TeX 宏；最多追踪 2,000
  个输入、单份源码读取上限 4 MiB，超限或不可读会提示。大项目图扫描仍在 GUI
  防抖阶段执行，40,000 词统计仍需约 1.6 秒后台计算，不能声称所有操作已实时化。
- 大图暖缓存仍完整核验原图/代理 SHA-256；当前测量未支持增加仅靠文件元数据的
  捷径。快速预览的反向 SyncTeX 已按 D019 开放；无 SyncTeX 映射的内容仍无法
  保证定位，源码到 PDF 的预览方向未开放。

公开 Beta 已如实排除 Windows x64/Setup，并保留 Windows ARM64 与 macOS 的既有
限制。后续仍需补齐 Windows x64 构建机、Inno Setup、Windows TeX 验收和 macOS
notarization；在新的 bounded assignment 前不向该 Release 追加产品功能。

## Maintenance Rule

只有验证后的事实才写入本文件。命令、哈希和任务过程追加到 `PROJECT_LOG.md`；
尚未接受的设计保留在 roadmap/decision log，不写成当前能力。
