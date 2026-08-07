# pix2tex 本地兼容性 Spike 报告（Phase 6）

## 1. 结论

本机（macOS，Apple Silicon）**仅有 Python 3.12**；pix2tex==0.1.4 的依赖解析在
**有界 4 分钟内未完成**（dry-run 被中断，无解析结果），因此**未执行真实安装、模型下载与
推理测量**。按工单 No-Go 条款“pix2tex 无法在目标环境稳定安装/验证”，真实模型接入在本
环境**暂缓（Go 条件未满足）**；Sidecar 框架已实现并以 Fake Worker 全量测试，可在具备
Python 3.10/3.11 与网络的机器上按 5.2 步骤复测后放行。

## 2. 环境

| 项 | 值 |
| --- | --- |
| 平台 | macOS / Apple M3 |
| 可用解释器 | Python 3.12.6（无 3.10/3.11） |
| 上游版本 | pix2tex 0.1.4（PyPI 已确认存在） |

## 3. 已完成

- PyPI 版本确认：`pip index versions pix2tex` → 0.1.4 可用；
- 隔离 venv 创建成功（`python3 -m venv`）；
- `pip install --dry-run pix2tex==0.1.4`：**4 分钟内无解析结果（中断）**。

## 4. 未完成与原因

| 项 | 状态 | 原因 |
| --- | --- | --- |
| 依赖解析（3.12） | 未完成 | 有界时间窗内无结果，疑似旧版本 pin 与 3.12 生态冲突或网络慢 |
| 真实安装 | 未执行 | 依赖未解析；PyTorch 等体积大 |
| 模型下载/离线推理 | 未执行 | 权重 CC BY-NC-SA，且安装未完成 |
| 冷启动/热推理/内存 | 未测量 | 依赖安装未完成 |
| 同图重复一致性 | 未测量 | 同上 |

## 5. 下一步（维护者机器）

1. 安装 Python 3.10/3.11 并 `python -m venv`；
2. `pip install pix2tex==0.1.4`（禁止 `[gui]`/`[api]`），生成
   `packaging/optional/pix2tex/requirements.lock`；
3. 用 `app.optional_tools.pix2tex.installer.download_models` 下载权重并生成
   `model-manifest.json`；
4. 记录安装/模型大小、冷启动、热推理、峰值 RSS、重复一致性；
5. 通过后放行真实模型集成（Go 条件见工单 §5.4）。

## 6. 框架现状（已交付、可独立验收）

- `app/optional_tools/pix2tex/`：protocol / environment / manifest / installer /
  installer_cli / worker_entry（pix2tex 延迟导入、禁剪贴板副作用、禁静默下载）/
  client（QProcess JSONL，状态机+超时+取消）/ manager（生命周期、会话路由）；
- `tests/test_formula_ocr.py`：sanitizer / protocol / client（Fake Worker 的
  ready→recognize→result→shutdown、crash、load_fail）/ review 共 10 项全绿；
- GUI 从不 import pix2tex；核心 requirements 无新增。
