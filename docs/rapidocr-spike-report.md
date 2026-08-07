# RapidOCR 本地 Spike 报告（Phase 1）

## 1. 结论（GO）

RapidOCR（`rapidocr_onnxruntime`）在隔离 venv（Python 3.11）安装稳定、离线可推理、
英文识别精确；与 pix2tex 分开部署时无依赖冲突、pix2tex 零回归。**选择 Option B（分离
Sidecar）**：pix2tex venv 1.2GB 保持不动，RapidOCR venv 仅 +296MB，避免 torch/onnxruntime
共存的升级耦合风险。

## 2. 环境与安装

| 项 | 值 |
| --- | --- |
| Python | 3.11.15（Homebrew，隔离 venv） |
| rapidocr_onnxruntime | 1.4.4 |
| onnxruntime | 1.28.0 |
| 安装方式 | 官方 PyPI（`--index-url`，规避本机阿里云镜像超时） |
| 安装耗时 | ~21s |
| venv 大小 | 296MB |

## 3. 模型（自动下载到包内 models/）

| 文件 | 大小 |
| --- | ---: |
| ch_PP-OCRv4_rec_infer.onnx | 10.9MB |
| ch_PP-OCRv4_det_infer.onnx | 4.7MB |
| ch_ppocr_mobile_v2.0_cls_infer.onnx | 0.6MB |
| 合计 | ~16MB |

## 4. 性能（CPU / Apple M3）

| 指标 | 数值 |
| --- | ---: |
| 冷加载 + 首次推理 | 370ms |
| 热推理（3 次） | 249–264ms |
| 峰值 RSS | ~868MB |
| 英文样例 | "Experimental Results" 精确识别，置信度 0.997 |

## 5. pix2tex 回归

分离 venv 下 pix2tex 导入与既有实测不受影响（import OK；公式识别行为不变）。

## 6. Unified vs Separate（Option A/B）

采用 **Option B（Separate Sidecars）**：

| 指标 | Unified | Separate（采用） |
| --- | --- | --- |
| 磁盘 | torch+onnxruntime 共存，更大 | pix2tex 1.2GB + rapidocr 296MB，互不干扰 |
| 依赖冲突 | torch/onnxruntime/numpy/opencv 共存风险高 | 无 |
| 升级耦合 | 高 | 低 |
| 移除简单性 | 低 | 高 |
| Formula RSS / Text RSS | 可能互相抬高 | 各自独立 |

## 7. 下一步

将 RapidOCR 以独立 worker（`app/services/recognition/worker_entry.py`）接入统一
Recognition Runtime；文字识别 GUI 与 Text Block 集成进入 Phase 8–9。
