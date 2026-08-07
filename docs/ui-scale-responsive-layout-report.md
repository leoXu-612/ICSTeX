# UI Scale 与响应式布局 - 最终实施报告

> 分支：`feature/ui-scale-responsive-layout`（基线 `527808f`，644 tests OK）
> 完成后：**658 tests OK**（新增 15 项 UI Scale / 响应式测试）
> 依据：`<HOME>/Downloads/ICSTeX_UI_Scale与响应式布局修复执行方案.md`

## 1. 根因结论

此前的按钮/字号失真的根因是：**固定像素宽高与散落的 QSS 字号不随字体增长**——
欢迎页 Logo `setFixedSize(88,88)`、PDF 页码框 `setFixedWidth(72)`、工具箱 rail/按钮
固定宽、`theme.py` 中 92 处含尺寸属性（`font-size` 13/12/11/10/15/23px 分散、控件
`min-height` 22–32px 分散）都写死基线值，UI 字体一放大就会截断或失真；且没有任何
统一缩放机制，窗口/Dock 变化与 UI Scale 混为一谈。

## 2. 三类缩放的分离（已实现并测试锁定）

| 变化 | 触发 | 行为 |
| --- | --- | --- |
| 窗口/Dock/Splitter 尺寸 | resize | 只重排（欢迎页断点、标签滚动、PDF 工具栏分级），**不改字号** |
| 应用 UI Scale | 视图菜单 5 档（90/100/110/125/150%） | 从**基准字体**重算 UiMetrics/TypographyMetrics，重建 QSS、图标、Dock/Splitter 约束 |
| 内容 Zoom | PDF 缩放按钮 | 只改 `QPdfView`，不动工具栏与外层（测试 `test_pdf_zoom_does_not_change_ui_scale_or_font` 锁定） |

## 3. 关键实现

- `app/gui/theme/ui_metrics.py`：`UiMetrics`（间距/控件高度/图标/圆角/Dock 最小宽/诊断高度，全部 = 基线 × scale）、`TypographyMetrics`（body/caption/button/sectionTitle/pageTitle/monospace 角色）；
- `app/gui/theme/ui_scale_manager.py`：`UiScaleManager`（`_base_point_size × scale`，**永不基于当前字号再乘**；`SCALE_TIERS` 固定档位；切换时刷新工具栏图标、重建 QSS、`refresh_window_metrics` 重约束 Dock/Splitter；重排只作用于可见窗口）；
- `theme.py → theme/__init__.py`（包化，导出不变）；`stylesheet(metrics, typography)` 用字体角色与度量派生关键数值；
- `AppSettings`：`appearance/ui_scale` + `density` 持久化；MainWindow 启动应用保存的档位，视图菜单提供 5 档切换（`Ctrl+Shift+Z` 等不变）；
- `app/gui/responsive/helpers.py`：`LayoutBreakpoints(1100/760)`、`resolve_layout_mode`、`update_button_minimum_size`（QFontMetrics 计算，杜绝截断）、`layout_reflow`（实例稳定重排）、`configure_tab_bar`；
- 欢迎页：可滚动容器 + 操作按钮 4/2/1 列、卡片 2/1/1 列响应式；Logo 尺寸与按钮最小尺寸跟随 metrics；
- 标签栏：`setExpanding(False)` + 滚动按钮 + `ElideRight`（源码/Block/底部标签），字号与高度稳定；
- PDF 工具栏：核心工具常显（页码/缩放/适合宽度），次要工具（翻页/搜索/导出/显示）在 <700 DIP 时收进“更多”菜单；页码框固定宽改为最小宽；
- Diagnostics：出错时自动展开 Dock，平时保持紧凑最小高度；项目关闭时清空编译回调，杜绝晚到结果在已删会话上发信号（修复偶发竞态）。

## 4. 移除/替换的固定尺寸

| 位置 | 原固定值 | 处理 |
| --- | --- | --- |
| welcome_page logo | 88×88 | `UiMetrics.logo_size` 派生 |
| pdf_panel 页码框 | fixedWidth 72 | `setMinimumWidth(64)` |
| toolbox rail/按钮 | fixedWidth 72/64 | 保留（导航常显），图标尺寸入 metrics |
| panelHeader | fixedHeight 36 | 与令牌统一为 `panel_header_height`（38×scale） |
| compile_progress | fixedWidth 100 | 保留（状态指示），窄工具栏可接受 |
| engineSelector | min-width 112 | `round(112×scale)` |
| iconButton | 28×28 | `large_icon_size` 派生 |
| QSS 字号/min-height | 分散字面量 | 字体角色 + metrics 派生 |

## 5. 测试与验证

- 新增 15 项：档位/基准字号不漂移、Metrics 比例、工具栏图标、PDF Zoom 隔离、项目与 Stable LaTeX 隔离、设置持久化、全档位 QSS、关键按钮不裁切、断点解析、欢迎页 4/2/1 重排、可滚动、标签栏配置、PDF 工具栏“更多”菜单、主工具栏结构；
- 全套件 **658 tests OK**；
- `tools/run_mvp_ci.sh`（本地 CI 模拟）全绿，demo 构建通过；
- 未发现 `devicePixelRatio` 手写乘除 / `IgnoreAspectRatio` 拉伸（审计 §3），Qt6 原生 High DPI 未被二次放大。

## 6. 已知限制

- 全套件耗时从 ~27s 升至 ~130s：UI Scale 切换会触发应用级 QSS 重排，测试中残留的多个窗口使单次切换约 1.4s；生产环境单窗口下切换 <0.5s，可接受，后续可考虑按窗口作用域缓存样式；
- 多显示器 `screenChanged` 尚未显式挂接（审计确认无重复 DPR 计算，Qt6 原生处理）；已在建议中列出；
- 工具栏 overflow 依赖 Qt `QToolBar` 原生行为（结构测试已锁定），未强制注入自定义溢出菜单；
- density 字段已入设置与度量，UI 尚未提供紧凑/舒适切换入口（默认 comfortable）。

## 7. 后续建议

1. 挂接 `windowHandle().screenChanged`：清理依赖屏幕的图标缓存 + 重算断点；
2. 提供 density（紧凑/舒适）设置入口；
3. 优化 QSS 重排作用域（per-window 样式缓存）以恢复测试耗时；
4. 用 SVG 图标源替换低分辨率 PNG（当前图标为矢量生成，无拉伸风险）。

## 8. 修改文件清单

新增：`theme/ui_metrics.py`、`theme/ui_scale_manager.py`、`responsive/__init__.py`、
`responsive/helpers.py`、`tests/test_ui_scale.py`、`tests/test_responsive_layout.py`、
`docs/ui-scale-fixed-size-audit.md`、`docs/ui-scale-responsive-layout-report.md`。

修改：`theme.py → theme/__init__.py`、`main_window.py`（scale 应用/持久化/菜单同步）、
`main_window_actions.py`（UI Scale 子菜单）、`main_window_layout.py`（标签栏配置）、
`welcome_page.py`（响应式重写）、`pdf_panel.py`（工具栏分级）、`block_mode.py`
（诊断自动展开）、`blocks/workspace_widget.py`（标签栏）、`blocks/diagnostics_dock.py`
（error_seen）、`blocks/project_session.py`（停止编译回调清空）、`core/settings.py`
（ui_scale/density）。
