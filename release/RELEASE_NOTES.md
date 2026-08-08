# ICSTeX 2.1 Beta 1 — Formula Intelligence

## 版本

- 工程版本：`2.1.0-beta.1`
- 发布通道：`beta`
- 平台：macOS Apple Silicon（arm64）与 Windows on ARM（ARM64）Developer Beta
- Git Tag：`v2.1.0-beta.1`

## 摘要

ICSTeX 2.1 introduces a new local-first formula workflow.

You can write formulas through the structured formula editor or import
formula images through the optional local pix2tex runtime. Recognition
results remain editable and are reviewed before being written into the
document.

This release does not require a cloud account or API key. Formula
recognition runs locally after the optional runtime has been installed.

中文：

ICSTeX 2.1 引入了新的本地公式工作流。

用户既可以通过结构化公式编辑器输入数学公式，也可以通过可选的
pix2tex 本地运行时从图片识别公式。所有识别结果都会先进入编辑与
核对流程，确认后才会写入文档。

本版本不依赖云端账户或 API Key。完成可选组件安装后，公式识别可在
离线环境中运行。

## 纳入 2.1 Beta 1

- Formula Editor 2.0（结构化公式编辑器：可视化 + 源码双视图、草稿隔离、单次写回）
- pix2tex 本地公式识别（可选运行时）
- 统一批量图片识别窗口：队列、顺序识别、进度条
- 逐项状态（待识别/识别中/成功/失败/已取消/已精调）、单项重试、查看错误、从批次移除
- ROI 创建、移动、缩放和删除；8 点 ROI 手柄；选中 ROI 单独重识别；ROI 变化防抖重识别
- Formula / LaTeX 双视图同步；aligned 多公式合并
- 重复提交幂等；重复图片指纹去重（可勾选允许重复入队）；对话框打开防抖
- Formula Block 单次写回；Undo / Redo；离线本地运行
- UI Scale 响应式布局；Block 模块与主控制台集成

## 不纳入 2.1 Beta 1

- RapidOCR 文字识别 GUI（入口已禁用，后续 Beta 开放）
- OCR → Text Block 完整提交流程（同上）
- 自动判断文字或公式、整页文档 OCR、表格 OCR、图表识别
- 云端识别、MCP

## 升级与回退

本版本为独立安装包；如需回退，请保留 0.2.7 及更早的安装包与项目备份。

## Windows 制品边界

- `ICSTeX-2.1.0-beta.1-Windows-arm64.zip` 仅用于 Windows on ARM。
- x64 ZIP 与 x64 Setup EXE 尚未生成；ARM64 包不能改名后分发给 Intel/AMD Windows 用户。
- Windows 包未签名，且不内置 MiKTeX 或 TeX Live。

## 安全边界

- 打开项目不再自动编译；首次 Compile 后才在本次会话恢复该项目的自动预览。
- 编译强制忽略项目 `.latexmkrc`、关闭 shell escape，并设置有限超时。
- Magic Root、Block 图片和可移植导出拒绝越界路径与符号链接；公式从受管 AST
  重建，不执行可篡改的缓存文本。
- DOI 与 arXiv 元数据只访问固定 HTTPS 端点，禁止重定向并限制响应大小。
