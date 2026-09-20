# ICSTeX 应用内更新：实现与发布边界

日期：2026-09-08。本文取代同日的自定义 JSON 更新目录提案；长期决策为 D020。

## 结论与当前状态

客户端源码已接入 macOS Sparkle 2.9.6 与 Windows WinSparkle 0.9.4。
Qt 负责中文入口、联网同意、定期检查和全部窗口的保存退出；原生更新库负责
appcast、下载、签名验证和安装交接，不另写密码协议或通用文件替换引擎。

这不是已开放的线上升级服务。仓库没有真实更新源配置或签名密钥，普通源码运行
和默认打包均保持离线。首个带更新器、公钥和固定渠道的版本仍需手动安装。
实际双版本升级、平台签名和失败恢复验收完成后，才能发布可自动更新的安装包。

## 为什么采用两套原生库

Velopack 有直接适用于 PySide6 的示例，曾作为统一方案优先评估。但检查 1.2.0
的 macOS apply 源码后发现：新 bundle 替换路径未验证代码签名，且新应用移动失败后
仍可能清理承载旧应用的临时目录。因此本轮不采用它。依据是
[上游问题 975](https://github.com/velopack/velopack/issues/975) 与
[1.2.0 macOS apply 源码](https://github.com/velopack/velopack/blob/1.2.0/src/bins/src/commands/apply_osx_impl.rs)，
不代表对所有后续版本的结论。

选择 Sparkle/WinSparkle 增加了两个很薄的平台适配层，但能直接复用各自的原生
更新界面与签名下载流程。SDK 固定版本及下载摘要在 `packaging/native_updates.py`；
不能用后续 SDK 替换现有文件而跳过重新审查和测试。

## 已实现的用户行为

- “帮助 → 软件更新…”显示当前版本、固定渠道、更新源主机和状态；macOS 菜单
  位置由系统 ApplicationSpecificRole 处理。源码版及未配置安装版明确显示不可用。
- 自动检查默认关闭；用户开启后持久保存，启动延后 30 秒尝试，运行期间按 24 小时
  间隔检查。失败也记录尝试时间，避免联网重试循环。原生库自身的定时检查关闭。
- 同一应用进程的全部窗口共用一个控制器，首次明确检查或已同意的定期检查才加载
  原生库。检查错误不显示“已是最新版”。不在应用关闭后运行 daemon 或推送服务。
- 下载和安装由用户在原生窗口确认；不自动下载，不热替换运行中的 Python/Qt/JS。
  不上传项目、正文、日志、PDF 或截图；公开服务器仍可见连接 IP 和常规请求信息。
- 安装前先检查全部窗口再保存：用户取消、后续文档保存失败、外部冲突、编译/导出、
  图片导入、OCR 安装/任务、打开的编辑对话框或 Block 项目均可阻止安装。
  只有全部保存成功后短暂冻结窗口；取消或启动安装器失败会恢复编辑。
- 原生 Windows worker 回调经 Qt 主线程执行文档检查。最终退出复用现有
  `MainWindow.closeEvent`，清理编译器、watcher、统计 worker 和日志桥，不绕过保存逻辑。

普通保存不会切换光标或滚动位置；未命名文档可通过现有“另存为”完成明确保存，
拒绝另存会保留全部窗口。已经成功的保存不会因为随后取消更新而撤销。

## 代码与信任分工

| 层 | 入口 | 责任 |
| --- | --- | --- |
| 纯规则 | `app/core/app_updates.py` | 严格构建配置、进程架构、检查间隔、同安装程序的只读进程检查 |
| Qt 界面/生命周期 | `app/gui/update_dialog.py`、`app_update_controller.py` | 中文设置、同意状态、应用级单例、全窗口保存退出 |
| 原生适配 | `app/gui/update_backends.py`、`packaging/native_updates/sparkle_bridge.m` | 固定 C API、回调生命期/线程、原生检查和安装交接 |
| 构建接入 | `packaging/native_updates.py`、两个 PyInstaller spec | 固定 SDK 摘要、按目标暂存、可选配置/库/许可证嵌入 |

运行时只读取打包资源 `app/assets/app-update.json`，不从项目、当前目录或环境变量
加载更新配置/代码。`ICSTEX_UPDATE_RUNTIME` 仅供构建时显式启用。配置必须与当前
源码版本、平台和进程架构匹配，并包含正整数发布序号、stable/beta 固定渠道、
公共 HTTPS appcast 和 32 字节 Ed25519 公钥。发布序号而非版本字符串用于原生排序。

macOS 同时要求签名 appcast、归档解压前签名验证，并将 signed-feed 失败后的
宽限降级关闭。还须完成实际应用的 Developer ID 签名、公证及嵌套 helper 验收。
Windows 使用 HTTPS appcast 和 Ed25519 安装器签名；**不声称其 appcast 元数据本身
具备 Sparkle 相同的签名认证**。应用忽略远程 installerArguments，只启动原生库
已验证的本地 EXE，并要求一次性的应用退出授权；不回退到远程命令行。

库负责其网络重定向、缓存、下载和版本协议；Qt 不增加第二套下载器。最低系统版本、
版本排序、渠道隔离和签名异常须在实际 feed/安装器验收中证明，不能用配置单测替代。

## 发布侧接入

维护者操作见 [`packaging/UPDATES.md`](../packaging/UPDATES.md)。沿用 GitHub Release
托管版本化完整包，静态 HTTPS 站点托管按系统/架构/渠道分开的原生 appcast。
`website/release.json` 仍只服务网站展示，不是原生更新 feed；不新增自定义签名 JSON。
实际公共 endpoint 尚未发布，不在源码中填入猜测地址或测试公钥。

所有包、appcast 与网站展示应来自同一份已验收发布记录。先上传并匿名核验各平台
签名资产，最后发布对应 feed；失败平台维持旧 feed，不把 ARM64 包冒充 x64。
公开版本和序号必须递增，不覆盖同名历史资产。初版渠道由安装包固定，不提供
运行时切换渠道或自动降级。发布由维护者在本机执行，不使用 GitHub Actions。

macOS 使用签名完整应用归档；Windows 初版只接受匹配架构的安装版 EXE。
现有 Windows portable ZIP 不直接原地升级，须先人工迁移到受支持安装形态。
Inno Setup 的架构、版本、稳定 AppId、原安装路径与权限范围仍是发布端待验收工作。

## 验证与明确限制

源码回归及原生 UI/SDK 探针结果见 `docs/PROJECT_STATE.md` 和 `PROJECT_LOG.md`。
UI 合成截图与报告：`docs/data/app-updates-2026-09-08/`；重现入口：
`tools/probe_app_updates.py`。SDK 暂存验证覆盖 macOS arm64/x86_64 桥与 Windows
arm64/x64 DLL 的实际文件架构；只有本机 arm64 桥经过加载验证，Windows 未执行。

进程检查在 macOS 比较同一可执行路径、Windows 保守比较同名进程；失败时阻止安装。
这不是跨进程安装锁，不能阻止检查后新开实例。最终安装器必须验证文件占用、外部
MCP/其他进程及并发安装，不能杀掉外部 Harness 或把仅 GUI 单例当作充分保护。

未实现自定义会话恢复、启动回执或自动回滚。签名下载不是安装事务保证，尤其不能
推定 Inno Setup 能恢复任何中断。发布门槛包括 N→N+1 真实升级、错误签名、离线、
取消保存、权限/磁盘不足、安装中断、新版启动失败及从外部重装旧可信包。
不修改学生项目、外部 TeX/OCR 环境或项目格式；应用可重装不等于文档可回滚。

原生接口依据：
[Sparkle 集成](https://sparkle-project.org/documentation/)、
[配置](https://sparkle-project.org/documentation/customization/)、
[非 Xcode 签名](https://sparkle-project.org/documentation/sandboxing/)、
[WinSparkle 集成](https://winsparkle.org/guides/integrating-winsparkle/)、
[发布](https://winsparkle.org/guides/publishing-updates/) 与
[回调](https://winsparkle.org/c-api/callbacks/)。
