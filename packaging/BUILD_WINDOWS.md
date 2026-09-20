# ICSTeX 2.1.0-beta.1 Windows 构建指南

Windows 安装包必须在 Windows 实机或虚拟机中构建，不能在 macOS 上生成后改名。

## 1. 准备

- 将 `ICSTeX-Source-2.1.0-beta.1.zip` 复制到 Windows 并解压。
- 公开 x64 包使用 x64 Python 3.12–3.14；Windows on ARM 测试包使用 ARM64 Python。
  运行 `python -c "import platform; print(platform.machine())"` 核对架构。
- 最终用户不需要 Python；Python 只用于本次打包。
- 源码包已附带 `packaging\wheels\pylatexenc-2.10-py3-none-any.whl`，无法连接 PyPI 时会自动优先使用。

## 2. 复制到 Windows 本地目录

不要直接在 `C:\Mac\...` 共享目录中运行 PyInstaller。在 Command Prompt 中执行，并把第一行路径改成实际解压位置：

```bat
mkdir "%USERPROFILE%\ICSTeX_Build_210b1"
tar -xf "%USERPROFILE%\Downloads\ICSTeX-Source-2.1.0-beta.1.zip" -C "%USERPROFILE%\ICSTeX_Build_210b1"
cd /d "%USERPROFILE%\ICSTeX_Build_210b1\ICSTeX-Source-2.1.0-beta.1"
python --version
call packaging\build_windows.bat
```

不要先在 `C:\Mac\...` 或其他共享目录解压再构建；上述路径从开始就是 Windows-local。

当终端显示 `Build completed successfully.` 时，应生成：

```text
dist\ICSTeX\ICSTeX.exe
dist\ICSTeX-2.1.0-beta.1-Windows-x64.zip
dist\ICSTeX-Windows-x64.zip
```

如已安装 Inno Setup 且 `iscc` 在 PATH 中，还会生成：

```text
dist\ICSTeX-2.1.0-beta.1-Windows-x64-Setup.exe
```

## 3. Windows 验收

### 不依赖系统 Python 启动

新开一个 Command Prompt，临时使用不含 Python 的 PATH，再直接启动打包结果：

```bat
cd /d "%USERPROFILE%\ICSTeX_Build_210b1"
set "PATH=%SystemRoot%\System32;%SystemRoot%"
start "" "dist\ICSTeX\ICSTeX.exe"
```

此时 App 应能打开，但可能暂时提示找不到 LaTeX 工具，这是清空 PATH 测试的预期结果。

### 恢复正常环境

关闭上述 Command Prompt，重新打开一个终端，然后检查：

```bat
where latexmk
where pdflatex
where texcount
```

正常启动 ICSTeX，在“环境医生”中确认 App 版本为 `2.1.0-beta.1`，并能检测 MiKTeX 或 TeX Live。

## 4. 分发前

- x64 用户只发送 `ICSTeX-2.1.0-beta.1-Windows-x64.zip` 或对应 Setup EXE。
- ARM64 测试包命名为 `ICSTeX-2.1.0-beta.1-Windows-arm64.zip`，不得称为通用 Windows 包。
- 保留 `README.txt` 和 `CHANGELOG.md`。
- 当前 Windows 包未做代码签名，SmartScreen 可能提示未知发布者。
