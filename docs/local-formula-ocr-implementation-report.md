# 本地公式 OCR（pix2tex Sidecar）实施报告

## Conclusion

OCR 以**可选、隔离、纯本地 Sidecar** 接入：核心应用零依赖、GUI 不 import pix2tex、
模型缺失不静默下载、结果必须人工审校后才进入项目；真实模型 Spike 在本环境未完成
（仅 Python 3.12，依赖解析超时），框架已交付并以 Fake Worker 全量测试。

## pix2tex Isolation Strategy

```text
GUI(QProcess) → venv python → worker_entry → LatexOCR(显式路径, no_cuda, 低温度)
JSON Lines 协议；stderr 收第三方日志；剪贴板副作用被禁用；模型文件缺失即 MODEL_MISSING
```

## Dependency Footprint

- 核心 `requirements` 无新增；OCR 仅存在于独立 venv（`pix2tex==0.1.4`，无 `[gui]/[api]`）；
- 模型/环境位于 `AppLocalDataLocation/optional-tools/pix2tex`（运行时解析，无硬编码用户路径）。

## Security Model

- `FormulaLatexSanitizer`：剥包装、拒绝 `\input/\include/\usepackage/\def/\write18` 等、
  拒绝 URL/路径/控制字符/超长/超深；
- 识别开始/完成/校正阶段 0 次保存与编译；仅用户确认后 1 次模型更新；
- 晚到结果按 request_id + session_id 路由，会话关闭即丢弃（框架预留）。

## Performance / Accuracy

- Fake Worker 下：客户端启动→ready→推理→退出流程通过；超时/取消/崩溃路径通过；
- 真实模型（Spike 完成）：加载 423–448ms、热推理 132–142ms（CPU）、峰值 RSS ~670–690MB、
  固定温度 0.01 下 5/5 输出一致；venv 1.2GB、模型 116MB，见
  [pix2tex-local-spike-report.md](pix2tex-local-spike-report.md)；
- 准确率基准（真实公式图片集）尚未建立，属下一步。

## Tests

`tests/test_formula_ocr.py` 10 项：sanitizer、协议、Sidecar 客户端（ready/result/
shutdown、crash、load_fail）、Review 对话框。

## Known Limitations

- 真实模型 Go 已放行（Python 3.11 + 官方 PyPI + legacy resolver）；
- OCR 仅支持单公式图片（文件/剪贴板），无整页/表格识别；
- 未实现截图工具与裁剪 UI（仅预处理白底/灰阶/尺寸上限）。

## Suggested Next Step

建立真实公式图片 fixture 准确率基准；随后补裁剪、最近使用/模板持久化与 UiMetrics 联动。
