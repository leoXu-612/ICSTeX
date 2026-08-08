# ICSTeX

Current version: 2.1.0-beta.1. Current packaged release: 2.1.0-beta.1. The working source may be ahead of the packaged
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
final build rather than copying a preview or stale PDF. This source-only change
is not in 2.1.0-beta.1.

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

This creates both `dist/ICSTeX-2.1.0-beta.1.dmg` and a latest alias at
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
path such as `C:\Users\<name>\ICSTeX_Build_027`, then run the batch file there.
Do not build from a `C:\Mac\...` shared-folder path.

The build helper ignores unreachable `localhost`/`127.0.0.1` proxy variables
for its own `pip` subprocess without changing Windows proxy settings. For an
offline fallback, place `pylatexenc-2.10-py3-none-any.whl` in the project root
and run the same command again.

On Windows this creates `dist\ICSTeX-2.1.0-beta.1-Windows.zip` plus the latest alias
`dist\ICSTeX-Windows.zip`. If Inno Setup is installed and `iscc` is on `PATH`,
it also creates `dist\ICSTeX-2.1.0-beta.1-Setup.exe`.

The package does not bundle a LaTeX distribution; users need MacTeX, TeX Live,
or MiKTeX installed separately.
