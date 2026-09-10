# ICSTeX for macOS

版本：2.1.0-beta.2

Beta 2 的 macOS arm64 更新通道正在验收；未完成前，公开制品仍为 Beta 1。

ICSTeX - ICC Student's TeX - 是一个面向学生的桌面 LaTeX 编辑器，支持实时编译、PDF 预览、项目模板、插图/表格辅助、BibTeX 引用和标签工具。

## 系统兼容性

当前 2.1.0-beta.1 DMG 为 Apple Silicon `arm64` 版，适用于 M1/M2/M3/M4 等 Mac。
本次未生成 Intel (`x86_64`) 或 Universal 2 安装包，Intel Mac 请不要使用该 DMG。

## 打开 App 前需要安装什么

ICSTeX 不内置 LaTeX 发行版。请先安装 MacTeX：

https://tug.org/mactex/

初学者建议安装完整 MacTeX。BasicTeX 体积更小，但后续可能需要手动补装缺失的 LaTeX package，也可能缺少 Word Count 需要的 `texcount`。

运行打包好的 ICSTeX 不需要额外安装 Python 或 PySide6。

## 第一次启动

请把 `ICSTeX.app` 拖到 Applications 文件夹。

当前版本使用 ad-hoc 签名，尚未使用 Developer ID 签名或进行 Apple notarization。第一次打开时，macOS 会弹出
「无法打开"ICSTeX"，因为无法验证开发者」或「Apple 无法验证此 App 不含恶意软件」。
这是正常现象，不代表 App 有问题，按下面步骤打开一次即可，之后就不再提示。

**步骤（macOS Ventura / Sonoma / Sequoia 通用）：**

1. 双击 `ICSTeX.app`，在弹窗里先点「完成 / Done」（这一步是必须的，先让系统记录这次尝试）。
2. 打开「系统设置 / System Settings」>「隐私与安全性 / Privacy & Security」。
3. 滑到页面底部「安全性 / Security」区域，会看到一行「已阻止"ICSTeX"…」，点右边的
   「仍要打开 / Open Anyway」。
4. 系统再次确认时，输入登录密码或用 Touch ID，然后点「仍要打开 / Open Anyway」。
5. 之后正常双击即可打开，不会再拦截。

> 注意：macOS 15 (Sequoia) 起，旧版本里「右键 →"打开"」的快捷方式已被移除，必须走上面
> 「隐私与安全性」里的「仍要打开」。

**如果以上仍打不开（极少数情况，常见于从网盘/聊天软件下载）：**

文件可能被加了"隔离"标记。打开「终端 / Terminal」，把下面命令里的路径换成你实际的 App 位置后回车：

```bash
xattr -dr com.apple.quarantine /Applications/ICSTeX.app
```

然后再双击打开。

Apple 官方说明：

https://support.apple.com/en-us/102445

## 快速测试

1. 打开 ICSTeX。
2. 点击“项目”或工具栏里的项目按钮，新建项目。
3. 选择 IB/IA 模板。
4. 点击“编译”。
5. 试用“插入图片”或“插入表格”。
6. 试用“引用”面板添加 BibTeX 条目，或点击“导入”粘贴 BibTeX、DOI、arXiv ID、URL 或标题。
7. 试用“标签”面板刷新并插入 ref/autoref/eqref。
8. 点击工具栏“环境”，复制诊断报告，确认 MacTeX/texcount/synctex 状态。

## 如果编译失败

- 确认已经安装或重新安装 MacTeX。
- 安装 MacTeX 后重启 ICSTeX。
- 点击 ICSTeX 工具栏“环境”，复制诊断报告发给维护者。
- 在 Terminal 里检查：`which latexmk`
- 如果字数统计异常，在 Terminal 里检查：`which texcount`
- 确认图片文件仍然存在。
- 查看“错误”面板，排查缺失标签、citation 或 package。

## 如果字数统计和 Overleaf 不一致

- 先看“字数”面板底部的统计模式。
- `texcount 精确统计` 更接近 Overleaf。
- `Python 简化统计` 表示没有找到 `texcount`，或 `texcount` 调用失败。请安装完整 MacTeX 后重启 ICSTeX。

## 关于测试版

这个 DMG 适合发给可信同学或本地测试使用。它仅使用 ad-hoc 签名，还不是经 Developer ID 签名和 Apple notarized 的公开发布版本。
