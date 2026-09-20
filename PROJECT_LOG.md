# ICSTeX Project Log

This file is the append-only history for completed work. Active handoff files
must link here instead of repeating old task details.

## Logging Policy

- Add one concise entry only after a task is complete and verified.
- Record date, outcome, important files, verification, and lasting warnings.
- Do not store open task lists, temporary plans, raw command output, or repeated architecture notes here.
- `FORCODEX.md`, `FORCLAUDE.md`, `MEMORY.md`, and `DEARCLAUDE.md` are replace-in-place active briefs, not logs.
- When an active brief is updated, remove completed work after adding its durable result here.

## 2026-06-10 - ICSTeX 0.2.0

- Renamed the application to ICSTeX - ICC Student's TeX.
- Added the app icon, macOS DMG scaffolding, beginner insertion tools, templates,
  references, labels, and project initialization.
- Distribution continued to require an external MacTeX/MiKTeX/TeX Live installation.

## 2026-06-12 - ICSTeX 0.2.1

- Improved Environment Doctor, feedback diagnostics, Word Count mode reporting,
  and macOS packaging guidance.
- Missing LaTeX tools stopped producing a modal warning at application startup.

## 2026-06-15 - ICSTeX 0.2.2

- Added source soft wrapping and its persistent setting.
- Improved multi-file root inference and feedback bundles.
- Fixed stale wrapping after insertion tools update the preamble with `setPlainText()`;
  the editor now forces a `NoWrap -> WidgetWidth` relayout.
- Switched file watching to `PollingObserver` for stable macOS behavior.

## 2026-06-19 - Reliability and Workflow Batches

- Added table reverse parsing, CSV/Excel paste, and opt-in DOI/arXiv metadata lookup.
- Fixed compile-process shutdown, engine switching races, background-tab PDF
  replacement, watcher reference leaks, external-save echo handling, and live
  `% !TEX program` refresh.
- Added strict source decoding and atomic text writes; source encoding failures no
  longer truncate or silently replace the original document.
- BibTeX writes, project initialization, image publication, and history restoration
  received equivalent corruption protections.

## 2026-06-30 - ICSTeX 0.2.3 Release

- Added six-category Word Count visualization and excluded `thebibliography` from
  Python fallback body counts to match `texcount` behavior.
- Added privacy-safe quick feedback bundles; raw logs and absolute paths are excluded.
- Added three-way save/discard/cancel close handling.
- Packaging dependency installation gained loopback-proxy recovery and local
  `pylatexenc` wheel fallback.
- macOS Apple Silicon DMG was rebuilt and verified. It is ad-hoc signed, not
  notarized, and not Intel/Universal 2.
- Release verification baseline was 211 tests. Windows matching artifacts still
  required a Windows-local rebuild.

## 2026-06-30 - Unreleased 0.2.4 UI Candidate

- Replaced platform `QStyle` icons with a bundled, licensed Lucide SVG subset.
- Reworked the toolbar into compact project/workspace/compile/check groups.
- Replaced nine cramped toolbox tabs with a vertical icon rail and stacked pages.
- Added a PDF empty state, icon PDF controls, compile status pills, error/check
  counts, a compact auto/manual switch, and a collapsible Console header.
- Refined theme tokens, syntax colors, welcome-page spacing, splitter behavior,
  and the ICSTeX red accent.
- Added icon and offscreen visual regression tests at 1440x900, 1280x720, and
  1100x720. Compileall, 217 tests, and packaging preflight passed.
- Version metadata and packages intentionally remained 0.2.3 pending user acceptance.

## 2026-07-01 - PDF Refresh Verification

- Reverified the full manual and automatic compile paths with temporary real LaTeX
  documents, not mocks.
- Both paths saved the latest editor text, changed the generated PDF bytes, and
  reloaded PDF text containing the new marker in the internal viewer.
- A failed build intentionally leaves the last successful PDF visible; the Errors
  panel is the source of truth in that case.

## 2026-07-04 - ICSTeX 0.2.4 macOS Release

- Promoted the accepted UI candidate to version 0.2.4 across Python metadata,
  README files, CHANGELOG, macOS packaging, and Windows installer metadata.
- Windows build naming now produces `ICSTeX-0.2.4-Windows.zip`, a latest ZIP
  alias, and `ICSTeX-0.2.4-Setup.exe` when Inno Setup is available.
- Preflight and all 217 tests passed before packaging.
- Built `dist/ICSTeX-0.2.4.dmg`; frozen App smoke, arm64 architecture, signature
  integrity, mounted contents, and mounted App version 0.2.4 were verified.
- Versioned/latest DMGs share SHA-256
  `f73b9079b2a6cf349af8957eec6e8ebf53a5705e0ba6f4b9ce9e05ad872fcde8`.
- Windows 0.2.4 remains pending a Windows-local build and runtime verification.

## 2026-07-06 - Export PDF and Reveal-in-Finder Actions

- Added 文件 menu actions and PDF toolbar buttons for 导出 PDF (copy compiled
  PDF via save dialog) and 在 Finder/文件夹中显示 PDF (reveal in file manager,
  cross-platform: `open -R` / `explorer /select,` / folder URL fallback).
- Both actions are safe no-ops with a status-bar hint when no compiled PDF exists.
- Added regression test `test_export_and_reveal_pdf`; compileall and all 218
  tests passed.

## 2026-07-06 - PDF Export/Reveal Hardening (Slice 1, Part 3)

- Export/reveal actions and PDF toolbar buttons are now disabled until a
  non-empty successful PDF exists; state refreshes after every compile.
- Export refuses zero-byte PDFs and warns (with cancel) when the active source
  was edited after the last successful build, using file mtime plus unsaved-edit
  flags. Reveal keeps platform-safe argument lists with no shell interpolation.
- Added `test_export_pdf_rejects_empty_and_warns_when_stale` and extended the
  export/reveal test with disabled-state and argument-list assertions.
- compileall, all 219 tests, and packaging preflight passed.

## 2026-07-06 - Root-Scoped PDF Freshness State Machine and Compile Outcomes

- Added `app/core/pdf_state.py`: `PdfFreshness` six-state machine with one
  `PdfBuildRecord` per normalized compile root (magic-root/`\input` children
  share the root record), monotonic source revisions, and build-id guards so a
  late result from an older build can never overwrite newer state.
- Added `CompileOutcome` (8 values) to `app/core/compiler.py`; `CompileResult.ok`
  now derives from `outcome == SUCCESS` plus a non-empty PDF. User stop is
  detected via a lock-protected `_stop_requested` flag (works for negative and
  positive platform return codes); internal failures return `INTERNAL_ERROR`
  instead of crashing the Qt loop. No compile timeout was introduced.
- Added `app/core/compile_feedback.py`: the single CompileOutcome → Chinese
  title/detail/severity/next-action mapping and root-filename headlines; the
  first parsed LaTeX diagnostic leads, never the latexmk footer.
- GUI: `MainWindow` owns a `PdfStateStore`; edits dirty the shared root record,
  tab switches load only the active root's last successful PDF or call the new
  `PdfPanel.clear_pdf()`, background builds cannot touch the active viewer, and
  a persistent freshness banner sits above the PDF view. Export/Reveal enable
  from the active record; export warns on stale states and is atomic
  (temp file + `os.replace`, no partial file on failure). This fixes the
  release blocker where switching a.tex → b.tex could export a.pdf.
- Tests: new `test_pdf_state.py` (16), `test_compile_feedback.py` (6),
  `CompileOutcomeTests` (11), and `GuiPdfStateTests` (13) covering all required
  transition/outcome/GUI scenarios, including the offscreen two-document proof
  that an uncompiled tab cannot export another root's PDF.
- Verified: compileall passed, all 267 tests passed, packaging preflight passed.

## 2026-07-06 - PDF State Hardening Round 2 and 0.2.5 macOS Release

- External reload now marks the root record dirty immediately (banner shows
  待更新) and reschedules the compile on the reloaded tab's own root manager.
- Background builds no longer touch the active tab's status bar, timer,
  progress bar, or stop button; these indicators re-sync per root on tab
  switch (`MainWindow._sync_compile_indicators_to_active_root`).
- One shared `CompileManager` per normalized root (`window.compile_managers`):
  root and child tabs serialize builds instead of racing over `.latex_build`;
  closing a tab stops the manager only when no other tab shares it.
- Clean cache invalidates in-flight build ids (`invalidated_build_id`), so a
  late STOPPED/failed result cannot bounce 尚未编译 back to 编译失败.
- Save-As rebinds the PDF state record: viewer clears, export disables, and
  compile indicators re-sync when the compile root changes.
- Child dirty detection is now a recursive `\input`/`\include`/`\subfile`
  closure (`latex_dependency_closure`, cycle-safe, 200-file cap) cached per
  root and invalidated on saves/external reloads.
- `sync_pdf_to_source` uses only the active root's successful PDF; the global
  `PdfPanel.current_pdf` fallback is gone. `reveal_pdf` catches launch
  failures and shows a hint instead of raising.
- Tests: +14 (dependency closure, clean-cache invalidation, compile-queue
  serialization, and 10 GUI scenarios for the above). Total 281.
- Verified: compileall, 281 tests, and preflight passed; real-latexmk
  offscreen acceptance passed with two roots, a root+child project, and an
  external modification (7 checkpoints).
- Released macOS 0.2.5: version bumped across app/pyproject/README/CLAUDE/
  installer/READMEs, CHANGELOG entry added, `dist/ICSTeX-0.2.5.dmg` built
  (arm64, ad-hoc signed, not notarized), mounted contents verified at 0.2.5.
  SHA-256 3980bcfa1eb82a036b455e7006406b42afba6f16bfc4945657e0cafdc4f763ef.
- Windows 0.2.5 artifacts still require a Windows-local rebuild.

## 2026-07-08 - Template, Guide, and Root-State Polish

- Fixed two residual state issues: plain `\input{child}` files without
  `% !TEX root` now resolve to the parent root when creating compile managers,
  and Save-As removes the old unshared compile manager from
  `window.compile_managers`.
- Expanded built-in student templates with Extended Essay, Physics IA, Math IA,
  chemistry lab report, and Chinese XeLaTeX article.
- Added user template workflow: save current document as a personal template,
  import `.tex` templates, export selected templates, and refresh the template
  panel after changes.
- Added a local Chinese beginner guide available from the welcome page and Help
  menu, plus new toolbox insertions for section headings, piecewise functions,
  and quote blocks.
- UI polish: styled guide dialog, template selector, and help text using the
  existing neutral ICSTeX theme tokens.
- Stabilized the Windows-positive-returncode stop test by mocking the process
  result instead of relying on platform-specific shell signal timing.
- Verified: compileall passed; full test suite passed at 284 tests; packaging
  preflight passed and detected both versioned macOS DMG and Windows ZIP.

## 2026-07-08 - macOS 0.2.6 Release Build

- Promoted the template/guide/toolbox polish slice to version 0.2.6.
- Synced version metadata across `app/__init__.py`, `pyproject.toml`, README,
  packaging READMEs, CLAUDE/FOR* context, Windows installer metadata, and
  CHANGELOG.
- Built `dist/ICSTeX-0.2.6.dmg` and refreshed the latest alias
  `dist/ICSTeX.dmg`; both are 45 MB and share SHA-256
  `8aca1679a3c5ab17379230466b76adb55319ce2353b264f5499a8c4bef2a2a42`.
- Verified `dist/ICSTeX.app` code signature, bundle id `com.icstex.app`, and
  bundle versions `CFBundleShortVersionString = 0.2.6` /
  `CFBundleVersion = 0.2.6`.
- Mounted the DMG and confirmed it contains `ICSTeX.app`, `README.md`,
  `CHANGELOG.md`, and `Applications`.
- Verified: `bash packaging/preflight.sh` passed with 284 tests.
- Windows 0.2.6 artifacts still need a Windows-local rebuild before sharing
  with Windows users.

## 2026-07-11 - Word Count Visual Review Layer

- Reviewed the Word Count flow: `texcount` remains the primary numeric source,
  while ICSTeX's local parser now provides explanatory visual segments for the
  current editor text.
- Added `WordCountSegment` and `WordCountResult.visual_segments`, classifying
  visible text into effective body, headers, captions, inline math, display
  math, and numbers.
- Added a Turnitin-style colored preview to the Word Count panel, with legend
  and truncated rich-text rendering for long documents.
- Verified: `python3 -m compileall -q app tests` passed; full test suite passed
  at 285 tests.

## 2026-07-11 - Project-Aware Word Count Preview

- Reproduced and fixed the mismatch where `texcount -merge` counted included
  files but the colored explanation showed only the root buffer.
- Added deterministic, cycle-bounded project analysis for `input`, `include`,
  and `subfile`; preview segments now carry source-file labels.
- Word Count resolves the active compile root and passes every open buffer from
  that root as an in-memory override. A temporary shadow project lets real
  `texcount` see unsaved child text without modifying user files.
- Real `texcount` verification counted root plus an unsaved child as 9 words,
  visualized both files, and left the child file unchanged on disk.
- Include context is preserved: preamble child macro definitions are excluded
  from body text while title text remains categorized as a header.
- Shadow copies rewrite direct include targets, covering absolute includes and
  Windows cross-drive fallbacks without reading stale child content.
- Disk-only child sources now use strict declared-encoding detection: CP1252 /
  Latin-1 text is preserved, while undecodable files warn and are skipped rather
  than silently inserting replacement characters.
- Temporary shadow cleanup is asserted after successful and failed `texcount`
  execution.
- Python fallback tokenization now treats accented Unicode words and straight /
  curly apostrophes as one word while retaining per-character CJK counting.
- Claude independently reviewed the preceding 292-test project-aware slice with
  adversarial paths/cycles and a real 9-word `texcount` fixture; no defect was
  found. The later encoding/cleanup/Unicode delta remains a bounded follow-up.
- Verified: compileall, 296 tests, and packaging preflight passed.

## 2026-07-11 - Claude Delta Review: CP1252 texcount Boundary Fix

- Independent post-292 delta review (Claude): tokenization, cleanup assertions,
  and new tests all passed; one validated defect found at the texcount boundary.
- Defect: with no unsaved overrides, `_count_project_with_texcount` fed the raw
  disk tree to `texcount -utf8`; a declared-CP1252 child split accented words on
  invalid bytes, silently inflating totals (7 vs correct 6) and diverging from
  the UTF-8-normalized preview.
- Fix: `_ProjectAnalysis.needs_utf8_shadow` marks projects with any non-UTF-8
  disk source; such projects now always route through the UTF-8 shadow tree.
  Verified with real texcount: both paths return 6 == 6; disk bytes untouched.
- Regression: `test_declared_cp1252_child_uses_utf8_shadow_even_without_overrides`.
- Verification: compileall clean, 297 tests OK, packaging preflight passed.
  No version bump or packaging change.

## 2026-07-11 - Codex Counter-Review: Undecodable Child Isolation

- Codex tested the neighboring unknown-encoding path after Claude's CP1252 fix
  and reproduced another totals/preview mismatch with real `texcount`.
- Defect: an undecodable child was warned as skipped, but the no-override fast
  path still let `texcount -utf8` read its raw bytes; direct output was 5 words
  while the normalized project correctly counted only the 2 root words.
- Fix: unreadable or undecodable included children are represented by empty
  UTF-8 files inside the temporary shadow project. Include targets, including
  absolute paths, are rewritten to those placeholders; user files are never
  modified.
- Regression: `test_undecodable_child_is_skipped_by_texcount_without_overrides`.
- Real texcount verification returned 2 words and unchanged source bytes.
- Verification: compileall clean, 298 tests OK, packaging preflight passed.
  No version bump or packaging change.

## 2026-07-11 - ICSTeX 0.2.7 macOS Release

- Promoted the reviewed project-aware Word Count work to version 0.2.7 and
  synchronized app/package metadata, README files, Inno Setup, and CHANGELOG.
- Release gates passed: compileall clean, 298 tests OK, preflight passed.
- Built `dist/ICSTeX-0.2.7.dmg` and refreshed `dist/ICSTeX.dmg`; both SHA-256
  values are `cf09459e7aaddf0c7ce16930f108a7a965ebe8849e56b847c632e838f8453e1c`.
- Read-only mount verified ICSTeX.app, README.md, CHANGELOG.md, Applications
  link, bundle version 0.2.7, arm64 architecture, and ad-hoc signing. The mounted
  App passed strict deep code-sign validation and an offscreen cold-start test.
- During verification, the old `makehybrid` fallback was found to inject
  FinderInfo into bundled binaries and invalidate the mounted App signature.
  The fallback was removed; standard `hdiutil create` now must succeed, and the
  staging App is copied without extended attributes and verified before imaging.
- Package remains Apple Silicon only, ad-hoc signed, and not notarized.
  Windows 0.2.7 still requires a Windows-local rebuild and verification.

## 2026-07-11 - ICSTeX 0.2.7 Final DMG Refresh

- Corrected current documentation to distinguish ad-hoc signing from Developer
  ID signing/notarization, then rebuilt the complete package with the hardened
  standard `hdiutil create` workflow.
- Final `dist/ICSTeX-0.2.7.dmg` and latest alias SHA-256 is
  `b4ce9f668312aa2e308b3535c66021dce160ac127c886c780cb985b2e7caa7dc`;
  this supersedes intermediate 0.2.7 DMG hashes recorded earlier in the build
  investigation.
- Mounted README and CHANGELOG match source; bundle version is 0.2.7, the App is
  arm64/ad-hoc, and strict deep code-sign verification passes after mounting.

## 2026-07-11 - Windows 0.2.7 Transfer Package

- Added `packaging/build_source_archive.sh` to create a clean versioned source
  ZIP without macOS build products, caches, bytecode, or Finder metadata.
- Added `packaging/BUILD_WINDOWS.md` with shared-folder-to-local copy commands,
  build steps, a no-system-Python launch check, and MiKTeX/TeX Live validation.
- Added the pure-Python offline dependency
  `packaging/wheels/pylatexenc-2.10-py3-none-any.whl` (SHA-256
  `cbf8159f7200efffbfb3c0f53801d0a36e2d8679a40f0502f2bab0ac7e28c320`),
  which the existing dependency helper discovers before online requirements.
- Built `dist/ICSTeX-Source-0.2.7.zip` (SHA-256
  `4a66f4ddabf4b52f86c3c40c12a0a29ba30e9260234b8a413f7a1d91c03fce5d`).
- ZIP integrity passed; a fresh extraction passed preflight with 298 tests.
  The actual Windows executable/ZIP still requires a Windows-local build and
  launch/MiKTeX verification before distribution.

## 2026-07-12 - Workspace Migration to ICS-Project-

- Created a complete 945 MB pre-migration archive at
  `ICS-Project-/_backups/ICSTeX-pre-move-20260711-2326-CST.tar.gz`;
  gzip validation passed and SHA-256 is
  `5039ff2da338090089185b8ae1f2cd59aa6b3211638043ddb5ae45603a246253`.
- Migrated the authoritative workspace to this repository root
  (`ICS-Project-/ICSTeX`), preserving source,
  tests, documentation, release artifacts, and collaboration files.
- Excluded rebuildable `build/`, Python bytecode, Finder metadata, and
  transient watcher/Claude lock files. The old root remains as a rollback copy.
- Normalized the collaboration watcher to `en_US.UTF-8` because macOS lacks
  the inherited `C.UTF-8` locale and its Perl-backed `shasum` otherwise fails.
- New-root verification passed: 976/976 stable content hashes, compileall,
  298 unittest cases, and packaging preflight.

## 2026-07-13 - Code Review, PDF-State Debug, and UI Availability Polish

- Fixed a correctness defect where restoring a history snapshot replaced the
  editor with signals blocked but left the root-scoped PDF marked current;
  restore now marks the source dirty and reapplies soft-wrap options.
- Recent-project UI hides `.icstex`/`.latex_build` internals and maps files from
  those folders back to the real project root. The initial file tree now starts
  at Home rather than filesystem root.
- Added context-aware Save/Compile/Check/Word Count/Find/SyncTeX and PDF-toolbar
  enabled states plus accessible names for the engine, project tree, PDF page,
  and PDF search controls.
- Raised faint, option, and comment text to at least 4.5:1 editor contrast and
  resolved QSS font families from installed fonts.
- Added four focused regression/visual checks. Verified compileall, 302 tests,
  packaging preflight, and a real local `latexmk` source-to-PDF UI run.
- Source-only delta: no version bump and no DMG/ZIP rebuild; existing 0.2.7
  artifacts predate these fixes.

## 2026-07-13 - Mixed Chinese and English Font Stack

- Changed the global UI, source editor, and log typography to use SF Mono for
  Latin glyphs and Source Han Serif SC for Chinese glyphs, with compatible
  macOS/Windows fallbacks when the preferred families are unavailable.
- On macOS, load the complete built-in `.SF NS Mono` family before a partial
  user-installed `SF Mono`, preventing a Bold-only installation from forcing
  both English and Chinese text into a heavy weight.
- Added a font-resolution regression test and visually checked mixed Chinese,
  English, numbers, and LaTeX commands in the full workbench.
- Verified compileall, 303 tests, and packaging preflight. This remains a
  source-only delta; no version or package artifact was changed.

## 2026-07-14 - Documentation Architecture and Memory Governance

- Established `docs/PROJECT_STATE.md`, `docs/ROADMAP.md`,
  `docs/DECISION_LOG.md`, and `docs/MEMORY_MANAGEMENT.md` as the authoritative
  current-state, planning, decision, and context-lifecycle layers.
- Migrated durable product identity, architecture boundaries, release truth,
  privacy/file-safety rules, non-regression constraints, and future priorities
  from duplicated root-level context files into those new documents.
- Reduced `AGENTS.md` to operational rules; converted `CLAUDE.md` and
  `DEARCLAUDE.md` to compatibility entry points; reduced `MEMORY.md` to durable
  reminders; and refreshed `FORCODEX.md`, `FORCLAUDE.md`, `PROJECT_INDEX.md`,
  and README navigation without rewriting historical entries.
- Explicitly separated the post-0.2.7 verified source delta from existing 0.2.7
  artifacts and kept the next release-version choice pending.
- Documentation-only migration: no application source, version metadata, or
  generated package artifact changed. Verification passed: compileall clean and
  303 tests OK.

## 2026-07-14 - Role-Based Typography Refinement

- Replaced the global serif/monospace pairing with three explicit roles:
  SF Pro/PingFang-style sans fonts for normal controls, SF Mono/Source Han
  Serif SC for editors and logs, and sans Latin/serif Chinese for emphasis titles.
- Preserved the macOS built-in full SF Mono registration so a Bold-only user
  font cannot force English or Chinese editor text into an unintended weight.
- Expanded the font regression check to cover UI, editor, and heading stacks;
  actual glyph runs resolved to regular platform sans fonts for UI and regular
  SF Mono/Source Han Serif SC for the editor.
- Visually checked the 1280x720 workbench and verified compileall plus all 303
  offscreen tests. No version or generated package artifact was changed.

## 2026-08-01 - Isolated Fast Preview and Original-Image Export

- Added an isolated PREVIEW build purpose with root-scoped build/assets paths,
  `PreviewStateStore`, process-local `TEXINPUTS` image overlay, SHA-256/policy
  cache manifest, atomic proxy publication, and original-image fallback.
- Manual Compile and Export PDF remain FINAL-only. Export flushes every open
  document in the root, waits for a same-revision canonical build, retries when
  source changes during the build, and atomically publishes only that PDF.
- Added image dependency watching, deleted-image recreation handling, FINAL
  priority across running and debounced queues, logical-root PDF viewport
  preservation, and dual-cache cleanup.
- Replaced full-resolution image-sidebar decoding with 44×44 decode-time
  thumbnails and a 128-entry revision-aware LRU cache.
- Real TeX Live 2025 verification with a 42,429,430-byte 5000×3500 PNG confirmed
  preview `.fls` input from a 3,699,924-byte 1800×1260 proxy and FINAL `.fls`
  input from the original. Measured cold preview 1.095 s, warm preview 0.372 s,
  cold FINAL 0.736 s, and warm FINAL 0.435 s on this fixture; cold proxy creation
  is therefore an explicit limitation, not a universal speedup claim.
- A real EXIF-orientation fixture found and fixed a proxy/final geometry mismatch;
  both outputs now preserve the encoded pixel orientation used by LaTeX.
- Verified compileall, 356 offscreen tests (including the real `.fls` overlay
  integration when TeX Live is available), real preview/final compilation, and
  an offscreen application cold-start smoke. No version bump or artifact build.

## 2026-08-01 - Fast Preview Adversarial Hardening

- Preserved PNG/JPEG natural size by scaling proxy density with pixel geometry;
  real TeX tests cover physical-density PNG, density-free PNG, and JPEG.
- Added static `\graphicspath` proxy resolution and watcher coverage for
  project-local fallback assets, including dot-relative, absolute, missing, and
  PDF references; moved-source events now invalidate the original path.
- Fixed same-path revised PDF reload, displayed-purpose banner precedence,
  FINAL export/build binding, preparer-stage cancellation, clean-cache exclusion,
  and retired-manager callback ownership.
- Verified compileall and all 372 offscreen tests, including real preview/final
  TeX boundary and natural-size checks. No version bump or artifact build.

## 2026-08-06 - DeepSeek Collaboration Onboarding and DS-001 Queue

- Added `DEEPSEEK.md` as a compatibility entry and `FORDEEPSEEK.md` as the
  replace-in-place bounded assignment for DeepSeek work.
- Updated the shared agent read order, document lifecycle, and project index so
  DeepSeek follows the same source-of-truth and review rules as Codex and Claude.
- Queued `DS-001`, a tightly scoped 0.2.9 formula-composer core contract and test
  slice. It remains blocked until the maintainer activates it and the 0.2.8
  release boundary is complete or explicitly overridden.
- Recorded proposed decision D013 and a non-priority-overriding roadmap candidate:
  LaTeX remains the sole source of truth, unsafe formulas fall back without
  rewriting, and third-party visual technology requires a separate packaging and
  offline validation gate.
- Documentation and agent-instruction change only; no application source,
  version metadata, or generated artifact changed. Verification passed:
  compileall clean and all 372 offscreen tests OK.

## 2026-08-07 - Modular Layout Block MVP (feature/modular-layout-mvp)

- Implemented the modular Block layout MVP per the deep-research task checklist:
  `app/core/blocks/` data model, six JSON Schemas (Draft 2020-12), atomic
  store/migration, table import (CSV/clipboard/XLSX), four table LaTeX
  strategies, three-way source merge, DocumentTheme-to-.sty rendering, compile
  timeout, block source mapping, portable export, and the 2×2 demo.
- Added `app/gui/blocks/` console: table editor, layout panel (drag reorder/
  undo/inspector), merge dialog, theme settings, formula tab, six-tab project
  dialog, existing-project loader, and a MainWindow help-menu entry.
- Added `tools/run_mvp_ci.sh` local CI simulation and
  `docs/modular-layout-mvp-report.md` final report.
- Verification (2026-08-07, local authority): compileall clean, ubuntu subset
  72 tests OK, full suite 619 tests OK, demo builds and compiles
  (xelatex/ctex), export package verified in a clean temp directory.
- GitHub Actions remains the only open gate: the ubuntu job previously passed
  (22s); macOS full-suite hardening (job timeout, `-v`, `timeout_seconds=300`)
  is committed. Push is paused per maintainer instruction until Actions quota
  is restored.

## 2026-08-07 - macOS CI Hang Root Cause and Compile Tree-Kill Fix

- Diagnosed the macOS runner hang from the timeout-cancelled run logs: the
  suite stopped right after `test_blocks_gui`'s formula test and stayed silent
  for 28 minutes; job cleanup found orphan `xetex` + `Python` processes.
- Root cause: `BlockProjectDialog._build_pdf_sync` compiled without a timeout,
  and timeout/stop termination killed only the direct child (latexmk), leaving
  the xelatex engine child holding the stdout/stderr pipes so the subsequent
  `communicate()` blocked forever.
- Fix: compile processes now start in their own process group/session and are
  terminated as a tree (POSIX `killpg` SIGTERM→SIGKILL; Windows
  `taskkill /T /F`); the dialog preview compile gained a 300 s timeout.
- Added regression test `test_timeout_kills_entire_process_tree` (verifies the
  engine grandchild dies on timeout). Full suite: 620 tests OK locally.
- GitHub billing/spending-limit remains the only gate for the remote run;
  push stays paused per maintainer instruction.

## 2026-08-07 - Block Console Acceptance Blocker Fix (DocumentTheme/AppTheme)

- Acceptance found the "Block 项目（MVP）" console silently failed to open any
  existing project: `load_block_project()` returns a `DocumentTheme`, which was
  passed straight into the AppTheme-only `ThemeSettings`, raising
  `AttributeError: 'DocumentTheme' object has no attribute 'tokens'` during
  dialog construction (the console never appeared; unit tests never passed a
  theme, so they missed it).
- Fix: `BlockProjectDialog` now accepts a separate `document_theme` (loaded
  document theme) and defensively falls back to a default `AppTheme` for the
  settings tab when a non-AppTheme is passed as `theme`; the preview build now
  honors the loaded document theme instead of a hardcoded one; the preview
  preamble always loads `graphicx` so empty/text-only projects compile.
- Added regression test `test_dialog_opens_with_loaded_document_theme`
  (dialog opens with a loaded DocumentTheme, six tabs, preview PDF honors the
  loaded theme). Full suite: 621 tests OK locally.

## 2026-08-07 - Block Module Main-Console Integration (feature/block-console-integration)

- Executed the integration plan end to end on
  `feature/block-console-integration` (from modular-layout-mvp 9ee1c22):
  Phase 0 audit + baseline freeze (621 tests), then ProjectSession/
  repository/workspace/controller/commands extraction, MainWindow dock
  embedding, unified selection/undo/save/compile routing, image asset
  import, window-state persistence.
- BlockProjectDialog is now a thin wrapper over one shared ProjectSession;
  the duplicate CompileManager and direct LaTeX/JSON writes were removed
  from the Block GUI layer.
- Full suite: 643 tests OK locally; `tools/run_mvp_ci.sh` green including
  demo build; docs/block-console-integration-report.md records the
  before/after architecture, event flows, manual acceptance steps and
  known limitations.
- Not pushed; remote CI remains gated by the GitHub billing/spending limit.

## 2026-08-07 - UI Scale 与响应式布局修复 (feature/ui-scale-responsive-layout)

- Executed the UI scale/responsive layout plan on
  `feature/ui-scale-responsive-layout` (from 527808f, 644 tests baseline):
  fixed-size audit, unified UiMetrics/TypographyMetrics, UiScaleManager with
  90/100/110/125/150% tiers from base font (no drift), AppSettings
  persistence, responsive welcome page (4/2/1 reflow + scroll), tab bars
  with scroll/elide, PDF toolbar tiering with More menu (zoom isolated to
  QPdfView), diagnostics auto-expand, dock/splitter clamp on scale change,
  and a project-close compile race fix.
- Full suite: 658 tests OK (15 new UI scale/responsive tests); local CI
  simulation green. Known: full-suite runtime rose to ~130s due to app-wide
  stylesheet rebuilds on scale change; production single-window switch is
  fast. Not pushed.

## 2026-08-07 - UI Scale 收口与版本冻结准备（feature/ui-scale-responsive-layout）

- Phase A: 测试基线口径澄清并写入报告——643（主控制台集成正式报告）→ 644（提交 527808f
  新增 A6 布局撤销栈回归测试）→ 659（本轮新增 15 项 UI Scale/响应式测试）。
- Phase B: 清理 docs/PROJECT_LOG/CHANGELOG 中所有本机绝对路径，改为相对链接或可移植表述；
  grep 复查为空。
- Phase C: `RealTeXTest/`（127MB 个人本地测试材料）按情况 A 写入 `.git/info/exclude`，
  工作区 git 状态恢复干净。
- Phase D: 生成 docs/assets/ui-scale/ 截图矩阵（90-wide/100-medium/125-narrow/150-wide/
  pdf-more-menu）与 docs/ui-scale-visual-acceptance.md；多显示器未手测（仅内置 Retina），
  已在文档如实标注。
- Phase E: 性能治理——QSS 缓存、注册窗口 WeakSet、可见窗口重排、`ICSTEX_UI_SCALE_PROFILE=1`
  探针；定位根因（应用级 setStyleSheet × ~100 残留窗口，~9.6s/次）；生产单窗口实测
  72.5ms（目标 <300ms 达标）；套件耗时记为技术债（结果 B），见
  docs/ui-scale-performance-report.md。
- Phase F/G: screenChanged 未发现真实二次 DPR 问题，保持 Qt6 原生；Density 记为 P2 待
  外观设置阶段提供 UI。
- Phase H: 最终回归 compileall OK、全套件 659 tests OK、run_mvp_ci.sh 全绿、
  Stable LaTeX 在 90% 与 150% 下输出字节一致。
- Phase I/J: 报告补 15 问回答与基线说明；CHANGELOG 未发布段更新；收口提交；未推送。

## 2026-08-07 - Formula Editor 2.0 审计与 pix2tex 本地 OCR Sidecar (feature/formula-editor-local-ocr)

- Phase 1 审计：公式系统已具备 Formula Editor 2.0 主体（结构化画布、AST 权威、草稿隔离、
  本地撤销、源码模式、无损往返），输出 docs/formula-editor-current-state-audit.md；
- 新增 FormulaLatexSanitizer（剥包装/拒绝危险命令/路径/超长/超深）与 OCR JSONL 协议；
- 新增可选 pix2tex Sidecar：environment/manifest/installer/installer_cli/worker_entry
  （延迟导入、禁剪贴板副作用、禁静默下载）/client（QProcess 状态机+超时+取消）/manager
  （生命周期与会话路由）；核心 requirements 零新增、GUI 不 import pix2tex；
- FormulaDialog 接入“从图片识别…”→ RecognitionReviewDialog → 人工核对 → 可视化编辑 →
  一次命令写回；
- Spike：本机仅 Python 3.12，pix2tex==0.1.4 依赖解析在有界 4 分钟内未完成，真实模型
  验证未执行（如实记录，Go 门禁延后）；Fake Worker 全量测试通过；
- 新增 tests/test_formula_ocr.py 10 项；全套件 673 tests OK（本地）。未推送。

## 2026-08-08 - pix2tex Spike 完成与 OCR 端到端打通（feature/formula-editor-local-ocr）

- 安装 Homebrew Python 3.11，隔离 venv 安装 pix2tex==0.1.4 成功（官方 PyPI + legacy
  resolver；先前卡顿根因为本机 pip 配置阿里云镜像超时）；venv 1.2GB、模型 116MB；
- 实测：冷加载 423–448ms、热推理 132–142ms（CPU）、峰值 RSS ~670–690MB、
  temperature=0.01 下 5/5 输出一致；Spike 完成（Go 通过）；
- 依据真实 API 修正 worker（Munch 参数、PIL 图像、透明背景合成白色）与安装器模型下载；
- 新增 `tools/bench_formula_ocr.py` + 10 张 xelatex 渲染 fixture + 准确率 CSV；
- 设置页新增“可选工具 → 公式识别 (pix2tex)”区（状态/安装/移除/许可说明）；
- `ICSTEX_PIX2TEX_ENV` 环境覆盖使应用可直接使用已装 venv；全套件 673 tests OK。

## 2026-08-08 - ICSTeX 2.1 Local Recognition Runtime（feature/local-recognition-runtime）

- RapidOCR Spike 通过（GO，Option B 分离 Sidecar）：安装 21s、venv 296MB、模型 16MB、
  冷加载 370ms、热推理 ~250ms、RSS ~868MB、英文精确；pix2tex 零回归；
- 新增 app/services/recognition：models（Kind/Request/Region/Result + Router）、
  runtime_manager（检测/安装命令/pip 源检测/移除/磁盘/manifest）、泛化 JSONL
  worker_entry（pix2tex/RapidOCR 懒加载）、QProcess client、fake_worker；
- 设置页新增 RapidOCR 文字识别状态行；测试新增 6 项；全套件 685 tests OK；未推送。

## 2026-08-08 - 2.1 工单完成后的收尾调整（feature/local-recognition-runtime）

- ROI 交互解耦（Shift 新建/拖拽移动/8 点手柄/Delete 删除）；aligned 种子修复
  （_seed_editor_latex 同时写源码与可视化区并屏蔽 toggle 信号）；ROI 变化 500ms
  自动重识别 + “识别选中 ROI”；“清空”拆分为“清空 ROI”与“清空识别内容”；
- 统一批量图片识别窗口（队列+进度条+可滚动 ROI 行+精调当前+插入到编辑器）；
- 修复插入链路：ROI 点击 KeyError 与识别重入 IndexError 导致批量结果为空，
  加 drag 容错、索引校验、_recognizing 重入锁、批量单图失败容错；
- 提交幂等：四处提交入口 _submitted 一次性锁 + 队列图片内容指纹去重；
  打开防抖：图片识别/精调当前 400ms 防抖防排队弹窗；修正 _remove_selected
  QListWidgetItem.row 崩溃；测试 685→698 全绿；报告写入
  docs/ocr-post-2.1-adjustments-report.md；未推送。

## 2026-08-08 - OCR 收口工单：冻结/审计/批量状态/防抖常量/真实材料 Dogfooding/RapidOCR→Text Block

- 冻结基线 tag `ocr-interaction-freeze-20260808`（指向报告提交 39f6bf7）；
- 独立审计 6 个提交（dd3204d..d1d165b），输出 docs/ocr-post-2.1-independent-audit.md：
  发现中危 F1（精调后合并结果重复拼接，实证复现）、F2（_wait_ocr 全局信号提前退出）、
  F3/F4/F5 低危与 F6 提交说明不符；F1 由本次批量状态改造修复；
- 批量队列逐项状态：Pending/Recognizing/Succeeded/Failed/Cancelled/Refined，
  每行提供[重试此项][查看错误][从批次移除]，单项失败不再静默跳过（含“未识别到内容”与
  “识别异常”两类错误区分），精调结果标记 Refined；每行独立结果修复 F1；
- “允许相同图片重复入队”复选框（默认去重）；400ms 打开防抖提取为命名常量
  DIALOG_OPEN_DEBOUNCE_SECONDS（app/gui/formula_ocr/__init__.py）；
- 真实材料 Dogfooding：arXiv 论文公式（Attention/MultiHead/ResNet 真实 LaTeX 渲染）、
  论文 PDF 真实页面裁剪、CROHME 真实手写轨迹光栅化，走应用真实链路推理，
  结果与复现命令写入 docs/ocr-dogfooding-report.md；教材 PDF 因网络受限未纳入（如实记录）；
- RapidOCR Review → Text Block 独立流程：app/gui/text_ocr/（manager+review dialog+flow），
  Block 导航面板新增“文字识别…”入口，幂等提交、空内容保护、Undo 可撤销；
  报告 docs/rapidocr-text-block-flow-report.md；
- 全套件 698→706 tests OK；未推送。

## 2026-08-08 - ICSTeX 2.1.0-beta.1 版本冻结与打包（release/2.1）

- 收口审计中危/低危：F2（_wait_ocr 按 request_id 退出，外来会话不再提前结束等待）、
  F3（ROI 无几何变化不再 emit rois_changed）、F4（RoiCanvas.selected_index 公开访问器）、
  F5（手改合并结果后重识别需确认）、F6（修正“3 项测试”文档表述）；新增 4 项回归测试；
- 版本单一来源更新为 2.1.0-beta.1（PRODUCT_NAME/MAJOR/MINOR/VERSION/RELEASE_NAME/
  RELEASE_CHANNEL），pyproject/README/打包文档/CLAUDE/CHANGELOG 全部对齐；
- 冻结 2.1 Beta 1 范围：RapidOCR“文字识别…”入口禁用（代码与测试保留，后续 Beta 开放）；
- 应用退出时关闭 OCR worker（aboutToQuit），避免孤儿进程；
- 发布资产 release/：RELEASE_NOTES/KNOWN_LIMITATIONS/INSTALLATION/THIRD_PARTY_NOTICES/
  SHA256SUMS + Formula-Intelligence-Demo.zip；pix2tex 代码 MIT、权重 CC BY-NC-SA 4.0、
  权重 SHA-256 a63d9141…1dfaa 已记录；
- 门禁：preflight 通过（版本一致 + compileall + 全套件 710 OK）；build_macos.sh 产出
  dist/ICSTeX-2.1.0-beta.1.dmg（61MB）；打包 .app 在干净目录 offscreen 启动验证通过、
  Demo main.tex 编译通过；DMG/ZIP 二进制不入库（gitignore）；
- tag v2.1.0-beta.1 创建于打包验证通过后；未推送（遵循 action rate 约定）。

## 2026-08-08 - 2.1.0-beta.1 Windows ARM64 Portable Build

- 先核对发布基线：`release/2.1` 和本地 tag `v2.1.0-beta.1` 尚未推送；macOS
  preflight 重新运行，710 tests OK；旧 `dist/ICSTeX-Windows.zip` 被判定为可能过期。
- 修正 README、Windows 构建指南与当前状态中残留的 0.2.7/旧包表述；Windows 构建脚本
  现在读取 Python architecture，并输出 `Windows-x64` 或 `Windows-arm64` 制品名。
- 从 matching source archive 解压到 Windows-local
  `C:\w2\ICSTeX-Source-2.1.0-beta.1`，使用 ARM64 Python 3.12.10 和 PyInstaller 6.21.0
  成功构建 `ICSTeX-2.1.0-beta.1-Windows-arm64.zip`。
- 在只含 Windows system directories、没有 Python 的 PATH 下启动打包应用；8 秒后
  `ICSTeX.exe` 仍正常运行（103,924 KB working set）。ZIP 完整性检查通过，SHA-256：
  `97cb1c8917480a3b763146ef64a601d38318bb5b2b1c9413d76fc1dc49753949`。
- 当前虚拟机没有 MiKTeX/TeX Live 或 Inno Setup，且为 ARM64；因此 Windows
  source-to-PDF、x64 ZIP 和 x64 Setup EXE 未验证，不能宣称 Windows 发布已完整收口。

## 2026-08-08 - 2.1.0-beta.1 Release Website and Publication Preparation

- 新增 `release/release-manifest.json` 作为版本、资产、SHA-256、平台状态与官网生成的
  单一发布元数据；`tools/update_release_site.py`、`tools/verify_release_consistency.py`
  和 `tools/release_prepare.py` 保持其与 `app/__init__.py`、release documents 和本地资产一致；
- 新增纯静态 `website/`（HTML/CSS/vanilla JavaScript、仓库内已核验 UI 截图、无账号/
  追踪/后端/CDN 字体）。未发布的 GitHub Release 会明确禁用下载，Windows x64 与 ARM64
  开发者 Beta 的边界在页面中单独说明；
- 为可追溯性分三笔提交：Release 元数据与一致性校验、静态官网、官网测试与 Pages 手动
  交接。`tests/test_release_site.py` 覆盖生成、路径泄露、语义、资产与 push guard；
- 验证：官网专项 6 tests、`packaging/preflight.sh` 716 tests、`tools/run_mvp_ci.sh`
  72 项模块化子集 + 716 项完整套件 + Demo 构建均通过；真实浏览器在 1440 px / 375 px
  视口无 console error；
- GitHub connector 对仓库返回 404、Linear connector 要求重新授权；没有推送 branch/tag、
  没有创建 GitHub Release，也没有部署 Pages。`tools/deploy_release_site.sh --push` 还需要
  明确授权与 `ICSTEX_RELEASE_SITE_PUSH=1`。

## 2026-08-08 - Release Website Figma Design Handoff

- 创建 Figma design draft `ICSTeX 2.1 Beta 1 Release Website`，从本地已验证官网捕获
  成可编辑的 1703 × 5737 画板；链接与“raw frames、源码仍为真值”的边界写入
  `docs/release-2.1-beta1-preparation-report.md`；
- 临时 Figma capture script 已在捕获完成后移除，静态网站没有新增第三方运行时或联网行为。

## 2026-08-08 - Local Pages Publication Rehearsal

- `tools/deploy_release_site.sh --prepare` 从干净的 Release 候选创建本地 `gh-pages`
  root commit `434152e`，仅包含 10 个静态站点文件；未执行 `git push`、未修改 GitHub
  Pages 设置。公开部署仍需维护者明确授权和 `ICSTEX_RELEASE_SITE_PUSH=1`。

## 2026-08-08 - Release Website Proof-Dossier Visual Refresh

- 将 `website/` 的视觉语言改为“编译证明单”：Hero 直接表达 source.tex → local build →
  proof.pdf 的关系，信息从本地边界、功能工作台、交付路径到发布台账展开，避免通用营销卡片；
- 中文正文采用思源宋体兼容栈，英文与技术令牌优先 SF Mono 兼容栈；对品牌和文件令牌加
  `translate="no"`，不会加载外部字体或把用户内容交给第三方；
- 仓库内置 Pico CSS 2.1.1（MIT，`website/vendor/`，含许可证），作为语义 HTML 的基础样式，
  本地样式表保留可访问焦点、减弱动画、触控目标、响应式布局和明确图片尺寸/加载优先级；
- `tests/test_release_site.py` 新增对本地 Pico 与许可证、动态下载状态的覆盖；专项 7 tests，
  `compileall` + 离屏完整套件 717 tests 均通过；真实浏览器复核桌面与 390 px 移动视口，未见
  横向溢出或控制项不可达。发布状态仍为未发布，未推送 GitHub、未发布 GitHub Release。

## 2026-08-08 - Vercel Static Website Deployment Record

- 使用 Vercel CLI 从 `website/` 上传静态站点；首次项目部署在未传 `--prod` 的情况下被 Vercel
  自动标记为 production target，部署 ID 为 `dpl_47JdBfdEeGKhACBu7iH8js473VmW`。这是 Vercel
  的首部署行为，不等同于 GitHub Release 或自定义域名发布；
- 匿名浏览器被 Deployment Protection 重定向到 Vercel 登录页；有权限的 Vercel connector 对
  部署源返回 HTTP 200，确认了已上传的当前 `index.html`，响应带 `x-robots-tag: noindex`。没有
  创建公开分享链接、没有配置自定义域名、没有推送 GitHub；
- 新增 `website/.gitignore` 忽略 Vercel 生成的 `.vercel/` 本地项目关联信息，避免将团队/项目
  标识提交入仓库。后续若要公开上线或改动该 production target，必须由维护者明确授权。

## 2026-08-08 - Deep Research Release Website Task Integration

- 将维护者提供的 Release Website 研究报告转译为
  `docs/tasks/WEB_RELEASE_SITE_REFACTOR.md` 的 WEB-001～004 可执行工单，覆盖移动端 Hero、
  信息瘦身、Release 数据完整性、QA 与部署交接；
- 消解两项报告与仓库约束的冲突：H1 版本必须继续由 `data-release-*` 注入，不硬编码
  `ICSTeX 2.1`；GitHub Releases/Pages 保持发布真值和公开展示路径，受保护 Vercel target
  仅作为当前外部状态，不替代正式发布流程；
- 工单已接入 `FORCODEX.md` 当前 Release gate 与 `docs/ROADMAP.md`，明确禁止新增 React、
  Next.js、Tailwind、Node build chain、远程字体或未经授权的 Tag/Release/Pages 发布；
- 当前源码核查确认 `id="download"` 重复和 `2.1 BETA 1` 硬编码是待处理问题；本次仅建立
  开发任务与验收边界，没有实施网站源码改动；`compileall` 与离屏完整套件 717 tests 通过。

## 2026-08-08 - WEB-RS-001 Release Website Gate Completion

- 完成 WEB-001～004：移动端 Hero 在 390 x 844 首屏展示动态版本、Formula Intelligence、
  Apple Silicon 主操作和主截图；页面收敛为七个一级信息组，Windows 状态降为次级详情；
- Release 名称、版本、Tag、Channel、下载 URL 和发布状态继续由生成的 `release.json` 驱动；
  未发布下载保持禁用，未硬编码发布常量，也未改变 GitHub Releases 的发布真值边界；
- Codex 内置浏览器在 390 x 844 和 1440 x 900 验证无横向溢出、无控制台错误；Lighthouse
  移动端 Performance 97 / Accessibility 100，桌面端 100 / 100，两端 Best Practices 与
  SEO 均为 100；
- `tools/update_release_site.py --check`、9 项官网专项测试、`compileall`、719 项离屏完整套件
  与 `packaging/preflight.sh` 全部通过；验收证据写入 `docs/release-site-checklist.md` 和
  `release/release-site-changes.json`；
- 未推送 branch/tag，未创建 GitHub Release，未部署 GitHub Pages 或更新 Vercel target。

## 2026-08-08 - Platform Installer Interaction and GitHub 404 Gate

- Release 区新增 macOS / Windows 可访问平台标签：支持鼠标、Left/Right/Home/End 键与
  `#panel-macos` / `#panel-windows` 深链；macOS 展示 DMG/ZIP，Windows 明确区分 x64
  尚不可用与 ARM64 开发者 Beta，并显示生成的 SHA-256 与各平台安装步骤；
- GitHub 实查确认仓库为 Private，远端没有 `release/2.1`、`v2.1.0-beta.1` 或对应
  Release；本机 `gh` 认证可读仓库，但 Codex GitHub Connector 仍因缺少 Private 权限
  返回 404；
- Release manifest 新增 `github_repository_public` 真值。下载必须同时满足仓库 Public 和
  Release 已发布；当前 Private 状态下，内置浏览器确认 GitHub、文档和下载出站链接为 0，
  不再把用户送往已知 404；
- Codex 内置浏览器在 390 x 844 与 1440 x 900 验证平台切换、键盘、深链、零横向溢出和
  零控制台错误；Lighthouse 移动端 Performance 98 / Accessibility 100，桌面端 100 / 100，
  两端 Best Practices 与 SEO 均为 100；
- 10 项官网专项测试、Release 一致性、`compileall`、720 项完整离屏测试与
  `packaging/preflight.sh` 全部通过；未修改仓库可见性，未推送或创建远端 Release。

## 2026-08-09 - Public 2.1 Beta Release and Download Site

- Rewrote the public Git history with explicit leases after a complete backup,
  full-history maintainer-path scan, unchanged current tree verification, 731
  passing tests, and preflight; fresh remote history scans contain no
  `/Users/leo.xu` path.
- Published `v2.1.0-beta.1` as a public GitHub prerelease with nine retained
  assets. Anonymous HEAD requests returned HTTP 200 for the macOS DMG/ZIP,
  Windows ARM64 ZIP, and source ZIP.
- Enabled the generated website release flags in commit `ef1d0b2`, with GitHub
  Actions manually disabled before the push; no CI was intentionally run.
- Deployed `website/` directly to Vercel production as deployment
  `dpl_2AGNS5Pg6iZv2yMW9XqxLeFowPuf`; state is READY, production aliases are
  assigned, SSO Protection is disabled, and Git fork protection remains enabled.
- Release-site consistency, 10 focused website tests, `compileall`, 731-test
  offscreen suite, and `packaging/preflight.sh` passed before publication.

## 2026-08-09 - Public Website Copy Rewrite

- Rewrote the public site from release-engineering language into user-facing
  Chinese without changing layout, download URLs, platform truth, or interaction
  logic. Hero, platform guidance, formula/OCR, workspace, privacy, limitations,
  status messages, and footer now describe concrete user actions and outcomes.
- Localized the generated Release display name and all four published
  limitations; retained necessary terms including LaTeX, PDF, SHA-256, ARM64,
  DOI, arXiv, and product UI labels where precision matters.
- Added copy-regression assertions. Ten focused website tests, `compileall`, the
  731-test offscreen suite, and `packaging/preflight.sh` passed.
- Playwright verified macOS and Windows panels at 390 x 844 and 1440 x 900 with
  matching viewport/scroll widths, enabled download links, and zero browser
  warnings or errors.

## 2026-08-09 - Release Website Content and Information Architecture Expansion

- Executed the latest research work order as a presentation-layer slice. The
  homepage now separates product understanding, current release, feature stories,
  local-first assurances and Beta/download actions; release logic and asset facts
  remain unchanged.
- Added factual `website/guide/` and `website/about/` pages, preserving the
  founder letter in `docs/product/FOUNDER_LETTER_ZH.md`. Added the frozen IA and
  release DOM contracts under `docs/website/`.
- Added a static HTML contract audit to `tools/verify_release_consistency.py`:
  every page is checked for unique IDs, one H1, image dimensions/alt text,
  allowed `data-release-*` bindings and hard-coded version/tag leakage.
- Visual implementation follows the installed frontend-design direction: Source
  Han Serif-compatible display roles, UI sans body copy, SF Mono utility text and
  a restrained typeset-grid signature. The web-design-guidelines audit basis was
  fetched and applied to focus, semantics, keyboard behavior, images, locale and
  responsive layout.
- Evidence: 12 focused website tests, 733 full tests, compileall and
  `packaging/preflight.sh` passed. Playwright verified 390/430/1024/1280/1440 px
  homepage widths, Guide/About dynamic loading, platform tab keyboard/deep-link
  behavior, skip-link focus and no console warnings/errors.
- Committed as `22ecb00 website: add guide and philosophy content architecture` and
  pushed to `release/2.1` while both GitHub Actions workflows were temporarily
  disabled; `gh run list` showed no run for the new SHA. Workflows were restored to
  active immediately afterward.
- Deployed the committed `website/` to Vercel Production as
  `dpl_D71b854e1vvoJa4GAwfAxnEmFAfn`; deployment inspection returned `READY`, the
  existing public alias remained assigned, and SSO Protection remained disabled.

## 2026-08-13 - Project-Scoped MCP and Agent Skill

- Added an optional local stdio MCP adapter with 11 semantic tools covering
  project inspection, CAS document writes, image import, queries, Block state,
  compilation, local recognition candidates, reference metadata and export.
- Bound each process to one canonical root. Traversal, symlink and non-regular
  inputs fail closed; host startup grants control write, compile, network,
  recognition, raw-LaTeX, external input and export authority.
- Added project locking, SHA-256/revision CAS, atomic replacement and verified
  byte-exact preimage snapshots. Recognition never writes automatically.
- Extracted deterministic Block LaTeX assembly into `app/core` for GUI/MCP reuse.
  MCP compilation adds relative entry/output arguments and TeX
  `openin_any/openout_any=p` to the existing no-rc, no-shell and timeout rules.
- Added the repository-owned `icstex-control` Skill, optional `mcp>=1.28,<2`
  dependency, `icstex-mcp` entry point, Codex registration instructions and
  source-archive inclusion.
- Verification: compileall passed; 62 focused tests passed; a real stdio MCP
  initialize/list/call handshake exposed all 11 tools; 764 offscreen tests
  passed; a real restricted TeX Live FINAL compile succeeded while external
  absolute input and project-source `openout` overwrite were blocked.
- The official Skill validator passed after PyYAML was supplied only through a
  temporary validation directory, without changing product dependencies. Local
  pix2tex/RapidOCR isolated Python runtimes were absent, so real model inference
  remains an acceptance item.
## 2026-08-08 - Public-release security boundary

- Standard desktop security scan identified seven publication blockers across
  compilation, Block rendering, export, Magic Root, online metadata, timeout,
  and publication hygiene.
- Architect review accepted the default-deny boundary recorded in D014.
- `python3 -m compileall -q app tests packaging/install_build_dependencies.py` passed.
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests` passed: 731 tests.
- `bash packaging/preflight.sh` passed; existing macOS/source/Windows ARM64
  artifacts are intentionally marked stale pending rebuild.

## 2026-08-08 - Hardened artifact rebuild

- Rebuilt macOS arm64 DMG and ZIP; strict deep code-sign verification, arm64
  executable inspection, and offscreen cold-start smoke passed.
- Rebuilt the clean source ZIP from hardened app source; final archive SHA-256 is
  `e2556c4356e8c8bbb20d2b548f33ced91d8c631cccd5b76c147f0ae301dbb51a`.
- Rebuilt Windows ARM64 in Windows-local `C:\w3` with Python 3.12.10 ARM64.
  Packaged launch with Python removed from PATH passed; ZIP SHA-256 is
  `9f7ee34c82c6c781fbdeebf6d86704d823d91e9915185b3e64b2c12c685030fb`.
- Windows x64/Setup and Windows TeX source-to-PDF remain unavailable and are
  still excluded from public claims.
- Release metadata regeneration, all recorded SHA-256 checks, source archive
  integrity/exclusion inspection, Windows PE AArch64 inspection, and 10 website
  release tests passed.

## 2026-08-13 - MCP Interface and Skill Contract Hardening

- Kept the existing 11-tool semantic surface and added standard MCP behavior
  annotations for read-only, destructive, additive and open-world operations.
- Replaced free-form protocol parameters for query kind, Block operation,
  compile action/purpose/engine, recognition kind and export kind with bounded
  enum schemas; core grant and validation checks remain authoritative.
- Clarified the `icstex-control` Skill's path rule and mapped each host startup
  grant to the operations that require it.
- Verification: official Skill validation passed; the installed `mcp` SDK was
  1.28.1; 62 focused tests and 764 offscreen tests passed; compileall passed;
  the real stdio handshake verified all tools, annotations, enum schemas and a
  read-only `inspect_project` call.

## 2026-08-13 - Audited ICSTeX Control Skill Revision

- Audited the maintainer-provided 638-line Skill candidate against the current
  11-tool MCP schema, core responses, grants, CAS rules and D015 boundary.
- Replaced the repository Skill with a 122-line revision that retains the
  candidate's useful untrusted-content, no-shell-fallback, diagnostic,
  visual-review and failure-handling guidance without duplicating the existing
  workflow.
- Removed unsupported claims about project revisions, transaction IDs, compile
  profiles, bibliography/job/cache metadata, asset deduplication, `CHECK_SKIPPED`
  and a nonexistent doctor command.
- Official Skill validation, an AST-to-Skill tool-contract check and repository
  to global-symlink comparison passed. Compileall, 62 focused MCP/core tests and
  all 764 offscreen tests also passed.

## 2026-08-28 - MCP 2.x Safe Concurrency

- Migrated the optional adapter from `mcp>=1.28,<2` and `FastMCP` to
  `mcp>=2.0,<3` and the official `MCPServer`. The verified local environment used
  `mcp 2.1.1`; the server reports the ICSTeX application version and preserves
  the existing 11-tool wire schema, annotations, grants and CLI surface.
- Added a pure-core project concurrency coordinator: at most four ordinary
  readers, one OCR request and one network request; writer-priority FIFO
  exclusivity for mutations, compilation and export; and cancellation of queued
  compile work without blocking `compile_project(action="stop")`.
- Registered compile intents before queueing, applied the existing preview/final
  120/300-second bounds to queue plus execution, serialized the full validation,
  optional Block assembly, build and artifact publication path under a reentrant
  cross-process project lock, and prevented active CompileManager replacement.
- Converted anticipated workspace/concurrency failures to MCP 2.x `ToolError`
  so permission, CAS, path, timeout and cancellation messages remain visible;
  unexpected exceptions remain redacted by the SDK.
- Added focused coverage for bounded readers, writer priority, FIFO/cancellation,
  two-project compile overlap, same-project serialization, active stop, compile
  deadlines, reentrant export, two-process CAS competition, current/legacy stdio
  handshakes and synchronous tool thread offload.
- Verification: `python3 -m compileall -q app tests packaging/install_build_dependencies.py`
  passed; 77 focused tests passed; `QT_QPA_PLATFORM=offscreen python3 -m unittest
  discover -s tests` passed all 779 tests; `python3 -m pip check`, `git diff
  --check`, the official Skill validator and repository/global Skill comparison
  passed. No package, publish, push or GitHub Actions workflow was run.

## 2026-08-29 - Word Count Accuracy Repair

- Compared the existing counter with the TeX Live TeXcount source, Overleaf's
  `texcount -inc` service path and newer syntax-tree/Unicode-segmenter client
  path, plus pylatexenc's custom parsing model. Reused the architectural ideas
  only; no third-party source was copied and no dependency was added.
- Reproduced TeXcount `-chinese` counting U+3002 and U+3001 as Han-script words;
  ICSTeX now requests `-logograms=Ideographic`, verified with the installed
  TeXcount 3.1.1 against Chinese punctuation, numbers and U+20000 ideographs.
- Replaced fragment-by-fragment fallback totals with category-level visible-text
  tokenization. Accent macros and formatting inside a word now remain one word;
  standard text-symbol macros, `%TC:ignore`, inline verbatim, optional short
  headings/captions and footnote classification have focused regression tests.
- Repeated `input`/`include`/`subfile` expansions are counted each time while an
  ancestor stack stops true cycles. Unsafe cyclic/over-limit projects bypass
  external TeXcount instead of waiting for its 15-second timeout.
- Preserved all `WordCountResult` and MCP fields. The UI now calls the modes
  `TeXcount 兼容统计` and `ICSTeX 结构化统计`, labels TeXcount's third category as
  `说明/脚注`, and states that course-specific inclusion rules remain external.
- Verification: 32 focused Word Count tests and 156 Word Count/Environment
  Doctor/GUI tests passed; `python3 -m compileall -q app tests
  packaging/install_build_dependencies.py` passed; full offscreen discovery
  passed all 787 tests in 214.403 seconds; `git diff --check` passed. No package,
  publish, push or GitHub Actions workflow was run.

## 2026-09-03 - Completion Selection and Normal-Mode Image Layouts

- Reproduced the completion mismatch with the popup highlighting `\textit{}`
  while `QCompleter.currentCompletion()` remained `\textbf{}`. Enter and Tab now
  resolve the popup's current index before falling back to the completer value.
- Replaced the normal-mode two-image dialog with structured horizontal, vertical
  and adjustable 2x2 layouts. Each image has an independent width and subcaption;
  generated LaTeX constrains width only, preserves source aspect ratio and rejects
  a row total above `1.0\textwidth`.
- Made multi-image asset copying transactional: all inputs are checked first,
  repeated source paths reuse one copy, and partial copy failure removes every new
  file from that operation before source insertion.
- Added regression coverage for popup selection, dialog state, layout generation,
  row validation, normal-mode insertion, asset rollback and a real XeLaTeX compile.
  Default and 150% offscreen visual checks showed no horizontal control clipping.
- Verification: `git diff --check` and `python3 -m compileall -q app tests
  packaging/install_build_dependencies.py` passed; the editor/insertion suite
  passed 146 tests, and full offscreen discovery passed all 796 tests in 141.204
  seconds. The Word Count checkpoint is `ea56060`; the editor/layout commit is
  `9103c31`. The verified line was merged locally into `release/2.1` without any
  package, publish, push or GitHub Actions workflow.

## 2026-09-03 - High-Frequency LaTeX Completion Catalog

- Expanded the deterministic static catalog from 23 to 68 unique templates for
  document structure, text styles, labels, citations, links, mathematics,
  scientific units, project composition, bibliography and layout controls.
- Replaced hand-counted cursor offsets with a single-marker template builder.
  Popup labels strip intentional trailing whitespace while insertions and cursor
  placement retain it, preserving `\item ` trailing-space and `\centering`
  newline behavior.
- Added `\text{}` as the exact first result for `\text`, plus
  `\textcolor{}{}`, font/style variants and `textcite` within the 12-result
  bound. `\textcolor{}{}` places the cursor in its color argument; `pageref`
  now uses the existing project-label completion path.
- Extended deterministic package diagnostics for xcolor commands and amsmath's
  `text`, `dfrac` and `operatorname`; missing packages offer the existing
  idempotent fix and declared packages remain warning-free.
- Verification: completion/diagnostic/GUI focused tests passed all 142 tests;
  `git diff --check` and `python3 -m compileall -q app tests
  packaging/install_build_dependencies.py` passed; full offscreen discovery
  passed all 805 tests in 132.196 seconds. The feature commit is `2af0c90`; it
  was merged locally into `release/2.1` without new dependencies, packaging,
  publishing, pushing or triggering GitHub Actions.

## 2026-09-03 - Guarded Project File Toolbox and Multi-Window Recovery

- Kept `QFileSystemModel` read-only while expanding the visible project set to
  `.tex`, `.bib`, common images and directories. Opening a nested source no
  longer replaces the selected canonical project root.
- Added `.tex` drag handling for editors and the empty welcome surface, explicit
  current/new-window routes, a `Ctrl+Shift+N` shortcut and window-registry cleanup
  after an accepted close.
- Reused the existing background image-import transaction for file-tree drags;
  no second copy or insertion path was introduced.
- Added pure project-path planning, containment/collision/symlink/internal-dir/
  same-filesystem validation, atomic rename, path remapping and fail-closed LaTeX
  reference analysis across disk sources and unsaved open buffers.
- Guarded GUI mutations reject active compiles, then rebind open tabs, watchers,
  recent files and compile/PDF ownership after success. Referenced paths are not
  silently rewritten.
- Verification: `git diff --check` and `python3 -m compileall -q app tests
  packaging/install_build_dependencies.py` passed; full offscreen discovery
  passed all 825 tests in 159.766 seconds. No dependency, package, publish, push
  or GitHub Actions workflow was run.


## 2026-09-06 - Clarify Agent Instruction Conflicts

- Replaced the stale non-Git assertion in AGENTS.md with live repository checks,
  bounded path resolution, and an explicit prohibition on initializing or
  replacing a repository to work around a failed check.
- Scoped icstex-control conflict and unsaved-GUI pauses to affected mutations;
  independent authorized read-only checks may continue, with saved disk state
  distinguished from unsaved GUI buffers. Synchronized the repository Skill
  with the global installation.
- Preserved CAS preconditions, concurrent user edits, GUI save/close requirements,
  OCR write-back approval, host grants, and destructive Git approval.
- Verification: compileall and git diff --check passed; full offscreen unittest
  discovery passed all 825 tests in 198.505 seconds. Repository/global Skill
  contents match. No application source, package, or release behavior changed.

## 2026-09-08 - Response and Compile Performance Exploration

- Audited current `f0f6935` source and pinned GitHub implementations from LaTeX
  Workshop, TexLab, TeX Live/latexmk and VimTeX. Kept the existing application,
  release boundary and unrelated agent-instruction edits unchanged.
- Added `tools/bench_response_pipeline.py`, an isolated synthetic-project probe,
  and retained samples in `docs/data/response-pipeline-probe-2026-09-08.json`.
  It measures synchronous GUI/analysis work, watch registration, external-event
  decisions and real XeLaTeX/BibTeX builds without using student documents or
  the normal application settings store.
- Reproduced an authorized external TeX edit scheduling one automatic compile
  while the auto-compile toggle is off. The watch set after opening the root
  omitted its unopened child and bibliography. These are findings, not fixes.
- Measured about 108 ms synchronous GUI Word Count for a 4,000-word fixture and
  about 111 ms extra GUI timer delay. The 8-page compile fixture had medians of
  1,763 ms cold, 59 ms unchanged and 729 ms after a text edit; same-content
  rewrites did not rerun engine rules. Each compiled PDF was readable with
  8 pages and the command retained `-norc` and `-no-shell-escape`.
- Recorded prioritized mechanisms, upstream source links, non-adopted options,
  scope limits and implementation gates in
  `docs/response-and-compile-exploration-2026-09-08.md`. No measured application
  speedup is claimed because no `app/` code was changed.
- Verification: the complete probe succeeded; compileall for app/tests,
  packaging dependency helper and the new probe passed; full offscreen
  unittest discovery passed all 825 tests in 154.578 seconds; git diff --check
  passed. No dependency installation, packaging, commit, push or release ran.

## 2026-09-08 - Automatic Build Admission and Async Word Count

- Unified automatic-build admission across idle saves, external text reloads,
  asset changes and non-user compile requests: enabled toggle plus existing
  root authorization are both required.
- Moved GUI structural analysis and TeXcount to immutable snapshots in a bounded
  worker, with latest-request replacement, revision/root/lifetime validation,
  disk-change checks, bounded result caching and explicit pending labels.
  TeXcount reads the same shadow snapshot as the structural count; manual refresh
  bypasses cache. The synchronous core/MCP result contract is unchanged.
- Updated the synthetic probe to distinguish dispatch from completion. Retained
  `docs/data/response-pipeline-after-2026-09-08.json` separately: app tree digest
  `08f8bf40393441d3f6b55c36b07532c0dbbde4c8d8450ee17d25d3411c04dd79`,
  uncached dispatch median 0.244 ms, completion median 115.910 ms, timer lateness
  17.544 ms; auto-off external TeX events scheduled zero builds. Engine timings
  varied upward, so no engine speedup is claimed.
- Verification: compileall and full offscreen discovery passed all 833 tests
  in 174.869 seconds. The full implementation goal remains open for dependency
  watching, dirty panels, pending deadlines and image/PDF visibility measures.
  No dependency, package, commit, push, publication or installed-app replacement.

## 2026-09-08 - Response Optimization Completion and Native PDF Measurement

- Completed the remaining authorized slices: root-owned static/FLS input
  watching, unopened/missing dependency observation, content-based event
  deduplication, conflict-safe saves, dirty/visible panel refresh and early
  directory pruning. PollingObserver remains; missing-parent recovery and a
  stop/reconcile registration race have focused regression coverage.
- Compile requests now capture configuration and input identity, keep one
  running/latest pending request, preserve FINAL priority and remaining
  deadlines, and invalidate launched-but-not-entered work on cancellation.
  FLS inputs are captured before the next worker can overwrite the recorder;
  queued Qt started signals retain the original request revision.
- Final synthetic response report:
  `docs/data/response-pipeline-final-2026-09-08.json`. Uncached Word Count
  dispatch median 0.203 ms, completion median 114.364 ms, GUI timer lateness
  18.345 ms; baseline synchronous GUI refresh was 108.052 ms and lateness
  110.739 ms. The selected-outline edit callback fell from 4.092 to 0.208 ms.
  A separately visible outline measured 0.236 ms per edit, one refresh after
  15 edits and zero image-index scans. Ignored 5,000-file subtree scan median
  fell from 12.572 to 0.021 ms. Unopened child/bibliography are watched and an
  auto-off external edit schedules zero builds.
- Added `tools/bench_pdf_pipeline.py`; Cocoa native-window evidence is retained
  in `docs/data/pdf-pipeline-2026-09-08.json` and three screenshots. Two 24 MP
  synthetic images totaling 92,864,798 bytes took 636.536 ms cold proxy
  preparation and 43.923 ms median warm content verification. Preview/final
  both displayed 2 pages with isolated output paths. Process exit to nonblank
  viewport observation was 125.001 ms for cold preview, 323.930 ms for cold
  final, and 30.071 ms for warm preview after a source edit. These are sampled
  upper bounds after native Paint, not compositor/scanout timestamps; proxy
  preparation was measured separately and the build runs used warm proxies.
- Kept full image SHA-256 verification and the existing PDF renderer because
  the measured warm cost did not justify another invalidation cache. Real
  8-page latexmk builds retained cache/no-op, bibliography convergence and
  safety flags; no engine acceleration is claimed.
- Both final measurement reports and a live source recheck identify app tree
  SHA-256 `0ad9f48d485483ba88d11200be2b4ee65b44ffcc50e3342e99b1ac34cacb74ef`.
  Updated Project State, D018, Roadmap, Project Index and the maintainer brief;
  the six-gate mapping and limits are in
  `docs/response-optimization-verification-2026-09-08.md`.
- Final verification: compileall for app/tests/packaging helper and both probes
  passed; full offscreen unittest discovery passed all 859 tests in 165.474
  seconds. This includes the final open-child-before-include/flush test and
  confirmed-save failure retaining conflict protection. git diff --check
  passed; core has no GUI imports, and the MCP response serializer is unchanged.
- Preserved original research/baseline/first-slice data and unrelated agent
  instruction edits. No runtime dependency, package, commit, push, publication,
  CI trigger, installed-application replacement or student document edit.
  Preview PDF-to-source SyncTeX remains outside this implemented scope.

## 2026-09-08 - Fast Preview PDF-to-Source SyncTeX

- Implemented the separately authorized reverse-navigation follow-up. PDF
  double-clicks use the actual displayed PREVIEW or FINAL record, checking
  root, revision, build id, viewer path and CURRENT freshness before and after
  the local SyncTeX query. Same-purpose worker starts are rejected even before
  queued Qt signals arrive; a separate FINAL build does not invalidate a
  current preview. Same-revision new builds now reload the PDF while retaining
  the existing logical-document view-state restoration.
- Relative SyncTeX input paths use the original compile-root directory. Pure
  core validation rejects out-of-scope, symlink, generated, missing and
  non-source targets and invalid line numbers before opening. PDF page margins
  and inter-page gaps no longer fall back to unconverted viewport coordinates.
  Source-to-PDF remains FINAL-only; export still cannot copy preview output.
- Real local pdfLaTeX generated a two-page preview with a 2400x1600 PNG proxy
  and its own SyncTeX sidecar, without generating a FINAL PDF. At PDF zoom
  factors 0.9 and 1.25, real viewport double-clicks on page 2 opened the original
  child source at line 2, retaining the compile root and unchanged source text.
  The same test passed offscreen and with `QT_QPA_PLATFORM=cocoa`; the native
  window was exposed and its preview banner/source cursor were visually checked.
  Canonical temporary paths and explicit PDF cleanup keep this fixture aligned
  with normal file opening and avoid alias/teardown artifacts.
- Verification: compileall for app/tests/packaging helper passed; the SyncTeX,
  preview pipeline and PDF panel focused suite passed 37 tests. Final full
  offscreen discovery passed 875 tests in 216.253 seconds. The standalone native
  test `tests.test_gui_preview_pipeline.GuiPreviewPipelineTests.test_real_preview_double_click_maps_original_child`
  passed in 2.023 seconds. `git diff --check` passed.
- Updated current state, README/user guides, roadmap and the bounded brief;
  D019 supersedes only D012's initial reverse-SyncTeX restriction. App Python
  tree SHA-256 (relative POSIX path, NUL, content, NUL per sorted source file):
  `c01cae5ac60d591033c4f8462bed0ec98a7f6964a4ed54db2ad577cfc1077cd5`.
  Working branch remains `release/2.1`, HEAD `f0f6935`, with prior changes preserved.
- No runtime dependency, engine or MCP wire-contract change; no student document
  edit, packaging, installed-application replacement, commit, push, release or
  GitHub Actions trigger. Preview source-to-PDF is not part of this assignment.

## 2026-09-08 - Local macOS Update for User Evaluation

- The user explicitly authorized updating the local installed app to the latest
  working source. Repository root and `release/2.1` HEAD `f0f6935` were rechecked;
  the app Python tree remained
  `c01cae5ac60d591033c4f8462bed0ec98a7f6964a4ed54db2ad577cfc1077cd5`.
- `QT_QPA_PLATFORM=offscreen bash packaging/preflight.sh` passed, including
  compileall and 875 tests in 214.693 seconds. PyInstaller 6.21.0 with Python
  3.12.6 generated a separate local app under
  `dist/local/ICSTeX-2.1.0-beta.1-20260908-184726-c01cae5a/` using the repository
  spec and a separate build work directory. Existing public DMG/Windows ZIP
  timestamps and sizes were unchanged.
- Inspected bundle version `2.1.0-beta.1`, identifier `com.icstex.app`, arm64
  application/QtCore/Python binaries and a valid ad-hoc deep strict signature.
  Ten critical embedded modules matched current source bytecode/constants,
  including background analysis, dependency tracking, PDF display identity and
  preview reverse SyncTeX. No Developer ID credentials or notarization were used.
- Copied the candidate to a staging app in `/Applications`, verified its
  signature, and rechecked that no ICSTeX process was running. Preserved the old
  app with a same-filesystem rename into
  `~/Library/Application Support/ICSTeX/Install Backups/20260908-184726/ICSTeX.app`,
  then moved the staged app to `/Applications/ICSTeX.app` with rollback on failure.
  The original bundle and executable kept their device/inode identity; their
  hash and signature were revalidated. A non-following recursive rsync checksum
  comparison reported no differences between the new build and installed bundle.
- New installed executable SHA-256:
  `d0f4a53af225e02ab513f50f76bbf5331e52e584aeff3eb56f9b0952040f8226`.
  Preserved old executable SHA-256:
  `1b47139d28d72cbdd78220dc7a7adfa0c0eb4e849991b4b23b82065790e48bf3`.
  `INSTALL_RECEIPT.md` beside the backup records provenance and rollback guidance.
- Cold-launched the exact installed app, observed its welcome window and
  LaTeX-ready status, and confirmed process 32646 was still running from the
  expected executable path after more than a minute. Dock already targeted that
  path and was not modified. Left the application open for user evaluation.
  This installation check did not open a student document or repeat a full
  project compile inside the packaged application.
- Updated current state and the handoff brief to distinguish this local build
  from unchanged public release packages. No application source changes, version
  bump, student document changes, dependency installation, commit, push, public
  release or GitHub Actions trigger; final compileall and diff checks passed.

## 2026-09-08 - Update Delivery Mechanism Design

- Completed the requested design for opt-in update discovery, signed release
  metadata, complete-package delivery, and save/quit/install coordination in
  `docs/update-delivery-design-2026-09-08.md`. Added Proposed decision D020 and
  linked the proposal from the roadmap and project index.
- Rechecked repository root, `release/2.1`, app version, PyInstaller specs,
  Windows installer template, manifest-to-website generator, and multi-window
  shutdown seams. The shared worktree already contained application and document
  changes; they were preserved. The existing formula/table implementation brief
  was not replaced by this design-only assignment.
- Verified current upstream documentation for PyInstaller, Sparkle, WinSparkle
  and MSIX. Platform integration remains a prototype gate, not a tested ICSTeX
  capability. The design explicitly separates installer failure recovery from
  post-launch rollback and requires an initial manually installed updater build.
- Documentation validation passed: relative links, code-fence pairing, and
  scoped `git diff --check`. No application source or agent-instruction changes
  were made, so the application test suite was not rerun for this proposal.
  No installed application changes, package generation, key generation, remote
  configuration, deployment, commit, push or GitHub Actions workflow was performed.

## 2026-09-08 - Formula and Table Interaction and Key Artwork Improvements

- Implemented the user's formula/table interaction request and subsequent
  structural-button visual correction in the authoritative `release/2.1`
  working tree. Existing response/preview work, instruction edits and the
  separate update-delivery design were preserved.
- Formula keyboard edits, source mode, wrappers and draft preview now stay in
  sync. Tab/Shift+Tab navigate slots; Enter does not submit. Source fallback,
  matrix package planning, revision checks, cancel and single-document Undo
  remain explicit. The compact keyboard keeps stable layouts and one submission
  action, with its alphabet view in a separate stack page.
- Ordinary tables support bounded, blank-preserving rectangular paste/copy,
  clear, draft Undo/Redo, source preview and confirmation before destructive
  shrink. Block tables bind edits to stable row/column IDs, retain zero/False,
  preserve HTML paste and group rectangular mutations into one atomic Undo.
  Oversize input is rejected without truncation or partial mutation.
- Replaced heavy solid placeholder blocks with uniform outlined slots and
  thinner vector artwork. Root bars now contain the radicand slots; script,
  matrix and cases previews share a normalized canvas. Corrected e/10 exponent
  and custom-log-base artwork while preserving action mappings. Regression
  coverage checks empty slot interiors and compact-key drawing bounds.
- Required compileall passed. Final offscreen discovery passed 912 tests in
  245.646 seconds. An earlier run had one process-tree timeout fixture error:
  its one-second deadline elapsed before `grandchild.pid` existed. That test
  passed alone, and the full suite passed on repeat without compiler changes.
  Native Cocoa math-keyboard and editor-layout checks passed 9 tests in
  1.326 seconds.
- `tools/probe_editor_interactions.py --keyboard-pages` rendered three exposed
  synthetic-only native windows and all five math-keyboard categories. Screenshots
  and `report.json` in `docs/data/editor-interactions-2026-09-08/` were inspected;
  formula drafts remained unsubmitted, table zero/False and rectangular Undo
  checks passed. Layout coverage includes 800-1040-pixel-wide formula dialogs.
- System Events could not enumerate the isolated QA process windows, so this
  is not macOS AX automation acceptance. Windows was not tested. No student
  document or OCR input was used.
- Before concurrent updater additions, the app Python tree contained 166 files
  with path/content SHA-256
  `d6093bbef62130f82f6f6d58bd21fac8075335708388291cc2340601f878b7f1`.
  Final recheck detected separate updater files and MainWindow wiring changes
  made during the test run. They were preserved and are not covered by this
  editor acceptance; the earlier whole-tree hash is not the current shared tree.
- Editor-only source scope: `app/core/blocks/table_import.py`,
  `app/core/blocks/table_model.py`, `app/core/formula_input.py`,
  `app/core/latex_insertions.py`, `app/core/table_clipboard.py`,
  `app/gui/blocks/table_editor.py`, `app/gui/formula_dialog.py`,
  `app/gui/insert_panel.py`, `app/gui/math_editor_widget.py`,
  `app/gui/math_keyboard.py`, `app/gui/table_grid.py`, `app/gui/user_guide.py`.
  These 12 files retain path/content SHA-256
  `0ff367e2189d5cd1314fac9a60c282bc899435171e5a7c54e86d90f8cdf9c7b4`
  (sorted relative path, NUL, raw bytes, NUL for each file).
- Installed-app boundary:
  `/Applications/ICSTeX.app` executable remained
  `d0f4a53af225e02ab513f50f76bbf5331e52e584aeff3eb56f9b0952040f8226`;
  it does not contain these later editor changes. No runtime dependency,
  packaging, installed-app replacement, version bump, commit, push, publication
  or GitHub Actions trigger by this editor assignment. Current state, user guide and bounded handoff were
  synchronized with this source-only result.

## 2026-09-08 - Native application update client (source-only)

- Implemented Chinese update settings, default-off daily checks, lazy native
  initialization and one process-wide Qt controller. The app menu and startup
  seams are small; unrelated editor/compiler changes and the local-installation
  task's root brief were preserved.
- Chose Sparkle 2.9.6 and WinSparkle 0.9.4 after inspecting Velopack 1.2.0's
  macOS apply/signature and failed-move cleanup paths. Replaced the earlier
  custom signed-JSON/download proposal with native appcasts and adapters; D020,
  the implementation document, roadmap and maintainer handoff reflect the choice.
- Build-bound configuration enforces source version, positive release sequence,
  target, channel, HTTPS feed and Ed25519 public key. No real configuration is
  shipped. Native automatic scheduling is disabled; Qt owns explicit consent.
  Sparkle requires signed feed/payload validation without the feed-failure
  expiration fallback, and its delegate pins the feed against legacy preferences.
  Windows ignores remote installer arguments and uses one-use exit authorization
  before launching only the native-verified local EXE.
- All-window save/exit guards cover cancellation, later save failure, unnamed
  files, conflicts, editing dialogs, Block sessions, compilation, PDF/image work,
  OCR tasks and other installed processes. Windows callback preparation is
  marshalled to Qt; cancellation/launch failure restores editing. Existing
  MainWindow close cleanup is retained. The process scan is not an installer lock.
- Required compileall passed. The final frozen Python source passed 958 tests in
  484.198 seconds; updater-focused tests passed 46 in 0.715 seconds. The latter
  include a real MainWindow synthetic save preserving cursor selection and
  scroll position. No student document was opened by this assignment.
- Exposed Cocoa source-build settings were inspected at 100% and 150% UI scale,
  at 380x314 and 444x398 logical pixels respectively. Both showed unavailable
  source-mode updates with no native backend loaded. Evidence is in
  `docs/data/app-updates-2026-09-08/`; `tools/probe_app_updates.py` reproduces it.
- Official SDK archives matched pinned upstream SHA-256 digests and staged for
  macOS arm64/x86_64 and Windows arm64/x64; native file architectures matched.
  Both macOS bridge targets compiled with warnings-as-errors. After the final
  feed delegate change, both targets were restaged and the included Sparkle
  framework passed deep strict signature verification. The arm64 bridge loaded
  from its actual Frameworks layout and safely rejected checking before init.
  A standalone bridge load without its adjacent framework failed to resolve
  `@rpath/Sparkle.framework`; the staged-layout load passed without source changes.
- The frozen app Python tree contains 170 files with path/content SHA-256
  `b002533f20a35533487f6c108c96a49163d05abfc377616a12f16d4cc60a1c7b`
  (sorted relative POSIX path, NUL, raw contents, NUL per file). In the order
  `packaging/ICSTeX.spec`, `packaging/windows.spec`, `packaging/native_updates.py`,
  `packaging/native_updates/sparkle_bridge.m`, the same hash encoding yields
  `9923f95da34c115c017d6f9f432f95699fa7fb8ba617d4704ac4627bb50d3ce8`.
  These identities were sent to the separate authorized local-installation task;
  its no-runtime build does not compile or embed the optional Objective-C bridge.
- Native Windows execution, configured Sparkle initialization, signed-feed
  delivery, real two-version installation and recovery remain unverified.
  Public update activation, signed installers, initial manual bootstrap and
  recovery gates are documented in `packaging/UPDATES.md`. No automatic rollback
  or cross-version session restoration is claimed.
- No app packaging/installation, production key generation, signing credentials,
  version bump, commit, push, publication or GitHub Actions trigger by this
  assignment. SDKs were inspected in temporary staging only; default dependencies
  and the offline ordinary-build behavior remain unchanged.

## 2026-09-08 - Latest local application synchronization

- User explicitly requested synchronizing the installed application to the
  latest working source. Confirmed the authoritative repository, preserved
  unrelated changes and coordinated the source freeze with the separate updater
  task. This local development installation is not a public release.
- `QT_QPA_PLATFORM=offscreen bash packaging/preflight.sh` passed, including
  compileall and all 958 tests in 432.518 seconds. The log contained non-fatal
  `welcome_page.py` scale callbacks accessing deleted QLabel objects; this is
  recorded separately from unittest success. Required compileall and
  `git diff --check` were also rechecked during installation handoff.
- Frozen app Python source: 170 files, path/content SHA-256
  `b002533f20a35533487f6c108c96a49163d05abfc377616a12f16d4cc60a1c7b`.
  Final 326-input path/digest manifest SHA-256:
  `aa412476927228c5c711650eff8e03375efd8da25d2aebf07de4dc9e3f57bcaa`.
  The only change after the final preflight input snapshot was the optional
  Objective-C update bridge, independently verified by the updater task; this
  unconfigured build neither compiles nor embeds it. Both snapshots were kept.
- Built with the repository PyInstaller spec into the separate versioned path
  `dist/local/ICSTeX-2.1.0-beta.1-20260908-204029-b002533f/ICSTeX.app`, using
  `build/local-20260908-204029` as the work path. The package version remains
  `2.1.0-beta.1`; the local build ID distinguishes this newer source.
- Bundle identity is `com.icstex.app`; executable, QtCore and Python framework
  are arm64. Ad-hoc deep strict signature verification passed. No Developer ID
  signing or notarization was performed. All 157 embedded app modules matched
  source bytecode/constants; one namespace package and 35 assets also matched.
- Verified a staged copy before replacement. The previous app had already
  exited; no force quit, student save or discard action was used. Renamed the
  original bundle into the user Application Support backup directory
  `ICSTeX/Install Backups/20260908-204029/ICSTeX.app`, then moved the staged
  bundle to `/Applications/ICSTeX.app`. Original bundle/executable inodes
  `223791362` / `223791367`, old SHA-256 and deep strict signature were preserved.
- Old executable SHA-256:
  `d0f4a53af225e02ab513f50f76bbf5331e52e584aeff3eb56f9b0952040f8226`.
  New executable SHA-256:
  `718e263c89dfce7eb840cddc919c76e75f3e7209ee6f0954628891599ee50d08`.
  Recursive checksum/symlink comparison between candidate, stage and installed
  copy showed no differences. `FINAL_SOURCE_SNAPSHOT.tar.gz` matched every
  manifest input; macOS resource-fork sidecars were retained. The backup also
  contains `INSTALL_RECEIPT.json`, both manifests and a read-only verifier.
- Cold launch from the exact installed path was observed as PID 45230; the
  same process remained alive about ten minutes later. Native screenshots
  showed the new outlined formula keys, blank table cells with new controls,
  and the unconfigured update dialog. Actual keypresses produced
  `\frac{a}{b}` using Tab; Enter did not submit, and Cancel retained the
  synthetic source unchanged. A rapid initial automation batch ran before the
  queued button action settled; sequential state-checked keypresses passed.
  Qt accessibility activation of a navigation toggle only changed its check
  state, so the visible control was clicked directly to open the panel.
- Update configuration/runtime is absent, daily checks and the check button
  are disabled, and no online updater acceptance is claimed. Formula/table
  drafts were not submitted; the temporary document was closed and the app
  left on its welcome page with the file toolbox restored. The student file
  seen before the update remained byte-identical by SHA-256. No new ICSTeX
  crash report was present after repeated native observations.
- This installation did not re-run a full project compile, the complete table
  mutation suite inside the packaged process, or real signed-feed delivery.
  Existing public DMG/ZIP size and modification-time records were unchanged.
  No version bump, runtime dependency, student text change, commit, push,
  publication or GitHub Actions trigger occurred. Current state and the bounded
  handoff were updated to the verified installed-build identity.

## 2026-09-08 - Accumulated source committed and synchronized to GitHub

- User authorized appropriate renaming, committing and remote synchronization.
  No concrete filename or branch mismatch required renaming; retained
  `release/2.1`, the existing commit history and the application version.
- Committed 106 reviewed files as
  `39e315e59748aa87e1b1c8b5dcf3c7b65955a4f2`
  (`feat: integrate editor and update improvements [skip ci]`). The commit
  includes response/dependency work, preview reverse SyncTeX, formula/table
  interactions, the default-offline update client, tests, documentation and
  synthetic evidence. No product source was changed by this synchronization.
- Required compileall passed. The complete offscreen unittest discovery passed
  958 tests in 245.698 seconds. The previously recorded welcome-page scale
  callback/deleted-QLabel exceptions recurred without failing the suite; no fix
  or disappearance of that issue is claimed. Source and test input fingerprints
  remained unchanged throughout the gate; the app Python tree still matches
  the verified installed build's `b002533f` fingerprint.
- Checked 202 staged or previously unpushed blob objects for private keys,
  common GitHub/API/AWS token patterns and actual maintainer/home temporary
  paths. No match was found; this is a bounded publication check, not a complete
  security audit. Eleven staged screenshots were inspected as synthetic UI
  evidence. Three original PDF-performance screenshots contain raw build logs
  and machine-local temporary paths, so they remain local and are now explicitly
  ignored by Git. The published JSON measurements were not changed; their
  README and verification report identify the screenshot-access boundary.
- Pushed the new source commit and the existing 11 local commits by normal
  fast-forward update from `bc73a1b` to `39e315e` on `origin/release/2.1`.
  A fresh `git ls-remote` returned the full source commit hash above. GitHub's
  Actions API returned zero runs for that commit. No force push, history rewrite,
  workflow/security setting change, release creation, artifact upload, version
  bump, updater activation or student-content change was performed.
- Updated the current source matrix and completed handoffs to distinguish
  synchronized repository source from unchanged public installation packages.

## 2026-09-09 - macOS arm64 Beta candidate prepared; signing awaits human authorization

- User assigned activation of macOS arm64 Beta using Vercel plus GitHub Releases,
  approved a dedicated Ed25519 key in the local Keychain, and later approved
  production publication after acceptance. Windows, Apple Developer ID signing,
  notarization and GitHub Actions remain excluded. Started from clean
  `release/2.1` at `4d15bdd`; this round remains local/uncommitted.
- Advanced source metadata to `2.1.0-beta.2` and bound the candidate to sequence
  `210002`, arm64/Beta, the existing Vercel domain and a new dedicated public key.
  Sparkle `generate_keys --account com.icstex.app.beta` reported successful
  Keychain storage; a subsequent public-key-only lookup matched the checked-in
  configuration. No private key was exported or printed.
- Revalidated Sparkle 2.9.6 archive SHA-256
  `52bf9e88cdd972fc0c81501377a880e90d47031bd8ca5462488f843e2609e192` before extraction.
  The initial bridge inherited macOS 26.0 from the host; the actual Qt 6.11.1
  QtCore slices declared 13.0. Added explicit bridge deployment target 13.0 and
  matching bundle minimum, then recompiled with warnings as errors. `vtool`
  verified the resulting arm64 bridge minimum OS 13.0. This is a binary target
  check, not a macOS 13 runtime acceptance claim.
- Initial full preflight failed two site tests because the source version had
  advanced beyond the published Beta 1 manifest. Kept the download page and old
  assets pinned to their manifest, while retaining strict source-version checks
  in release preparation and tag-at-HEAD verification. Added focused regressions
  for that boundary and the explicit bridge target. Final required compileall
  and packaging preflight passed: 962 tests in 222.579 seconds. Existing
  welcome-page scale callback/deleted-QLabel warnings recurred without failing
  the suite; they were not fixed or hidden in this task.
- Built a fresh frozen PyInstaller candidate with the opt-in runtime. The
  executable is arm64, bundle version/display version are 210002/Beta 2, and
  the embedded public configuration/plist agree. Deep strict ad-hoc signature
  verification passed. Candidate executable SHA-256:
  `4804a92062a9e2e332bfeba039ac5a349d6c28528c22024fcd38b77055b247c5`.
  Input app-tree hash is
  `7951127e915ac29d80039c7c42af86d623cf26d449462e98eff5a5203e3d4934`
  for 211 files, sorted path + NUL + file bytes + NUL, excluding `__pycache__`.
  A checksum comparison found no source-file differences from the frozen copy.
- Native candidate UI showed Beta 2, the fixed update host and automatic checks
  off. An explicit check initialized Sparkle and displayed its retrieval-error
  alert because no accepted update source was published; cancellation kept the
  application usable. No successful feed retrieval/download/install is claimed.
  QA used a temporary home, but the recent-project UI still exposed existing
  preferences, so this is not claimed as fully isolated preferences. No listed
  project or student document was opened. The native automation's post-quit
  observation relaunched its selected candidate; that exact QA process was
  terminated afterward. The original installed process remained running.
- Copied the verified candidate under
  `dist/ICSTeX-2.1.0-beta.2-macos-arm64-candidate/`; generated a symlink-preserving
  ZIP using `ditto`. Archive length 56,212,119 bytes, SHA-256
  `c58effd2ce9f0528589ada9ec4f18311870e8c0db571fecaa88a4705b9bca300`.
  Local preflight/build/launch logs remain in its `verification/` folder.
- The first `sign_update` call failed with Keychain error -60008; `security error`
  described inability to obtain authorization. The unsigned appcast was excluded
  from deployment. The verified SDK was retained under
  `dist/updater-sdk-Sparkle-2.9.6/` for the explicit human Terminal signing step
  documented in `docs/BETA_ACTIVATION_HANDOFF.md`.
- Vercel CLI download timed out and its existing login token was expired, but
  the authenticated Vercel connector successfully deployed the original website
  project as preview `dpl_7KCFhWRVwYtSdbS2WdUyavEFqobJ` (READY). URL:
  `https://website-9jgkbdafm-leoxuminghua-7962s-projects.vercel.app`.
  The preview contains unchanged website content plus update cache headers and
  no appcast; production was not promoted. No GitHub release/tag/push/upload,
  old-asset overwrite, installed-app replacement, Developer ID signing,
  notarization or GitHub Actions run was performed.
- Activation remains unfinished: human Keychain authorization, archive/feed
  signature validation, real signed two-version update and failure/recovery
  acceptance, then immutable assets and signed production feed publication.

## 2026-09-09 - Signed Beta 2 native QA completed; activation held at installation exclusion

- Maintainer completed the Keychain authorization. Official Sparkle 2.9.6 tools
  then signed local production-intended and loopback-only QA feeds/archives.
  Independent Ed25519 verification of exact feed/archive bytes passed using the
  configured public key. No private material was exported. No new signing key
  or OS security workaround was used.
- Native testing exposed obscured progress behind the Qt settings dialog.
  Fixed manual-check window handoff and added a working active-session progress
  button without changing the scheduled attempt time or auto-check re-entry
  policy. Added three controller regressions and visual coverage. Required
  preflight passed 965 tests in 215.812 seconds before the revised candidate was
  built; existing welcome/deleted-QLabel warnings remain.
- Built r2 from frozen current app/packaging source. App tree (211 files, sorted
  path + NUL + content + NUL, excluding __pycache__) SHA-256:
  `d48056f79629e13a861d9082751075134f63c854032408c19bb0e695566d5474`.
  Archive `ICSTeX-2.1.0-beta.2-macos-arm64.zip` length 56,211,122 bytes, SHA-256
  `342c0300a6d7dc82d087aaee0703576996666678c01b6b01f163c16574b1061f`;
  executable SHA-256
  `86dac5d20b468325dc147e21795324040241310898e353218b4279c586b4f9c3`.
  Signed production-intended feed SHA-256
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
  Preserved r1 separately; no published identity/asset was overwritten.
- Private QA builds changed only copied-source test seams: explicit temporary
  INI preferences, fixed loopback feed exception, QA label/sequence and local
  networking plist option. Public source remains HTTPS-only. Native signature
  and installer policy were unchanged. Served byte-identical r2 archive from a
  loopback-only server; no project contents were served or uploaded.
- Real native checks exercised HTTP 503, feed and archive tampering, no update,
  download cancellation, two-window Save/Cancel, unnamed Save As cancellation,
  and a pre-existing same-executable-path process. Successful Save/Install
  replaced bootstrap 210001 with exact r2 210002 and automatically relaunched it
  before UI automation selected it. Full bundle checksum/symlink comparison
  showed no differences; deep strict signature and independent cold launch
  passed. Synthetic source hash stayed unchanged; saved unnamed content matched
  its expected fixture. No student document was opened or edited.
- A 240 MB APFS fixture with about 24 MiB free rejected installation, preserving
  the old complete bundle. Manual cold launch passed. A read-only remount was
  rejected by Sparkle before download. A deliberately signed broken QA build
  exited 86 after installation; it did not automatically roll back. Preserved
  that installed broken bundle, restored the trusted whole old bundle, and
  verified recursive checksum, signature and visible cold launch. The test app
  and loopback server were stopped; the APFS fixture was detached.
- Inspection of Sparkle 2.9.6 InstallerProgressAppController.m lines 319-325
  found its explicit one-process/late-instance monitoring limitation. ICSTeX's
  GUI probe is not held across host exit. This is an unmet installation-exclusion
  proof obligation, not a reproduced corrupt update. The existing activation
  gate remains unchanged. Late-instance races, forced installer interruption,
  and actual public HTTPS delivery remain unverified. Native external-conflict
  and active-work fault injection is not claimed beyond automated coverage.
- Recorded the bounded implementation decision required before adding a helper,
  altering startup policy, or modifying the pinned engine. No new installer was
  introduced, and no public activation was performed. Vercel preview remains
  READY with no appcast; only GitHub v2.1.0-beta.1 is published. The installed
  application, production deployment and prior release assets remain unchanged.
  Changes remain local/uncommitted; no push, tag, release, asset upload, Windows
  activation, Developer ID signing, notarization, or GitHub Actions was performed.
- Final handoff preflight passed 965 tests in 246.461 seconds. Candidate source,
  archive and feed signatures were independently rechecked and remained equal.
  The production domain still resolved through Vercel metadata to
  `dpl_D71b854e1vvoJa4GAwfAxnEmFAfn`; GitHub still listed only v2.1.0-beta.1.
  Published-website consistency passed; strict source-version release checking
  correctly rejected the Beta 1 manifest against the unreleased Beta 2 source.
  No new matching ICSTeX/Python/Updater/Autoupdate crash report was observed.

## 2026-09-10 - Next-generation Codex development instructions (documentation only)

- Added `docs/CODEX_V1_DEVELOPMENT_INSTRUCTIONS.md` as an inactive handoff
  for a future user-started development session, and linked it from
  `PROJECT_INDEX.md`. It defines M0-M7 phases, three end-to-end user workflows,
  fifteen acceptance scenarios, preservation rules and a copyable launch prompt.
- The local source-development scope is separate from platform/user acceptance,
  packaging, installation and public distribution. Existing `FORCODEX.md`,
  Beta handoffs, signatures, update configuration and public/installed artifacts
  were not changed. The instructions require live baseline checks and preserve
  the unresolved installation-lifetime exclusion gate.
- Required compileall completed with exit code 0. Full offscreen unittest
  discovery completed with 965 tests OK in 232.304 seconds, exit code 0.
  The pre-existing welcome-page scale callback still emitted deleted-QLabel
  RuntimeError messages at `app/gui/welcome_page.py:161-172`; no application
  fix or new native GUI acceptance is claimed.
- Whitespace checks produced no diagnostics. This round changed only the new
  instructions, the index entry and this appended record; no product source,
  version metadata or student documents were edited. No commit, push, packaging,
  installation, signing, deployment or release was performed.

## 2026-09-10 - User-authorized source synchronization with held feed isolation

- User requested necessary renaming and submission after asking whether changes
  were synchronized to the GitHub remote. Live checks found `release/2.1` and
  its remote at `4d15bdd`, with Beta 2 source and the V1 development handoff still
  uncommitted. Preserved all existing source and historical records.
- Moved the unpublished signed appcast from the website tree to local-only
  `release/updates/candidates/macos-arm64-beta-r2.appcast.xml` and added a narrow
  Git ignore rule. SHA-256 before and after was
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
  No signed bytes, old artifact names, release tags or branch names were changed.
  Replaced machine-specific paths in the new development instructions with
  repository-root discovery; development and publication permissions are unchanged.
- Required compileall exited 0. Full offscreen unittest discovery passed
  965 tests in 196.352 seconds, exit 0, on macOS with Python 3.12.6. The existing
  welcome-page deleted-QLabel RuntimeError remains; no fix or fresh native GUI
  acceptance is claimed. Local test output is retained outside the repository.
- Whitespace, generated website metadata and published-release consistency
  checks passed. The strict source-version gate correctly rejected the Beta 1
  published manifest against Beta 2 source. A bounded scan of the selected files
  found no private-key blocks or common access-token patterns; this was not a
  full-history security audit. Only public update configuration was included.
- Committed 32 source/test/document/configuration files as
  `fef37316a2ffff74bee0309e2bb052628f1cfc97` with `[skip ci]`, then pushed normally
  to `origin/release/2.1`. `git ls-remote` returned the exact same SHA. No force
  push, tag, GitHub Release, asset upload, packaging, installation or signing
  occurred. The signed feed and all application archives remain local.
- Post-push GitHub checks showed no Actions run for the source commit and only
  `v2.1.0-beta.1` with nine assets. Vercel's latest deployment stayed
  `dpl_7KCFhWRVwYtSdbS2WdUyavEFqobJ`; no deployment was requested. Updated current
  state and handoffs in the follow-up documentation commit without weakening
  installation-lifetime exclusion, late-instance or interruption acceptance gates.

## 2026-09-10 - V1 M0 baseline and partial M1 read-only submission checks

- Continued the explicit local-only V1 goal from clean synchronized HEAD
  `f03776e87c0f938421a70ff5b085db920f2d01d7`, without reusing the preceding batch's
  commit/push authorization. Read the complete development instructions and
  current governance context; preserved the independent held Beta brief.
- Completed M0 capability delta, acceptance ledger, reusable new-only synthetic
  single-file/multi-file/Block fixtures and baseline response measurements.
  Baseline source digest is recorded in `docs/data/v1/m0-response-baseline.json`;
  measured targets and source/platform limitations are in the active plan.
- Added pure read-only check rules and a bounded GUI worker/panel. Ordinary
  source checks capture buffers, root, engine/tools, dependency observations and
  existing FINAL records; expose status/reason/location/input identity; and
  reject changed, cancelled, failed, late or closed-window results. No refresh
  saves, compiles, uploads or changes source. Static coverage stays UNKNOWN,
  unset word targets stay N/A, and preview is not treated as FINAL.
- Bound Block checks to the visible session and compared captured model JSON
  with safe bounded metadata reads and pure generated source. Retained pending
  save reasons are no longer used as saved-state evidence. Block FINAL/PDF are
  explicitly UNKNOWN; no direct overwrite/assembly actions are offered for
  discrepancies. Ordinary hidden source changes no longer alter the Block key.
- Native inspection exposed squeezed adjacent docks and a false metadata-event
  assumption. Tabified the bottom docks; added explicit, owner-scoped listening
  for three Block metadata files without enabling preview/build events. Replaced
  synthetic-only metadata coverage with a real polling-event test. A navigation
  test that raced an undelivered file event now waits for actual generation change.
- Fixed the known WelcomePage retained-lambda lifetime issue using a Qt bound
  slot and repeated destroyed-page/scale regression. Required compileall passed.
  Final full offscreen discovery passed 998 tests in 212.415 seconds, exit 0;
  log: `/tmp/icstex-v1-m1-block-suite-r2.log`. The focused submission/Block/watcher
  run passed 62 tests in 4.974 seconds, exit 0. The intentional worker-failure
  test now captures/asserts its expected error log. Final full output had no
  RuntimeError, RuntimeWarning or traceback; whitespace checks passed.
- Final native command was `QT_QPA_PLATFORM=cocoa python3
  tools/probe_submission_check.py --output /tmp/icstex-v1-native-20260910-m1-block-r3`.
  Exit 0; macOS 26.6.1 arm64, Python 3.12.6. App Python path/content digest:
  `7af81592d3235997563f6b835511120e26a8291d17302bab20cf96b0af08f140`.
  Verified a real one-page ordinary FINAL, child navigation line 4, invalidation,
  five scale tiers, active Block ownership, actual metadata-event invalidation,
  no Block compiler initialization, and restored original synthetic bytes.
  Inspected native images; high-scale Block editor/inspector clipping and the
  shared old source PDF remain open M2 issues, not accepted Block PDF evidence.
- No student files, installed app or release artifacts were edited. Signed
  candidate appcast SHA-256 remains
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`;
  live remote `release/2.1` remains `f03776e`. All V1 changes remain local and
  uncommitted. M1 is partial; next work is Block FINAL identity and formal-log
  coverage, then M2-M6. No packaging, installation, signing, deployment, release,
  goal-completion claim or relaxation of Beta installation exclusion occurred.

## 2026-09-10 — V1 M1 actual FINAL evidence and read-only acceptance

- Continued local V1 work without staging or changing the synchronized Git HEAD.
  Captured bounded known inputs around actual FINAL jobs and hashed the returned
  PDF before the completion callback. Current checks bind actual job identity,
  source/model revision, engine/toolchain, input observations and formal log.
  CURRENT without evidence, changed inputs/PDF, stale logs and PREVIEW cannot pass.
- Block sessions now set model revisions on compile jobs, accept each result once
  on their Qt thread, reject old/duplicate/closed callbacks, and retain FINAL
  separately from PREVIEW. Block display no longer mutates ordinary-source PDF
  state; background Block completion cannot replace a source PDF. Existing Block
  save behavior is preserved, and M2/M4 conflict/draft work remains explicit.
- Required compileall and whitespace checks passed. Focused tests passed 98 in
  6.857 seconds; final full command `QT_QPA_PLATFORM=offscreen python3 -m unittest
  discover -s tests` passed 1009 in 230.919 seconds, exit 0. Log:
  `/tmp/icstex-v1-m1-final-binding-suite.log`. No traceback, RuntimeError or
  RuntimeWarning was found in that final full output.
- Final native command: `QT_QPA_PLATFORM=cocoa python3
  tools/probe_submission_check.py --output /tmp/icstex-v1-native-20260910-m1-final-r2`,
  exit 0. Both ordinary and Block workflows generated and displayed an actual
  one-page XeLaTeX FINAL; Block completed exactly once. Input/PDF/log checks pass
  only for matching current evidence. External metadata and generated-child edits
  invalidate/reject old evidence. Synthetic originals were restored byte-exactly.
  Five scale tiers were exercised. App Python path/content SHA-256:
  `4a4e58ca20356a22000d86a9a45fa81b0adf68566411368b68c85e1dd8a55116`.
- Detailed mechanism, native evidence and limits are in
  `docs/v1-m1-final-evidence-2026-09-10.md`. M1 read-only acceptance is complete;
  before/after sampling is not M5 frozen-input delivery. M2–M6, Block high-scale
  layout/close conflicts, IME/AX/Windows/human acceptance remain incomplete.
  No commit, push, package, installation, signing, deployment or release action.

## 2026-09-10 — V1 M2 declarative project profile slice

- Added optional version-1 `.icstex/project-profile.json` and an explicit scoped
  editor. Existing template/engine choices are recommendations; directory hints
  are not created and no course limit is invented. Word targets and static-check
  visibility affect M1 checks; absent/disabled/invalid states are distinguished.
  Core FINAL/PDF/log/saved-input guards cannot be disabled. Visible Block scope
  is used instead of a hidden ordinary tab.
- Profile reads are bounded to 64 KiB, strictly decoded, repeated for consistency
  and protected by existing safe project reads. Unknown/duplicate/executable
  fields and unsafe suggestions are rejected. Atomic single-file CAS preserves
  external winners and the UI draft; POSIX temp creation/replacement is anchored
  to a non-symlink directory descriptor. Extracted the existing MCP project lock
  without changing its identity/authority; GUI profile saves refuse a busy lock
  immediately. This is not a frozen project snapshot or an external-editor lock.
- Added exact-profile-only watcher opt-in and invalidation, no implicit refresh
  during typing. Dialog Save/Cancel, two-writer CAS, oversize/unknown input,
  symlinks, disk failure, mid-save changes, active Block scope, actual file events
  and five-scale keyboard access have focused regressions.
- Required compileall and `git diff --check` passed. Final focused suite passed
  104 tests in 20.680 seconds, exit 0; log
  `/tmp/icstex-v1-m2-profile-focused-r4.log`. Initial full discovery passed 1028
  tests in 225.637 seconds but was superseded by final plain-text UI hardening,
  a directory validation adjustment and the added visual regression. Final
  `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests` passed 1029
  tests in 329.444 seconds, exit 0; log
  `/tmp/icstex-v1-m2-profile-suite-r2.log`. No traceback, RuntimeError or
  RuntimeWarning in the final output; offscreen size-hint warnings remain.
- Native command: `QT_QPA_PLATFORM=cocoa python3 tools/probe_project_profile.py
  --output /tmp/icstex-v1-native-20260910-m2-profile-r3`, exit 0. macOS 26.6.1 arm64,
  Python 3.12.6; app Python path/content digest
  `cc34365cc2dc294c1888bd06321be785a423eadb70c4d6b9821edfc2a5778da4`.
  Real one-page FINAL bytes/build identity and original synthetic sources remained
  unchanged. Keyboard cancel wrote nothing; Save applied the word target, a real
  file event invalidated the old check, and the next check showed the target
  failing while FINAL still passed. Conflict/disable and five scale tiers passed;
  lower fields, visible buttons and conflict/target-result images were inspected.
  Source cursor and scroll stayed unchanged. No native traceback/RuntimeError/
  RuntimeWarning/IMK or table-bounds warning in the final probe output.
- Evidence and limits: `docs/v1-m2-profile-verification-2026-09-10.md`. M2 profile
  slice accepted locally; full M2–M6 are still incomplete. Next slice is safe
  project creation and coherent workbench/onboarding, then Block layout/close
  conflicts. IME/AX/Windows/human and release gates remain separate.
- HEAD remains `f03776e`; signed candidate appcast SHA-256 remains
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
  All V1 work remains uncommitted. No package, installed-app replacement,
  credentials, deployment, release or goal-completion action occurred.

## 2026-09-10 — V1 M2 creation and workspace slice

- Added Chinese-name project creation with destination/template preview, explicit
  engine selection, optional profile, missing-tool guidance and preservation of
  the existing window by default. Validate before mutation, reject all existing
  targets, create files exclusively and verify bytes. Partial new directories are
  retained and reported as failed, never silently opened as a successful project.
- Added a full-width workspace presentation row using existing cached root/save/
  FINAL state and existing navigation/action guards. Child source navigation
  preserves project asset/search scope. Block uses the visible session's engine,
  and source-only toolbar controls remain hidden through real layout. Clean Block
  close restores source controls and its FINAL. No new universal session or
  automatic profile application to existing projects.
- Required compileall and diff check passed. Focused suite: 203 tests, 26.188
  seconds, exit 0 (`/tmp/icstex-v1-m2-workspace-focused-r6.log`). Final full command
  `QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest discover -s tests`:
  1042 tests, 396.325 seconds, exit 0
  (`/tmp/icstex-v1-m2-workspace-suite-r2.log`), no traceback/RuntimeError/
  RuntimeWarning/fatal Python error. Superseded full run was stopped after later
  source changes; it is not acceptance evidence.
- Native `tools/probe_workspace_flow.py`, Cocoa, output
  `/tmp/icstex-v1-native-20260910-m2-workspace-r6`, exit 0. Real keyboard-operated
  Chinese wizard -> explicit one-page FINAL -> read-only checks -> byte-identical
  PDF export -> second-window reopen. Create/open did not compile. Source bytes
  stayed unchanged; input coverage stayed unknown. Source/Block/header/wizard
  captured at five scales; clean Block close restored the source FINAL.
  App Python path/content SHA-256:
  `9d713aa8350aa690ff9b6e516b35cdc78c179f8c7cff83a916fae0a5590a5be9`.
- Failure history and limitations are recorded in
  `docs/v1-m2-workspace-verification-2026-09-10.md`: early Qt timer SIGSEGV causal
  uncertainty remains despite later green runs; native IMK/table warnings and
  Block editor/inspector clipping persist. Global-stylesheet sampling in a large
  test process is not a product performance benchmark. Pending Block edits,
  external conflicts and whole-window close are not accepted by a clean-close test.
- Next active slice remains M2 Block layout/pending-edit close protection, then
  the remaining M3-M6. No restart of completed M0/M1, architecture promotion,
  credentials, package, installed-app replacement, signing, deployment or release.
- Live `git ls-remote` still matched HEAD `f03776e87c0f938421a70ff5b085db920f2d01d7`;
  the previous source-sync batch is complete, while subsequent V1 work stays
  uncommitted under the active local-development instruction. The signed local
  candidate hash remains `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

## 2026-09-10 — V1 M2 guarded Block save and close slice

- Preserved the existing Block session, formats and command stack. Captured
  original metadata/generated ownership; safe bounded reads, cooperating project
  lock, before/after byte rechecks and conditional rollback now refuse lossy,
  unknown, external and unsafe-path writes. Bounded pending recovery evidence is
  staged before project replacement. Partial/unresolved evidence blocks retry;
  it is neither an OS-atomic project transaction nor an accepted M4 checkpoint.
- Save persists metadata and corresponding managed TeX without compiling. A real
  native save-close-reopen run exposed the earlier metadata-only save defect;
  the red regression and corrected generation/readiness expectations are retained.
  A malformed legacy table draft also reproduced silent empty-table conversion;
  validation now retains the unknown payload and refuses unsafe saving.
- MainWindow/Block close and owned-dialog Escape use Save/Discard/Cancel before
  shutdown, with Block auto-writes paused throughout Source and Block prompts.
  Conflict keeps the window, draft and external winner. Explicit Discard and
  shutdown ignore late writes/results. Stop no longer closes the session. Visible
  FINAL uses the existing asynchronous compiler; Source/PDF ownership stays separate.
- Required compileall and `git diff --check` passed. Final focused suite:
  255 tests, 24.633 seconds, exit 0 (`/tmp/icstex-v1-m2-block-focused-r6.log`).
  Final full discovery: 1068 tests, 389.469 seconds, exit 0
  (`/tmp/icstex-v1-m2-block-suite-r2.log`); no Python traceback, RuntimeError,
  RuntimeWarning or fatal Python error. Superseded r1 was intentionally terminated
  after the reopen fix became necessary; its interrupt and exit 143 are not
  successful validation. A later sampling attempt found the final test process
  already exited; it produced no performance evidence.
- Native `tools/probe_block_close.py`, Cocoa, output
  `/tmp/icstex-v1-native-20260910-m2-block-close-r4`, exit 0. Real modal keyboard
  Save/Cancel/Discard, saved-model reopen, actual one-page FINAL, conflict refusal,
  owned-dialog close and late-callback protection passed. The PDF text contains
  the saved synthetic draft; final SHA-256
  `f828a65f684839173d3c4ef9a6dc40b910071e25e2094816c5c42b6c069d87cd`.
  Small-sample FINAL dispatch was 2.450 ms with 97 GUI heartbeat ticks during
  compilation, not a general performance claim. Source PDF/cursor/scroll remained
  unchanged. Same-source r3/r4 final, cancel, error and retained-draft images were
  inspected. Font-alias warning remains; no Python exception in the final native log.
- Same-source `tools/probe_workspace_flow.py` r7 also exited 0: Chinese creation,
  FINAL/check/export/reopen and clean Block close still passed, with unchanged
  synthetic source bytes. The workspace probe recorded table-bounds/font-alias
  warnings. No new Python crash report was found; earlier timer SIGSEGV causal
  uncertainty and IME/AX/Windows/human acceptance remain open. Block narrow/high-
  scale controls still clip; next active slice is layout/keyboard reachability.
- App Python path/content SHA-256 for these runs:
  `4c0b3b607adaec9aea9340c6f8bb25206e10cc99cb9cfd490532bd3864cbcd0d`.
  Detailed reproducibility and limits:
  `docs/v1-m2-block-close-verification-2026-09-10.md`. M2-M6 remain incomplete;
  M4 still owns explicit recovery to a new directory and M5 frozen delivery.
- Live remote `release/2.1` remained at HEAD `f03776e87c0f938421a70ff5b085db920f2d01d7`;
  V1 work stays uncommitted. Signed candidate appcast SHA-256 remained
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
  No commit/push, package, installed-app replacement, credentials, signing,
  deployment, release or goal-completion operation occurred.

## 2026-09-10 — V1 M2 Block layout/keyboard reachability verified locally

- Retained the existing Block session, command stack, guarded model writer and
  shared Source/PDF ownership. Added whole-button wrapping, scroll containment,
  contextual inspector rows, first-window scale registration and explicit narrow
  editor/PDF switching. Real Block toolbar actions replace Source placeholders;
  standalone dialogs retain their compile controls.
- Reproduced and fixed layout projection changing loaded middle/error values,
  ineffective slot-weight editing and removal of unedited fallback fields.
  Selected-slot edits preserve other slot fields/selection and enter one Undo.
  Physical Control+Tab focuses Apply without committing; ordinary Tab and text
  Undo/Redo remain local. Detailed files and red/native attempts are in
  `docs/v1-m2-block-layout-verification-2026-09-10.md`.
- Required compileall and `git diff --check` passed. Final focused GUI/layout
  run: 82 tests, 27.638 seconds, exit 0, log
  `/tmp/icstex-v1-m2-block-layout-focused-r6.log`. Full discovery: 1076 tests,
  539.011 seconds, exit 0, log `/tmp/icstex-v1-m2-block-layout-suite-r1.log`.
  No Python traceback/RuntimeError/RuntimeWarning/fatal error in the full log;
  offscreen plugin warnings remain. No app source changed during the full run.
- Native Cocoa layout r6, close r5 and workspace r8 all exited 0 on app Python
  path/content SHA-256
  `ea723c4ae672e8504fa3213efbc83b228ca22e04ce9e2c0032d377b81e9adcea`, rechecked afterward.
  Evidence directories begin `/tmp/icstex-v1-native-20260910-m2-` and end
  `layout-accept-r6`, `block-close-r5`, `workspace-r8`. Five scales and two sizes,
  whole-button scroll reachability, keyboard local/global Undo, explicit Save
  without compilation, actual FINAL, PDF identity/zoom and Source cursor/scroll/
  byte preservation passed. Selected narrow/wide/FINAL and conflict-dialog
  screenshots were inspected. The 150%/1080 center body is 111 logical pixels:
  scrolling is needed; this is not simultaneous full-editor visibility.
- Save/Cancel/Discard, reopen, conflict preservation and late callbacks were
  reverified. The retained one-page close-probe FINAL contains the saved draft,
  SHA-256 `87f22e8dcbd2d5adde50a7ead402af9102828e92961d46d4b72534fd1c033550`.
  The same-source Chinese create/FINAL/check/PDF export/reopen flow also passed.
  Font-alias warnings remain in native logs, and workspace still emits a table-
  bounds warning. No new Python crash report was found in the directory check;
  earlier timer SIGSEGV, IME/AX/Windows/human acceptance remain open.
- The full suite ran longer than the preceding 389.469-second run. A read-only
  live one-second sample showed Qt application stylesheet/CSS work and 2.1 GB
  process footprint (2.2 GB peak); this is not an isolated app benchmark or proof
  of a leak. Preserve `/tmp/icstex-v1-m2-block-layout-suite-sample-r1.txt` as an M6
  investigation signal. Do not equate full-suite success with performance pass.
- A separate synthetic reproduction confirmed unapplied Inspector text is not
  reflected in `has_unsaved_changes` and is lost on `refresh()`. This pre-existing
  editor-draft gap remains unresolved and is the next active M2 safety slice;
  model close protection does not cover every widget draft. M2-M6 remain incomplete.
- Live remote `release/2.1` still matched HEAD
  `f03776e87c0f938421a70ff5b085db920f2d01d7`; signed local candidate feed remained
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
  V1 changes remain uncommitted. No commit/push/rename, package, installed-app
  replacement, credential action, signing, deployment or publication occurred.

## 2026-09-11 — V1 M2 unapplied Inspector properties verified locally

- Added pure target/base property-draft rules and session-visible pending state.
  Refresh, selection and local text Undo preserve unapplied fields without model
  edits, disk writes or compiler authorization. Pending properties pause automatic
  save/preview and invalidate saved/FINAL readiness. Alias/text/heading/image and
  selected layout/slot-parent properties are covered; untouched values, unknown
  fields and pt gap units are preserved.
- Explicit Apply or a confirmed batch validates all captured bases before one
  model Undo command. Save/close/FINAL explain application of pending properties;
  cancellation, changed confirmations, newer re-entrant input and deleted/changed
  targets retain drafts. External save conflicts preserve both memory and disk
  versions. This is memory-only protection, not M4 crash recovery or a checkpoint.
- Required compileall and `git diff --check` passed. Focused suite: 115 tests,
  91.311 seconds, exit 0 (`/tmp/icstex-v1-m2-property-drafts-r5.log`); a later
  EOF-only whitespace cleanup was covered by native/full validation. Final full
  discovery: 1098 tests, 1677.963 seconds, exit 0
  (`/tmp/icstex-v1-m2-property-drafts-suite-r1.log`). No Python traceback,
  RuntimeError, RuntimeWarning or fatal error; offscreen plugin warnings remain.
  No app source changed during the full run. App Python path/content SHA-256:
  `e675b187e1b02c5b69afd8730d9c53b073e56f7d38fb72eae79859145e43970d`, rechecked afterward.
- Three same-source Cocoa probes exited 0: property drafts r5, layout acceptance
  r7 and Block close r6 under `/tmp/icstex-v1-native-20260911-m2-`. They verified
  native keyboard text/confirmation paths, cross-object draft retention, five
  scale tiers, batch application, Save-close-reopen, conflict preservation and
  actual FINAL. Source PDF/cursor/nonzero scroll/bytes remained intact. The retained
  one-page property FINAL contains the applied synthetic draft, SHA-256
  `57ee2d8059ab29b071aa052102d67d85b95fa8be9cdbc7bdc3c282a383552568`.
  Final PDF, 150% draft, Save-close and external-conflict screenshots were inspected.
  Font-alias/table-bounds warnings remain; no new Python crash report was found.
- Full-suite duration exceeded the preceding 539.011-second run. A one-second
  sample again found QApplication stylesheet/CSS work and a 2.1 GB footprint;
  receipt `/tmp/icstex-v1-m2-property-drafts-suite-sample-r1.txt`. A later machine
  sample showed substantial swap use. These are investigation signals, not an
  isolated app benchmark, proof of a leak or attribution solely to this patch.
  M6 retains window/style lifetime, earlier timer-crash causality and separate
  native IME/AX/Windows/human acceptance. Next full discovery should be verbose.
- Independent synthetic, no-project-directory/no-compiler reproductions found
  two still-open M2 defects: selecting the second table opens/edits the first
  registry table, and an accepted formula modal overwrites a target changed while
  the dialog was open. Image replacement's modal path remains untested. The next
  bounded slice fixes secondary editor target/revision ownership; M2-M6 are not
  complete. Details and failed runs are in
  `docs/v1-m2-property-draft-verification-2026-09-11.md`.
- Live remote `release/2.1` matched HEAD
  `f03776e87c0f938421a70ff5b085db920f2d01d7`; the signed local candidate feed remained
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
  V1 work stays uncommitted. No commit/push/rename, packaging, installed-app change,
  credentials, signing, deployment or publication occurred. Beta holds remain.

## 2026-09-11 — V1 M2 secondary editor targets, focused/native verified; full pending

- Implemented explicit multi-table target/cache/draft ownership, live-cell dirty
  tracking, captured-base table batches and one global Undo without first-table
  synchronization. FormulaTab/Inspector share guarded modal application; stale
  accepted text is retained. Deleted pending targets reopen, tuple draft-choice
  selection survives refresh, and exact-draft Discard refuses newer input. The
  image picker changed-target reproduction now refuses copying before mutation.
- Native testing found an additional Enter/immediate-Save-or-switch stale delegate
  commit warning. Two red regressions reproduced it. Delivering only the existing
  delegate's queued MetaCall before manual closure fixed both; native replay has
  no stale commit warning. No general GUI event pumping or warning suppression.
- Frozen app Python path/content SHA-256:
  `caac75122b49f7a0e283cf1a8203a1beaa62d5d458b9c67ad21eb24abc1b1625`.
  Required compileall and diff whitespace checks passed. Focused final-source
  170 tests passed in 91.731 seconds, exit 0; the new target module has 22 tests.
  Full verbose r2 is still running in `/tmp/icstex-v1-m2-editor-targets-suite-r2.log`
  (owned process 71286, exec session 78934). Do not count this as full acceptance.
  Full r1 was superseded by the native-found app change and terminated with 143;
  its earlier SIGINT was caught inside a Qt callback, not a functional test result.
- Four same-source Cocoa probes exited 0: editor targets r5, property drafts r6,
  layout r8 and Block close r7. Actual two-table edits, local/global Undo, formula
  Cancel/Apply/stale-base conflict, guarded Save/close/reopen and visible FINAL
  passed while Source PDF/cursor/nonzero scroll/bytes were retained. The one-page
  target FINAL visibly contains both intended tables and `x+4`, SHA-256
  `9cd54006f5ec4de503dfe39ea14b218a44c490f7c149443b359daa9035734ba5`.
  Final/150%/formula-conflict/external-conflict screenshots were inspected. Real
  native activation was required; early focus-failed attempts are not acceptance.
  Font-alias, table-bounds and input-service warnings remain; no new Python crash
  report was found in the contemporaneous check. IME/AX/Windows/human gaps remain.
- Slow full-suite scaling has bounded diagnostic evidence: the isolated nine-test
  scale module passed in 6.648 seconds. Eight submission GUI tests passed in
  4.607 seconds but left 8 closed MainWindows/5518 widgets after GC/deferred-delete;
  explicit synthetic window disposal left no MainWindow and 7 widgets. This is
  fixture-retention evidence, not an app-wide leak conclusion. A one-second full
  process sample again shows QApplication stylesheet work (1.8 GB footprint,
  2.0 GB peak). Fix test fixture disposal after capturing the frozen full result.
- A next-slice synthetic image import reproduced an internal `assets/images`
  symlink writing into a sibling directory while returning a project-relative
  path; original source bytes stayed intact. This remains unfixed; picker target
  protection is not full asset safety. M2-M6 and independent Beta gates remain
  open. Details: `docs/v1-m2-editor-target-verification-2026-09-11.md`.
- Live remote still matches local HEAD
  `f03776e87c0f938421a70ff5b085db920f2d01d7`; local signed candidate feed hash remains
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
  No staging/commit/push/rename, packaging, installed-app replacement, credentials,
  signing, deployment or release action occurred. V1 development stays local.

## 2026-09-11 — User-authorized V1 branch rename and source checkpoint synchronization

- The user explicitly requested the needed rename and submission after asking
  whether the work had reached GitHub. Renamed the local `release/2.1` branch to
  `codex/v1-development`, removed its old upstream and pushed the development
  branch with a new matching upstream. No reset, force push, remote branch
  deletion, merge, tag or PR creation. This authorization applies only to this
  checkpoint, not future automatic commits or releases.
- Source commit `e78c2cda19a89d1c0a90c49255bf9b376350f4f3` contains the existing
  V1 source, tests, probes, synthetic measurements and documentation (91 files).
  `git ls-remote` independently matched that SHA on `codex/v1-development`;
  remote `release/2.1` remains `f03776e87c0f938421a70ff5b085db920f2d01d7`.
  GitHub API reported zero Actions runs for the source commit using `[skip ci]`.
- Required compileall and staged whitespace checks passed. The complete verbose
  offscreen suite passed 1134 tests in 872.176 seconds, exit 0, receipt
  `/tmp/icstex-v1-source-sync-20260911-tests-r1.log`. App path/content SHA-256 was
  unchanged before and after:
  `5acfce28d24ebcb2fe9b87ba56cfc9bb9f47d68e7e26d8b452db3affe599cce5`.
  Staged app/test files matched the tested working bytes. No traceback,
  RuntimeError, RuntimeWarning, fatal Python or stale delegate commit warning
  appeared; offscreen warnings and slow full-suite scale checks remain.
- The preceding secondary-editor full run is now terminal: 1122 tests passed in
  996.164 seconds on `caac75122b49f7a0e283cf1a8203a1beaa62d5d458b9c67ad21eb24abc1b1625`,
  receipt `/tmp/icstex-v1-m2-editor-targets-suite-r2.log`. The prior log's running
  status described that earlier observation, not the present state.
- Subsequent image import uses guarded staging/exclusive publication and captured
  drop targets. Nine core and four navigation checks passed; final focused
  integration passed 182 tests in 15.752 seconds. Failed copying, observed source/
  destination changes, internal links, collision winners and closed sessions have
  explicit regression coverage. Submission-check/navigation fixture disposal is
  test-only. The new drop fixture's borrowed QMimeData caused one exit 139 before
  it was retained correctly; this does not resolve older native crash causality.
- Actual Cocoa image picker cancellation reached zero-mutation assertions, but
  successful PNG selection/import remained incomplete. Stopped only the owned
  synthetic probe when the source-sync request arrived; no native image acceptance
  is claimed. Resume through `docs/V1_IMPLEMENTATION_PLAN.md` and
  `docs/v1-m2-image-import-verification-2026-09-11.md`. M2-M6, IME/AX/Windows/human
  acceptance and independent Beta installation gates remain open.
- No packages, installed apps, versions, workflow settings, website files,
  credentials or release assets were changed. The signed candidate appcast stays
  ignored and local with SHA-256
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
  Live GitHub release listing still showed only the Beta 1 prerelease. Changed
  files passed a bounded common-key/token/path scan, not a full security audit.

## 2026-09-11 — Local formula replacement and paste fidelity, native held by lock screen

- Reproduced invalid new envelopes accepted when replacing a valid formula, and
  visual paste folding comment newlines into spaces. The pure edit-plan guard now
  validates new replacement text; paste keeps exact body text and uses the existing
  literal fallback when the tree cannot round-trip. No parser or source-format change.
- App SHA-256 `0c430570de459bea98fd81452a122e3af3a09a24f7f3365c68c0ac0794014ea5`
  was unchanged before/after verification. Compileall/diff checks passed; focused
  138 tests passed in 3.669 seconds and full verbose discovery passed 1140 tests
  in 563.678 seconds, exit 0. Full receipt:
  `/tmp/icstex-v1-m2-formula-fidelity-suite-r1.log`. No traceback, RuntimeError,
  RuntimeWarning or fatal Python failure appeared; offscreen warnings remain.
- A same-source offscreen dialog's actual paste/edit plan compiled through the
  real pdfLaTeX FINAL path with unchanged synthetic source bytes. Extracted and
  rendered PDF content visibly includes `x + a + b + z`; PDF SHA-256
  `33258250942ef69afd8a2b195a9924b901f2c4d7696582e4c84b3526fdc0f008`.
  Report/PDF/render remain in `/tmp/icstex-v1-formula-final-20260911-r1`.
  This is actual compile evidence, not native screen/clipboard/IME acceptance.
- The desktop tool reported a locked Mac and required manual unlock. No bypass
  was attempted. Image native r3 was stopped at the first picker when the app
  source changed; it is not accepted. M2 native image/formula, IME/AX/Windows/human
  checks remain open. Details: `docs/v1-m2-formula-fidelity-verification-2026-09-11.md`.
- Independent synthetic M3 orientation confirmed the old missing-source search
  hashes a project-external file through a link and hashes internal `.git/config`,
  reporting both as moved candidates. Receipt:
  `/tmp/icstex-v1-m3-source-boundary-red-r1.log`. This remains the next bounded
  fix, not a completed M3 implementation or an incident involving real user data.
- No staging, commit/push/rename, packaging, installed-app replacement, credentials,
  signing, deployment or publication. The earlier one-time sync permission is spent.

## 2026-09-11 — Local bounded source status and affected-Block navigation

- Replaced unbounded synchronous source hashing/search with explicit background
  observations, one active/latest pending request and cooperative cancellation.
  Source paths reject observed links/internal paths; POSIX directory enumeration
  is descriptor-anchored. Shared candidate search covers same-extension CSV/XLSX
  only, with 2000-record/entry, 64 MiB file and 256 MiB batch limits. Ambiguity,
  errors, changed reads and limit exhaustion remain unknown, not a safe-merge claim.
- The Sources tab is now labelled 来源, read-only and dated. It shows baseline/
  observed digests and candidate paths, and navigates existing provenance-linked
  Blocks. Removed the old resync action that only advanced a digest; no data
  import, baseline update or technical merge is implied. Filtering does not rebuild
  source/layout panels; model refresh never launches source I/O.
- Core red tests and synthetic probes reproduced the old outside-link/internal
  reads and false moved/ambiguous/error behavior. Follow-up reappearance during
  search also reproduced a false moved result. GUI/probe fixture setup errors were
  corrected without weakening the guarded writer or source checks; exact scope is
  in `docs/v1-m3-source-status-verification-2026-09-11.md`.
- Frozen app SHA-256
  `6c87ebcf98f88c87f1ae43a89ee79f34310ea69ee45fb4bcee3508fc4765e020`
  remained unchanged after compileall/whitespace checks, 82 focused tests
  (2.311 seconds, exit 0) and 1168 full verbose tests (477.939 seconds, exit 0).
  Receipts: `/tmp/icstex-v1-m3-source-focused-r2.log` and
  `/tmp/icstex-v1-m3-source-suite-r1.log`. Exec 70944/PID 84015 are terminal.
  No traceback, RuntimeError, RuntimeWarning, fatal Python or failed test appeared;
  offscreen/font-alias warnings and broader M6 performance/lifecycle gaps remain.
- Final-source synthetic offscreen refresh actually distinguished unchanged,
  changed, same-content candidate and missing sources, selected the linked table,
  and left every project byte, source baseline, table content and Undo count
  unchanged. Reloading preserved them. Report/render:
  `/tmp/icstex-v1-source-status-20260911-r3/`, product log
  `/tmp/icstex-v1-m3-source-product-r3.log`, exit 0. Render inspected; not native
  acceptance. The last desktop state still requires manual unlock; no bypass.
- Read-only orientation for the next citation slice reproduced duplicate-key
  collapse, optional-citation misses, commented-citation false positives and
  ignored nondefault bibliography paths in existing helpers. Receipt:
  `/tmp/icstex-v1-m3-citation-orientation-red-r1.log`; exit 0 confirms existing
  failures, not a fix. Citation code was not changed during this frozen full run.
- Live remote development HEAD remains `e5cd13273ee6de326bc629e65c0752a9f474848e`;
  release/2.1 remains `f03776e87c0f938421a70ff5b085db920f2d01d7`. No staging,
  commit/push/rename, packaging, installed-app replacement, credentials, signing,
  deployment or publication. Ignored signed feed SHA-256 is still
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

## 2026-09-11 — Local read-only citation health and usage navigation

- Added bounded ordinary-source citation/BibTeX syntax and health checks, a focused
  background controller and the ReferencesPanel health tab. Explicit checks use
  declared static libraries and captured editor buffers, retain key definitions/
  uses with file/line locations, distinguish duplicate/missing/unparsed states and
  unused suggestions, and recheck content before navigation. One active/latest
  request, cancel, edits, external events, mode/tab changes and close guard results.
  No check-induced save, compile, import, network lookup, normalization or deletion.
- The conventional shortcut library is now labelled separately and uses bounded
  strict safe reads. Regressions reproduced and fixed missing distro-input
  misclassification, empty-file recheck errors, false complete manual/scoped/alias
  coverage, link reads, replacement decoding and macOS selected-directory aliases.
  Field/use/relation limits and nonstandard source-suffix uncertainty remain visible.
  Technical repair, arbitrary macro execution and M1 rule replacement are not implied.
- Frozen app SHA-256
  `a12ade12f6d5573f99a03e83f8ef9e3b784538b5c0cfc4cbe520ba0ad9a84baf`
  remained unchanged after compileall, 36 focused tests (1.434 seconds, exit 0),
  80 integrated tests (9.495 seconds, exit 0) and 1200 full verbose tests
  (559.206 seconds, exit 0). Full exec `33298` / PID `88960` are terminal, receipt
  `/tmp/icstex-v1-m3-citation-suite-r1.log`. No test failure or Python exception
  appeared. Scale-phase sampling still shows QApplication stylesheet work and
  about 2.0 GiB process footprint; substantial system swap and full-suite fixture
  retention prevent attributing that observation to this patch alone.
- Final-source actual offscreen window probe checked duplicate/missing/unused
  entries, jumped to `chapters/child.tex:2`, checked unsaved BibTeX, and cancelled
  with zero source-byte changes and no compile authorization. Five scale tiers
  and two requested sizes retained button access via scrolling; the smaller request
  clamped to existing 1080x720 minimum. This is not native/narrow-screen acceptance.
  Separate explicit BibTeX 0.99d / TeX Live 2025 FINAL used four entries and produced
  one visually inspected page, including strings/concatenation, crossref and nocite.
  PDF SHA-256 `d9a5d659c8a3c4c5a39d9126bf67dd29154c6ba433774c2e715595728b52a811`.
  Evidence `/tmp/icstex-v1-citation-20260911-r3/`, product log
  `/tmp/icstex-v1-m3-citation-product-r3.log`, exit 0. Probe fixture corrections and
  primary grammar reference are documented in
  `docs/v1-m3-citation-health-verification-2026-09-11.md`.
- Next material slice orientation reproduced saved-buffer double counting,
  comment use, graphicspath misses and stale disk use after an unsaved removal.
  Synthetic receipt `/tmp/icstex-v1-m3-material-orientation-red-r1.log`, exit 0
  confirms old behavior, not a fix. No material code changed during the full run.
- Native M2/M3 waits for manual Mac unlock; IME/AX/Windows/human checks, material
  tracking, separately confirmed repair, M4/M5 and M6 remain incomplete. No staging,
  commit/push/rename, packaging, installed-app replacement, credential, CI, signing,
  deployment or publication. Remote development remains `e5cd132`, release remains
  `f03776e`; ignored signed feed retains SHA-256
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

## 2026-09-11 — Local read-only material usage and content observations

- Added bounded ordinary-source material usage/content checking, a focused
  background controller and the ImagesPanel health tab. Supported literal image,
  SVG/PDF and graphicspath locations use captured root/buffer ownership; comments
  and duplicate saved-buffer reads no longer create uses in the new check. Missing,
  changed, same-content candidate, ambiguous and unused-suggestion states remain
  distinct. Unsupported/incomplete static coverage stays unknown. Rereads and
  late-event invalidation prevent observed changed inputs from passing as current.
- Previous readable digests are bounded window/root-local observations, not stored
  provenance or backups. The shortcut inventory now displays usage pending and
  reuses an in-memory metadata index without loading/saving project cache files.
  Typing and the health tab do not launch the old source-usage scanner. The new
  check does not decode thumbnails, save, compile, import, rename or rewrite files.
- First full discovery failed one old disk-cache assertion: 1223 tests in 368.431
  seconds, exit 1, exec `15407` terminal, receipt
  `/tmp/icstex-v1-m3-material-suite-r1.log`. Its replacement verifies same-index/
  record reuse, one metadata read, no load/save or project-byte changes and no
  compile authority. The stronger test exposed warm scans incorrectly counted as
  cold; the corresponding red receipt is
  `/tmp/icstex-v1-m3-material-memory-index-red-r1.log`. That metric is now corrected.
- Final app SHA-256
  `cc506a5a59b3f4e187937ed4283650b53f6b7de817c7f249f7896b3f7e5fa61e`
  passed compileall, whitespace checks, 109 focused integration tests (9.786 seconds,
  exit 0) and 1223 full verbose tests (364.943 seconds, exit 0). Full exec `96648` /
  PID `96374` are terminal and the app hash was rechecked unchanged. Receipts:
  `/tmp/icstex-v1-m3-material-focused-r3.log` and
  `/tmp/icstex-v1-m3-material-suite-r2.log`. No failed test or Python exception was
  found; offscreen/font warnings and native lifecycle/performance gaps remain.
- Final-source actual offscreen product r4 used five real synthetic PNGs, root/child
  graphicspath sources and isolated settings. It verified changed/missing/candidate
  distinctions, child line-4 navigation with PDF view preserved, noncurrent draft
  precedence and cancellation with zero source/asset/cache writes. A separate
  explicit pdfLaTeX FINAL produced one visually inspected page, PDF SHA-256
  `ddb60095102d50de0b549316052306243bddf050f37afc84e080cd193845aed7`.
  That compile created its existing history records without changing original
  input bytes; later read-only checks did not recompile the stale PDF. Product
  exec `3179` exited 0, log `/tmp/icstex-v1-m3-material-product-r4.log`, evidence
  `/tmp/icstex-v1-material-20260911-r4/`.
- Actual queued watcher events invalidate results, including during this fixture;
  the probe observed them and explicitly retried (1, 4 and 1 attempts), without
  suppressing invalidation. The 621.71 ms five-asset measurement includes a 600 ms
  settle wait and is not worker latency. Five scales/two requested sizes retained
  scroll access to control centers; high-scale text/columns still require scrolling
  and the smaller request clamps to 1080x720. Captures were inspected, not accepted
  as native/IME/AX/Windows/human proof. Details and earlier probe corrections are in
  `docs/v1-m3-material-usage-verification-2026-09-11.md`.
- Next-slice synthetic orientation reproduced MergeDialog accepting one conflict
  dropping an untouched sibling cell (`/tmp/icstex-v1-m3-merge-orientation-red-r1.log`).
  CSV import also returned 5000 of 5001 body rows without a truncation error
  (`/tmp/icstex-v1-m3-import-limit-orientation-r1.log`). These are memory-only
  reproductions, not fixes. The current label-only merge UI, missing genuine table
  baseline and positional IDs must be resolved before preview/confirmed/CAS/Undo
  repair is called functional. No merge/import application source changed here.
- Live remote development remains `e5cd13273ee6de326bc629e65c0752a9f474848e` and
  release/2.1 remains `f03776e87c0f938421a70ff5b085db920f2d01d7`. Nothing is staged;
  no commit/push/rename, packaging, installed-app replacement, credentials, CI,
  signing, website, deployment or publication. The earlier checkpoint permission
  remains one-time only. Ignored signed feed SHA-256 remains
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

## 2026-09-11 — Independent merge candidates and table import fidelity

- Repaired the reproduced same-row conflict data loss. The pure resolver preserves
  siblings, sparse cells, value types, exact manual text, row order and chosen table
  metadata without mutating Base/Remote/Local or the original comparison. Results
  do not alias mutable input rows/notes/merges. Duplicate identities/unknown columns
  are refused. Two-sided structural or order changes require an explicit whole-table
  choice, not guessed positional merging or silent row resurrection.
- The real dialog now requires a fresh complete candidate preview after choices
  change. It displays table identity and full original conflict values, retains
  Cancel zero-application behavior and bounds controls/preview output. It returns a
  detached candidate, not a project edit. The existing workspace no longer reports
  synchronization merely from confirmation, and disables its previously empty/no-op
  entry. Actual source baseline/mapping, target/source CAS and one Undo remain open.
- CSV/XLSX import rejects row/column/range overflow instead of returning partial
  tables, preserves blank rows and short-header extra cells, and retains actual
  header rows for the existing renderer. XLSX merge coordinates and range translation
  are corrected; cutting a merged region is refused. New headers are row_000;
  existing persisted tables are not migrated. Numeric header text is allowed while
  invalid body text still warns. Spreadsheet values and merge XML use the same
  bounded captured bytes; archive member/declared-expanded-size limits and explicit
  close support were added. This is not project-path or source-to-apply authorization.
- Red receipts `/tmp/icstex-v1-m3-merge-import-red-r1.log`,
  `/tmp/icstex-v1-m3-merge-import-red-r2.log` and
  `/tmp/icstex-v1-m3-import-fidelity-red-r1.log` cover the original merge/input-loss,
  truncation, missing header and wrong merge-coordinate behavior. The numeric warning
  fixture now declares a body row explicitly and separately tests allowed header/
  rejected body text. The first full run passed on app hash 35ac5133; a later red
  test found omitted preview table identity, prompting the final display correction
  and Chinese Cancel label. That red receipt is
  `/tmp/icstex-v1-m3-merge-preview-identity-red-r1.log`.
- Final app SHA-256
  `39f26a52093da449f06ddf32bf5610808b1e126616298c6a96b3abdb042c6cee`
  passed compileall, whitespace checks, 113 focused integration tests (4.720 seconds,
  exit 0) and 1242 full verbose tests (360.894 seconds, exit 0). The app hash was
  rechecked unchanged after completion. Full exec `96245` / PID `1534` are terminal;
  receipts `/tmp/icstex-v1-m3-merge-import-focused-r5.log` and
  `/tmp/icstex-v1-m3-merge-import-suite-r2.log`. No failed test or Python exception
  appeared. The earlier full exec `51161` / PID `99944` is also terminal, not a
  running blocker or a substitute for final-source verification.
- Actual offscreen product r4 used real dialog mouse/key events, selected two
  conflicts in one row, retained sibling key/False values and exact manual spaces,
  cancelled a second dialog with original models unchanged, imported a synthetic
  XLSX header/body and refused oversize CSV. Five UI scales rendered with reachable
  preview/confirmation control centers; the final 150% capture was inspected.
  JSON/detail scrolling remains technical, not full student/native/IME/AX acceptance.
  Probe r1/r2 clicked the radio widget's empty center and failed; r3/r4 click and
  verify its actual indicator. No failed choice was accepted as success.
- A separate explicit disposable LaTeX fixture from the candidate/imported table
  compiled through MainWindow FINAL into one page. It visibly contains both table
  headers, A=11/B=21, reviewed note, false/true and both imported 20/30 data rows.
  PDF text/render were inspected; original fixture source bytes stayed unchanged.
  PDF SHA-256 `7fc0a9d6e7a711b2a63e6c5101c3b080f6e740ddd565e5a2bc903ea86e2b0ad0`.
  Product exec `36337` exited 0, log `/tmp/icstex-v1-m3-merge-import-product-r4.log`,
  evidence `/tmp/icstex-v1-merge-import-20260911-r4/`. This fixture generation is not
  linked-source application. Details: `docs/v1-m3-merge-import-verification-2026-09-11.md`.
- Next work must use a genuine digest-matching source baseline, explicit stable
  mapping and existing raw-content-preserving table draft/command seams. SourceRecord
  and document authority formats are unchanged; positional IDs are not stable data
  identity. Native M2/M3 still waits for manual unlock; M3 application, M4/M5,
  IME/AX/Windows/human acceptance and M6/M7 closeout remain incomplete.
- No staging, commit/push/rename, package, installed-app replacement, credentials,
  CI, signing, website, deployment or release mutation. Live remote development
  remains `e5cd13273ee6de326bc629e65c0752a9f474848e`, release/2.1 remains
  `f03776e87c0f938421a70ff5b085db920f2d01d7`, and ignored signed feed SHA-256 remains
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

## 2026-09-11 — Explicit source repair with real baseline and all-target Undo

- Added the real Block Sources repair entry, backed by immutable project-local
  source captures, a digest-matching original version and explicitly selected
  import/column/key mappings. Actual stable keys, not importer position IDs, bind
  rows. All linked objects must be supported tables, and every table must be
  reviewed before advancing the shared source record. Whole-table replacement is
  an explicit alternative; no undocumented source baseline is invented.
- Separate candidate and final raw-content previews precede source-byte rechecks,
  exact model/draft/source ownership checks and one Undo command. The command
  preserves unchanged opaque fields, restores consumed local drafts on Undo and
  does not erase newer input. Cancel, changed inputs, unsupported formats and
  partial candidate sets do not apply. Original CSV/XLSX files are never rewritten;
  existing guarded persistence and compile authorization remain in force.
- CSV repair text retains raw whitespace/identifiers before explicit target-type
  conversion. Synthetic red tests reproduced dishonest XLSX dimensions hiding
  actual body rows and uncached formulas accepted as empty values; both now refuse
  data loss without executing formulas. A GUI fixture's unsupported root opaque
  field was moved to supported header/cell locations without relaxing the schema.
- Actual mapping screenshots exposed overlapping combo rows and unused width;
  `/tmp/icstex-v1-m3-source-mapping-geometry-red-r1.log` reproduced it. Row heights
  now fit the real controls and columns stretch. A cancellation stress test then
  reproduced overlapping retries while an old parser remained active; receipt
  `/tmp/icstex-v1-m3-source-repair-worker-red-r1.log`. One session-owned active-read
  token now refuses a second read until prior work finishes, with no pending queue.
- Final app SHA-256
  `aebdfa7b7c9183a6485d1e7934e7c0bbe9452369879dd6e47386adc9dd2fb4cd`
  passed compileall, whitespace checks, 120 focused integration tests (3.018 seconds,
  exit 0) and 1264 full verbose tests (361.082 seconds, exit 0). App hash was rechecked
  unchanged. Final full exec `53595` / PID `7114` are terminal; receipt
  `/tmp/icstex-v1-m3-source-repair-suite-r3.log`. No failed test, traceback,
  RuntimeError, RuntimeWarning or fatal Python failure appeared; offscreen/font
  warnings remain separate from native acceptance.
- First full exec `12034` / PID `5200` passed but became obsolete during the geometry
  fix. Second full exec `51781` / PID `6246` was deliberately stopped after the
  active-read fix: SIGINT landed in a Qt callback without ending the process, then
  SIGTERM ended that same verified PID with exit 143. It is not a pass or an
  unexplained application crash. No obsolete run was substituted for the final run.
- Final-source product r5 exercised actual navigation/modal widgets, keyboard column
  mappings, worker reads and final confirmation on two synthetic linked tables.
  Cancel left all project bytes/models/drafts unchanged; a source mutation at final
  confirmation was refused. Apply/Undo/Redo, restored pending draft, guarded save
  and reload matched. Explicit MainWindow Block FINAL generated one page containing
  A=12/B=21 and A=11/B=21; original source bytes remained unchanged. R1 failed only
  at the probe's nonexistent pdf_path attribute, then r2-r5 repeated the workflow
  with the actual pdf_file field; final exec `99975` exited 0.
- Product receipt `/tmp/icstex-v1-m3-source-repair-product-r5.log`, retained project,
  JSON, captures and PDF under `/tmp/icstex-v1-source-repair-20260911-r5/`. PDF SHA-256
  `488eba5ae42a5c5bba4ae1d150396d745d6eb70134788de07a47017833ae36d9`.
  Text was checked; the rendered PNG is byte-identical to the inspected r4 image.
  Details: `docs/v1-m3-source-repair-verification-2026-09-11.md`.
- No persistent baseline-byte store or project-format migration was introduced;
  source versions must be retained separately. Large JSON-preview limits, native
  IME/AX, Windows, human usability and broader M6 remain open. M4 byte-consistent
  checkpoints/restore-to-new-directory and M5 frozen delivery are the next required
  work. No staging, commit/push/rename, package, installed-app replacement, credentials,
  signing, CI, deployment or release mutation; all earlier local changes remain.

## 2026-09-11 — Byte-exact checkpoint core and legacy history boundary audit

- Implemented a bounded selected-file checkpoint core with raw saved bytes,
  relative-path/version/hash manifests and separate supplied UTF-8 drafts. Two
  content passes and final observations precede exclusive checkpoint publication.
  Restore validates all objects, writes/readbacks an explicitly incomplete staging
  tree, rechecks its bytes/inventory and atomically publishes only a NEW directory.
  Original projects and existing targets remain untouched; no draft is applied,
  project switched, compiler launched or network authority granted by these APIs.
- New core regression tests reproduced and then fixed substituted archive/directory
  handling, cleanup of foreign directories, changed earlier restore files and extra
  unlisted output. Additional cases cover corrupt/unknown/duplicate/compressed input,
  links/traversal/case collisions, limits, I/O failure, cancellation and an actual
  child process killed during restore. Hard interruption leaves an incomplete name,
  not a successful target. Native macOS no-replace rename also refused an empty
  target created immediately before publication; Linux/Windows remain unverified.
- Final app Python path/content SHA-256:
  `71ff39885c237665a25cf801947aa20dc58194b489c8ab7283a5a67e7d4ea933`.
  Required compileall and `git diff --check` passed. Focused 25 tests passed in
  0.139 seconds, exit 0, `/tmp/icstex-v1-m4-checkpoint-focused-r5.log`.
  Full verbose discovery passed 1289 tests in 366.453 seconds, exit 0; exec `1766` /
  PID `10802` terminal, `/tmp/icstex-v1-m4-checkpoint-suite-r2.log`, with app hash
  rechecked unchanged. Earlier full exec `72702` / PID `10326` was intentionally
  stopped (exit 143) before clarifying incomplete-directory README semantics; it
  is not accepted final-source evidence or an unexplained application crash.
- Final synthetic filesystem probe r3 passed, exec `59850` terminal exit 0:
  `/tmp/icstex-v1-m4-checkpoint-probe-r3.log`, retained artifacts/result JSON under
  `/tmp/icstex-v1-checkpoint-20260911-r3/`. Six-file ordinary and nine-file Block
  projects retain all raw bytes, including GBK/CRLF, Chinese paths, images and empty
  files; 2/3 drafts remain separate. Block registry/layout reopen matches, and each
  restored project produced an explicitly requested FINAL without changing selected
  originals/restored inputs. Actual PDF hashes are in the verification report.
  No GUI/native workflow, power-loss, iCloud or large-project performance is implied.
- The required legacy history audit reproduced two existing faults using synthetic
  files only: changed UTF-8 history bypasses the recorded digest, and a forged
  absolute snapshot_path in retention deletes a sentinel outside the project.
  `/tmp/icstex-v1-m4-history-boundary-orientation-r1.log` records reproduction,
  not a safety pass. Original synthetic source stayed unchanged; no real user data
  was read/modified. Existing GUI restore also reads the path directly after
  confirmation. Next bounded slice must repair source-bucket/read/delete/confirmation
  ownership before GUI checkpoint/draft recovery. New checkpoint APIs do not reuse
  that unsafe path trust; M4 as a whole is not complete.
- Details: `docs/v1-m4-checkpoint-core-verification-2026-09-11.md`. No staging,
  commit/push/rename, application packaging, installed-app replacement, credentials,
  signing, CI, deployment or release action. HEAD/upstream remain `e5cd132`; index
  empty, held feed hash unchanged, earlier shared source changes preserved. Native
  M2/M3 unlock, IME/AX/Windows/human, M4 GUI/migration and M5/M6 acceptance remain.

## 2026-09-11 — M4 owned text history and authorized source checkpoint preparation

- Repaired the synthetic audit's manifest-path deletion and unchecked-content
  faults. New source-specific buckets, strict records, bounded owned reads,
  content hashes, anchored POSIX operations and guarded retention replace absolute
  path trust. Valid old buckets remain read-only; unknown/changed objects are
  preserved. Failed history creation does not invalidate a successful source save.
- GUI recovery rechecks registered source/history and the captured editor through
  confirmation. Acceptance is one undoable unsaved change, without Save or compile
  authorization. Cancellation, corruption, switching and close preserve newer work;
  corrupt metadata is explicit in the History panel.
- Final app path/content SHA-256:
  `b2a8297c88089ac76925a8d55378b50d299694180bb7aa93641a263260392802`.
  Required compileall passed. Focused 33 tests passed in 1.101
  seconds; final full discovery passed 1312 tests in 371.893 seconds, exit 0,
  exec `74919` / PID `15672` terminal, app digest rechecked unchanged. Receipts:
  `/tmp/icstex-v1-m4-history-focused-r5.log` and
  `/tmp/icstex-v1-m4-history-suite-r2.log`. Earlier app `cf83e36b` passed 1311 tests
  before the final pre-open leaf-link guard; it is not substituted for this result.
- Final product r8 result, real confirmation and visible FINAL screenshots were
  checked in `/tmp/icstex-v1-history-restore-20260911-r8/`. Synthetic Cancel is
  byte-preserving, tamper is refused, Undo/Redo restores both drafts, and separately
  explicit Save/reopen/FINAL succeeds. One-page PDF SHA-256:
  `d1e9790b2448395adcd9f928bfa88ba33ba4208d3b2458c4971487fefa183040`.
  Product probe title/pixel-sampling/paint-timing corrections and native limits are
  recorded in `docs/v1-m4-history-safety-verification-2026-09-11.md`.
- The latest user request explicitly authorizes rename/submission of the local
  increments since `e5cd132`. The existing `codex/v1-development` branch name is
  already correct. Prepare source/tests/synthetic probes/documentation only; keep
  local screenshots, PDFs, test logs and the ignored signed appcast out of Git.
  Push verification will be recorded separately after it occurs. No package,
  installed-app replacement, version change, release-branch update or publication.
  The held feed still hashes to
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
  M4 project-checkpoint GUI and the wider M2-M6/native/platform gates remain open.
- Staging the full 74-file source/test/probe/documentation batch exposed only two
  blank-at-EOF warnings, in `app/gui/blocks/source_status.py` and
  `tests/test_gui_material_usage.py`; preserve the tested source bytes. The prior
  unstaged diff check did not cover these newly added files. Added-line scans found
  no common private-key/token/credential-URL or maintainer-home patterns. No release,
  website, workflow, binary artifact, screenshot, PDF or test log is staged; this
  limited hygiene check is not a whole-repository security audit.

## 2026-09-11 — Authorized V1 increment push verified

- The requested source checkpoint was committed as
  `c521041cb2b44740405abf4c513be5fbfca4acd3`
  (`feat: add V1 source checks and guarded recovery [skip ci]`) and pushed with the
  explicit refspec `HEAD:refs/heads/codex/v1-development`, without force or tags.
  `git ls-remote --heads origin` returned that exact development-branch hash.
  Existing `codex/v1-development` already matched the scope, so no further rename.
- All 74 prepared source/test/probe/documentation files are in this checkpoint;
  app digest remains `b2a8297c88089ac76925a8d55378b50d299694180bb7aa93641a263260392802`,
  matching the completed 1312-test run above. Worktree and index were clean after
  the source push; this receipt updates documentation only.
- Remote `release/2.1` remains
  `f03776e87c0f938421a70ff5b085db920f2d01d7`. No package, installed-app replacement,
  version/workflow/website/feed edit, signing, tag or release was performed. The
  source checkpoint's skip marker preserves the existing no-CI-request boundary;
  all outstanding native/platform/product acceptance and Beta gates remain open.

## 2026-09-11 — M4 checkpoint GUI verified and source submission authorized

- File-menu/History entry points now capture an explicitly selected file inventory
  plus actual source/Block drafts, with a GUI-owned cooperating-write lease. Review
  and restore are bound to the verified manifest and publish only a new directory;
  originals and separate drafts are preserved. A late publication/cancel race was
  reproduced and fixed so an already-generated result retains its visible location.
- Final app Python path/content SHA-256:
  `11b95515d2cb3984d152de46a2791a3c58ddfd8069e82d4b6e5b90a23464c46d`.
  Required compileall passed; final focused 38 tests passed in 1.192 seconds,
  exit 0 (`/tmp/icstex-v1-m4-checkpoint-gui-focused-r7.log`). Full discovery passed
  1325 tests in 373.316 seconds, exit 0; exec `81933` / PID `21124` terminal,
  `/tmp/icstex-v1-m4-checkpoint-gui-suite-r2.log`; the app hash remained unchanged.
  Earlier full r1 was deliberately stopped before the final UI race correction,
  exit 143, and is not final-source acceptance.
- Final actual GUI product probe r5 passed on the same source; five ordinary and
  eight Block files, including GBK/CRLF, recovered byte-exactly. One ordinary and
  two Block-workflow drafts came from real editors and remain separate; originals
  were unchanged and confirmation cancellation produced no output. Explicitly
  reopening saved recovered sources and requesting XeLaTeX produced one-page FINAL
  PDFs; both creation-review and FINAL screenshots were inspected. Results live
  under `/tmp/icstex-v1-checkpoint-gui-20260911-r5/`; PDF hashes and failed attempts
  are recorded in `docs/v1-m4-checkpoint-gui-verification-2026-09-11.md`.
- The current user request authorizes submitting this local increment. Existing
  `codex/v1-development` and the source/test/report filenames already match scope;
  no further rename is required. Prepare source, tests, synthetic probe and docs
  only; screenshots, PDFs, logs and the ignored signed appcast stay local. The Git
  push receipt will be recorded only after live remote verification.
- Native picker/IME/AX/Windows/human acceptance, reviewed recovered-draft resumption,
  interrupted Block writes, migration, M5 and M6 remain outstanding. No version,
  workflow, website, artifact, installed application or release change is authorized
  by this source checkpoint. Preserve the independent held Beta activation gates.

## 2026-09-11 — Authorized checkpoint GUI push verified

- Source commit `1b1f3715c0f4b6c89050c477ab47636c32be698b`
  (`feat: add reviewed project checkpoint GUI and draft capture [skip ci]`)
  contains the 20 prepared files. Explicit non-force push
  `HEAD:refs/heads/codex/v1-development` succeeded; live `git ls-remote` matched
  the complete local hash and the local/upstream ahead-behind counts were 0/0.
  The worktree and index were clean before this documentation-only receipt.
- The app digest still matches the completed 1325-test acceptance above. Staged
  whitespace checks passed, and a limited added-line common-secret/home-path scan
  found no matching private-key/token/credential-URL or maintainer-home patterns.
  This is not a comprehensive security audit. No raw screenshots, PDFs or logs
  were committed. GitHub API returned zero Actions runs for the source commit.
- Remote `release/2.1` remains
  `f03776e87c0f938421a70ff5b085db920f2d01d7`. The ignored candidate appcast remains
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
  Branch/file names already matched scope; no rename, force push, tag, package,
  installed-app replacement, version/workflow/website change or release occurred.

## 2026-09-11 — Recovered drafts resume/edit/save verified for authorized source submission

- Explicit recovery-copy review now rechecks all manifest-listed saved/draft bytes
  after confirmation and opens selected source or Block drafts in a new window.
  Source insertion is one undoable edit; Block models and pending properties stay
  separate, with actual live-table-cell input reopening through the existing GUI.
  Initial automatic writes remain paused until explicit Save. Existing conflict
  guards preserve external winners, originals and independent draft files.
- Frozen app Python path/content SHA-256:
  `305fb3dbb5f6f8accfb3ebda55eab249c185b90f0c1787a7a38d79eb3728efbc`.
  Required compileall and staged whitespace checks passed. Final focused 13 tests
  passed in 7.848 seconds, exit 0; integrated 92 tests passed in 10.108 seconds,
  exit 0. Final full discovery passed 1338 tests in 1220.539 seconds, exit 0;
  exec `70159` / PID `25486` are terminal, with unchanged app hash after completion.
  Receipt: `/tmp/icstex-v1-m4-recovered-drafts-suite-r1.log`; no test failure or
  Python exception was found. The slower UI-scale stage sampled in QApplication
  stylesheet work; this does not isolate a regression or prove a memory leak.
  Controlled performance/lifecycle comparison remains M6 work.
- Actual offscreen product r3 passed on this same app hash. Ordinary and Block
  workflows exercised real capture/review/confirmation, cancelled without project
  writes, resumed pending text, Undo/Redo, explicit Save and fresh-window FINAL.
  Original projects and independent draft files remained byte-identical. Review,
  Block pending input and reopened PDF-view screenshots were inspected; PDF text
  extraction independently confirmed both recovered texts. Receipts/screenshots
  remain under `/tmp/icstex-v1-recovered-drafts-20260911-r3/`; PDF hashes, initial
  theme-validation failure and r1/r2 probe viewport failures are retained in
  `docs/v1-m4-recovered-drafts-verification-2026-09-11.md`.
- The renewed user request authorizes committing and pushing this increment.
  Existing `codex/v1-development` and source/test/report names already match the
  scope, so no further rename is needed. Submission includes source, tests,
  synthetic probe and related documentation only; screenshots, PDFs, logs and
  the ignored signed candidate remain local. The live Git base is `1155acb`;
  remote push evidence will be recorded only after successful verification.
- No complete V1/M4, native picker/IME/AX/Windows/human, interrupted-write or
  migration acceptance is claimed. M5/M6 and held Beta installation-lifetime
  exclusion gates remain open. No packaging, installation, version, workflow,
  website, feed, tag, credential or release changes are included.

## 2026-09-11 — Authorized recovered-draft source push verified

- Source commit `9360f864273d50977ee84b23b9c34ba6dd5e73ac`
  (`feat: resume reviewed source and Block recovery drafts [skip ci]`) contains
  the 24 prepared source/test/probe/documentation files. Explicit non-force push
  `HEAD:refs/heads/codex/v1-development` succeeded; `git ls-remote` returned the
  complete local hash and local/upstream ahead-behind counts were 0/0. Worktree
  and index were clean before this documentation-only synchronization receipt.
- The app digest remains `305fb3dbb5f6f8accfb3ebda55eab249c185b90f0c1787a7a38d79eb3728efbc`,
  matching the completed full-suite evidence above. Staged whitespace validation
  passed; a limited added-line common-key/token/credential-URL/home-path scan had
  no matches, not a comprehensive security audit. Raw screenshots, PDFs and logs
  were not committed. GitHub API, queried with the full source SHA, reported zero
  Actions runs after push.
- Remote `release/2.1` remains
  `f03776e87c0f938421a70ff5b085db920f2d01d7`. The ignored signed appcast remains
  `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
  Branch/file names already matched scope; no rename, force push, tag, package,
  installed-app replacement, version/workflow/website edit or release occurred.
  This checkpoint does not grant standing permission to push later development.

## 2026-09-11 — Reviewed interrupted-write recovery and scoped Cocoa mitigation

- Added explicit before/after/current journal review, strict known Block candidate
  validation and new-directory publication with separate drafts and all changed-file
  alternatives. The original project and pending journal are never overwritten,
  cleaned or unlocked. Reused checkpoint staging/readback/exclusive publication;
  confirmation, source races, cancellation and late-publication identity checks
  preserve actual user choices and visible outcomes. Scope and limits:
  `docs/v1-m4-write-recovery-verification-2026-09-11.md`.
- Final app SHA-256 `bb899c986d4d5adb7fc30c3f618ad948319d7d94567c1c5317b42e57b059b75f`.
  Required compileall and diff checks passed; focused integration passed 54 tests
  in 9.501 seconds (exit 0), `/tmp/icstex-v1-m4-journal-guard-focused-r2.log`.
  Full verbose discovery passed 1358 tests in 1176.674 seconds, exit 0, receipt
  `/tmp/icstex-v1-m4-journal-guard-suite-r1.log`. Exec 36846 / PID 33491 are terminal.
  Frozen app+tests SHA-256 `bc83709bd8828fb6dbe4021206bf0a8179ebdbf5af86c56b70ee424e961664d0`
  was rechecked unchanged afterward. Full-suite scaling remains slow; synthetic
  native follow-ups overlapped the loaded suite, so this is not performance acceptance.
- Actual interrupted writer exited 73 after its first managed replacement. Final
  offscreen r2 and Cocoa r2 recovered before/after copies, separately reopened and
  explicitly compiled FINAL while preserving original files, pending evidence and
  independent drafts. Both probes exited 0. The first native run instead failed
  with SIGBUS; DiagnosticReports/Python-2026-09-11-093624.ips remains retained.
  Runtime/disassembly and Qt source trace its AX selected-children path. A temporary
  macOS 26 arm64 / Qt 6.11.1 / cocoa-only nil-returning selector guard was wired
  before MainWindow UI creation after a red wiring test. Real runtime inspection
  confirmed the method ABI and unchanged inspected children/role/title/parent
  methods. Recovery r2 returned five external AX trees and terminated normally,
  with no new Python crash report at post-run inspection. The missing selected-
  children attribute is a deliberate temporary degradation, not complete AX repair.
- Before the user requested background-only work, M3 citation r3, material r3 and
  source-repair r2 Cocoa synthetic flows passed with actual rendered/extracted PDF
  evidence on the same app source. Probe fixes wait for rendering, select the real
  narrow Block PDF view and wait for completed workspace state. Earlier blank
  capture and source-repair timeout remain non-acceptance; source-repair IMK warning
  and failed material AX observation remain recorded. Full details and PDF hashes:
  `docs/v1-m3-native-followup-verification-2026-09-11.md`.
- Legacy migration orientation reproduced original replacement, normalized backup
  bytes, nondeterministic IDs, shared-version plan skipping, unknown-format rewriting
  and output rejected by the actual loader. `tools/probe_legacy_migration_gaps.py`
  and `/tmp/icstex-v1-m4-migration-orientation-r1.log` preserve the synthetic evidence;
  this is not a migration fix. The next slice must validate a new copy and retain
  raw originals. M4 migration, M5, full M6 and external release gates remain open.
- No Git mutation: HEAD remains `3bde2b5d25803262dedef89a081ee6ffbe2b6967`, index empty;
  source/test/probe/docs increment stays local. The ignored signed feed hash was
  rechecked as `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
  No package, installed app, version, workflow, website, credentials or release change.
  Current user constraint is background-only; do not resume foreground/native QA
  without explicit permission. Continue shell, source, documentation and offscreen tests.

## 2026-09-11 — Deterministic legacy conversion and verified new-copy core

- Replaced the unused destructive migration runner with a no-write refusal and
  pure, independently repeatable known-format plans. Preserve raw originals,
  existing IDs, unknown entry fields and verbatim untrusted LaTeX; validate the
  complete current model. Recursive schema validation now matches existing nested
  LayoutNode values without accepting unknown child fields.
- Added selected local byte capture, current-format exact copying, known legacy
  conversion only in a new candidate, and checkpoint-backed exclusive publication
  outside the original. Every selected legacy original is retained as evidence;
  no original move/write, GUI switch, trust grant or implicit compile occurs.
- App SHA-256 `363673a32cbfa94e9e4007d82d9fb05d539883df46c8eae101ee8847919f52d2`;
  app+tests SHA-256 `a32315d6dee15f9d0288fd99daacd8c9d9154b12ce529e583f08f24347956430`.
  Compileall/diff check passed. Focused 80 tests passed in 6.073s, exit 0, log
  `/tmp/icstex-v1-m4-migration-core-focused-r2.log`. Final frozen full regression:
  1371 tests, 1368.580s, OK/exit 0; exec 98240 / PID 42233 terminal; log
  `/tmp/icstex-v1-m4-migration-core-suite-r1.log`. Post-run app/tests hashes match.
- `tools/probe_project_migration.py` r2 completed ordinary multi-file/current Block/
  legacy copy, real Block loader, independent draft/GBK/CRLF retention and explicit
  XeLaTeX FINAL. Each one-page PDF's expected text was checked with QPdfDocument.
  Legacy raw snippets remain blocked and are NOT represented as rendered content.
  Results/hashes: `/tmp/icstex-v1-project-migration-20260911-r2/result.json` and
  `docs/v1-m4-migration-core-verification-2026-09-11.md`. Probe r1's incorrect
  first-line marker assertion was replaced with an exact wrapped-file assertion;
  no renderer/safety relaxation. Synthetic data only; no GUI/native acceptance.
- Full run used nice 10, startup load 6.40/7.87/9.18 and memory free 30%. Live
  one-second sample remained in QApplication.setStyleSheet during the profile
  scale test; this does not prove application leakage or a migration regression.
- Core acceptance does not cover the subsequent migration GUI, original-evidence
  reader and draft-target protection increment. Those were applied only after this
  frozen full run ended and require their own tests. M4/M5/full M6 remain open.
  No commit/push/package/installation/signing/deployment/release; the local Beta
  feed still hashes to be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03.

## 2026-09-11 — Migration GUI offscreen evidence and pre-M5 export defects

- Actual File migration flow now selects files, shows original/candidate byte
  differences, verifies retained originals/decision/drafts, and separately confirms
  opening a new source or Block window. Opening grants no compile authority and
  does not apply drafts. Old drafts targeting regenerated paths are detached;
  original target and all selected legacy originals remain in evidence. Closing
  restores existing unchanged autosave requests, not permanent write suppression.
- Frozen app SHA-256 d9756e68f9336be479fe4c59ec6955ff0ac0191dad468a42575e6687d34d007f;
  app+tests 67494aa28692d7a3b4473a37b40fcf69a5500ad6ef9a4e344072abe287a3046d.
  Focused 21 tests/3.931s and expanded 131 tests/34.606s passed, exit 0; exec
  69815/86827 terminal. Required compileall and diff check passed.
- Product r4 / exec 9323 exited 0 after all three actual synthetic offscreen menu,
  cancel, copy, separate-open, reopen and visible FINAL flows. GBK/CRLF/originals
  and independent drafts retained. Legacy unknown raw LaTeX remains untrusted and
  absent from PDF. Results, PDF hashes, r1 autosave-fixture isolation and r2/r3
  viewport/diagnostic failures are recorded in the migration GUI verification report.
  No pixel/text assertion was relaxed; native GUI/pickers/IME/AX remain unverified.
- Current GUI full run was launched as nice 10, exec 2446 / PID 47068, log
  /tmp/icstex-v1-m4-migration-gui-suite-r1.log. Last check at 9:09 elapsed showed
  live CPU and continuing ui_scale tests; no terminal result/pass yet. App/tests
  hashes were rechecked unchanged. Do not restart this run on observation timeout.
- While frozen, tools/probe_submission_delivery_gaps.py reproduced five unclosed
  current export defects: actual-window stale PDF before watcher delivery,
  implicit sensitive-name/environment copying, README/manifest mismatch, prior
  delivery modification on copy failure, and mixed-version copying. Exec 50142
  exited 0 because defect assertions held, NOT because exports were repaired.
  Evidence: /tmp/icstex-v1-m5-export-gaps-20260911-r1/result.json and
  docs/v1-m5-delivery-audit-2026-09-11.md. Synthetic placeholders only, no real keys.
  Current-state/user docs now preserve these limitations; next implementation must
  repair actual export seams, not add a safe button while leaving old paths unsafe.
- Background-only user constraint honored throughout. No CUA/native launch,
  desktop focus/input, commit, push, package, install, signing, deploy or release.
  M4 full pending; M5 and full M6 incomplete; no V1 or release completion claim.

## 2026-09-11 — M4 migration full terminal and M5 frozen-delivery core progress

- The M4 migration GUI full run finished: 1384 tests in 1208.224s, OK / exit 0,
  exec 2446 / PID 47068 terminal and closed. Post-terminal app d9756e68f9336be479fe4c59ec6955ff0ac0191dad468a42575e6687d34d007f
  and app+tests 67494aa28692d7a3b4473a37b40fcf69a5500ad6ef9a4e344072abe287a3046d
  matched before applying the subsequent M5 changes. Previous running-state notes
  above remain historical; this result does not cover M5 source.
- Added an initial pure frozen-delivery model: bind saved inputs and actual FINAL
  job/PDF to M1 report/profile/count identity, capture raw selected bytes and absent
  inputs, recheck after review and before exclusive new-directory publication.
  Default PDF-only; source/report independent opt-ins; explicit acknowledgement of
  unconfirmed checks. Private names/history/drafts excluded; explicitly selected
  known Block/profile metadata and original README/manifest bytes can be retained.
  Factored checkpoint staging without changing recovery's manifest/README payloads.
- Current app SHA-256 d4f6e35fdbd71f6a1b6eadac7817058e013e50cc47bbd066b2d4e0359524764c;
  app+tests 89cc72ac67066e7dce6368e948ac1bda5b8b73777b3deb05ca3b0349595f22d3.
  Compileall/diff check passed. Focused 118 tests, 22.693s, exit 0 / exec 28469
  terminal; log /tmp/icstex-v1-m5-delivery-core-focused-r6.log. Early mode-string
  expectation corrected to the existing fallback value. A true red regression for
  an absent dependency appearing after the final report is now green; analogous
  pending-journal checks preserve unresolved evidence rather than bypassing it.
- Core product r5 / exec 62018 exited 0: actual single/multi/Block FINAL, PDF-only
  and optional source/report delivery, exported ordinary TeX recompilation,
  selected Block metadata loader reopening, checkpoint restore and restored FINAL.
  All use synthetic bytes, real XeLaTeX/TeXcount and QPdfDocument text/byte checks.
  Earlier r1/r2 candidate inventory did not include README/JSON, so their broader
  flag alone was insufficient. Submission-specific inventory and actual inclusion
  assertions now cover README/manifest/non-UTF8 bytes and unchanged checkpoint defaults.
  Evidence: /tmp/icstex-v1-m5-delivery-core-20260911-r5/result.json and
  docs/v1-m5-delivery-core-verification-2026-09-11.md.
- Integration remains open: source GUI, standalone Block and AgentWorkspace/MCP
  still use old export entrances. AgentWorkspace's existing empty-stage calling
  convention and wire/capability/locking contract must be preserved while fixing
  its guarantees. Build-time tool binary versions are explicitly unknown. No
  current full run is active; this newer M5 code still requires caller integration
  and final full validation before a completion claim. M5/full M6 are not complete.
- Background-only throughout: no Cocoa launch, focus or physical input; no
  commit/push/application packaging/install/signing/deploy/release. HEAD stays
  3bde2b5d25803262dedef89a081ee6ffbe2b6967; Beta feed remains
  be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03.

## 2026-09-11 — Foreground reauthorized; native migration follow-up

- User explicitly restored foreground window-control permission. Only synthetic
  temporary projects and isolated settings were used; no student documents or
  installed application were touched. Other Git/packaging/release gates remain.
- Added explicit --native plus cocoa opt-in and bounded observer pauses to
  tools/probe_project_migration_gui.py; default stays offscreen. Three platform
  mismatch checks refused before creating QApplication or an output directory.
  No app/ or tests/ edits in this increment. Probe SHA-256
  0426d09133ab839e180b7645e4b2dfa14bdb309c92a29b283b98be6452c14742.
- Required compileall/diff checks passed. Focused 21 tests in 10.418s, OK / exit 0,
  exec 15991 terminal, /tmp/icstex-v1-m4-migration-native-focused-r1.log. Default
  offscreen multi-file product r5 also exited 0, exec 22361 terminal.
- Native product r1 passed all three actual File/review/publication/separate-open/
  reopen/FINAL workflows, original bytes and independent drafts retained; legacy
  raw LaTeX still untrusted and absent from PDF. Exec 3227 / PID 54017 exited 0.
  Evidence: /tmp/icstex-v1-migration-native-20260911-r1/result.json and
  docs/v1-m4-migration-gui-verification-2026-09-11.md (native follow-up section).
  App d4f6e35fdbd71f6a1b6eadac7817058e013e50cc47bbd066b2d4e0359524764c and
  app+tests 89cc72ac67066e7dce6368e948ac1bda5b8b73777b3deb05ca3b0349595f22d3
  remained unchanged. Native screenshot/PDF text checks passed; narrow PDF view
  is not full-page visual acceptance or cross-environment PDF reproducibility.
- Five external AX tree reads returned under the existing selected-children
  mitigation; normal process exit and unchanged four-file Python crash inventory.
  Retained IMK mach-port and Sans-serif alias warnings; no full IME/AX, native
  picker, physical input, Windows, human, power-loss or release acceptance claim.
- No test/full run remains live. No newer-M5 full regression here; existing
  export entrance defects remain open until caller integration and validation.
  No commit/push/package/install/sign/deploy/release. Active next work stays M5.

## 2026-09-11 — M5 real GUI delivery integrated and frozen full passed

- File preparation, existing PDF export and main/standalone Block entrances now
  share an explicit project-bound review dialog. Save/FINAL remain independent
  protected actions; default PDF-only and separately selected source/report bytes
  are reviewed before new outside-directory publication. Related dirty buffers,
  revisions/options/target/content changes, failure and cancellation are guarded;
  publication winning cancellation remains reported. No fake standalone facade,
  new project format, implicit save/compile or MCP wire/capability change.
- App SHA-256 b5bce3681839b945d31aad3852554fff460e0d336a89605ee3f6fc02fd782fcd;
  app+tests 9deda6dc8270279e5fae9f44e3a5376a6bb8883afcbf0fd53e22f5049c66f7ad.
  Expanded 163 tests in 22.113s passed, exec 45657 exit 0. A genuine deleted-PDF
  late callback was separately reproduced with a failing regression; QObject-owned
  QTimer contexts repair it and the same red case now passes. Earlier failures and
  canonical-root fixture correction remain documented, without relaxed byte/lifetime
  assertions, in docs/v1-m5-delivery-gui-verification-2026-09-11.md.
- Real offscreen r2 / exec 29435 and Cocoa r1 / exec 96488 / PID 58100 ended exit 0.
  Single, multi-file, main Block and standalone Block each completed actual Save,
  new FINAL, review, default-No cancel, PDF-only and source/report publication;
  every previewed payload equals delivered bytes. Exported source recompiles
  independently, selected Block metadata reopens, restored checkpoints compile.
  Original selected bytes stay unchanged. Native result:
  /tmp/icstex-v1-m5-delivery-native-20260911-r1/result.json.
  One external AX read returned; a second timed out and is not counted as success.
  Subsequent process exit was normal and four-file Python crash inventory unchanged.
  Existing narrow selected-children mitigation warning and full IME/AX gaps remain.
- Frozen required full regression finished: 1421 tests in 718.732s, OK / exit 0,
  exec 10341 / PID 58091 terminal and handle closed. Log
  /tmp/icstex-v1-m5-delivery-gui-suite-r1.log, SHA-256
  ebf15d609c9df765f61d222c3d8fc244d549d941889a169a9465a082618b6e2c.
  Both app/tests hashes above matched after terminal collection. Required
  compileall and diff check passed again. No Traceback/RuntimeError/failure record
  found in the full log; offscreen plugin warnings remain. Native/product overlap
  and suite widget/style workload make duration unsuitable for performance claims.
- While app/tests were frozen, new tools/probe_agent_delivery_gaps.py exercised
  actual AgentWorkspace calls with synthetic projects. Exec 5817 exited 0 because
  it reproduced stale-after-FINAL PDF, late-target overwrite, synthetic private-name
  inclusion, README/manifest mismatch and mixed-version package publication.
  It also confirms the caller's existing empty-stage contract. This is not repair
  or stdio MCP transport acceptance; no real key material was read. Evidence:
  /tmp/icstex-v1-m5-agent-export-gaps-20260911-r1/result.json and the AgentWorkspace
  follow-up section of docs/v1-m5-delivery-audit-2026-09-11.md.
- No test process remains live. M5 still requires actual MCP export repairs and
  build-time tool-version evidence; full M2-M6/native/platform/human quality gates
  remain open. Read-only Git remote check confirmed both HEAD and origin's
  codex/v1-development at 3bde2b5d25803262dedef89a081ee6ffbe2b6967, release/2.1 at
  f03776e87c0f938421a70ff5b085db920f2d01d7. Later changes remain uncommitted;
  index empty. Signed candidate feed remains
  be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03.
  Foreground permission used only for isolated synthetic QA. No commit/push,
  application package/install/sign/deploy/release or student-document changes.

## 2026-09-11 - M5 Agent/MCP export integrity and actual FINAL rebuild

- Replaced Agent PDF blind copying with actual CompileResult/context/input/PDF
  evidence, exact staged bytes and exclusive publication ordered against stop.
  Portable export now preserves original README/manifest/encoding bytes, filters
  known private names and rejects incomplete/mixed captures. Existing empty-stage
  Python callers, MCP wire/grants/locks and GUI/MCP writer exclusion remain intact.
  Generated package metadata is under .icstex-package/. Known generated Block
  roots retain the XeLaTeX default; persisted theme overrides remain compatible.
- Agent-only app 4f785766 / app+tests ed851a3b passed expanded 129 tests,
  shared GUI 68 tests and full 1443 tests in 392.115s (exec 44063 / PID 64609,
  exit 0; hashes match). Actual ordinary/multi/Block exports, both stdio MCP
  routes and four offscreen GUI export/recompile/restore flows passed. Earlier
  red failures, implementation lock deadlock and Block engine/theme failures are
  retained in docs/v1-m5-agent-export-verification-2026-09-11.md.
- During that source freeze, a real warm-cache probe exported an unrelated valid
  PDF substituted with preserved mtime. Shared FINAL now adds latexmk -g without
  changing PREVIEW, output paths, clean behavior or compile safety flags. One red
  command regression and 130 focused tests pass after repair. Actual pdfLaTeX and
  XeLaTeX probes rebuild both the substituted PDF and same-size/same-mtime source;
  Agent/stdio r6 and all four Cocoa GUI delivery/recompile/restore flows pass.
  LuaLaTeX fails local restricted luaotfload initialization even without -g;
  it is not accepted and no system environment or permission policy was changed.
- Final app SHA-256
  d0a7012904829a786d3d21aa7950abfda7d4fc441afc9ac440bb9dea494f5ac6;
  app+tests 85806c1ce44006ed4178d8fc9c3f29706c7c632cdf263f6a82d8b87493283a4e.
  Cocoa exec 83942 / PID 66842 ended exit 0 with four exact-byte product results;
  published multi-source and standalone-PDF screenshots were inspected, windows
  closed. Existing narrow AX mitigation warning retained; no new physical/AX scan
  or full IME/Windows/human acceptance claim.
- Final-source full r1 exec 51729 / PID 66375 failed with exit 139 during
  test_ui_scale font scaling. Python-2026-09-11-134542.ips identifies that offscreen
  PID, EXC_BAD_ACCESS/SIGSEGV at 0x30 and QtWidgets/QApplication.setStyleSheet.
  Isolated scale tests passed 9/1.523s; unchanged-source diagnostic full r2 with
  PYTHONFAULTHANDLER=1 passed 1444 tests in 390.908s, exec 99478 / PID 67357,
  exit 0. Log /tmp/icstex-v1-m5-final-cache-suite-r2.log, SHA-256
  e3b6687155c54eca1326f98c4dd0e875e73461b20ce536727ef8639c88be569b.
  Hashes matched after terminal, compileall/diff passed, no additional crash
  report. All handles closed. Green rerun does not explain or repair the r1 crash;
  controlled stylesheet/lifecycle isolation remains the next quality task.
- Full M2-M6, build-time tool versions, platform/human and independent Beta gates
  remain open. Live read-only Git check confirms HEAD and remote development at
  3bde2b5d25803262dedef89a081ee6ffbe2b6967, release/2.1 unchanged at
  f03776e87c0f938421a70ff5b085db920f2d01d7. Index empty; later work uncommitted.
  Ignored signed feed remains be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03.
  Foreground authorization used only for isolated synthetic QA. No commit/push,
  packaging/install/signing/deployment/release or student-file modification.

## 2026-09-11 - M6 accepted window close releases Qt widgets

- The test-triage workflow separated the prior Qt stylesheet SIGSEGV from a
  reproducible lifetime defect. On app d0a70129, 24 closed empty MainWindows and
  15,275 widgets survive explicit GC; an explicit-delete control leaves none of
  those windows and 611 widgets for one survivor. Natural and forced-in-style GC
  probes do not reproduce the old SIGSEGV. It remains causally unexplained.
- MainWindow now uses WA_DeleteOnClose and unregisters accepted closes from the
  scale manager, matching its existing terminal controller shutdown. Two red
  tests fail before the fix and pass after it; Cancel keeps drafts/controllers,
  actual spawn-window registration is preserved and another window still scales.
  One fixture's duplicate deletion after event processing was replaced with an
  accepted-close/destruction assertion; no product assertion was weakened.
- Focused 13 tests pass; expanded 244 tests in 47.455s pass after two earlier
  teardown errors were fixed. Repeated fixed close and forced-GC diagnostics
  retain no closed MainWindows. Cocoa 6-close/scale and four actual source/Block/
  standalone delivery/recompile/checkpoint-restore workflows pass, exec 23874 /
  PID 70508 and exec 59032 / PID 70518 exit 0. Remaining-window and published
  Block-package screenshots inspected; all windows closed. No new Python crash
  report; AX/IME/physical focus and complete performance acceptance remain open.
- Final app SHA-256
  2f8d15e03061a54fa7780ec07d8dde7164a661123286bece4d00b13a5f63e16d;
  app+tests aa139cd92b649c2669a0a771bc2b099829e86afa3a21dd27ce4aa43b358c2552.
  Required frozen full: 1446 tests in 113.088s, OK / exit 0, exec 85117 / PID
  70795. Log /tmp/icstex-v1-m6-window-lifetime-suite-r1.log, SHA-256
  f27b899cbbce984e1280fda80e2f022eaff309abb30f9ab50b8352e22e188931.
  Post-terminal hashes match; compileall/diff pass; no new failure/traceback/crash.
  All known full/native handles are closed. Duration is not a product benchmark.
- Receipt: docs/v1-m6-window-lifetime-verification-2026-09-11.md. Next fill M5
  build-time tool identity while keeping the remaining M2-M6 matrix and original
  SIGSEGV uncertainty visible. No commit/push, packaging/install/signing/deploy,
  release or student-file edits; HEAD remains 3bde2b5 and index empty.

## 2026-09-11 - M5 actual FINAL version labels retained in delivery reports

- Added bounded, pure startup-banner parsing of fresh FINAL stdout. Immutable
  CompileResult/FinalBuildEvidence carries the initial latexmk/engine labels into
  the exact reviewed/published report bytes. No extra tool invocation, cached log
  inference, export-time environment query, new grant or MCP wire field. PREVIEW,
  input/PDF identity, source-writing and GUI lifecycle behavior are unchanged.
- Reports separate configured names from observed self-reported versions. Missing,
  unsupported and auxiliary versions remain unknown; stdout is not authenticated
  binary identity and configured paths do not identify latexmk's child binaries.
  Only allowlisted names/bounded version/distribution tokens are retained; raw
  output and absolute local paths are not exported by this addition.
- 94 focused tests passed in 8.026s, exec 78727 / exit 0. Actual synthetic
  single/pdfLaTeX, multi/BibTeX and Block/XeLaTeX delivery, independent source
  recompilation and checkpoint restore/recompilation pass, exec 76869 / exit 0.
  Original bytes and reviewed/published report bytes match. Product receipt:
  /tmp/icstex-v1-m5-tool-versions-product-r1/result.json, SHA-256
  c956a30bf39036f6b14775d33eecd9d8e8ff354c53290547c42590d84ca18a3d.
- Final app d7d57520c5a1a26044ed70457df5ecc79d839707c8475f6dddf5a954658e3219;
  app+tests 48066a6e4cbb26176dc0ce213fea8ade3dfaa91235c64d0c31fd154b6ffb38bc.
  Required frozen full: 1455 tests in 111.922s, OK / exit 0, exec 21755 / PID 73377.
  Log /tmp/icstex-v1-m5-tool-versions-suite-r1.log, SHA-256
  9d815a2f23705e92e398a6f53a812b0eb8dadba4ac06aff1500bdf9c0bc4eba6.
  Post-terminal hashes match; compileall/diff pass; no new Python crash report.
  All handles closed. No foreground window used; this is not native acceptance.
- Receipt: docs/v1-m5-tool-versions-verification-2026-09-11.md. Next inspect the
  remaining local acceptance matrix and current image-picker probe cleanup before
  native cancel/import/conflict/save/reopen/FINAL. Original stylesheet SIGSEGV,
  restricted LuaLaTeX, complete platform/IME/AX/performance/human and Beta gates
  remain open. No commit/push, packaging/install/signing/deploy/release or student
  document changes. HEAD remains 3bde2b5; prior shared changes are preserved.

## 2026-09-11 - M2 native image picker and reopened FINAL acceptance

- Completed the previously unfinished real Cocoa image-picker flow using the
  computer-use skill/NodeREPL on an isolated synthetic Python QA window. Actual
  Cancel preserves model/files/undo; successful PNG import preserves source and
  original bytes, supports one Undo/Redo, saves/readbacks the relative path and
  produces a visibly correct green image in FINAL. A third real picker refuses
  a synthetic symlink destination without changing model/undo/outside contents.
  A fresh GUI ProjectSession reopens saved data and explicitly compiles another
  correct visible FINAL. No mocked picker result or student project was used.
- Go-to-path initially selected the PNG while Open stayed disabled. Actual
  keyboard reselection enabled Open and the import succeeded. This establishes
  a working native keyboard path, not the root cause of previous automation
  trouble. The current app required no image-filter or other code change.
- Updated tools/probe_image_import.py to require --native/Cocoa, assert current
  delete-on-close, and verify actual GUI-session reopen/FINAL instead of loader
  readback alone. Restored tools/probe_submission_delivery.final's existing
  two-argument default-XeLaTeX compatibility for other GUI probes; signature
  binding and syntax pass. All earlier shared source changes are preserved.
- Native exec 79095 exited 0, all QA windows destroyed. Receipt
  /tmp/icstex-v1-m2-image-import-native-r3/report.json, SHA-256
  8b0c4a18b43b6922465ed0b66d3d79a3f82813a1c75c9b027a5370d53cb9307f.
  Both actual-image-final.png and reopened-image-final.png inspected. No new
  Python crash report; the existing narrow selected-children guard remains
  active. A NodeREPL variable error and post-cleanup App quit observation are
  automation events, not an application crash or a reason to restart the probe.
- Application SHA-256 remains
  d7d57520c5a1a26044ed70457df5ecc79d839707c8475f6dddf5a954658e3219;
  app+tests 48066a6e4cbb26176dc0ce213fea8ade3dfaa91235c64d0c31fd154b6ffb38bc.
  Required follow-up full: 1455 tests in 139.577s, OK / exit 0, exec 3225 / PID
  75313. Log /tmp/icstex-v1-m2-image-import-followup-suite-r1.log, SHA-256
  92bdeea6e5a4432026ebaaf1a021278440fba1582c3d44104ff02ff7a8190d77.
  Post-terminal hashes match; compileall/diff/probe syntax pass. All handles
  closed. No full M2-M6, native IME/AX/Windows, human or performance claim.
- Current receipt: docs/v1-m2-image-import-verification-2026-09-11.md. Next native
  formula envelope/real clipboard/keyboard/Undo acceptance, then remaining M6
  comparable measurements. Original crash uncertainties and Beta gates remain.
  No commit/push, packaging/install/signing/deploy/release or student-file edits.

## 2026-09-11 - M2 real formula clipboard flow and invalid-draft message

- Added tools/probe_formula_clipboard.py for isolated Cocoa MainWindow/FormulaDialog
  observation. The computer-use skill supplied actual clipboard paste and native
  keys/controls; the probe did not simulate paste or apply a fake edit plan.
  Verified exact comment/LF/tab/custom-macro body, malformed visual/source refusal,
  local and whole-document Undo/Redo, Cancel byte/range/scroll preservation and
  refusal of a lossy visual projection. No student document or installed app used.
- Native r1 revealed a misleading "formula valid, reselect source" message for
  an invalid draft. A focused assertion failed before the narrow classification
  repair in app/gui/formula_dialog.py; 138 focused tests pass in 2.501s afterward.
  The test-triage skill separates this product assertion from clipboard-helper
  acknowledgement timeouts and transient header capture. No parser/authority change.
- Native r2 exec 90551 / PID 77614 exited 0. Explicit Save and actual pdfLaTeX
  FINAL preserve cursor/scroll; visible PDF contains both expected expressions,
  and the workspace header reaches FINAL/current. All native windows destroyed.
  Receipt /tmp/icstex-v1-m2-formula-clipboard-native-r2/report.json, SHA-256
  aeb7048b8e5dd6b104c9706ca51f7fcef6888ffb62913312004071252371b0b2.
  Final PDF b1e6cafe7ad15a9cfd9d2b3c40c03cfd4222d34373c89523ca93fa57adc8ecdf.
- Frozen app e4e978cb79d3321462bbe52d6597195ff1a0da13f93df7273a7d75887a635baf;
  app+tests 1627c79866b811f38951d7ec5995ea43bfc548067ac88abcec7b95513e6784a3.
  Required full r1 log ended 1455 / OK in 140.216s, but handle retirement returned
  no exit code. Preserved that receipt gap and ran bounded same-source r2 with
  explicit shell status: 1455 tests / 142.032s / OK, exec 12954, tool exit 0.
  Log /tmp/icstex-v1-m2-formula-native-followup-suite-r2.log, SHA-256
  115838854933191983decfaec2d3ea48ef021d5670bd1ce129dcbabc45815d30.
  Post-terminal hashes match; compileall/diff pass; no new Python crash report.
- Current receipt: docs/v1-m2-formula-fidelity-verification-2026-09-11.md.
  All this slice's handles are closed. Next M6 comparable response/dependency/
  count measurements and separate PREVIEW/forced-FINAL timing, after probe cleanup
  alignment. Original stylesheet SIGSEGV, restricted LuaLaTeX, full IME/AX/Windows/
  human and independent Beta gates remain. No staging/commit/push, packaging,
  install/signing/deploy/release; HEAD 3bde2b5 and prior shared changes preserved.

## 2026-09-11 - M6 response measurements and component-bound path checks

- Preserved M0 response samples and added explicit PREVIEW/forced-FINAL labels,
  real visible-check input burst counts, 10/50/200-child dependency graph/hash
  and GUI callback/timer measurements, current RSS and actual Qt destruction.
  Reproduced 200-child GUI refresh at 72.218–76.238 ms with timer lateness
  62.352–66.847 ms. Profiling identified repeated ancestor construction in
  safe_project_input, not Word Count or TeX engine work.
- Replaced repeated relative_to/is_relative_to operations with component prefix
  comparison and parent-step depth. Scope resolution, every traversed link check,
  internal/generated rejection and openat protection remain. No safety cache,
  async ownership change or weakened compile-time child-save protection.
  Added two boundary/link-replacement tests; the nine core tests pass before
  optimization too. The red evidence is measured latency, not a claimed failed
  correctness assertion. The focused core/GUI/dependency/PDF/check set passes
  58 tests / 11.252s / exit 0, exec 33638.
- Final 200-child samples are 46.376–46.549 ms with timer lateness
  36.470–36.656 ms. M0-comparable visible edit max 0.343 ms, count dispatch max
  0.245 ms, count timer lateness 7.482 ms; 15 edits trigger no immediate scan/
  count/check and only one debounced count and graph refresh. Unchanged count
  code varied with host conditions; do not claim all timing changes as speedups.
  Core unchanged PREVIEW median 60.525 ms performs no rules; forced FINAL
  median 801.313 ms does real work, unlike the old warm FINAL no-op.
- Native r1 exec 6899 exited 1: first of three PDF trials passed, then no Paint
  after Ready following closure of the last window; a context-free probe timer
  also accessed a deleted viewport during cleanup. Computer-use observed native
  state and test-triage separated these failures. Probe-only keep-alive and
  QObject-bound callback changes pass r2 on unchanged app, exec 16266 / exit 0:
  three trials, 15 actual visible two-page PREVIEW/FINAL cases, every window
  destroyed. Representative screenshots inspected; not complete IME/AX evidence.
- Frozen app e1bf4fa9720c84cae9bda909da55dd890103f85ec36561f3a3512500e6e647da;
  app+tests 22fe3ad301b10219aedd3bd6d198b5341c89766c30438f08a23aa3ee4247649c.
  Required full 1457 tests / 138.295s / OK, exec 88033 / explicit exit 0. Log
  /tmp/icstex-v1-m6-response-suite-r1.log, SHA-256
  d7867df7500aafa418fe194e898530b34181a36f54e8a3396f69ffad8b889c55.
  Post-terminal hashes match; compileall/diff/probe syntax pass, no new Python
  crash report, all handles closed. Native raw report SHA-256
  8d8c84a119a54b2ad129e1f973c03f3f79d9dd8d35ec8872fef9bd92dd2e4ccc.
- Receipt docs/v1-m6-response-verification-2026-09-11.md and numerical reports
  docs/data/v1/m6-*.json; native paths removed from the repository-side copy.
  Next requirement-by-requirement local acceptance reconciliation and any actual
  gaps, then M7 readiness handoff. Old stylesheet SIGSEGV, restricted LuaLaTeX,
  full platform/IME/AX/human and Beta gates remain. No commit/push/package/install/
  signing/deploy/release; candidate feed unchanged and index empty.

## 2026-09-11 - M6 formula input methods and composition boundaries

- A12 audit found that the custom visual formula widget rejected actual
  QInputMethodEvent commits. Added input-method queries, slot-scoped UTF-16
  replacement, separate attributed preedit painting, candidate/Apply guards and
  protected navigation. Formula source mode now has the same premature-Apply/
  mode-switch guard. Source formats, compiler and file writers are unchanged.
- Added ordinary source, formula source/visual, Inspector and actual table-cell
  delegate composition tests. Initial red visual commit rejection was a product
  defect; QPlainTextEdit textChanged during preedit was a test assumption, and
  an end-of-slot selection setup was corrected without relaxing expected text.
  The 109-test focused scope passed / 2.337s / exit 0, exec 97037. A further red
  proved two partial commits after selection merged too broadly into one undo;
  the boundary fix passes 63 formula/widget tests / 1.055s / exit 0, exec 96822.
- test-triage separated product assertions, setup assumptions and the full
  suite's timing failure. First full: 1470 / 142.519s / error, exec 47785 / exit 1;
  test_timeout_kills_entire_process_tree reached TIMEOUT but grandchild.pid was
  missing. Isolated rerun passed / 1.012s / exec 94941 / exit 0. No compiler or
  fixture assertion was changed to conceal it; the intermittent cause remains
  unproven. Failed full log /tmp/icstex-v1-ime-suite-r1.log, SHA-256
  8fb826928400e5389d0e1a8659fd4784ae08382ca3885f1db447cb32a10dff24.
- Actual Cocoa desktop key presses used the existing Pinyin input source.
  Visual and source runs each observed 12 native IME events, committed Chinese,
  Undo/Redo, Escape cancellation of a second preedit, and explicit Apply of
  $x+中文$. Original document strings remained unchanged and windows were
  destroyed. Source exec 68664 and visual exec 94644 exited 0 on app b6da0987;
  earlier visual exec 38643 also exited 0 on app 4bddf8b5. No student files,
  paste simulation or generated QInputMethodEvent was used as native evidence.
  Restored the prior English input source. The later partial-commit history
  increment remains event-level verified, not relabelled native acceptance.
- Final frozen app d8175978f5d47186440a6ccd8abb9b785e4b128b301ea2c79cbecf8c6965550b;
  app+tests 0e85d64636b7c8fb436b24c4cd02b17de58e2ba64c1d05179cae0923141cc324.
  Full 1471 / 138.051s / OK, exec 39883 / explicit shell and tool exit 0.
  Log /tmp/icstex-v1-ime-suite-r2.log, SHA-256
  e38e894ad123f4bab5316ca6e253f7a224fd2fdfb47793cb32f3e745bdd96971.
  Post-terminal hashes match, compileall/diff pass, and no new Python crash
  report was found. All native/test handles are terminal. IMK/font warnings,
  scoped AX mitigation and older unexplained crashes are retained.
- Receipt docs/v1-m6-ime-verification-2026-09-11.md, path-free native JSON under
  docs/data/v1/ime-native-*.json and user-guide entry added. The active plan's
  old completed-slice narratives were replaced with the current bounded brief;
  historical receipts remain in their files and this append-only log. Next:
  final-source native partial-commit/focus work and the full M1–M6/A01–A14 audit.
  No automatic Git, packaging, install, signing, deployment or release action.

## 2026-09-11 - Workbench IME evidence guards and finite acceptance inventory

- Continued the live ordinary workbench probe, exec 41820 / PID 92341, rather
  than restarting it. CUA reported the Mac locked; no keyboard/pointer or input
  source switch occurred. The probe reached its own 600s deadline, destroyed its
  isolated window and exited 1 with zero input/save/apply events and unchanged
  synthetic bytes. This is incomplete environment-blocked evidence, not an IME
  product failure or pass. Raw report /tmp/icstex-v1-ime-workbench-ordinary-r1/report.json,
  SHA-256 2502905e8d781ef79c83e7c62683fa11eb528aa08f478b4975ea07e88971d037.
- Probe counterexamples demonstrated 9 false-positive cases in 11 tests, exec
  74482 / exit 1. Required ordered commit/Undo/Redo, separate candidate/cancel,
  observed preedit/source/model/disk boundaries, explicit Block Apply and Save,
  no unexpected Block compiler, exact final bytes and destruction. Observer now
  reads the current registry, counts the table Apply control and records events
  with QObject-bound post-event snapshots. No app/ code changed. Corrected probe
  SHA-256 071a620ed094adb0c99d2ee18ad0fcdd1bd0bc166b7f91e881ba2348ef836fba.
- test-triage separated the locked environment and probe assertions from product
  regressions. Small scope 11 / 0.001s / exit 0, exec 83495; expanded composition
  scope 121 / 5.171s / exit 0, exec 86686. Full 1482 / 257.308s / OK / explicit
  exit 0, exec 20957. Log /tmp/icstex-v1-workbench-evidence-suite-r1.log,
  SHA-256 3290618b83fcc11ba8ea65d27c5e03be65d1bf760634d7753ee51fa70cf729b7.
  App d8175978f5d47186440a6ccd8abb9b785e4b128b301ea2c79cbecf8c6965550b;
  app+tests 2e01d70c6a5623c75be57997bef61dbb671729111ae61cd90f9b42d39d771584.
  Post-terminal hashes match; compileall/probe syntax/diff pass; unchanged five
  Python crash reports. All this follow-up's handles are closed. New observer
  runtime is not yet native-accepted, and prior compiler timing/crash risks remain.
- Added docs/V1_ACCEPTANCE_MATRIX.md mapping the original M0–M7/A01–A15 scope to
  implementation/tests/receipts, with finite R1–R6 local and E1–E4 external work.
  Updated active plan/index/current state and IME receipt. This is not an all-pass
  certificate. While locked, next safe work is background process-tree fixture,
  Qt crash or restricted-engine triage; after unlock resume actual workbench and
  final-source formula input/focus. No Git mutation, package, installed-app change,
  signing, deployment, release, student-data access or system settings change.

## 2026-09-11 - Unlocked workbench Pinyin and source Save shortcut

- After the user explicitly reported unlocking, actual Cocoa source/Inspector/
  table key input produced 12 IME events per completed sequence: Pinyin Chinese
  commit, Command+Z / Command+Shift+Z, a second ni candidate and Escape cancel.
  Original model/disk stayed unchanged before Block Apply; exact saved Chinese
  and the second untouched table were verified. English input restored and all
  windows destroyed. Ordinary r2 exec 6177, table r1 88803 and Inspector r2 72390
  exited 0 on app d8175978. Inspector r1 31688 exited 1 because the probe watched
  source Save instead of Block Save; retained, not relabelled. Corrected observer
  SHA-256 b507789cc49bc6b017c0547a04ab9dba329c5116ff009b3cb5579ada9e7da279.
- Ordinary r2 exposed missing Command+S while toolbar Save worked. The source
  QAction had no shortcut. One application-code assignment now sets StandardKey.Save
  and retains existing mode/guard/ownership behavior. Actual-key regression failed
  first (exec 85991 / exit 1), then passed; expanded 38 tests / 14.349s / exit 0,
  exec 63983. A second test verifies only the visible source/Block Save action runs.
  Final ordinary r3 exec 54390 exited 0 using Command+S only: exact saved text,
  unchanged cursor/scroll and destroyed window. Raw report SHA-256
  f5c4537f579c663a68cad1c12a9ab2236df1d5f9e8b78b202ac9772d1e92e6af.
- Frozen app 40842d9379ff458173f175b07198d32a207296922214dd6d72880464584b6946;
  app+tests 9a056619d84f3d3ad02a33946df18c3f567eb1c45597ba4475c585fb0b356a8b.
  Full 1484 / 251.103s / OK, exec 53862 / explicit shell and tool exit 0. Log
  /tmp/icstex-v1-save-shortcut-suite-r1.log, SHA-256
  ae8d98f630207b60da7c83ea09178bce0572349a6a1b4d899491aa6d71852ff3.
  Post-terminal digests match, compileall/diff pass, unchanged five Python crash
  reports and candidate feed. Every handle is closed; no new installed build.
- Retained a separate native focus failure: Inspector Control+Tab emits
  ShortcutOverride Tab/Qt Meta, but no matching KeyPress reaches the editor and
  focus does not move. Mouse Apply is not keyboard acceptance. Next bounded work
  reproduces that event boundary; final-source formula partial/focus, default
  idle-save composition, other matrix and independent release gaps remain.
  Receipt docs/v1-m6-workbench-input-verification-2026-09-11.md; plan/state/matrix/
  index and source-only guide updated. No Git mutation, package/install/signing/
  deployment/release, student files or system settings change.

## 2026-09-11 - Inspector shortcut routing and ready process-tree fixture

- Continued from the verified 40842d93 source without restarting M0 or replacing
  shared edits. Inspector's event filter accepted ShortcutOverride but moved
  focus only on KeyPress, absent in the prior physical Cocoa receipt. New
  content-widget QShortcuts route forward/backward at shortcut dispatch, retain
  scroll-to-target and never Apply/Save/compile. The boundary test failed in
  both directions first, then passed; MainWindow 100%/150%, Tab/Undo/Redo, exact
  draft/model/files, Alias and hidden-mode scope checks pass. Old GUI test now
  waits for activation and uses QWindow dispatch with its original assertions.
- New native attempt exec 63025 / PID 99831 was blocked by a locked Mac before
  input. SIGINT ran synthetic fixture cleanup and terminated at exit 130; no
  completed JSON or native pass. Observer now records exact focus_role, but its
  IME predicate alone is not focus proof. No input-source or system-setting change.
  One integration run was stopped at exit 143 after a live sample proved fixture
  cleanup waiting in QMessageBox; only synthetic dirty/timer cleanup was fixed.
- R4 test startup delay 1.2s reproduced missing grandchild.pid with TIMEOUT already
  reported. Test-only readiness now observes the real child's own PID, live state
  and inherited group before the unchanged real timeout. Death must be observed
  before cleanup. A three-second test-only post-kill drain bound rejects broken
  driver-only termination rather than waiting for natural child exit. Negative
  control checks INTERNAL_ERROR/TimeoutExpired rejection. Production compiler
  code/policy unchanged; historical host scheduling cause remains unproven.
- Final focused 124 / 15.503s / OK, exec 55326 exit 0. Current app SHA-256
  43816cb0a8f221e5b1ffbf18f1cfe96bf98529ef7351be7d818cb752618d8b6d;
  app+tests 4d775d7adbd81fa40e0314282336c3f5eb8871896d57aee46a770c871e145d54.
  Frozen full 1488 / 123.977s / OK, exec 16530 explicit shell/tool exit 0. Log
  /tmp/icstex-v1-focus-readiness-suite-r1.log SHA-256
  bf124e4c6d0871e43ba72763ba533438dfa99e3bf6957f93184da9f6c90b5d63.
  Post-terminal source identities match, compileall/probe syntax/diff pass; five
  unchanged Python crash reports and unchanged held candidate feed. Index empty,
  HEAD remains 3bde2b5; all new process/test handles are terminal.
- Receipt docs/v1-m6-focus-readiness-verification-2026-09-11.md, current state,
  matrix, plan and index updated. R4 local fixture work addressed, R2 physical
  post-fix focus pending unlock. Next safe background work is R5 restricted
  LuaLaTeX diagnosis without changing security/system dependencies. R1/R3/R6 and
  all independent platform/human/release gaps remain. No commit/push, packaging,
  installed-app replacement, signing, deployment, release or student-data access.

## 2026-09-11 - Restricted LuaLaTeX diagnosis and fatal error visibility

- Continued from app 43816cb0 without restarting M0 or replacing shared work.
  Existing TeX Live 2025/LuaHBTeX 1.21.0/luaotfload 3.29 resolves an installed
  ScriptExtensions.txt but paranoid Lua io.open denies its absolute path;
  luaotfload-multiscript.lua then dereferences nil f at line 70. An identical
  synthetic project-local copy is readable; a parent synthetic sentinel remains
  denied; shell_escape is 0. Restricted pdfLaTeX/XeLaTeX FINAL pass, LuaLaTeX
  remains latex_error/exit 12/no PDF. No unrestricted compile, dependency repair
  or security-policy change. The copy is a diagnostic fixture, not a workaround.
- Fixed an actual product gap: fatal luaotfload logs previously yielded no parsed
  errors. Bounded fatal/detail recognition now joins quoted log wraps and does
  not misassign Lua line numbers to student source. Chinese diagnostics preserve
  raw cause, have no automatic fix/location and retain failed/non-current PDF
  state. Core red/green plus MainWindow/source/cursor/scroll assertions pass.
  Corrected only the compiler's overly broad distribution-read comment; ordinary
  GUI defaults and explicitly restricted MCP policy remain unchanged.
- Final-source synthetic actual compile/offscreen MainWindow r5, exec 92330,
  exit 0: settled workspace/PDF failure, complete visible Chinese diagnostic,
  disabled fix, unchanged source/cursor/scroll/engine/policy and cleanup verified.
  This is diagnostic success, not engine or native acceptance. Report
  /tmp/icstex-v1-lualatex-restricted-r5/report.json SHA-256
  20a9f3c31bff13fbfe57ddca65c679010295e7ed78f8ce1d4a7811979c84ecb0.
  Earlier doctor absolute-entry failure, INITEX fixture failure, truncated GUI
  receipt and incorrect export-menu test assumption remain explicitly classified.
- Focused 91 / 15.561s / OK, exec 91383 exit 0. Final app SHA-256
  bc2a7b3e00f62f2e0114d1cba4804a60844756c27ab6a6bfcf97a32e43e43f74;
  app+tests e6279c2075db371aec0115eeeed20a483064bc09aff9a1168a5e959d1fcddb67.
  Frozen full 1495 / 121.819s / OK, exec 74763 explicit shell/tool exit 0;
  /tmp/icstex-v1-lua-diagnostic-suite-r2.log SHA-256
  3fe2103c6564fd236daebeb758c2114c49cb279dfe431c4831c7611f97e6d045.
  First full also passed 1495 / 121.879s, but the comment changed during it;
  only r2 is the frozen final receipt. Post-terminal identities match,
  compileall/probe syntax/diff pass, five unchanged Python crash names/count,
  candidate unchanged, index empty and HEAD 3bde2b5 unchanged. All handles closed.
- Receipt docs/v1-m6-lualatex-verification-2026-09-11.md, plan/state/matrix/index
  updated. R5 diagnosis/visibility addressed; compatibility still needs a bounded
  security/platform decision. Next background slice R3; R1/R2/R6 and E1–E4 remain.
  No foreground operation in this slice, Git mutation, packaging/installation,
  signing/deployment/release or student-file access.

## 2026-09-11 - Synchronous style traversal keeps cyclic widgets alive

- Read original timer and stylesheet crash reports, preserving separate causes.
  Old timer PID 77194 had 115 threads; stylesheet PID 66375 had 343, consistent
  with independently observed old window retention but not proof of causation.
  Matching Qt 6.11.1 source/binary shows raw-pointer stylesheet traversal across
  callbacks. Controlled cyclic QLabel collection reproduced a baseline native
  crash during setStyleSheet, exec 67228 / PID 6992 / exit 139. New retained
  report Python-2026-09-11-175448.ips is the intentional red; old/new internal
  instruction offsets differ and the exact historical victim is not identified.
- A probe-held wrapper control passed. UiScaleManager now holds only a local
  allWidgets snapshot through synchronous font/metrics/style notification and
  releases it afterward. No global GC/ownership change or persistent cache.
  A safe font/style boundary test failed on baseline and passes after the fix;
  a real Qt StyleChange subprocess verifies all owned cycles survive dispatch,
  then are destroyed at final GC. Setup missing-manager and transient-widget-
  total assumptions were corrected without weakening owned-object assertions.
- Focused 55 / 4.910s / OK, exec 10064 exit 0. Final-source natural offscreen
  24-window run, forced 24-window/12-collection run and Cocoa six-window/eight-
  collection run pass without probe-only keepalive. Native exec 9692 / PID 7614
  exit 0; final welcome/workspace rendering inspected and windows closed.
  No physical input/AX scan; scoped AX mitigation warning remains. Native report
  /tmp/icstex-v1-style-pin-native-r1/result.json SHA-256
  4748774cd774fcccf83bcbd505b7a6c5fdf688759f2ce466818e35d490c147c6.
- Probe-only portability makes resource optional, RSS null when unavailable,
  lifecycle assertions unchanged. Four lifetime tests pass again. An invalid
  first simulation restored sys.modules after loading Qt and removed the newly
  imported binding modules: startup failed in Shiboken setStyle conversion,
  before the style probe. Its report Python-2026-09-11-180815.ips / PID 8869 is
  preserved. A module-inventory control confirms that removal; normal-entry
  no-resource simulation passes, exec 13447 exit 0, all four cycles released.
  This does not claim Windows-native acceptance or require an application patch.
- Final app SHA-256 f71ec949f96011e0c510bd1d953d2b5e56e53d0597e6106ca577a77d236f6ab4;
  app+tests e5d34abda609ffb76b6ab398e0c1acfc760d46279aacb8cf32e5d4fa8d36cb49.
  Frozen full with final portable probe: 1497 / 125.290s / OK, exec 19099 / PID
  9023 explicit shell/tool exit 0; /tmp/icstex-v1-style-pin-suite-r2.log SHA-256
  7774a0b994ac01273a48430678ea11a2758ec604b38f2a3335a0ed6c2e054d21.
  Earlier full also passed 1497 / 124.943s, before the portability adjustment.
  Post-terminal digests match; compileall/probe syntax/diff pass. Crash inventory
  now seven: five prior plus red and malformed harness; no other new report.
  All handles terminal, index empty, HEAD 3bde2b5 and held candidate unchanged.
- Receipt docs/v1-m6-style-gc-verification-2026-09-11.md and current state/plan/
  matrix/index updated. R3 reproduced style/GC mechanism addressed, old timer
  and historical-object uncertainty retained. Next bounded work R1 ordinary
  default idle-save/partial composition; R2/R5/R6 and E1–E4 remain. No commit,
  push, package, installed-app replacement, dependency/security change or release.

## 2026-09-11 - Ordinary-source preedit and default idle-save separation

- User reported unlock, but Computer Use still returned locked. No new native
  window/input or input-source change was started; continued the planned R1
  background slice. Physical Inspector focus remains unverified, not failed.
- Four baseline application failures: preedit/cancel wrote unchanged bytes,
  restarted a committed-save timer, repeated a partial-save write on cancellation,
  and failed to preserve an active candidate against an external reload after
  partial save. Red r2 4 / 5.723s / failures, exec 56453 exit 1. Initial red r1
  additionally had a missing eager compile-manager fixture, corrected explicitly.
- LaTeXEditor now exposes actual source-change notifications across the native
  IME boundary; normal Qt signals/Undo remain intact. MainWindow uses this signal
  instead of treating candidate layout updates as source edits. External reload
  uses existing conflict protection when native preedit exists. No change to
  atomic writes, encoding, root/save/compile authority or the default 800 ms timer.
  Selection removal at composition start remains a real native edit with Undo.
- Five actual-MainWindow/default-timer tests and three source-notification tests
  cover disk/candidate/view/Undo/UTF-16/ownership/conflict cases. An initial empty-
  Undo assumption was corrected against observed pre-existing formatting state.
  Expanded timing failure was reproduced with timer active, remaining 0, dirty
  true and no conflict: qWait had returned before delivery. Tests now observe the
  actual timeout and matching disk state, without manual flush or debounce change.
- Final focused 280 / 47.244s / OK, exec 51524 exit 0. App SHA-256
  75c177e002c371a26a469a37741ec19a9bf30069fb9f6d26da9838dfeb5fd42b;
  app+tests fd872bfdd810a28b57874dd6604576920abcc1b2a71d3210688bc19117e19a2c.
  Frozen full 1505 / 131.638s / OK, exec 95354 explicit shell/tool exit 0;
  /tmp/icstex-v1-idle-composition-suite-r1.log SHA-256
  53feb2fa4dcdc68db7f8f6abd61bdacc92e4658c968ae19e4f1cf6df695d5d12.
  Post-terminal source hashes match, compileall/diff pass; seven crash reports
  unchanged, all handles terminal. HEAD 3bde2b5, empty index and candidate unchanged.
- Receipt docs/v1-m6-idle-composition-verification-2026-09-11.md; state/plan/matrix/
  index updated. Next bounded background action R2 high-scale citation review.
  R1 physical/focus, R2 native focus, R3 historical timer/AX, R5 restricted engine,
  R6 reconciliation and external human/platform/release gates remain open.
  No commit/push, packaging, installed-app replacement, release or student changes.

## 2026-09-11 - Citation high-scale visibility and keyboard tool-rail scrolling

- Baseline real MainWindow/offscreen citation observation found outer horizontal
  overflow, clipped locate action, elided values without tooltips and same-row
  report replacement leaving detail blank. Timestamp QLabel minimum width caused
  the dock expansion; targeted red r2 had 13 failed assertions. Source before
  this slice: app 75c177e002c371a26a469a37741ec19a9bf30069fb9f6d26da9838dfeb5fd42b.
- ReferencesPanel now uses wrapping button rows, short status with complete
  timestamp/root in copyable detail/tooltip, font-sized table rows/status column,
  complete cell/location tooltips and explicit selection reset during report
  replacement. No check/worker/write authority change. The user guide matches
  the shorter “检查引用” action and retains its read-only boundary.
- Screenshot review rejected an intermediate width-ignore workaround that clipped
  the timestamp. It also disproved viewport-only visibility: the fixed tool rail
  forced the dock below the window; 31 of a 67-pixel locate button were visible.
  The navigation rail now scrolls vertically and reveals Up/Down keyboard focus
  across all nine unchanged tool entries. Final checks include true visibleRegion,
  full bounds/text-size hints and source-navigation/no-write invariants.
- Final-source five-scale/two-size offscreen probe exec 74593 exit 0, actual small
  window 1080×720. All ten layouts have no outer horizontal overflow and fully
  visible actions. Real child navigation reaches line 2; original files and
  compile authorization unchanged. Screenshots inspected, source hashes match.
  /tmp/icstex-v1-citation-layout-final-r1/report.json SHA-256
  ec55025698ed8a975b5dfc2560f52c2cc7f0baa78b771601d8c3aa71a3bd6c15.
- Focused 227 / 40.502s / OK, exec 40534 exit 0. Final app SHA-256
  d25a13526e611621a2a13b8823ed7deaf2b0b39678a192c9dd1c9a612372ee6f;
  app+tests ffc66e895c4161595561327f69f0b3c3203bc08f5e955ad7de04d8dd62550251.
  Frozen full 1508 / 139.135s / OK, exec 93978 explicit shell/tool exit 0;
  /tmp/icstex-v1-citation-layout-suite-r1.log SHA-256
  459131c5f24f5c9ef9259798f29a65b4b998e5b58316147a8a5a3633fc61ee5d.
  Post-terminal identities match; compileall/probe syntax/diff pass. Seven old
  crash reports unchanged; all handles terminal, HEAD/index/candidate unchanged.
- New unfixed R1 finding: citation periodic reconcile still uses Qt revision;
  preedit alone advances it 2→3 and invalidates a retained report without byte
  changes. Final-source diagnostic log /tmp/icstex-v1-citation-preedit-reconcile-r1.log
  SHA-256 fa414b198198f275f71ce8ea57aacd2b5c67b293d2f158bf8bb4e7202c567070.
  Previous immediate-notification receipt is qualified, not silently treated as
  full identity coverage. This source identity path is the next bounded action.
- Receipt docs/v1-m6-citation-layout-verification-2026-09-11.md; current plan/state/
  matrix/index and prior receipt boundary updated. Native focus/layout/IME, R3
  historical timer/AX, R5 restricted engine, R6 and E1–E4 remain. No foreground,
  commit/push, package, installation, signing, deployment, release or student changes.

## 2026-09-11 — M6 read-only source identity during IME composition

- Verified authoritative root, branch codex/v1-development and unchanged HEAD
  3bde2b5d25803262dedef89a081ee6ffbe2b6967. Preserved the shared dirty worktree,
  empty index and independent Beta gates. No native control/window was attempted.
- Added four failing baseline regressions for preedit-only citation/material/
  submission report invalidation and Word Count key changes. Baseline app
  d25a13526e611621a2a13b8823ed7deaf2b0b39678a192c9dd1c9a612372ee6f;
  /tmp/icstex-v1-source-identity-red-r1.log, 4 failures / 0.604s, SHA-256
  42813473eaa7fab690c7b60fd9e5e02a7de0421dfdea1c871179c0f3d124c59c.
- LaTeXEditor now supplies a monotonic source revision using document content
  events outside IME, and one increment before source notification for actual
  input-method text changes. Candidate updates/cancel alone keep identity.
  Citation/material/submission/Word Count/project-panel readers use it; no
  periodic full-text comparison. Blocked reload, Undo/Redo and inactive related
  editors still change identity. Existing byte/dependency/root/build guards and
  stricter raw Qt history/checkpoint transaction guards remain unchanged.
- Smallest post-fix 9 / 0.715s / OK, exec 93886 exit 0. Expanded development
  retained a missing test-call argument and a false child-membership fixture
  assumption as failures; corrected the fixture's real include relationship,
  not the product's root-ownership rule. Actual late callback, edit→Undo,
  cached snapshot/no-worker/no-text-read and default-save regression passes.
- Final focused 285 / 38.527s / OK, exec 25148 exit 0. App SHA-256
  c7e9859961795c2ec082583e9a7aad2fc2e0d60e859e614d784e4a5a4e09676f;
  app+tests c317ad7e93f462154fff59bbc67185e33279ea3ec6f0f89a9e9ba097e186e4bf.
  Frozen full 1518 / 140.039s / OK, exec 4947 explicit shell/tool exit 0;
  /tmp/icstex-v1-source-identity-suite-r1.log SHA-256
  0bfca036f7d2217fbd5931043d17e2f6e73126c238fe0d23a186b9894f40783d.
  Post-terminal digests match, compileall/diff pass; seven existing Python crash
  reports unchanged. All handles terminal, HEAD/index/candidate unchanged.
- Receipt docs/v1-m6-source-identity-verification-2026-09-11.md; current state,
  plan, matrix and index updated, earlier receipts linked without relabelling
  their source/native evidence. R1 read-only identity defect is locally repaired;
  current-source physical R1/R2, R3 historical timer/AX, R5 restricted engine,
  R6 and E1–E4 remain. No commit/push, packaging, installation, signing,
  deployment, release, student-content change or native acceptance claim.

## 2026-09-11 — M6 deferred file selection and renewed native timer failure

- Verified authoritative root and unchanged codex/v1-development HEAD 3bde2b5;
  shared changes/index/Beta gates preserved. Initial computer-use state request
  returned locked; no native probe/input or repeated lock polling. Background
  triage proceeded under the test-triage skill using synthetic data only.
- Baseline's context-free post-rename callback raised deleted-QFileSystemModel
  RuntimeError after actual window destruction and selected the old project's
  path after a root switch. Two red cases: exit 1, one error/one assertion.
  Window-context singleShot plus captured-root check repairs both without
  changing filesystem/reference/compile/save guards. Positive actual-window
  rename retains selected path, recent files, source bytes and editor viewport.
  Focused 17 / 2.365s / OK, exec 9161 exit 0.
- Expanded GUI regression exec 38360 / PID 19769 ended at SIGBUS / exit 138
  during textcolor completion's processEvents. Preserved new report
  Python-2026-09-11-191921.ips, incident F3FA2242-649E-4281-97A9-6BA012D89A95,
  SHA-256 87584f007eea91006477b8078479346cf012b16894e1e14f2999ff9e57e689d2.
  The QtCore UUID and activateTimers +1268 area match old reports; the receiver
  and cause remain unproved. This is not explained by the callback RuntimeError.
- Unchanged-source isolated completion passes, no-rename control 138 / 17.406s
  passes, 20 short rename/destroy/scope-switch/completion cycles 80 / 6.256s
  pass. These do not prove absence or causality. LLDB attach was system-denied
  before tests; no security-setting change, binary modification or bypass.
- Final app da75a16945bbae46550b8fce5c207bba7077b6f82d1e72f322c5085e77664477;
  app+tests a7eb74546e03b2345ebc8920de93253457eab314e58c1f87d5c231f227e640e6.
  Required frozen full 1520 / 141.008s / OK, exec 36520 explicit shell/tool exit 0;
  /tmp/icstex-v1-file-selection-suite-r1.log SHA-256
  67a2564b80dcfdb2144e5640bdc6810e804916274dc00a5bf7acb6bfef176507.
  Post-terminal digests match, compileall/diff pass. Eight crash reports remain;
  all handles terminal, HEAD/index/held feed unchanged. The passing full does
  not erase the failed expanded run or certify M6 stability.
- Receipt docs/v1-m6-deferred-selection-verification-2026-09-11.md; state/plan/
  matrix/index updated. Next background action is bounded current-source timer
  and test-order isolation. Native R1/R2, R5 decision, R6 and E1–E4 remain.
  No Git mutation, packaging, installation, signing, deployment, release or
  student-content change. Suggested commit only: fix(gui): bind deferred file
  selection to its window and project.

## 2026-09-11 — M6 editor/gutter ownership cycle and timer-prefix controls

- Continued the existing local M6 assignment, preserving shared changes and
  codex/v1-development HEAD 3bde2b5. Test-triage guided prefix/GC controls. One
  native inventory request reported locked; no foreground QA window/input,
  student-content change, Git mutation or release action.
- Baseline app da75a169: 131-test prefix through textcolor completion again
  crashed in native timer dispatch (exec 38729 exit 139). Natural GC was observed
  in watchdog polling threads. A signal-observed prefix passed 131 / 17.957s
  (exec 26260 exit 0); it did not identify the failing native object.
  New report Python-2026-09-11-193542.ips, incident
  96EF44C5-6436-4AAD-A66A-559BE6378462, hash
  8117e1041d2d36c622f574b8dde8d87efd8d0d7699238deaa5a6b1cc2fdce332.
- Isolated editor/gutter ownership cycle survives dropping its external owner.
  Worker GC with pending highlighter work reproduced SIGSEGV/exit 139; settled
  events and weak-gutter-only controls exited 0. The small red report
  Python-2026-09-11-193919.ips, incident 01B50D9A-EFE1-45C4-81BF-86F0E76F98F3,
  hash 87f333b27989de376de65e3af07944d44a3839d88e90266f0da24aa4ba48606a,
  has mainThreadDeletionHandler, not the original timer stack. Python wrapper
  finalization on a worker does not itself prove native deletion on that worker.
- LineNumberArea now uses a weak proxy back to its editor. Qt parent ownership,
  gutter painting/width, text and input/save/compile behavior remain unchanged.
  Two baseline lifetime assertions fail, then pass; focused 9 / 1.983s / OK,
  exec 8322 exit 0. Twenty fixed-source pending-event/worker-GC cycles pass.
  The exact original expanded command passes 252 / 59.446s, exec 38659 exit 0.
- Final app e65bac97cb0be2f1a68be509f502a17fea628b3c4d315292dc811b5a7a8e546f;
  app+tests 5d3f32cfe17840a80f9167a7e35d6d50da2cf99a9e9be2b3b5a854ca3be8ad2b.
  Required frozen full 1522 / 143.802s / OK, exec 9432 explicit exit 0;
  /tmp/icstex-v1-gutter-lifetime-suite-r1.log SHA-256
  9c62a8df7e2bbded731c4daa44db670be67e77035b180857230b0437444ccfae.
  Post-terminal source hashes match; compileall/diff checks pass.
- Paired disposable-process prefix controls (exec 88596) both exit 0: fixed
  131 / 16.565s, restored strong gutter 131 / 15.903s. Five worker wrapper
  finalizations occur in both; no signal reproduced. Do not present this as
  original-crash causality. Next check separates already-deleted QObject wrapper
  recycling from pending native deletion in the identified closed-window fixtures.
  No global GC suppression, blanket test cleanup, Qt patch or debugger bypass.
- Receipt docs/v1-m6-gutter-lifetime-verification-2026-09-11.md; current state,
  plan, matrix and index updated. Ten retained crash reports (two baseline
  diagnostics added), no fixed-source full/pair crash; all handles terminal.
  HEAD/empty index/held candidate remain unchanged. R1/R2 native, original R3
  causality/AX, R5 decision, R6 and E1–E4 remain open. Suggested commit only:
  fix(gui): avoid owning editor cycles in the line-number gutter.

## 2026-09-11 — M6 closed-tab disposal and native/wrapper boundary

- Continued from the verified gutter repair in the authoritative dirty worktree,
  preserving codex/v1-development HEAD 3bde2b5 and the empty index. No foreground
  attempt, user-content change, Git mutation, packaging or release action.
  Test-triage guided separate native-destroyed and weakref-finalized observations.
- Four original closed-window fixtures (five editors) pass with explicit Qt
  DeferredDelete followed by worker GC, exec 57779 exit 0. The original 131-test
  prefix then passes 16.593s without added drains/GC, exec 33175 exit 0. Each
  observed worker-finalized wrapper has a prior GUI-thread native destruction
  record. This discards the inference of a new cross-thread native deletion in
  those cases, not the original timer crash reports or their unknown receiver.
- Actual tab-close probe: baseline keeps 25 native editors after 24 Discard
  closures with one open tab; all closed editors release only with the window.
  Initial probe made a wrong empty-template assertion after recording counts;
  corrected r2 preserves actual initial text and exits 0. Two accepted-close
  disposal assertions fail on baseline while Cancel passes (3 / 0.647s,
  exec 58488 exit 1).
- EditorTabManager now schedules removed editors for Qt deletion only after
  accepted close. New/extended GUI tests cover native child destruction, live
  document bytes/cursor/scroll, Cancel and named/unnamed save failure. Shared
  compile managers and PDF identity remain governed by existing code. Final
  focused 42 / 6.408s / OK, exec 50604 exit 0. Fixed actual 24-cycle probe keeps
  only the one open editor, zero live closed editors, unchanged surviving text.
- Final app 890bbd2c2968cbd5de120a729cccb6bb0951d1f9af5d3a48db8fbcdfcb0fd514;
  app+tests 39f1a73e8c287e85bf8ef69b47052bdf55bfcaa681064815d31ceb2a72f86f50.
  Expanded 254 / 49.498s and frozen required full 1524 / 140.927s pass;
  sequential exec 57755 records both child exit 0 and explicit terminal exit 0.
  Full log /tmp/icstex-v1-tab-retention-suite-r1.log SHA-256
  e06c8e2f557d2835288e551b1b3846a493bd2d34cdd38d46e6f29b9ed17e55da.
  Post-terminal source hashes match; compileall/diff pass. Ten retained reports
  unchanged, all handles terminal, HEAD/index/held feed unchanged.
- Follow-up read-only probe on final source: six actual insert_table modal
  Cancel cycles retain six parent-owned TableDialog children after event drains;
  source unchanged, exit 0. This separate gap is not fixed in the current patch.
  Next bounded work is TableDialog disposal after Cancel/value extraction,
  preserving actual ownership/drafts and not blanket-deleting OCR workers.
  Receipt docs/v1-m6-tab-disposal-verification-2026-09-11.md; state/plan/matrix/
  index updated. Original timer causality, physical R1/R2/AX, R5, R6 and external
  E1–E4 remain. Suggested commit only:
  fix(gui): dispose editors after confirmed tab closure.

## 2026-09-11 — M6 table disposal, one-Undo insertion and stale-target refusal

- Continued the actual source-table workflow, preserving shared work, branch
  codex/v1-development, HEAD 3bde2b5 and empty index. No foreground control,
  student-file writes, commit/push, packaging, install or release action.
- TableDialog values are extracted before deferred native deletion in a finally
  guard. Actual Cancel, exec/value errors and accepted parent closure retain
  source/disk safety. Disposal alone exposed a separate one-Undo failure.
  Test-triage separated lifetime, transaction and later target errors rather than
  weakening tests or assigning them to the historical native crash.
- Shared package insertion no longer resets all text/Undo. QTextCursor edits
  preserve selection direction and UTF-16 coordinates; packages and the snippet
  form one edit block, and padding uses actual replacement bounds. Prior Undo,
  consecutive operations, independent package fixes, inline cursor and wrapping
  pass. Intermediate transaction source passed 264 expanded and 1534 full tests.
- A subsequent actual modal external reload accepted a table at the old cursor,
  splitting documentclass after a header was inserted. The first diagnostic's
  selection-preservation assumption was wrong (retained r1 exit 1); corrected
  r2 observes selection clearing and split command while original external disk
  bytes remain intact. Four stale-target refusal tests then fail on baseline.
  Table confirmation now checks the captured editor revision/target context;
  source reload/edit/Undo, cursor move or target closure keep the draft and
  copyable preview open rather than apply to a changed target. Cancel disposes it.
- Final app 61b4578c66fda33f78ddb63952ade35c7069c93e9947cc8fd18fbc318614ec8a;
  app+tests f24bcd01113d0398c08c37950abe1e1e66772ac674e1656f7232432737210a0a.
  Focused 14 / 2.020s, expanded 268 / 51.853s, required full 1538 / 142.721s
  all pass; final sequential exec 94339 terminal exit 0. Post-terminal hashes
  match, compileall/diff pass. Full log /tmp/icstex-v1-insertion-full-r2.log SHA
  540b0ae31a2cc48b887c2d5b3fdeab041e93e035f4a16a77c555a668cfb4b832.
- Actual unpatched modal/buttons probe r2, exec 67845 exit 0: six Cancel cycles,
  accepted replacement, one Undo plus prior history, explicit Save/reopen and
  real visible pdfLaTeX FINAL pass. A separate external-reload case retains grid,
  zero/caption/label, copyable preview and explanation while refusing real OK.
  Inspected images show retained draft and settled FINAL status. Ten retained
  crash reports and held candidate unchanged; all handles terminal. Not native
  IME, AX, Windows or original timer-cause acceptance.
- Receipt docs/v1-m6-table-insertion-verification-2026-09-11.md; state, active
  plan, acceptance matrix, index and development-source user guide updated.
  Next bounded check is ordinary-source formula coordinates after non-BMP text,
  not a repeat of completed table cycles or blanket OCR-dialog cleanup. R1/R2,
  historical R3/AX, R5, R6 and E1-E4 remain open. Suggested commit only:
  fix(gui): preserve table insertion history and reject stale targets.

## 2026-09-11 — M6 formula coordinates, target guards and actual FINAL

- Continued the bounded source-formula check from the verified table slice,
  preserving shared work, codex/v1-development HEAD 3bde2b5 and empty index.
  No student-file change, commit/push, packaging, install or release action.
- Real modal baseline reproduces rejected/misplaced selections after non-BMP
  text, misplaced packages/cursors, stale empty-range acceptance and deleted
  editor access. Explicit Python/UTF-16 boundary helpers, tracked Qt replacement
  cursors and a shared table/formula source-target validator now preserve exact
  replacement, package/snippet one-Undo and prior history. Changed/closed targets
  refuse OK while retaining the draft and copyable preview. Wrapper switching
  now clamps using UTF-16 length. No OCR-worker lifetime policy changed.
- Retained baseline 7-test failure, separate wrapper-cursor failure and initial
  focused fake-dialog keyword error; fixture corrected without weakening its
  original assertions. Test-triage separated these from actual product failures.
  Final focused 133 / 5.788s, expanded 277 / 54.319s and required full
  1550 / 145.308s pass. Sequential expanded/full exec 30576 terminal exit 0;
  compileall/diff pass. App 489657f34516f5bfeee0934b84a26885e217e8ff3ea7cad05f3f1297819d0085;
  app+tests 136e1892c4de31d04db0de8a2a40e97f7d58877238e90ab0784e161fc31ad59a.
  Full log /tmp/icstex-v1-formula-full-r1.log SHA-256
  7d9ecd3fd31f9f9714ce43116423dae07a52021bd7cb6ac382f7e2c9a3c136b1.
- Actual unpatched modal/buttons probe r6, exec 19189 exit 0: backward Cancel,
  unknown macro/comment preservation, package/replacement Undo plus prior edit,
  explicit Save/reopen, real pdfLaTeX FINAL, current PDF/source identity and
  external-reload refusal all pass. Viewed final PDF and retained-draft images.
  Earlier r1-r5 exit-1 verifier runs remain: the old <100 lightness criterion
  missed visible gray glyphs (minimum 119). Final paired contrast/blank-paper
  control detects 115 pixels <160 versus zero on blank paper, with source/PDF
  identity checks retained. The visible 200% offscreen pixelation is not certified
  fixed or assigned a renderer cause. This is not native/IME/AX acceptance.
- Receipt docs/v1-m6-formula-coordinates-verification-2026-09-11.md; current
  state, plan, matrix, index and development-source guide updated. Formula
  handles terminal, ten crash reports and held candidate unchanged. No foreground
  control occurred during this formula slice. User subsequently reported wake;
  next is fresh R2 native Inspector shortcut/high-scale verification. R1/R2,
  historical R3/AX, R5/R6 and E1-E4 remain. Suggested commit only:
  fix(gui): preserve formula targets across UTF-16 boundaries.

## 2026-09-11 — M6 awakened native Inspector focus and high scale

- User reported the computer awake; new isolated Cocoa MainWindow was readable
  and controllable. No existing installed app, student file, input-source or OS
  setting changed. Source/app+tests remain the preceding 489657f3/136e1892 hashes.
- Actual Control+Tab and Control+Shift+Tab reach Apply/Alias before Chinese input,
  after real Pinyin commit/Undo/Redo/second-candidate cancellation, and after the
  test window's View menu changes its isolated UI scale to 150%. States 7/9,
  25/27 and 29/31 record focus roles with original model/files and zero Apply/Save.
  Native-window images 29/31 show the respective visible focus outlines.
- Alias Tab → content → Control+Tab → Apply, Space then Command+S produce one
  explicit Apply and one Save. Final reloaded target is exactly base 中文, second
  table untouched, no compiler created. Existing Block autosave after explicit
  Apply is observed, not mistaken for premature draft saving. Twelve real IME
  events and 36 state snapshots retained. Input source remained Chinese Pinyin.
- Exec 58955 / PID 38006 ends at exit 0; report passed/window_destroyed true and
  timeout false. CUA timeout after closing is not the completion evidence; native
  deletion and terminal process/report are. Report /tmp/icstex-v1-focus-native-r2/report.json
  SHA-256 94df0996a30b7b30603d12d533313cf7a532b436e99761b2ea65dfcab4f2e4b0;
  log /tmp/icstex-v1-focus-native-r2.log SHA-256
  e482a2631255d09c0bec293a2c022877f1bf91248684c6d1b8174e12215811a9.
- No source/test/probe changes during native follow-up; preceding 1550 full pass
  still matches current hashes. Compileall/diff pass again, ten crash reports,
  HEAD/empty index/held feed unchanged. All handles terminal. No commit/push,
  package, install or release. Receipt docs/v1-m6-inspector-native-focus-verification-2026-09-11.md;
  state/plan/matrix/index updated. Inspector native case is closed; next bounded
  R1 is ordinary-source partial commit/default 800 ms, not this probe's one-hour
  override. R2 citation/tool-rail/broader layout, old R3/AX, R5/R6 and E1-E4 remain.

## 2026-09-11 — M6 native default-save observation and input boundary

- Continued from completed Inspector native evidence, not a no-progress turn.
  New tools/probe_idle_composition.py uses real default 800 ms saves, isolated
  settings/source, actual native input and unpatched save/input methods. It
  observes disk bytes/inode/mtime, preedit, revision, cursor/Undo and real timer
  timeouts. No application or test source changed; app 489657f3 and app+tests
  136e1892 identities remain exactly the preceding formula snapshot.
- Native r1 exec 29935 exits 0, window destroyed, zero manual Saves. Partial
  Pinyin selection produces preedit 中wen with empty commit, unchanged original
  source/disk/identity and no timer for a sampled 44.356 s. A later real 中文
  commit followed immediately by n/ni saves only committed bytes while retaining
  ni, cursor/anchor 67, scroll 0, Undo and source revision. Configured interval
  800 ms; observed delivered-save delay 1.0642 s, not a timing guarantee.
- Escape cancellation retains disk inode/mtime/bytes, revision/Undo, no new
  timer or save in a further 25.223 s sampled hold. Actual Command+Z and
  Command+Shift+Z each restore/save the expected state; three save timeouts total.
  Fourteen IME events, one text commit, zero combined commit/preedit events.
  Post-terminal assertions and viewed candidate/cancel screenshots verify the
  bounded result; no relabelling as native combined partial-commit evidence.
  Report SHA-256 30d2ad9d99727b12ea3478609374d94531177b985dc2c9c73c3c1d84c13b4c6c;
  log /tmp/icstex-v1-native-idle-r1.log SHA-256
  6f4bd865e6952637b96505a4c721d25642f59812e2cae441632ff0619c9c6888.
- Test-triage distinguishes IME conversion from commitment and manager creation
  from compile execution. The final observer renames compile_created to
  manager_created and separately observes build-start signals. R1 raw evidence
  retains its original field; no retrospective build-start claim.
- A new external-conflict r2 fixture received an unattributed s key before agent
  key input. Closed to avoid possible contention with user typing; async question
  asks about keyboard use. Exec 73055 / PID 42598 exits 0, window destroyed,
  zero IME events/compile starts; no external change/conflict tested. This is not
  a product failure/pass or a locked-screen claim. Extra input remains in the
  saved synthetic file/report. Both CUA close timeouts were resolved by terminal
  process and destruction evidence; all native handles closed.
- Required full repeat 1550 / 281.502s / OK, exec 90745 terminal exit 0. Log
  /tmp/icstex-v1-native-idle-full-r1.log SHA-256
  ebec68bac17372f87689dd6f37d649f92628296ba1a5b354d4c15295d36316aa.
  Post-terminal hashes match; compileall/probe syntax/diff pass, ten crash reports,
  HEAD/empty index/held feed unchanged. No student data, input-source/OS change,
  commit/push, package, installation or release. Receipt
  docs/v1-m6-native-idle-save-verification-2026-09-11.md; state/plan/matrix/index
  updated. Next after keyboard is free: native external conflict then formula
  partial-conversion/commit. Completed default-save case is not to be repeated;
  remaining R2/R3/R5/R6 and E1-E4 keep their scope.

## 2026-09-11 — V1 current-state and readiness reconciliation

- Background-only follow-up while awaiting keyboard-use clarification; no native
  window, input, application source, test, dependency or installed-app change.
  Re-read the complete development instructions and reconcile the finite matrix
  against source-identified M2 image, M3 Cocoa, M4 migration/recovery and M5
  delivery receipts. Raw image/citation/material/repair/migration/tool-version
  result files were present and their SHA-256 values matched their receipts.
- Replace stale current-risk claims that image import, source/material workflows,
  checkpoint/draft/migration or delivery chains had never been implemented or
  exercised. Preserve historical receipt identities and native-vs-Qt/offscreen
  limits; do not rewrite old results as current-source native acceptance.
  Roadmap now distinguishes implemented submission checks/profiles from remaining
  local acceptance and future course content. D010/D013 and release gates unchanged.
- Add docs/V1_RELEASE_READINESS.md as a draft seven-state checklist: source,
  platform, artifact, signing/notarization, install/upgrade, online distribution
  and real-user acceptance. Link it from the index, current state and matrix.
  R6 is partial, not complete; R1/R2/R3/R5 and E1-E4 remain explicit. No release-
  candidate recommendation. Held Beta r2 evidence remains a separate older tree.
- Read-only remote check exits 0: development branch is
  3bde2b5d25803262dedef89a081ee6ffbe2b6967, release/2.1 is
  f03776e87c0f938421a70ff5b085db920f2d01d7. Worktree increments remain uncommitted
  and not pushed. Verified empty index, unchanged HEAD and held feed SHA-256
  be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03.
- App 206 Python files / 489657f3 and app+tests 325 / 136e1892 still match the
  preceding native/full-test source identities. Rechecked the exact full log
  hash and 1550 / 281.502s / OK result; no new full run was claimed for this
  ordinary documentation-only change. Fifty-six local Markdown link targets
  across the five state/index/roadmap/matrix/readiness files exist; diff check
  passes. Matrix source paths exist; AST scan found no direct app.gui imports
  in app/core. These are bounded documentation/architecture checks, not full
  product acceptance. No commit, push, package, signing, installation or release.
- Next native action remains external conflict during real composition, only
  after keyboard-use clarification. Do not repeat the completed default-save
  or Inspector cases. Suggested commit only:
  docs: reconcile V1 evidence and release readiness gates.

## 2026-09-11 — Restricted LuaLaTeX cache-root policy review

- Background-only test-triage follow-up; use the smallest name-policy check,
  not another full suite or unrestricted compilation. The original R5 receipt,
  current compiler/Agent source, D015 and installed Kpathsea manual distinguish
  the protected/MCP failure from the ordinary GUI's default I/O policy.
- Eighteen actual kpsewhich checks completed, containing command exit 0.
  With openin_any/openout_any=p, the installed ScriptExtensions input/output
  names are both denied; overriding only TEXMFVAR or TEXMFSYSVAR to texmf-dist
  makes both pass. Relative project names pass and parent names remain denied.
  This rules out treating these overrides as a read-only compatibility fix.
  Name-policy acceptance is not OS write permission or an actual successful
  write. No TeX/Lua file-open/write or compile was attempted; host hash reads
  confirm the installed resource remains unchanged. Child-check environments
  only; no persistent setting, dependency or production-code change.
- Captured stdout retained in
  docs/data/v1/m6-lualatex-policy-names-2026-09-11.json, SHA-256
  bf3e36d8024b6162a213c541ee5ad48fcf8b28027e1b4057c7907cc98b094b7b.
  New receipt docs/v1-m6-lualatex-policy-review-2026-09-11.md records the exact
  command, local primary-manual identity, results and limitations. State,
  matrix, readiness checklist and index updated; R5 remains unresolved.
- App 489657f3 / app+tests 136e1892 unchanged; preceding full-test result is not
  relabelled as a new run. All 18 stored observations and 59 local Markdown
  targets verify; diff check passes. HEAD, empty index and held feed unchanged.
  No foreground control, student document, commit/push, package, installed-app
  replacement or release. Suggested commit only:
  docs: record restricted LuaLaTeX cache-root policy limits.
- Keyboard-use clarification remains unanswered across the native-idle,
  reconciliation and this policy-review goal turns. Independent bounded
  background work completed during that wait; no live process remains to poll.
  Remaining native R1/R2 needs keyboard availability, and R5 compatibility
  still needs a bounded maintainer security/toolchain decision. Do not restart
  passed tests or invent further cleanup to substitute for either gate.

## 2026-09-12 — Native source conflict and formula Pinyin closeout

- User explicitly confirmed keyboard control, resolving the prior contention
  question. Three isolated synthetic Cocoa probes used current app 489657f3 /
  app+tests 136e1892, no app/test/probe source change. No student file, installed
  application, input-source setting, commit/push or release action.
- Source conflict exec 65068 exits 0, timeout false, window destroyed. Actual
  external file edit during live Pinyin preserves candidate, original buffer,
  revision, cursor/anchor, scroll and Undo. First continuous conflict/preedit
  sampled hold is 22.185 s; an earlier scratch 50.941 s span included a second
  composition and is not used as continuous-hold evidence. Escape, later Chinese
  commit and native Command+S/default No keep the external file untouched.
  Native Save As creates local-draft.tex containing the exact local Chinese
  draft while main.tex retains external-A. All later original-file inode/mtime/
  bytes are stable. Eighteen IME events, zero save timeouts/compile starts.
- Actual Save As panel initially points to home. Clipboard paste into its Go To
  sheet times out with the old field unchanged; observed AX path/name fields
  select only the synthetic directory. This fallback is not physical path typing
  or a successful clipboard test. Native saved-path state plus separate bytes
  prove both versions, not the observer's fixed original-path disk field alone.
- Formula visual/source execs 96322/13141 each end at exit 0, passed true and
  window destroyed. Each records 20 native IME events/seven states: partial
  conversion 中wen remains preedit, Apply disabled and x+ draft unchanged;
  Escape restores the original state, 中文 commit and native Undo/Redo pass,
  Command+Return returns exactly $x+中文$. Original document snapshot untouched.
  No combined nonempty commit/preedit event was emitted. These actual dialogs
  verify returned plans, not a new MainWindow document insertion/FINAL run.
- Native IMKCFRunLoopWakeUpReliable warnings retained in all three logs. CUA
  post-close observation timeouts resolved by polling the same process handles
  to terminal exit 0 and checking destruction reports; no restart on timeout.
  No new September Python crash report: the ten retained names remain unchanged.
- Receipt docs/v1-m6-native-conflict-formula-verification-2026-09-12.md records
  exact commands, report/log/file hashes and limits. Conflict report SHA-256
  e82ca6eaa4a263215126f095860d563200c7777684a17345df9d936d40edfd49;
  formula visual/source reports 44e4e780629ae439b01cc48ddce3024ee1f74819fbdf2d05abf664581fa77417 /
  2ee542832c6bdab446441cb579e71a84135e6e1cb38bdd0f457d5a0de221bb72.
- Required compileall and full discovery pass: 1550 / 169.147s / OK, exec 32613
  terminal exit 0. Full log SHA-256
  9f410c6a7829d0f7e874dca166faf2c9bd2db11880c9554bc0413b761fad95a7.
  Post-terminal app/app+tests, HEAD, empty index and held feed unchanged; diff
  check passes. Active brief, matrix, state, index and readiness updated. R1
  addressed for tested local Pinyin; R2 citation/tool-rail/scale is next. R3
  historical timer/style/AX, R5 bounded decision, R6 and E1-E4 remain. No full
  M6/V1 or release-candidate claim. Suggested commit only:
  docs: verify native conflict preservation and formula composition.

## 2026-09-12 — Native citation focus trap and bounded repair

- With keyboard authority, native r2 reproduced Tab/Shift+Tab cycling within
  the read-only citation table at 1080x720/100%. Down/Up selected the expected
  missing/used/unused rows and updated full detail; no keyboard child navigation
  completed. Nineteen recorded states, two checks, unchanged synthetic files,
  zero compile starts, no observation errors. Exec 40699 terminal exit 0 and
  window destroyed; report SHA-256
  9495261b7a0e85cb0a9f74a2dc87e69147be509999ff8bb3089d70fdcffaac23.
- Added passive native observation mode to tools/probe_citation_layout.py.
  Initial r1 mistakenly called the report.items tuple, so Qt callback errors
  prevented post-report snapshots despite an exit-0 receipt. That evidence is
  retained as incomplete. The correction uses the tuple and rejects completion
  after any observation error; it does not synthesize UI actions.
- Set Tab key navigation false on the two read-only ReferencesPanel tables,
  preserving arrow row selection while restoring widget traversal. Two baseline
  red tests fail at the intended focus assertions. Focused final 46 / 3.663s / OK,
  exec 22710 exit 0; explicit Tab-to-Locate/Space reaches child.tex:2 without
  compile authority. The earlier offscreen Return-in-list non-navigation is
  retained, not relabelled or attributed to a proven platform cause.
- Final offscreen layout probe exec 25930 exits 0 on all five scales/two requested
  sizes; actual minimum is 1080x720, files unchanged and bounded layout predicate
  passes. Report SHA-256
  ab006dba37572607bc6fa1b57a9ec85e508cbd445e2147d7f657b3dda7e8658f.
  Screenshot inspection confirms the scrolled Locate button fits; programmatic
  reveal is not native keyboard evidence.
- Post-fix native r3's first CUA selection reported a newly locked Mac. No keys
  were sent; only identified synthetic probe PID 64756 received SIGINT. Exec
  94853 terminal exit 130/expected KeyboardInterrupt, no completion receipt.
  No probe process remains. User keyboard authority is not revoked, but manual
  unlock is needed before actual repaired-path/rail/scale acceptance resumes.
- Final app 4f83dd34551c6fcf6fd5912df54b690471dd5fc8678e7ffdf687b6c66f0a217a;
  app+tests 2f9a46c25b5e594a4c64ca9497f1583ef947dcc5efd80e5732557de9f4aabd14.
  Required frozen full 1552 / 152.832s / OK, exec 74555 terminal exit 0; full log
  SHA-256 4a2cd243e9e41ad806066f01f3cad8b01e894c5416a68a445f77740e51a98328.
  Post-terminal hashes, compileall/probe syntax/diff checks pass. Ten existing
  Python crash reports, HEAD/empty index and held candidate feed unchanged.
- Receipt docs/v1-m6-citation-keyboard-verification-2026-09-12.md, active brief,
  current state, matrix, readiness and index updated. No commit/push, packaging,
  installed-app replacement, release or student-content change. R2 remains open;
  R3/R5/R6 and external gates unchanged. Suggested commit only:
  fix(gui): restore keyboard traversal through read-only citation tables.

## 2026-09-12 — Read-only workbench table focus sweep

- Background follow-up from the native citation trap identified the same default
  QTableWidget Tab behavior in nine other NoEditTriggers tables. No foreground
  call or unlock retry; the preceding locked-Mac receipt is not a fresh lock poll.
  Editable source/formula/table-draft/mapping behavior remains unchanged.
- Nine one-line focus settings added: six project panels (outline, search,
  image inventory, material check, history, labels), diagnostics, compiler errors
  and Block sources. Existing signals/controllers and save/compile boundaries
  unchanged. Shared worktree changes preserved; no Git mutation.
- New real-MainWindow test covers ten result tables at all five scales, Tab and
  Shift+Tab exit to another widget in the same window, Down/Up row selection,
  unchanged cells, NoEditTriggers and no compile authority. The synthetic saved
  Block source fixture separately reaches Refresh/reverses focus and retains
  block content, revision and file bytes, with zero compile launches.
- Initial test fixture mistakenly queried ProjectSession.revision; corrected
  to the existing _revision before product changes. Initial r1 retains 80 focus
  failures plus that fixture error. Corrected baseline r2 has 81 focus assertion
  failures / 1.258s, exec 25269 exit 1; red log SHA-256
  6fda7ff10f912f4a640372ba7b12c25a121ecbfe8d85aa007daa7316ff22b8db.
  Prior repaired citation tables already passed. Focused final 273 / 52.890s / OK,
  exec 81322 terminal exit 0; log SHA-256
  00ea92449eaeaa75c4a60076e6754cc4823a1dcf1200d38665cffc12f4f91df6.
- Final app 1c577ced8fa231c679d200a4211fdb6cd7d4c93c58fa9e51596404853e51b7aa;
  app+tests 50f3884907e67e54e3042b4d22de356bc11f3a420db22694a1a4b41e3fb0eb27.
  Required frozen full 1554 / 159.894s / OK, exec 90981 terminal exit 0; full log
  SHA-256 b4a08a526b836f90d9a17b15b0be9136ad85d54ac86be1ba722adaa5157fa26a.
  Post-terminal digests match; compileall/diff and HEAD/empty index/held feed
  verified. Ten existing Python crash reports unchanged; all handles terminal.
- Receipt docs/v1-m6-readonly-table-focus-verification-2026-09-12.md, state,
  active brief, matrix, readiness and index updated. Focus traversal is not
  native visibility or Return/Enter/action activation evidence. Continue bounded
  action-route inspection in background; actual native paths/rail/scale await
  manual unlock. R3/R5/R6 and E1-E4 remain. No packaging/install/release/student
  content operation. Suggested commit only:
  fix(gui): release focus from read-only workbench tables.

## 2026-09-12 — Native navigation, focus visibility and read-only activation

- User unlock was confirmed and actual Cocoa input resumed. Native r4 retained
  rail-skipping and 150% offscreen-Locate failures. Scroll focus/resize handling,
  one selected rail Tab entry and explicit focus order repaired these; r5 then
  exposed MainWindow assembly order that the independent widget fixture missed.
  Parenting the sidebar before finalizing its chain closes the MainWindow red.
- Four read-only location tables now route widget-scoped, non-repeating Return/
  Enter through existing controllers. Eight baseline activation failures become
  green; negative selection/focus/repeat cases retain files and zero compile
  authority. No repair/restore/insert/delete shortcut authority added.
- Native r5 records visible Locate at all five scales and all nine tools at
  100%/150%, but retains wrong panel order. Final-source r6 verifies Auto toggle
  ↔ rail ↔ panel, citation table/detail/list/Locate, 100%/150% focus visibility,
  external reverse entry and Space to child line 2. All three native runs exit
  0, preserve synthetic bytes and destroy their windows; zero compile starts.
  Their source/report hashes and failure boundaries are in
  docs/v1-m6-native-navigation-verification-2026-09-12.md.
- A fixture sent QtTest a null focus and aborted; its SIGABRT report is retained
  with the earlier ten reports, not counted as a product pass or erased. The
  corrected fixture processes focus events and checks the target before keys.
  Expanded 301 / 61.299s / OK, exec 65395 exit 0. Frozen full 1560 / 174.959s /
  OK, exec 67870 terminal exit 0; log SHA-256
  d1b4a9ea0e52b556b5d56bb00b13b9b56723812ef6c90ed39a073a3d6a765b49.
- Final app 9b2f44f5d46bd7b2895a6c73ea8f19d1228495b80da9d91c41916d6de21d181b;
  app+tests 7b83ae9b6ab073d906a5875561f4a011c7f48744e756bdb8ccd0379ef91c2f64.
  Post-terminal digests match; compileall/diff, unchanged HEAD/empty index and
  held feed verified. All handles terminal and no live native probe remains.
  No Git mutation, packaging, install replacement, publication or student edit.
- State, active plan, matrix, readiness and index reconciled. R2 still requires
  four-route native activation, broader tools and 200% PDF quality; R3/R5/R6 and
  E1–E4 remain. Suggested commit only:
  fix(gui): restore native tool navigation and visible keyboard focus.

## 2026-09-12 — Four-route native continuation and explicit row selection

- Added a labelled navigation fixture/observer mode to probe_citation_layout.py.
  Real outline and UI-triggered search use synthetic source; diagnostic/error
  records are explicitly synthetic, not a claimed compiler result. Table
  selection, activation and resulting file/line are captured separately.
- Native app 9b2f44f5: outline Return reached main.tex:5 once; a single search
  result with focus but no selection correctly ignored Return. Space selected
  the row, then Return opened child.tex:3 once. Clipboard acknowledgment timed
  out, but AX confirmed the text present; no duplicate paste. A later CUA call
  reported a fresh locked Mac before diagnostics/errors. No further front-end
  call followed. Same process exec 22952 reached its 600-second deadline,
  retained partial report and destroyed the window, exit 1. Zero compile starts,
  no compile authority or changed bytes. Report SHA-256
  c6dcef7ffe91384ab8802ed2fb55bc05319d851b6e9f1b07e4f0c17f3462340b.
- Four existing tooltips and the source guide now explain Space selection;
  activation logic/empty-selection guard unchanged. New real single-result
  regression passes location/byte/authority assertions; four red assertions
  specifically identified missing hint text. Final focused 4 / 1.108s / OK,
  exec 70086 exit 0. Probe interruption now retains partial output and refuses
  success; an explicitly offscreen/mock fixture verifies that branch, not native.
- Final app 60e50d6fbefd94a09fbb3ffbd1f652e3bc3cc8f6fffc2873396088d7723492c0;
  app+tests 907f675326dead46d546436036f9bfdb06bd7088c4d9de6168c928f73b2af6ba.
  Required frozen full 1561 / 164.006s / OK, exec 71950 terminal exit 0; log
  SHA-256 accf27559fc3b214e8d2e8157fa1a16a247699fbb0aaf829fed4ff0a939d2a8d.
  Post-terminal hashes match; compileall/probe syntax/diff pass; eleven retained
  crash reports, HEAD/empty index and held feed unchanged. No live native probe.
- Receipt docs/v1-m6-four-route-navigation-verification-2026-09-12.md and current
  state/plan/matrix/readiness/index updated. Remaining native diagnostics/error
  actions and 200% PDF observation await manual unlock; earlier completed
  cases are not restarted. R3/R5/R6 and external gates retained. No Git mutation,
  packaging, installed replacement, publication or student-content edit.
  Suggested commit only: fix(gui): explain explicit keyboard row selection.

## 2026-09-12 — Unlock retry retained as interrupted native setup

- After the user confirmed unlock, the fresh r2 synthetic navigation window's
  first CUA app selection still reported a locked Mac. No keys/actions or
  further foreground calls were sent; visible desktop unlock is not disproven
  by that service error. Only identified probe PID 76832 received SIGINT.
- Exec 16200 terminal exit 1; partial report records interruption (not timeout),
  destroyed window, unchanged files/source, no observer errors or compile
  starts/authority. App remains 60e50d6f; eleven retained crash reports unchanged.
  Report /tmp/icstex-v1-four-route-native-20260912-r2/report.json SHA-256
  0e50a3d837288241e1a4101f2465a9a4c7213f41203cf366ca62714659e2482d.
- Receipt/current state/active next action updated; no app/test source change,
  repeated full regression, Git mutation, packaging, installed replacement or
  publication. Diagnostics/error native actions and 200% PDF remain unverified.

## 2026-09-12 — Read-only blocked-state revalidation

- No foreground call/window or test rerun. Filtered OS session inspection via
  ioreg reports CGSSessionScreenIsLocked=Yes and kCGSSessionOnConsoleKey=Yes;
  no probe/full-suite process is live. This corroborates the locked-session
  condition at this observation without claiming what the user saw earlier.
- Recomputed app/app+tests digests remain 60e50d6f/907f6753; the recorded full
  regression log retains SHA-256 accf27559fc3b214e8d2e8157fa1a16a247699fbb0aaf829fed4ff0a939d2a8d
  and 1561 / 164.006s / OK. Branch/HEAD and empty index unchanged; diff check
  passes. No code, Git, installed application, credentials or release change.
- Rechecked the development requirements and remaining matrix: native R2,
  unresolved R3 boundaries and the R5 security/toolchain decision prevent local
  completion. No claim of completed M6/V1 or reduced platform scope.

## 2026-09-12 — Native console routes and 200% PDF observation completed

- After fresh user continuation, control resumed. The first app lookup timeout
  was followed by a live inventory/bundle-ID lookup of the same probe; no
  restart. Native error Return reached main.tex:3 and diagnostic Return reached
  child.tex:4, one activation each. Labelled fixture records, not compilation.
  Exec 6828 exit 0, unchanged files, zero compile starts/authority, destroyed
  window. Report SHA-256 dbf4e064d8f77f62157dcf8d2873950570d780cec34b1a89a5beac4cf23350cf.
- Diagnostic focus was clipped at 1080x720/100%; dragging the splitter exposed
  the table. Actual offscreen MainWindow inspection reproduces viewport height
  zero; minimum-hint pane sizing alone also fails at 150%. This new R2 layout
  defect remains unfixed; the workaround is not keyboard-only acceptance.
- Added tools/probe_pdf_native_quality.py to inspect an explicitly hash-checked
  existing synthetic PDF in the production PdfPanel. Native 200%/DPR 1 sample
  is readable without obvious blocky pixelation; no renderer/source change,
  new compilation, native zoom-input or all-font/HiDPI claim. Exec 17850 exit 0,
  unchanged PDF, window destroyed. Report SHA-256
  f6f570b4e1fa2fde77e8727f34b6b0c073041525a1357a3fb81bd62d954d016d.
- Both close actions were followed by CUA read timeouts; terminal process and
  report evidence confirms closure, not a native test timeout. App/app+tests
  remain 60e50d6f/907f6753, matching the prior 1561 / 164.006s / OK regression;
  no new full run. Compileall/probe syntax/diff pass. Eleven crash reports,
  HEAD/empty index and held feed unchanged; no live probe/window.
- New receipt docs/v1-m6-console-pdf-native-verification-2026-09-12.md and
  current state/plan/matrix/readiness/index updated. Next bounded slice is
  console visible-focus/layout repair across all five scales, then native
  recheck. R3/R5 and E1-E4 retained; M6/V1 incomplete. No Git/release operation.
  Suggested commit only: test(macos): record console navigation and native PDF quality.
- Native stderr remains nonempty: scoped AX mitigation, font alias timing,
  IMK mach-port and Caps Lock LED messages, plus accessibilityLabel on invalid
  object 0 in the console run. No new Python crash report; causes not inferred
  from normal exit. These are preserved in the receipt, not AX/IME acceptance.

## 2026-09-12 — Console clipping and visible keyboard targets repaired

- Reproduced the previous native diagnostic clipping with real MainWindow
  five-tier assertions: 2 tests/2.876s, ten failures (selected-row visibility
  and hidden collapsed content). An earlier scale-manager fixture ordering
  error is retained separately, not counted as a product failure.
- Expanded console sizing now uses a parent-owned/coalesced tab-layout timer;
  collapse hides content and retains the header. Diagnostics reuse the focus
  scroll container; item views reveal their current cell and row changes queue
  that reveal. No core, renderer, save/compile/repair authority or selection
  guard change. Focused 2/2.184s and expanded 269/63.964s pass, exits 0.
- Actual Cocoa 100%/150% Tab/Shift+Tab, selected-row visibility, collapse/expand
  and Return child:4 pass without splitter dragging. One activation, unchanged
  files, zero compilation, destroyed window; exec 86860 exit 0. Report SHA-256
  2ea43d16243e38adad55bab69672319dc329e99543afab0f9bcecba969002fad.
  Scoped AX/font/IMK/Caps Lock messages retained; not full AX/IME acceptance.
- Frozen app d73dbdf30e6301a289c99468980282e4bf6bafa8f7cb2fa3182e0d769766f07a;
  app+tests dd236693d317e64ec95435665ba65fb777a79ad01e68d3617d3ee3b8a9a45c5f.
  Required full 1563/195.995s/OK, exec 72051 terminal exit 0; log SHA-256
  f471c659c231d4bbb30ddd299e6deadf7aa5dfec7d079a888f02e6d2f3097712.
  Post-run digests match; compileall/probe syntax/diff pass. Eleven retained
  crashes, HEAD/empty index and held feed unchanged; all handles terminal.
- Receipt docs/v1-m6-console-layout-verification-2026-09-12.md and guide/current
  state/plan/matrix/readiness/index synchronized. Next bounded R2 review is
  remaining Word Count/Submission Check console targets; R3/R5 and E1-E4 stay
  open. M6/V1 not complete. No commit/push/package/install replacement/release.
  Suggested commit only: fix(gui): keep console keyboard targets visible at all scales.

## 2026-09-12 — Read-only console focus and text clipping repaired

- Word Count external focus re-entry and Submission Check selected-row clipping
  reproduced at five scale tiers: six failures in 2/2.619s, exec 71560 exit 1.
  Initial wrappers passed short-text tests and 298/73.992s expanded, but native
  r1 exposed a hidden detail tail. Its completed observer exit is not a UI pass.
  Long-text/expanded-toolbox Home/End assertions then failed ten times in
  2/2.762s, exec 67555 exit 1; the former cursor-at-zero assertion was insufficient.
- Focus-aware Word Count wrapping, scrollable Submission Check and selected-row/
  read-only-text endpoint following repair the observed paths without changing
  text cursors, source, report identity or next-step authority. Final focused
  2/2.951s and expanded 298/76.936s pass. The latter includes source cursor/scroll
  invariants, original bytes and zero save/compile/network/next-step assertions.
- Actual Cocoa r2 verifies 100%/150% keyboard Refresh, Tab/Shift+Tab, result
  selection and Home/End first/last text lines. Exactly two count refreshes and
  two submission refreshes, zero next-step/compile, one unchanged source-buffer
  version, original files unchanged, window destroyed. Exec 58087 exit 0;
  report SHA-256 85f1116a6c3e8bd519e51641dec67d2a4d30d7f56170bf131470d4d8603155a0.
  Qt AX table bounds and text-position warnings are retained, not causally
  explained or dismissed by normal exit. Eleven crash reports unchanged.
- Frozen app 2b010b8a82c93eb3464cf19f18034f6f6bf64aa89a10c700f8cb142494c981eb;
  app+tests 080baad60905030ffd80ae36e5e9ad716df2733b07218207c675a35c11bc2fd8.
  Full 1565/222.776s/OK, exec 43957 terminal exit 0, log SHA-256
  b876a91acb920bfd6d99ac88b4c3f7aede2d54cb2942b6248b14d0063c992c5a.
  Post-terminal hashes match; compileall/probe syntax/diff pass. HEAD/empty
  index and held feed unchanged. All processes ended and native windows closed.
- Receipt docs/v1-m6-reading-console-verification-2026-09-12.md and current
  state/plan/matrix/readiness/index/guide updated. Next R2 slice is PDF page/zoom/
  fit-width native keyboard controls with an existing synthetic PDF and no
  compilation. R3/R5 and E1-E4 remain open; V1 is incomplete. No commit, push,
  package, installed-app replacement or release.
  Suggested commit only: fix(gui): reveal read-only console text and keyboard targets.

## 2026-09-12 — PDF menu guards repaired; native layout and zoom defects retained

- PDF overflow actions previously bypassed disabled buttons through direct
  clicked emission. Ten state/click red failures reproduced the defect; actions
  now mirror EnabledChange and use guarded button.click. More explicitly uses
  StrongFocus/InstantPopup after a separate failing focus assertion. These are
  bounded GUI repairs, not changed export authority or a renderer rewrite.
- Final expanded PDF/visual/preview/editor/export suites: 287/70.287s/OK,
  exec 19852 exit 0. Frozen full: 1569/221.616s/OK, exec 5984 terminal exit 0;
  log /tmp/icstex-v1-pdf-keyboard-full-20260912-r2.log, SHA-256
  c98a944c35efe5657962089946df06d1aba2768084adf31155cde73bbde36da2.
  App d243b3a491d918b76a1b57c657f08748e9ff67586486f882933797e097ca46fd;
  app+tests 12894b9793f3052242800073de02da6c0e46411bbaa4f271a4137a1783f53be2.
- Native r1 retains missed More focus and one Down key reaching source without
  text changes. Final-tree r2 confirms More forward/reverse focus and page 1 to
  2 on a labelled QPdfWriter fixture, but actual menu selection remains open.
  It exposes 35–60px source/PDF overlap and Zoom Out enlarging effective
  FitToWidth 0.5664 to 0.8696 while drifting from page 2 to 1. Read-only
  offscreen geometry/zoom reproduction confirms these defects. Existing green
  visibleRegion/custom-factor predicates were insufficient; not a native pass.
- r2 exec 78498 exits 0, report SHA-256
  73eda655284a1769397389b51868e9dc5d9223c4c0347370ad719daf574df6c6.
  Files/source unchanged, no export/reveal/compile, window destroyed. Scoped
  AX/font/IMK/Caps Lock warnings retained. Post-terminal source hashes match;
  compileall/probe syntax/diff pass. Eleven crash reports, HEAD/empty index and
  held feed unchanged; all handles ended and native windows closed.
- Receipt docs/v1-m6-pdf-keyboard-verification-2026-09-12.md and current state,
  plan/matrix/readiness/index updated. Next strengthen non-overlap and effective
  zoom/page-anchor assertions, repair the observed defects, then native
  100%/150% and menu selection. Test-triage separated fixture failures and weak
  assertions from product evidence. R2/R3/R5 and E1–E4 remain open; V1 incomplete.
  No commit/push/package/installed-app replacement/release.
  Suggested commit only: fix(gui): guard PDF overflow actions and enable menu focus.

## 2026-09-12 — PDF overlap, effective zoom and whole-page centering repaired

- Five-scale actual sibling-bounds red reproduced 35–60px overlap. Replaced
  impossible source/PDF hard minima with content-derived hints. Effective
  scaling now matches Qt DPI, integer per-page geometry and mixed page sizes;
  ordinary zoom/Fit Width retain the reading point, with parent-owned deferred
  scrollbar correction cancelled by navigation/load/clear/destruction.
- Stronger tests inspect actual rendered red-marker pixels, first/middle/last
  pages, both zoom directions, real ancestor bounds and stale-anchor rejection.
  Native r2 further exposed Fit Page bottom clipping; whole-page bounds failed
  on all three pages before explicit page centering. Fixture scale-manager
  ordering, raw mode-settle issues and interpreter-teardown warning are
  retained separately, not counted as evidence of historical R3 crash causes.
- Final focused 16/7.271s/OK; expanded 291/77.035s/OK; required frozen full
  1573/231.650s/OK, sequential exec 78234 terminal exit 0. Full log SHA-256
  38411b2ec193bc8b7d01ecb7af4a1cd659c3825527c2dcf25791cf7174d9fd69.
  App 08de3e1c73ea586268873b99d67a6be3197198e372490033f987b35dc8377663;
  app+tests c1bd2ca4016ca6fd4aa09a36eb1a4368e90a89ee2df29b66aed9263168919408.
- Native r1/r2 retain intermediate-source zoom/menu evidence and the Fit Page
  failure. Final-source r3 shows whole page 2 at 100% and page 3 at 150% after
  actual More/arrow/Return selection; separate current CUA screenshots confirm
  both page edges. Exec 74670 exits 0, report SHA-256
  d2c6343f0ada9bb6e737315914416e93db6ec45bfaa314384591bd3ed04b4fa8.
  Combined AX/screenshot sometimes returned old imagery; separate screenshots
  resolved the observation, not proof of a product or event-loop cause.
- All three windows destroyed, original bytes/source unchanged, zero export/
  reveal/compile. No new crash report; retained scoped AX/font/IMK warnings.
  Post-terminal source digests, compileall/probe syntax/diff, HEAD/empty index
  and held feed verified. No commit/push/package/install replacement/release.
- Current state/plan/matrix/readiness/index and
  docs/v1-m6-pdf-geometry-verification-2026-09-12.md synchronized. Following the
  user's elapsed-time concern, next perform a finite original-requirement
  closeout audit instead of another unbounded UI sweep. R3/R5 and E1–E4 remain
  explicit; this is not V1 completion. Test-triage required independent pixel
  and whole-page predicates rather than treating earlier green tests as proof.
  Suggested commit only: fix(gui): preserve PDF viewport and prevent pane overlap.

## 2026-09-12 — Original-requirement closeout audit and finite remainder

- Reread M0–M6, A01–A15 and the original stopping conditions; inspected actual
  read-only submission, checkpoint fault and delivery assertion bodies. The
  remaining modal creation/profile, delivery, checkpoint/restore and distinct
  Block/migration keyboard routes are now finite R2a–c. Existing direct dialog
  calls are functional evidence, not proof of keyboard completion. Accepted
  Pinyin/conflict/navigation/console/PDF cases are not to be restarted.
- Current app 08de3e1c73ea586268873b99d67a6be3197198e372490033f987b35dc8377663
  and app+tests c1bd2ca4016ca6fd4aa09a36eb1a4368e90a89ee2df29b66aed9263168919408
  still match the last frozen full. Retained log remains 1573/231.650s/OK,
  SHA-256 38411b2ec193bc8b7d01ecb7af4a1cd659c3825527c2dcf25791cf7174d9fd69.
  This is an identity/log check, not a repeated test run.
- Read the retained M3/M4/M5/navigation/console/PDF/style/Lua product reports.
  Re-read actual three-workflow core delivery/external-recompile/restored-PDF
  and report files, plus four GUI workflows' PDF-only/source-package outputs.
  All twenty recorded digests have matching files. All seven submission
  reports' declared output sizes and hashes match; no historical receipt is
  relabelled as a new compilation or current-source native test.
- R3 bounded lifetime fixes remain distinct from unresolved historical receiver
  attribution and the scoped AX selection-enumeration limitation. R5 remains
  an actual restricted/MCP LuaLaTeX failure under accepted D015, not a claim
  that ordinary GUI LuaLaTeX always fails. No policy/dependency relaxation or
  risk waiver was inferred. Windows/storage/human/release E1–E4 remain explicit.
- Added docs/v1-local-closeout-audit-2026-09-12.md and synchronized the active
  plan, matrix, readiness, roadmap, current-risk section and index. R6 audit
  complete does not mean local V1 complete. Test-triage separated missing
  keyboard evidence from functional failure and rejected blind full reruns.
- No app/tests edit or foreground window, Git commit/push, package, installed
  application replacement, signing, publication or student-file modification.
  Suggested commit only: docs: bound V1 keyboard closeout and retain reliability and engine gates.

### 2026-09-12 — Modal keyboard safety and ordinary delivery/recovery

- Reproduced and repaired directory-field Tab insertion, Cocoa-policy skipped
  dialog combos, Return/Enter propagating from a combo into parent confirmation,
  and skipped delivery/migration tab bars. Added DialogComboBox and focused
  five-tier/current-policy/popup assertions; no OS keyboard setting changed.
- Final app SHA-256 700b9b832978d2eec3104ab83cc0c465507fa58f844f354bdc4036c154e7db6f;
  app+tests d9445b7087e225e30ea1697cbfb794c9147a72a3f38ce1db07c2e5136f0fa731.
  Expanded 81/40.113s and full 1583/297.883s passed, exec 29022 terminal exit 0;
  compileall, probe syntax, diff and post-native source identity checked.
- Retained native r2's implicit-create failure; r3 verified creation/profile
  keyboard selection and explicit confirm/cancel at 100%/150%, while retaining
  the missing tab-page focus. Final r4 verified native page navigation, PDF-only
  actual output, default-No cancellation, three-file/one-draft checkpoint,
  restore to a new directory and separate confirmation/open of the draft.
  Original/restored files match manifest bytes and hashes; draft stays separate.
- All native runs ended; r4 exit required an explicit Don't Save for the
  synthetic original-window draft already retained in the checkpoint. Eleven
  existing crash reports remain unchanged. Scoped AX and TSM UI-server warnings
  are retained; no historical-cause or full-accessibility claim is made.
- Menu/compile AX activation and one native picker field correction are not
  keyboard-only proof. R2c distinct Block/migration, 150% delivery/recovery,
  RecoveryDraftDialog five-tier focus and OS/menu keyboard evidence remain.
  R3, R5 and E1–E4 remain independent; no deferral/security relaxation inferred.
- Added docs/v1-m6-modal-keyboard-verification-2026-09-12.md and refreshed the
  plan, state, matrix, readiness, roadmap and index. No commit/push, packaging,
  installed application replacement, release, network content upload or student
  edit. Suggested commit: fix: keep modal keyboard selection separate from confirmation.

### 2026-09-12 — Standalone Block and recovery/migration keyboard follow-up

- Added five-tier RecoveryDraftDialog, published migration source/open and
  standalone Block delivery-entry assertions. Native r5 reproduced skipped
  Block page labels; a one-line StrongFocus repair in workspace_widget.py has
  five-scale red/green and native r6 100%/150% actual delivery-entry evidence.
- Diagnosed the new test's publication timeout with a live-worker observation
  and unchanged 8-second deadline; processEvents plus 3ms Python yield resolves
  the harness delay without weakening byte assertions. Selector focus negative
  control fails; the post-copy Return negative control still passes and is not
  claimed as Return red/green proof.
- Final app da2b8d242bf75091e7ed81ce6b4cb66e545c2544225421e52aa6ed77f1ec52c5;
  app+tests 78ef218e43e7b0f4f350a0a68fec691d3bc5817f4cb68a0068f4aa14c8d757f4.
  Expanded 76/29.178s and full 1586/318.535s pass, exec 73414 terminal exit 0.
  Compileall/diff pass; both digests rechecked after native terminal exit.
- User confirmed unlock; final native r6 ended exit 0, 104 states and 990
  propagated key records, no errors/timeout/interruption, tracked windows
  destroyed. Explicit 150% Block FINAL/review/default-No cancellation, two-scale
  legacy-copy publication and 150% checkpoint/recovery keyboard controls were
  observed. The two 12-file migration copies match their manifests; five original
  files and evidence copies match retained hashes. Cancel targets are absent;
  prior archive/restored source/independent draft remain unchanged. No new crash
  report among the eleven retained reports.
- Separate migrated-copy opening defaults No correctly. After later Yes the
  dialog closes, but a visible independent window was not established; retain
  this narrow visibility/lifetime check. CUA NSMenu routing reached the lower Qt
  dialog, so menu entry is mixed AX evidence, not a human keyboard failure or
  pure-keyboard pass. A one-second process sample shows an idle event loop.
- Updated state, matrix, readiness, plan, roadmap, index and the follow-up
  receipt. All owned test handles are terminal; no new native window is left.
  R2 window/menu evidence, R3 risk, R5 decision and E1-E4 remain. No commit/push,
  packaging, installation/release, student edit or security relaxation.
  Suggested commit only: fix(gui): make standalone Block delivery keyboard reachable.

### 2026-09-12 — Migrated-window confirmation and disposal evidence

- Reused the retained twelve-file legacy copy for two background diagnostics:
  the real open helper and actual default-No/Return then Shift-Tab/Space-Yes
  confirmation both create a visible registered independent window, with no
  compile authorization. The window survives migration-dialog DeferredDelete.
  No application code change or native activation conclusion follows from this.
- Added test_modal_no_then_keyboard_yes_keeps_new_window_after_dialog_disposal
  and deletion-aware fixture cleanup. Focused 1/0.625s and related 37/24.662s pass.
  A process-local real-spawn-then-hide control fails the new visibility assertion
  (1/0.529s, one failure); it is not a reproduction of the older native event.
- App unchanged: da2b8d242bf75091e7ed81ce6b4cb66e545c2544225421e52aa6ed77f1ec52c5.
  App+tests: 019169dd24d375f59e56f1568857fd6878979db4c94316628d17d5dc386a8fc5.
  Required full 1587/280.723s/OK, exec 87633 terminal exit 0; compileall, probe
  syntax, diff and post-terminal hashes checked. Both retained migration copies
  still pass the real reader; eleven crash reports unchanged.
- Added an all-window native visibility/activation observer that reuses the
  post-publication fixture and real production open/cleanup path without keys,
  automatic answers or compilation. First CUA call reported a newly locked Mac;
  no keys sent. Owned exec 22600 was interrupted and reached exit 1, with
  source/copy unchanged and no errors/timeout. Its empty destruction array is
  not counted as proof; terminal process plus Close/Hide/final empty-window
  observations establish cleanup. The next probe version retains observed
  references for a non-vacuous destruction check and has syntax verification.
- Native front-to-back visibility and OS/menu evidence remain pending usable
  control. Manual unlock requested once; no repeated unlock attempts. R3/R5 and
  external gates remain. Updated evidence receipt, state, active brief, readiness,
  matrix and index. No Git mutation, packaging, installation/release or student edit.
  Suggested commit only: test(gui): cover confirmed migration window lifetime.

### 2026-09-12 — Confirmed migration copy now becomes the active window

- After manual unlock, native visibility r2 proved the new copied window was
  visible/alive while closing the application-modal dialog reactivated its
  original owner. Exec 40617 ended normally with source/copy unchanged, no
  compile, no errors/timeout/interruption and both tracked windows destroyed.
  This establishes a focus defect, not a missing-window or GC-cause conclusion.
- The production modal wrapper now raises/activates only a valid, explicitly
  opened copy after its modal scope ends. The existing lifetime test uses the
  real wrapper and checks activation order/target; a cancellation test proves
  no activation requests. Baseline 2/0.977s has one intended failure; fixed
  2/0.881s and related 38/26.809s pass.
- Native r3 reused the retained copy/source and unchanged observer. Physical
  default-No/Return cancellation then Shift-Tab/Space Yes shows the copied Block
  window active with Search Block focused; no manual Raise obtained the result.
  Explicit close returns to the owner, then QA Finish ends exec 96010 exit 0.
  Both windows destroyed, source/copy unchanged, no errors/timeout/interruption.
- App: 4e0720eb707fecce1394a7b5f20868be7ea9bd668ba56b615297c23afa267e54.
  App+tests: ddf709d30299aa185630c6fc56ec290e085245d36651931c5a09425ab28a1d73.
  Full 1588/313.379s/OK, exec 32984 terminal exit 0; log
  /tmp/icstex-v1-migration-activation-full-20260912-r1.log, SHA-256
  f39dc4c6aabf1c241fe805785f243193d3d6a0a54b776cbdc86d646f1a44cb96.
  Post-terminal hashes, compileall and diff checks pass. All handles terminal.
  Exact native/test log identities are in the updated migration-window receipt.
- Closed only this observed activation case. OS/menu keyboard evidence, R3
  retained reliability disposition, R5's unapproved compatibility decision and
  E1-E4 remain. No repeated publication/FINAL/recovery workflows, Git mutation,
  packaging, installed-app replacement, release, security change or student edit.
  Suggested commit only: fix(gui): activate migrated copy after modal confirmation.

### 2026-09-12 — Authorized restricted LuaLaTeX compatibility research

- Existing TeX Live 2025/LuaHBTeX 1.21.0 confirmed with latex-doctor detection
  scripts; no installation, Tectonic download or generic smoke run. Synthetic
  direct engine checks retain actual CompileManager p/p and no shell escape.
  Current flags exit 255 at luaotfload multiscript; safer mode exits 1 because
  luaotfload refuses it. Neither candidate generates PDF or is accepted.
- Primitive probes deny the owned parent/absolute sentinel reads, parent write
  and installed-resource output-name predicate. Current local read/write work;
  safer mode disables both. No installed-resource write is attempted. Original
  synthetic bytes, three installed resource hashes and app hash are unchanged.
  Earlier marker-parsing and positive-read assertion failures remain recorded;
  final exec 29815 exit 0 means observation completion, not compatibility.
- Pinned upstream commit 84c5597d60805634f5a4ee0aebf59c2c769488f3 (2026-01-06)
  removes effective openin_any checking. Upgrade-only is not a boundary-preserving
  fix. No 2026 binary tested. OS isolation is a proposed separate mechanism;
  local Apple sandbox-exec manual marks that command deprecated, so a prototype
  would not itself establish shipping support. D015 is unchanged.
- Durable raw report SHA-256:
  487b1f023208ac6fc2d1d86cf0d476e05c4331dd8aa2332401d1f5b31a7edd45.
  Receipt: docs/v1-m6-lualatex-compatibility-research-2026-09-12.md. Current state,
  plan, readiness, matrix, roadmap and index link the result and bounded next
  decision. App remains 4e0720eb707fecce1394a7b5f20868be7ea9bd668ba56b615297c23afa267e54;
  app+tests ddf709d30299aa185630c6fc56ec290e085245d36651931c5a09425ab28a1d73.
  Prior full 1588/313.379s/OK is unchanged-source evidence, not rerun here.
  Compileall/diff checks pass; all owned probe handles terminal.
- No app/test source edits, foreground operation, student edits, Git mutation,
  packaging, installed-app replacement, release, dependency or security change.
  R5 remains open. The newly authorized research is complete; an OS-isolation
  prototype and experimental policy changes require a separate bounded decision.
  Suggested commit only: docs: record restricted LuaLaTeX compatibility findings.

### 2026-09-12 — Revalidated remaining native and Windows access boundaries

- Previous goal turn made progress by completing the newly authorized R5
  candidate research; its separate OS-isolation prototype approval is still
  pending. Test-triage was used to check a distinct available environment rather
  than repeat a full suite or the failed macOS menu input sequence.
- Read-only `prlctl list -a -o uuid,status,name` confirms the existing Windows 11
  VM is running. A single `prlctl exec` request for OS/Python/TeX availability
  returned exit 255: the command requires Parallels Pro or Business. No guest
  command ran, dependency was installed, license was changed or VM configured.
- CUA shows the Windows guest desktop, but coordinate click returns
  `noWindowsAvailable`. Its exposed Raise action was tried; one Ctrl+Escape
  produced no visible Start menu, and the post-Raise click returns the same
  error. No terminal was opened and no product test ran. These are access-tool
  observations, not Windows keyboard or ICSTeX failure evidence. No continuing
  process was created; no alternate OS-event mechanism was invoked.
- Current state and active brief now preserve this concrete E1 access limit.
  Roadmap no longer requests repeating the already closed migration-window
  activation case. R2 menu evidence, R3 historical risk disposition and R5's
  separate enforcement-mechanism decision remain; no new discriminating R3
  test was established and no blind full rerun was used as a substitute.
- No app/test edits, student content changes, Git mutation, packaging,
  installed-app replacement, release, security change or new task/subagent.
  Documentation diff check passes. Goal remains incomplete.
  Suggested commit only: docs: clarify remaining native validation access limits.

### 2026-09-12 — User directs Mac-first completion

- User stopped VM work and directed completion of the Mac product first.
  No further VM action was taken; no guest terminal, test process, software
  installation or configuration change had been started by the attempted check.
- Updated current state and active brief: defer E1 until the user resumes it,
  retain the original platform scope, and focus on macOS R2/R3/R5. The separate
  proposed R5 enforcement mechanism is not implicitly approved by this priority
  change. No source/test, Git, packaging or release mutation. Diff check passes.

### 2026-09-12 — Authorized Mac sandbox prototype produces Latin and CJK PDFs

- User explicitly allowed the temporary Mac compiler sandbox and isolated
  input-policy experiment. No Windows or foreground operation followed. Existing
  TeX Live 2025/LuaHBTeX 1.21.0 detected with supplied latex-doctor script; no
  dependency download, install, distribution edit or app replacement.
- Implemented a temporary deny-default sandbox-exec prototype. An initial true
  bootstrap aborted in dyld/libignition; importing only Apple's dyld-support
  profile made it start. Recorded separately from historical ICSTeX crashes.
  First complete prototype passed boundary controls but lacked Library/Fonts
  read access; a read-only addition allowed Latin compilation. All prior failures
  retain their results. The command is deprecated and the imported rules private.
- Final r3 passes unconfined/isolated positive and negative controls for owned
  file access, source-write and write-symlink denial, external symlink and Data
  volume alias read denial, loopback TCP denial and child-launch denial. Only
  then was openin_any=a used for isolated actual LuaHBTeX checks; openout_any=p
  and no shell escape stay in place. No relaxed TeX process ran outside isolation.
- Latin/math PDF: one page, 26769 bytes, compile exit 0/7.283s. Chinese input path
  with ctexart/Fandol: one A4 page, 41449 bytes, exit 0/4.035s. Text extraction
  and rendered pages inspected; expected text/glyphs/equation are readable.
  A ready infinite Lua loop is terminated through the existing process-group
  helper, final -15/1.006s, drained pipes. Exec 40967 terminal exit 0; no live
  owned probe remains. This is not a latexmk descendant-tree or GUI test.
- Owned inputs and installed inspected resource hashes match; app+tests remain
  ddf709d30299aa185630c6fc56ec290e085245d36651931c5a09425ab28a1d73. Prior full
  1588/313.379s/OK remains unchanged-source evidence; not rerun. Compileall/diff
  pass. Durable raw report SHA-256
  24dabe27f0a15976340f75acbe8c2e0b2300816df09cb69c5d78c44e4859b6a2; exact
  prototype text SHA-256 2621ed96acdb34f57fe4305de7a2c717ed714317eb50952189a0818365c387af.
- Added prototype receipt and durable evidence, updated current state, active
  brief, matrix, readiness, roadmap and index. No product source/test or policy
  change, Git mutation, packaging, signing, release or student edit. D015 stays
  accepted and unchanged. Formal backend support and actual product integration
  remain separate decisions; successful prototype does not close R5 or V1.
  Suggested commit only: docs: record Mac compiler sandbox feasibility evidence.

### 2026-09-12 — Approved fail-closed Mac compiler source integration

- User approved integrating the proven local sandbox, requested no repetitive
  tests and a result within five hours. Work began around 15:29 Asia/Taipei;
  bounded source result and final gate completed by 15:52. No VM, foreground UI,
  student files, installed app, TeX distribution, dependency, Git mutation,
  signing, packaging or release action. D021 scopes the local security decision.
- Added the core Mac adapter and a focused shared-compiler seam. A whitelist
  environment and exact executable profile confine driver/engine children;
  owned kernel checks precede isolated openin_any=a, output p stays. Missing or
  failed isolation refuses compilation. Existing output hardlinks are rejected;
  source-only inputs, no-shell-escape, -norc and process-group stop remain.
  Ordinary GUI policy and MCP schema are unchanged.
- Actual latexmk/LuaLaTeX/BibTeX Chinese/math/reference PDF passes in r4,
  20.865s, one A4 page / 40661 bytes; PDF SHA-256
  6a9ebb1a46431ed8c6753e738be33354424c642e57c35607d8a726da6fe2eb43.
  Text and rendered page inspected; originals and build input evidence stable.
  OS denial controls and existing-hardlink refusal pass. Real driver/Lua child
  readiness then stop confirms idle/drained completion and no remaining group.
  Earlier pdf/Xe and actual stdio-export successes retain intermediate identities.
- Retained failures explain exact /bin/bash, kpsewhich and Cwd /bin/pwd needs;
  no general executable-directory grant. Pre-existing hardlink append-open was
  reproduced on owned data without writing bytes, then refused. Stop probe's
  early is_running and hidden-output-name fixture errors were corrected without
  weakening the product policy. Unchanged prototype and old GUI cases not replayed.
- Initial adapter/compiler 42 focused pass; added guard tests expose one fixture
  cancellation misuse, corrected and checked singly. One frozen required full:
  1598 / 313.187s / OK, exec 15456 terminal exit 0. Log
  /tmp/icstex-v1-macos-sandbox-full-20260912-r1.log, SHA-256
  358a6f5f32e1637aea70f004d2467e33e01c3b793d1cd5ecfa29e82aeda1ab95.
  Post-terminal app 7009463b6f091f8d58f46fcfee3e08b03b3535fe9d89b0882ac7d3a133e87506;
  app+tests 14093898a54aa926b992b20106c570c1d2f6a5899af2ab35b69c157b1467cbc4.
  Compileall/diff pass; HEAD 3bde2b5/empty index intact. Python crash-report count
  still eleven, all owned handles terminal and no QA window opened.
- Receipt: docs/v1-m6-macos-sandbox-integration-2026-09-12.md. Durable selected
  raw report manifest SHA-256 b4a0c2fecdce3065dddfa3c14350c454566e1903569e0ee0b833218a4ae1c7a4.
  Updated current state/active brief/security/matrix/readiness/roadmap/index.
  Biber/PAR, other installations/macOS/TeX versions and the deprecated/private
  backend's release support are unaccepted. R2/R3 and E1–E4 remain; not full V1.
  Suggested commit only: feat: isolate restricted macOS compiler jobs fail closed.

### 2026-09-12 — Biber-only bootstrap failure narrowed without replaying accepted workflows

- Continued M6 from the verified Mac integration, not from M0. New biblatex/Biber
  fixture fails closed: LATEX_ERROR / driver 12 / 17.591s, unchanged source/bib
  bytes and stable input evidence. The intermediate unresolved-citation PDF is
  not accepted as a successful FINAL or exported. Exec 99902 terminal exit 1
  records the probe's failed success assertion, not a native crash.
- Reduced diagnosis invokes only the installed Biber --version with owned
  temporary state and no document input. Same binary/environment: outside
  isolation exit 0 / 24.420s / version 2.20; inside isolation exit 255 / 0.131s,
  misleading Command Line Tools missing message. Actual developer directory and
  CLT directory exist. Exact sandboxed xcode-select and lipo invocations both
  return 71 / execvp Operation not permitted. No install or system change.
- Installed-binary strings identify xcode-select/lipo, thin-binary extraction
  and custom interpreter execution; successful startup creates 3868 temporary
  files including thin/biber, biber and libperl.dylib, cleaned afterward.
  This proves a runtime boundary gap, not that allowing one command fixes it.
  No product policy change or unconfined document fallback. Proposed separate
  restricted preparation with a read-only exact runtime needs explicit approval.
- Added selectable lua-biber probe case and standalone runtime/dependency
  diagnosis. Runtime exec 89576 and dependency driver exit 0; denied child codes
  retained. All owned handles terminal, no GUI/VM, new dependency, student edit,
  Git mutation, packaging or release. py_compile/diff pass. Application/tests
  unchanged at 7009463b / 14093898, so the preceding full 1598/313.187s/OK is
  reused rather than rerun. HEAD 3bde2b5 and empty index preserved.
- Receipt docs/v1-m6-macos-biber-boundary-2026-09-12.md; durable selected report
  SHA-256 904dd3bc9dc32ddb9b72b4e35e7ebf4fba40d3b8cc79458c1dc13610fd2064fd.
  Updated current state, active brief, matrix, readiness and index. R2's host
  menu route and R3 historical receiver/AX disposition remain distinct; the
  alternative keyboard tool found is simulator-only and was not used on Mac.
  Suggested commit only: test: record restricted Biber bootstrap boundary.

### 2026-09-12 — Ordinary Mac writing handoff prioritized; restricted Biber deferred

- User explicitly chose ordinary Mac writing delivery first and deferred the
  Biber feature. Updated the active brief, current state, roadmap, acceptance
  matrix and readiness checklist: the Agent/MCP restricted Biber failure stays
  recorded, but runtime preparation/approval is no longer this handoff's blocker.
  No new runtime design, sandbox relaxation, GUI policy change or implicit
  BibTeX substitution. R2 OS/menu and R3 reliability risks are not waived.
- Added docs/MAC_WRITING_HANDOFF.md with the existing python3 -m app source
  entry, implemented writing workflows and explicit evidence/install limits;
  indexed it. Corrected the matrix's stale duplicated app digest to refer to
  authoritative PROJECT_STATE instead. No student content, installed app,
  foreground UI, VM, package, dependency or Git mutation.
- Live repository root and physical cwd match. HEAD remains
  3bde2b5d25803262dedef89a081ee6ffbe2b6967, with the index empty. Current app
  7009463b6f091f8d58f46fcfee3e08b03b3535fe9d89b0882ac7d3a133e87506 and app+tests
  14093898a54aa926b992b20106c570c1d2f6a5899af2ab35b69c157b1467cbc4 match the
  previous full gate. Retained log still reports 1598 / 313.187s / OK and hashes
  to 358a6f5f32e1637aea70f004d2467e33e01c3b793d1cd5ecfa29e82aeda1ab95.
  Documentation-only scope change; no test replay or new native launch claimed.
  Suggested commit only: docs: prioritize ordinary Mac writing source handoff.

### 2026-09-12 — User-confirmed Mac source stage closeout

- User explicitly confirmed: “按 Mac 源码阶段性交付收尾，未完成验收留到后续”.
  Closed this stage under that adjusted scope, not as full M1–M6 acceptance.
  Updated current state, handoff, implementation brief, roadmap, matrix and
  readiness to retain deferred requirements and await the next user Goal.
- The existing Python source had been launched at the user's request with
  `env QT_QPA_PLATFORM=cocoa python3 -m app`; its native ICSTeX welcome screen
  and LaTeX-ready state were observed. This is launch evidence, not a claim that
  the user's real-project, keyboard, reliability or accessibility acceptance passed.
  This closeout did not restart or control that user-facing application.
- Live root/cwd match the authoritative repository. HEAD remains
  3bde2b5d25803262dedef89a081ee6ffbe2b6967 and the index is empty. App digest
  7009463b6f091f8d58f46fcfee3e08b03b3535fe9d89b0882ac7d3a133e87506 and app+tests
  14093898a54aa926b992b20106c570c1d2f6a5899af2ab35b69c157b1467cbc4 still match
  the retained final full gate; no test replay for this documentation-only closeout.
- R2 menu evidence, R3 reliability/accessibility, restricted Biber, Windows,
  real-storage/human acceptance and release gates remain deferred or held, not
  waived or passed. No source/test edit, student edit, Git commit/push/rename,
  VM work, packaging, installed-app replacement or release. No new performance
  implementation is started by this closeout.

### 2026-09-12 — Performance/UI B1 asynchronous membership increment

- Implemented immutable membership calculation with one active/one latest request,
  GUI context checks, existing watcher-repair dispatch, close/reopen ownership,
  stable parsed-input checks and fresh save/compile preflight. Original writers,
  FINAL rebuild/content evidence and explicit cancellation remain authoritative.
- Final app SHA-256 4d54b93d1116b68e1abad7543a9f8367e94ff69cdd526e2779ac0745aa71a5f3;
  app+tests c690f4b26d25497d823b4eea1c7b36ae0b940a230c16f68f99c369f57c03e943.
  Related integration: 318 / 52.084s / OK, exec94597 exit0. It includes the new
  red/green two-editor external-reload reentrancy guard. Compileall/diff pass.
- Earlier measured app 96e270b3 retains its own evidence: 30-sample 200-child GUI
  commit p95 3.664ms; timer lateness p95 94.825 -> 1.453ms against A. Native simple
  typing p95 27.794 -> 16.152ms; large-project p95 33.257ms but one 79.378ms spike
  remains unresolved. These are GUI/observation metrics, not TeX-engine speedups.
  Ordinary multi-file Cocoa fixed-byte delivery and external/recovery recompiles
  pass on that measured source; no relabelling as final-guard native acceptance.
- Receipts, source boundaries and remaining work: docs/PERFORMANCE_UI_PROGRESS.md.
  B2/B3, C–F, full combined regression, original PDF timeout and native input spike
  remain open. All owned handles terminal; no student edit, user-window control,
  Git mutation, VM, dependency install, package, installed-app replacement or release.

### 2026-09-12 — Performance/UI B2/B3 PDF reuse and reachable search

- Added worker-captured PDF content identity, reusing FINAL's existing output
  digest. Matching path/logical document/verified bytes can retain the viewer,
  search and viewport while build identity advances. Missing/stale evidence loads
  normally; the MCP compile response is unchanged. Added generation guards for
  delayed view/search callbacks and a red/green deleted-document page-signal guard.
- Added persistent PDF search entry, existing-model expandable row, menu and
  Command+Option+F on Mac, guarded Enter/Esc/IME and focus return. Fixed the
  screenshot-observed missing close icon and cramped count with existing assets,
  shared toolbar styling and measured text width.
- Final app aafb0f45d7d93fa0f05387df324cd213068d96c485e15d5544e9100e54264586;
  app+tests a91c548787c5e4eba832afb87e3239f638bce7c569ac14f4cdf67277992dc80b.
  Core/PDF/compiler 76 focused pass on its source; later 54 / 16.118s / OK and
  final width-related 3 / 1.733s / OK. Final Cocoa search r5 covers ten scale/size
  states with no callback errors, intact source/PDF and destroyed window.
- Measured db320fa6 source: five trials, 25 visible outcomes; unchanged PREVIEW
  reused in all five, exit-to-visible median 43.929 -> 16.815ms against A.
  FINAL remains about 442–462ms; 30% experimental improvement not achieved.
  The later row-only source is not relabelled as this measured/native PDF source.
- Earlier focus, teardown and width failures remain in the b2 receipts linked
  from docs/PERFORMANCE_UI_PROGRESS.md. Full combined regression, C–F, historical
  blank-PDF cause and the B1 input spike remain open. Compileall/diff pass, all
  owned handles terminal; no user-window mutation, Git/package/install/release.

### 2026-09-12 — Performance/UI C1 source workspace and three-slice layout evidence

- Default writing console now collapses, preserves explicit expansion preference,
  and reveals requested diagnostics without moving editor focus. Welcome uses the
  main workspace; source header and toolbar repetition reduced. Manual action is
  labelled formal compilation; existing compiler menu/actions remain authoritative.
- Source and Block share the instance-stable editor/PDF splitter, with wide-size
  restoration and compact search/focus routing. Targeted existing-theme sizes and
  delivery's fixed primary/cancel footer do not alter publishing transactions.
- App 4ae07f45012f1caebbd29bc298aeed601644966b7d4750e2e7f32fff49f94bd5;
  app+tests 56a420c14045c530ce43a7665fdefed0058baf20c9d66e8f93da9683f320365c.
  Related 83 tests / 20.400s / OK (exec99094); compileall, tool syntax and diff pass.
  Offscreen three-slice probe has 26 states (exec94622), unchanged input bytes,
  no compiler/delivery, no callback errors, destroyed window and matching digest.
  At 1440x900 / 100%, editor height 647px, text viewport 615px, formal button 34px.
  This is not a matched Cocoa before/after result or full-suite acceptance.
- PDF expansion SIGSEGV narrowed to the old B2 fixture deleting the document
  while a Qt search timer retained it; two-case red/green and the final related
  suite validate detaching consumers before deliberate destruction. The original
  deleted-document page-signal assertion is retained. Qt null-document warnings
  remain; no claim about unrelated historical native/style crashes is made.
- Inspected screenshots still show Block auxiliaries crowding the 1080x720 /150%
  editor. Next: context-aware auxiliary visibility, repeated-action/close styling,
  then matched native source/delivery/Block evidence before migrating other panels.
  C–F, historical PDF timeout and B1 spike remain open. No foreground operation,
  student edit, Git mutation, dependency change, package, install or release.

### 2026-09-12 — Performance/UI C2 Block auxiliary layout and bounded evidence

- Existing Block docks now reveal on demand, one at a time in compact layouts.
  Explicit visibility/width preferences survive mode changes and reload; widgets,
  models and draft documents remain the same. Explicit text editing reveals the
  existing inspector. Errors do not hide a focused property draft or become saved
  preferences; unparsed failures reveal diagnostics, user Stop does not.
- Removed repeated compile actions from the summary row, added a neutral source
  tab-close asset using the existing theme, and kept compiler settings in its menu.
- Final app 0bdc1b779745c07db4eee90606d96740abe2746e5f54223fcb6e69ef94c2f823;
  app+tests c1de1f6c7e8295c2706ef69c581bf99dc0eb33bc204db1a3d1973b31af336b11.
  Early 65 related tests passed. Final app's 106-test expansion had two stale C1
  toolbar-selector assertions; both passed after checking the retained menu
  controls instead (2 / 1.283s / exec98748). No blanket rerun/full-suite claim.
- Offscreen c2/layout-r2 has 27 states on 7af89d23, original files unchanged, no
  compile/delivery, no callback errors, destroyed window and matching digest.
  Block's 1080x720 /150% workspace measures 1080x450; matched C1/C2 screenshots
  show the removal of empty auxiliary crowding. Source viewport remains 615px.
  R1 retains a focus failure; a minimal modal-close probe showed no offscreen
  active window. Establishing that test prerequisite made r2 pass.
- Cocoa c2/native-r1 on 331a2cb8 reached welcome, then lost active/exposed state
  before source keyboard injection and exited 1. Window was destroyed; do not
  classify the cause as lock/occlusion/product without evidence. This is distinct
  from A's PDF timeout. No repeated foreground pull or user-window operation.
- Compileall, probe syntax and diff checks pass. Source records retain exact
  evidence identities; final small error/mode-switch fixes do not relabel earlier
  screenshots. C native acceptance, D–F and prior performance anomalies stay open;
  no Git mutation, package, installation, release, VM or dependency changes.

### 2026-09-12 — Performance/UI C3 source auxiliaries and scoped indicators

- Source toolbox/console now share compact space while retaining wide choices
  and dimensions; automatic errors keep focused toolbox input visible. Fixed
  immediate clicks racing the coalesced resize transition. Full project status
  is a bounded, selectable, scrollable read-only region with preserved selection.
- Real FINAL screenshots exposed Block reusing hidden-source compile duration.
  Block now presents its own session progress/result, source callbacks are not
  current UI work while Block is active, and returning to source restores its
  indicators. Build ownership/transactions remain separate and unchanged.
- Final app b59188f69b8b41d129de25e63081b8ca265ebf8f31f3d98e8d0252ecb04f35f4;
  app+tests 8d720db42b5abee97b4d60ee8327e34d2f7265e424b1647b06422f32418db7f7.
  Final related 70 / 15.259s / OK (exec62681). Earlier 66-test integration had
  one resize race; its focused follow-up 5 / 4.738s passed. No full-suite rerun.
- c3/offscreen-final-r1: 28 states/five scales on 1ce23953, actual source/Block
  FINAL and fixed-byte review; no delivery, original files unchanged, no callback
  errors, window destroyed. Final-source indicators-final-r1 uses only 100/150%
  and 13 states; separate real durations and source restoration verified. Frozen
  review PDF equals source FINAL byte hash. These are not performance benchmarks.
- c3/native-final-r1 recorded activation then application inactivity while the
  widget remained visible/non-minimized; active/exposed failed at welcome and no
  keyboard/compile followed. Cause remains unclassified, window destroyed. Asked
  the user about foreground availability; no repeat foreground pull afterward.
- Updated user-facing workbench instructions and identified a measured-next-step
  candidate: Word Count already has category text_parts, while visual-segment
  concatenation remains local code to profile. No speculative E optimization yet.
  C native gate, D–F and historical anomalies remain open. Compileall/probe syntax/
  diff pass; no student edits, Git mutation, package, install, release or environment changes.

### 2026-09-13 — C4 native slices and E1 Word Count accumulation

- With explicit foreground confirmation, c4/native-final-r1 completed 28 Cocoa
  states/five scales on b59188f6 (exec92376 exit 0): real source/Block FINAL,
  identical frozen-review PDF bytes, keyboard/draft/Undo and indicator restoration.
  Originals preserved, no delivery, window destroyed, no Python callback errors;
  IMK/AX limitations and earlier inactivity/crash causes remain unclosed.
- E1 batches contiguous visual fragments by category/source and joins once.
  Public result fields, lexical rules, mode/fallback labels, snapshots, queue,
  cache, TeXcount command and timeout remain unchanged. Constructor red case
  drops from 8000 intermediate segment objects to one final object.
- Final app 4c6b169c64b29b86d7b56969d28f1d9ca86e6e5194cdd70092e05a4ed7acc8f4;
  app+tests 5a3f3c3b72f32ae79a351c3439deb21d83e5870fdb4b71f4f981749d58526cb0.
  62 related core/UI/cache/lifetime tests / 1.544s / OK (exec85441); compileall,
  tool syntax and diff pass. No full-suite or current-source native claim.
- 17 completed matrix outputs match the pre-change full result digests. Same-
  process alternating 40k English fallback medians 1167.283 -> 957.389ms (5 pairs);
  mixed 5423-word project 281.998 -> 269.947ms (7 pairs). Separate-batch regressions
  and all raw samples retained, not universal or TeX-engine speedup claims.
  Single English traced peak rises about 2.48MB; mixed allocation-release/GC
  diagnostic has comparable remaining bytes. No application GC change/RSS claim.
- Baseline script exited 1 when the final stress case fell back instead of
  returning TeXcount mode; preceding 17 timing rows remain individually valid,
  not a full 18-case pass. One later diagnostic observed TimeoutExpired at
  15.010s and honest fallback; no extended timeout or repeated five-run stress.
  Result fields match old fallback except its appropriate failure warning.
- Evidence/source snapshots live under e1/ and c4/ in the task evidence root.
  C's native slice prerequisite now permits D work; other E experiments, F full
  matrix and historical performance anomalies remain open. No student edits,
  Git mutation, packaging, installation, release or runtime/dependency changes.

### 2026-09-13 — D1 submission-check presentation and usable reading area

- Added separate fail/unknown/pass summary, priority display with original
  report-item indices, reason/next-step text and complete copyable technical
  identity. Fixed actions sit outside reading content; expanded reading restores
  the same list, selection and widths. Core checks and action authority unchanged.
- Kept focused Refresh enabled with the existing bounded queue; widening source/
  Block windows retains an explicitly opened compact check panel. Added actual
  reading/header/row sizing and post-resize selected-row visibility. A suspected
  source-stack/welcome minimum-height change was disproved and fully withdrawn.
- Final app e2e1bc99eae6f0b2029d656847bd6e518505709b99a84dd0bcd28ac671ca1f12;
  app+tests 05d7cad19a30f4dec9bed51380a7b79b6e0afa431fc96f6151f43597c09817b4.
  48 related tests / 10.227s / OK and final 12-state offscreen probe (exec18898)
  pass: actions and selected rows visible, no overlap, unchanged check semantics,
  original files retained, no save/compile/repair actions, no Python callback errors and
  destroyed window. Compileall, probe syntax and diff pass, not a full-suite claim.
- d1/before-offscreen and after-offscreen-r6 retain same-recipe/state comparisons;
  independent paths/timestamps/Block identities are not byte-identical fixtures.
  Earlier focus, widening, nested-scroll, minimum-height and clipping failures
  are retained, with stronger final assertions rather than weakened gates.
- before-native and after-native-r1 both failed active/exposed prerequisites,
  exited 1 without keyboard actions, and destroyed the synthetic windows. No
  assertion of lock-screen cause or native D1 acceptance. D2/D3, remaining E/F
  and prior anomalies stay open. No Git, package, install or release operations.

### 2026-09-13 — D2 staged fixed delivery and bounded foreground follow-up

- Reorganized delivery into preparation, frozen review and destination/confirm;
  fixed footer and UNKNOWN acknowledgement, source selection only during
  preparation, copyable complete technical identity, and actual success paths
  with explicit open-directory action. No second publication authority: original
  prepared/lease/cancel/exclusive transaction and late-cancel success remain.
- SHA-256 presentation is calculated once by the existing background worker;
  page/technical navigation does not rehash payloads. No live PDF preview is used
  as frozen evidence. Invalidated contents are explicitly labelled not fixed.
- Final app 00eefebffcfd865855f91b9f9119578dd3a4857024d03d50171e8c2e1a6c6942;
  app+tests 76e49052fc1afd1015bf51fca3cd95f23321d1b03d8f02a71fbef1abe2ad1d7c.
  Four initial red cases retained. Related suite 24 / 12.640s / OK (exec27318),
  incremental suite 4 / 7.828s / OK (exec11483), final navigation/invalidation
  case 1 / 0.346s / OK (exec77568); overlapping runs are not summed as unique.
  Compileall, probe syntax and diff pass. Final whole-repository suite remains F.
- d2/before-offscreen and after-offscreen-r2 use the same unit-fixture recipe,
  preserving exact PDF payloads; after has eight 100%/150% states. A clipped
  acknowledgement in r1 was moved outside the scroller and its full visibility
  asserted. Synthetic unit PDF bytes are not renderer/actual FINAL evidence.
- d2/real-delivery-offscreen-r1 (exec19646, app 07c793bd) passed eight actual GUI
  deliveries: single/multi/main Block/standalone Block, each PDF-only and source/
  report. Each project compiled once; unchanged FINAL reused for second options.
  All frozen/output bytes match, PDF text is expected, originals retained; No
  cancels with no output, Yes publishes. Unchanged checkpoint/recompile routes
  deliberately skipped, not passed. Last technical-location and status/confirm
  wording changes do not relabel that earlier source receipt.
- Renewed D1 native attempt after user foreground confirmation still failed
  active/exposed before keys (exec71555, d1/after-native-r2); synthetic window
  destroyed, no callbacks. CUA separately reported locked Mac, inconsistent with
  user confirmation; actual cause unproven and no repeated foreground retries.
  D1/D2 native acceptance remains open. Next D3, remaining E and F; no Git,
  packaging, installation, release, environment or student-document changes.

### 2026-09-13 — D3 main task-panel labels, identity and formula controls

- Outline title gets flexible width, with short type labels and original line
  authority; refresh preserves selection/scroll. Quick references now expose the
  actual read path and explain empty/fallback scope without importing declared
  libraries or changing write targets. Missing/flat/nested paths verified.
- Formula caret/selection/keys use existing amber theme; compact category and
  collapsible number pad keep the same editor/model, preedit and undo history.
  No new parser or application path. Unknown-source and UTF-16 protections stay.
- Block labels replace raw types/IDs, with context/standard-Copy identity actions,
  inspector copy and previous-build technical copying. Combo display differs
  from stored enum data. Fixed an unmounted nonempty navigation root and replaced
  display-text parsing with existing UserRole identities for slot select/reorder.
  Original command/session and one-undo behavior retained; successful build no
  longer claims that PDF rendering has already refreshed.
- Final app 93be767c0df08addaa0d5d51493535f6afc20ace7b32d378cb5873eede9c2c07;
  app+tests 9e2aa940ecf48c6ffa2b81ffd67d89c678bee14b550622574f9609366227f9f8.
  Initial five red cases retained. Broad related 77-case run had 74 pass/3 fail;
  formula-target/composer plus additions 45 had 44 pass/1 test-edit error. Old
  label/Tab assertions were adapted, an accidentally moved helper return restored,
  and the citation recheck timing was diagnosed, not accepted as green.
- Citation diagnostics showed dependency generation update and a separate queued
  external-file notice canceling a newly requested report. The test now waits for
  the actual notice and settled dependencies before requesting again; no product
  identity guard, watcher or stale-result policy weakened. Single case passes
  (exec8520, 1.020s). Final 10-case incremental set passes (exec81963, 1.424s),
  covering new UI identities, keyboard/preedit, draft copy and path/refresh/layout.
  Compileall, tool syntax and diff pass. Runs overlap; not a full-suite claim.
- d3/before-offscreen-r2 and after-offscreen-r3 capture six isolated components at
  two scales, twelve states each. After source 1dc6df39 retains unchanged model/
  formula, no compile/delivery, destroyed widgets and fully visible named actions.
  Formula's 150% height returns to original 790px after 825/798px intermediate
  regressions; this is not 720px-screen acceptance. Screenshots inspected.
  Initial probe setup failure and intermediate screenshots retained. Last source
  only refines request/copy labels and no-selection copy disabling.
- Shared checkpoint/recovery/migration inspection and D embedded/small-screen/
  native matrix remain before D acceptance; other E/F and historical performance
  risks stay open. No repeated foreground attempt or stable delivery/full-suite
  rerun, and no Git, package, install, release or student-document operations.

### 2026-09-13 — D3 shared review-dialog reading space and fixed actions

- Inspected real synthetic checkpoint creation/restoration, recovered drafts,
  interrupted Block writes, migration review and post-publication UI before
  edits. d3-common/before-offscreen has 16 states: migration primary actions
  scrolled off-screen, while dense large-font checkpoint/recovery content could
  squeeze file rows and version selectors. No student content was used.
- Moved migration review/publish/open actions to a fixed ButtonFlowLayout footer;
  actual result controls are only shown after publication. Checkpoint/recovery
  bodies now scroll and keep minimum tree/preview reading heights, with fixed
  main actions. Existing theme and explicit keyboard behavior reused; independent
  transaction, default-No, lease, byte identity and cancellation logic unchanged.
- Final app 7454ce65717edc05dffd82d881f5fec0137786ca551a979da63c5428abae9d49;
  app+tests 424c2c3ec784349038973593b1e6a46403995e6eed3f25d1d3be74b94d7db717.
  Two new red cases then 2 / 0.402s / OK (output19b490). Related suite 36 / 16.304s
  had 35 pass/1 post-publication reverse-Tab failure; explicit source/open/close
  order fixes that original case (exec33511, 1.786s). Four large-font/picker checks
  pass (output6607eb, 0.425s), including Return choosing a version without recovery.
  Initial geometry-only test omitted UserRole; corrected fixture, not product
  leniency. Compileall/tool syntax/diff pass; no final whole-repository suite.
- d3-common/after-offscreen-r1 (exec57674, source ff3161cb) has 24 states at
  100%/900x640 and 150%/760x620, top/bottom positions. All named primary/cancel
  controls visible and requested window bounds retained; actual originals/drafts
  preserved and windows destroyed, no compilation or opening. Screenshots reviewed.
  Synthetic migration publishes a real independent copy: 20/21 output hashes match
  before, with manifest.json differing; no byte-identical-container claim. The
  final source only subsequently changes Tab order, not receipt source identities.
- Common-dialog inspection is now performed. Next measure E startup/scale/idle
  costs for bounded experiments; D embedded/full-size/native and F remain open.
  No repeated foreground retries, stable delivery/compile loops, commits, pushes,
  application packages, installations, releases or environment changes.

### 2026-09-13 — E2 desktop overhead evidence and F source regression

- Added isolated fresh-interpreter startup, single/multiple-window scaling,
  plain/observed idle CPU and window-retirement measurements. Five startup
  samples are medians, not cold-cache/native p95; 30 scale interactions per
  scenario preserve source/Block/formula drafts. No environment, GC or cache
  policy changes; resource detection was ephemeral/read-only, psutil not installed.
- e2/startup-before: imports median 211.73ms, theme 47.10ms, constructor191.59ms,
  first new document23.96ms. Offscreen stages do not establish native startup.
  e2/runtime-before: scale p50/p95 114.15/137.80ms for one source window and
  334.25/366.11ms for source+Block+formula. The provisional250ms multi-window
  goal is unmet. Plain8s idle uses0.0357CPU seconds; observer adds overhead.
  Five retirement cycles return to651Qt widgets; RSS movement is not leak proof.
- Separate cProfile attributes338.9ms of a344ms multi-window scale to Qt QSS
  application; text generation is cached. Probe-only freeze-updates experiment
  has multi-window median337.53ms, no improvement; not adopted in product.
  All samples and diagnostic limitations retained under e2/. No broad styling
  replacement or deferred first-use loading introduced without evidence.
- First required full suite (exec74441) ran1688 tests/343.061s, exited1 with6
  failures. f/full-r1.log explicitly notes an intermediate tool-output truncation;
  final failure details were captured. Five cases needed current UI/async test
  prerequisites, preserving action binding, focus, genuine overflow, welcome/
  document PDF states and actual file-notification invalidation.
- A real wide-split bug saved Qt's temporary narrow/minimum-constrained sizes
  as the user's ratio. Added deterministic480px-minimum red coverage. A pre-resize
  snapshot attempt remained order-sensitive and was removed. The final component
  retains declared defaults and updates preference only on handle movement;
  tests retain exact widths, selection, scroll, widget identity and one Undo.
  Source default790:650 and Block3:2 remain. Standalone test-module QApplication
  setup was also corrected; that harness abort is not a native product diagnosis.
- Current app d84a296085cd5b76851fbd120d4cfb33f5de5c0a78d69cdb73798f2eba6c95c6;
  app+tests ae014598108f722de61e4eb157aa23abd1d2ae1d8e09dbc967169dbb7ccc6338.
  After focused diagnosis/fixes, required full discovery passes1690 tests in
  324.050s, exit0 (exec37148). f/full-r2/unittest.log and result.json retain full
  output, command and identical before/after identities. Compileall, tool syntax
  and diff pass. Temp-directory background diagnostics and Qt PDF nullptr-connect
  warnings remain in the log; not a warning-free/native stability claim.
- Added the shortest explicit human input/OS/native checklist to the task record.
  D combined size/native matrix, multi-window budget and historical PDF/input
  anomalies remain open. Goal not complete. No foreground retry, Git mutation,
  package, installation, release, dependency upgrade or student-document edit.

### 2026-09-13 — F four-size matrix, formula access and stable split restoration

- Read-only foreground check still reported locked Mac; no native window launch.
  Extended the existing probe to four sizes/five scales with actual source/Block
  FINAL and frozen review. Before run stopped at formula125%/1080x720 growing to
  732px;150% cases reached790px. Fixed scrollable body and fixed main actions,
  keeping fonts, editor instances, draft/preedit/Undo and explicit application.
- Added editor-scoped physical Control+Tab/Control+Shift+Tab focus escape, reusing
  composition protection. Plain Tab/Shift+Tab retain math-slot behavior. Red
  focus trap then focused tests pass. An initially misplaced test cleanup caused
  NameError; restored original cleanup, not treated as an application defect.
- Visual review exposed3:2 being supplied as tiny pixel sizes. Convert preference
  to current pixel space. Reapplying every layout introduced421/430px viewport
  oscillation and long observation duration; removed it. Owner-bound single-shot
  restoration after returning wide preserves ratio and settles; height-only layout
  does not reapply. Related20 tests pass in4.629s, exact assertions retained.
- Corrected a PDF-observation false negative: stride2/threshold90 missed tiny
  antialiased text. BareQt6.11.1 in both page modes shows text; app image has131
  darker-gray pixels in its text region. Retracted sustained-blank claim; no
  rendering-mode/reload change. Full-pixel white-single-page helper has blank and
  sparse-gray controls,2 tests pass. Old reports/images retained with limits.
- f/dimensions-final-r5 (exec12527) passes83 states on app549f350e, requested bounds
  and named primary actions visible.100%/1440x900 source viewport615px; Block
  workspace648px versus approximately400px earlier. Actual FINAL, frozen PDF
  identity, draft/focus/Undo, indicator restoration, originals and window disposal
  pass. Target PDF keeps422x593/page1/scroll0,0 and131 ink pixels over four grabs.
  Offscreen evidence is not compositor timing or historical native-blank causality.
- Final app549f350e741c18d9a244624bfa4a3d21c841899bb517eaca746f11de03499e81;
  app+tests fc980aa942990719c9d472f75dc14de9501b66b1377660a55e0359bdbfc5b82e.
  Earlier full-r3 passed1692 tests on c620f3de. Current full-r4 passes1696 tests
  in354.783s, exit0 (exec11755), matching before/after identities and full raw
  receipt. Compileall/probe syntax/diff pass. Native/human acceptance, final
  performance budget and historical risks remain. No Git, package, install,
  dependency, release or student-document operations; all run handles terminal.

### 2026-09-13 — Frozen-source final performance verification and gate audit

- Application/tests unchanged from full-r4: app549f350e and app+tests fc980aa9
  (complete identities remain in PROJECT_STATE). Branch/HEAD unchanged, index
  empty. No new implementation, dependency, native-window, full-suite, delivery
  or large-image compile rerun in this verification turn.
- f/final-overhead/runtime.json (exec96819) has30 samples per scenario: single
  source scale p50/p95/max115.81/137.87/150.03ms; source+Block+formula
  342.37/351.00/360.73ms. The multi-window250ms target remains unmet. Draft/state
  preservation and disposal pass, no callback errors. One-second idle fragments
  are not compared to the earlier8s observations or used for energy claims.
- f/final-dependencies.json (exec32352) refreshes10/50/200-child fixtures30 times
  each in the original bounded measurement mode.200-child GUI dispatch p95
  0.214ms, commit p95/max0.490/0.497ms, timer lateness p951.079ms; worker p95
  83.661ms and capture-to-commit p9585.515ms. Worker time is not GUI blocking;
  forced refresh time excludes input debounce and does not prove live500ms
  convergence. Hidden offscreen window and paused synthetic watcher limitations
  remain explicit. Original bytes/cursor/scroll/authority and disposal pass.
- Added a requirement-level gate audit to PERFORMANCE_UI_PROGRESS. Current
  full1696 and83-state evidence remains valid; native/IME/OS-menu/VoiceOver,
  visual-state completeness, historical anomalies and multi-window budget are
  explicitly unaccepted. CUA again reported locked Mac; requested user confirmation
  of desktop/control availability, with no repeated foreground launch. Goal active,
  no completion claim or automatic Git/release action.

### 2026-09-13 — Goal blocked pending native-control recovery

- Third consecutive Goal-turn foreground inventory again returned locked Mac;
  cause unproven and no attempt to control the user's existing writer. Latest
  source identities, full-r4 exit0,83-state matrix, final performance receipts
  and disposed test windows were rechecked. No live test remains to poll.
- Goal status set to blocked, not complete, under the repeated-blocker rule.
  Resume after user confirms native control is usable. Current-source Cocoa,
  human IME/OS-menu/VoiceOver and other unaccepted rows remain open;351ms
  multi-window p95 is not relabelled as meeting250ms. Broader architecture or
  runtime changes require a separate decision. No repeated full tests, source
  edits, Git mutations, packaging, installation, publishing or memory updates.

### 2026-09-13 — Resumed foreground and bounded current-source Cocoa acceptance

- User restored foreground access; CUA inventory succeeded and Goal was active.
  Only newly created, uniquely titled synthetic Cocoa windows were operated.
  Application549f350e and app+tests fc980aa9 stayed unchanged; full-r4's1696
  regression was not rerun. No commits, pushes, packages, installs or releases.
- f/native-final-r1 retained62 source/frozen-review/formula states before a
  modeless-formula-close activity failure. f/formula-owner-diagnostic compared
  show/reject with the product's exec/cancel: only the latter restored editor
  focus. Corrected the probe lifecycle, not app code. f/native-block-r1 then
  covered only remaining Block dimensions/editing:22 states, exit0;83 distinct
  states across both receipts, not a claimed single uninterrupted pass. Actual
  FINAL, frozen PDF digest, draft/Undo and source viewport661px have evidence.
- f/native-submission-r1 passed12 current D1 Cocoa states. f/native-search-r1
  retained7 states and an immediate125%-narrow layout assertion. Diagnostic
  observed PDF width0 then1080 after event processing. Separating synchronous
  focus from asynchronous geometry completed125/150% in native-search-remaining;
  layout observations1.27–13.38ms,3 Chinese matches, keyboard return, original
  source/PDF preserved. This is synthetic input, not human IME acceptance.
- f/native-writing-200-r1 (exec46487 exit0):30 keys with live watcher and250ms
  interval, p50/p95/max8.825/29.494/74.756ms, one observation over50ms. Handler
  max2.487ms; slowest observation handler1.181ms, Paint entry3.481ms. Remaining
  observation time includes queue/grab costs; no causal closure of old79ms
  handler spike. Last key to current memberships415.477ms, bounded queues.
- f/native-flow-r1 retained a premature-pixel assertion before the first paint.
  r2 separated document readiness and actual ink:30 dual-root transitions with
  correct background-result ownership and preserved selection, document-ready
  p95/max2.876/3.064ms. Three pixel probes became nonzero after approximately
  140–233ms including scanning, not2.9ms final presentation. r2 later tried Stop
  before the QAction was enabled and remained failed. native-build-controls
  ran only the missing enabled-Stop/error/recovery segment: success→stopped→
  latex_error→success; stale PDF digest and restored original source verified.
- All owned windows disposed; callback error lists empty, existing IMK/font/AX
  limitations retained. Probe changes add activity prerequisites, Block-only and
  scale-selective scopes, proper modal lifecycle and measured geometry readiness.
  compileall and9 observer/pixel focused tests passed; detailed log is
  f/native-probe-checks.log. No app/tests changes or repeated full test run.
- Updated current task/state/roadmap/acceptance records to remove the obsolete
  foreground block. Goal remains incomplete:351ms multi-window scaling against
  250ms, input observation spike, full visual-state/human acceptance and historical
  native risks remain. Broader global-style/rendering work needs a separate
  decision; no runtime upgrade or renderer replacement is authorized.

### 2026-09-13 — Bounded input-observer diagnostic and remaining manual scope

- Rechecked the approved E scope and current UiScaleManager: unchanged-scale
  calls return early and identical QSS is not reapplied. Existing profile already
  places the scale cost in Qt's global stylesheet application, not generation;
  no newly proven duplicate call was found. No product/style architecture change.
- Added observer-entry, grab start/end and compare-end timestamps to the existing
  writing probe. Its caret-only negative/text-change positive focused test passed.
  f/native-writing-observer-split (exec12941) retained4 Cocoa samples, then stopped
  on lost activity/exposure and disposed its window. Exit1, no p95 and no inference
  about the earlier74.756ms spike. Did not reacquire foreground or restart the run.
  A future failure-context field now separates active/exposed state; no historical
  receipt was backfilled. Tool syntax check passed.
- Application549f350e and app+tests fc980aa9 remain unchanged. Refined the manual
  checklist to exclude already-recorded normal dimensions and automated root/
  cancellation scenarios, while keeping genuine IME/OS/VoiceOver and missing
  hover/focus/disabled/long-text/error visual states explicitly unaccepted.
  Goal remains active/incomplete pending the scope decision and remaining human
  acceptance. No full-suite repetition, user-document, Git or release mutation.

### 2026-09-13 — User-approved local style experiments, no product candidate retained

- User chose local optimization, not structural style-system changes. Tested
  two in-memory candidates in isolated offscreen processes,30 alternating-order
  pairs each across five scales with source/Block/formula drafts preserved.
  No application/tests/style file edits, full-suite repetition or native control.
- f/local-scale-order (exec54202 exit0): moving metric refresh after QSS produced
  median/p95 460.02/605.63ms against438.68/554.59ms baseline; no speed benefit.
  Its geometry snapshot used Python-wrapper ids, which are not stable Qt-object
  identities. Those differences cannot establish a product regression. Candidate
  was discarded without repeating an already-negative experiment.
- f/local-qss-dedup had a regex-escaping preparation failure before any samples;
  retained the empty failed receipt. r2 (exec72456 exit0) used exact block bounds
  and stable C++ addresses. Removing redundant toolbox Dock declarations gave
  median/p95 405.35/442.74ms versus412.89/452.83ms baseline. About1.8% median
  difference with large paired variability is not enough evidence to retain it.
  Visible widget geometry/fonts matched; six hidden tab-scroll controls differed
  at90%, so complete state equivalence was not claimed.
- All test windows disposed, callback error lists empty; app549f350e and
  app+tests fc980aa9 unchanged. Extra snapshot/reset conditions prohibit direct
  comparison with the prior351ms production-path receipt. Both candidates remain
  evidence only; no runtime, dependency, architecture, Git or release changes.
  Goal and remaining performance/human gates are unchanged, not complete.

### 2026-09-13 — Primary-control feedback, performance isolation and final local candidate

- f/control-states captured15 real-control Qt states plus5 long-text/empty/
  selected/pending/error panels, offscreen only. Two new regressions demonstrated
  identical normal/focused primary-action pixels, including the parent margin,
  and identical enabled/disabled formula-primary pixels. No compilation, delivery
  or student-document action occurred.
- The first state-only global-QSS candidate4a1d1047 passed two five-scale geometry/
  draft/pixel tests and f/full-r5:1698 tests/970.014s, exit0, unchanged app+tests
  ed8746c9. Full logs and a read-only CPU sample are retained. Independent30-sample
  runtime was slow: single median/p95254.02/739.04ms, multi835.08/1735.19ms.
  Correctness passing did not establish performance acceptance.
- f/control-style-isolation initially failed because of prototype escaping/label
  mistakes; its measurements are invalid for comparison. Validated r2 compared
  previous/current/narrow global rules in one process,30 rotating rounds:
  medians754.41/841.45/890.72ms, p951554.57/1630.48/1633.94ms. Old QSS also slowed,
  so this does not assign the entire change to the new rules.
- f/widget-local-feedback retained the old global QSS and applied state colors
  only to compile/formula primary widgets.30 pairs had old/local medians1036.19/
  964.03ms, but paired median local-minus-old+9.25ms,15/30 faster, and p95
  1305.81/1381.16ms. No speed gain is claimed. Local feedback and draft preservation
  passed; all experiment windows disposed, callback errors empty.
- Final candidate moves the feedback to local primary-widget styles and restores
  the original global QSS. Current appf9dd0936 and app+tests fcb71c45 have two
  five-scale focused tests passing, matching source/Block bindings, compileall,
  and f/control-states-local15+5 captures. The three normal control PNG digests
  match the original549f350e captures. No layout, transaction, runtime or global
  style-architecture change is made; general-button disabled styling is not widened.
- Final full-r6 is running in its existing exec22951, not passed or restarted.
  User confirmed the Mac is idle; wait for that regression to end before the next
  isolated timing measurement, including GUI-thread CPU versus wall time. Final
  performance and native/human gates remain open; no Git or release operation.

### 2026-09-13 — Final local candidate regression, idle CPU timing and Cocoa feedback

- Continued existing full-r6/exec22951 to terminal, without restart:1698 tests
  passed in492.806s, process496.114s, exit0; appf9dd0936 and app+tests fcb71c45
  unchanged. Previous candidate/earlier native receipts retain their own identities.
- Added GUI-thread/process CPU clocks beside the existing wall-time samples in
  bench_desktop_overhead; syntax and2 statistic-label tests passed. After user
  confirmed idle and the regression process ended, f/local-idle-cpu/exec49713
  recorded30 samples per scenario: single wall median/p95148.06/210.34ms,
  multi411.00/444.74ms; GUI CPU144.69/188.68ms and404.71/432.75ms. Wall-minus-GUI
  includes scheduling/waits/other-thread work and does not identify a causal source.
- f/primary-feedback-native/exec8676 retained five successful source scale states
  before a premature toolbar-widget assertion. The remaining-only exec53275
  observed Block enabled=true/visible=false before layout, then passed10 Block/
  formula records after readiness. Combined15 current Cocoa mode/scale records
  confirm visible focus, unchanged geometry and formula pressed/disabled feedback;
  original bytes unchanged, no compile/publication, all windows disposed. This
  does not claim physical keyboard, human IME or VoiceOver acceptance.
- f/idle-local-paired/exec43967 completed30 alternating-order old/local pairs in
  the same process and unchanged global QSS. Wall median402.78/400.78ms, p95
  416.84/413.20ms; GUI CPU median398.83/396.38ms, p95411.42/406.82ms. Paired wall
  median delta-1.25ms and20/30 faster is small, not a meaningful speedup claim.
  The local531.56ms wall maximum remains in the raw data. No broad CPU-cost
  increase is shown by this bounded comparison; the250ms target is still unmet.
- Final local feedback remains scoped to primary controls, with normal PNGs
  matching original captures and full/changed-native checks passed. Goal remains
  incomplete for performance and other unaccepted gates. No app/tests changes in
  this verification turn, no Git mutations, packages, installs or publication.

### 2026-09-13 — Goal blocked pending the structural-style decision

- Three consecutive Goal turns retained the same unresolved scope decision after
  local implementation, verification and handoff. No new structural-style authority
  was supplied; the confirmed idle desktop is not authority for architecture work.
- Rechecked authoritative cwd/root, branch codex/v1-development and HEAD3bde2b5,
  empty index, appf9dd0936/app+tests fcb71c45, full-r6 pass/exit0/unchanged identity,
  and terminal native/idle-paired receipts with disposed windows. No test remains
  running and no stable suite was restarted.
- Marked Goal blocked, not complete, preserving the full objective and unmet
  multi-window250ms, human and historical boundaries. Resume only after the user
  supplies the next scope decision; no implicit architecture, Git or release action.

### 2026-09-13 — Authorized minimum structural scale path implemented

- User authorized structural adjustment with minimum implementation and prompt
  delivery. Reused the existing QSS generator, UiMetrics, widget instances and
  menu tiers. Relative-unit feasibility did not update with the app font, so that
  route was discarded. Fixed-rule prototype r2 preserved visible fonts/geometry
  at all five tiers using property updates, parent-first polish and StyleChange.
- Production changes are confined to the three existing theme files, plus scale/
  lifecycle tests. The fixed stylesheet adds only generated size deltas; no second
  handwritten metric map, dependency, layout engine, widget cache or service.
  New widgets receive the current marker at Polish; non-menu values keep legacy
  full-QSS behavior. D022 records the authorized decision and boundaries.
- structural/runtime-after has30 samples per scenario: single wall median/p95
  35.85/43.00ms, multi95.12/101.36ms, multi GUI CPU p9598.50ms. Prior same-recipe
  idle p95 was210.34/444.74ms; this is the bounded UI scale benchmark, not TeX or
  compositor latency. Draft/disposal checks pass and callback errors are empty.
- structural/dimensions-after passed83 four-size/five-scale offscreen states,
  actual source/Block FINAL, fixed PDF identity, original bytes and draft/Undo.
  First full1701 failed only the old mandatory-setStyleSheet test assumption.
  Observing the actual style dispatch preserves every GC/liveness/release assertion;
  14 focused checks pass. Final structural/full-r2 passed1701 tests in279.652s,
  exit0, with unchanged appa66b445d and app+tests57c526c8. Runtime/matrix receipts
  retain c3f06d3b identity; only a module description and test observer changed later.
- Five new-interpreter startup samples: theme median60.93ms, window construction
  196.63ms, first new document26.24ms. No startup p95 or native cold-start claim.
  compileall and diff checks pass. All background run handles are terminal.
- CUA inventory reported locked Mac; requested user restoration and did not raise
  a native test window. Structural native/input acceptance remains pending; Goal
  stays active/incomplete. No Git, packaging, install, runtime or release operation.

### 2026-09-13 — Structural result retained, Goal blocked on native access

- Third consecutive resumed Goal-turn CUA inventory still reported locked Mac.
  No native test window was launched and no automatic unlock or repeated backend
  verification was attempted.
- Rechecked authoritative root, appa66b445d/app+tests57c526c8 and full-r2 pass/
  exit0/unchanged identity. Runtime and window-disposal receipts are terminal;
  no live test remains to wait on. The101ms multi-window result is retained as
  offscreen evidence, not promoted to native/input acceptance.
- Goal marked blocked, not complete, preserving the full objective. Resume after
  foreground access is restored, then run only the missing structural native/
  new-window/input acceptance. No Git, packaging, installation or release action.

### 2026-09-13 — Structural Cocoa coverage restored; input tail retained

- User restored foreground access. Source remains appa66b445d/app+tests57c526c8;
  no product changes or repeat of the1701-test/full offscreen runs. Used only
  isolated, uniquely titled native synthetic windows, not the existing writer.
- structural/native-final-r1 built source FINAL successfully, then the application
  became inactive while the window remained exposed; the probe stopped before
  layout/key operations and disposed its window. Preserved the first failure.
  Added optional process-name-only deactivation diagnostics to the layout probe,
  without reactivation or assertion changes. native-layout-diagnostic completed
  all83 states, source/Block FINAL, fixed PDF identity, draft/Undo and original
  protection. No repeat ApplicationInactive event occurred; cause remains open.
- structural/native-search passed10 scale/size states with three Chinese matches,
  composition/Tab/Esc/focus, unchanged source/PDF and disposed window. This is
  synthetic Qt input, not human IME or full OS accessibility acceptance.
- structural/native-writing-200 recorded30 inputs with live200-child watcher:
  p50/p95/max9.346/56.002/93.281ms,2 above50ms, handler max3.077ms, last-key to
  current members457.652ms. The input target is not passed.
- One bounded wait-loop wall/GUI-CPU diagnostic recorded p95/max24.674/69.582ms,
  still one tail above50ms; it does not replace the initial failed target. In the
  slowest sample, event pumping took63.85ms wall versus6.07ms GUI CPU; this does
  not identify GIL, OS scheduling or native waiting as the cause. Current-member
  convergence was509.815ms. All test windows were destroyed and hashes unchanged.
- Inspected actual source,150% formula and Block/PDF captures. Current-source
  native matrix/search evidence is preserved separately from historical evidence;
  IMK/font/AX warnings, initial deactivation and prior native failures remain open.
  Updated current state/roadmap/acceptance; no commit, push, packaging or release.

### 2026-09-13 — Input event-loop hypothesis rejected without product changes

- Previous turn made progress through current-source native coverage and input
  wait/CPU separation. Revalidated authoritative root and appa66b445d/tests57c526c8.
  No source, runtime, dependencies, tests or user documents changed in this turn.
- An isolated QEventLoop waiter retained original deadlines/pixel predicates and
  passed immediate/timer/timeout/exception self-checks with manual sleep forbidden.
  native-input-event-loop recorded30 inputs p95/max12.975/17.938ms,0 above50ms.
  This single result was not promoted to a fix.
- One same-window AB/BA comparison, native-input-wait-paired, used30 inputs per
  method: manual p95/max18.699/86.891ms, Qt74.063/76.138ms. Qt-minus-manual paired
  median was-0.937ms,22 of30 pairs faster; both methods retained tails. Rejected
  the explanation that manual sleep alone caused the failures; kept production
  and the canonical benchmark unchanged. Mixed60-input summary is not presented
  as a single-method benchmark. Source identity, bounded queues and disposal pass.
- After tests had ended, read-only top/vm_stat showed variable desktop CPU load
  and compression activity. Recorded exact boundaries in structural/environment-
  after-input.md; these snapshots do not identify the cause of earlier spikes.
  No other application, VM or system setting was changed. Avoid further repeated
  measurements until a stable-load window is coordinated; input/human/historical
  gates remain open and Goal is active, not complete. No Git or release actions.

### 2026-09-13 — Goal blocked pending coordinated input acceptance window

- The stable-load foreground acceptance-window request remained unanswered for
  three consecutive Goal turns. Previous turn was a no-progress state check,
  not a verified wait on running work. No new authorization or test condition
  was inferred from an automatic continuation.
- Rechecked authoritative cwd/root, appa66b445d/app+tests57c526c8, full-r2 pass/
  exit0/unchanged source, paired-probe completion/disposal and no matching live
  native probe processes. No source change or repeated test was performed.
- Marked Goal blocked, not complete, preserving the full objective, all retained
  results and unmet input/human/historical gates. This is not a new locked-screen
  claim; earlier host-load snapshots are not proof of the current load. Resume
  after coordinating the requested acceptance window. No Git or release action.

### 2026-09-13 — Confirmed input window measured; current handoff compacted

- User confirmed the requested short acceptance window. Revalidated root/branch/
  HEAD and appa66b445d/app+tests57c526c8, then ran only the canonical200-child,
  live-watcher,250ms-interval,30-input Cocoa probe in a fresh output directory.
  native-input-confirmed-window passed its data/lifecycle assertions, exit0:
  p50/p95/max8.728/43.290/91.936ms, one sample above50ms, handler max5.135ms.
  The slowest sample's handler was1.423ms, Paint event86.797ms and observation
  completion91.936ms. This run meets the p95 target, not a root-cause resolution
  of tails, a CPU-only diagnosis or an overwrite of prior failed runs.
- Final membership convergence396.988ms, one accepted commit4.594ms, bounded
  queues, unchanged source files and disposed window. No compile, source change,
  repeat full/layout suite, other-window control, VM operation or system change.
  Pre-run1-second top sample recorded66.10% overall idle and WindowServer45.1%
  of one core; background activity/swap-ins remained. User confirmation is not
  proof of a perfectly idle machine or causality for the delayed sample.
- Goal resumed active; the requested window has been used and is no longer a
  blocker. Do not repeatedly request the same confirmation or run identical
  samples. Tail diagnosis requires new execution-position evidence; historical
  native and human-only acceptance remain open.
- Compacted the task's947-line current progress entry to101 lines, preserving
  the exact original in the local evidence root as progress-history-before-
  confirmed-window.md. Both copies had SHA256d58a5bc95020b6773b7d4a2dfb0df02e308aa3603f03979cdd389a279271c475
  before replacement. Historical log entries and failures were not changed.
  Updated state/roadmap/acceptance/navigation; app/tests remain unchanged and
  their existing1701-test receipt remains valid. No Git or release actions.

### 2026-09-13 — Default-scale no-op event filter removed with bounded evidence

- Added a probe-only QApplication.notify/wall/GUI-CPU diagnostic. Its self-check
  located an intentional User event wait without recording text. Native profile
  retained two slow inputs: MainWindow UpdateRequest about71ms wall/6–7ms GUI CPU,
  with repeated5–6ms low-CPU Paint waits. Notify instrumentation adds overhead;
  this is execution-position evidence, not acceptance p95 or proof of GIL cause.
- At100%, UiScaleManager's global event filter did no work but received all events.
  Offscreen same-window30-pair controlled-Python-contention isolation had filter
  on/off redraw p9521.164/8.763ms, paired median-0.689ms,21 of30 disabled faster.
  A new regression first failed because100% still received the User event.
- Production change is limited to theme/ui_scale_manager.py: no filter at startup
  100%; scale transitions remove it, reinstalling only for non-default supported
  tiers that require new-widget markers. Legacy styles, Polish behavior, fonts,
  QSS rules, widget retention and GC/threads are unchanged. One added scale test
  covers100%,125%,100%,117%,150%,100% filter dispatch. All13 scale tests passed.
- compileall passed. Full required discovery passed1702 tests in305.349s; wrapper
  elapsed307.331s, exit0, unchanged appcddab32e/app+tests05a1e070. Existing Qt and
  synthetic-cleanup warnings remain. No full/layout suite was restarted unchanged.
- Standalone current-source native input retained p95/max104.527/116.001ms and
  three of30 above50ms. Do not hide that failure. Once full testing was terminal,
  one same-window native AB/BA control used30 cases per filter state: enabled
  p95/max16.727/72.925ms, disabled11.935/12.706ms; paired median-0.768ms,22 of30
  disabled faster. Retain the small no-op reduction, not a cure for all tails.
  Mixed60-case totals are not a product baseline. Originals/queues/disposal/hash
  checks passed; last-key membership432.421ms in the paired run.
- One standalone handler sample spent44ms in _mark_source_edited; its code path
  contains path resolution, but no trace yet identifies which nested call waited.
  No speculative path-identity change was made. Current short handoff/state/
  roadmap/acceptance updated, original receipts kept. No Git or release actions.

### 2026-09-13 — Source path identity increment and bounded handoff

- GUI-only spans located35.714ms wall/0.207ms CPU in main-window path
  normalization during one61.668ms offscreen key handler. Initial cProfile
  attempt mixed background functions, produced inconsistent cumulative timing
  and failed after28 recorded cases; retained, but not used for GUI attribution.
- Removed repeated tab.path resolution from _mark_source_edited while retaining
  state-store normalization and FINAL/save checks. Regression verifies the
  established path reaches two distinct dependency owners even after replacing
  the child with a symlink. The first test fixture accidentally reused one root;
  corrected the fixture and added a distinct-root assertion before accepting it.
- First1704-test full run failed deep-child dirty propagation through a legacy
  tab-registration entry. Fixed normalization once in _add_tab, preserving the
  old assertion. A save-alias test then established canonical post-save tab/
  local-content keys while keeping the actual atomic-write path unchanged.
  Focused sets54,52,87 and final4 boundary checks passed at their respective
  stages. The removed GUI normalization call was0 in the after trace, but a
  state-store normalization still waited56.035ms; no full latency cure claimed.
- Final app3897ec74/tests7d4d3fc6 ran1705 tests in353.816s, wrapper355.756s,
  exit1, identities unchanged. Only feedback metadata's old macOS /var alias
  expectation failed. Changed that expectation to chapter.resolve(), retaining
  every other metadata assertion; the single test passed in0.504s. Current app
  remains3897ec74; app+tests is32fcb913. No repeat full run or new native test
  was started after this test-only correction. Original failed receipts remain.
- User objected to two days elapsed. Collected the existing live run and handed
  off source/evidence/limitations without more experiments. No unknown item is
  marked passed and Goal is not marked complete. Latest native path validation,
  input tails, historical native failures and human IME/menu/VoiceOver remain
  open. All task test processes are terminal; no Git or release actions.

### 2026-09-13 — User-authorized local Beta2 installation for acceptance

- User explicitly requested updating the Mac's installed ICSTeX to current source
  for their own acceptance. This added local build/backup/install/start authority,
  not Git synchronization, public updater activation or release publication.
- Existing /Applications/ICSTeX.app was Beta1, arm64/ad-hoc; both Info.plist and
  embedded app code confirmed2.1.0-beta.1. No installed-app process was running.
  Preserved the old executable hash718e263c... and plist75a1d478... before changes.
- Ran the required packaging/preflight.sh with offscreen Qt: all1705 tests passed
  in311.320s, command exit0. App3897ec74/tests32fcb913 unchanged before/after.
  Terminal middle output was truncated; this is an observed result, not a claim
  to have archived its full console stream. Prior failed receipts remain intact.
- Built the existing packaging/ICSTeX.spec using installed PyInstaller6.21.0/
  Python3.12.6/PySide6.11.1 in a fresh version/source-tagged local evidence directory.
  Did not run dependency upgrades or touch existing dist/DMG aliases. Explicitly
  omitted ICSTEX_UPDATE_RUNTIME; no public update framework/feed was activated.
- New arm64/ad-hoc bundle passed deep strict verification. Compared all201
  embedded application modules against current-source compilation: zero mismatches
  and no required module missing. Runtime asset diff matched except .DS_Store.
- Staged and verified the new app, rechecked no installed-app process, moved Beta1
  to /Users/leo.xu/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.1-20260913.app,
  then installed Beta2 at /Applications/ICSTeX.app. Old program/plist hashes and
  signature remain valid. Installed program exactly matches the fresh build:
  executable25207f46acb86fd609d6f5db7f0f47a6788035df999c7f0d3cdac1ae5af87d65,
  plist4836e24f0860aa462e571d58469d5628d07355270d2730b17bc6d788c109d3e6.
- Launched the installed path; PID23314 and native welcome/latexmk-ready AX state
  observed. No document was opened or edited. Screenshot API was unavailable for
  the full path, and bundle-ID lookup was ambiguous among retained builds; no
  screenshot/whole-workflow acceptance claim. Cancelled the inspection menu and
  left the main window ready for the user. Local receipt is under
  local-install-2.1.0-beta.2-3897ec74/source-receipt.json in the task evidence root.
  Build/test processes ended; the installed user app remains running. User
  acceptance, historical risks and latency limitations remain open.

### 2026-09-13 — Goal blocked awaiting the user's acceptance feedback

- Local installation/handoff was completed and the user explicitly took ownership
  of acceptance. Three consecutive Goal turns reached that same pending-feedback
  gate; no new acceptance result was supplied. Last turn was a read-only state
  check, not a wait on a running test job.
- Reverified authoritative root, local Beta2 receipt/preflight pass and installed
  executable25207f46... matching the delivered build. Did not inspect the user's
  current UI, restart testing, change source or touch the running application.
- Marked Goal blocked, not complete, preserving its original objective and all
  open acceptance/risk items. Resume only for user feedback or explicit direction.

### 2026-09-14 — Real EE automatic compile latency fix and local installation

- User prioritized edit-event-to-current-PDF latency and supplied the Physics EE
  root for read-only access and isolated-copy measurements. Original root SHA256
  ab4179b6569ca117f9197d0e31d451c7c5f4ac48cb9f4dd0c29084432858b750 was preserved.
- Removed the extra forced membership job for ready automatic PREVIEW; registered
  successful atomic-save bytes immediately to prevent own-save external echoes
  from replacing immediate preview with another debounce. Background Word Count
  yields during automatic save/queued/active compile and initial PDF presentation;
  explicit count remains available. Focused save/queue/ownership regressions passed.
- Ordinary XeLaTeX preview uses level-1 lossless PDF compression. FINAL, other
  engines, restricted compilation, source/asset content and build guards remain
  unchanged. Fixed-XDV alternating probe: median3226.564→945.754ms; all26 pages
  rendered identically at72dpi, temporaryPDF about6.36% larger.
- Same-copy offscreen complete latency, five warm samples per version:
  median9962.086→7034.751ms, down29.385%; max10386.582→7995.616ms. Earlier candidate
  medians12001.230 and9405.563 remain in their original receipts. Native current-source
  warm confirmation:7671.768/6743.804/7282.913ms. First preview remains about12s.
  Current build/revision/new-color pixels,26 pages, count settlement and window
  disposal were asserted. Not compositor timing or a native before/after comparison.
- Final app8dd861b0/tests b0c61873 passed packaging preflight:1710 tests in638.177s,
  command642.471s, exit0, source hashes unchanged. Full log and receipts retained
  in auto-compile-20260914/preflight. No suite or performance rerun during installation.
- Built the existing PyInstaller spec in fresh version/source-tagged paths without
  upgrades or public update runtime. All201 source modules, entrypoint and assets
  matched; arm64/ad-hoc bundle passed deep/strict signature validation.
- First installation paused when UI control reported a locked Mac and the old app
  remained running. On the user's explicit continuation, verified old process gone;
  moved the old app to ICSTeX-2.1.0-beta.2-before-auto-latency-20260914.app under the
  existing ICSTeX Backups folder and installed the verified staged bundle.
  Old executable25207f46... remained intact; new executableb2757de2... matches build.
  Both signatures passed. /Applications startupPID42486 and native welcome/latexmk
  ready state were confirmed. No manuscript opened, no Git commit/push or release.
- Full installation receipt: local-install-2.1.0-beta.2-8dd861b0/source-receipt.json
  under the task evidence root. Local fix handed off for user acceptance; historical
  V1/native risks remain open, not marked complete by these results.

### 2026-09-14 — Preview marginal-gain check, then C/F welcome UI corrections

- User confirmed performance recovered, then requested more fast-preview efficiency
  until marginal gains became small, followed by the approved Goal UI plan.
  Applied the minimum-change workflow; no broad search framework, subagents or
  new compiler/runtime architecture. Did not modify the shared held-release brief.
- On unchanged8dd861b0 source, one instrumented warm EE-copy sample was3042.505ms;
  preview preparation32.629ms, static check108.969ms, PDFload7.841ms. This diagnostic
  is not a new improvement over the earlier7.03s measurement on another time window.
- Fixed-XDV1/0,0/1,1/0 lossless-compression comparison: medians456.775/360.967ms;
  only95.808ms saved while temporaryPDF grew7.35→12.53MB, about71%. All26 rendered
  pages matched. Rejected the option; no additional production compiler change.
- Proceeded with C/F UI gaps. Restored writing-toolbox visibility no longer crowds
  a projectless welcome page, while explicit toolbox/folder navigation and saved
  writing preferences survive welcome restart. Window state captures the actual
  writing preference, not the temporary presentation collapse.
- Welcome layout reflow previously left stretch on empty grid columns and
  reparented buttons. Removed both causes: narrow rows use their available width
  and preserve the current button focus. Reused existing local primary-button
  state rules for visible focus/pressed/disabled feedback without globalQSS changes.
- Red assertions reproduced all three UI gaps. Related72 tests passed in10.829s;
  Cocoa3 targeted tests passed in3.415s, covering five scales/two sizes, preference
  restoration and focus retention. Preserved the IMKCFRunLoopWakeUpReliable warning;
  programmaticQt focus is not humanIME/menu/VoiceOver acceptance.
- Final source44f1fdc4/tests7bc30f48: compileall passed; all1714 unittest tests passed
  in273.836s, process275.277s, exit0; both source identities unchanged. Full log and
  receipt under preview-next-20260914/full. Offscreen before/after and native images
  retained under ui-before/ui-final/ui-native; diagnostic and rejected comparison
  under phase-profile/compression-zero. No old performance-matrix rerun.
- Compared installed embedded app code with repository sources: only six GUI
  modules differ, allcore code remains identical. Installed8dd861b0 performance
  build, student originals and unrelated shared changes retained. No packaging,
  installation, commit, push or release in this follow-up. Broader Goal F/human
  and historical stability boundaries remain open.

### 2026-09-14 — C/D primary-action state consistency, native focus held on locked Mac

- Continued the approved UI plan rather than another compiler experiment. Audited
  fourteen existing component families: submission check/delivery, checkpoint,
  recovery/migration/interrupted-write recovery, Block, references/history/images,
  templates/table insertion, diagnostics and environment report.
- Actual component rendering reproduced missing focus feedback everywhere and
  indistinguishable pressed/disabled states in multiple families. Focus ownership
  was checked separately; enabled states were explicitly simulated for appearance
  only, with zero clicked signals, unchanged synthetic source and no compilation,
  restore, publication, insertion or clipboard action executed.
- Bound existing local primary-button state rules at every primaryButton entry.
  Added a deeper warm-brown pressed token to distinguish hover+pressed from hover
  for both QPushButton and toolbar QToolButton primary roles. No globalQSS rules,
  size/font changes, action connections or enabling/confirmation logic changed.
  Global stylesheet function bytecode/constants still match the installed version
  after normalizing source line metadata; its first line moved171→174 only.
- Fourteen families×five scales,70 offscreen state sets passed. Ordinary pixels at
  the common100% scale match the pre-change controls; geometry retained and no
  business click emitted. Related117 workflow tests passed in28.185s; final15
  rendering/theme tests passed in4.878s, including hover+pressed and existing
  formula/welcome draft/geometry guards.
- Native attempt retained all70 unfocused rows. The foreground inventory then
  explicitly reported a locked Mac. Did not auto-unlock, seize input or call this
  native acceptance. Added active/exposed preconditions to the test so the next
  run stops at missing foreground readiness. User was asked once to unlock;
  current native focus, humanIME/menu/VoiceOver and historical risks remain open.
- Final app614f6a68/tests5dcfda77: compileall and required full discovery passed,
  all1716 tests in265.571s; process266.966s, exit0, both source hashes unchanged.
  Evidence and retained failures: task-button-states-20260914/{before,
  remaining-before,all-after,final,native,full} under the task evidence root.
- No compiler-core, student-document, installed-application, dependency, Git or
  release mutation. This Goal turn made concrete progress; full completion is not
  claimed while native/manual acceptance is missing.

### 2026-09-14 — Goal blocked after three confirmed locked-desktop turns

- The primary-action UI implementation turn and two subsequent Goal turns each
  received a fresh native-control report that the Mac was locked. This is the
  current resumed-run audit, not reuse of an older blocked condition.
- Required full regression had already exited0; rechecked its receipt against
  app614f6a68/tests5dcfda77. Source remains unchanged, and no test was restarted.
  Remaining native focus and human acceptance cannot be replaced by the passing
  offscreen rendering results or a capture from an inactive/locked desktop.
- Marked the existing Goal blocked, not complete, preserving the full objective
  and open acceptance boundaries. Resume after manual unlock/user direction;
  only fill missing native/manual evidence. No application source, installation,
  runtime, Git or publication change in the blocked audit.

### 2026-09-14 — Foreground restored, native buttons confirmed, human fixture prepared

- User explicitly continued. Native-control inventory now reported available apps
  instead of the prior lock error; source still matches the1716-test passed receipt.
- Reused the existing Cocoa test entry with active/exposed prerequisites and a new
  native-unlocked output directory. Two checks passed in6.205s, exit0. Independently
  read all70 rows: active windows, owned focus, distinct feedback, retained geometry,
  zero clicked actions and matching app614f6a68. Kept the original locked capture and
  the IMKCFRunLoopWakeUpReliable warning. No full-suite or performance rerun.
- Started a source-runtime human-acceptance window from an isolated evidence-local
  script: manual_acceptance.py; PID47352, terminal session96673. Own QSettings and
  manual-test.tex, automatic compile disabled, no student manuscript. Native AX
  confirmed the exact manual-test title/file, manual mode and editor focus.
  Positioned the cursor in the empty test comment using the selected owned window;
  text remained unchanged. The user must perform IME/keyboard steps before they
  can be marked accepted. This live interactive app is not an autonomous test job.
- Original lock condition is resolved for this resumed attempt; broader Goal and
  human/historical acceptance remain incomplete. No app-source, installed bundle,
  original manuscript, Git, packaging or release mutation.

### 2026-09-14 — Agent-operated Unicode/undo/formula checks, IME channel limit retained

- User explicitly rejected being asked to perform tests and then confirmed unlock.
  Reused the owned agent-ime fixture/observer; no application or test source change.
  Native GUI paste of中文测试🙂 was verified in editor and saved bytes. Undo restored
  the exact baseline; redo restored exactly one copy, with UTF-16 cursor173→179→173→179.
- Selected the complete formula after the non-BMP prefix through native UI, opened
  Edit Formula, and changed only its source-mode draft to a Chinese/emoji expression.
  Native AX independently confirmed exact draft text. Parent source/disk remained
  unchanged; Escape canceled the dialog and restored source focus/selection without
  formula or package insertion. Final cleanup restored initial fixture bytes.
- Actual Pinyin composition was not established: CUA pressKey/typeText submitted
  Latin letters and the observer captured no QInputMethodEvent. A fresh Apple
  TextEdit native-control comparison likewise retainedzhongwen afterEscape. This
  bounds the observed tool/OS route, not a root-cause finding against ICSTeX.
  Ctrl+F2 menu entry also lacked positive evidence. Do not reclassify paste as IME.
- Paste-tool read-detection timeouts were reconciled against actual UI/state/files
  before further action; each paste happened once. Modifier-onlyShift was unsupported.
  Helper-app probes failed; no input-source configurations were changed. Selected
  input source before/after remainedSCIM.ITABC; paired temporary toggles restored it.
- TextEdit unexpectedly auto-saved its synthetic8-letter control in the default
  iCloud-backed directory. Moved the new document through File/Move to localagent-ime;
  verified local presence and old-path absence, then quit. No manuscript content was
  involved; cloud sync/history was not inspected and is not claimed absent.
- Closed the QA process normally (61641, terminal42291, exit0), and quit the two
  agent-opened helper apps. Source remainsapp614f6a68/tests5dcfda77, matching prior
  passed1716-test receipt. No rerun/full build/install/Git/release activity.
  Evidence: task-button-states-20260914/agent-ime/result.json and01–06 snapshots.

### 2026-09-14 — User-scoped items 1/2/5 and local Mac update

- User explicitly deferred IME-candidate, keyboard-menu and VoiceOver acceptance.
  Kept changes to registered-root state lookup, 500ms idle batching of membership/
  Word Count, and PDF reload search-count presentation; no runtime/renderer upgrade.
- Native 200-child, 30-key, 250ms-interval before/after p95 50.757→13.483ms,
  max52.936→14.366ms, over50ms 3→0; p50 7.008→12.207ms did not improve.
  State path resolutions per key5→0, membership completions28→1; last-key settlement
  374.184→729.679ms. Interrupted native runs and the insufficient lookup-only
  candidate remain in closeout-125-20260914. Final PDF-count delta does not touch
  that measured no-PDF input path; identities are explicitly separated.
- Native PDF initial/reuse/new-bytes/switch-root, six search-clear-reloads, pending
  search disposal pass. Fixed stale displayed count without auto-jumping on reload.
  Old search crash matches the already-fixed deliberately deleted-document fixture;
  historical A blank PDF lacks its original artifact/exposure evidence and is not
  claimed causally fixed. No unlimited retries or blanket Qt-stability promise.
- Physics EE frozen-copy automatic preview: first5.476s/warm3.015s,26pages and new
  revision/color pixels, saved bytes, settled count and disposal pass offscreen.
  Concurrent single-round functional check, not a new speedup ratio. Original EE
  hash remainsab4179b6; original EA was only reopened after installation.
- Final appd8292f5b/testsc52f6ca0: compileall and one preflight pass1722 tests in
  278.153s (process279.726s), exit0, matching identities; raw warnings preserved.
- Fresh local Beta2 built with existing spec/dependencies. Actual201 app modules+
  entry and36 assets match; old/new module sets equal. Arm64/ad-hoc deep/strict
  verification passes; no updater runtime/public distribution. Installed executable
  6a8843ffae83540119ebdcf415f8cab97766c357e518589159867e7b3ddcc267.
- Confirmed existing EA saved/idle, quit normally, backed up8dd bundle intact to
  /Users/leo.xu/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.2-before-125-d8292f5b-20260914.app.
  Installed/started /Applications/ICSTeX.app (PID66126), observed welcome/latexmk,
  reopened the same EA file and observed saved/idle. No force kill, source save,
  original-project compile, Git commit/push, VM or public release.
- Receipts: closeout-125-20260914/preflight, installed-receipt.json, installation.md;
  detailed boundaries in docs/PERFORMANCE_UI_PROGRESS.md. Items1/5 delivered;
  item2 current paths verified but historical causality remains unproven. Goal not
  relabelled fully complete; stopped repeating completed checks.

### 2026-09-14 — Reproduced PDF pending-render failure and local fix delivery

- User requested completion of item2. Traced matching Qt6.11.1 source: a queued
  render dropped against a closed document remains pending and suppresses future
  equal-size requests; view page-cache results have no document generation guard.
  Deterministic old-code clear/reopen test produced a blank viewport, new-code test
  displays the expected blue marker. Preserved PDFs/red/green images. A delayed
  old-image completion also fails with isolation disabled and passes with it enabled.
- Keep panel/document/search/toolbar stable; replace only QPdfView and its native
  render queue for changed content. Verified identical content retains its existing
  viewer/cache. Rewire page/focus/observer connections and preserve same-root view state.
  Parent the document last to PdfPanel so search/render consumers die first.
- Rejected document-as-view-child candidate: Qt view private state was already
  freed when its child document emitted close signals. Preserved111204/111300.ips.
  Initial probe-stub missing-viewChanged/partial-filter failure is recorded in
  Python-2026-09-14-110838.ips; fixture contract/initialization fixed, not hidden.
- Final33 focused tests pass/8.588s. Native final lifecycle passes initial/reuse/
  new bytes/cross-root/six search-clear-reloads and pending-search close; interrupted
  native-owned run remains failed. EE frozen-copy actual auto-preview first5.493s,
  warm3.086s,26pages/current-revision pixels/save/count/close pass; no speedup claim.
- Final app7478cba7/test4ff9e4b7 preflight passes1725 tests/289.494s, process291.267s,
  exit0, compileall and source identities match. Qt/temporary-directory warnings remain.
  Old A incident lacked its PDF/exposure state; its exact historical sequence is
  not retrospectively claimed proven. Current reproduced defects are fixed.
- Fresh Beta2 local package verified201 modules+entry/36assets, same archive module
  set and explicit13 existing exclusions; arm64/ad-hoc deep/strict signatures pass.
  Installed executabled79a85f84f1c7b0dd2a30185e335d35a84e61fa81289259b8077cd2d07ff6a1b.
  Complete d829 backup preserved at ICSTeX Backups/ICSTeX-2.1.0-beta.2-before-pdf-7478cba7-20260914.app.
  Saved/idle EA quit normally, new /Applications/ICSTeX.app launchedPID68965;
  native welcome/latexmk and reopened EA saved-state screenshot observed. Picker
  AX timeouts did not trigger duplicate Open; original EA hash a24d90cd unchanged.
- No original-paper save/compile, dependency upgrade, Git commit/push, public release,
  or unrelated UI/IME/VoiceOver matrix. Details in the PDF lifecycle verification doc;
  raw receipts under pdf-root-cause-20260914, including preflight-final and installed-receipt.

### 2026-09-14 — Six writing-UI pain points implemented; local install awaits OS folder consent

- Kept existing Qt controls/palette and compiler actions. Empty PDF uses a narrow
  actionable side area; valid PDF restores the reading split. Source toolbar and
  project context share a row, PDF header/success text duplication removed,
  common actions have short labels, custom auto switch scales with the UI,
  comments are upright, and the console fully hides behind a readable footer toggle.
- Four new tests preserve source/cursor/top reading line, split preferences,
  compiler-action delegation, console content/expansion preference and five-scale
  button sizing.62 related tests and29 existing workbench tests passed.
  Native final four states passed with real synthetic PDF pixels and owned-window
  disposal; no student content or compiler invocation in the UI screenshot fixture.
- Final appcf281f47/tests2bb0f8d8 preflight passes1729 tests/291.148s,
  process292.798s, exit0 and identical source hashes. First full run failed only
  the old360px empty-PDF width expectation; replaced it with narrow-area action/
  overlap checks, retained original black-toolbar/window bounds assertions, and
  reran the focused case then final required preflight. No app delta between them.
- Existing89 packaged core modules equal the prior installation. Frozen Physics EE
  auto-preview first5.590s/warm3.073s,26pages/new revision pixels/save/count/disposal
  passed offscreen. Single functional check, not a new speedup comparison.
- Built a fresh Beta2 with existing dependencies/spec.201 app modules+entry and36
  assets match; old/new archive module set equal,13 existing exclusions explicit.
  Arm64/ad-hoc installed/backup signatures pass. Installed executable:
  776d175eb8a3e53c3a957ece0cc6cd8c6438d5659dcaded07d5d553cb9a9aea6.
  Complete prior7478 bundle retained as
  ICSTeX Backups/ICSTeX-2.1.0-beta.2-before-writing-ui-cf281f47-20260914.app.
- Confirmed EA saved/idle, quit normally, replaced and launched the new bundle
  (PID6984). Welcome and new labeled toolbar observed. Reopening EA blocked at
  openat; tccd explicitly reports changed code identity and pending DesktopFolder
  authorization. AX and screenshot timeouts are not recorded as successful reopen.
  UserNotificationCenter access was denied by the computer-use tool; no alternate
  permission route, database edit, force kill or full-disk access request attempted.
  Await user manual consent, then inspect the final UI only. EA bytes remaina24d90cd.
- Evidence: ui-painpoints-20260914/preflight-final, native-final, real-auto,
  installed-receipt.json and installed-process-sample.txt; design record in
  docs/writing-ui-refinement-2026-09-14.md. No source-paper edit, Git commit/push,
  public release, dependency upgrade, or unrelated IME/VoiceOver/performance matrix.

### 2026-09-14 — Writing UI handoff after user Desktop authorization

- User continued after the OS permission pause. Read-only tccd log confirms
  kTCCServiceSystemPolicyDesktopFolder Allowed (User Consent) at14:51:30 for
  com.icstex.app/PID6984. No agent interaction with the protected prompt or TCC
  database. The same installed process completed opening the existing EA file.
- Fresh AX and screenshot show EA saved/idle, labeled toolbar, scaled auto switch,
  upright comments, narrow actionable PDF empty state and footer console entry;
  no remaining authorization/file picker. Program776d175e and original EAa24d90cd
  hashes unchanged. No source edits, manuscript save/compile, rebuild, reinstall,
  or repeated tests. Prior1729-test preflight remains the source receipt.
- Local UI delivery is now ready for user acceptance; follow-up is limited to
  new concrete feedback. Historical permission diagnostics and backups retained.

### 2026-09-14 — Console toolbar entry and legacy cases-button removal

- Replaced only the top Word Count action with a checkable Console action shared
  by toolbar, footer and View menu. It toggles the existing panel, preserves its
  active tab and expansion preference, and does not force a count. Compile-menu
  Word Count still selects/refreshes its statistics tab. Removed the old Insert
  Panel “分段函数” button, retaining the formula editor's cases structures/API.
- 25 related checks/8.731s and one native toggle check/1.188s pass. Final preflight
  passes1730 tests/310.601s, process312.390s, exit0; compileall and identities match.
  Sourceb950dc60/test703e2598; no performance matrix or manuscript compilation.
- Fresh existing-spec local Beta2 package matches201 app modules+entry/36assets,
  same module set and explicit existing exclusions. Arm64/ad-hoc deep/strict
  signature checks pass for candidate, installed app and backup. Installed hash
  499d04f091de18f19343c583b3cac13129564344c8656dca028b37b3425a8bf3.
- Confirmed current Physics EE saved/idle, quit normally and checked process exit
  after the post-quit AX timeout. Original fileab4179b6 unchanged. Priorcf281 app
  retained in ICSTeX Backups/ICSTeX-2.1.0-beta.2-before-console-b950dc60-20260914.app,
  prior hash776d175e intact. New PID10157 welcomed with Console label/description.
  Left at welcome as announced; no desktop-document reopen or OS-consent handling.
- Receipts in console-entry-20260914; focused logconsole-entry-focused-20260914.log.
  User guide updated. No dependency upgrade, Git commit/push, public release,
  original text change, forced app termination or unrelated feature removal.

### 2026-09-14 — Bounded preparation for macOS online updates

- User authorized preparation of the macOS arm64 Beta update workflow, not live
  deployment or replacement of the current application. Opted-in startup checks
  now use a30s delay and5min restart cooldown before returning to daily checks.
  Compilation/export/modal/no-window states defer automatic work; manual checks
  consume the pending startup check. Failed native initialization now records its
  attempt before returning, preventing a repeated once-per-minute failure loop.
-58 update checks/1.056s and one updated dialog check/0.137s passed. A single final
  preflight passed1739 tests/301.196s, command302.910s, exit0, including compileall.
  Source identity remainedceb2ffd55f012c3b34dd81413f9923bae43612c0331716728b9f2ed1381e7a87;
  app+tests remainedf5994502df672a584b3a4f5ac884368232d0a790a820a33a4e7b6e921b795bcc.
  Raw Qt/offscreen and asynchronous temporary-directory diagnostics are retained
  under ~/.codex/visualizations/2026/09/14/icstex-update-preparation-1318/full/.
- Read-only GitHub verification returned repository admin/push permissions and
  only the published v2.1.0-beta.1 release. The existing Vercel project/domain
  was verified through its connector; latest READY deployment remains a preview.
  The configured public appcast returned404. Existing update configuration passed
  strict parsing; no signing-key access, asset upload or deployment was attempted.
- Re-read the pinned Sparkle2.9.6 termination-monitor source: first-instance,
  late-instance and other-login-session limits remain. No process scan was relabeled
  an installation lock. A non-resident, installation-only coordinator is proposed
  in docs/UPDATE_ACTIVATION_PREPARATION.md and requires a bounded decision before
  implementation; no custom helper or installer was added.
- No version bump or obsolete candidate rebuild while that decision is pending.
  Installed executable still hashes499d04f091de18f19343c583b3cac13129564344c8656dca028b37b3425a8bf3.
  No application interaction, student-document change, compilation-core edit,
  performance retest, SDK upgrade, Git commit/push or public activation occurred.

### 2026-09-14 — Voluntary GitHub Star entry points

- Added one optional support invitation below the website platform panels, using
  the existing release-driven repository link and styles. Added Help > 在 GitHub
  支持项目（Star） as an explicit browser-opening action. Failed browser launch
  exposes the URL in the status bar, not a modal. No OAuth, token storage, Star
  read/write API, tracking, automatic browser opening or download/update gate.
- Initial focused run had one Qt temporary-menu-wrapper lifetime error in the
  new test. Retaining the menu action before retrieving its menu fixed that test;
  the single failing test passed in 0.460s without a product-code change. Final
  full discovery passed 1742 tests in 293.193s, command 294.761s, exit 0, with
  unchanged source identities; compileall and git diff --check passed. Raw Qt and
  asynchronous temporary-directory diagnostics remain in the full log.
- App SHA-256 a8bb8ee66b8ae6d9a28f969df5795d0a05fc4b33687810bb964fe7f84dd05caf;
  app+tests eadecb035cdf6be25dd06a009a4ed83f95be3ec749ac12473030f2f6e5ff5a91.
  Receipt: ~/.codex/visualizations/2026/09/14/icstex-star-entry/full/.
  Only website/index.html changed in the site; its SHA-256 is
  34e1386608e50acb7716286587d2f39394fe214637c416f6eceb09fe674b6521.
- Hidden in-app-browser verification showed the correct GitHub URL, independent
  download links and readable desktop/390px layouts, with no observed console
  errors. No external link or download was activated. Reset the viewport, closed
  the tab and stopped only the task-created localhost server. Offscreen Help-menu
  capture was inspected at icstex-star-entry/help-menu.png; it is not a native
  installed-app acceptance claim.
- No compilation/updater change, dependencies, foreground takeover, packaging,
  app replacement, Git commit/push or site deployment. The separate temporary
  installation coordinator remains an unapproved proposal.

### 2026-09-14 — Latest Star/update-preparation source installed locally

- User explicitly requested synchronizing the local app for personal acceptance.
  Required packaging preflight passed 1742 tests/299.439s, command 301.192s, exit0,
  including compileall. Before/after source identities match the prior Star source:
  app a8bb8ee66b8ae6d9a28f969df5795d0a05fc4b33687810bb964fe7f84dd05caf;
  app+tests eadecb035cdf6be25dd06a009a4ed83f95be3ec749ac12473030f2f6e5ff5a91.
  No product-source edit or repeated performance/manuscript/UI matrix was added.
- Used the existing PyInstaller 6.21.0/PySide6 6.11.1 and original spec with a new
  output/work directory, explicitly without ICSTEX_UPDATE_RUNTIME. Build passed.
  Candidate and installed bundle match 201 app modules, entry and36 assets, retain
  the same packaged module set, and enumerate the existing13 excluded modules.
  Arm64/ad-hoc, deep/strict signature checks passed; this is not Developer ID or
  notarization and contains no public updater runtime.
- No ICSTeX process was running before replacement. Copied the new bundle to a
  distinct Applications staging path, checked it, then moved the entire old bundle
  to ~/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.2-before-star-a8bb8ee6-20260914.app
  and installed the staged bundle. Old executable hash remains499d04f091de18f19343c583b3cac13129564344c8656dca028b37b3425a8bf3;
  installed executable hash is19fc3696f337a1024460557742ac711cbaf3284d393daab1cd85585ce4ac80af.
- Launched /Applications/ICSTeX.app, PID47864. Native AX confirmed the welcome
  screen, latexmk readiness and Help > 在 GitHub 支持项目（Star）. Closed the menu via
  its exposed Cancel action after Escape did not change AX state; left the app at
  welcome. No document open/save/compile, forced quit, Star click or OS consent.
- Evidence and versioned candidate are under
  ~/.codex/visualizations/2026/09/14/icstex-local-star-a8bb8ee6/ with preflight,
  candidate-receipt.json and installed-receipt.json. Website changes remain local;
  cloud update activation/installation coordination remains incomplete. No Git
  commit/push, site deployment, Release upload or key access occurred.

### 2026-09-14 — Star invitation published on production website

- User explicitly authorized website deployment and cloud-update activation.
  Published only the existing static site plus its verified Star invitation to
  the original Vercel project prj_BXdZTV6vil9XDBCg2Nh43roEVFsm. No new project,
  CLI installation, Git commit/push, application archive or appcast upload.
- Deployment dpl_BNjncgsErUro32pizaRDenSRjnHT reached READY with target production
  and no aliasError. Production aliases include ics-tex.vercel.app and the prior
  website-phi-beryl-92.vercel.app. Immutable deployment URL:
  https://website-3f0m04yan-leoxuminghua-7962s-projects.vercel.app.
- Uploaded 15 allowlisted static files, including the existing guide/about,
  assets and update-path cache headers; excluded .vercel metadata and all update
  candidates. HTML SHA-256 remains34e1386608e50acb7716286587d2f39394fe214637c416f6eceb09fe674b6521;
  release.json remainsfd9a2a26f0234ff5df241b8e34ea73fbcfff9ffbe90cd5146a98925ef5c8a511.
  update_release_site.py --check and verify_release_consistency.py passed.
- Hidden-browser verification on the production alias waited for release data,
  then confirmed the optional Star invitation links to github.com/leoXu-612/ICSTeX
  and the independent DMG link still targets published Beta1. No console errors
  observed, no external link/download activated, and the tab was closed.
- Application/source-test identities remain a8bb8ee6/eadecb03; reused the matching
  prior preflight without redundant app tests or packaging. No installed-app or
  student-document changes. Cloud-update publication permission is now explicit,
  but activation remains incomplete because installation-lifetime exclusion and
  its acceptance are unfinished. The temporary-coordinator proposal still needs
  a concrete architecture decision; no helper/SDK change or key access occurred.

### 2026-09-14 — Calmer website typography and Chinese wrapping

- User requested redesign of oversized headings and awkward wrapping using local
  design Skills. Applied frontend-design's scoped refinement and emil-design-eng's
  hierarchy/readability guidance. Changed only the site stylesheet: smaller type,
  existing sans-serif stack for Chinese headings, normal tracking, roomier leading,
  wider title columns and shorter section spacing. No text, asset, script, download,
  Star behavior, dependency or animation additions.
- At the same1280px viewport, the observed homepage h1 changed89.6→54.4px and h2
  changed57.6→32px; the download heading changed from two lines to one. Checked
  homepage320/390/901/1280px and guide/about390/1280px without page/heading horizontal
  overflow. Inspected actual desktop/mobile screenshots, including the mobile
  guide's two-line title; source-file text was preserved rather than manually cut.
-17 site checks passed/0.195s, compileall and release metadata checks passed.
  One final discovery passed1743 tests/299.170s, command300.830s, exit0, with stable
  source identities. App stays a8bb8ee66b8ae6d9a28f969df5795d0a05fc4b33687810bb964fe7f84dd05caf;
  app+tests e619e6d10d3db80985c90d6d97dbd895c2c732a34ad49d32a74be2545b14c055.
  Receipt/raw diagnostics: ~/.codex/visualizations/2026/09/14/icstex-website-typography/full/.
- Reused the prior verified15-file Vercel site payload and replaced only styles.css,
  SHA-25692a08884cf5e671a6fa456f6d7857b3be17b3b0a82d2cdb6d62372ecec568738.
  Production deployment dpl_6BMsHpQ7kAUmUZh2j22VCH2pdK93 reached READY in the original
  project, with no aliasError. URL https://website-bx7mymnvp-leoxuminghua-7962s-projects.vercel.app;
  production aliases include ics-tex.vercel.app and website-phi-beryl-92.vercel.app.
- Production-browser verification confirmed the new32px single-line download
  heading, normal tracking, unchanged repository Star URL and Beta1 DMG URL, with
  no observed console error. Closed hidden tabs, restored viewport and stopped
  only the task-created localhost server. No desktop app interaction/rebuild,
  Git commit/push, appcast publication, app archive upload or signing-key access.

### 2026-09-15 — Website downloads synchronized to macOS Beta 2

- User requested updating the website's installer version. Separated manual
  download delivery from the held automatic-update installer. Reused the exact
  verified a8bb8ee6 GUI application; no app-source change, recompile, local app
  replacement, manuscript access or signing-key access.
- Created an isolated release worktree on codex/beta2-manual-release-20260915,
  copying the verified app/tests/tools and public website/build files. Original
  development checkout, branch and index were preserved. The release snapshot
  fea315a9c0b5290ab106384e4fc24537cef95192 was tagged v2.1.0-beta.2; only the tag
  was pushed. Existing workflows are branch-push/PR scoped; no Actions run was
  observed for this release SHA. New raw diagnostic logs/screenshots were excluded.
- Required preflight passed1743 tests/308.141s, command309.961s, exit0, with
  matching app/test identities a8bb8ee6/e619e6d1. Release-worktree site checks,
  compileall, source-version/tag/asset consistency and SHA256SUMS checks passed.
  Raw Qt and temporary-directory diagnostics remain in the local preflight log.
- Created DMG/ZIP wrappers around the existing signed bundle. DMG size63524767,
  SHA256934ca18aa00b4c62d7188ab5354e11c702f159871055ec05bac6f6dbdca4dd57;
  ZIP size55627757, SHA2562a13bceacb754458b4a81069bac17bc509631ef1b4df47ae32a7ed46c9d8a511.
  Container integrity, extraction, deep/strict signatures and exact packaged
  source/assets passed; executable remains19fc3696f337a1024460557742ac711cbaf3284d393daab1cd85585ce4ac80af.
  The temporary read-only DMG mount was detached.
- Published GitHub prerelease388907299 at
  https://github.com/leoXu-612/ICSTeX/releases/tag/v2.1.0-beta.2 with two Mac
  archives and six release/verification documents. Draft asset digests matched
  before publication; anonymous downloads then returned HTTP200 with exact
  byte/hash matches. Beta1 and old Windows assets were not overwritten.
- Deployed15 static files to the original Vercel project. Production deployment
  dpl_CqXS2m5JyyAUWjBr5vmCMJhdNbK4 reached READY with no aliasError, at
  https://website-5q8z2jvs7-leoxuminghua-7962s-projects.vercel.app and the original
  production aliases including ics-tex.vercel.app. Browser verification confirmed
  three Beta2 version labels, correct DMG/ZIP links and hashes, explicit legacy
  Windows copy and no new-Windows download href; no console errors observed.
- Synchronized only the public release/site metadata back to the development
  checkout. CSS/Star behavior preserved. Evidence and public re-downloads are in
  ~/.codex/visualizations/2026/09/15/icstex-beta2-manual-release/.
  This remains arm64/ad-hoc, not notarized, with no public updater runtime or
  appcast; automatic-upgrade gates were not waived. Future updater releases must
  use a new version rather than republishing the old internal r2 as Beta2.

## 2026-09-15 — Delivered macOS Beta 3 online updates

- Implemented installation-position shared leases, atomic entry/upgrade gates, a bundle-ID
  update gate and a short-lived native guard. It tracks the exact in-bundle Sparkle
  Autoupdate PID/start time with kqueue, retains exclusion after GUI exit and keeps
  a fail-closed journal if the guard dies. No SDK modification, daemon or new installer.
- Final preflight passed 1758 tests/302.583s (command304.212s), compileall passed,
  app/test identities unchanged: app500675e9, app+testsdd4f1114. Earlier missing
  reference-asset and fixture/verifier failures and non-fatal Qt diagnostics are retained.
- Local native acceptance included the user's confirmed download/install, accurate new
  binary and complete file/symlink equality, modified-feed/archive rejection, main exit
  with stopped Autoupdate82184, blocked late entry, coordinator82183 killed while the
  journal still blocked entry, and recovery/cold launch after the exact installer ended.
- Signed Beta3/210003 ZIP5cf1413c (56,747,305bytes) and DMG15f9736c (65,266,837bytes).
  Public tagv2.1.0-beta.3 points81b1672d162de2128374e9cdb9a7c20b00a95110.
  GitHub prerelease388996893 published2026-09-15T09:02:00Z, with eight assets; all
  server digests matched and both installers were anonymously downloaded HTTP200.
- Production Vercel dpl_7P7UsiCcEtNRYbuanZkyy8WJDpba is READY; website version/download
  links/hashes and no observed console errors were checked. The fixed signed appcast
  is live; its signed-byte SHA256 is ab86e84fd8a0bf5d3c80b7c5a5ab7ebea4d0525d038946c1b01b2dce7430eab6.
- With fixture server81416 stopped, the HTTPS bootstrap opted into automatic checks,
  found the public update, downloaded and installed after explicit CUA confirmations.
  Old process93669 exited; new process93769 existed before UI inspection, version210003,
  executablefa4a83f83829a367c5760ccfe1a3f66776752212d3444fbd59c9b342f8f92ad4.
  Complete bundle contents/symlinks matched; the native writing window was observed.
- Installed the anonymous public ZIP at /Applications/ICSTeX.app after confirming no
  installed process; kept the complete Beta2 backup at
  ~/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.2-before-online-beta3-20260915.app.
  Both signatures/hashes verified. The Mac locked again before opening the final installed
  path, so that final window observation remains user-facing handoff, not claimed complete.
- Original development branch/index and unrelated edits preserved. No student document,
  private-key export, Windows/VM change or claim of notarization/automatic rollback.
  Evidence: ~/.codex/visualizations/2026/09/15/icstex-online-update/.

Beta3 delivery follow-up: sanitized delivery state and the website network-consent
copy were committed as5fedd8b8d9b75b19b9dfcec98c40c2b59fa8f91a and pushed to
codex/update-release-20260915. The full-head-SHA GitHub query returned zero Actions
runs. The application release tag remains81b1672; no published archive was changed.

## 2026-09-16 — Student writing flow, first source batch

- Added purpose/language selection and descriptions to the existing project wizard,
  nine genuinely precompiled template thumbnails, and collapsed source/advanced controls.
  Kept the existing creation transaction, engine selection and no-overwrite boundary.
- Reused saved/revision/PREVIEW/FINAL state for distinct document and PDF feedback;
  fixed the saved-document waiting message. Diagnostics now expose location, next step,
  raw text and explicit diff confirmation before package edits. Welcome environment status
  is compact, recheck is explicit, and recent entries show file/path context without scanning.
- No dependency, runtime template compile, compilation scheduling or rendering-engine change.
  An owned Chinese project passed GUI-entry compilation, edited-title rendering, saved/old-PDF
  feedback and real missing-image failure retaining the previous PDF. All captures were offscreen.
  The v2 updated-PDF capture preceded paint; the corrected v3 waits for ink and the actual title
  was visually inspected. This is not native, IME, student-trial or fresh-machine acceptance.
- Bounded warm auto-preview median was2219.516ms, with unchanged old-code controls
  at2150.623/2323.857ms. These few time-separated samples do not establish a speedup.
- First full exitedSIGABRT after247.397s in the PySide allWidgets wrapper/malloc path;
  root cause remains unproven. The102-test targeted run and later complete runs did not reproduce
  it. Preserved Python-2026-09-16-152749.ips and all failed logs, not calling it fixed.
  Corrected old keyboard/tooltip/banner assertions and invalid success-PDF fixtures using
  existing valid-PDF helpers; the changed preview/recent group passed17 tests/3.401s.
- Final compileall and full regression passed1770 tests/288.095s, command289.481s, exit0,
  unchanged app808efbd7 and app+tests48c0c754. Nonfatal Qt/temp-directory diagnostics remain.
  Evidence: ~/.codex/visualizations/2026/09/16/icstex-first-task/full-regression-final/;
  implementation and boundaries: docs/student-writing-first-batch-2026-09-16.md.
- Kept the shared existing edits and empty index. No commit/push/package/install/release,
  student-file edits or foreground control. Installed Beta3 executable still hashes
  fa4a83f83829a367c5760ccfe1a3f66776752212d3444fbd59c9b342f8f92ad4.
  Interactive tutorial, image reselection and student/native/fresh-machine acceptance deferred.

## 2026-09-16 — Local simplification and behavior consistency

- Used the actual dirty codex/v1-development tree at HEAD3bde2b5, not a release checkout.
  Saved only affected files under icstex-local-simplification/before; original edits/index kept.
- Reproduced the citation failure leaving an idle200ms timer running. Stop decisions now follow
  pending handoff; report monitoring remains. The material pending-failure concern was not a
  demonstrated existing failure: replacement requests already cancel the old owner. Tests retain
  that monitoring boundary and reject late owners. Shared only the full immutable source key,
  not navigation, report application or material baselines. Worker diagnostics omit exception text.
- Batched checkbox assignment now uses scoped QSignalBlocker, applies each editor once, and
  writes preferences only when requested. Engine synchronization has explicit persistence/build
  intent; single user actions remain immediate. One red batch fixture previously wrote six times.
- Shared one-stat nonempty-regular-file observations in the existing core module; directories
  no longer count as available FINAL files. Kept separate state machines and fresh export checks.
  PDF button refresh obtains root once and reuses its synchronous file observation.
- Avoided unchanged recent settings writes and menu/button reconstruction; retained path ordering,
  deletion checks, Save-As and exact serialized-path normalization. Compiler selection in the wizard
  updates only its hint, preserving source selection/scroll and the verified static thumbnail.
- Focused controllers passed29 tests/4.238s; final settings3/0.593s, recent9/1.063s and template6/2.563s
  passed. The PDF group initially had one wrong fixture helper name (88 other tests passed); that
  single test passed after correction. Early thread mocking also intercepted a watcher thread;
  the corrected test mocks only the selected controller launch. No product safety assertion removed.
- A later independent check caught this task's recent dedup skipping legacy textual normalization.
  Compare serialized values, not just resolved Paths; six affected tests passed/0.591s. Preserved
  the prior full1789 pass as a prior identity, not final evidence. Initial GUI capture preceded deferred
  widget deletion; fixed only the capture boundary, then observed the final recent/engine states.
- Final compileall passed; full1790 tests/310.500s, command311.987s, exit0. Appc69c53da and
  app+tests24d1b596 were identical before/after. Qt platform/PDF-link and temporary-path diagnostics
  remain in the full log. No claim that the previous allWidgets native abort was fixed.
- Same-source gui-current captures verify actual offscreen controls, saved bytes, recent file
  captions, stable preview selection/image and no build authorization. Simulated worker failures
  are deterministic boundary tests, not native or external-tool acceptance. No end-to-end speedup claim.
- Only existing source/tests/governance files changed; no new application framework, dependency,
  student-file edit, foreground control, commit/push/package/install/release or old upgrade matrix.
  Evidence: ~/.codex/visualizations/2026/09/16/icstex-local-simplification/; final receipt full-final/result.json.

## 2026-09-16 — Illustrated onboarding and an independent writing exercise

- Replaced the application's long static guide with four task-focused Chinese pages and four
  genuine local UI illustrations (231294 bytes). Explicit image links use the system viewer,
  limited to the known local assets. No network illustrations, autoplay or new dependencies.
- Added an opt-in three-step exercise using the existing Chinese template, project creation,
  window factory and compile action. Owned examples/settings are independent of the original
  window; remembered paths are scope/link checked. Title selection respects UTF-16 boundaries.
  Progress requires an edit, explicit compile action and current root/revision/build-id PDF;
  the user confirms seeing the new title. Failed/stale/busy/foreign output cannot finish it.
- Hidden guides stop refreshing. Returning reuses the controller/window; after closing the window,
  saved content remains and a new compile confirms the PDF. Reopened exercise preferences use
  the current application-wide scale, not a stale scale that would change the owner's windows.
- Fourteen focused tests passed/12.019s. An initial missing PropertyMock import was corrected.
  Real offscreen compilation/rendered title, cursor/scroll, failure preserving the old PDF and
  hide/resume passed. The first capture waited on a hidden compact PDF; the corrected script uses
  the actual Show PDF action. Export illustration is the prepare page only, not a delivered package.
- A separate unresolved-temp-path probe stopped in QMessageBox, confirmed by sample33351;
  the owned probe was terminated143. Canonicalizing the trusted base before computing its settings
  path fixes the alias mismatch; added alias and stale-scale reopen regressions. Not a native crash
  or a global-style rewrite. Earlier full1801 pass remains evidence for its earlier identity only.
- Final compileall and tool syntax checks passed. Full1803 tests/718.104s, command721.288s, exit0;
  unchanged app003d6540 and app+testse4ceb8d5. Qt/platform/PDF-link and temporary-directory
  async diagnostics remain. No claim of fixing the previous allWidgets native failure.
- Updated the existing user guide, state, roadmap, brief and index. Captures, initial snapshots
  and final receipt: ~/.codex/visualizations/2026/09/16/icstex-task-guide/ (capture-delivery/, full-final/).
  No student documents, installed application, website, remote repository or release were changed.
  Human student trials and native end-to-end acceptance remain separate; source delivery is complete.

## 2026-09-17 — Install current source locally and open the illustrated guide

- User authorized local installation/open only. Preserved branch/index, student documents and
  existing dependencies; no application-source change, public release, push or website deployment.
- Required preflight passed: 1803 tests/312.672s, command314.326s, exit0; unchanged app003d6540
  and app+testse4ceb8d5. Retained Qt/temporary-path diagnostics and stale artifact reminders.
- Built using the existing spec and final Beta3-bound-installer Sparkle runtime; native bridge/guard
  source matched the prior release. Verified 205 modules/entry and all source assets, with no lost
  previously bundled modules. Arm64, ad-hoc deep/strict integrity passed; no notarization claim.
- New installed executable is 5e46d205efcb83ba713a655db04ae2664095f1ae2d04f3a579a3dc9d4ca1fda1.
  Version label/sequence stays Beta3/210003; unique local ZIP uses 20260917-003d6540 and has SHA256
  d4340b88c0acdbd169849d9e730bfe1f959deab2e0e4a4fa39beecac78e11c0c. Public manifests unchanged.
- With no running app, staged then moved the intact old bundle to ICSTeX Backups/
  ICSTeX-2.1.0-beta.3-before-tutorial-20260917.app. Old executable remains fa4a83f8...f92ad4.
  Ordinary diff emitted Qt symlink-loop notices; a non-following manifest then verified equality
  of all 472 files and 160 links. Both installed and backup signatures passed. No security bypass.
- CUA launched /Applications/ICSTeX.app (PID89477), observed environment ready, four guide tabs,
  independent-exercise CTA and the actual title-edit illustration. Returned to the first tab top;
  did not start an exercise, open student files or claim native full writing acceptance.
- Receipts and logs: ~/.codex/visualizations/2026/09/17/icstex-local-install/. Build warning about
  the system libobjc absolute ctypes import remains recorded. Bounded local handoff complete.

## 2026-09-17 — Source-only portable project ZIP export

- Added File / 导出为工程文件… with a local checkable file list and standard ZIP output. Source,
  images, CSV/XLSX/DAT tables, BibTeX, local styles and known project metadata retain exact paths/
  bytes under project/. README.txt names the real entry; files.json records selected hashes.
- Reused checkpoint inventory/portable path rules, export capture/recheck, CaptureLease and exclusive
  output publication. The submission filename filter accepts an optional suffix set without changing
  its existing defaults. No compiler/PDF state, global UI, dependency, network or proprietary importer.
- Dirty/conflicting buffers require resolution; closing waits for worker cancellation. Old ZIPs and
  late destination owners remain intact. Missing/dynamic/out-of-scope/absolute references and
  deselected recognized dependencies require explicit acknowledgement; original paths are not rewritten.
  In-scope/local supported files only, not a completeness/privacy certificate or system-font/TeX bundle.
- Six core and five GUI cases passed in the final suite. Related existing export/submission/checkpoint
  tests: 55 passed/2.478s. First case-collision fixture was invalid on a case-insensitive Mac volume;
  simulated inventory now tests the portable collision rule. A warning-dialog fixture changed disk
  bytes behind an open tab and hit an earlier guard; a coherently opened fixture tests the intended
  confirmation. No protective assertions removed. A prematurely started full run was stopped with
  SIGINT (-2,42.987s) while fixing that fixture; its changed-identity receipt is not a passing result.
- Real offscreen GUI export and extraction kept all six example inputs identical. After moving the
  original directory aside, the extracted PNG/CSV/child/style/BibTeX project compiled with actual
  latexmk/pdfLaTeX (exit0,71168-byte PDF, expected bibliography text). Final source receipt is in
  roundtrip-final/. Success screenshots initially preceded deferred Qt layout; roundtrip-layout/
  processes the layout event and confirms the full visible success path. No product change for that.
- Final compileall passed. Full1814 tests/306.702s, command308.180s, exit0; unchanged app5834af3e
  and app+testsdecca1518. Qt/platform/font and temporary-path diagnostics remain. Evidence and scoped
  before snapshots: ~/.codex/visualizations/2026/09/17/icstex-project-archive/ (full-final-v2/).
- Updated guide/index/state/brief. Preserved other worktree changes and index; no student-file edits,
  application packaging/install, Git commit/push or website release. Installed app remains the earlier
  tutorial build; cross-device OS/native student acceptance is separate from this local round trip.

## 2026-09-19 — Source-only PREVIEW forward SyncTeX and historical checklist boundary

- Resumed the user-selected writing-efficiency increment, not the former onboarding/release task.
  Reused the existing reverse SyncTeX display guard for both directions: exact root, purpose,
  revision, build id, viewer path and current file. Navigation rechecks after the query and after
  compact-pane layout; forward requests also retain tab/path/document revision/caret identity.
- The existing source-to-PDF action now accepts latest PREVIEW as well as FINAL, reveals a compact
  PDF pane and rejects absent/invalid results. A real child-file test found the old handler returned
  solely because a newly opened child had no compiler manager; removed that unnecessary condition.
  No save/build authorization, extra compilation, source edits, renderer changes or new dependency.
  Per-refresh root/file observations remain shared; actual navigation and export revalidate on use.
- Added six focused regressions and extended existing cases, including same-revision/new-build,
  late callback, missing tool/file, page/coordinate bounds, foreign viewer and independent purposes.
  The focused batch passed 23 tests/13.573s; final full discovery covers all final source changes.
  Real pdfLaTeX/SyncTeX preview with proxy image and original child passed both directions at
  0.9/1.25 zoom, then forward navigation in a compact writing pane: target page 2, unchanged source/
  caret, no FINAL output. Final isolated capture passed 1 test/3.996s with the final app identity;
  inspected rendered target text, not just a Ready document or window. Offscreen Qt, not native
  student/physical-keyboard acceptance.
- Earlier tests wrongly assumed stale FINAL reveal eligibility was forbidden; corrected the test
  oracle while preserving existing FINAL freshness/submission rules. Compact fixture first ignored
  the main-window minimum width, then tested isHidden on the inner child instead of the wrapper;
  corrected only the fixture, not product layout. Kept those logs and the reproduced manager failure.
- Required compileall passed. Full 1820 tests/564.503s, command568.878s, exit0; before/after app
  6019e05630dc79811751ebb3b4ec680dbb97ab63b26a17c92587528b00e4d576 and app+tests
  a404b1f2b1cdf4ae677503b2ffd7eff26482a33e37d8fbe603e34ebb2cf749e7 match. Qt/platform/font/
  PDF-link and temporary-directory async diagnostics remain; no zero-warning or performance claim.
- Marked V1_RELEASE_READINESS as the 2026-09-12 historical snapshot, linked current state/Beta3
  delivery, and updated D019, roadmap, user guide and brief. No waiver of unrelated unverified scope.
  Evidence and scoped pre-task snapshots: ~/.codex/visualizations/2026/09/19/icstex-preview-forward-sync/
  (full-final/result.json, visible-final/result.json and pdf-viewport.png).
- Task branch codex/preview-forward-synctex retains HEAD3bde2b5d and the pre-existing dirty tree.
  Index remains empty; historical source changes are not attributed to this increment or silently
  committed. GitHub Actions remain disabled; no CI, commit/push, package/install, release or student
  manuscript operation. Installed tutorial app remains unchanged and lacks this source increment.

## 2026-09-19 — Accepted preview navigation, source target cue and local installation

- User accepted app6019e056 preview navigation, requested a visible cue at the PDF double-click
  target, then explicitly confirmed saved/closed windows and a complete effective-source local
  checkpoint including previously uncommitted dependencies. No push/public release authorization.
- Added a two-second amber ExtraSelection at the accepted source line; source pane is revealed in
  compact layout. Cursor movement, actual edits or hiding the editor clear it. One owned timer is
  restarted for later targets; search matches keep their own layer/lifetime. No text selection,
  document/undo mutation, extra compile or PDF renderer change. Failed/cancelled opening does not
  flash another file. SyncTeX line-level correspondence is not claimed to be word-level precision.
- Added three cases, extended original-child and real preview tests. First 24-case focused run
  had one test-only borrowed QTextCursor wrapper lifetime error; retaining the returned selection
  list fixed the oracle. The two editor cases then passed/0.499s; final full suite covers all cases.
  Actual pdfLaTeX/SyncTeX capture passed/5.244s at both zooms, original child line2, no text selection,
  active one-shot timer and 10713 amber pixels per screenshot. Visually inspected the target text.
- One final local preflight passed: compileall and 1823 tests/709.960s, command715.424s, exit0.
  Before/after app180277afaf1f5111e65271641ed473ed48daa0ec1d3f87e5ceb2f44cab8facf2 and
  app+testsd30da6034a20d16671e8dd672564c27d3f136dd59f3310b1efbd21c03b5ded33 match.
  Qt/platform/font/PDF-link, synthetic failure and temporary-path diagnostics are retained; no
  claim of eliminating old native problems or improving measured compilation speed.
- Existing PyInstaller spec reused the verified Beta3-bound-installer Sparkle runtime. Bridge,
  native guard, startup hook and lease sources match release commit5fedd8b. No dependency install
  or upgrade. Verified208 modules/entry and all assets, with no lost previous module;12 independent
  non-GUI modules remain unbundled. Build retains the existing libobjc ctypes warning. Arm64 and
  ad-hoc deep/strict integrity pass; no Developer ID/notarization claim.
- Used existing InstallationLease to exclude running apps/installers, staged and checked a full
  copy, preserved the old bundle, then renamed into /Applications/ICSTeX.app. All472 files/160 links
  equal the candidate; all backup content is unchanged. New executable SHA256 is
  d8c0d3c327ebbeb631d40749f7ac6bb7a0349fbf79afff9569aef34f9f9a0286. Old5e46d205...fda1
  remains in ~/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.3-before-synctex-highlight-20260919.app.
- Native launch from /Applications observed PID92638, welcome/environment ready and current
  navigation tooltip. Did not open a student manuscript or claim physical highlighter acceptance;
  cue evidence is the isolated real offscreen build above. Update runtime and user settings remain.
- Evidence: ~/.codex/visualizations/2026/09/19/icstex-sync-highlight/ (preflight-final/result.json,
  visible-result.json, package-receipt.json, install-receipt.json and screenshots). Local ZIP uses
  version/date/source180277af identity; public Beta3 metadata/feed/tag remain unchanged. Current
  state, guide, roadmap and bounded brief updated. Full effective-source commit scope is explicitly
  authorized; its accumulated historical work is not attributed to this small highlighting change.
- The full staged snapshot contains328 paths. Its whitespace check reports only four existing
  historical JSON receipts with a blank EOF line; original evidence bytes are intentionally retained.
  Credential-marker matches are synthetic private-key-header fixtures in export protection tests,
  not private keys. No active Git hooks, generated bundle/cache or student manuscripts are staged.

## 2026-09-20 — Formula caret navigation and experimental local handwriting

- Started clean at2d36956 on codex/formula-navigation-handwriting. Reused the existing math AST,
  painter/caret boundaries and OCR manager/protocol/review rather than replacing the editor/backend.
  Fixed reversed base-to-script arrows, direction-insensitive script switching, node-index versus
  caret-index exits and missing entry repaint. Vertical movement enters adjacent structures, reaches
  outer fractions from nested roots and chooses the nearest rendered x-position; absent slots are
  not created by navigation. Added the active-slot label. No source write, Undo entry or compilation.
- Added a small local stroke canvas, stroke undo/clear and explicit recognition button. A uniquely
  owned temporary image excludes the widget border; fractions are not auto-split into line bands.
  Async results are request-id bound, timeout/cancel/failure preserve isolation, and existing review
  plus sanitizer precede formula-draft seeding. Final document application retains the old guard.
- The existing optional environment had no Python and a stale manifest pointing into a missing
  temporary spike. After explicit user consent, installed pix2tex0.1.4 with Python3.11.15 in the
  ICSTeX optional-tools directory, about1.4GB; pip check passes. Preserved the old manifest locally.
  Fixed installer honoring the supplied Python and readiness checking actual model files. No system
  Python/core dependency upgrade, student file, manuscript upload or cloud OCR. Exact environment
  versions and model SHA256s are retained with the local evidence.
- For cancelled/restarted recognition, existing stopped clients now start again. Absolute worker
  entry plus three stdlib-only raw worker modules in the spec remove dependency on the host cwd/PYZ;
  an isolated resource-layout test verifies --help startup without GUI modules. No new app packaged.
  Disabled Albumentations' import-time online version check in the inference worker.
- First real-model GUI probe failed immediately: client.start() synchronously emitted a state
  notification before OcrManager stored its client, so status incorrectly returned STOPPED. Assigning
  the client before start fixed this ordering; an actual fake-process startup/restart regression
  protects it. Failed first receipt retained, not represented as a model-quality result.
- Final real-ocr-v2 uses the actual pix2tex CPU model and generated Qt mouse strokes. Candidate
  windows visibly showed x+1 -> \\times+\\ ^{\\gamma}, one-half -> \\frac{1}{\\mathcal{Z}}, and x-square ->
  \\displaystyle{X^{2}}. All reviews were explicitly cancelled by the probe; no formula was applied.
  First call including model startup/review took13.071s, later examples0.489/0.456s. This is functional
  local inference evidence, not handwriting accuracy acceptance, student testing or a speed benchmark.
  The default model is insufficient for reliable handwriting; no unapproved model replacement/training.
- Focused math/OCR/composer checks passed, including111 cases at an intermediate scope and final
  affected manager/math cases. A fake-worker test emitted a QProcess teardown warning; retained.
  Final compileall passed; full1841 tests/542.555s, command547.262s, exit0. Before/after app
  b5601f0ee7223b7bd9c3c23da8b69f709395bb8a64d3565bd2de052cc0232eb7 and app+tests
  cb129a50ee40bbb470ef32cf293679982fdfd395c3e972e2380c0fdd0f16990a match. Qt/platform/font/
  temporary-path diagnostics remain. No prior native-crash-resolution or zero-warning claim.
- Updated the existing guide/state/roadmap/brief. Evidence root:
  ~/.codex/visualizations/2026/09/20/icstex-formula-input/ (full-final/, real-ocr-v2/, failed real-ocr/,
  GUI captures and installation log). Visible checks are offscreen Qt, not physical native input.
  Source-only handoff: no commit/push/CI, new bundle/install or public release. The installed
  2026-09-19 sync-highlight application remains unchanged; generic packaged OCR installer bootstrap
  was not validated by the separately authorized local environment installation.

## 2026-09-20 — Local handwriting model size, memory and coverage evaluation

- User requested local-first, measured weight/resource/feature tradeoffs. Preserved the pending
  formula changes and appb5601f0e; only task/state/history documentation changed in the repository.
  No production backend switch, manuscript operation, system setting change or app installation.
- Read-only resource probe observed M3,16GiB unified memory,8 logical/physical CPUs and about14GB
  filesystem availability; available RAM was unknown to that detector. Framework MPS availability
  was checked separately. Actual model runs were single-process/batch1 with4CPU threads, no CUDA
  fallback and bounded per-case/profile budgets. Did not modify power settings or close user apps.
- Downloaded official Tiny at3f09ac4b1cd583be47ea20a7d7daef839473028a and Small at
  82cb85440138c2038680fca410c8f70bb7343d6d into a separate optional-tools/unimernet-eval directory.
  SHA256s: Tiny6f7608624e2d7549c7f0f05fcfbe073ae521328cf70f1d46374d96f9881d7371;
  Smallfa54b0a8126bb60060bc90818ce20a5ca1b5dd5d7da5c0983579f5c3a2cc90ea. Both strict state loads
  match all keys. One HF metadata command disconnected, one alternate mirror check timed out;
  fixed-revision HF downloads then succeeded. No credentials, uploads, new SDK or system Python.
- Separate unimernet0.2.3 environment uses torch2.14.0,transformers4.42.4,timm0.9.16; pip check
  passed. Initial compatibility import was slow in local dylib loading, with a retained sample;
  that concurrent setup observation is not used as an inference timing result. pix2tex is unchanged.
- Frozen all100 human/test MathWriting excerpt inks before inference plus3 existing generated mouse
  cases. Stored original archive hash, image/ink hashes, normalized labels and rendering contract.
  Qt rendering is not the paper's official raster benchmark. Data remains local, CC BY-NC-SA4.0;
  no student content. Rendering/gold-label ambiguity is retained, not filtered after predictions.
- Tiny CPU FP32:107402740 parameters/409.71MiB tensor payload; peakRSS1333.92MiB; cold-worker
  ready9.98s; warm median/P950.603/0.856s. Tiny MPS FP16:same parameters/204.85MiB; RSS1052.73MiB;
  ready14.02s; median/P950.393/0.947s. Sampled Metal allocator/driver peaks221.74/1140.13MiB
  are separate, not additive dedicated VRAM. CPU/GPU and precision changed together.
- Small CPU FP32:202454766 parameters/772.30MiB; RSS1882.25MiB; ready16.52s including additional
  checkpoint verification; median/P950.901/1.338s. No total-system-cold-start or UI-visible-latency
  claim. All309 inference cases completed without errors or output-cap truncation.
- Unified conservative token scoring gives real-handwriting exact6/100,6/100,7/100 respectively;
  mouse2/3,2/3,1/3. Fixed a prototype end-of-string script-brace normalizer boundary and re-scored
  preserved raw outputs without re-running models. Tiny FP32/FP16 outputs agree102/103 after
  normalization. Manual checks include real gradient/partial-derivative misrecognitions, not only
  layout differences. No category meets the predeclared >=10samples/>=90% provisional gate.
- Root4/matrix-or-cases2 samples are insufficient; sums/integrals were absent. Retain all manual
  editing/source fallback/compile/PDF functions; handwriting remains an explicit-review experiment.
  Dense models cannot shed corresponding weights just by disabling formula-category buttons.
  Do not adopt either model as a reliable default or continue unbounded downloads/training.
- Evidence: ~/.codex/visualizations/2026/09/20/icstex-local-model-eval/REPORT.md, inputs.json,
  scored-results.json and raw per-profile directories. Environment+two checkpoints about2.6GiB
  disk; all benchmark workers exited. Reproduction scripts are local evidence, not product code.
- Required compileall/full1841 tests passed369.923s, command371.996s, exit0; unchanged appb5601f0e
  and app+testscb129a50. Finished before benchmark timing to avoid competing test load. Existing
  Qt/font/temporary-path diagnostics retained. No commit/push, CI, package, release or install.

## 2026-09-20 - Withdraw unqualified handwriting input; retain formula navigation

- On top of the existing dirty codex/formula-navigation-handwriting tree at 2d36956,
  removed only the unshipped handwriting button, dialog/canvas and dedicated tests.
  Kept prior keyboard/caret improvements and existing image OCR readiness/startup fixes.
  Added an assertion that image OCR remains available without the experimental entry;
  guides, current state, roadmap and the active brief now reflect withdrawal.
- Removed the task-created optional-tools/unimernet-eval directory after checking its
  physical/non-symlink path, exact model/model-small/venv children and no active worker.
  Before removal du -sk reported 2699856 KiB (about 2.6 GiB directory allocation, not a
  measured free-space delta). Existing pix2tex environment, shared caches, system Python,
  student work and installed application were left intact. All evaluation inputs,
  scripts, predictions, scoring, requirements and model revision/hash records remain.
- Focused formula/editor/OCR tests: 109 passed in 2.201s. Required compileall passed;
  full offscreen discovery: 1835 passed in 461.291s, command 463.559s, exit 0.
  Before/after app 753b785b804cab09874c815795153480a33aaf8840db64f3e8392770b927225e;
  app+tests a54004d6f238170877e9c460766531d989b9c2474e60f6405084500ba591b891.
  Qt/font/offscreen and temporary-directory asynchronous FileNotFound diagnostics remain;
  focused mock-worker teardown emitted a QProcess diagnostic. No native GUI acceptance
  or model accuracy success is inferred from these tests.
- Evidence: ~/.codex/visualizations/2026/09/20/icstex-handwriting-withdrawal/
  source-before.tgz, cleanup.md and full-final/result.json plus unittest.log.
  Installed executable remains d8c0d3c327ebbeb631d40749f7ac6bb7a0349fbf79afff9569aef34f9f9a0286.
  No further model downloads, training, cloud service, CI, commit/push, packaging,
  release or installation. The installed app still lacks the new navigation edits.

## 2026-09-20 - Deliver standalone formula-navigation acceptance ZIP

- User requested a downloadable build to inspect the completed formula input improvements.
  No new application code: built dirty effective app753b785b/app+testsa54004d6, keeping the
  keyboard/caret fixes and existing picture OCR, without withdrawn handwriting or model weights.
- Required packaging/preflight.sh passed: 1835 tests/329.458s, command331.362s, exit0,
  source identity unchanged. Existing dependencies and PyInstaller spec reused; no pip upgrades.
  The previous standalone Sparkle runtime directory no longer existed, so reused matching
  framework/bridge/guard/public config/license from the signature-verified installed app.
  Native updater source unchanged; raw helper/config copies matched, no download or feed edits.
- Existing artifact verifier matched209 modules/entry and all assets, no lost baseline modules;
  three raw pix2tex worker files matched their source. Arm64/ad-hoc deep/strict passed.
  Executable SHA256 4d0b5206e8f73fe1de76dff110bfe29db54373ada09d2a4d0d9aa68167a2a46d.
  No Developer ID/notarization or native-user acceptance claim. Retained Qt/temp-path warnings,
  stale artifact reminders and libobjc absolute-ctypes build warning.
- Delivered ~/Downloads/ICSTeX-2.1.0-beta.3-formula-20260920-753b785b-macos-arm64.zip,
  57337682 bytes, SHA256 f90f8faeb86e14d8057bea500ad60f74876fb93b2deee93cd6f036dc89243eee;
  ZIP CRC passed. Contains app, disposable three-formula .tex fixture and Chinese test steps.
  Beta3/210003 label retained; unique filename identifies this local source, not a public release.
- Evidence: ~/.codex/visualizations/2026/09/20/icstex-formula-preview-package/
  preflight-final/result.json, package-receipt.json, build.log, acceptance/ and staged archive root.
  Installed executable remains d8c0d3c327ebbeb631d40749f7ac6bb7a0349fbf79afff9569aef34f9f9a0286.
  No foreground launch, installed-app replacement, student edits, commit/push, CI or publication.
  Waiting for user acceptance; do not install automatically.

## 2026-09-20 - Space visual formulas and install the accepted navigation build

- User accepted navigation, requested wider horizontal/vertical spacing and direct local replacement.
  On the dirty effective source, changed only math editor display/layout: letter/node/structure gaps,
  consistent small-font painting, single big-operator glyph, limit-column width, fraction rule placement,
  and complete baseline-aligned bounds. Hit testing now reuses the same measured layout.
  LaTeX/content/history/compilation behavior unchanged; no handwriting/model reintroduction.
- Added five focused layout/font/hit/source-preservation tests. 76 focused tests passed1.331s;
  final extended deep-script assertion passed separately. Initial preflight was deliberately interrupted
  at108.797s/exit130 after a direct deep-fraction superscript probe showed child-bottom99.925 exceeding
  box-height92.216875. Fixed the bounding/clearance calculation and retained the interrupted receipt.
- Final mandatory preflight passed1840 tests/332.194s, command333.972s, exit0.
  Frozen app fd584fd58c9b317589a99aad662060821279458bb9aad83f80dced6031642e6c;
  app+tests562981f4297cdebc93efada83db4e35f72eeabee725740329d872fd3a4a4650d unchanged.
  Existing Qt/font/temp-directory diagnostics and stale artifact warnings retained.
- Existing spec/runtime/dependencies produced arm64 ad-hoc bundle;209 modules/entry and all assets
  matched source, raw OCR worker sources matched, deep/strict integrity passed. No notarization claim.
  Libobjc absolute-ctypes build warning retained. No dependency/model downloads or public metadata edits.
- Used existing InstallationLease after normal exit of an empty old window; backed up old bundle to
  ~/Applications/ICSTeX Backups/ICSTeX-2.1.0-beta.3-before-formula-spacing-20260920.app,
  preserving old executable d8c0d3c327ebbeb631d40749f7ac6bb7a0349fbf79afff9569aef34f9f9a0286.
  Installed /Applications/ICSTeX.app matched candidate475 files/160 links; new executable
  0e06c53d4b8ef6e944f9c1468e1b5b490cb5d827f0c20005ec51dab86d2332ab.
- Native installed app displayed spaced superscript/subscript, fraction and sum in an unsaved fixture.
  Existing lossless guard correctly kept x_i^2 in source mode; changed only the dialog fixture to
  canonical x^2_i to inspect visual layout. Cancel preserved underlying draft; discarded the unsaved
  test and reopened to clean welcome page. No student file open/save/compile or preference toggle.
- Evidence: ~/.codex/visualizations/2026/09/20/icstex-formula-spacing/
  source-before.tgz, before.png/after-final.png, preflight-final[-v2]/result.json,
  package-receipt.json, install-receipt.json, build.log; native screenshot/state in this turn's tools.
  Preserved version label Beta3/210003 and updater; local install only, no CI, commit/push or release.
## 2026-09-19 — Lightweight GitHub Flow preparation

- Isolated codex/github-workflow from origin/main 2ff24e9a; preserved the dirty
  codex/v1-development checkout, existing PR #1, all product code and releases.
- Activated main Ruleset 23690757: PR, six observed GitHub Actions check names
  bound to integration15368, up-to-date base, resolved conversations, zero required
  approvals, squash only, no force-push/deletion/bypass. Read back effective rules.
- Added a five-section PR template, two Chinese-friendly Bug/Feature forms using
  existing labels, and one-page CONTRIBUTING.md. Priority is a form field, not
  new label automation. Template prose is a convention, not a new CI body validator.
- Corrected only stale Git/path guidance in AGENTS and linked the contribution
  workflow; updated this branch's bounded brief and governance-state section.
  No CI split, release-branch protection, CODEOWNERS, Dependabot or deployment.
- Local compileall and full offscreen unittest passed:417 tests/31.320s, exit0.
  App/tests tree IDs d10ae9d87d519aff915992cef9c1a102ae1ee47f /
  b3838ce478c9a86fdb768ac6e7f09defc0061354 unchanged; workflows unchanged.
  Issue YAML/fields, PR sections, contribution links and diff checks passed.
- Existing main Actions run31268120524 failed before jobs started: GitHub reports
  failed account payments or a spending-limit restriction. Owner action is needed;
  no billing change, CI bypass or merge performed. Templates await PR merge before
  becoming active on main. Local evidence is retained separately from this PR.
- Follow-up evidence after opening PR #2 supersedes the initial billing diagnosis:
  new PR run35417076078 actually started. Linux/macOS Python3.12 each ran417 tests
  and failed the existing stop_current confirms-exit/kills-unresponsive cases
  (2 failures,3 skips); their Python3.11 jobs failed too, Windows remained running.
  This docs-only PR did not change those app/tests trees. Updated the current
  handoff and PR body; did not change billing, weaken tests, bypass CI or merge.
## 2026-09-19 — Repair process-stop CI and observed Windows blockers

- Reproduced both exhausted post-kill deadline and a surviving child holding the
  output pipe with real Python subprocess fixtures on the unchanged main compiler.
  Both regression cases failed before the fix; no stop-success assertion removed.
- Launch isolated compile process groups. POSIX cancellation targets the original
  PGID even after its leader exits; Windows uses bounded taskkill /T before losing
  parent ancestry. Reserve time for force termination and worker/pipe drain;
  only the existing idle event authorizes a successful stop/cache cleanup.
- Replaced Unix-only shell test programs with real portable Python processes;
  wait for fixture readiness and retain native exit/result checks. Normalize the
  TEXINPUTS expectations to its existing forward-slash contract, not host separators.
- Cancelled only the two obsolete, failed PR #2 runs after Windows had hung for
  over an hour. Retained their logs: Windows was stuck in cache-clearing PDF state
  tests. Clear the active PDF reader after safety guards and before deleting cache;
  restore panel synchronization on failure. State-only malformed-PDF fixtures mock
  native parsing and close their reader before temporary-directory cleanup.
- Added a 15-minute CI job bound; retained all six existing jobs and full discovery.
  Local compileall passed;60 focused tests/6.117s and418 full tests/26.354s passed.
  GUI state mocks do not establish native rendering acceptance. Hosted checks are
  the merge gate; no bypass, release, dependency upgrade or installation performed.
- Work is isolated in codex/ci-process-stop from main; the dirty development tree
  and student files remain untouched. Evidence is retained under the dated local
  icstex-ci-process-stop directory; CI logs remain attached to the relevant runs.
- First repair CI passed all Linux/macOS jobs; the duplicate push run was cancelled
  to retrieve Windows logs, which showed the next preview/final state-fixture suite
  blocked. Applied the same malformed-PDF parser boundary there and made unexpected
  warning dialogs fail fast in both state suites. No renderer assertion removed.
  Final local full418/19.702s and compileall passed after that fixture correction.
- Merge closeout under the user's new no-CI policy: released native image test
  handles, corrected literal TeX paths, scrubbed native/forward-slash feedback
  paths, and compared CRLF save echoes in Qt's LF view without rewriting bytes.
  The 23 focused tests passed; final compileall and full419/24.706s passed on the
  repair source before merge. No hosted run was triggered after Actions disablement.
  Existing remote failure history is retained, not relabelled as Windows acceptance.

## 2026-09-19 — Local-only workflow merge closeout

- User disabled GitHub Actions and removed required CI checks. Main retains PR,
  resolved conversations, zero approvals, squash-only, no force-push/deletion/bypass.
- Repair PR #3 merged as 27582ca after local419/24.706s validation. Merged that
  main into the governance branch; reconciled the brief and retained both complete
  log entries. Updated CONTRIBUTING/state to the no-CI policy. Product app/tests
  are identical to the validated repair tree, not reimported from the dirty checkout.

## 2026-09-19 — Integrate modular-layout PR with repaired main

- Governance PR #2 merged as 3bbc8e4. Merged that main into the original PR #1
  branch in an isolated worktree; resolved compiler, compiler-test imports and
  log conflicts explicitly. Preserved both complete historical log sequences.
- Kept Block/formula/import features and opt-in compile timeouts; retained main's
  deadline-aware cancellation and isolated process-tree handling. Timeout cleanup
  delegates to the same signaling helper, including hard cleanup after leader exit.
- Added the post-leader-exit timeout orchestration regression. The first focused
  run exposed an existing env-python fixture startup race; initial full624 passed,
  but that did not waive the fixture failure. Pinned the fixture to sys.executable;
  both targeted cases passed/1.012s. Final compileall and full624/104.266s passed
  with stable app/tests and no remaining Git conflict entries. Qt warnings retained.
- Actions remained disabled. No CI simulator, workflow, packaging, dependency
  installation, installed-app replacement or student-document edit was performed.
  The original dirty development checkout and release branches were preserved;
  this integration covers the three open PRs, not unpublished development deltas.
  Evidence: dated local icstex-merge-closeout logs; exact merge state is on GitHub.

## 2026-09-20 - Integrate accepted writing source and prepare Beta 4

- User authorized GitHub integration and website/update publication. Saved the original dirty
  worktree at a5451d8; isolated integration starts at main69ca0b6. Shared feature44eecb8 is
  an ancestor of accepted local source and the original of main's squash. Resolved actual
  cancellation/CRLF conflicts, retained workflow governance and both history logs.
- Kept newer PDF fixtures' real reader and loaded identity checks instead of the old class-wide
  loader stub. Initial targeted125 had11 failures/2 errors from that stale mock; after fixing
  test integration, PDF cases passed. A mistyped standalone test name was corrected and the
  CRLF/save-echo test passed. No product guards or correctness assertions were weakened.
- Beta4/210004 app source frozen at ca778fe504893584d5fe6ece318876062b450268b8f662147832725e40dfebe6;
  app+tests7a6d2aa5d84295cff71a56731ba45fe3e284707317666a5cdf73e1b3d96aafaf.
  Final preflight1843 passed321.019s, command322.704s, exit0, identities unchanged.
- Candidate209 modules/entry, assets and three raw worker sources match; arm64/ad-hoc strict
  verification passed. ZIP57188923 bytes and DMG validated; archive signed with the existing
  Beta account. Feed signing is waiting on macOS Keychain authorization; no unsigned feed
  may be deployed. Vercel login restored; original website project and aliases confirmed.
- Keep public Beta3 assets/feed and installed local app unchanged until publication gates pass.
  Retained Qt/temp-path diagnostics, libobjc warning and failed premature unsigned-feed check.
  Local evidence: icstex-beta4-release/preflight-final, package-receipt.json, build.log.

## 2026-09-20 - Publish Beta 4 and activate the existing production feed

- Keychain signing completed through the existing account; no private-key export or key rotation.
  Local signed feed/archive verified with the embedded public key. Release/site consistency and
  all17 website tests passed; app/tests remained at the1843-test preflight identity.
- PR#4 squash-merged into main4ea00ff. Old release headf03776e was already an ancestor of
  accepteda5451d8; a branch from main recorded that incorporated lineage with no tree change.
  PR#5 froze the identical main tree at release/2.1 commit79fcd868a7109fb3b8dfa8c589007fbfa67a1414.
  Tagv2.1.0-beta.4 points there; strict tag-at-HEAD release consistency passed.
- Public prerelease https://github.com/leoXu-612/ICSTeX/releases/tag/v2.1.0-beta.4 contains
  DMG/ZIP and six documents. Anonymous ZIP download57188923bytes matched signed local bytes
  (170696e77b5eca6b09fefe3bb4cdab95d2c4862c9ebe56589811220e4e01aa6a); DMG endpoint200,
  65672242bytes and GitHub digestcfcffab1e0b80f7c78df49fd953d4c4d213ab138a2735862306a9f7ed2821c94.
- After asset verification deployed the16-file existing static website to production:
  dpl_3rSnXMYS45Ke5Leo1Gc5eT9ZYFdX, READY; website-2z2160iy5-leoxuminghua-7962s-projects.vercel.app.
  Both ics-tex.vercel.app and the old embedded website-phi-beryl-92.vercel.app alias are current.
  Browser rendered Beta4, current checksums and real download links. No new project or Git integration.
- Live release.json and appcast exactly matched local files. Anonymous appcast HTTP200 with
  no-cache-staleness policy; independent public feed/archive signature verification passed.
  Feed SHA2562300e564f8760b2847de848ee68697928df3d0d210314dc3b2bdd482aff3a352.
  Installed210003 and offered210004 share the same feed URL/key. Collaborator's real automatic
  discovery/download/install/restart is not claimed; opt-in,30-second start delay,5-minute startup
  cooldown and busy/modal deferral remain. User confirmation still protects download/install.
- Evidence: local icstex-beta4-release/public-check/verified.json, signed-package-receipt.json,
  preflight-final/result.json, build.log and this turn's browser/API output. Preserved old assets,
  tags and installed Beta3; Actions stays disabled. No CI/rule bypass or force-push.
