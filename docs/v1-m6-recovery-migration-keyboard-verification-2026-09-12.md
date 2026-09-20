# Recovery, migration and standalone Block keyboard checks

Date: 2026-09-12. Three remaining five-tier checks pass, including a one-line
repair for the standalone Block tab bar. After the user confirmed manual
unlock, native r5 reproduced that gap and r6 verified the repaired entry at
100%/150%, actual Block FINAL/review/cancel, legacy-copy publication and 150%
checkpoint/recovery controls. The later window receipt closes the observed
migrated-window activation defect; OS-menu keyboard-only evidence remains open,
so this is not complete R2 acceptance.

## Source and assertions

Branch `codex/v1-development`, HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`;
shared changes remain uncommitted and the index is empty.
App (208 Python files):
`da2b8d242bf75091e7ed81ce6b4cb66e545c2544225421e52aa6ed77f1ec52c5`.
App+tests (327 files):
`78ef218e43e7b0f4f350a0a68fec691d3bc5817f4cb68a0068f4aa14c8d757f4`.
Digests use sorted repository-relative Python paths, NUL, bytes, NUL.
Environment remains macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1.

`tests/test_ui_visual.py::ModalWorkflowKeyboardTests` now has 13 methods:

- RecoveryDraftDialog: actual checkpoint/restore fixture, keyboard draft
  selection and text preview, forward/reverse traversal of all five controls
  at 90/100/110/125/150% in 900x640, explicit Cancel, no opened window or
  compilation, original/restored source and separate draft bytes preserved.
- Published migration: an actual new copy enables the source/open controls;
  confirmation is mocked only for this setup. Six post-copy targets are
  reachable in both directions at the same five scales, including the source
  selector. Actual popup Home/Down/Return changes the entry without requesting
  opening; original and copy bytes remain unchanged. This is not native picker
  or confirmation evidence.
- Standalone Block: the actual reusable workspace tab bar now has StrongFocus.
  At all five scales, Tab reaches it from Compile, Right selects Export, Tab
  reaches Prepare Submission, Space routes the exact owner/session, and reverse
  Tab returns to the labels. This focused entry test mocks the delivery dialog;
  r6 below verifies the actual dialog separately. The baseline fails at all five
  scales (1/1.787s, five failures); the one-line repair passes (1/1.576s).

Both exercise the process-local text/list Tab policy observed on this Mac;
the OS preference is unchanged. Restoring only the selector's old TabFocus
policy in a disposable process produces five scale failures plus a reverse-Tab
failure (1 test, 4.447s, exit 1). Replacing only its Return handler with the
base QComboBox handler still passes this particular post-copy case (1/1.721s,
exit 0); that control is **not** Return red/green evidence. The earlier
creation/profile Return reproductions retain their separate scope.

## Waiting-harness diagnosis

The new post-copy test initially timed out twice before keyboard assertions.
A third observer showed the live publication worker still reading verified
staged files. With the same 8-second deadline and assertions, using the existing
migration suite's `processEvents()` plus 3ms Python sleep completed inventory,
review and publication in 0.0256/0.0146/0.0183s; the test passed in 1.907s.
Only the modal test helper adopts that yielding wait. No timeout increase,
weakened file assertion or worker shortcut was made for this harness issue.
This controlled harness observation does not establish a product copy deadlock.
The test-triage skill guided the smallest failure and explicit control.

## Terminal test evidence

All paths below are local `/tmp/` logs, not published artifacts:

- `icstex-v1-recovery-keyboard-focused-20260912-r1.log`: 1/3.677s/OK.
- `icstex-v1-modal-keyboard-expanded-20260912-r6.log`: 56/35.460s/OK,
  before the post-copy test/helper change.
- `icstex-v1-modal-keyboard-expanded-20260912-r7.log`: 57/31.057s/OK,
  exec 69247 exit 0; SHA-256
  `cc347c8c18ec2776e43d4ef40e27972dfa891e70cf97061b9ca96b13998d18c9`.
- Retained diagnostics: `icstex-v1-recovery-migration-keyboard-focused-20260912-r1.log`,
  `icstex-v1-migration-keyboard-focused-20260912-r2.log`,
  `icstex-v1-migration-keyboard-observer-20260912-r1.log`,
  `icstex-v1-migration-keyboard-yield-control-20260912-r1.log`,
  and `icstex-v1-migration-keyboard-{return,focus}-negative-20260912-r1.log`.

- Before the Block repair, full r5 passed 1585/296.574s, exec 43157 exit 0,
  on app `700b9b83` / app+tests `b73eb852` (not the final source above).
- Final affected modules: 76/29.178s/OK, exec 45376 exit 0;
  `/tmp/icstex-v1-standalone-keyboard-expanded-20260912-r1.log`.
- Required final compileall and full: 1586/318.535s/OK, exec 73414 exit 0;
  `/tmp/icstex-v1-modal-keyboard-full-20260912-r6.log`, SHA-256
  `a887c35860ae0052c168952fca29f3d410fbd737700e9eadebacdd775fb0b8eb`.
  Both source digests were rechecked after the terminal result and native exit.

## Native r5 and r6

Probe `tools/probe_modal_keyboard.py` SHA-256
`7c8c95f13798eef790c3b6d939687901640131f5c13ad5be5e4c38f47eef634b`.
Logs, screenshots and observer records are local synthetic evidence, not release
artifacts. CUA supplied keyboard events; QA fixture/scale and product menu entry
used explicit AX activation. No OS setting or AX field-value correction was used.

- r5, `/tmp/icstex-v1-modal-native-20260912-r5`, app `700b9b83`:
  standalone Tab skipped the page labels and jumped to Compile. No build/output.
  Exec 35671 exit 0; 8 states, 73 propagated key records, no errors or timeout,
  both tracked windows destroyed. Report SHA-256
  `3331294fcae96d6391dc56a4023b9b1ca6a6fb1cd0e37a1c5ec8703d5f72903a`.
- r6, `/tmp/icstex-v1-modal-native-20260912-r6`, final app above:
  exec 16458 exit 0; 104 states, 990 propagated key records (not 990 distinct
  physical presses), no errors/timeout/interruption, both tracked windows
  destroyed. Application digest equal before/after. Report SHA-256
  `8551a6da2afc764e9b9cb4a8430661b7f6029ec43f39ced3e4ea3de5b743f482`.
  Finish-menu CUA observation timed out after quit, but the same process handle
  reached terminal exit 0 and wrote its report; no restart was needed.

### Observed product paths

1. Standalone Block at 100% and 150%: Shift-Tab/Right/Tab/Space reaches Export
   and opens actual SubmissionDeliveryDialog for r6 `fixtures/block`. At 150%,
   explicit keyboard FINAL and submission check produce a 3464-byte PDF,
   SHA-256 `692b0929c9d1f18fdca05b1f84232a0edaa6cff449bfaca289983315593242f3`.
   The static-coverage unknown is read, not relabelled pass. Tabs, output preview,
   acknowledgement and source/report options are reachable. The real save panel
   uses typed name, Cmd-Shift-G, typed parent and keypad Enter; default-No Return
   cancels publication. `cancelled-block-delivery-150` remains absent.
2. Legacy migration at 150% and 100%: original folder picker, check/uncheck,
   original/candidate review and publication confirmation are keyboard-operated.
   Five original files produce twelve candidate files; `customMetadata` stays
   explicitly unmapped. Raw old snippets remain untrusted; `encoding-note.tex`
   preserves its 12 non-UTF-8 bytes. At 150%, the native target picker is operated
   by keyboard; default No is verified before explicit Yes publishes
   `legacy-keyboard-copy`. At 100%, a typed Qt target publishes
   `legacy-keyboard-copy-100`. Both retain all five original evidence files,
   zero drafts and no compile outputs. Original hashes remain unchanged.
3. Post-copy source selection with Space/Return does not request opening.
   At 100%, the separate open confirmation defaults No and cancellation is
   observed. A later Yes closes the migration dialog, but CUA and the observer
   did not establish a visible independent migrated window. This last step is
   **not passed**. A one-second process sample shows an idle native event loop,
   not evidence of a hang; the original window remains responsive. Preserve both
   copies for the next bounded window-visibility/lifetime diagnosis.
4. At 150%, RecoveryDraftDialog loads the retained r4 restored container via
   the native keyboard picker, verifies three files/one draft, allows keyboard
   selection and full draft preview, and exposes separate confirmation with
   default No. Return cancels; forward/reverse traversal and explicit Close work.
   Checkpoint restore reads the retained archive, selects the independent draft,
   reaches target/picker/action and cancels default No. Creation traverses
   Add/Select All/Clear/list/preview/target/action and cancels default No.
   `cancelled-restore-150` and `cancelled-create-150.icstex-checkpoint` are absent.
   No accepted ordinary archive/restore workflow was recreated.

The retained archive SHA-256 is still
`aebb07557de84710ff352849b4f15e474b6e01bc9ab2b96d3e17883e53d2e009`;
original/restored main.tex remains
`f141642cb5dfa0eeb2e73274cd2f125439c9cf8e58122e805d34d5cfc3dfc1ce`;
the separate draft remains
`cde7672c0253983bed029d47d5e5885d95a80f6a68d3ecc966662a1af91fa9be`.
All eleven retained Python crash reports are unchanged.

## Remaining boundary

Native NSMenu routing is not keyboard-only evidence: Ctrl-F2 did not focus the
menu, and Escape while a menu was open reached the underlying Qt migration
dialog. Its resulting closure is retained as mixed-input evidence, not a product
crash or successful copy opening. AX Cancel cleaned up the menu. Do not infer
that human keyboard menus are broken from this CUA routing behavior.

The subsequent [window check](v1-m6-migration-window-verification-2026-09-12.md)
establishes actual offscreen confirmation and dialog-disposal lifetime with a
hidden-window control. Native r2 then proves owner reactivation; the narrow
post-modal activation fix passes focused red/green and native r3. Do not repeat
that closed case. The OS/menu evidence boundary remains unresolved; do not replay
accepted workflows or infer a product menu defect from CUA routing. Prior results remain in
[the modal receipt](v1-m6-modal-keyboard-verification-2026-09-12.md).
R3 reliability disposition, R5 restricted LuaLaTeX decision and E1-E4 remain.
No Git mutation, packaging, install replacement, release or student-file edit.
Suggested commit only: `fix(gui): make standalone Block delivery keyboard reachable`.
