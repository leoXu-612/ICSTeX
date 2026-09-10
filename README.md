# ICSTeX

Current version: 2.1.0-beta.2. Current packaged release: 2.1.0-beta.1. The working source may be ahead of the packaged
release; see [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md) for the exact boundary.

ICSTeX - ICC Student's TeX - is local research-writing infrastructure for ICC
students, delivered as a Python/PySide6 desktop application. It combines LaTeX
editing with live compilation, PDF preview, SyncTeX hooks, Word Count, error
parsing, beginner-friendly insertion tools, project templates, and packaging
scaffolding.

Recent builds also include an environment doctor, quick BibTeX/DOI/arXiv/URL
reference import, drag-and-drop figure insertion, visual table editing, project
health checks, and Chinese beginner-oriented error explanations.

In the current working source, automatic compilation can use a local fast-image
preview: statically referenced project PNG/JPEG assets, including common
`\graphicspath` forms, are cached as smaller proxies in `.icstex/`. Their LaTeX
natural size is preserved; manual Compile and Export PDF always use the original
images. Preview and final build state are isolated, and export waits for a current
final build rather than copying a preview or stale PDF. This dual preview/final
build path is included in 2.1.0-beta.1.

The newer working source and local development build also support double-clicking a current
fast-preview PDF to locate its original project source with SyncTeX. Stale or
rebuilding output cannot drive navigation. The source-to-PDF toolbar action still
requires a current final PDF, and preview PDFs remain ineligible for export.
Published release packages have not yet been updated with this follow-up.

The working source also adds “软件更新…” with opt-in daily checks and guarded
all-window save/exit, using Sparkle on macOS and WinSparkle on Windows. Source
runs and ordinary builds remain offline and unconfigured; public in-app upgrades
are not enabled. Maintainer integration and the signed-installation acceptance
gate are documented in [`packaging/UPDATES.md`](packaging/UPDATES.md).

ICSTeX also understands common LaTeX editor conventions such as
`% !TEX root = main.tex` and `% !TEX program = xelatex`, and can infer a root
file from `\input{...}`, `\include{...}`, and `\subfile{...}` relationships in
multi-file projects.
The source editor uses soft wrapping by default, so long LaTeX lines adapt to
the current editor width instead of requiring horizontal scrolling.
Source files are decoded strictly: UTF-8 BOM and common TeX encoding declarations
are detected, legacy encodings can be selected explicitly, and saves use an
atomic replace so an encoding error cannot truncate the original paper.

## Project documentation

The V1 development source on `codex/v1-development` adds **编译 → 提交检查** (or `Ctrl+Shift+J`) for
read-only checks of saved inputs, actual FINAL/PDF evidence, references,
resources and Word Count. Refresh never saves, compiles or uploads. Unknown
coverage is not a pass, and this is not academic or course certification.

Use **文件 → 项目配置…** to edit optional local preferences: a reference template,
engine recommendation, relative directory suggestions, word targets and static
check visibility. No course limits are supplied. Saving writes only
`.icstex/project-profile.json`; it does not replace source, create suggested
directories or change the active engine. Disabling retains the configuration.
External conflicts and unknown formats preserve the original; cancel and reopen
before retrying. These local source features are not in the published packages.

The local project wizard now previews Chinese-name destinations and templates,
offers an explicit engine choice, and creates only new directories. First
compilation remains an explicit action. A workspace row shows the current project,
compile root, save/PDF state and next step, with links to existing project tools.
The Block menu/header provides guarded Save, explicit FINAL and Stop. Save keeps
metadata and managed TeX together without compiling; external/unknown-file
conflicts retain the draft and refuse replacement. Close asks Save/Discard/Cancel;
Stop does not close the project. Unresolved `.icstex/block-write.pending` evidence
blocks further writes and is not an automatic recovery feature. Unapplied
Inspector properties now survive refresh/selection changes in memory and appear
in the pending-draft list. **应用修改** validates the captured object before one
Undo command; Discard, Save, close and FINAL require explicit draft handling.
Conflicts retain the draft, and pending properties cannot pass saved/FINAL checks.
This is not process-crash recovery or frozen delivery; see the
[property-draft evidence and remaining editor risks](docs/v1-m2-property-draft-verification-2026-09-11.md).
Multi-table and formula dialogs now preserve captured targets and pending edits;
table navigation/read-only checks no longer overwrite the first registry table.
Live cell input is included in Save/close decisions, and a changed formula target
retains accepted text without overwriting the newer model. Focused/native checks
and full regression pass. These changes are not complete editor
acceptance; see [secondary-editor evidence and limits](docs/v1-m2-editor-target-verification-2026-09-11.md).

Block image imports stage bytes before exclusive publication, preserve existing
assets, and reject observed unsafe paths or source changes. Drag errors leave the
failed item's model unchanged. Focused checks pass; native picker-to-FINAL and
Windows race acceptance remain incomplete. See the
[image-import evidence and limits](docs/v1-m2-image-import-verification-2026-09-11.md).

Block controls now wrap and scroll at small/high-scale sizes; narrow center areas
switch between **编辑 Block** and **查看 PDF**, keeping the same PDF and zoom.
The selected slot weight is editable and undoable. In inspector text, Tab still
inserts a tab; physical Control+Tab moves to Apply without applying, and
Control+Shift+Tab returns to alias. See the
[layout/keyboard evidence and limits](docs/v1-m2-block-layout-verification-2026-09-10.md).

- User guide (使用指引): [`docs/user-guide.md`](docs/user-guide.md)
- Current verified state: [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)
- Product and technical roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md)
- Architecture decisions: [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md)
- Project memory rules: [`docs/MEMORY_MANAGEMENT.md`](docs/MEMORY_MANAGEMENT.md)

## Download & first launch (下载后打不开？)

The macOS DMG is ad-hoc signed but not Developer ID signed or notarized, and the
Windows ZIP is not code-signed. The OS may show a security warning the first
time you open them; follow the per-platform first-launch guide:

- macOS（「无法验证开发者」）：见 [`packaging/README_macOS.md`](packaging/README_macOS.md) 的「第一次启动」。
- Windows（SmartScreen / 杀毒误报）：见 [`packaging/README_windows.md`](packaging/README_windows.md) 的「第一次启动」。

The current macOS 2.1.0-beta.1 DMG is an Apple Silicon (`arm64`) build, not an Intel
or Universal 2 build. Windows artifacts must be rebuilt and verified on Windows.

## Run

Install a LaTeX distribution first:

- macOS: MacTeX
- Windows: MiKTeX or TeX Live

Then install Python dependencies and launch:

```bash
python3 -m pip install -r requirements.txt
python3 -m app
```

After installing as a Python package, the console script is:

```bash
icstex
```

## Agent / Harness integration

ICSTeX includes an optional local stdio MCP adapter. It is bound to one project
root and starts read-only; write, compile, network, local recognition, input,
and export access must be granted by the host at startup.

```bash
python3 -m pip install -e '.[agent]'
icstex-mcp --project-root /absolute/path/to/project
```

For Codex CLI, register that same read-only command with:

```bash
codex mcp add icstex -- icstex-mcp --project-root /absolute/path/to/project
```

To work with multiple projects concurrently, register one separately named
stdio server per project root. Do not start multiple writable server processes
for the same root; the supported topology is one process per project, while one
process can service bounded concurrent reads and safely queue mutations.

Add only the capabilities needed for the current task, for example
`--allow-write --allow-compile`. External images require one or more
`--allow-input` paths, and exports require an existing `--export-root`.
Mutations use SHA-256 compare-and-swap checks and byte-exact, restorable
preimage snapshots.
The companion Agent instructions live in
[`skills/icstex-control/SKILL.md`](skills/icstex-control/SKILL.md).

The MCP server does not remote-control the GUI or see unsaved GUI buffers. Keep
the same project closed or read-only in ICSTeX while an Agent is mutating it.

The app detects `latexmk` or `pdflatex` on `PATH`. It writes build artifacts to
`.latex_build/` inside the project folder instead of polluting the source folder.
Fast-preview caches live separately under `.icstex/preview/`; the in-app clean
action removes both trees for the active root. Fast image preview can be disabled
in Settings without changing manual Compile or Export PDF behavior.
Use the in-app "环境" action to copy a complete LaTeX environment diagnostic
report when helping another user debug installation or PATH issues.
See `CHANGELOG.md` for the short user-facing update log.

## Test

```bash
python3 -m unittest discover -s tests
```

Run the preflight gate before packaging or sharing a build:

```bash
bash packaging/preflight.sh
```

## Package

Packaging needs an extra dependency that the runtime does not:

```bash
python3 -m pip install -r requirements.txt -r requirements-packaging.txt
```

macOS:

```bash
bash packaging/build_macos.sh
```

This creates both `dist/ICSTeX-2.1.0-beta.2.dmg` and a latest alias at
`dist/ICSTeX.dmg`. Share the versioned DMG when distributing test builds.

Windows:

```bat
packaging\build_windows.bat
```

To prepare a clean versioned source ZIP for transfer from macOS to a Windows
machine or VM:

```bash
bash packaging/build_source_archive.sh
```

Extract that archive on Windows, copy the extracted project to a Windows-local
path such as `C:\Users\<name>\ICSTeX_Build_210b1`, then run the batch file there.
Do not build from a `C:\Mac\...` shared-folder path.

The build helper ignores unreachable `localhost`/`127.0.0.1` proxy variables
for its own `pip` subprocess without changing Windows proxy settings. For an
offline fallback, place `pylatexenc-2.10-py3-none-any.whl` in the project root
and run the same command again.

On Windows this creates an architecture-specific ZIP such as
`dist\ICSTeX-2.1.0-beta.1-Windows-x64.zip` plus the matching latest alias.
An ARM64 Python build is labeled `Windows-arm64`; it is not a generic x64 build.
On x64, if Inno Setup is installed and `iscc` is on `PATH`, the script also
creates `dist\ICSTeX-2.1.0-beta.1-Windows-x64-Setup.exe`.

The package does not bundle a LaTeX distribution; users need MacTeX, TeX Live,
or MiKTeX installed separately.
