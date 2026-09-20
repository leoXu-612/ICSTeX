# Block 编译管道性能审计（perf/block-compile-pipeline-audit）

> 目的：以证据回答“Block 集成后从修改到 PDF 更新变慢”的真实构成，先测量、后优化。
> 工具：`tools/bench_block_compile.py` + `ICSTEX_COMPILE_PROFILE=1` 事务探针。

## 1. 方法

- 合成项目：Small 11 Block、Medium 51、Large 101（含公式/图片/表格，最大 100×50）；
- 操作：改 Text / Formula / Table（每项 10 或 5/3/2 次），分段计时
  （save / assemble / latex 进程 / pdf 加载）+ 端到端自动路径（含 700ms 防抖）；
- 计数：compile_requested、实际 LaTeX PID（`_compile_launches`）、生成文件 written/unchanged、
  Watchdog 事件（静态审计）。

## 2. 实验矩阵（中位数，ms；written/unchanged 为文件数）

| 操作 | Block 数 | 表规模 | save | assemble | written/unchanged | latex 进程 | pdf 加载 | 自动端到端 |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| Text | 11 | – | 2.1 | 0.6 | 1 / 12 | 814 | 0.2 | 1974 |
| Text | 51 | – | 5.8 | 2.4 | 1 / 52 | 1049 | 0.3 | 2485 |
| Formula | 51 | – | 5.7 | 2.4 | 1 / 52 | 1055 | 0.3 | – |
| Table | 51 | 20×10 | 5.9 | 2.4 | 1 / 52 | 1075 | 0.3 | – |
| Text | 101 | – | 20.9 | 34.6 | 1 / 102 | 1152 | 0.3 | 2701 |
| Formula | 101 | – | 20.8 | 33.1 | 1 / 102 | 1125 | 0.3 | – |
| Table | 101 | 100×50 | 24.0 | 33.3 | 1 / 102 | 1107 | 0.3 | – |

修复前（全量重写）：每次编辑 written = N、unchanged = 0；save 2.3/5.6/20ms；
assemble 0.9/3.4/36ms；自动端到端 1952/2547/2706ms。

## 3. 假设逐项结论

1. **防抖设计等待**：500ms 保存与 700ms 编译**并行**（同一模型变化同时启动两个计时器），
   固定等待 ≈ 700ms；保存完成不重新触发预览。属设计性延迟（A 类）。
2. **项目保存**：每次编辑全量序列化（blocks/layouts/sources/theme 全部 JSON 原子重写），
   无 dirty tracking；11→51→101 Block 时 save 2.1→5.8→20.9ms，随规模增长（C 类，量级小）。
3. **Stable LaTeX 全量生成**：每次编辑对全部 Block 重新 `render_block`，再全量写文件。
   修复前 written=N；修复后（内容比较）written=1、unchanged=N−1（B/C 类，已修复）。
4. **latexmk 增量缓存**：修复前未变化文件也被重写 → mtime 全部变化 → latexmk 每次视为
   输入变化而重跑；修复后仅变化文件更新 mtime（C 类，已修复）。
5. **Watchdog 回环**：不成立。`ExternalFileWatcher` 只监视已打开的源码标签文件
   （`tab_manager.watch_path`），Block 生成文件未注册；静态审计无自触发路径（D 类，未发现）。
6. **重复编译入口**：不成立。Block 链仅 `notify_model_changed → request_preview →
   compile_async` 一条；`compile_final` 仅“生成并编译 PDF”按钮。实测每次编辑
   **恰好 1 个 LaTeX PID**（launches 计数与编辑次数一致）（D 类，未发现）。
7. **Undo 深拷贝 / 大表**：`UpdateTableCommand` 整表深拷贝 + `TableEditorModel` 自身快照
   双重拷贝；100×50 深拷贝 17ms、命令 push 25ms；500×50 深拷贝 82ms、命令 205ms
   （C 类，随表格规模显著增长）。
8. **视图全量刷新**：101 Block 时导航刷新 0.24ms、工作区 Block 列表 0.25ms——QListWidget
   全量重建成本可忽略（B 类，非瓶颈）。
9. **Diagnostics / PDF Reload**：编译成功后 Diagnostics 仅解析错误行（~0ms）；`load_pdf`
   调用 0.2–0.3ms（文档加载为异步，未计入渲染）；未做输出哈希去重（C 类候选，量级小）。

## 4. 根因分类

- **A 设计性延迟**：700ms 编译防抖（主导固定等待）。
- **B 必要计算**：XeLaTeX 进程 0.8–1.2s（含 latexmk/xdvipdfmx）；大表渲染。
- **C 可避免重复工作**：全量保存序列化；全量 assemble（修复后仍每次全量渲染，但已移入
  防抖）；修复前全量重写生成文件；大表双份深拷贝。
- **D 真实 Bug**：未发现（无双进程、无 Watchdog 回环、无旧会话回调）。

## 5. 排序根因（前三）

1. **700ms 编译防抖**（设计等待，端到端 ~2–2.7s 中最大固定分量）；
2. **每次编辑同步全量 assemble + 全量重写生成文件**（修复前；已改为防抖内执行 +
   内容比较只写变化文件）；
3. **全量项目 JSON 保存**（随 Block 数线性增长，~20ms@101，量级小，未做增量）。

## 6. 结论

“Block 集成后感觉变慢”的主要构成是 **700ms 编译防抖（设计） + ~1s XeLaTeX（必要） +
~0.3–0.5s 其他**；Block 系统本身在 101 Block 规模仅增加 save+assemble ~55ms/次（修复后
汇编已移出编辑热路径）。不存在双编译进程或 Watchdog 回环等真实 Bug。
