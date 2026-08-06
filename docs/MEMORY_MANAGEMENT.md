# ICSTeX Memory Management

更新时间：2026-08-06（Asia/Taipei）

本规范管理项目内部的状态、决策、任务和历史文档。目标是让人类与 coding agent
在最少阅读量下获得正确上下文，并避免同一事实复制到多个文件后发生漂移。

## Core Rule - One Fact, One Authoritative Home

同一事实只能有一个权威来源。其他文件可以链接或简短提示，但不复制易变化的
版本号、测试数量、artifact 状态或 active task 细节。

## Document Responsibilities

| 文件 | 职责 | 更新方式 |
| --- | --- | --- |
| `README.md` | 用户/开发者入口、安装、运行、测试、打包 | 用户可见行为或命令变化时更新 |
| `docs/PROJECT_STATE.md` | 当前已验证事实、release matrix、当前风险 | 验证后 replace stale facts |
| `docs/ROADMAP.md` | 已排序的产品和技术方向 | 优先级或完成条件变化时更新 |
| `docs/DECISION_LOG.md` | Accepted/Proposed/Superseded 长期决策 | append-oriented；用新决策 supersede 旧决策 |
| `AGENTS.md` | 所有 coding agent 的操作约束和必读顺序 | 规则变化时更新，保持简洁 |
| `CLAUDE.md` | Claude 兼容入口 | 只指向 `AGENTS.md` 和 Claude handoff |
| `DEEPSEEK.md` | DeepSeek 兼容入口 | 只指向 `AGENTS.md` 和 DeepSeek handoff |
| `FORCODEX.md` | Codex 当前 bounded assignment | replace，不积累历史 |
| `FORCLAUDE.md` | Claude 当前 bounded assignment/handoff | replace，不积累历史 |
| `FORDEEPSEEK.md` | DeepSeek 当前 bounded assignment/handoff | replace，不积累历史 |
| `MEMORY.md` | 高频、长期、跨任务提醒 | 只保留 durable context；不记录任务叙事 |
| `PROJECT_LOG.md` | 已完成且已验证工作的工程历史 | append-only，每个结果写一次 |
| `CHANGELOG.md` | 面向用户的版本变化 | release 时更新 |
| `PROJECT_INDEX.md` | 项目路径和文档/代码导航 | 结构变化时更新 |
| `MIGRATION_RECORD.md` | 2026-07-11 workspace migration 证据 | 历史证据，默认不改写 |

`DEARCLAUDE.md` 保留为旧工具兼容入口，不再承载独立规则。

## Source-of-Truth Precedence

发生冲突时按以下顺序判断：

1. 当前源码、实际 artifact 检查和本轮测试结果。
2. `docs/PROJECT_STATE.md` 中最近一次已验证状态。
3. 当前 agent 对应的 `FORCODEX.md` / `FORCLAUDE.md` / `FORDEEPSEEK.md`
   bounded assignment。
4. `docs/DECISION_LOG.md` 中 Accepted decisions。
5. `MEMORY.md` 的 durable reminders。
6. `PROJECT_LOG.md`、`CHANGELOG.md` 和 migration records 中的历史事实。

历史日志中的旧版本、hash 或测试数量不与当前状态冲突；它们描述的是过去的
accepted result。

## Required Read Order

### Any code or documentation change

1. 用 `pwd -P` 确认权威工作区。
2. 读取 `AGENTS.md`。
3. 读取 `docs/PROJECT_STATE.md`。
4. 读取当前 agent 对应的 bounded assignment。
5. 只在任务相关时读取 `docs/DECISION_LOG.md`、`docs/ROADMAP.md` 或 `MEMORY.md`。

### Architecture or product planning

读取 `PROJECT_STATE` → `ROADMAP` → `DECISION_LOG`；仅在需要历史原因时搜索
`PROJECT_LOG.md`。

### Release work

读取 `PROJECT_STATE` → current brief → `DECISION_LOG` 的 artifact decision →
packaging README。发布后更新 state、CHANGELOG、brief 和 PROJECT_LOG。

### Bug fix

读取 state 和相关 invariant；搜索 `PROJECT_LOG.md` 是否已有同类 defect；完成后
添加 focused regression test，并写一条 verified result。

## Information Lifecycle

### 1. Observation

尚未验证的发现只留在当前任务上下文或 bounded brief，不进入 `MEMORY.md`。

### 2. Verification

通过测试、artifact inspection 或可重复检查后：

- 当前事实写入 `PROJECT_STATE.md`；
- 完成结果追加到 `PROJECT_LOG.md`；
- 用户可见 release 变化写入 `CHANGELOG.md`。

### 3. Promotion

只有跨多个未来任务仍必须遵守的内容才进入长期层：

- 技术/产品选择 → `DECISION_LOG.md`；
- 高频操作提醒或关键入口 → `MEMORY.md`；
- 未来优先级与完成条件 → `ROADMAP.md`。

### 4. Retirement

- completed task 从 `FORCODEX.md` / `FORCLAUDE.md` / `FORDEEPSEEK.md` 移除；
- stale current fact 在 `PROJECT_STATE.md` 中替换；
- 被替代 decision 标为 Superseded，不删除；
- 历史日志不删除、不改写；
- `MEMORY.md` 中已被权威文档覆盖的重复内容删除并改为链接。

## Completion Write Matrix

| 变化类型 | 必须更新 | 条件更新 |
| --- | --- | --- |
| 纯 bug fix | `PROJECT_LOG`, current brief | `PROJECT_STATE`（若当前能力/风险改变） |
| 新功能 | `PROJECT_LOG`, `PROJECT_STATE`, current brief | `README`, `CHANGELOG`, `ROADMAP` |
| 架构决策 | `DECISION_LOG`, current brief | `ROADMAP`, `MEMORY` |
| Release | `PROJECT_STATE`, `CHANGELOG`, `PROJECT_LOG`, briefs | `README`, packaging docs |
| 文档治理 | `MEMORY_MANAGEMENT`, `PROJECT_INDEX`, `PROJECT_LOG` | `AGENTS`, compatibility entry files |

## Anti-Drift Rules

- 精确测试数量只写在 `PROJECT_STATE.md` 和当次 historical log。
- 当前版本与 artifact matrix 只写在 `PROJECT_STATE.md`；README 可显示公开 release
  版本，但不得暗示未打包源码已经发布。
- 永久 non-regression 原因写入 Accepted decision；agent 入口只保留简明规则。
- `FORCODEX.md`、`FORCLAUDE.md` 和 `FORDEEPSEEK.md` 不保存第二个
  completed-task section。
- `MEMORY.md` 建议保持在 120 行以内，不复制完整 architecture map。
- `AGENTS.md` 与 `CLAUDE.md` 不再维护两份相同的工程手册。
- 找不到 Git history 时，先保护现有文件；不要用 destructive reset/checkout。

## Review Cadence

- 每次 release：检查 state、roadmap、decision 和 active briefs 是否一致。
- 每次 architecture change：检查是否需要新 decision 或 supersede 旧 decision。
- 每月或文档超过职责范围时：删除 active files 中的历史叙事，保留链接。
- 发现冲突时：先验证 live state，再修正权威文件；不要批量修改历史记录。
