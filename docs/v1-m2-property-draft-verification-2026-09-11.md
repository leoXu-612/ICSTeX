# V1 M2 pending property drafts

Local source only, 2026-09-11. This slice protects unapplied Inspector properties
without replacing the Block ProjectSession, command stack, writer, format or
Source/PDF ownership. It is not disk crash recovery or complete M2-M6 acceptance.

## Implementation paths

- Pure captured-base and field rules: `app/core/blocks/property_draft.py`.
- Draft lifetime, command application and Inspector UI:
  `app/gui/blocks/project_session.py`, `commands.py`, `inspector.py`, `close_guard.py`.
- Existing workspace/FINAL/selection/layout wiring: `app/gui/block_mode.py`,
  `app/gui/blocks/project_dialog.py`, `workspace_widget.py`, `layout_panel.py`,
  `selection.py`, and `app/gui/workspace_controller.py`.
- Read-only readiness: `app/core/block_submission.py`, `submission_check.py`,
  and `app/gui/submission_check_controller.py`.
- Regression and native receipts: `tests/test_block_property_drafts.py`,
  `test_gui_submission_check.py`, `test_blocks_gui.py`, and
  `tools/probe_property_drafts.py`; existing layout/close probes were rerun.

## Implemented behavior

- Unapplied Block properties and layout properties have a captured target/base,
  initial displayed fields and explicit changed fields. Typing does not mutate
  the model, save files, authorize compilation or start a check worker. Pending
  properties participate in session dirty state and invalidate old check results.
  Automatic save/preview timers wait while properties remain unapplied.
- Refresh and selection changes preserve pending properties. Text documents and
  their local Undo/cursor are retained while their drafts exist; clean off-target
  document buffers are released. The pending list can reopen a draft whose target
  was deleted. Alias, text/raw LaTeX, heading, image size/caption and layout fields
  are covered. No unedited field is rewritten just because its widget rounded it.
- Apply validates the exact original object before creating one model command.
  Explicitly confirmed batches check every base before applying any patch and
  use one Undo command. A changed/deleted object or invalid alias refuses the
  batch and keeps all drafts. No automatic merge/rebase or overwrite is offered.
  A conflict can be reviewed/copied or explicitly discarded before editing again.
- Discard requires confirmation and affects only that object's unapplied fields.
  Save/close/FINAL explicitly state when all pending properties will be applied.
  Cancel retains them. Confirmation revision checks reject newer unreviewed input;
  re-entrant input during application is not cleared or silently saved. A failed
  disk save keeps the now-applied unsaved model and external bytes intact.
- Direct save/assembly/FINAL methods do not bypass pending properties. Visible
  Save and FINAL resolve them explicitly. Checks remain read-only and cannot pass
  saved/FINAL freshness while a property draft exists. The workspace and PDF banner
  distinguish the applied model from pending properties.
- Layout Inspector fields now belong to the selected container (or the selected
  slot's parent), not always the root. Applying layout properties updates the
  existing layout panel through a blocked presentation refresh. pt gaps display
  in mm; changing alignment/fallback preserves untouched gap units and values.
  Lower-panel immediate edits also change only the selected property.

## Verification

Final app Python path/content SHA-256:
`e675b187e1b02c5b69afd8730d9c53b073e56f7d38fb72eae79859145e43970d`.
Platform: macOS 26.6.1 arm64, Python 3.12.6, PySide6 6.11.1, native Cocoa.

Focused command passed 115 tests in 91.311 seconds, exit 0:

```sh
QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest \
  tests.test_block_property_drafts tests.test_block_session_safety \
  tests.test_block_console_integration tests.test_blocks_gui \
  tests.test_gui_submission_check tests.test_ui_visual
```

Log: `/tmp/icstex-v1-m2-property-drafts-r5.log`. A final EOF-only whitespace cleanup
followed this focused run; the native/full source identity is recorded above.
Required compileall and `git diff --check` passed. Full frozen-source discovery
passed 1098 tests in 1677.963 seconds, exit 0:

```sh
QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest discover -s tests
```

Log: `/tmp/icstex-v1-m2-property-drafts-suite-r1.log`. No app source changed during
the run. No Python traceback, RuntimeError, RuntimeWarning or fatal Python error
appeared; offscreen plugin warnings remain. The long duration is an unresolved
quality signal, not a performance pass. It exceeded the preceding 539.011-second
full run; the samples and attribution limits are recorded below.

The 21 new property tests cover no-I/O refresh, cross-selection text Undo,
single/batch Apply and Undo, all-field preservation, deleted targets, cancelled
discard/close/save/compile, stale bases, batch refusal before any edit, external
disk conflicts, re-entrant input, changed confirmations, late closed-session edits,
nested layout ownership and pt unit preservation. Submission-check integration
also verifies immediate invalidation and no false saved pass from pending fields.

Three final-source native runs exited 0:

```sh
QT_QPA_PLATFORM=cocoa python3 -X faulthandler tools/probe_property_drafts.py \
  --output /tmp/icstex-v1-native-20260911-m2-property-drafts-r5
QT_QPA_PLATFORM=cocoa python3 -X faulthandler tools/probe_block_layout.py \
  --output /tmp/icstex-v1-native-20260911-m2-layout-accept-r7
QT_QPA_PLATFORM=cocoa python3 -X faulthandler tools/probe_block_close.py \
  --output /tmp/icstex-v1-native-20260911-m2-block-close-r6
```

All use disposable synthetic projects and isolated settings. The property probe
enters text with native Qt keyboard events, switches between two Blocks, refreshes
and waits 800 ms with no model command, compiler or file changes. It also edits a
layout property as a separate draft, keeps Apply/Discard fully reachable by scroll
at five scale tiers in a 1080x720 window, and verifies a read-only saved-state FAIL.

Actual message boxes are answered by keyboard Space: Cancel retains the draft,
Save explicitly applies the two property drafts as one command without compiling,
and later Save-close applies a new draft that reopens without a compiler. The pt
gap remains 72.27 pt while the Inspector displays 25.40 mm. Explicit FINAL visibly
contains `Native property draft`; PDF and Save-close screenshots were inspected.
The final-source 150% pending-state and external-conflict screenshots were also
inspected; the conflict explicitly retains memory and external-file versions.
The retained one-page `property-final.pdf` SHA-256 is
`57ee2d8059ab29b071aa052102d67d85b95fa8be9cdbc7bdc3c282a383552568`.
An external metadata winner causes Save failure; the desired text remains visible,
Cancel preserves the window, and confirmed Discard/late callbacks do not change
the external file. Source's FINAL, cursor, nonzero scroll and original bytes survive.

The same-source layout probe repeats both window sizes and five scales, local
text Undo/Redo, literal Tab, Control+Tab, one global Apply/Undo/Redo and actual PDF
switching. The close probe repeats model Save/Cancel/Discard, reopen, conflicts,
legacy owned-dialog cancellation and late callbacks. Its small-sample FINAL
dispatch was 9.259 ms with 305 GUI heartbeat ticks, not a general performance claim.

## Failed runs and limits

- The initial property red run reproduced lost text/selection state, missing dirty
  tracking and unprotected close/save/compile. A focused integration failure then
  exposed the changed `block_updated` notification contract and duplicate deferred
  requests. The existing notification is retained and timers resume without
  broadcasting a second save/preview request.
- A transient new import error placed QPlainTextDocumentLayout in QtGui; it was
  corrected to the installed QtWidgets API before acceptance. Separate pt red
  tests reproduced 72.27 pt being displayed as 72.27 mm and now protect both UIs.
- Native r1 was refused while constructing an invalid synthetic second Block
  (missing text format), before user workflows ran. The fixture now uses the
  existing valid text constructor. Native r2 lacked active input focus; subsequent
  runs activate and assert the actual window/focused editor before keyboard input.
  Earlier successful source runs are superseded by the exact final-source runs.
- Font-alias warnings remain, and the property probe emits the known accessibility
  table-bounds warning. No new Python crash report appeared in the contemporaneous
  directory check. These are not real IME, AX stress, Windows or human acceptance.
  Earlier timer SIGSEGV causality and the previous suite/stylesheet performance
  signal remain open for M6, not closed by these functional tests.
- During this full run, a one-second live sample again found the main thread in
  QApplication stylesheet/CSS work, with a 2.1 GB footprint and peak. The receipt
  is `/tmp/icstex-v1-m2-property-drafts-suite-sample-r1.txt` (00:40:09 local time).
  This is whole-suite state, not an isolated app benchmark or proof of a leak;
  the run also overlapped bounded read-only diagnostics. M6 must isolate widget
  lifetime and style-application cost with comparable inputs. A later 00:47
  system sample reported load averages 10.44/11.36/12.65 and approximately
  9.6 GB swap in use on a 16 GB machine; no comparison-machine baseline was
  captured, so the elapsed-time change is not attributed solely to this patch.
- Drafts currently live in memory; process crash/power-loss recovery belongs to
  M4. Save failure preserves model/Undo data but is not a completed project
  checkpoint. M3 provenance, M4 restore and M5 frozen delivery remain incomplete.
- A subsequent read-only, synthetic two-table reproduction confirmed a separate
  target-ownership defect: selecting the second table and clicking the Inspector's
  full-table button still shows the first registry table; a cell edit updates that
  first table and leaves the selected second table unchanged. The session had no
  project directory and no compiler. `ensure_table_model` and
  `sync_table_to_registry` both select the first table; the Inspector only changes
  the workspace tab. This remains unfixed and is the next bounded M2 slice, not
  covered by the property-draft acceptance or a passing full suite.
- A separate pure in-memory modal simulation confirmed the formula button also
  lacks a current-target revision guard: start from `x+1`, change the registry
  target to `x+7` during the dialog, then accept its `x+2` plan. The target becomes
  `x+2` without rejecting the changed base. No compiler or project directory was
  present. This is a simulated interleaving, not native concurrent-user evidence;
  it remains unfixed. Image replacement's related modal path has not been tested.
- No commit, push, rename, package, installed-app replacement, credentials,
  signing, deployment or publication. The independent Beta activation hold remains.
