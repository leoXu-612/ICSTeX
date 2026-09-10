# ICSTeX Project Index

更新时间：2026-09-11（Asia/Taipei）

## 权威工作区

- 当前可写路径：`git rev-parse --show-toplevel` 返回的 `ICSTeX` 仓库根目录
- 旧路径：仅作回滚参考的 legacy workspace
- 旧路径只保留为 rollback context，不在其中继续开发。

## 文档入口

- `README.md`：用户/开发者安装、运行、测试和打包入口。
- `AGENTS.md`：所有 coding agent 的操作约束。
- `docs/PROJECT_STATE.md`：当前已验证源码、release matrix 与风险。
- `docs/ROADMAP.md`：产品和技术优先级。
- `docs/CODEX_V1_DEVELOPMENT_INSTRUCTIONS.md`：下一代正式版的待执行开发总纲、
  分阶段验收与授权边界；不自动替换现有 active brief。
- `docs/V1_IMPLEMENTATION_PLAN.md`：已启动的下一代本地开发范围、差额、验收账本、
  当前唯一 slice 与下一步；与独立 Beta 发布 brief 分离。
- `docs/v1-m0-m1-verification-2026-09-10.md`：M0/部分 M1 的合成数据、原生验证、
  复现入口和未完成边界；不代表完整 V1 或发布验收。
- `docs/v1-m1-final-evidence-2026-09-10.md`：后续实际 FINAL 身份、输入/产物摘要、
  Block 归属与只读检查验收；与 M2–M6 和发布验收分开。
- `docs/v1-m2-profile-verification-2026-09-10.md`：本地声明式配置、冲突保护、
  字数目标和检查联动的原生证据；不是完整 M2 工作台验收。
- `docs/v1-m2-workspace-verification-2026-09-10.md`：中文项目创建、只读工作区状态、
  原生 FINAL/检查/导出/重开与干净 Block 关闭；保留待保存/冲突和布局门槛。
- `docs/v1-m2-block-close-verification-2026-09-10.md`：后续受保护模型/生成源码保存、
  关闭选择、外部冲突、异步 FINAL 与原生重开；不是完整 checkpoint 或布局验收。
- `docs/v1-m2-block-layout-verification-2026-09-10.md`：窄窗口/五档缩放、键盘/Undo、
  布局属性与同源码原生复跑；记录当时的属性草稿和性能复核缺口。
- `docs/v1-m2-property-draft-verification-2026-09-11.md`：后续内存属性草稿、
  选择/刷新保留、显式应用/关闭、冲突和原生证据；记录当时的二次编辑器缺口。
- `docs/v1-m2-editor-target-verification-2026-09-11.md`：多表格/公式目标绑定、
  活跃单元格草稿、显式保存/撤销、原生冲突与实际 PDF；区分专项和全套结果。
- `docs/v1-m2-image-import-verification-2026-09-11.md`：图片暂存/独占发布、路径与
  拖入目标边界、测试夹具修正；真实 picker 成功导入仍待验收。
- `docs/DECISION_LOG.md`：长期架构决策及其原因。
- `docs/update-delivery-design-2026-09-08.md`：原生更新器实现、信任分工与发布验收边界。
- `packaging/UPDATES.md`：维护者提供配置、暂存固定 SDK、签名与 appcast 接入步骤。
- `docs/FORCODEX_UPDATES.md`：与本机安装任务隔离的并行更新器范围及收口 brief。
- `docs/MEMORY_MANAGEMENT.md`：文档职责、权威顺序和信息生命周期。
- `DEEPSEEK.md`：DeepSeek 兼容入口，只指向统一规则与任务 brief。
- `FORCODEX.md` / `FORCLAUDE.md` / `FORDEEPSEEK.md`：当前 bounded
  assignments。
- `MEMORY.md`：紧凑、跨任务的 durable reminders。
- `PROJECT_LOG.md`：append-only 已完成工程历史。
- `docs/response-optimization-verification-2026-09-08.md`：响应优化验收、测量边界与
  原始/后测样本入口。
- `CHANGELOG.md`：面向用户的版本变化。
- `MIGRATION_RECORD.md`：workspace migration、备份和验证证据。
- `PROJECT_FILE_INDEX.sha256`：迁移时建立的稳定内容索引，不代表后续源码未变化。

## 代码入口

```text
app/
  core/        编译、PDF 状态、Word Count、诊断、路径和纯文本规则
  gui/         PySide6 主窗口、controllers、编辑器、PDF、工具箱和主题
  assets/      App 内置视觉资源
tests/         unittest 回归与 GUI smoke tests
packaging/     macOS/Windows 构建脚本、spec、README 和 offline wheel
tools/         开发辅助、协作 watcher、隔离性能与编辑器交互探针
dist/          已生成 artifacts，不是源码权威来源
build/         可重建 packaging cache，不是源码权威来源
```

公式/表格交互回归：`app/gui/formula_dialog.py`、`app/gui/table_grid.py`、
`app/gui/insert_panel.py`、`app/gui/blocks/table_editor.py`；剪贴板纯规则位于
`app/core/table_clipboard.py`。原生合成数据检查入口为 `tools/probe_editor_interactions.py`。

应用更新：`app/core/app_updates.py`、`app/gui/app_update_controller.py`、
`app/gui/update_dialog.py`、`app/gui/update_backends.py`；原生 SDK 构建接入位于
`packaging/native_updates.py` 与 `packaging/native_updates/sparkle_bridge.m`。
默认不配置运行时；离线中文界面探针为 `tools/probe_app_updates.py`。

## 常用命令

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m app
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
bash packaging/preflight.sh
```

迁移索引验证需要使用 macOS 可用的 UTF-8 locale：

```bash
env -u LC_ALL -u LC_CTYPE LANG=en_US.UTF-8 \
  shasum -a 256 -c PROJECT_FILE_INDEX.sha256
```

正常开发后出现 index mismatch 是预期现象；用当前测试、Project State 和
PROJECT_LOG 判断后续变更，不要把迁移索引当作版本控制系统。
