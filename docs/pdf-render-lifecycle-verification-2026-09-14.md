# PDF 白页与渲染生命周期修复

本次不再以“重跑通过”代替根因。已构造确定失败的关闭/重开时序，并用同一断言验证
修复；另覆盖迟到的旧渲染结果和对象销毁顺序。当前源码/完整回归/安装身份统一见
`PROJECT_STATE.md`。原始实验根为任务证据目录`pdf-root-cause-20260914/`。

## 原因与修复

| 可验证的问题 | 修复 |
| --- | --- |
| Qt渲染任务遇到已关闭文档直接返回，却不清除pending；同页同尺寸的新请求被当成旧请求，永久白页 | 新内容加载使用新QPdfView及其新队列，旧队列不再复用 |
| Qt查看器按页号收取渲染结果，不校验文档代际；旧结果可填入新PDF的页面缓存 | 旧结果只能进入已脱离文档、待销毁的旧查看器 |
| 文档原先先于搜索模型/渲染器销毁 | 文档最后归属到PdfPanel；先销毁搜索与查看器、停止渲染线程，再销毁文档 |

仍使用原QtPdf渲染技术与多线程模式，没有引入新依赖、持续repaint、定时重载或
调低PDF质量。PdfPanel、工具栏、QPdfDocument及搜索模型保持稳定；只替换承载
旧队列/页面缓存的QPdfView。校验为内容未变时整个查看器继续复用。相同逻辑文档
保留阅读位置和缩放；焦点、搜索返回和页码信号重新连接；工具侧观察器随viewChanged
切换到实际新viewport，不能盯着已移除的旧控件统计。

技术依据为对应版本的Qt官方源码：
[QPdfPageRenderer](https://github.com/qt/qtwebengine/blob/v6.11.1/src/pdf/qpdfpagerenderer.cpp)
的RenderWorker::requestPage和pending去重，及
[QPdfView](https://github.com/qt/qtwebengine/blob/v6.11.1/src/pdfwidgets/qpdfview.cpp)
的pageRendered缓存提交、setDocument与析构路径。

## 可重复验证

- `test_pending_render_from_cleared_document_cannot_block_reopened_pdf`：只在测试中用
  Qt自身的单线程排队模式固定时序，让排队任务确实在clear后才执行。旧源码失败，
  新PDF蓝色标记为0；修复后同断言通过，蓝色页面实际出现。两个原始PDF和前后图
  保存在`red/`、`green/`，没有丢弃失败夹具。产品仍使用多线程模式。
- `test_late_old_render_cannot_replace_new_document_pixels`：在新load之后送达真实
  旧PDF生成的图像。关闭队列隔离的对照失败（`stale-completion-red.log`）；开启后
  新蓝色内容可见，旧红色像素为0。
- `test_document_outlives_search_and_native_renderer_on_panel_destruction`：直接断言
  QObject销毁顺序。避免仅凭“窗口消失”推断线程和文档安全退出。
- `native-final/`：产品默认多线程下，首次显示、同字节复用、同路径新字节、跨root、
  六次搜索中清空/重开、搜索未完关窗通过；新像素、3页/3匹配、页码/缩放与销毁有断言。
  自然Paint之后才取像素；窗口active/exposed。中途被切走的`native-owned`不算通过。
- Physics EE仅使用既有冻结副本；实际自动保存→PREVIEW→新revision颜色像素的回归
  见`real-final/`，不是单个load调用或进程结束代替显示。原稿不修改。

## 失败候选与证据边界

- 首次组合检查在探针模拟对象缺少新viewChanged信号后留下半初始化事件过滤器，
  退出139，报告`Python-2026-09-14-110838.ips`。已补模拟接口并先初始化观察状态再挂
  事件过滤器；这不是已安装产品发生的QtPdf渲染崩溃。
- 将文档直接放到QPdfView下面的中间候选不正确：QPdfView私有数据早于其QObject
  子对象析构，文档close信号可访问已释放的查看器私有数据。该候选在组合检查退出139，
  `Python-2026-09-14-111204.ips`为QPdfDocument::status/close相关栈，已弃用。
  同候选第二次小范围复现`Python-2026-09-14-111300.ips`停在QAbstractScrollArea::viewport，
  属于同一析构阶段访问已释放查看器的问题；两个失败文件均保留。
  最终文档属于PdfPanel而非QPdfView，并由上述实际销毁顺序断言保护。
- 早期记录中的搜索timer崩溃来自故意先销毁文档的旧测试夹具；其独立红绿修正保留。
  原A首次白页没有保留当时PDF或曝光状态，无法证明其每一步与本次复现完全相同。
  现在关闭的是已明确复现并修正的队列/旧结果/销毁缺陷，不改写那次历史记录，也不
  宣称任意Qt或任意损坏PDF从此不可能崩溃。
- Qt在setDocument(None)时的QPdfLinkModel连接提示及IMK警告保留，未用日志过滤掩盖。
  本次不升级依赖、不改FINAL证据/文件事务、不重做无关UI、IME或VoiceOver矩阵。
