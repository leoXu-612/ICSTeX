# Block 编译管道性能报告

## Conclusion

Block 集成后从“修改到 PDF 更新”的端到端时间约为 **2.0–2.7s**（Small–Large），其中：
**~700ms 是 500/700ms 防抖中的编译防抖（并行计时，设计等待）**，**~0.8–1.2s 是 XeLaTeX
真实进程（必要计算）**，Block 系统自身的保存 + 汇编在 101 Block 规模约 **55ms/次**（修复后
汇编已移出编辑热路径）。不存在双编译进程或 Watchdog 回环。两项可避免的重复工作已修复：
生成文件“内容不变不重写”、汇编延迟到防抖内执行。

## Environment

- Apple M3 / macOS；XeLaTeX（TeX Live 2025）本地编译；offscreen 渲染测量。

## Baseline（见 [审计文档](block-compile-performance-audit.md) 实验矩阵）

- 自动端到端（含防抖）：Small 1974ms / Medium 2485ms / Large 2701ms；
- latex 进程：0.8–1.2s；save：2–24ms；assemble：0.6–35ms；pdf 加载调用：~0.3ms。

## Instrumentation

`app/gui/blocks/profile.py`：`ICSTEX_COMPILE_PROFILE=1` 时输出事务级事件
（MODEL_CHANGED / SAVE_* / COMPILE_* / ASSEMBLE_* / LATEX_PROCESS_* / PDF_RELOAD_*），
含 revision、block_count、files_written/unchanged、bytes、elapsed_ms。生产默认零输出。

## Timeline Breakdown

一次 Text 编辑（Large，101 Block，自动路径）：

```text
编辑 → MODEL_CHANGED (0ms)
     → save 计时器启动 (0ms)，compile 计时器启动 (0ms)  ← 并行
     → SAVE_FINISHED (~20ms，500ms 计时器内)
     → ASSEMBLE_FINISHED (~35ms，700ms 计时器触发时)
     → LATEX_PROCESS_EXITED (~1.15s)
     → PDF_DOCUMENT_LOADED (~0.3ms 调用，渲染异步)
端到端 ≈ 2.7s
```

## Debounce Analysis

- 500ms 与 700ms **并行**（同一模型变化同时启动两个计时器）；理论固定等待 ≈ **700ms**；
- 保存完成不会再次触发 request_preview（无重置循环）；
- 连续编辑会重置 700ms 计时器（标准防抖语义）；一次编辑只有一次 `compile_requested`。

## Save Analysis

- 每次编辑全量序列化并原子重写全部项目文件（无 dirty tracking）；
- save 耗时：11 Block 2.1ms → 51 Block 5.8ms → 101 Block 20.9ms（随 Block 数增长，量级小）。

## Stable LaTeX Generation Analysis

- 每次汇编对全部 Block 重新 `render_block`（101 Block ≈ 35ms，线性）；
- 修复后汇编从“每次编辑同步执行”改为“700ms 防抖内执行一次”，移出编辑热路径。

## Generated File Write Analysis

- **修复前**：每次编辑重写全部生成文件（written=N、unchanged=0）→ mtime 全部变化 →
  latexmk 每次视为输入变化重跑；
- **修复后**：内容比较，仅写变化文件（written=1、unchanged=N−1）；未变化时
  `main.tex`/`.sty`/其他 Block 文件 mtime 不变（回归测试锁定）。

## Compile Process Count

- 每次编辑 `compile_requested` = 1、实际 LaTeX PID = 1（`_compile_launches` 与编辑次数一致，
  基准全项验证）；无第二入口（静态审计：`request_preview` 仅一处调用）。

## Watchdog Analysis

- `ExternalFileWatcher` 只监视已打开的源码标签文件；Block 生成文件未注册 → 无自触发回环
  （静态审计；基准中无 Watchdog 事件）。

## Undo/Table Analysis

- `UpdateTableCommand` 整表深拷贝 + `TableEditorModel` 自快照双重拷贝；
- 100×50 深拷贝 17ms、命令 push 25ms；500×50 深拷贝 82ms、命令 push 205ms
  （C 类；审计上限 100×50 为中等开销，500×50 显著，列为后续优化）。

## GUI Refresh Analysis

- 101 Block 下导航刷新 0.24ms、工作区 Block 列表 0.25ms——全量重建成本可忽略（非瓶颈）。

## Diagnostics/PDF Reload Analysis

- 成功编译后 Diagnostics 仅解析错误行（~0ms）；`load_pdf` 调用 0.2–0.3ms
  （文档加载/首帧渲染异步，未计入）；输出哈希去重未实施（候选，量级小）。

## Ranked Root Causes

1. 700ms 编译防抖（A 类设计等待，端到端最大固定分量）；
2. 每次编辑全量 assemble + 全量重写生成文件（C 类，已修复）；
3. 全量项目 JSON 保存（C 类，随规模增长，量级小）。

## Changes Made

- `app/gui/blocks/profile.py`（新增）：事务级探针，`ICSTEX_COMPILE_PROFILE=1` 开启；
- `app/gui/blocks/project_session.py`：save/assemble/compile 计时与统计；**生成文件
  内容比较（`_write_if_changed`）**；**汇编移入 700ms 防抖**（`_preview_timer` →
  `compile_async`）；`compile_final`/`stop_compile` 取消挂起预览计时器；
- `app/gui/block_mode.py`：PDF 重载计时探针；
- `tools/bench_block_compile.py`（新增）：合成项目基准；
- `tests/test_block_compile_pipeline.py`（新增 4 项）：只写变化文件 / 单进程 / 汇编延迟。

## Before/After Results

| 指标 | 修复前 | 修复后 |
| --- | --- | --- |
| 每次编辑写入生成文件 | N（全部） | 1（仅变化 Block） |
| 未变化文件 mtime | 全部变化 | 不变 |
| 汇编执行时机 | 每次编辑同步 | 防抖内一次 |
| 端到端自动路径 | ~2.0–2.7s | ~2.0–2.7s（防抖+latex 主导，不变） |
| LaTeX PID / 编辑 | 1 | 1 |

## Tests

- 全套件 **663 tests OK**（659 基线 + 4 项新管道回归测试）；
- Stable LaTeX 相同输入字节一致保持（既有测试）；
- 编译失败保留旧 PDF / 会话隔离未受影响（既有测试）。

## Known Limitations

- 大表（500×50）命令仍为整表深拷贝（~205ms），未做差异命令；
- 全量保存序列化未做增量（随 Block 数增长，量级小）；
- PDF 输出哈希去重未实施（`load_pdf` 调用本身 <1ms）；
- 端到端包含 700ms 设计防抖，不可通过“关闭防抖”掩盖（未实施）。

## Git Status

- 分支 `perf/block-compile-pipeline-audit`；按任务要求分阶段提交，未推送。

## Suggested Next Step

1. 大表差异式 Undo 命令（消除双重整表深拷贝）；
2. 项目 dirty tracking（按需保存变化的 Registry/布局部分）；
3. PDF 输出哈希未变时不重载；
4. 在更大真实文档（500+ Block）复测 assemble 与保存增长曲线。
