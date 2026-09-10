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
