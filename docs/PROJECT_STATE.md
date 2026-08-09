# ICSTeX Project State

更新时间：2026-08-09（Asia/Taipei）

本文件是当前已验证状态的权威来源；历史证据写入 `PROJECT_LOG.md`，未来计划写入
`docs/ROADMAP.md`，长期约束写入 `docs/DECISION_LOG.md`。

## Product and Source State

- 权威工作区：本仓库根目录；当前 Git 分支 `release/2.1`。
- 当前版本：`2.1.0-beta.1`；版本来源为 `app/__init__.py`。
- 技术栈：Python 3.11+、PySide6、本机 LaTeX distribution、PyInstaller。
- 产品边界：中文优先、本地文件与本地编译优先、不静默上传用户内容、不捆绑
  MacTeX、TeX Live 或 MiKTeX。
- `v2.1.0-beta.1` 已作为公开 GitHub prerelease 发布；`release/2.1` 包含后续网站
  发布态元数据提交，版本制品仍由该标签固定。
- 公开发布候选已加入默认拒绝的本地执行边界；旧安装包早于该修复，必须重建。

## Verified Capabilities

- Source/PDF 双栏、root-scoped 编译与 freshness、SyncTeX、Word Count、诊断、
  原子保存和正式 PDF 导出。
- 隔离的快速图片预览与原图正式构建链；preview 不得成为正式导出源。
- Block 项目控制台、ProjectSession、统一 Undo/保存/编译、表格与布局 Block。
- Formula Editor 2.0、显式提交、危险 LaTeX 过滤、可选本地 pix2tex 识别与人工复核。
- UI Scale 90/100/110/125/150%、响应式欢迎页、标签栏和 PDF 工具栏。
- RapidOCR 本地运行时和 Text Block 链路保留在源码中，但 2.1 Beta 1 用户入口禁用。

## Verification Baseline

2026-08-08 安全边界修复后的当前源码重新验证：

- `bash packaging/preflight.sh`：通过。
- `python3 -m compileall -q app tests packaging/install_build_dependencies.py`：通过。
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests`：731 tests passed。
- `bash tools/run_mvp_ci.sh`：72 项模块化子集、716 项完整套件与 Demo 构建通过。
- macOS arm64 打包应用冷启动与 Demo source-to-PDF：已验证。

## Release Matrix

| 对象 | 状态 | 说明 |
| --- | --- | --- |
| 当前源码 | Verified, release hardening complete | 2.1.0-beta.1；731 tests passed |
| macOS arm64 DMG/ZIP | Verified, rebuilt | hardened source；ad-hoc signed、未 notarize |
| clean source ZIP | Verified, rebuilt | hardened source；publication hygiene scan passed |
| Windows ARM64 ZIP | Verified beta artifact, rebuilt | Windows-local `C:\w3`；无系统 Python 启动通过 |
| Windows x64 ZIP | Pending | 当前构建机和 Python 均为 ARM64 |
| Windows x64 Setup EXE | Blocked by tools | 需要 x64 构建环境和 Inno Setup |
| Windows TeX acceptance | Blocked by tool | 构建机尚未安装 MiKTeX/TeX Live |
| Static release website | Public Vercel production deployment | `website-phi-beryl-92.vercel.app`；production READY，SSO Protection 已关闭；10 项专项测试通过 |
| GitHub repository / Release | Public / published prerelease | `v2.1.0-beta.1`；9 个资产；公开下载端点已匿名验证为 HTTP 200 |

旧的 `dist/ICSTeX-Windows.zip` 未版本化且早于当前源码，不是 2.1.0-beta.1 制品。

## Architecture and Non-Regression Boundaries

- 纯解析、状态、路径、诊断和文本规则留在 `app/core`；PySide6 编排留在 `app/gui`。
- `MainWindow` 保持兼容门面，通过 focused controllers 和 ProjectSession 渐进演进。
- 保存或编译不得移动光标或滚动位置；同文档 PDF reload 应保持 page/zoom/viewport。
- 编译前 flush 当前内容；失败 build 仅能显式保留 stale PDF。
- build id、source revision 和 normalized compile root 决定结果归属；后台结果不得覆盖
  当前无关标签页。
- PREVIEW 与 FINAL 使用独立路径和状态；正式导出只接受当前 revision 的 FINAL PDF。
- 严格解码与同目录原子替换保护用户文件；相对项目路径优先。
- 缺少 Python 或 LaTeX toolchain 时，打包应用必须仍能无阻塞启动并给出明确诊断。

## Current Risks and Immediate Work

- Windows ARM64 ZIP 已在 Windows-local `C:\w3` 从 hardened source ZIP 重建；
  Python 3.12.10 ARM64，移除系统 Python PATH 后的打包应用启动验收通过。
- Windows x64 ZIP/Setup 仍未生成；不能把 ARM64 包改名或宣称为通用 Windows 包。
- 构建机缺少 Inno Setup，因此 x64 Setup EXE 不能在未补齐构建环境时生成。
- Windows 构建机缺少 MiKTeX/TeX Live，因此不能把 source-to-PDF 记为已验证。
- Git 历史已重写；公开远端的提交信息与可达提交内容扫描均无维护者
  `/Users/leo.xu` 路径，当前源码 tree 在重写前后保持一致。
- GitHub Actions 在发布写入期间临时禁用，推送没有运行 CI；发布完成后恢复原配置。
- macOS 仅验证 Apple Silicon，且未 Developer ID 签名或 notarize。
- 2.1 是 Beta；公式 OCR 结果必须人工检查，重要项目仍需外部版本备份。

公开 Beta 已如实排除 Windows x64/Setup，并保留 Windows ARM64 与 macOS 的既有
限制。后续仍需补齐 Windows x64 构建机、Inno Setup、Windows TeX 验收和 macOS
notarization；在新的 bounded assignment 前不向该 Release 追加产品功能。

## Maintenance Rule

只有验证后的事实才写入本文件。命令、哈希和任务过程追加到 `PROJECT_LOG.md`；
尚未接受的设计保留在 roadmap/decision log，不写成当前能力。
