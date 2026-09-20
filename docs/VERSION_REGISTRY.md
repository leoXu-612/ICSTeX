# ICSTeX 版本注册表（按 2.1 命名规则回填历史版本）

> 规则来源：`app/__init__.py`（单一版本源）+ `release/release-manifest.json`（发布清单）。
> 本文档**不修改任何代码或历史产物**，仅把老版本整理进最新命名体系，便于检索、回溯与机器校验。

## 1. 最新命名规则（自 2.1.0-beta.1 起生效）

| 字段 | 规则 | 当前值（2.1.0-beta.1） |
| --- | --- | --- |
| `PRODUCT_NAME` | 产品名 | `ICSTeX` |
| `PRODUCT_MAJOR` / `PRODUCT_MINOR` | 语义化大版本 / 次版本 | `2` / `1` |
| `VERSION` | 工程版本（可含通道后缀） | `2.1.0-beta.1` |
| `RELEASE_NAME` | 发布代号 | `Formula Intelligence` |
| `RELEASE_CHANNEL` | 发布通道（beta / stable 等） | `beta` |
| Git tag | `v<VERSION>` | `v2.1.0-beta.1` |
| 资产命名 | `ICSTeX-<VERSION>-<platform>-<arch>.<ext>` | `ICSTeX-2.1.0-beta.1-macos-arm64.dmg` |
| 机器可读清单 | `release/release-manifest.json` | schema_version 1 |

## 2. 历史版本回填

老版本**保持原版本号**（0.2.x 不重编号为 2.x，避免伪造历史）；`RELEASE_CHANNEL` 统一回填为
`stable`（0.2 线为正式稳定发布线）；`RELEASE_NAME` 在 2.1 才引入，旧版标注 `—`（未命名）。
历史资产实际名为旧命名（如 `ICSTeX-0.2.7.dmg`），下表“规范资产名”为新规则下的等价命名，仅作对照，不实际改名。

| 版本 | 日期 | 通道 | 发布代号 | Git tag | 规范资产名（对照） | 校验和（有记录者） | 版本要点 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.2.0 | 2026-06-10 | stable | — | 未打（历史） | `ICSTeX-0.2.0-macos-arm64.dmg` | — | App 正式命名 ICSTeX；App 图标与 macOS DMG 测试包；插图/表格/模板/引用/标签辅助 |
| 0.2.1 | 2026-06-12 | stable | — | 未打（历史） | `ICSTeX-0.2.1-macos-arm64.dmg` | — | 环境医生与反馈包优化；Word Count 状态提示；macOS DMG 打包流程优化 |
| 0.2.2 | 2026-06-15 | stable | — | 未打（历史） | `ICSTeX-0.2.2-macos-arm64.dmg` | — | 源码自动换行与开关；多文件项目主文件识别优化 |
| 0.2.3 | 2026-06-30 | stable | — | 未打（历史） | `ICSTeX-0.2.3-macos-arm64.dmg` | — | 一键复制反馈包；Word Count 六类彩色分布条；可视化表格编辑器（tabular 反解析） |
| 0.2.4 | 2026-07-04 | stable | — | 未打（历史） | `ICSTeX-0.2.4-macos-arm64.dmg` / `ICSTeX-0.2.4-Windows.zip` | DMG `f73b9079b2a6cf349af8957eec6e8ebf53a5705e0ba6f4b9ce9e05ad872fcde8` | 浅色工作台重整与品牌强调色；工具栏收敛；Lucide 图标 |
| 0.2.5 | 2026-07-06 | stable | — | 未打（历史） | `ICSTeX-0.2.5-macos-arm64.dmg` | — | 每 root 独立 PDF 新鲜度状态条；标签间导出隔离 |
| 0.2.6 | 2026-07-08 | stable | — | 未打（历史） | `ICSTeX-0.2.6-macos-arm64.dmg` | DMG（45 MB）`8aca1679a3c5ab17379230466b76adb55319ce2353b264f5499a8c4bef2a2a42` | 子文件复用父 root 编译链；另存为编译器残留修复；模板库扩展 |
| 0.2.7 | 2026-07-11 | stable | — | 未打（历史） | `ICSTeX-0.2.7-macos-arm64.dmg` / `ICSTeX-0.2.7-Windows.zip` / `ICSTeX-Source-0.2.7.zip` | DMG `b4ce9f668312aa2e308b3535c66021dce160ac127c886c780cb985b2e7caa7dc`；Source `4a66f4ddabf4b52f86c3c40c12a0a29ba30e9260234b8a413f7a1d91c03fce5d` | Turnitin 风格文本分层预览；Word Count 合并 input/include/subfile |
| 2.1.0-beta.1 | 2026-08-08 | beta | Formula Intelligence | `v2.1.0-beta.1` | `ICSTeX-2.1.0-beta.1-macos-arm64.dmg/.zip`、`ICSTeX-2.1.0-beta.1-Windows-arm64.zip`、`ICSTeX-Source-2.1.0-beta.1.zip` | 见 `release/release-manifest.json` | 公式编辑器 2.0；pix2tex 本地公式识别；批量识别队列与逐项状态；ROI 交互；幂等与防抖；UI Scale；Block 主控制台 |

## 3. 机器可读版本

`release/version-registry.json` 按 `release-manifest.json` 的字段风格收录上述全部版本，供工具
（如 `tools/verify_release_consistency.py` 的扩展）直接消费。

## 4. 备注

- 0.2.0–0.2.7 在既有 git 仓库中**没有版本标签**（本仓库首个标签为 `ocr-interaction-freeze-20260808`，
  版本标签自 `v2.1.0-beta.1` 开始）；如需补打 `v0.2.x` 历史标签，请在确认对应提交后另行操作。
- 历史产物未按新规则改名（遵循“不得把旧产物改名冒充新版本”的发布纪律），仅在此登记规范名。
- Windows 0.2.x 的 ZIP/Setup 为“待 Windows 本机构建验证”状态；2.1.0-beta.1 的 Windows ARM64 为
  developer-beta（见 `release-manifest.json` 的 limitations）。
