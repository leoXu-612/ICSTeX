# ICSTeX 2.1.0-beta.2 安装说明

本次提供 macOS Apple Silicon（arm64）手动安装包，与已核验的本机测试版对应。
应用内自动更新尚未启用；下载新版后需要自行安装。

## 安装与升级

1. 下载 `ICSTeX-2.1.0-beta.2-macos-arm64.dmg`，或同名 ZIP。
2. 已安装旧版时，先保存文档并退出全部 ICSTeX 窗口，保留旧应用和项目备份。
3. 打开 DMG，把 `ICSTeX.app` 拖入“应用程序”文件夹；ZIP 用户先完整解压。
4. 本包使用 ad-hoc 签名，未经 Apple 公证。若 macOS 阻止首次打开，请在
   “系统设置 → 隐私与安全性”中查看并亲自确认。不要关闭系统安全保护。
5. 启动后打开“帮助 → 环境医生”，确认本机 LaTeX 工具链可用。

应用不包含 MacTeX、TeX Live、MiKTeX、pix2tex 模型或独立 OCR 运行环境。
运行应用不需要另外安装 Python；编译 LaTeX 仍需自行安装本地 LaTeX 发行版。

## 常用入口

- 编译器：macOS 顶部菜单“编译 → 编译器”，选择 Auto、pdfLaTeX、XeLaTeX 或 LuaLaTeX。
- 控制台：工具栏“控制台”，查看日志、错误、字数及检查信息。
- 项目支持：“帮助 → 在 GitHub 支持项目（Star）”，自愿打开仓库页面。

## 校验与恢复

下载文件的 SHA-256 见 `SHA256SUMS.txt`；构建身份和范围见 `BUILD_RECEIPT.json`。
如需恢复旧版，先退出应用，再使用保留的旧安装包。应用可重装不代表文稿可以回滚，
请另行保留项目备份。

## Windows

本次没有 Windows Beta 2 安装包。旧 Windows ARM64 Developer Beta 仍保留在
GitHub 的历史 Release 中；它不能用于 Intel/AMD x64 Windows。
