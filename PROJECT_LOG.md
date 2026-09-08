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
