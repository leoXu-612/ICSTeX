# ICSTeX 本地识别（2.1）工单完成后的调整与变动报告

> 范围：自上次完成工单（commit `36d7a3a`，2.1 方案 Phase 0-6 交付）之后，本分支上的全部调整与变动。

## 1. 报告范围

- 边界提交：`36d7a3a`（2026-08-08，`feat(ocr): local recognition runtime (pix2tex + RapidOCR) core`）
- 区间：`36d7a3a..HEAD`，共 **6 个提交**，全部位于分支 `feature/local-recognition-runtime`
- 净变更：**8 个文件，+856 / -135 行**
- 同步状态：全部提交仅存在于本地仓库，**未推送**（遵循 GitHub Actions 额度受限期间的约定）
- 测试演进：工单完成时 685 tests OK → 报告时点 **698 tests OK**

## 2. 提交总览

| 提交 | 类型 | 主题 |
| --- | --- | --- |
| `dd3204d` | feat | ROI 交互重构：创建/移动/删除解耦 |
| `e390623` | fix | aligned 种子修复、8 点 ROI 手柄、自动+手动重识别、拆分清空拆分 |
| `1f866cd` | feat | 统一批量图片识别窗口（队列 + 进度条 + 可滚动 ROI 行） |
| `63bc115` | fix | 防护 ROI 点击/重入，修复批量结果无法插入编辑器 |
| `2e9b3b7` | fix | 提交事件幂等 + 队列图片去重，重复事件只输出一次 |
| `d1d165b` | fix | 对话框打开事件防抖，重复点击只打开一次窗口 |

## 3. 各阶段调整详情

### 3.1 ROI 交互重构（`dd3204d`）

- 交互语义解耦：**Shift + 拖拽新建 ROI**；**直接拖拽移动**；**点击选中**；**Delete/Backspace 删除**；普通点击不再误建框。
- 拖动与缩放手柄分离，避免“拖拽=新建”的误操作。
- 新增 ROI 画布测试（添加/清除/选中/删除/手柄命中），全套件 690 tests OK（该阶段后为 688→690 区间内的增量修正）。

### 3.2 精调窗口与公式种子修复（`e390623`）

- **aligned 种子修复**：识别结果（`\begin{aligned}...`）写入编辑区时，原先会被源码模式切换的回调用旧源码重新解析覆盖；新增 `_seed_editor_latex`，同时写入源码编辑区与可视化编辑区，并在切换模式时屏蔽信号，保证识别内容真正出现在编辑器。
- **8 点 ROI 手柄**：4 角 + 4 边中点，支持单轴（上下/左右）缩放，替代原 4 角双自由度拖拽。
- **自动 + 人工重识别**：ROI 变化后 500ms 防抖自动重识别；新增“识别选中 ROI”按钮，只识别当前选中框。
- **“清空”拆分**：拆为“清空 ROI”（删框）与“清空识别内容”（清结果文本），互不干扰。
- 新增 2 项测试（`test_roi_canvas_edge_handles`、`test_dialog_manual_recognize_selected`）；全套件 688 tests OK。

### 3.3 统一批量图片识别窗口（`1f866cd`）

- **单一入口**：公式编辑器的“图片识别…”按钮统一打开批量识别窗口，替换原先分散的单图识别入口。
- **识别队列**：支持“添加图片…/从剪贴板添加/移除选中/清空队列”，队列项以列表呈现。
- **顺序识别 + 进度条**：逐张识别、进度可视化、可取消；多行图片自动合并为 `aligned` 块。
- **结果核对区**：合并后的 LaTeX 可在右侧文本区直接编辑。
- **“精调当前（逐行/ROI）”**：对选中图片打开逐行识别窗口做 ROI 级精调，精调结果回填队列结果。
- **“插入到编辑器”**：接受后把合并 LaTeX 写回公式对话框并刷新可视化编辑区。
- 逐行结果区改为可滚动（ROI 多时按钮与结果不丢失）。

### 3.4 插入链路修复（`63bc115`）

- **日志定位的两处异常**：
  - `roi_canvas.py`：普通点击/轻拖时 `mouseReleaseEvent` 读取不存在的 `drag["current"]`，抛 `KeyError`，导致画布每次点击都异常。
  - `multi_line_dialog.py`：识别循环遍历 ROI 数量，但识别期间 ROI 被自动重识别计时器/删除操作修改，索引越界抛 `IndexError`，中断整批识别。
  - 二者叠加使模态会话提前退出（`modalSession has been exited prematurely`），批量识别结果为空，最终“插入到编辑器”无内容可插。
- **修复**：拖动分支容错（回退到起始矩形）并校验索引；`_recognizing` 重入锁 + ROI 快照；批量识别单张失败不中断队列、`finally` 复位状态。

### 3.5 提交事件幂等与队列去重（`2e9b3b7`）

- **提交幂等**：四处提交入口（公式对话框“应用”/键盘 Apply、批量“插入到编辑器”、“应用为 aligned”、“应用候选公式”）加 `_submitted` 一次性锁，第二次提交事件直接忽略，不会重复写入编辑器；公式对话框应用后禁用确认按钮。
- **输入去重**：批量队列按图片内容指纹（SHA-256）跳过重复图片，状态栏提示“已跳过重复图片”；移除队列项后指纹重建，允许重新添加。
- **顺带修复既有崩溃**：`_remove_selected` 误用 `QListWidgetItem.row()`（Qt 无此方法），改为 `QListWidget.row(item)`。
- 新增 6 项测试；全套件 696 tests OK。

### 3.6 对话框打开事件防抖（`d1d165b`）

- 用户复测发现：连点“精调当前”或“图片识别…”，关闭一个窗口后第二个窗口会排队弹出。
- **修复**：两个打开入口均加重入锁 + 400ms 防抖时间戳，窗口打开期间按钮禁用；排队中的第二次点击事件被时间戳防护吸收，不再弹出第二个窗口。
- 顺带修正：识别运行中再点“开始识别”不再弹“请先添加图片。”的误导提示，改为静默忽略。
- 新增 2 项防抖测试；全套件 **698 tests OK**。

## 4. 用户可见行为变化（汇总）

| 维度 | 工单完成时 | 报告时点 |
| --- | --- | --- |
| 识别入口 | 分散的单图/多图入口 | 统一的“图片识别…”批量窗口（队列+进度条） |
| ROI 交互 | 点击即建框、4 角缩放 | Shift 新建 / 拖拽移动 / 8 点手柄 / Delete 删除 |
| 重识别 | 手动整窗重识别 | ROI 变化自动重识别 + “识别选中 ROI” |
| 识别结果落库 | aligned 结果可能被源码切换覆盖 | `_seed_editor_latex` 保证可视化区与源码区同步 |
| 重复提交 | 连点可能重复插入/重复弹窗 | 提交幂等 + 打开防抖 + 队列去重 |
| 测试规模 | 685 tests OK | 698 tests OK |

## 5. 测试与质量门禁

- 每阶段提交前均执行 `compileall` + 定向测试 + 全套件回归：
  - 685（工单完成）→ 688 → 690 → 696 → **698 tests OK**（最近一次全套件 109s）。
- 新增测试覆盖：ROI 手柄命中、重复图片去重、移除后重加、提交幂等（底层 accept 只执行一次）、打开防抖（快速连点只创建 1 个对话框）、OCR 对话框冒烟。
- 未推送、未跑远端 CI（遵守额度受限约定）。

## 6. 已知限制与后续建议

- 内容指纹去重会把“两张完全相同的图片”视为重复跳过；如需保留可加“允许重复”开关。
- 打开防抖窗口固定 400ms；如觉得过短/过长可提取为配置常量。
- 批量识别中单张失败目前静默跳过，无逐张失败提示；建议增加逐项失败标记与重试入口。
- RapidOCR 文字识别仅完成运行时框架接入，GUI/Text Block 提交流程属后续阶段。
- 远端推送与 GitHub Actions 待额度恢复后执行。

## 7. 提交清单（完整哈希）

```text
d1d165b9f1ea2346e21633d994c3bada7cfe3fed fix(ocr): debounce dialog open events so repeated clicks open once
2e9b3b7f6f50f2fbf200fd5eb0b7ac15fc0be7eb fix(ocr): idempotent submit and dedupe queue so repeated events emit once
63bc115e1ea79cb1d69e2f778e9167cf63ed7304 fix(ocr): guard ROI click/reentry so batch insert reaches editor
1f866cd2b48cd3b716b2a2328254f09556db1805 feat(ocr): unified batch image recognition window with scrollable ROI lines
e390623f37bf4ba77024c14f11f12720f323925a fix(ocr): aligned seed, 8-point ROI handles, auto+manual re-recognize, split clears
dd3204dc0e81794aa035390f55e850783b561195 feat(ocr): smoother ROI interaction with decoupled create/move/delete
```
