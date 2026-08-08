# RapidOCR Review → Text Block 流程报告

> 目标：独立于公式 OCR，新增“图片 → RapidOCR 文字识别 → 人工复核 → 创建 Text Block”的完整流程。

## 1. 组件结构（独立模块）

```
app/gui/text_ocr/
  __init__.py            # 包声明（与公式 OCR 无依赖）
  text_ocr_manager.py    # TextOcrManager：RapidOCR worker 生命周期 + 请求路由
  text_review_dialog.py  # TextReviewDialog：图片预览 + 可编辑识别文字 + 置信度摘要
  text_block_flow.py     # 入口：选图 → wait_text → 复核 → controller.add_block
```

入口 UI：Block 导航面板（主控制台左侧）“新建 Block”旁新增 **“文字识别…”** 按钮。

## 2. 数据流

```text
用户点击“文字识别…”
  → TextOcrManager（懒创建，挂 QApplication）
  → RecognitionWorkerClient（QProcess：python -m app.services.recognition.worker_entry --kind text）
  → RapidOCR 子进程推理 → JSONL 结果（text + regions + confidence）
  → TextReviewDialog 人工复核/编辑
  → 确认后 controller.add_block("text", alias, content_for_text(...))
  → QUndoCommand（AddBlockCommand）→ ProjectSession 统一保存/预览链
```

## 3. 关键行为

- **独立运行时**：复用 2.1 已建成的 generic worker 与 `provider_python("rapidocr")`（支持 `ICSTEX_RAPIDOCR_ENV` 覆盖），不触碰公式 OCR 的任何交互代码（保持冻结基线）。
- **幂等提交**：`TextReviewDialog.accept` 带 `_submitted` 锁，连点不会创建两个 Block。
- **空内容保护**：未识别到文字/用户清空后确认，均不创建 Block 并提示。
- **失败可见**：识别失败/超时给出明确提示；Block 创建走既有 Undo 命令，可撤销。
- **区块内容**：`content_for_text`（`{"format": "plain", "text": ...}`），alias 取首行前 20 字符。

## 4. 测试

新增 `tests/test_text_ocr.py`（5 项）：

- 复核对话框 accept 幂等（底层 QDialog.accept 只执行一次）；
- result_text 返回编辑后的文本；
- TextOcrManager 未安装时状态与 failed 信号；
- 完整流程：模拟识别成功 → 确认 → `add_block("text", ...)` 被调用且内容正确；
- get_manager 应用级单例。

全套件 **706 tests OK**（前值 698，新增 8 项：批量状态 3 + 文本 OCR 5）。

## 5. 已知限制与后续

- 需 RapidOCR 运行环境：启动应用时设置 `ICSTEX_RAPIDOCR_ENV=/tmp/rapidocr_spike.8cQ77a/venv`（或先安装）；未安装时按钮会提示。
- 当前仅“添加图片文件”入口；剪贴板入口与 ROI 区域选择（类似公式精调）留待后续。
- 无自动排版/标题推断；识别文本以纯文本 Block 落库，由用户后续编辑。
