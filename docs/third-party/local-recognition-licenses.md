# 本地识别组件许可审计

> 本文件不是法律意见；正式分发前必须进行模型资产再分发确认。

| 组件 | 代码许可 | 模型许可 | 备注 |
| --- | --- | --- | --- |
| pix2tex (LaTeX-OCR) | MIT | CC BY-NC-SA | 模型权重非商业 |
| RapidOCR (rapidocr_onnxruntime) | Apache-2.0 | Apache-2.0 | PP-OCR 模型 Apache-2.0 |
| ONNX Runtime | MIT | – | 运行时 |
| PyTorch | BSD-3-Clause | – | 运行时 |
| OpenCV | Apache-2.0 | – | 运行时 |

策略：所有识别组件均为**用户明确安装**的可选本地工具；核心安装包不捆绑任何模型；
导出包/项目不含模型；安装前展示体积与许可说明。商业化分发前必须确认 CC BY-NC-SA
权重与再分发条件。
