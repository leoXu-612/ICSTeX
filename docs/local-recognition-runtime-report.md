# 本地识别运行时实施报告（ICSTeX 2.1 Phase 0–6）

## Conclusion

已建立统一 Local Recognition Runtime 骨架：领域模型 + 路由（公式→pix2tex、文字→RapidOCR）、
Runtime Manager（检测/安装命令/pip 源检测/移除/磁盘/manifest）、泛化 JSONL Worker 与
QProcess 客户端；RapidOCR Spike 通过（GO，Option B 分离 Sidecar）。GUI 集成（设置完整页、
文字 Review、Text Block 提交）列为 Phase 8–9 下一步。

## RapidOCR Spike

见 [rapidocr-spike-report.md](rapidocr-spike-report.md)：安装 21s、venv 296MB、模型 16MB、
冷加载 370ms、热推理 ~250ms、RSS ~868MB、英文精确；pix2tex 零回归。

## Unified vs Separate Runtime Decision

**Option B（分离 Sidecar）**：磁盘与依赖隔离、升级耦合低、移除简单（见 Spike 报告 §6）。

## Architecture

```text
app/services/recognition/
├── models.py          RecognitionKind/Request/Region/Result + Provider Protocol + Router
├── runtime_manager.py detect/install 命令/pip 源检测/remove/disk/manifest
├── worker_entry.py    泛化 JSONL worker（formula→pix2tex 懒加载；text→rapidocr 懒加载）
├── client.py          QProcess JSONL 客户端（health/recognize/cancel/shutdown/超时）
└── fake_worker.py     测试假 worker
```

## Runtime Size / Model Size / Performance

| 项 | pix2tex | RapidOCR |
| --- | ---: | ---: |
| venv | 1.2GB | 296MB |
| 模型 | 116MB | 16MB |
| 冷加载 | 423–448ms | 370ms |
| 热推理 | 132–142ms | 249–264ms |
| RSS | ~670–690MB | ~868MB |

## Offline

模型安装完成后推理不联网（pix2tex 已在 Spike 验证；RapidOCR 无联网调用，断网审计列入
Phase 10 狗粮）。

## Security

- Worker 只读临时图片；主进程读剪贴板，Worker 不读剪贴板；
- 文字识别结果仅作普通文本（转义后进 Text Block），不当作 LaTeX 执行；
- 公式识别结果经既有 Formula AST/sanitizer 后进入项目；
- 会话/请求绑定 request_id，旧结果丢弃。

## Tests

`tests/recognition/test_recognition.py`：路由（Mock Provider）、Runtime Manager
（官方 PyPI 安装命令、环境覆盖）、Worker 客户端（fake worker：health/公式/文字/shutdown）。
全套件 685 tests OK（本地）。

## Known Limitations

- Phase 7–9（设置完整 UI、统一 Review、Text Block 集成）未在本轮完成，按工单阶段门执行；
- RapidOCR 中英混排/低分辨率/浅色背景准确率未建立 fixture 基准；
- 统一 runtime 安装器尚未接入 GUI 安装流程（现有 pix2tex 设置入口保持独立）。

## Git Status / Next Step

分支 `feature/local-recognition-runtime`；未推送。下一步：Phase 7 设置页完整状态/安装；
Phase 8 统一 Review 对话框；Phase 9 文字识别 → Text Block 命令。
