# ICSTeX 公式 OCR 交互代码独立审计报告

> 审计对象：`36d7a3a..HEAD` 六个提交（`dd3204d` / `e390623` / `1f866cd` / `63bc115` / `2e9b3b7` / `d1d165b`）
> 基线：`ocr-interaction-freeze-20260808`（冻结 tag，指向 `39f6bf7`）
> 审计方式：逐提交 diff 审查 + 运行时复现验证 + 全套件回归（**698 tests OK**）

## 1. 结论摘要

六个提交的交互目标（ROI 解耦、8 点手柄、自动/手动重识别、统一批量窗口、插入链路修复、提交幂等、打开防抖）均已实现并有测试覆盖，未发现破坏性操作或用户文档数据丢失风险。审计发现 **1 个中危数据正确性缺陷**（精调后合并结果重复拼接）与 4 个低危设计问题，另有 1 处提交说明与代码不符。

## 2. 发现清单

### F1 [中] 精调某一行后，合并 LaTeX 结果重复拼接（`1f866cd` 引入）

- **证据**：`_start` 中 `self._results[index] = "\n\n".join(blocks)` 保存的是“到该行为止的累计 blocks”；`_fine_tune_current` 成功后调用 `_refresh_result_text()`，它按行号重建 `parts`，于是第 1 行结果含 block0，第 2 行含 block0+block1，第 3 行含 block0+block1+block2，最终拼接出现 block0×3、block1×2。
- **复现**（offscreen 脚本，3 张不同图片）：精调第 0 行后结果为 `refined0 | block0 | block1 | block0 | block1 | block2`。
- **影响**：精调过任何一行后，“插入到编辑器”的 LaTeX 会重复。
- **修复方向**：每行保存独立结果，刷新时只按行序拼接单项结果（本次“逐项状态”改造将一并修复）。

### F2 [中] `_wait_ocr` 对全局完成信号过于敏感

- `multi_line_dialog._wait_ocr` 里 `manager.recognition_finished.connect(loop.quit)` 监听的是 manager 上的全局信号；若同一 manager 有其他会话的请求先完成（如公式对话框自身的识别、或并发精调），当前等待循环会被提前退出并误判为失败/超时。
- 建议按 `request_id` 过滤后再退出，或仅用 `recognition_failed` + 超时计时器退出。

### F3 [低] 纯点击选中也会触发 500ms 自动重识别

- `roi_canvas.mouseReleaseEvent` 在 move/resize 分支无条件 `rois_changed.emit()`，即使矩形未变化；`e390623` 又把 `rois_changed` 接到自动重识别计时器。纯点击选中会触发一次全量重识别。
- 建议仅在矩形实际变化时 emit，或在画布记录“无变化则不 emit”。

### F4 [低] 跨类访问私有属性

- `multi_line_dialog._recognize_selected` 读取 `self.canvas._selected`，属于跨类依赖私有名；建议 `RoiCanvas` 提供 `selected_index()` 公开方法。

### F5 [低] 结果双源与手改覆盖提示缺失

- `combined_latex()` 优先返回 `result_edit` 手改文本，但再次 `_start` 会覆盖手改内容且无提示；行为合理但缺提示，建议在重识别前提示或保留手改版本。

### F6 [低] 提交说明与代码不符

- `e390623` 提交说明写“3 new tests / full suite 688 tests OK”，实际新增 2 个测试方法（`test_roi_canvas_edge_handles`、`test_dialog_manual_recognize_selected`），686+2=688 计数正确，但“3 new”描述不符。
- 测试规模轨迹：685 → 686 → 688 → 690 → 690 → 696 → **698**（与各提交说明一致，最终全套件实测通过）。

## 3. 通过项（未发现问题）

- `63bc115` 修复的 ROI 点击 `KeyError` 与识别重入 `IndexError` 已由新增测试覆盖（点击不再抛异常、识别期间 ROI 变动不再越界）。
- `2e9b3b7` 的提交幂等（4 处 `_submitted` 一次性锁）与队列图片指纹去重实现正确；`_remove_selected` 的 `QListWidgetItem.row` 崩溃已修复为 `QListWidget.row(item)`。
- `d1d165b` 的打开防抖（`_ocr_open`/`_fine_tune_open` + 400ms）正确；防抖常量待提取为命名常量（见工单 #6）。
- 全部对话框遵循“草稿 → 编辑计划 → 单次写回”流程；写回路径有 revision guard，未发现覆盖用户文档的风险。

## 4. 后续动作关联

- F1 由“批量队列逐项状态与单项重试”工单修复（每行独立结果）。
- F2、F3、F4 列入后续改进建议；F5 在批量重识别改造中一并处理。
- F6 仅文档修正。
