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
- Migrated the authoritative workspace to
  `<HOME>/Desktop/Codex/ICS-Project-/ICSTeX`, preserving source,
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
