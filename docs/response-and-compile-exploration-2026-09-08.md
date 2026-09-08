# 响应速度、事件判断与 PDF 编译优化探索

结论：优先统一事件准入、移出 GUI 同步字数统计和减少全量面板扫描；现有 latexmk
增量构建已经有效，不宜把更换引擎或缩短所有防抖时间作为第一步。

## 范围与证据

- 本轮是方案研究和本地诊断，不改变 `app/` 行为，不修改学生文稿、不打包、不发布。
- 当前应用源码为 `release/2.1` 的 `f0f693542b6fe95121e719db3da804fc0679f9e5`。
  开始时已有 `AGENTS.md`、`PROJECT_LOG.md` 和 `skills/icstex-control/SKILL.md`
  未提交修改；这些修改不属于本轮性能研究。
- 环境：Apple M3、macOS 26.6.1 arm64、Python 3.12.6、PySide6 6.11.1、
  watchdog 6.0.0、TeX Live 2025 / latexmk 4.86a。
- [可复现探针](../tools/bench_response_pipeline.py) 只使用临时合成项目和隔离的
  QSettings；[原始样本](data/response-pipeline-probe-2026-09-08.json) 保留各次耗时、
  实际 latexmk rule、事件判定与 PDF 页数。没有向外发送项目内容。

```bash
QT_QPA_PLATFORM=offscreen python3 tools/bench_response_pipeline.py \
  --output docs/data/response-pipeline-probe-2026-09-08.json
```

## 本机实测

常规调用计时各 5 次，编辑信号各 15 次，编译场景各 3 次；表中是中位数，
不是跨设备基准或优化后的收益。英文重复句是受控负载，不代表全部真实 IA/EE。

| 探针 | 耗时 / 结果 | 证据边界 |
| --- | ---: | --- |
| 4,000 词 `count_project`，结构化统计 / TeXcount 模式 | 51.5 / 102.3 ms | TeXcount 路径仍先执行本地结构分析 |
| 12,000 词，结构化 / TeXcount | 208.8 / 327.8 ms | 同上 |
| 40,000 词，结构化 / TeXcount | 1,062.6 / 1,506.4 ms | 压力样本，不能外推为典型学生文稿 |
| 约 4,000 词的实际 GUI 字数刷新 | 108.1 ms | 10 ms GUI 定时器额外晚到 110.7 ms |
| 50 张小图，文件栏 / 大纲栏选中时单次编辑 | 0.15 / 4.09 ms | 同步编辑信号处理；不是屏幕首帧延迟 |
| 空目录资源扫描 / 另含 5,000 个被忽略构建文件 | 0.04 / 12.57 ms | `rglob` 仍进入被忽略目录，之后才过滤 |
| 8 页、目录、交叉引用与 BibTeX 项目：冷构建 | 1,763.1 ms | 3 次 XeLaTeX、2 次 BibTeX、1 次 xdvipdfmx |
| 同项目：无变化 / 同内容重新写入 | 59.3 / 58.6 ms | 0 次引擎 rule；PDF 字节未变 |
| 同项目：修改一个正文短语 | 728.6 ms | 1 次 XeLaTeX + 1 次 xdvipdfmx，无 BibTeX |

编译样本均成功、保持 `-norc` / `-no-shell-escape`，并用 QPdfDocument 确认 8 页
可读取 PDF。未测实际窗口的第一帧绘制、中文字体、大图或 Biber 大型书目性能。

重要修正：不能把“文件 mtime 改变”直接等同于“latexmk 重跑全部引擎”。本轮
同内容重写仍是 no-op。历史 Block 报告中的写入减少可以降低 I/O，但不能仅凭 mtime
变化推断引擎重编；也不能把历史 Block 测量直接套到普通源码模式。

## 建议顺序与机制

### 1. 统一事件准入与依赖归属

已复现：根文件获得会话编译授权后，即使自动编译开关关闭，外部 `.tex` 变化仍会
排队一次编译；文本重载成功，开关仍为 false。原因是
[`DocumentLifecycle.reload_external_change`](../app/gui/document_lifecycle.py)
仅检查授权，不检查自动编译开关，而图片事件走另一套判断。

另一个静态和注册集证据是：只打开 `main.tex` 时，watch set 不包含引用的未打开
`child.tex` 和 `refs.bib`；成功编译后的注册代码只补充图片依赖。不能依赖“未打开
文件没触发事件”来证明 PDF 仍然新鲜。

建议在 `app/core` 引入小型、可测试的事件决策函数，GUI 只执行决策：

| 事件 | 状态处理 | 自动构建 |
| --- | --- | --- |
| 自己保存的回声、内容未变 | 不产生新 revision | 不构建 |
| 真实外部变化，自动编译关闭 | 更新/保留缓冲区并明确标记受影响 root stale | 不构建 |
| 真实变化，但 root 未获会话授权 | 更新状态，不提升权限 | 不构建 |
| 已授权且自动编译开启的输入依赖变化 | 按 root 合并 dirty set | 只排最新必要构建 |
| `.latex_build` / `.icstex` 生成物事件 | 排除自触发；不当作源输入 | 不构建 |
| 手动 Compile / Export | flush 同 root 文档，保持 FINAL 优先 | 显式正式构建 |

先修正开关一致性，再把静态 include/BibTeX 引用与成功构建的 `.fls` 输入合并成
root-scoped 依赖图。`.fls` 也是不受信数据：必须排除输出、发行版目录、越界路径和
符号链接，不可因为文件出现在 `.fls` 就获得读取或监视权限。失败构建不能删除上次
有效依赖；缺失文件要保留重建监视，并使用有界的删除/重建确认。

GitHub 经验：[LaTeX Workshop 的自动构建准入](https://github.com/James-Yu/LaTeX-Workshop/blob/8264fc9178763261b326c5b10c66c5929689ff54/src/compile/build.ts)、
[FLS 输入/输出区分](https://github.com/James-Yu/LaTeX-Workshop/blob/8264fc9178763261b326c5b10c66c5929689ff54/src/core/cache/auxiliaries.ts)、
[二进制写入稳定及删除确认](https://github.com/James-Yu/LaTeX-Workshop/blob/8264fc9178763261b326c5b10c66c5929689ff54/src/core/watcher.ts)。
本项目已有 macOS FSEvents 崩溃规避理由，因此保留 polling 后端作为基线；先优化
事件分类和监视集合，不直接换回 native watcher。上游的固定等待值不直接照搬。

### 2. 把字数与项目分析从 GUI 热路径移出

[`MainWindow.update_word_count`](../app/gui/main_window.py) 在切换标签和活动编译结束时
同步执行 `count_project`；后者先结构化解析，再同步运行最长 15 秒的 TeXcount。
仅把 TeXcount 改为异步仍会留下前面的解析阻塞。

建议先在 GUI 线程捕获不可变文本快照，再异步执行解析和 TeXcount，以
`(root, source_revision, dependency_generation, count_mode)` 标识任务和缓存。
同 key 复用结果，连续修改只保留最新请求；回传时校验 root、revision 与窗口生命期。
显示上次结果时明确标记“待更新”，不可把旧值标为精确当前值。

QProcess 适合外部 TeXcount；Python 解析可先使用有界 worker，实测 GIL 对 GUI
延迟仍显著时才评估进程隔离。不能用去掉结构分析或把 fallback 冒充 TeXcount 来
换取表面速度。字符串 segment 聚合也有重复拼接成本，但解析器本身占有较多 CPU，
因此不应先把全部希望放在局部微优化上。

GitHub 经验：[TexLab 按文件和诊断来源保存结果](https://github.com/latex-lsp/texlab/blob/4cc18b37c0b46baf39189f173d1bd7468d3f56e1/crates/diagnostics/src/manager.rs)、
[外部 ChkTeX worker 与文件事件编排](https://github.com/latex-lsp/texlab/blob/4cc18b37c0b46baf39189f173d1bd7468d3f56e1/crates/texlab/src/server.rs)。
借鉴职责划分，不引入完整 LSP 或照搬其全部调度行为。

### 3. 按变化类型刷新面板，扫描时先剪枝

当前大纲、图片、历史、引用或标签栏可见时，每次键入都会调用完整
[`ProjectPanelController.refresh`](../app/gui/project_panel_controller.py)，而不是只更新
所选面板；保存也再调用同一个刷新入口。图片 metadata 和缩略图已有缓存，但资源
目录仍被遍历，列表仍重建。

建议：文本编辑只使大纲/label/citation dirty；图片目录变化才更新资源索引；快照
产生才更新历史。隐藏面板延迟刷新，可见面板在短防抖后按 revision 计算。把
[`AssetIndex.scan`](../app/core/asset_index.py) 的后过滤遍历改为目录下降前剪枝，避免
每次按键扫描构建缓存。仍保留显式 Refresh 和低频完整核对以修复丢失事件。

这项在小项目中仅节省数毫秒，不应宣传为数量级端到端提速；目录变大或文件位于
较慢存储时才更值得复测。

### 4. 保留 latexmk 增量语义，优化构建前后重复工作

现有 `-xelatex` 已由 latexmk 使用 XDV 中间结果并在需要时运行 xdvipdfmx；
本轮冷构建多次 XeLaTeX 后只转换一次 PDF。无变化时约 59 ms 已是低成本驱动检查，
正文修改约 729 ms 也没有无谓地重跑书目工具。

建议保留 `.aux` / `.fls` / `.fdb_latexmk` 与 preview/final 独立输出目录：

- `CompileManager` 已有单 root 串行、pending 合并、FINAL 优先和 timer generation。
  后续只补充完整 job key 与最新输入 revision，不另写全局编译系统。
- 已等待过空闲窗口的 pending 任务，不应无条件在前一构建结束后再等待完整防抖；
  按请求时间与输入 revision 计算剩余等待，同时保持 FINAL 和 stop 语义。
- 同 root / 同 revision 的 PDF 显示已经去重，不能把“每次成功都重载 PDF”作为事实。
  仍可对引擎 no-op 结果复用未变的分析；不同 revision 但 PDF 字节相同的场景须区分
  显示内容与 SyncTeX/正式 freshness，不能只凭 PDF 哈希宣称构建有效。
- [`ImageProxyCache`](../app/gui/image_proxy_cache.py) 暖缓存仍重读原图 SHA-256。
  图多时可评估变更集合驱动的内存验证缓存，但不能只凭 mtime/size 认定内容未变。
  需兼顾 watcher 丢事件、同大小替换、代理损坏与明确的全量复核策略；本轮未测大图
  收益，因此列为次级实验，不作为已证实的首要瓶颈。

GitHub 经验：[LaTeX Workshop 的最新请求 / generation / 串行 drain](https://github.com/James-Yu/LaTeX-Workshop/blob/8264fc9178763261b326c5b10c66c5929689ff54/src/compile/executor.ts)
也在 skipped build 后跳过 viewer 刷新；
[TeX Live 中的 latexmk](https://github.com/TeX-Live/texlive-source/blob/bb984049b0b66e1be0370ad161c57db1f09ba585/texk/texlive/linked_scripts/latexmk/latexmk.pl)
保留文件数据库并使用 XeLaTeX `-no-pdf`。本机结果来自已安装的 4.86a，而非声称
运行了链接中的最新版。

## 暂不采用与验证门槛

- [VimTeX 的持续 latexmk `-pvc`](https://github.com/lervag/vimtex/blob/e355987594cbf16283bee7b37e3aa3a65d5e1c5c/autoload/vimtex/compiler/latexmk.vim)
  可避免反复启动 driver，但本机 no-op 约 59 ms，收益上限不足以优先承担另一套
  watcher、跨 preview/final 生命周期和停止协议的复杂度。
- [Tectonic](https://github.com/tectonic-typesetting/tectonic) 是另一条工具链，不能仅凭
  “现代化引擎”推断更快。若以后比较，必须覆盖中文字体、书目、宏包、SyncTeX、离线
  资源和相同输出；本轮没有移植或速度优劣结论。
- 不并行编译同一 root 的共享输出目录，不关闭安全参数，不为了速度清空每次构建
  缓存，不默认修改用户 preamble、使用 shell-escape 外部化或跳过正式多轮收敛。
- 本轮没有证明真实窗口第一帧 PDF 渲染是瓶颈。后续需要独立测量 `process exit →
  artifact accepted → document ready → first visible paint`，不能用 `load_pdf()`
  调用耗时代替可见速度。已有 Block profiler 可复用，但普通源码模式要单独采样。

下一轮若授权实施，建议先做事件准入与异步字数两个 bounded slices；每个 slice
分别验证：自动编译关闭、首次授权、自己保存回声、原子替换、未打开依赖、相同大小
外部替换、连续输入、tab/root 切换、stop、旧 worker 回传、失败 stale PDF、FINAL
导出与光标/滚动不变。随后再做面板失效粒度和图多项目测量。

本轮没有复制第三方实现或新增 runtime 依赖；GitHub 代码只用作机制对照。
应用优化的实际收益仍需要在获准实现后，以同一探针前后对照证明。

验证：完整探针、`compileall`、全量 offscreen unittest 与 `git diff --check` 通过；
命令和最终结果记录在 [PROJECT_LOG.md](../PROJECT_LOG.md) 的本轮条目。
