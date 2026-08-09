# Release Website Presentation Contracts

这些属性是 `release/release-manifest.json → website/release.json → app.js → HTML` 的
展示层接口。页面可以改变布局和文案，但不能把它们改成硬编码发行事实。

## Text bindings

| Attribute | Allowed values | Source |
| --- | --- | --- |
| `data-release="version"` | `version` | generated `release.json` |
| `data-release="tag"` | `tag` | generated `release.json` |
| `data-release="channel"` | `channel` | generated `release.json` |
| `data-release="name"` | `release_name` | generated `release.json` |

## Links

| Attribute | Meaning | Runtime rule |
| --- | --- | --- |
| `data-release-link="repository"` | repository | disabled while repository is private |
| `data-release-link="issues"` | repository issues | disabled while repository is private |
| `data-release-link="releases"` | all GitHub Releases | disabled while repository is private |
| `data-release-link="limitations"` | current known limitations | resolved against published tag |
| `data-release-document="NAME"` | release document | `NAME` must appear in `documents` |

## Assets and checksums

| Attribute | Meaning |
| --- | --- |
| `data-release-download="macos-primary"` | manifest asset with `primary_download: true` on macOS |
| `data-release-download="macos-dmg"` | macOS DMG asset |
| `data-release-download="macos-zip"` | macOS ZIP asset |
| `data-release-download="windows-arm64"` | Windows asset whose architecture contains ARM64 |
| `data-release-sha="KEY"` | SHA-256 for the corresponding asset key |
| `data-release-limitations` | list populated from `limitations[]` |
| `data-release-availability` | publication / download status message |

Downloads must remain disabled until `github_repository_public && github_release_published`
is true. `app.js` resolves all URLs from the generated projection; HTML and JavaScript must not
duplicate a release URL, version, tag, SHA, or publication state.
