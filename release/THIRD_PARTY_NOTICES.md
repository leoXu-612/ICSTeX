# Third-Party Notices

## Lucide Icons

ICSTeX bundles a small modified-color subset of the
[Lucide](https://github.com/lucide-icons/lucide) SVG icon set.

Lucide is licensed under the ISC License. Some icons are derived from Feather
Icons under the MIT License. The complete notices bundled with the application
are stored at `app/assets/licenses/LUCIDE_LICENSE.txt`.

## pix2tex（可选本地公式识别运行时）

ICSTeX 2.1 的可选公式识别组件基于 [pix2tex](https://github.com/lukas-blecher/LaTeX-OCR)
（代码仓库：`lukas-blecher/LaTeX-OCR`）。

- pix2tex 代码版本：`0.1.4`
- pix2tex 代码许可证：MIT License
- 模型权重文件：`weights.pth`
- 模型权重许可证：**CC BY-NC-SA 4.0**（官方发布说明标记；非商业使用，见
  https://github.com/lukas-blecher/LaTeX-OCR/releases ）
- 模型权重 SHA-256：`a63d9141c53d266cb682fb5a8bd83bd5cbe283145e0e78ebdc0f895195a1dfaa`

### 主要运行依赖（pix2tex 虚拟环境内）

- Python 3.11
- PyTorch（实测 `torch 2.13.0`，其自身依赖遵循各自许可证）
- transformers、munch、PIL 等（安装时由 pip 解析，许可证见各包）

### 分发方式

- 应用安装包**不包含** pix2tex 代码、模型权重或 PyTorch 运行库。
- 用户在设置中主动安装“本地公式识别”后，由 Installer 按官方 PyPI 下载代码，
  并按官方发布说明下载模型权重；模型清单（版本与路径）保存在
  `~/Library/Application Support/ICSTeX/optional-tools/pix2tex/models/model-manifest.json`。
- RapidOCR（`rapidocr_onnxruntime`）为可选文字识别运行时，同样不由安装包分发，仅在用户主动安装后使用。
