# FORCODEX.md

当前交接（2026-10-02）：首次编译/写作性能局部修复已实现，专项与原生主路径通过；
完整回归已执行，11 项安装互斥测试被宿主 ChatGPT/Codex 更新进程阻挡，未全部通过。
工作树：/Users/leo.xu/.codex/worktrees/github-workflow/ICSTeX，分支 codex/first-compile-session-perf。
复用这个已完成且干净的工作树，基于8ddfc13播种主树全部现有未提交改动；开始时 app5aece7ca、
app+tests8df33741 与当前已安装有效源码一致，不把旧HEAD误作基准。

主树 /Users/leo.xu/Desktop/Codex/ICS-Project-/ICSTeX 作为未改动应用源码基线，保留原分支/
索引和界面改动。测量用明确真实EE的隔离副本及小型合成补充，不改学生原稿或实际设置。
当前 app7f0048e3 / app+tests f2f078b0。实现仅涉及统计让行和关闭文稿残留释放；
原始 A-C-C-A、反例修复、末轮波动与原生验证见 PROJECT_STATE/PROJECT_LOG。
区分新进程/项目冷缓存与OS冷启动、阶段时间与完整时间、离屏观察与原生屏幕证据；
没有暖预览稳定提速、RSS下降或小时级稳定性结论。

并行只读审查/分文件实现，性能实测串行。每个候选先指定机制、最小判别和停止条件；
不复做压缩参数实验、不删文件/构建安全校验、不增加依赖、改全局样式或编译引擎。
compileall通过，1889项回归中1878通过、11项环境错误；当宿主Autoupdate自然退出后，
仅补跑 QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_update_install_guard，
不要杀宿主更新进程、伪造idle成功或重跑不相关全套。除此之外停止追加优化实验。
新源码不默认提交、推送、打包、安装或部署；主树安装版仍为上一有效版本。
