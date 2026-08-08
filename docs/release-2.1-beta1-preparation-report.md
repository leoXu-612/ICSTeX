# ICSTeX 2.1.0-beta.1 Release Preparation Report

更新时间：2026-08-08（Asia/Taipei）

## 1. Release Summary

- Version / tag: `2.1.0-beta.1` / `v2.1.0-beta.1`
- Channel: Beta — Formula Intelligence
- Product boundary: 本地科研写作基础设施；不静默上传项目、日志、PDF 或截图。
- 发布真值：GitHub Release 资产；官网只展示状态和跳转，不复制二进制制品。

## 2. Commit and Branch State

- Release branch: `release/2.1`。
- 原有本地标签曾指向 `6de8146`；在最终 Release commit 和门禁完成前不得推送或移动。
- 本报告记录的是本地准备状态，不是公开发布声明。

## 3. Validation Results

- `python3 tools/release_prepare.py --check`：通过（生成的 `website/release.json` 与
  `release/release-manifest.json` 一致，Release assets SHA-256 一致）。
- `python3 -m unittest tests.test_release_site`：6 tests passed。
- `bash packaging/preflight.sh`：716 tests passed；版本化 macOS DMG 与 Windows ARM64
  ZIP 均被识别，Windows 仍保留与其验证范围相符的限制说明。
- `bash tools/run_mvp_ci.sh`：72 项模块化子集、716 项完整套件和 Demo 构建均通过。
- 静态页面通过真实浏览器检查：1440 px 与 375 px 视口可渲染，语义导航、焦点跳转、
  禁用的未发布下载项和 `prefers-reduced-motion` 均已实现；未发现浏览器 console error。

## 4. Artifact Inventory and Checksums

| Asset | Status | SHA-256 source |
| --- | --- | --- |
| macOS arm64 DMG | Verified | `release/release-manifest.json` |
| macOS arm64 ZIP | Verified | `release/release-manifest.json` |
| Source ZIP | Verified | `release/release-manifest.json` |
| Windows ARM64 ZIP | Developer Beta, launch-only verification | `release/release-manifest.json` |
| Windows x64 ZIP / Setup | Not available | Not applicable |

## 5. Website Verification

- Source: `website/` only; HTML/CSS/vanilla JavaScript, no account, analytics,
  backend, CMS, CDN fonts or binary duplication.
- Metadata: `website/release.json` is generated; its `github_release_published`
  value is currently `false`, so the macOS download control is deliberately
  disabled until GitHub Release publication is verified.
- Reused product assets are checked-in UI screenshots and an existing project
  application icon; no personal documents or screenshots are used.

## 6. Design Handoff

- Figma reference: [ICSTeX 2.1 Beta 1 Release Website](https://www.figma.com/design/14Y4KGsKuhXakNd7qPzyml?node-id=1-2)。
- 该文件由本地已验证页面捕获，包含可编辑的 1703 × 5737 画板，用于视觉评审与后续
  设计协作。
- 捕获结果是 raw frames，不是独立组件库；`website/` 的静态源码与生成的
  `website/release.json` 仍是官网发布真值。

## 7. GitHub / Pages Publication State

- GitHub remote: `https://github.com/leoXu-612/ICSTeX.git`.
- No branch, tag, Release asset, GitHub Release or Pages deployment was pushed
  by this preparation work.
- The GitHub connector returned repository `404` for the configured account;
  CLI remote verification did not complete in the current network session.
- Pages uses a guarded `tools/deploy_release_site.sh`: `--prepare` is local;
  `--push` requires both an explicit maintainer decision and
  `ICSTEX_RELEASE_SITE_PUSH=1`.
- Local Pages rehearsal created the root `gh-pages` commit `434152e` containing
  only the 10 static site files. It has not been pushed or connected to GitHub
  Pages settings.

## 8. Follow-up Tasks and Known Limitations

1. Obtain a Windows x64 Windows-local build environment and Inno Setup.
2. Complete Windows TeX toolchain / source-to-PDF acceptance; do not promote the
   ARM64 developer artifact as generic Windows support.
3. Reauthenticate GitHub and Linear integrations before creating external Release
   objects or linked work items.
4. Obtain explicit approval before remote push, GitHub prerelease creation or
   public site deployment.
