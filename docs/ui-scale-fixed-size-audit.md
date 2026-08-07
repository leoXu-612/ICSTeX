# UI Scale 与响应式布局 - 固定尺寸审计（Phase 1）

> 分支：`feature/ui-scale-responsive-layout`（基线 `527808f`，644 tests OK）
> 依据：`<HOME>/Downloads/ICSTeX_UI_Scale与响应式布局修复执行方案.md`

## 1. 固定几何 API 审计

| 文件 | 控件 | 当前写死值 | 问题 | 替换方案 |
| --- | --- | ---: | --- | --- |
| welcome_page.py:60 | logo cover | `setFixedSize(88, 88)`，`pixmap.scaled(82,82)` | UI Scale 变化后不联动 | UiMetrics.large_icon/logo 尺寸派生 |
| main_window_layout.py:96 | compile_progress | `setFixedWidth(100)` | 窄工具栏占位 | metrics 派生，或允许收缩 |
| main_window_layout.py:198 | toolbox dock | `dock.resize(340, …)` | 初始尺寸写死 | metrics.dock_min_width |
| main_window_layout.py:265 | bottom collapse 按钮 | `setFixedSize(26, 26)` | Scale 变化后偏小 | metrics.icon_size 派生 |
| widgets.py:29 | AutoCompileToggle | `setMinimumWidth(78)` / `setFixedHeight(30)` | 字号放大后截断风险 | QFontMetrics + metrics.control_height |
| main_window_support.py:77 | panelHeader | `setFixedHeight(36)` | 与 theme 令牌 `PANEL_HEADER_HEIGHT=38` 不一致 | 统一 metrics.panel_header_height |
| toolbox_navigation.py:35,74 | rail/按钮 | `setFixedWidth(72/64)` | 窄/宽窗均固定 | metrics 派生 + 允许省略 |
| pdf_panel.py:113 | 页码 spin | `setFixedWidth(72)` | 大 Scale 截断 | metrics 派生 |
| main_window.py:102 | 主窗口初始尺寸 | `resize(1440,900)` | 仅初始，无碍 | 保留 |
| user_guide/environment_doctor/formula/project dialog | 对话框 | `resize(...)` | 仅初始 | 保留 |
| latex_editor.py:98 | 行号区 | `setGeometry(...)` | 按字体计算，无碍 | 保留 |

## 2. QSS 固定数值审计（theme.py，92 处含尺寸属性）

主要散落项：

- `font-size`：13/12/11/10/15/23 px 分散定义（第 166–640 行）→ 应统一为字体角色（body/caption/button/sectionTitle/pageTitle/monospace）× scale；
- `min-height`：22/24/26/28/30/32 px 分散（QToolButton、QPushButton、QTreeView::item、QTabBar::tab、输入框、QComboBox 项）→ UiMetrics.control_height 系列派生；
- `min-width/max-width`：iconButton 28×28 固定、engineSelector 112、page_spin 72 → metrics；
- `width/height`：splitter handle 7px、separator 1px、divider 1px → 可保留常量或 metrics。

## 3. 图标 / 位图缩放审计

- `app/gui` 中**未发现** `QPixmap.scaled(...)`（除 welcome logo 的 KeepAspectRatio+Smooth，符合要求）、`Qt.IgnoreAspectRatio`、`devicePixelRatio/F()` 手写乘除 —— Qt6 原生 High DPI 未被重复放大；
- 图标经 `app.gui.icons.icon(name, size)` 按 size 生成，未发现低分辨率 PNG 强行拉伸。

## 4. 保留 / 移除结论

保留：主窗口/对话框初始 `resize`、行号区 `setGeometry`（按字体计算）。

移除/替换：上表所有固定宽高 → 统一 UiMetrics 派生；QSS 字号 → 字体角色；控件 min-height → metrics。

## 5. 与三种缩放的对应关系

- 窗口/Dock/Splitter 尺寸变化 → 仅响应式重排（欢迎页断点、标签滚动、工具栏 overflow），不改字号；
- UI Scale 变化 → 统一重算 UiMetrics 与字体角色，重生成 QSS，重新约束 Dock/Splitter；
- PDF/编辑内容 Zoom → 只改内容视图，不动工具栏与外层（现有 zoom 已隔离，需测试锁定）。
