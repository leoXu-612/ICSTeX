# pix2tex 本地兼容性 Spike 报告（Phase 6，已完成）

## 1. 结论（Go）

pix2tex==0.1.4 已在隔离 venv（Python 3.11.15）真实安装并完成离线推理验证：模型可下载、
CPU 推理稳定、固定低温度下重复输出一致、主应用零依赖。**Go 条件满足**，可放行真实模型
集成；验收前需补充真实公式图片集上的准确率基准（不在本 Spike 范围）。

## 2. 环境

| 项 | 值 |
| --- | --- |
| 平台 | macOS / Apple M3 / CPU |
| 解释器 | Homebrew Python 3.11.15（venv 隔离） |
| 上游 | pix2tex 0.1.4（PyPI，仅基础包，无 `[gui]/[api]`） |

## 3. 安装

- 方式：`python -m venv` + `pip install --index-url https://pypi.org/simple
  --use-deprecated=legacy-resolver pix2tex==0.1.4`；
- 耗时：约 70s；venv 体积 **1.2GB**（torch 2.13、transformers 5.14.1、opencv-headless、
  albumentations 1.4.24、timm 0.5.4、x-transformers 等）；
- 冲突修正：`tokenizers==0.23.0` 不存在于索引（transformers 要求 ≤0.23.0），改钉
  `tokenizers==0.22.2` 后导入通过；
- **先前卡顿根因**：本机 pip 配置为阿里云镜像（mirrors.aliyun.com）持续超时；
  改用官方 PyPI 后解析/下载正常。

## 4. 模型

| 文件 | 大小 |
| --- | ---: |
| weights.pth | 97MB |
| image_resizer.pth | 19MB |

下载到包内 `pix2tex/model/checkpoints/`；`LatexOCR()` 构造时若缺失会调用
`download_checkpoints()`（安装流程显式执行，运行时不再联网）。

## 5. 性能（CPU）

| 指标 | 数值 |
| --- | ---: |
| 模型加载（冷） | 423–448 ms |
| 热推理（单图） | 132–142 ms |
| 峰值 RSS（加载后） | ~670 MB |
| 峰值 RSS（推理后） | ~690 MB |

## 6. 一致性与 API 实测

- 固定 `temperature=0.01`：同一输入 **5/5 输出一致**（确定性达成）；
- 上游 API 实测：`LatexOCR(arguments=Munch(...))`（非关键字参数），`model()` 接收
  **图像对象**而非路径；`checkpoint/config` 为包内相对路径。

## 7. 对框架的修正（随 Spike 提交）

- `worker_entry.py`：改为 Munch 构造 + PIL 加载图像后调用；禁剪贴板副作用保持；
- `installer.download_models()`：在 venv 内执行 `LatexOCR()` 显式下载并写 manifest
  （指向包内绝对路径）；
- `manifest.py`：必需文件 = checkpoint / image_resizer / config。
