# UI Scale 视觉验收记录（Phase D）

## 1. 测试环境

- macOS（Apple M3），内置 Liquid Retina（2880×1864 逻辑 1470×956）；
- 外接显示器：**无**（`system_profiler SPDisplaysDataType` 仅显示内置屏）；
- 渲染方式：offscreen Qt 真实渲染截图（`window.grab()`）+ 正在运行的桌面实例；
- 说明：offscreen 虚拟屏宽上限约 1080 DIP，`100-medium`/`125-narrow` 截图宽度被平台
  钳制，仅用于结构示意，不代表真实窗口宽度。

## 2. UI Scale 循环（90→100→110→125→150→100）

自动化验证（`tests/test_ui_scale.py`）：

| 检查项 | 结果 |
| --- | --- |
| 字号回到 100% 后与首次一致（无累计） | PASS（基准字号断言） |
| 工具栏图标尺寸随档位恢复 | PASS（20×scale 断言） |
| 按钮高度无累计 | PASS（metrics 派生，单一基准） |
| QSS 无重复叠加 | PASS（缓存键 (scale,density)，同键只构建一次） |
| Logo 按 KeepAspectRatio 缩放、不逐次变模糊 | PASS（每次从原始 QPixmap 重新 scaled） |
| 窗口尺寸无异常增长 | PASS（未做 transform/resize 放大） |

截图：[90-wide.png](assets/ui-scale/90-wide.png)、[150-wide.png](assets/ui-scale/150-wide.png)。

## 3. 窗口尺寸矩阵

覆盖 1024×768 / 1280×800 / 1440×900 / 1728×1117 / 全屏。自动化+截图结果：

| 区域 | 检查项 | 结果 |
| --- | --- | --- |
| 欢迎页 | 4/2/1 列按钮、2/1/1 卡片、可滚动、按钮文字完整 | PASS（`test_welcome_reflows_to_4_2_1_columns`、`update_button_minimum_size`） |
| 标签栏 | 滚动按钮、ElideRight、字号/高度不变 | PASS（`configure_tab_bar` + `test_source_tabs_configured`） |
| PDF Panel | <700 DIP 出现“更多”、核心工具常显、页码框不压扁 | PASS（`test_narrow_toolbar_shows_more_menu` + [pdf-more-menu.png](assets/ui-scale/pdf-more-menu.png)） |
| Dock/Splitter | 拖动不改字号、中央不被压缩、恢复后边界校正 | PASS（`refresh_window_metrics`/`clamp_splitter_sizes`，运行中实测无字号变化） |
| Diagnostics | 无内容紧凑、出错自动展开 | PASS（`error_seen` → dock.show，测试覆盖） |

截图：[100-medium.png](assets/ui-scale/100-medium.png)、[125-narrow.png](assets/ui-scale/125-narrow.png)。

## 4. 三类缩放隔离

| 操作组合 | 断言 | 结果 |
| --- | --- | --- |
| UI Scale → PDF Zoom | PDF Zoom 不改变应用字体/UI Scale 档位 | PASS（`test_pdf_zoom_does_not_change_ui_scale_or_font`） |
| Dock/Splitter/标签宽度变化 | 不改应用字体 | PASS（重排只隐藏/换行/溢出，无 setFont） |
| 响应式重排 | 不改 AppSettings 中的 ui_scale | PASS（重排不写设置） |
| PDF Zoom | 不写项目 Schema | PASS（zoom 只调 QPdfView） |

## 5. 项目生命周期竞态

打开 A → 自动编译启动 → 立即关闭 → 打开 B：

- 应用不崩溃、无 deleted QObject 信号错误：PASS（`stop_compile` 清空 `on_finished`；
  测试套件两轮全绿）；
- A 的晚到结果不写入 B / B 的 PDF 不被覆盖：PASS（会话独立，编译回调已断开）；
- 已关闭会话不再接收回调：PASS；
- CompileManager 不残留孤立任务：PASS（stop_current + 回调清空）。

## 6. 多显示器

**未完成真实多显示器手测**（本机仅有内置 Retina，无外接屏）。已完成：

- Qt 6 High DPI 静态审计：未发现手写 `devicePixelRatio` 乘除、`IgnoreAspectRatio` 拉伸；
- 单屏验证：无累计缩放、图标不翻倍。

按指导 9.1：未发现真实二次 DPR 问题，暂不增加 `screenChanged` 监听，避免引入重复缩放。

## 7. 发现的问题与修复

- 本轮视觉验收未发现新的 P0/P1 布局问题；
- 收口期间修复的既有问题：项目关闭后晚到编译结果在已删除会话上发信号的竞态
  （`project_session.stop_compile` 清空回调，提交 `77a165b`）。

## 8. 未验证项

- 真实外接显示器切换（Retina ↔ 非 Retina）；
- 人工像素级观感复核（建议维护者基于上述截图与运行中应用完成）；
- 全屏模式下的极端长文档欢迎页滚动（结构已覆盖，观感待人工确认）。
