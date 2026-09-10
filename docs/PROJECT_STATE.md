# ICSTeX Project State

更新时间：2026-09-11（Asia/Taipei）

本文件是当前已验证状态的权威来源；历史证据写入 `PROJECT_LOG.md`，未来计划写入
`docs/ROADMAP.md`，长期约束写入 `docs/DECISION_LOG.md`。

## Product and Source State

- 权威工作区：本仓库根目录；Beta 2 源码与下一代开发说明已于 2026-09-10
  同步至 GitHub 的 `release/2.1`，源码提交为 `fef3731`。
  此后 V1 本地开发已完成 M0、M1 只读纵向切片，M2 已实现项目配置、创建/工作区
  和 Block 受保护模型保存/关闭、布局及键盘可达性、属性草稿保护专项；二次编辑器
  目标绑定已通过专项/原生和冻结源码全套；后续图片导入边界修复已通过专项，
  原生导入验收未完成。用户现已授权源码同步，本地分支改名为
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
  专项、合成重开/FINAL 和最终完整回归通过，GUI 尚未接入。旧历史审计
  复现的清单路径越界及摘要未校验已完成有界修复；登记归属、受控读取/清理、
  确认后一次 Undo 与显式保存重开/FINAL 已验证。用户再次授权的本批源码已以
  `c521041` 推送至 `codex/v1-development`，远端完整哈希已核对一致；该分支名
  已符合 V1 范围，无需再次改名。上次原生观察为
  Mac 锁定，待手动解锁后验收。
  这不是完整 V1 或发布验收。活动范围和未完成验收见 `docs/V1_IMPLEMENTATION_PLAN.md`。
  签名 appcast 已移至 Git 忽略的本地候选目录，不在网站树或远端提交中。
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

- V1 本地工作源码增加“提交检查”：普通源码采用只读后台快照核对保存状态、入口、
  工具路径、实际 FINAL/PDF 输入证据、正式日志、静态资源/引用和字数口径，展示输入身份和原因。
  不因打开或刷新检查而保存、编译或联网；修改、外部事件、切换和关闭会废弃旧结果。
  Block 模式绑定当前 Block 项目，比对模型与磁盘元数据/生成源码，复用同一面板。
  实际 FINAL 绑定 job/revision/purpose/引擎、构建前后输入与 PDF 摘要；Block 结果
  按模型 revision 独立接收一次，不再写入普通源码 PDF 状态。缺少实际证据仍为未知。
  这是开发分支的 M1 只读切片，不是已发布功能或完整提交工作流；M5 仍须冻结输入。
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
  五档缩放、两种窗口尺寸和实际键盘/FINAL 已验证；高缩放仍需滚动，不是完整 M2。
- 多表格编辑已按明确 Block 绑定，切换保留各自草稿/局部 Undo，未完成的单元格输入
  也进入保存/关闭判断；应用与批量保存先校验原对象，再形成一次全局命令。未编辑
  的 opaque 字段和 False/0 保留，未知/删除对象不回退到第一张表。公式两入口共用
  原对象校验，取消/无编辑不改内容，旧对话框接受结果遇冲突保留草稿、不覆盖新模型。
  原生发现的 Enter 后立即切换/保存重复提交警告已由两项红测试复现并修复；170 项
  专项与四组同源码原生、该源码全套通过。后续图片复制使用项目锁、暂存及独占
  发布，拒绝已观测的内部链接、源变化、部分复制和重名覆盖；拖入绑定实际目标行，
  关闭会话及失败不更新模型。专项通过，真实 picker 成功导入与 FINAL 链未完成；
  Windows 竞态与不支持独占发布的文件系统仍有明确限制，见图片导入报告。
- 最新本地公式替换与插入均校验新 envelope；歧义分隔符或末尾注释吞掉闭合符时
  不形成编辑计划，保留草稿供 Undo/源码修改。粘贴保留 body 的注释换行和空白；
  无法无损投影的片段保留为原文。未知宏不会仅因未识别而被改写。专项通过；
  原生键盘/剪贴板仍待验收，见 `docs/v1-m2-formula-fidelity-verification-2026-09-11.md`。
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
  草稿、重开及独立 FINAL 通过。尚未接入 History 界面，不是自动崩溃恢复或完整 M4；
  大小/路径/平台/断电限制见 `docs/v1-m4-checkpoint-core-verification-2026-09-11.md`。
- 普通源码文本历史按来源派生 bucket 和对象路径，清单绝对路径不授予读写/删除权限；
  恢复核对登记身份、严格 UTF-8、大小与 SHA-256，合法旧 bucket 保持只读。
  新索引最多 40 项，清理仅针对核验过的本 bucket 对象；清理失败可能留下未索引文件。
  确认前后复核编辑器与历史，接受后一次 Undo、未保存、不授权编译；取消/冲突保留
  原草稿，坏历史不会阻断成功的源文件保存。合成窗口恢复、保存重开和 FINAL 已验证；
  单文件文本历史不等同原始字节备份，见 `docs/v1-m4-history-safety-verification-2026-09-11.md`。
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

2026-09-11 V1 本地工作源码的当前验证：

- 最新 M4 文本历史保护源码 SHA-256 为
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
- 后续图片专项通过，真实 macOS picker 取消后零修改已走通，但成功选择/导入未完成。
  收到源码同步请求后停止该合成探针，不计原生验收通过。新增拖入测试曾因测试夹具
  提前释放 Qt 借用的 QMimeData 而退出 139；保留该对象后原应用达到预期失败断言，
  修复应用后专项通过。这不解决此前 timer-dispatch 崩溃因果。详见
  `docs/v1-m2-image-import-verification-2026-09-11.md`。
  完整 M2–M6、IME/AX/Windows/真人验收仍未完成，不打包或发布。

## Release Matrix

| 对象 | 状态 | 说明 |
| --- | --- | --- |
| 当前源码 | V1 development increments synchronized | 2.1.0-beta.2；`c521041` 已推送至 `codex/v1-development`，包含公式保真、来源/引用/素材检查、来源修复及 M4 核心/文本历史保护；保留 Beta 远端 `release/2.1`；不是完整 V1 验收或发布 |
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

- V1 已完成普通源码和 Block 的 M1 只读切片与实际 FINAL 输入/日志绑定；M2 已有
  可编辑配置、中文项目创建、全宽工作区状态/导航、受保护模型保存/关闭及布局专项。
  属性草稿与多表格/公式对象绑定已通过专项、原生与各自源码全套。图片导入已修复
  合成测试确认的内部链接越界、部分输出、重名覆盖和拖入目标路由问题；专项通过，
  真实 picker 成功导入/FINAL 尚未验收。仅测试夹具增加已关闭窗口显式释放；
  不据此改变应用窗口所有权或宣称应用级泄漏修复。公式新输入/粘贴保真专项和其
  全套已通过；来源状态的首个只读后台片段通过专项和全套，真实窗口仍待手动解锁。
  M3 普通源码引用健康已实现首个只读片段，专项、合成窗口/FINAL 与完整回归通过；
  普通源码素材使用检查已实现并通过专项/实际合成窗口和完整回归，原生未验收。
  独立确认的来源修复已接通，并通过专项、真实合成确认/取消/冲突/Undo/重开/FINAL；
  最终源码全套通过，原生与大型预览可用性未验收。已复现的合并丢单元格和导入截断/表头/区域问题
  通过专项、真实合成候选/FINAL 和最终源码完整回归。不得将仅推进摘要或展示
  合并标签当作数据同步；
  现有 SourceRecord 仍没有持久表格基线，当前修复要求用户选择摘要匹配的原始版本；
  不把选择当前表格或仅推进摘要当作基线恢复。M4 检查点核心已通过专项与合成
  字节恢复/重开，但 GUI 选定清单、实际源/Block 草稿捕获与恢复审阅仍待接入。
  项目级 checkpoint 完整工作流、冻结导出和完整端到端验收尚未完成；
  本次源码提交/推送获单次明确授权，不改变后续开发默认不自动提交或任何发布门槛。
- M4 旧文本历史的路径/摘要/确认归属修复已通过有界合成验证，未触及真实用户文件。
  已观测链接在打开前拒绝；POSIX 目录句柄锚定不等于任意外部写者的 OS 原子 CAS。
  Windows 原生重解析竞态、断电与云盘仍未验收；搬家后的旧绝对路径记录拒绝并保留，
  不自动迁移。少量同步历史 I/O、清理失败残留与原生可用性仍需后续检查。
  新项目检查点尚无 GUI 捕获/审阅工作流，不把文本历史修复标记为完整 M4。
- 本轮早期 focused GUI 运行发生 Qt timer-dispatch SIGSEGV，后续专项和原生复跑
  未再出现，但因果链尚未确认，不记为已修复。原生 IMK/table-bounds 警告仍保留；
  高缩放可滚动访问不等价于完整键盘/IME/真人可用性。早先完整测试出现长耗时，
  活进程采样处于 Qt application stylesheet；独立 8 个测试结束后仍保留 8 个关闭
  窗口和 5518 个控件，显式释放测试窗口后仅 7 个控件。这支持测试夹具残留问题，
  不证明应用整体泄漏。M6 须对照检查性能、内存和生命周期，
  不能用完整套件成功替代原生稳定性结论。
- 提交检查解析常见静态依赖，不解释任意 TeX 宏或判定学术/课程合规；默认不假设
  课程字数上限。Block 外部冲突不会提供强制覆盖；未解决的中断写入证据阻止重试，
  其显式恢复与断电/进程终止验收留给 M4，不把部分日志当成完整项目快照。
- macOS arm64 Beta 的签名与隔离双版本替换已验证，发布暂缓于晚启动实例/安装全生命周期
  互斥门槛；需要先决定其有界实现路径，再完成原生竞态/中断和公开 HTTPS 分发验证。
  首个带更新器版本仍须人工引导安装；不把 GUI 占用扫描当作安装锁。普通网站 JSON
  不是更新 feed，现有 Windows ZIP 不直接进行原地更新。
- Windows ARM64 ZIP 已在 Windows-local `C:\w3` 从 hardened source ZIP 重建；
  Python 3.12.10 ARM64，移除系统 Python PATH 后的打包应用启动验收通过。
- Windows x64 ZIP/Setup 仍未生成；不能把 ARM64 包改名或宣称为通用 Windows 包。
- 构建机缺少 Inno Setup，因此 x64 Setup EXE 不能在未补齐构建环境时生成。
- Windows 构建机缺少 MiKTeX/TeX Live，因此不能把 source-to-PDF 记为已验证。
- 本轮用户授权的源码同步保留既有提交历史，不使用强制推送。提交范围为源码、
  测试、合成测量和文档；常见模式扫描未发现私钥、访问令牌或实际维护者目录路径。
  不据此宣称全历史或全面安全审计通过。
- 原始 PDF 性能截图含本机临时路径和编译日志，仅留本地；公开 JSON 测量数据与
  复现脚本保留。本次 `e78c2cd` 采用 `[skip ci]`，未改变工作流或仓库设置；
  推送后 GitHub API 查询该源码提交的 Actions run 数量为 0。
- 后续授权源码检查点 `c521041cb2b44740405abf4c513be5fbfca4acd3` 采用 `[skip ci]`
  并经远端哈希核对；74 个文件仅含源码、测试、合成探针和文档。未改动发布分支、
  版本、网站、工作流或候选 appcast；本轮同步不是后续开发的自动推送许可。
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
