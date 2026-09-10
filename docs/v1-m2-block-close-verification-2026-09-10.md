# V1 M2 guarded Block save and close slice

Local source only, 2026-09-10. This slice keeps the existing Block ProjectSession,
formats, command/Undo stack, compiler and separate Source/PDF ownership. It is
not a universal session, a completed M4 checkpoint, frozen delivery or release.

## Implemented behavior

- Opening captures supported metadata and generated-source ownership before
  editing. Unknown/lossy metadata, hand-edited generated files, unsafe paths and
  existing pending write evidence refuse replacement. Bounded, link-safe reads
  replace the old direct metadata reads. Incomplete in-memory drafts may remain
  visible; unknown table data is not silently converted to an empty table.
- Save writes the model and its generated TeX in one guarded batch, without
  starting or authorizing a compiler. This is necessary for a clean reopen to
  recognize its own generation. Changed-only writes preserve unchanged files;
  prior explicit compilation still permits debounced previews in this session.
- The existing cooperating project lock, before/after byte rechecks, same-directory
  replacement and POSIX directory anchoring protect the write path. Before/after
  bytes and hashes are staged before project replacement, with a 64 MiB combined
  evidence budget, 2,000 payload-file limit and existing per-file read limit.
- Failed writes conditionally roll back only bytes still owned by this write.
  A new external winner is never force-restored. Unresolved or partially staged
  `.icstex/block-write.pending` evidence blocks retry/reopen writes; original and
  desired bytes remain available where staging reached them. No automatic cleanup
  or recovery is offered for unknown/partial evidence. Storage failure during
  staging leaves project files unchanged but may require later explicit recovery.
- Block close and whole-window close ask Save/Discard/Cancel before shutting down
  sessions. Automatic Block writes are paused throughout Source and Block close
  prompts. Cancel keeps the draft; failed Save keeps the window and both versions;
  Discard drops only unsaved memory, not prior autosaves or external files.
- Stop cancels compilation without closing the editing session. Confirmed shutdown
  suppresses late timers/results. The owned legacy dialog uses the same close gate;
  a dialog sharing a MainWindow session does not own its shutdown.
- Block menu/header Save, FINAL and Stop actions use the visible Block session.
  Visible FINAL launches the existing background compiler; synchronous FINAL is
  retained only for compatibility/probes. Source-only actions do not overwrite the
  Block state, and returning to Source restores its prior PDF and cursor/scroll.

## Verification

App Python path/content SHA-256 for the final native runs:
`4c0b3b607adaec9aea9340c6f8bb25206e10cc99cb9cfd490532bd3864cbcd0d`.
Platform: macOS 26.6.1 arm64, Python 3.12.6, Qt Cocoa.

Focused command, exit 0, 255 tests in 24.633 seconds:

```sh
QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest -v \
  tests.test_block_project_write tests.test_block_session_safety \
  tests.test_block_console_integration tests.test_block_compile_pipeline \
  tests.test_blocks_gui tests.test_gui_submission_check tests.test_gui_editor
```

Log: `/tmp/icstex-v1-m2-block-focused-r6.log`. This includes before/after write
faults, rollback conflicts, staging failure, symlink reads, unknown versions,
model reopening, late callbacks, both Source/Block close cancellation and actual
MainWindow controller preservation. It does not replace native acceptance.
Required compileall and `git diff --check` passed. Full discovery passed 1068
tests in 389.469 seconds, exit 0, using
`QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest discover -s tests`.
Log: `/tmp/icstex-v1-m2-block-suite-r2.log`. No Python traceback, RuntimeError,
RuntimeWarning or fatal Python error appeared; offscreen plugin warnings remain.

Native command, exit 0:

```sh
QT_QPA_PLATFORM=cocoa python3 -X faulthandler tools/probe_block_close.py \
  --output /tmp/icstex-v1-native-20260910-m2-block-close-r4
```

The probe uses disposable synthetic projects and isolated settings. Model edits
go through the existing UI command controller, not a simulated student or IME.
Real QMessageBoxes are operated with keyboard Space. Cancel pauses writes for
650 ms and resumes the pending draft; Save persists a matching model/generation
that reopens without compiling. Source PDF, cursor and scroll are preserved.

Visible Block FINAL dispatched in 2.450 ms for this small sample; 97 GUI heartbeat
ticks occurred during real compilation. One PDF page with the expected draft was
visibly rendered. This is a small-sample observation, not a general performance
claim; generation/preflight still run before the asynchronous compiler launch.
FINAL SHA-256: `f828a65f684839173d3c4ef9a6dc40b910071e25e2094816c5c42b6c069d87cd`.
The PDF's extracted text also contains the exact saved draft; the synthetic PDF
is retained as `block-final.pdf` in the evidence directory.
Source's existing PDF record remained separate. Compile/Stop actions returned to
the completed state after worker exit.

At 150% scale, an actual external metadata edit caused Save-on-window-close to
fail, leaving the window, memory draft and external winner intact. Explicit
Discard followed by late callbacks and 750 ms of event processing caused no
further write. Owned-dialog Escape/Cancel and close/Discard preserved its draft
or discarded it explicitly, without creating its not-yet-saved project directory.
Final/Cancel/error/retained-draft screenshots from same-source r3/r4 were inspected
by the main agent.

The existing creation/workspace probe also passed on this same app source:
`/tmp/icstex-v1-native-20260910-m2-workspace-r7`, exit 0. Actual Chinese project
creation, one-page FINAL, checks, byte-identical PDF export, second-window reopen
and clean Block close passed; Source files stayed unchanged. Its older generic
"close workflow pending" limit refers to that probe's clean-close-only scope;
pending-close evidence is supplied separately above. Input coverage stays unknown.

## Reproduced failures and remaining limits

- Initial guarded save wrote only metadata. Native close/save/reopen reproduced
  a false external-source conflict, also captured by a failing regression test
  (`/tmp/icstex-v1-m2-block-reopen-red.log`). Save now persists the corresponding
  guarded generation. The checker test now expects matching generated bytes after
  Save, while still asserting that no compiler exists and FINAL is not passed.
- A legacy malformed table draft initially became an empty supported table.
  Validation before table-model construction now preserves the unknown content
  and refuses saving it; the red/green safety runs retain that evidence.
- The superseded full run was intentionally stopped after the reopen fix became
  necessary. Its interrupt traceback and exit 143 are not successful validation
  or a new native crash. Final-source validation is recorded separately.
- Block central/editor/inspector contents still clip, including narrow middle
  columns at 100% and lower controls at 150%. Header and close dialogs being
  accessible does not establish full M2 workbench or keyboard acceptance.
- The close probe logged a font-alias warning. The same-source workspace probe
  logged an accessibility table-bounds warning and font-alias warning. Neither
  final native log contains a Python traceback/RuntimeError/RuntimeWarning; no
  new Python crash report was found in the contemporaneous directory check.
  Earlier timer-dispatch SIGSEGV causal uncertainty, IME/AX stress, Windows and
  human acceptance remain open; this is not a claimed lifecycle fix.
- Multi-file writes are not one OS-atomic transaction against arbitrary external
  editors, and no process-kill/power-loss recovery is accepted here. Partial
  journals remain held for M4's explicit recover-to-new-directory workflow.
  M3 materials/citations, M4 recovery, M5 frozen delivery and M6 remain incomplete.
- No commit, push, package, installed-app change, credential operation, signing,
  deployment or publication. The independent Beta activation gate is unchanged.
