# V1 M2 project creation and workspace slice

Local source only, 2026-09-10. M2 is not complete. This slice connects existing
creation, source editing, FINAL, submission checks and PDF export; it does not
implement project checkpoints, frozen delivery or safe pending Block close.

## Implemented boundaries

- The project wizard preserves Chinese names, previews the actual destination
  and template, offers an explicit engine choice and an optional editable profile,
  and explains missing-tool/first-compile behavior. An existing workspace defaults
  to keeping its window. Cancel does not create files. Creating/opening does not
  authorize compilation or install TeX; ordinary background Word Count is retained.
- Templates and profiles are validated before filesystem mutation. Only a new
  destination is accepted, including rejection of existing empty directories and
  symlinks. Files use exclusive creation and read-back verification. A failed
  partial creation remains clearly labelled and unopened; partial new files are
  deliberately retained instead of recursively deleting possible external edits.
  This is not an atomic multi-file project transaction.
- A full-width workspace row shows visible project/mode, cached compile root,
  save state, engine, PDF purpose/freshness and check counts. It does not create
  managers or rescan source while refreshing. Unknown coverage stays unknown.
  Ordinary-source navigation reuses existing files/outline/materials/references/
  history/insertion panels. Child navigation retains canonical project scope.
- Source save/compile/export actions reuse existing guards. Block presentation
  uses the visible session, not the hidden source tab. Source-only engine/auto-
  compile controls stay hidden through toolbar relayout. Closing a clean Block
  project restores source controls and its existing FINAL. This does not accept
  pending Block edits, external metadata conflicts or whole-window close safety.
- Templates, formula/table/image editors, compiler and PDF stores retain their
  ownership. The row is presentation, not a new authoritative ProjectSession;
  D010 remains Proposed. Existing-project profile recommendations still do not
  automatically switch engines or create directories.

## Verification

Focused command, exit 0, 203 tests in 26.188 seconds:

```sh
QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest -v \
  tests.test_project_tools tests.test_gui_editor tests.test_gui_submission_check
```

Local log: `/tmp/icstex-v1-m2-workspace-focused-r6.log`.
Required compileall and `git diff --check` passed. Final full discovery
(`QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest discover -s tests`)
passed 1042 tests in 396.325 seconds, exit 0; log
`/tmp/icstex-v1-m2-workspace-suite-r2.log`. No traceback, RuntimeError,
RuntimeWarning or fatal Python error was present in that output. Offscreen
size-hint/keyboard warnings remain; the earlier native crash uncertainty below
is not closed by this result.

Native command, exit 0:

```sh
QT_QPA_PLATFORM=cocoa python3 -X faulthandler tools/probe_workspace_flow.py \
  --output /tmp/icstex-v1-native-20260910-m2-workspace-r6
```

macOS 26.6.1 arm64, Python 3.12.6. App Python path/content SHA-256:
`9d713aa8350aa690ff9b6e516b35cdc78c179f8c7cff83a916fae0a5590a5be9`.
The real modal wizard was operated with keyboard Space. A Chinese XeLaTeX
template created a new Chinese-path project without compiling. Explicit FINAL
produced one displayed PDF page. Saved/root/toolchain/FINAL/PDF/log checks passed;
input coverage remained unknown and the unset word target was not applicable.
The existing export action copied byte-identical FINAL output, and reopening in
a second window did not compile. Source bytes remained unchanged. The PDF chooser
was supplied a synthetic temporary destination; it is not human chooser evidence.

Creation/source/Block windows were captured at 90/100/110/125/150 percent.
Block header refresh did not create a compiler or write files; clean close
restored the source FINAL. Raw screenshots and report remain local. Main-agent
inspection confirmed readable full-width Block identity at 150 percent; the
surrounding Block editor/inspector still clips and is explicitly not accepted.
The wizard keeps its buttons outside its scrollable form at high scale.

## Failed runs and evidence limits

- Initial tests incorrectly treated background TeXcount as a compiler launch and
  assumed opening a file had created a CompileManager. The former assertion now
  targets actual compile entry points; the latter exposed a real header bug,
  fixed by reusing the dependency controller's already-resolved tab/root cache.
- Clean Block close initially left source controls hidden. Native show/scale
  then exposed QWidget visibility being undone by toolbar layout; visibility is
  now controlled by the owning QWidgetAction. The final native probe waits for
  layout before asserting restored widget visibility.
- Earlier focused runs ended in a Qt timer-dispatch SIGSEGV, including
  `Python-2026-09-10-134729.ips`. Later focused/native runs passed after assertion
  and cleanup corrections, but the crash's causal chain is not conclusively
  established. This remains an M6 lifecycle investigation, not a claimed fix.
- A superseded full run was stopped after subsequent source fixes. Repeated
  global stylesheet changes in the large shared GUI test process were expensive;
  a native sample showed QApplication stylesheet/layout work. Unit coverage now
  tests real show/resize/toolbar ownership locally; the isolated native probe
  still exercises all five actual UI scales. This is not a product performance
  improvement claim.
- Native logs contain IMK wake-up, accessibility table-bounds and font-alias
  warnings. No claim of IME/AX acceptance follows from the probe's exit status.

## Next boundary

Continue M2 with Block high-scale reachability and pending-edit/close/conflict
handling. Preserve both the in-memory draft and external disk winner; do not
silently stop timers or force an unguarded save. Keep actual Source/PDF cursor,
viewport, keyboard/Undo and lifecycle checks. M3-M6, Windows and human acceptance
remain unfinished. M4/M5 still own consistent recovery and frozen delivery.
No commit/push, package, installed-app change, signing, deployment or publication.
