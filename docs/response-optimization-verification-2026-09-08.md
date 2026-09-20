# 响应与编译优化验收

日期：2026-09-08（Asia/Taipei）

结论：本轮优化已在工作源码中完成并通过回归；实测收益来自减少 GUI 同步工作与
无谓排队，不是 LaTeX 引擎提速，尚未打包或替换已安装应用。

## 实施边界

1. 自动编译统一要求开关开启及 root 的会话授权；静态依赖和成功 FLS 共同维护
   root-owned 输入集合。未打开输入后台按内容校验；相同字节事件不重复递增 revision，
   丢失事件由低频复核补偿，删除后重建继续可见。编辑器/磁盘冲突不自动覆盖。
2. Word Count 使用不可变 buffer 快照，运行任务和最新待处理请求均有界；结果同时
   校验 root、编辑器 revision、磁盘依赖及窗口生命期，显示明确 pending 状态。
3. 面板按 dirty domain 和可见性刷新；150 ms 内连续输入合并，资源扫描提前剪枝。
   显式完整刷新和 30 秒复核保留。
4. 编译任务绑定 root、purpose、输出目录、引擎、工具链、安全配置、source revision
   与 dependency generation。待处理任务只等待原截止时间的剩余部分；FINAL 优先，
   取消令牌覆盖已发出的 timer 与尚未进入编译的 worker。FLS 在当前 worker 退出前
   捕获，Qt 晚处理 started 信号仍使用该请求的 revision。

未替换 latexmk、PollingObserver、PDF 渲染器或运行时依赖；未更改 MCP wire schema，
未静默改写学生源码，未实现快速预览下的反向 SyncTeX。

## 响应对照

原始样本保留在 [baseline](data/response-pipeline-probe-2026-09-08.json)，第一阶段
样本保留在 [first slice](data/response-pipeline-after-2026-09-08.json)，最终样本见
[final probe](data/response-pipeline-final-2026-09-08.json)。全部为临时合成项目。

| 测量 | 基线 | 优化后 | 含义 |
| --- | --- | --- | --- |
| 4,000 词 GUI Word Count | 同步约 108 ms | 后台提交约 0.2 ms，完成约 0.1 秒 | 主线程解除阻塞，不是统计算法提速 |
| 同场景 GUI timer 额外迟到 | 约 111 ms | 约 18 ms | 单次探针，受宿主负载影响 |
| 大纲选中时编辑回调 | 约 4.09 ms | 约 0.2 ms | 旧/新同口径，原窗口未显示 |
| 真正可见的大纲，15 次输入 | 未测 | 防抖后一次刷新，0 次图片扫描 | 新增独立场景，不能回填旧基线 |
| 忽略目录含 5,000 文件 | 扫描约 12.57 ms | 约 0.02 ms | 剪枝避免进入无关子树 |
| 自动编译关闭时外部 TeX 修改 | 仍排队一次 | 排队 0 次 | 行为修复 |
| 未打开 child / bibliography | 不监听 | 均监听 | 行为修复 |

显式完整面板刷新仍需数毫秒；40,000 词后台统计仍约 1.6 秒。保留缓存校验与
pending 状态，不能把提交时间当成得到新结果的时间。三次真实 XeLaTeX/BibTeX
试验继续保留 8 页输出、安全参数、无变化/相同字节改写不重跑引擎以及正文修改只跑
XeLaTeX + xdvipdfmx 的行为；引擎时间波动，不宣称改善。

排队测试使用确定性时钟验证：请求截止 10.7 s、前一构建在 10.4 s 结束时只等待
0.3 s；在 12.0 s 结束时等待 0 s，不重新加入 0.7 s。100 次连续异步请求只启动
一个 worker，保留最新输入身份与 FINAL 优先级。

## 大图与原生 PDF 显示

[独立探针与原始数据](data/pdf-pipeline-2026-09-08.json) 使用 macOS Cocoa 窗口，
两张 6000×4000 RGB 合成噪声图共约 93 MB；这是解码/IO 压力样本，不代表典型论文。

- 冷代理准备 636.5 ms，其中解码/缩放约 412 ms；暖准备中位数 43.9 ms，主体是
  原图和代理的 SHA-256 校验。代理共约 4.55 MB，未改变既有 1800 px 策略。
- 原生窗口实际显示 preview 与 FINAL 的 2 页 PDF，输出分别约 4.56/92.79 MB，
  显示路径与对应构建结果一致；原始截图因包含本机临时路径和原始编译日志，仅在
  本地保留，不随 Git 发布。公开测量数据不变，见
  [截图证据范围](data/pdf-pipeline-2026-09-08/README.md)。
- 退出进程 → worker result → artifact accepted → document ready → Paint →
  检测到非空 PDF 内容均有独立时间点。退出到可见内容观测上界：冷 preview
  125.0 ms、冷 FINAL 323.9 ms、暖 preview 修改 30.1 ms。
- 可见内容通过 native Paint 后的 viewport grab 与合成红色区域识别确认，包含
  采样开销；不是 compositor 或显示器 scanout 时间。构建测量中的代理缓存已暖，
  冷代理准备单独统计，不能将二者混为完整冷启动。

据此保留完整内容哈希：约 44 ms 的暖准备不足以证明引入额外失效缓存值得其
正确性成本。本轮没有改动图片代理或 Qt PDF 渲染策略，也没有相应加速宣称。

## 验证与剩余限制

原方案六项门槛的证据映射：

| 门槛 | 权威证据 |
| --- | --- |
| 自动准入与安全依赖 | `test_build_events`、`test_project_dependencies`、`test_file_watcher`、`test_gui_dependencies`；GUI 重命名/关闭/冲突回归 |
| 异步 Word Count | `test_word_count` 与 GUI worker/latest request/cache/tab/close 测试；最终响应探针 |
| dirty/visible 面板与剪枝 | `test_asset_index` 与 GUI panel 三项回归；15 次输入一次刷新及忽略目录实测 |
| 编译身份/截止时间与不退化 | `test_compiler`、`test_pdf_state`、`test_preview_state`、`test_pdf_export_controller`；真实 8 页 latexmk 多轮/缓存构建 |
| 大图及可见 PDF | `bench_pdf_pipeline.py` 的 Cocoa 原生窗口时间线、2 页 PDF 与截图；不支持额外哈希缓存变更的结论 |
| 验证与文档 | compileall、全套 offscreen tests、diff check；Project State、D018、Roadmap、Index、FORCODEX 和 append-only Project Log |

- compileall、完整 offscreen suite（859 tests，165.474 s）与 git diff --check 通过。
- 聚焦回归包含外部冲突确认、同大小/同 mtime 编辑、missing parent 重建、共享 root、
  watcher 关闭竞态、后台 Word Count、late signal、冻结配置、FLS 覆盖与 stop。
- 两份最终测量的 `app_python_tree_sha256` 均为
  `0ad9f48d485483ba88d11200be2b4ee65b44ffcc50e3342e99b1ac34cacb74ef`。
- 静态依赖不解释任意宏；最多 2,000 输入、单份源码 4 MiB。大型依赖图的同步解析
  仍需另行真实项目采样；本轮不推断 Windows 或其他机器的延迟。
- 本次响应优化验收时工作树未提交，保留原有 agent-instruction 编辑。没有打包、push、发布、触发 CI、
  替换 `/Applications/ICSTeX.app` 或修改现有论文。维护者可在合成验收后选择真实项目
  验收及独立的本地升级/发布任务。
