# FORCODEX.md

当前交接（2026-10-02）：工作台分区、顶部分组和布局记忆已实现并推送PR #9；
本机安装尚未完成，因宿主ChatGPT/Codex的Autoupdate仍在运行而停止在安全替换之前。
实际实现位于当前附加工作树，分支 codex/workbench-layout。基线为已推送的
7284b20（此前导出状态/性能工作独立留痕），app7f0048e3 / app+tests f2f078b0。

复用现有 QAction、项目导航、源码/PDF splitter 和控制台。宽屏清晰分区，窄屏继续
折叠避让；只补现有分栏比例/控制台尺寸的设置读写，不引入布局框架或重建控件。
保留 ICSTeX 配色、中文文案、原有编译、文件、root/build/revision 和导出保护。
不新增后台刷新、联网、动画或全局 QSS 热路径，不重做已结束的性能实验。

当前应用源码对应6e1603c：app7cb9d8f6 / app+tests7a5cabf3。最终preflight完整执行
1902项：1891通过、11项安装互斥环境错误，原始退出1不可改称通过；详见PROJECT_STATE。
原生宽窗布局、真实编译、导出入口取消和分栏重启已验证；窄窗直接退出另有复现及17项
相关专项。不要重开设计、扩大测试矩阵或再跑旧性能实验。

宿主更新自然退出后，先检查已安装helper --idle，再仅运行
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_update_install_guard，
核对应用/测试摘要未变并保留新收据；不要重复已通过且未改的1891项。
确认门槛后沿用spec及已准备的Beta4 updater runtime打包，验证源码/产物一致与签名；
完整备份旧安装版，再用InstallationLease安全替换并核对实际运行路径/可见布局。
若宿主更新仍存在，不终止它、伪造idle或弱化保护；用户文稿未保存时先交还用户处理。
GitHub通过当前任务PR留痕，不直接推main、不启用Actions、不自动合并。仅本机安装，
不修改公开版本、feed或网站。当前安装版仍为自动导出状态版，未打新包或覆盖。
