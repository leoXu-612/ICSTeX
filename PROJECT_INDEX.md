# ICSTeX Project Index

更新时间：2026-08-06（Asia/Taipei）

## 权威工作区

- 当前可写路径：`<HOME>/Desktop/Codex/ICS-Project-/ICSTeX`
- 旧路径：`<HOME>/Desktop/Codex/Codex_Latex编译器`
- 旧路径只保留为 rollback context，不在其中继续开发。

## 文档入口

- `README.md`：用户/开发者安装、运行、测试和打包入口。
- `AGENTS.md`：所有 coding agent 的操作约束。
- `docs/PROJECT_STATE.md`：当前已验证源码、release matrix 与风险。
- `docs/ROADMAP.md`：产品和技术优先级。
- `docs/DECISION_LOG.md`：长期架构决策及其原因。
- `docs/MEMORY_MANAGEMENT.md`：文档职责、权威顺序和信息生命周期。
- `DEEPSEEK.md`：DeepSeek 兼容入口，只指向统一规则与任务 brief。
- `FORCODEX.md` / `FORCLAUDE.md` / `FORDEEPSEEK.md`：当前 bounded
  assignments。
- `MEMORY.md`：紧凑、跨任务的 durable reminders。
- `PROJECT_LOG.md`：append-only 已完成工程历史。
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
tools/         Codex/Claude collaboration watcher
dist/          已生成 artifacts，不是源码权威来源
build/         可重建 packaging cache，不是源码权威来源
```

## 常用命令

```bash
cd "<HOME>/Desktop/Codex/ICS-Project-/ICSTeX"
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
