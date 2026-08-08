# ICSTeX for Windows

版本：2.1.0-beta.1

ICSTeX - ICC Student's TeX - 是一个面向学生的桌面 LaTeX 编辑器，支持实时编译、PDF 预览、项目模板、插图/表格辅助、BibTeX 引用和标签工具。

## 打开 App 前需要安装什么

ICSTeX 不内置 LaTeX 发行版。Windows 用户请先安装 MiKTeX 或 TeX Live：

- MiKTeX: https://miktex.org/download
- TeX Live: https://tug.org/texlive/windows.html

初学者建议安装 MiKTeX，并允许它自动安装缺失 package。运行打包好的 ICSTeX 不需要额外安装 Python 或 PySide6。

## 第一次启动

请先核对文件名中的架构：大多数 Intel/AMD Windows 电脑应使用 `Windows-x64`；
Windows on ARM 设备使用 `Windows-arm64`，二者不能混称为通用包。

如果你拿到的是 `ICSTeX-2.1.0-beta.1-Windows-x64.zip`、
`ICSTeX-2.1.0-beta.1-Windows-arm64.zip` 或对应 latest alias：

1. 先把 zip 解压到一个普通文件夹，例如 Desktop 或 Documents。
2. 打开解压后的 `ICSTeX` 文件夹。
3. 双击 `ICSTeX.exe`。

如果你拿到的是 `ICSTeX-2.1.0-beta.1-Windows-x64-Setup.exe`：

1. 双击安装器。
2. 按提示安装到默认目录。
3. 从 Start Menu 或桌面快捷方式打开 ICSTeX。

当前版本是同学测试版，暂未做代码签名。第一次打开时，Windows 可能会拦一两道，
都是正常现象，按下面处理即可。

**SmartScreen 蓝色提示「Windows 已保护你的电脑 / 未知发布者」：**

1. 点击提示里的「更多信息 / More info」。
2. 点击「仍要运行 / Run anyway」。

**杀毒软件误报（Windows Defender 或第三方杀毒提示有风险、自动隔离/删除）：**

这是 Python 打包程序（PyInstaller）的常见误报，ICSTeX 不联网上传任何文件，是安全的。
如果被误删或拦截：

1. 在杀毒软件的「隔离区 / 病毒和威胁防护历史记录」里找到 ICSTeX，选择「恢复 / 允许」。
2. 或把解压后的 `ICSTeX` 文件夹（或安装目录）加入杀毒软件的「排除项 / 例外」。
3. 如果整个 zip 在下载时就被删，请改用其它浏览器下载，或暂时关闭实时防护后再下载解压。

如仍不放心，可以把诊断报告（工具栏「环境」>「复制诊断报告」）发给维护者确认。

## 如果编译失败

- 确认已经安装 MiKTeX 或 TeX Live。
- 安装 LaTeX 发行版后重启 ICSTeX。
- 点击 ICSTeX 工具栏“环境”，复制诊断报告发给维护者。
- 在 PowerShell 或 Command Prompt 里检查：
  ```bat
  where latexmk
  where pdflatex
  ```
- 如果使用 XeLaTeX 或 LuaLaTeX，检查：
  ```bat
  where xelatex
  where lualatex
  ```
- 确认图片文件仍然存在。
- 查看“错误”面板，排查缺失标签、citation 或 package。

## 如果字数统计和 Overleaf 不一致

- 先看“字数”面板底部的统计模式。
- `texcount 精确统计` 更接近 Overleaf。
- `Python 简化统计` 表示没有找到 `texcount`，或 `texcount` 调用失败。
- 在 PowerShell 或 Command Prompt 里检查：
  ```bat
  where texcount
  ```

## 关于测试版

这个 Windows 包适合发给可信同学或本地测试使用。它还不是正式签名的公开发布版本。
