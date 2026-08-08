# ICSTeX 模块化排版 MVP 最终实施报告

依据 `deep-research-report.md` 任务清单执行。本报告为最终交付物之一，
记录实际架构、Schema 版本、能力矩阵、测试统计、CI 状态、Demo 路径、
已知限制与后续建议。所有事实以代码、测试与仓库提交为准。

## 1. 最终架构图

```text
Project(icstex.project.json)
  ├── BlockRegistry (.icstex/blocks.json)
  │     ├── text / heading / quote / list / rawLatex
  │     ├── formula  (FormulaBlockAdapter: 受管 AST + latexCache)
  │     ├── image
  │     └── table    (TableData + TableEditorModel)
  ├── LayoutTree (.icstex/layouts.json)
  │     └── Row / Column / Grid / FullWidth（BlockSlot 引用 Block ID）
  ├── DocumentTheme (styles/document-theme.json -> .sty)
  └── AppTheme（仅控制 UI，永不进入 LaTeX）
          │
          ▼
  Layout Solver（权重/gap/minWidth/回退/嵌套/长表入盒检查）
          ▼
  Stable LaTeX（minipage + \input{blocks/*.tex} + % ICSTEX: 机器注释）
          ▼
  CompileManager（PREVIEW/FINAL、超时、取消、失败保留旧 PDF）
          ▼
  PDF（Qt pdf_panel / 控制台去抖自动预览）
```

数据流与安全边界：外部 CSV/XLSX/剪贴板 → 适配器（仅缓存值、不执行公式/宏、
大小上限）→ TableData；SourceRegistry 追踪链接源（ok/missing/moved/changed/
unsafe）；三方合并 Base/Remote/Local；导出包排除缓存/密钥/绝对路径并生成
manifest。

## 2. Schema 版本（全部 1.0.0，JSON Schema Draft 2020-12）

Block、Layout、Project、AppTheme、DocumentTheme、Source 六个 Schema 均由
`app/core/blocks/schema.py` 提供运行时校验（jsonschema 4.26）。

## 3. 完成能力矩阵

| 能力 | 实现 | 证据 |
| --- | --- | --- |
| Block 类型 | text/heading/quote/list/rawLatex/formula/image/table | Schema 枚举 + 8 类 fixture 测试 |
| 布局容器 | Row/Column/Grid/FullWidth + BlockSlot（拖拽重排） | solver/renderer/2×2 编译测试 |
| 表格导入 | CSV RFC4180+编码、XLSX 多 Sheet/范围/合并、剪贴板 TSV/HTML | 适配器测试 |
| 表格渲染 | tabular/booktabs、tabularx、longtable、siunitx S、multicolumn/multirow | golden + xelatex 编译测试 |
| 链接同步 | SourceRegistry + 三方合并 + 冲突 UI | merge/source 测试 |
| 主题 | AppTheme（不进 PDF）/DocumentTheme（geometry/字体/标题/表格 → .sty） | 主题测试 + 编译测试 |
| 编译 | 防抖合并、单进程、超时 TIMEOUT、取消、旧 PDF 保留 | compiler/pdf_state 测试 |
| 诊断 | LaTeX 行号 → Block/布局槽位（% ICSTEX:BEGIN/END） | source_map 测试 |
| 导出 | 可移植包（manifest+sha256、排除项）、空目录可编译 | export/demo 测试 |
| 安全 | 路径穿越拒绝、超大文件上限、公式/宏不执行 | security 测试 |
| GUI | 控制台：布局/表格/公式/同步/主题/导出/实时预览/项目加载 | tests/test_blocks_gui.py |

## 4. 测试统计

```bash
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
# 620 tests passed（本机，2026-08-07 复跑；含 golden、编译、安全、确定性、GUI）
```

本地 CI 模拟 `tools/run_mvp_ci.sh` 完整通过（compileall → ubuntu 子集 →
全套件 → Demo 构建）。

## 5. CI 状态（截至本报告）

- workflow：`.github/workflows/modular-layout.yml`（ubuntu 单元/schema/golden；
  macOS 全套件 + Demo + artifacts 上传）。
- ubuntu 任务在实跑中已绿（22s）。
- macOS 任务：TeX 安装已修复（`longtable/tabularx` 属 tools collection，
  已从 tlmgr 清单移除）并安装成功。挂起根因已从超时运行日志定位：
  `BlockProjectDialog._build_pdf_sync` 的预览编译无超时，且超时/停止只终止
  直接子进程（latexmk），xelatex 引擎子进程残留并持有管道，导致后续
  `communicate()` 永久阻塞（表现为静默 28 分钟至 job 超时、清理时残留
  xetex 孤儿进程）。已修复：编译进程以独立进程组启动，超时/停止整组终止
  （POSIX `killpg`，Windows `taskkill /T /F`）；预览编译加 300 秒超时；
  新增进程树终止回归测试。**恢复额度并推送后**按 `-v`/TIMEOUT 日志复核。
- 分支 `feature/modular-layout-mvp` 已推送过并建立 Draft PR #1；当前按维护者
  指示暂停推送（Actions 额度耗尽）。

## 6. Demo 路径

`demo/`：icstex.project.json、.icstex/blocks|layouts|sources.json、main.tex、
blocks/*.tex、styles/icstex-generated.sty、assets/images/apparatus.png、
data/snapshots/results.xlsx、output/demo.pdf（2×2 田字格：实验装置图 +
链接 Excel 表（含本地补丁）+ 速率公式 + 交叉引用分析文本，45:55 Row 组成）。
导出包已在空临时目录编译成功（测试证明）。

## 7. 已知限制

- Grid 等宽（45:55 通过 Row 权重实现）；垂直合并已支持（multirow）。
- `.sty` 未覆盖 titlesec 权重样式细节；两栏切换交由 documentclass。
- 超时/停止已按进程组终止整个编译树（含 latexmk 派生的引擎子进程）；
  Windows 路径依赖 `taskkill /T /F`，未做 POSIX 信号模拟。
- 像素级拖拽画布未实现（列表多选 + 槽位拖拽重排已满足清单验收点）。
- PDF.js 不适用（Python 栈沿用 Qt pdf_panel）；Electron 安全边界不适用。
- GitHub Actions 实跑唯一剩余障碍是账户计费/支出上限
  （“recent account payments have failed or your spending limit needs to be
  increased”），需在 GitHub Billing 设置处理；恢复后重推即可复核 CI。

## 8. 后续建议

1. 修复 GitHub 账户计费/支出上限后重推分支，按 `-v`/TIMEOUT 日志复核 macOS
   套件（进程树终止 + 预览编译超时已提交，预期不再静默挂起）。
2. 合并 `modular-layout.yml` 到 main 使其正式注册。
3. 完成最终门禁宣告（P0 全部完成、无数据丢失、导出无敏感路径、Demo 空环境
   可编译、同输入稳定 LaTeX、公式编辑器无回归——均已满足，待 CI 绿收尾）。
