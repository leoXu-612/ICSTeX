# UI Scale 测试套件性能报告（Phase E，收口结论：结果 B）

## 1. 结论

生产环境单窗口 UI Scale 切换平均 **72.5 ms**（目标 <300 ms，达标）；完整测试套件由基线
~27s 增至 ~116s，根因已定位为 **Qt `QApplication.setStyleSheet()` 的应用级重排作用于测试
进程中残留的约 100 个顶层窗口**，属于测试隔离问题，不阻塞本轮合并（结果 B）。

## 2. 可复现数据

探针开关：`ICSTEX_UI_SCALE_PROFILE=1`（默认关闭，不污染生产控制台）。

一次完整套件（659 tests）内的量测：

| 指标 | 数值 |
| --- | --- |
| Scale 切换次数 | 10 |
| 每次切换平均注册窗口数 | ~104 |
| `apply_scale` 总耗时 | ~96.5 s |
| 其中 `app.setStyleSheet`（apply） | ~96.0 s（~9.6 s/次） |
| 其中 QSS 构建（已缓存） | ~0 ms |
| 其中 icons+layout refresh | ~4 ms |

生产单窗口（本机 offscreen，MainWindow + 显示）：

| 档位 | 耗时 |
| --- | --- |
| 100% → 125% | 77.3 ms |
| 125% → 100% | 68.0 ms |
| 100% → 150% | 77.1 ms |
| 150% → 100% | 67.5 ms |
| 平均 | 72.5 ms |

## 3. 根因

- Qt 对应用级样式表变更会重排**所有**顶层窗口的全部控件；测试进程在多个模块中创建了约
  100 个未关闭的 `MainWindow`，使单次 `setStyleSheet` 从单窗口的 ~70ms 放大到 ~9.6s；
- 已排除：QSS 字符串构建（缓存后 ~0ms）、工具栏图标扫描与 layout invalidate/activate
  （合计 ~4ms）、Scale 管理器的基准字体计算（无累积）；
- 尝试过的缓解：只重排可见窗口、注册窗口 WeakSet、QSS 字符串缓存、`test_gui_editor`
  模块级清理——模块级清理未能显著降低窗口残留（其他模块仍创建大量窗口），故未保留。

## 4. 技术债

- 项：完整套件耗时 ~116s（基线 ~27s）；
- 根因：应用级样式表重排 × 测试残留窗口；
- 方向 A：将 Scale 样式改为**按注册窗口**作用域（`window.setStyleSheet`），需验证无父级
  弹层（菜单/工具提示）在非 100% 档位下的样式一致性；
- 方向 B：为 GUI 测试建立统一 Fixture（关闭自建窗口 + `processEvents`），全量改造测试
  文件（规模较大，宜独立分支进行）；
- 不阻塞本轮：生产单窗口 72.5ms 达标；CI 正确性不受影响；套件耗时仅影响开发循环。

## 5. 基准复现命令

```bash
ICSTEX_UI_SCALE_PROFILE=1 QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
# 观察 stderr 中的 ui-scale: 行
QT_QPA_PLATFORM=offscreen python3 /tmp/bench_single.py  # 单窗口 benchmark
```
