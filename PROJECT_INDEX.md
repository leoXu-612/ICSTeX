# ICSTeX Project Index

更新时间：2026-09-17（Asia/Taipei）

## 权威工作区

- 当前可写路径：`git rev-parse --show-toplevel` 返回的 `ICSTeX` 仓库根目录
- 旧路径：仅作回滚参考的 legacy workspace
- 旧路径只保留为 rollback context，不在其中继续开发。

## 文档入口

- `app/core/project_archive.py`、`app/gui/project_archive_dialog.py`：源工程 ZIP 导出，
  复用文件筛选/快照和 CaptureLease；不要求成功编译，不替代正式 PDF 提交检查。
- `docs/user-guide.md`：学生图文指引；应用内入口为“帮助 → 新手导引”。
- `app/gui/user_guide.py`、`app/gui/tutorial_controller.py`、`app/core/tutorial.py`：
  本地配图阅读、独立写作练习及纯标题/项目规则；不替代真实学生验收。
- `app/assets/user-guide/`、`tools/capture_user_guide.py --output <新目录>`：
  四张真实界面配图及再生成入口；仅使用工具自己创建的练习，需要本地 LaTeX 环境。
- `README.md`：用户/开发者安装、运行、测试和打包入口。
- `AGENTS.md`：所有 coding agent 的操作约束。
- `docs/PROJECT_STATE.md`：当前已验证源码、release matrix 与风险。
- `docs/ROADMAP.md`：产品和技术优先级。
- `docs/UPDATE_ACTIVATION_PREPARATION.md`：Mac Beta 启动检查与线上升级准备、安装期
  临时协调方案及未授权/未验收边界；不等于公开更新服务已启用。
- `docs/PERFORMANCE_UI_PROGRESS.md`：性能/UI任务的简明当前A–F交接，含完整旧记录归档链接、新基线、失败证据
  和下一步；与旧V1验收和Beta发布brief分离。
- `tools/bench_word_count_segments.py`、`tools/probe_texcount_fallback.py`：E1合成字数
  对照、精确结果核验与单次降级诊断；使用新证据目录，不操作真实论文或运行环境。
- `tools/bench_desktop_overhead.py`：E2新解释器启动分段、单/多窗口缩放、独立空闲
  CPU与事件观察、窗口回收；统计样本与原生/冷启动边界分开，实验变体不修改产品。
- `tools/run_source_regression.py`：执行仓库强制unittest discovery，保存完整输出、
  退出码及前后源码身份；仅用于当前源码回归，不代替原生/人工验收。
- `tools/probe_workbench_layout.py --full-matrix`：F四尺寸五档的源码/交付/公式/Block
  对照；`--observe-target-pdf`另记录指定白底单页夹具的稳定像素，不替代原生验收。
- `tools/pdf_pixel_evidence.py`、`tools/probe_pdf_fit_bounds.py`：合成PDF的像素观察及
  裸Qt校准，包含纯白/稀疏灰字对照；不是通用PDF空白分类器。
- `tools/probe_submission_panel_ui.py`：D1源码/Block检查面板的同状态布局与只读操作
  探针；活动/可见前提、按钮/选中行与原件保留分别核验，不替代真人验收。
- `tools/probe_delivery_stages_ui.py`：D2固定交付的同配方离屏布局对照，使用明确标注的
  合成单位证据；实际FINAL/交付由`probe_submission_delivery_gui.py --delivery-only`验证。
- `tools/probe_task_panel_ui.py`：D3大纲、快捷引用、公式、Block导航/槽位/结果的独立
  Qt部件对照；合成模型与结果不冒充真实编译、嵌入窗口或原生验收。
- `tools/probe_transaction_panels_ui.py`：D3共用审阅界面的真实合成文件/草稿对照；
  核验顶部/底部固定动作、请求尺寸和原件保留，不自动打开副本或编译。
- `docs/CODEX_V1_DEVELOPMENT_INSTRUCTIONS.md`：下一代正式版的待执行开发总纲、
  分阶段验收与授权边界；不自动替换现有 active brief。
- `docs/V1_IMPLEMENTATION_PLAN.md`：已启动的下一代本地开发范围、差额、验收账本、
  当前唯一 slice 与下一步；与独立 Beta 发布 brief 分离。
- `docs/MAC_WRITING_HANDOFF.md`：用户优先选择的 Mac 普通写作源码启动入口、已有
  功能和已知限制；受限 Biber 延期，不代表已更新安装版或完整 V1 验收。
- `docs/V1_ACCEPTANCE_MATRIX.md`：M0–M7 要求与 A01–A15 场景的证据入口、
  有限本地剩余项及平台/真人/发布门槛；不是完整验收通过证明。
- `docs/V1_RELEASE_READINESS.md`：源码、平台、制品、签名、安装、分发和真人验收
  七项独立状态的工作清单；当前仍是草稿，不是完成交接或 release candidate 推荐。
- `docs/v1-local-closeout-audit-2026-09-12.md`：原始要求收尾审计、实际交付文件复核，
  以及有限键盘流程 R2a–c、历史稳定性风险和受限引擎决策；不是完整 V1 验收通过。
- `docs/v1-m6-modal-keyboard-verification-2026-09-12.md`：目录 Tab、下拉框焦点与
  Return 误确认、分页栏修复；实际普通 PDF-only 交付/独立草稿恢复和未完成键盘边界。
- `docs/v1-m6-recovery-migration-keyboard-verification-2026-09-12.md`：独立 Block
  分页焦点修复、三类五档键盘验收、解锁后的迁移/150% 恢复操作及剩余窗口/菜单证据。
- `docs/v1-m6-migration-window-verification-2026-09-12.md`：真实打开确认框与独立窗口
  销毁边界回归、隐藏窗口失败对照、复用已有副本的原生位置观察入口。
- `docs/v1-m6-response-verification-2026-09-11.md`：M0 同样本响应复核、200 子文件
  GUI 路径检查优化及三组原生冷暖 PREVIEW/FINAL；保留探针失败与平台验收边界。
- `docs/v1-m6-ime-verification-2026-09-11.md`：公式可视区输入法接入、源码/可视
  预编辑保护、Undo 与真实 Cocoa 拼音证据；区分事件级、原生及全套结果。
- `docs/v1-m6-workbench-input-verification-2026-09-11.md`：解锁后普通源码/属性/表格
  原生拼音与落盘验证、普通源码保存快捷键修复，以及当时的 Control+Tab 焦点缺口。
- `docs/v1-m6-focus-readiness-verification-2026-09-11.md`：Inspector 焦点路由修复、
  进程树夹具就绪/反例验证；区分后台回归与锁屏后未完成的原生复验。
- `docs/v1-m6-inspector-native-focus-verification-2026-09-11.md`：唤醒后当前源码的
  Inspector 原生双向快捷键、中文草稿及 150% 焦点可见性；明确应用/保存/关窗。
- `docs/v1-m6-lualatex-verification-2026-09-11.md`：受限 LuaLaTeX 读取失败的本机
  证据、致命日志漏报/折行修复与最终界面；保留未解决的引擎兼容及安全边界。
- `docs/v1-m6-lualatex-policy-review-2026-09-11.md`：只读路径判定排除以 Lua 缓存
  目录作为发行版只读白名单的方案；输入/输出均会放行，不改配置或进行实际写入。
- `docs/v1-m6-lualatex-compatibility-research-2026-09-12.md`：授权兼容研究的实际失败
  结果、上游读取策略变更及待决定的 OS 隔离原型；不作为兼容或安全验收通过。
- `docs/v1-m6-macos-sandbox-prototype-2026-09-12.md`：后续获批 Mac 临时隔离原型的
  正反边界、中英文 PDF 和终止证据；区分可行性、正式接入及弃用接口支持风险。
- `docs/v1-m6-macos-sandbox-integration-2026-09-12.md`：Mac 受限编译源码接入、
  LuaLaTeX/BibTeX 和 stdio 导出、硬链接拒绝及进程树停止；明确源码与发布支持边界。
- `app/core/macos_compiler_sandbox.py`、`tests/test_macos_compiler_sandbox.py`、
  `tools/probe_macos_compiler_sandbox.py`：隔离后端、专项测试和可分项执行的合成真实链探针。
- `docs/v1-m6-macos-biber-boundary-2026-09-12.md`、`tools/probe_biber_runtime.py`：
  未重复的 Biber 实际链/启动缩小诊断；后续已按用户选择延期，运行时准备方案未实施。
- `docs/v1-m6-style-gc-verification-2026-09-11.md`：Qt 样式遍历期间循环控件回收
  的原生崩溃复现、同步引用保护及回归；与旧计时器崩溃和 AX 限制分开。
- `docs/v1-m6-idle-composition-verification-2026-09-11.md`：普通源码候选输入与真实
  正文通知分离、默认自动保存/外部重载保护；区分实际计时器回归和待验证的物理输入法。
- `docs/v1-m6-native-idle-save-verification-2026-09-11.md`：当前源码原生默认保存、
  候选保留/取消不重复写盘及保存后撤销；区分分段转换与真实提交，保留未执行的冲突场景。
- `docs/v1-m6-native-conflict-formula-verification-2026-09-12.md`：后续原生外部冲突、
  默认拒绝覆盖与另存双版本；当前源码公式可视/源码模式分段候选、撤销/重做及键盘确认。
- `docs/v1-m6-citation-layout-verification-2026-09-11.md`：高缩放引用详情/动作与导航栏
  可见区域修复；记录几何断言盲点和新发现的候选输入导致周期检查失效的问题。
- `docs/v1-m6-citation-keyboard-verification-2026-09-12.md`：原生引用表焦点循环复现、
  两个只读表的 Tab 修复与回归；保留当时的锁屏中断，后续原生证据见下。
- `docs/v1-m6-native-navigation-verification-2026-09-12.md`：解锁后引用键盘定位、
  焦点滚动与工具导航顺序修复；四类只读表 Return/Enter 回归和原生证据边界。
- `docs/v1-m6-four-route-navigation-verification-2026-09-12.md`：大纲/搜索实际键盘
  定位、单条结果空格选择说明与当时锁屏中断；后续诊断/错误证据见下。
- `docs/v1-m6-console-pdf-native-verification-2026-09-12.md`：诊断/错误实际 Return
  定位、原生 200% 合成 PDF 观察，以及当时发现的控制台裁切问题。
- `docs/v1-m6-console-layout-verification-2026-09-12.md`：控制台高度/诊断滚动与
  当前行显露修复；五档红绿、原生 100%/150% 键盘/折叠复验和冻结全套。
- `docs/v1-m6-reading-console-verification-2026-09-12.md`：字数/提交检查焦点与
  嵌套文本裁切修复；长文本五档红绿、原生首尾阅读/反向导航及冻结全套。
- `docs/v1-m6-pdf-keyboard-verification-2026-09-12.md`：PDF 菜单禁用保护与焦点修复；
  保留当时发现的源码/PDF 重叠、适宽缩放方向和页码漂移，后续修复见下。
- `docs/v1-m6-pdf-geometry-verification-2026-09-12.md`：上述面板重叠、实际缩放/页内
  位置及整页居中修复；像素/几何断言、原生菜单复验与截图滞后证据边界。
- `docs/v1-m6-readonly-table-focus-verification-2026-09-12.md`：同类问题在另外九个
  工作台/来源只读表的红绿与键盘焦点修复；与原生动作及可见性验收分开。
- `docs/v1-m6-source-identity-verification-2026-09-11.md`：普通源码独立版本号与五类
  只读消费者；候选保留、晚到结果/撤销/重载/后台标签和缓存读取边界。
- `docs/v1-m6-deferred-selection-verification-2026-09-11.md`：重命名后延迟选择的
  窗口/项目归属修复，以及扩展回归新发计时器 SIGBUS 和有界对照；不宣称崩溃已修复。
- `docs/v1-m6-gutter-lifetime-verification-2026-09-11.md`：编辑器/行号栏引用环与
  后台回收崩溃对照、弱引用修复及原失败命令复验；保留历史崩溃对象与原生验收边界。
- `docs/v1-m6-tab-disposal-verification-2026-09-11.md`：区分 Qt 销毁和包装器回收，
  修复已关闭标签编辑器累积；保留当时发现的表格对话框累积证据。
- `docs/v1-m6-table-insertion-verification-2026-09-11.md`：表格对话框释放、宏包与
  正文一次撤销、Unicode/选区保全；外部重载后的旧目标拒绝、草稿及保存重开/FINAL。
- `docs/v1-m6-formula-coordinates-verification-2026-09-11.md`：公式 Python/UTF-16
  坐标边界、目标关闭/重载拒绝及草稿保留；实际保存重开/FINAL 与灰色字形检查器修正。
- `docs/v1-m0-m1-verification-2026-09-10.md`：M0/部分 M1 的合成数据、原生验证、
  复现入口和未完成边界；不代表完整 V1 或发布验收。
- `docs/v1-m1-final-evidence-2026-09-10.md`：后续实际 FINAL 身份、输入/产物摘要、
  Block 归属与只读检查验收；与 M2–M6 和发布验收分开。
- `docs/v1-m2-profile-verification-2026-09-10.md`：本地声明式配置、冲突保护、
  字数目标和检查联动的原生证据；不是完整 M2 工作台验收。
- `docs/v1-m2-workspace-verification-2026-09-10.md`：中文项目创建、只读工作区状态、
  原生 FINAL/检查/导出/重开与干净 Block 关闭；保留待保存/冲突和布局门槛。
- `docs/v1-m2-block-close-verification-2026-09-10.md`：后续受保护模型/生成源码保存、
  关闭选择、外部冲突、异步 FINAL 与原生重开；不是完整 checkpoint 或布局验收。
- `docs/v1-m2-block-layout-verification-2026-09-10.md`：窄窗口/五档缩放、键盘/Undo、
  布局属性与同源码原生复跑；记录当时的属性草稿和性能复核缺口。
- `docs/v1-m2-property-draft-verification-2026-09-11.md`：后续内存属性草稿、
  选择/刷新保留、显式应用/关闭、冲突和原生证据；记录当时的二次编辑器缺口。
- `docs/v1-m2-editor-target-verification-2026-09-11.md`：多表格/公式目标绑定、
  活跃单元格草稿、显式保存/撤销、原生冲突与实际 PDF；区分专项和全套结果。
- `docs/v1-m2-image-import-verification-2026-09-11.md`：图片暂存/独占发布、路径与
  拖入目标边界、测试夹具修正；真实 picker 取消/导入/链接拒绝与保存重开/FINAL 已补验。
- `docs/v1-m2-formula-fidelity-verification-2026-09-11.md`：公式替换的新输入校验、
  粘贴注释与空白保真；真实 Cocoa 剪贴板/Undo/源码回退/FINAL 及错误提示修正。
- `docs/v1-m3-citation-health-verification-2026-09-11.md`：普通源码只读引用健康、
  跨文件/草稿位置、解析未知边界、合成窗口与真实 BibTeX/FINAL；完整与原生验收分别记录。
- `docs/v1-m3-source-status-verification-2026-09-11.md`：来源有界后台检查、
  关联 Block 定位和不推进基线；区分专项、全套和待解锁的原生验收。
- `docs/v1-m3-material-usage-verification-2026-09-11.md`：素材静态使用位置、内容变化、
  同内容候选与只读内存缓存；记录专项、实际图片 FINAL、全套及旧合并器丢单元格缺陷。
- `docs/v1-m3-merge-import-verification-2026-09-11.md`：独立合并候选保全、结构冲突、
  导入拒绝截断/保留表头/正确合并区域；后续真实来源应用见下一项。
- `docs/v1-m3-source-repair-verification-2026-09-11.md`：真实摘要匹配基线、显式行键映射、
  全部关联表格一次确认/Undo、取消与冲突拒绝、保存重开和实际 FINAL；保留原生及快照缺口。
- `docs/v1-m3-native-followup-verification-2026-09-11.md`：后台限定前完成的 Cocoa 引用/
  素材/来源修复合成流程、实际可见 PDF、探针修正和保留的 IMK/AX/输入法边界。
- `docs/v1-m4-checkpoint-core-verification-2026-09-11.md`：选定文件原始字节检查点、
  独立草稿、恢复到新目录、损坏/竞争/中断验证；核心阶段证据，并记录旧历史路径信任风险。
- `docs/v1-m4-history-safety-verification-2026-09-11.md`：文本历史来源/路径/摘要保护、
  合法旧记录只读兼容、确认后一次 Undo、保存重开/FINAL 验证与剩余平台边界。
- `docs/v1-m4-checkpoint-gui-verification-2026-09-11.md`：项目检查点真实选择/确认/恢复界面、
  多窗口源码和 Block 属性草稿独立捕获、保存字节重开/FINAL；捕获阶段证据。
- `docs/v1-m4-recovered-drafts-verification-2026-09-11.md`：恢复副本复核、独立窗口继续
  源码/Block/未应用单元格草稿、首次显式保存保护与重开/FINAL。
- `docs/v1-m4-write-recovery-verification-2026-09-11.md`：中断写入逐文件版本比较、
  新目录恢复与全部冲突证据保留；实际进程中断、恢复/重开/FINAL 及 Cocoa AX 临时保护的边界。
- `docs/v1-m4-migration-core-verification-2026-09-11.md`：旧格式确定性转换、原始字节
  保全与新副本发布的后台证据；该核心冻结源码完整回归通过。
- `docs/v1-m4-migration-gui-verification-2026-09-11.md`：选定文件/字节差异审阅、证据
  复核与单独确认打开；离屏实际副本/重开/FINAL 通过，后续完整回归单独跟踪。
- `docs/v1-m5-delivery-audit-2026-09-11.md`：已复现的旧 PDF/可移植包导出缺口及
  下一有界实现契约；不是修复或验收通过。
- `docs/v1-m5-delivery-core-verification-2026-09-11.md`：固定输入/PDF、独立输出选择、
  暂存发布及真实合成重编译/恢复证据；初始核心源码的独立验证边界。
- `docs/v1-m5-delivery-gui-verification-2026-09-11.md`：Source/主窗口与独立 Block
  审阅交付、四种实际离屏/原生重编译与恢复、晚 PDF 回调回归及其已通过的完整回归。
- `docs/v1-m5-agent-export-verification-2026-09-11.md`：Agent/MCP 内容绑定与独占导出、
  包字节保全、实际 stdio 证据、共享 FINAL 暖缓存缺陷与当前修复回归边界。
- `docs/v1-m6-window-lifetime-verification-2026-09-11.md`：确认关窗后控件残留的
  可重复诊断、销毁/取消/多窗口回归、Cocoa 与完整回归；不冒充原 SIGSEGV 根因证明。
- `docs/v1-m5-tool-versions-verification-2026-09-11.md`：实际 FINAL 初始版本标签、
  固定报告字节、三类真实编译/交付/恢复及完整回归；自报标签不是二进制身份认证。
- `docs/DECISION_LOG.md`：长期架构决策及其原因。
- `docs/update-delivery-design-2026-09-08.md`：原生更新器实现、信任分工与发布验收边界。
- `packaging/UPDATES.md`：维护者提供配置、暂存固定 SDK、签名与 appcast 接入步骤。
- `docs/FORCODEX_UPDATES.md`：与本机安装任务隔离的并行更新器范围及收口 brief。
- `docs/MEMORY_MANAGEMENT.md`：文档职责、权威顺序和信息生命周期。
- `DEEPSEEK.md`：DeepSeek 兼容入口，只指向统一规则与任务 brief。
- `FORCODEX.md` / `FORCLAUDE.md` / `FORDEEPSEEK.md`：当前 bounded
  assignments。
- `MEMORY.md`：紧凑、跨任务的 durable reminders。
- `PROJECT_LOG.md`：append-only 已完成工程历史。
- `docs/response-optimization-verification-2026-09-08.md`：响应优化验收、测量边界与
  原始/后测样本入口。
- `CHANGELOG.md`：面向用户的版本变化。
- `MIGRATION_RECORD.md`：workspace migration、备份和验证证据。
- `PROJECT_FILE_INDEX.sha256`：迁移时建立的稳定内容索引，不代表后续源码未变化。

## 代码入口

```text
app/
  core/        编译、PDF 状态、Word Count、诊断、路径和纯文本规则
  gui/         PySide6 主窗口、controllers、编辑器、PDF、工具箱和主题
  assets/      App 内置视觉资源
tests/         unittest 回归与 GUI smoke tests
packaging/     macOS/Windows 构建脚本、spec、README 和 offline wheel
tools/         开发辅助、协作 watcher、隔离性能与编辑器交互探针
dist/          已生成 artifacts，不是源码权威来源
build/         可重建 packaging cache，不是源码权威来源
```

公式/表格交互回归：`app/gui/formula_dialog.py`、`app/gui/table_grid.py`、
`app/gui/insert_panel.py`、`app/gui/blocks/table_editor.py`；剪贴板纯规则位于
`app/core/table_clipboard.py`。原生合成数据检查入口为 `tools/probe_editor_interactions.py`。

应用更新：`app/core/app_updates.py`、`app/gui/app_update_controller.py`、
`app/gui/update_dialog.py`、`app/gui/update_backends.py`；原生 SDK 构建接入位于
`packaging/native_updates.py` 与 `packaging/native_updates/sparkle_bridge.m`。
默认不配置运行时；离线中文界面探针为 `tools/probe_app_updates.py`。

## 常用命令

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m app
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
bash packaging/preflight.sh
```

迁移索引验证需要使用 macOS 可用的 UTF-8 locale：

```bash
env -u LC_ALL -u LC_CTYPE LANG=en_US.UTF-8 \
  shasum -a 256 -c PROJECT_FILE_INDEX.sha256
```

正常开发后出现 index mismatch 是预期现象；用当前测试、Project State 和
PROJECT_LOG 判断后续变更，不要把迁移索引当作版本控制系统。
