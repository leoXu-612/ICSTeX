# ICSTeX 2.1.0-beta.1 安装说明

## macOS Apple Silicon

### 1. 安装 ICSTeX

1. 下载 `ICSTeX-2.1.0-beta.1-macos-arm64.dmg`（或同名 `.zip`）。
2. 双击 DMG，将 `ICSTeX.app` 拖入“应用程序”文件夹。
3. 首次启动：若出现“无法验证开发者”提示，右键（或按住 Control 点击）图标 → “打开” → 确认；
   或前往 系统设置 → 隐私与安全性 → “仍要打开”。

### 2. LaTeX 环境（必需）

ICSTeX 不内置 LaTeX 发行版。请先安装：

- MacTeX（推荐）或 BasicTeX：https://tug.org/mactex/

安装后确认 `xelatex` / `pdflatex` 可用。

### 3. 可选：本地公式识别（pix2tex）

公式识别为可选本地组件，安装包默认不包含：

1. 打开 ICSTeX → 设置 → 可选工具 → 公式识别 (pix2tex)。
2. 点击“安装”（首次安装约需数分钟，包含 Python 3.11 虚拟环境与模型下载，占用约 1.2 GB）。
3. 安装完成后状态显示为可用；打开公式编辑器 → “图片识别…” 即可使用。

卸载：在设置中点击“移除”即可删除对应运行环境。

> 开发者提示：运行环境路径可用环境变量覆盖，例如
> `ICSTEX_PIX2TEX_ENV=/path/to/pix2tex/venv`、`ICSTEX_RAPIDOCR_ENV=/path/to/rapidocr/venv`。

### 4. 验证安装

- 打开示例项目：`release/demo/Formula-Intelligence-Demo.zip`（解压后用 ICSTeX 打开 `main.tex`）。
- 在公式编辑器输入 `\frac{a}{b}` 或使用“图片识别…”导入公式图片，确认可编译并生成 PDF。

## Windows on ARM（ARM64 Developer Beta）

1. 下载 `ICSTeX-2.1.0-beta.1-Windows-arm64.zip` 并解压到普通本地目录。
2. 双击解压目录中的 `ICSTeX.exe`；运行应用不需要安装 Python。
3. 安装 MiKTeX 或 TeX Live，重启 ICSTeX 后在“环境医生”检查 `latexmk`、
   `pdflatex` 和 `texcount`。
4. Windows SmartScreen 可能提示未知发布者；本 Beta 未做代码签名。

此 ARM64 ZIP 不适用于常见 Intel/AMD x64 Windows 电脑。x64 ZIP 与 x64 Setup EXE
必须在 x64 Windows-local 构建环境另行生成，不能通过改名 ARM64 制品替代。
