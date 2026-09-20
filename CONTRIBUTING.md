# Contributing to ICSTeX

采用轻量 GitHub Flow：**一个任务、一个短期分支、一个 PR**。不要把多个任务持续堆在
`codex/v1-development`，也不要直接向 `main` 或 `release/*` 塞功能。

## 从哪里开始

先读 [AGENTS.md](AGENTS.md)、[当前状态](docs/PROJECT_STATE.md)；Agent 再读自己的
任务文件。以当前 Git 根目录和实际分支为准，本机开发版、`main` 和已发布安装包不一定相同。
较大的功能或 Bug 先建 Issue；小型文档/维护改动可在 PR 中直接说明。
Bug / Feature 使用仓库提供的两套表单，优先级 P0–P3 先记录在表单中，不自动等同标签。

```bash
git fetch origin
git switch -c feature/short-task-name origin/main
python3 -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python3 -m pip install -r requirements.txt
python3 -m app
```

已有未提交工作时，不要清空、stash 或换分支强行覆盖；另建隔离 worktree。

## 分支角色

| 分支 | 用途 |
| --- | --- |
| `main` | 稳定开发主线；修改经本地验证、PR 审阅后进入 |
| `feature/<name>` | 新功能 |
| `fix/<name>` | Bug 修复 |
| `docs/<name>` | 文档 |
| `perf/<name>` | 性能优化 |
| `codex/<name>` | Agent 的单个独立任务 |
| `release/<version>` | 发布冻结；只接收从 `main` 发起的发布准备 PR |

发布分支不承担日常开发；修复先经 `main`，再通过 PR 纳入发布准备。
tag / GitHub Release、打包与签名需维护者另行授权，不随功能 PR 自动执行。
本轮只配置 `main` Ruleset；`release/*` 的上述角色是流程约定，不宣称已有远端强制规则。

## 提交 PR 前

先运行改动对应的专项，再完成仓库规定的检查：

```bash
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
```

PowerShell 中先执行 `$env:QT_QPA_PLATFORM="offscreen"`，再运行 unittest。
发布准备才运行 `bash packaging/preflight.sh`；它不代替实际安装包和原生界面验收。
GitHub Actions 已按维护者决定关闭，`main` 没有 CI 必过门槛。现有 workflow 文件仅保留，
不代表正在运行。验证在本地进行，并在 PR 中写明平台、命令、结果和未覆盖范围；
未获维护者授权，不重新开启 Actions 或添加其他自动化来代替它。

- 复用已有实现，不为小任务新增框架或依赖。纯规则在 `app/core`，Qt 编排在 `app/gui`。
- 保存不能丢内容或移动光标；失败 PDF 必须标明过期，PREVIEW 不能冒充 FINAL。
- 测试使用独立项目；不提交论文、个人路径、密钥、构建产物或未脱敏截图。
- 保留无关改动；按 [文档规则](docs/MEMORY_MANAGEMENT.md) 更新当前任务、状态与工程日志。

## Review 与合并

填写 PR 模板的五项：What changed、Why、Testing、Potential issues、Screenshots。
没有截图需求写 N/A，未跑测试写原因；有关联 Issue 时写 `Closes #123`。
模板是填写约定，不是 PR 正文自动校验器，本轮不增加这类 Actions。

[`main` Ruleset](https://github.com/leoXu-612/ICSTeX/rules/23690757) 要求 PR 和所有讨论解决；
禁止 force-push 和删除，无 bypass。暂不要求 approval（0 人），仍建议互相 Review。
按 **Squash merge** 合并，标题建议 `feat: ...`、`fix: ...`、`docs: ...` 等。
合并前先同步最新 `main`，处理实际冲突并验证整合结果。不能把“没有文本冲突”当成
行为正确，也不能把旧 CI 失败改称通过；本地验证不足时明确说明，不直接 push 主线。
