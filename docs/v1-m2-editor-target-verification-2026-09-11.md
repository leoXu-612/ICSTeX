# V1 M2 secondary editor target ownership

Local source only, 2026-09-11. Multi-table and formula edits now retain explicit
target/base ownership through the existing Block session, draft and Undo seams.
Focused/native and final frozen-source full discovery passed. This is not complete
M2-M6 acceptance, crash recovery or a release.

## Implemented behavior

- The Inspector opens the selected table, not the first registry table. The
  table tab names its target and retains each pending table's model/local Undo
  and view position. Deleted/unknown targets are not replaced with another table.
- Cell/row/column edits stay as unapplied in-memory drafts. Live QLineEdit text
  participates in dirty state before the delegate commits it. Save, Apply,
  switching and close finish the existing input before deciding what to apply.
  Navigation and read-only checks never synchronize a table over registry data.
- Explicit table application and confirmed batches validate all captured bases,
  use one global command, and preserve unedited opaque fields by stable row/column
  IDs. Invalid table data refuses the whole batch. Local projection differences
  are not external three-way merge. Existing four-integer merge rectangles now
  match the schema; no format version or automatic migration was introduced.
- FormulaTab and Inspector use one captured-target dialog path. Cancel/no-edit
  do not normalize opaque formula content. A changed/deleted target refuses old
  accepted input and retains it as a reviewable draft. Global Undo stays bound to
  the edited object after selection changes. Closed sessions ignore late results.
- Pending table/formula drafts can reopen even when the original object was
  deleted. Discard confirms the exact draft still present after the modal. Draft
  chooser selection uses Python tuple equality rather than Qt QVariant identity.
- Image replacement checks the captured object after file selection, before
  copying, and again before the model command. The reproduced changed-target
  picker case now refuses the copy. Image import failure leaves the model intact;
  comprehensive asset-copy and native picker acceptance remain separate work.
- Enter queues Qt's normal delegate commit/close. An immediate Save or target
  switch now delivers only that delegate's already-queued MetaCall before any
  manual close, avoiding a second commit to a detached editor. This does not pump
  arbitrary GUI input events or suppress warnings.

Core rules: `app/core/blocks/property_draft.py`, `schema.py`. GUI ownership:
`app/gui/blocks/project_session.py`, `table_editor.py`, `workspace_widget.py`,
`formula_edit.py`, `formula_tab.py`, `inspector.py`, `commands.py`, `close_guard.py`,
`project_dialog.py`. Read-only status uses `submission_check_controller.py` and
`app/core/submission_check.py`. Regressions are in `test_block_editor_targets.py`,
`test_blocks.py`, `test_blocks_gui.py`, `test_ui_visual.py`; the native entry point
is `tools/probe_editor_targets.py`.

## Frozen-source verification

App Python path/content SHA-256:
`caac75122b49f7a0e283cf1a8203a1beaa62d5d458b9c67ad21eb24abc1b1625`.
macOS 26.6.1 arm64, Python 3.12.6, PySide6 6.11.1; native platform Cocoa.
Required compileall and `git diff --check` passed before final full discovery.

Focused command passed 170 tests in 91.731 seconds, exit 0:

```sh
QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest -v \
  tests.test_block_editor_targets tests.test_block_property_drafts \
  tests.test_block_session_safety tests.test_block_console_integration \
  tests.test_blocks_gui tests.test_gui_submission_check tests.test_ui_visual \
  tests.test_blocks tests.test_table_model
```

Receipt: `/tmp/icstex-v1-m2-editor-targets-focused-r4.log`.
The 22 target tests include real offscreen cell delegates, Enter-immediate-Save/
switch, Cancel, deleted/unknown/changed targets, formula modal simulations, late
acceptance, opaque data/zero/False, batch refusal, no-I/O checks and the image
picker reproduction. UI tests also check scroll-reachable table draft actions.

Final full command passed 1122 tests in 996.164 seconds, exit 0:

```sh
QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest discover -s tests -v
```

Receipt: `/tmp/icstex-v1-m2-editor-targets-suite-r2.log`.
The source hash above was rechecked after completion. No traceback, RuntimeError,
RuntimeWarning, fatal Python error or stale delegate commit warning appeared;
offscreen plugin warnings remain. Slow stylesheet/fixture-lifetime work is still
an open quality issue, not a performance pass. The process is now terminal.

Same-source native editor-target r5, property-draft r6, layout r8 and close r7 probes exited
0. Evidence directories are `/tmp/icstex-v1-native-20260911-m2-editor-targets-r5`,
`/tmp/icstex-v1-native-20260911-m2-property-drafts-r6`, and
`/tmp/icstex-v1-native-20260911-m2-layout-accept-r8`, and
`/tmp/icstex-v1-native-20260911-m2-block-close-r7`. All use temporary synthetic
projects and isolated settings. Terminal-launched Cocoa focus initially failed;
the probes now wait for real activation and the desktop tool selected only their
Python test application. Active-window and actual focused-editor assertions were
not bypassed. Native Qt keyboard events drive cells/formulas and confirmation
buttons; this is not a real IME test.

The multi-table probe verifies live-cell dirty state, separate targets and local
Undo, no implicit model/I/O/compiler changes, five scales, read-only saved FAIL,
confirmed batch Save, readback including False/opaque row data, real formula
Cancel/Apply/global Undo, actual FINAL and clean reopen. A simulated model edit
while the real formula dialog is open preserves both the new model and old
accepted draft. External metadata changes reject Save; close Cancel retains
state and Discard/late timers preserve the external bytes. Source FINAL, cursor,
nonzero scroll and original bytes survive.

The final-source one-page PDF visibly contains `First intended`, `Second intended`
and `x+4`, SHA-256
`9cd54006f5ec4de503dfe39ea14b218a44c490f7c149443b359daa9035734ba5`.
Actual FINAL, formula-conflict, external-write-conflict and 150% screenshots were
inspected on final-source r5. The 150% view is scroll-dependent and crowded, not
human usability pass.
The property and layout reruns preserve their earlier draft/pt/Undo/keyboard/PDF
assertions; their reports identify the same source above.
The close probe also verifies model Save-close-readback without compilation,
Cancel/Discard, conflicts, late callbacks and legacy owned-dialog closure. Its
one-page FINAL contains the saved draft; 5.869 ms dispatch and 230 heartbeat ticks
are one synthetic sample, not a general performance bound.

## Failed runs, superseded evidence and remaining work

- Initial target tests reproduced wrong-table routing, lost table drafts and
  stale formula overwrites. Live-cell tests then reproduced missing dirty state
  and Save bypass. Deleted-target selection exposed Qt tuple QVariant lookup;
  one separate test typo used `blocks_json` instead of the actual `blocks` field.
- Native editor r1-r3 failed before input because the Cocoa window was not active.
  An attempted PID-specific OS activation did not resolve it and was removed from
  the probe. r4 completed behavior but exposed two stale delegate commit warnings.
  Two focused red tests reproduced those exact warnings; all 22 target tests
  passed after the targeted fix (3.332 seconds), and native r5 has no such warning.
- Full r1 was explicitly superseded when this native-found source fix was added,
  not declared failed for being slow. Its owned process was interrupted; Qt caught
  SIGINT inside an event callback, so SIGTERM ended it with exit 143. Its partial
  log/KeyboardInterrupt is not acceptance evidence. Full r2 is the frozen run.
- Font-alias, accessibility table-bounds and TSMSendMessage input-service warnings
  remain. The contemporaneous crash-directory check showed only the two earlier
  September 10 Python reports, not a new crash. This is not repeated AX/IME stress
  or a causal explanation of earlier Qt crashes.
- Full-suite stylesheet cost remains open. The superseded full run spent minutes
  in `test_ui_scale.ScaleManagerTests.test_font_scales_from_base_without_drift`;
  the separate nine-test module passed in 6.648 seconds during the final run.
  This suggests suite-state/lifetime interaction, not proof of a memory leak or
  patch-specific app regression. The starting machine sample had load averages
  3.27/3.24/3.85 and 7987.50 MiB swap used; runs overlap short native/focused checks.
- A separate eight-test fixture-lifetime diagnostic passed in 4.607 seconds.
  Before tests there were no MainWindows/widgets. After tests, 8 closed
  MainWindows and 5782 widgets remained; GC plus DeferredDelete still left 8
  windows/5518 widgets. Explicit deletion of those synthetic test windows left
  no MainWindows and 7 widgets. This proves test-fixture retention and justifies
  bounded cleanup work, not an application-wide leak claim. The full-run sample
  `/tmp/icstex-v1-m2-editor-targets-suite-r2-sample.txt` again shows QApplication
  stylesheet work, 1.8 GB footprint and 2.0 GB peak. No test cleanup or app source
  was changed during final full discovery.
- Pending formula/table drafts are memory-only; M4 owns crash recovery. Unknown
  macro/source-mode fidelity, image import/path safety, native picker, IME/AX,
  Windows and human acceptance still need bounded verification. M3-M6 remain
  incomplete. No package, installation, Git write, signing or publication occurred.
- Next-slice synthetic reproduction: `project/assets/images` was a symlink to a
  sibling `outside` directory. `import_image` returned `assets/images/synthetic.png`
  but created matching image bytes outside the canonical project; original source
  bytes were preserved. This core import boundary remains unfixed. The picker
  revision guard does not protect this path; do not report complete image safety.
