# ICSTeX Release Website 信息架构

状态：`Accepted for website/`
更新：2026-08-09（Asia/Taipei）

## 页面职责

```text
Homepage = 产品理解 + 当前版本 + 下载
Guide    = 功能目录 + 安装与操作步骤
About    = 产品理念 + 创作者公开信
GitHub   = 源码、Issues、Release 与真实发行资产
```

## 首页顺序

1. NAV：功能、使用指南、理念、下载、GitHub。
2. HERO：ICSTeX、当前版本、Formula Intelligence、产品截图、macOS Apple Silicon CTA。
3. CURRENT RELEASE：版本、平台、发布通道、下载包和校验信息。
4. FORMULA EDITOR：结构化公式、源码可见、确认后写回。
5. LOCAL RECOGNITION：图片 → 本地识别 → 人工核对 → 插入。
6. MODULAR WORKSPACE：源码、PDF、Block 和属性面板。
7. BUILT LOCAL-FIRST：不自动上传、编译 freshness、主动联网查询。
8. PUBLIC BETA + LIMITS：备份提示、已知限制、文档、报告问题和最终下载 CTA。
9. FOOTER：定位、Guide、About、GitHub、当前版本。

## 二级页面

### `/guide/`

功能一览、安装与环境检查、项目工作流、Formula Editor、图片转公式、编译与 PDF、
Block 工作区、FAQ。每个功能说明用途、入口、步骤、结果、依赖和注意事项。

### `/about/`

精炼说明、Local-first / Understandable / LaTeX-compatible 三项原则，以及未改变原意的
创作者公开信。

## 内容边界

- 版本、tag、asset URL、SHA-256、平台状态和限制只来自 `release/release-manifest.json`
  生成的 `website/release.json`。
- 首页使用普通用户语言；工程术语只在确实帮助下载、校验或排错时出现。
- Windows x64 不得描述为可下载；Windows ARM64 的 Beta 限制必须保持可见。
- Guide 的能力描述必须能够追溯到源码、测试、用户指引或 Release 文档。
- About 页公开信的正文由 `docs/product/FOUNDER_LETTER_ZH.md` 保存，网页副本不得擅自润色改意。

## 响应式与无障碍不变量

- 所有页面都有唯一 `h1`、`main`、skip link、可见 `:focus-visible` 和有效 `lang`。
- 截图有明确 `alt`、`width`、`height`；首屏图高优先级，后续图 lazy-load。
- 390px、430px、1024px、1280px、1440px 宽度不产生横向滚动。
- 平台 tab 保留 `tablist` / `tab` / `tabpanel`、箭头键和 URL hash 状态。
- 站点继续使用 Pico CSS + 自定义 CSS + 原生 JavaScript，不引入运行时框架或构建链。
