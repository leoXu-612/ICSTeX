# ICSTeX Workspace Migration Record

迁移日期：2026-07-11（Asia/Shanghai）

## 路径

- 原工作区：`<legacy-workspace>`
- 新工作区：`<repo-root>`
- 备份目录：`<private-backup-root>`

## 迁移策略

1. 在原工作区生成稳定文件索引 `PROJECT_FILE_INDEX.sha256`。
2. 创建包含源码、测试、文档、发行包和历史构建产物的迁移前备份。
3. 将项目复制到独立的新工作区，不覆盖 `ICS-Project-` 中的其他项目。
4. 清除并重建可再生的 Python 索引/字节码缓存。
5. 在新工作区校验文件索引，并运行 compileall、全部测试和 packaging preflight。
6. 新工作区验证后成为唯一权威工作区；旧目录暂时保留，不自动删除。

## 备份记录

- 备份文件：`ICSTeX-pre-move-20260711-2326-CST.tar.gz`
- 备份大小：945 MB。
- 备份 SHA-256：`5039ff2da338090089185b8ae1f2cd59aa6b3211638043ddb5ae45603a246253`
- gzip 完整性检查：通过。
- 稳定文件索引：976 项；索引 SHA-256
  `dcd9399247b729e302934fdf747406064caeba807b306eace6c5a55e4c14305b`。

索引和备份排除 `.DS_Store`、`__pycache__`、`*.pyc`、watch 状态和
Claude lock 文件。这些内容由系统自动改写，不属于项目权威数据。
索引另外排除会在验证结束后更新的 `MIGRATION_RECORD.md`，避免索引自引用；
也排除已完整备份、但应在新路径重新生成的 `build/`。

## 验证记录

- 迁移结果：完成。
- 新工作区大小：856 MB（重建缓存后）；`build/` 未复制。
- 自动化基线：298 项测试。
- 原工作区稳定索引校验：976/976 通过。
- 原工作区 `bash packaging/preflight.sh`：298 项测试通过，preflight 通过。
- 新工作区稳定索引校验：976/976 通过。
- 源目录到新目录 `rsync --checksum --dry-run`：无内容差异，仅目录时间戳差异。
- 新工作区 compileall：通过。
- 新工作区 unittest：298 项通过。
- 新工作区 `bash packaging/preflight.sh`：通过。
- 新工作区 watcher locale 已规范化，并成功建立非空基线。
- 当前目录不是 Git 仓库，因此使用压缩备份、SHA-256 内容索引和
  `rsync --checksum` 保证可恢复性与完整性。

## 复制执行记录

迁移使用以下排除规则复制，避免把旧路径缓存带入新工作区：

```bash
test ! -e "<repo-root>"
mkdir "<repo-root>"
rsync -a \
  --exclude='/build/' \
  --exclude='.DS_Store' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.codex_watch_state' \
  --exclude='.claude/scheduled_tasks.lock' \
  "<legacy-workspace>/" \
  "<repo-root>/"
```

复制后已在新根目录完成索引、compileall、298 项测试和 preflight 验证。

## 切换规则

- Codex 当前任务仍绑定旧工作区；下一任务必须从新路径打开工作区。
- Claude Code 需结束旧 cwd 中的会话，再从新路径启动。
- 确认两端均从新路径工作后，才考虑归档或删除旧目录。
