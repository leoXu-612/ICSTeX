# Modal keyboard safety and ordinary delivery/recovery

Date: 2026-09-12. **Four concrete keyboard defects are repaired. Ordinary
PDF delivery and independent-draft recovery have native product evidence;
the complete R2a–c keyboard/scale acceptance is still open.**

## Source and scope

Branch `codex/v1-development`, HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`.
The shared worktree remains uncommitted; the index is empty. No Git mutation,
package, installed-app replacement, publication or student-file edit occurred.

Final application tree (208 Python files):
`700b9b832978d2eec3104ab83cc0c465507fa58f844f354bdc4036c154e7db6f`.
Application plus tests (327 files):
`d9445b7087e225e30ea1697cbfb794c9147a72a3f38ce1db07c2e5136f0fa731`.
Digests use sorted relative Python paths, NUL, bytes, NUL; both matched after
the final native process exited. Environment: macOS 26.6.1 arm64, Python 3.12.6,
PySide6/Qt 6.11.1. This is not an installed-build or Windows identity.

## Reproductions and repairs

- Profile directory suggestions inserted Tab instead of leaving the multiline
  field. Five scale-specific failures were reproduced after correcting unrelated
  fixture assumptions. `setTabChangesFocus(True)` preserves multiline editing,
  Undo/Redo, Cancel and explicit Save without changing source files.
- Under this Mac's text/list-only tab policy, noneditable template/engine/source
  combos were skipped. Native r1 stopped before creation. A process-local policy
  simulation and negative control reproduced the skipped targets. StrongFocus
  is now limited to the five affected dialog combos; no OS preference changed.
- Native r2 showed Return selecting a popup item and then implicitly creating
  the project. The event receipt shows Return reaching the combo and parent
  dialog. Four creation/profile Return/Enter failures reproduced it offscreen.
  `DialogComboBox` retains normal combo handling but consumes Return/Enter before
  it can confirm the parent. Closed-combo and actual popup selection tests pass;
  native r3 confirms selection leaves the form open and explicit button Return
  still creates/saves. No global shortcut or dialog-default policy was changed.
- Delivery and migration tab bars also had TabFocus rather than StrongFocus.
  Ten failures across five scales reproduced missing keyboard access under the
  same policy. Only these two tab bars now use StrongFocus. Tab access, visible
  bounds and Left/Right page changes pass; native r4 verifies delivery pages.

The mechanism matches official Qt 6.11.1 implementation: restricted tab
navigation requires StrongFocus; combo popup selection can finish during
ShortcutOverride, while the subsequent Return is ignored by a noneditable
combo and can reach a dialog default. Sources:
[focus traversal](https://github.com/qt/qtbase/blob/v6.11.1/src/widgets/kernel/qapplication.cpp),
[combo event handling](https://github.com/qt/qtbase/blob/v6.11.1/src/widgets/widgets/qcombobox.cpp).

Changed product files: `app/gui/dialog_combo_box.py`, `project_panels.py`,
`project_profile_dialog.py`, `project_migration_dialog.py`,
`submission_delivery_dialog.py`. Tests are in
`tests/test_ui_visual.py::ModalWorkflowKeyboardTests` (10 methods).
`tools/probe_modal_keyboard.py` observes keys/states and opens only synthetic
fixtures; optional retained-fixture reopening does not compile or confirm forms.

## Terminal regression evidence

All logs below are under `/tmp/`; retain their distinct source identities.
An earlier enum-OR TypeError was a test setup error, not a product failure.
The first mixed red also incorrectly expected changing read-only previews to
remain identical; corrected red isolates the directory-field defect.

| Run | Result |
| --- | --- |
| `icstex-v1-modal-keyboard-red-20260912-r2.log` | 5 tests, 16.015 s, 5 profile Tab failures |
| `icstex-v1-modal-combo-focused-20260912-r1.log` | 1 test, 0.483 s, OK |
| `icstex-v1-modal-combo-negative-20260912-r1.log` | 1 test, 0.367 s, 3 expected baseline failures |
| `icstex-v1-modal-return-red-20260912-r1.log` | 1 test, 0.731 s, 4 Return/Enter failures |
| `icstex-v1-modal-return-focused-20260912-r1.log` | 1 test, 0.641 s, OK, including popup selection |
| `icstex-v1-modal-tabs-red-20260912-r1.log` | 1 test, 2.420 s, 10 tab-bar failures |
| `icstex-v1-modal-tabs-focused-20260912-r1.log` | 1 test, 2.354 s, OK |
| `icstex-v1-modal-keyboard-expanded-20260912-r5.log` | 81 tests, 40.113 s, OK, exec 77025 exit 0 |
| `icstex-v1-modal-keyboard-full-20260912-r4.log` | 1583 tests, 297.883 s, OK, exec 29022 exit 0 |

Expanded command: `QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m
unittest tests.test_ui_visual.ModalWorkflowKeyboardTests
tests.test_gui_submission_check tests.test_project_profile
tests.test_submission_delivery_gui tests.test_project_checkpoint_gui
tests.test_project_migration_gui -v`.
Required compileall, full `unittest discover -s tests`, probe syntax and
`git diff --check` passed. Expanded log SHA-256:
`7763da05055464fbebb7fdc546360060b63b9ab0bb3a8b9f350f819ddc54dea8`.
Final full log SHA-256:
`952af0e3b99535b69e9382973471bf50197ec7ff5d6bc8b39dbfe2fb0d1dc752`.
Earlier full runs 1580/251.666 s, 1581/277.486 s and 1582/282.918 s passed before
the subsequent repairs; they are not substituted for the final run.

## Native evidence and exact limits

All sessions used `QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3
tools/probe_modal_keyboard.py --output <new directory>`, synthetic data and
isolated settings. CUA supplied native input. The observer did not synthesize
keys, confirm dialogs or fake FINAL evidence. Qt event propagation creates
multiple records for one physical key; event counts are not action counts.

- Native r2, `/tmp/icstex-v1-modal-native-20260912-r2`: terminal exit 0,
  no observer errors, no timeout; retained the implicit-create defect. App
  `e2f78e6179e96bd8b89bf21650ae726fa41f10492c500994a80250b0e55a59b4`.
  Report SHA-256 `f0e2576bed96721d5853e2ad03efc3aa311b808d4c1eccf1fd6424dd36a77d1f`.
- Native r3: app `52d1aeb056ee16ee7337789557581ab4a88b07614a5ddea42c4ec8976b0c6f55`;
  exec 8914 exit 0, 52 states, no timeout/errors. Creation/profile combo
  selection, forward/reverse traversal and explicit create/save or Cancel were
  observed at 100% and 150%. `Cancelled150` was not created. Profile directory
  text remained two lines when leaving by Tab. Actual pdfLaTeX FINAL passed;
  source/report choices, checked source inventory and `source/main.tex` byte
  preview were exercised, then cancelled. Tab-page keyboard access remained
  open at this source. Report SHA-256
  `b8493af5542d96fce9cb1330602c7a359fd0d04b3c29de2e22127964bf976125`.
- Native r4: final source above, exec 47111 / PID 40099 terminal exit 0,
  64 states, 457 propagated key records, no timeout/interruption/observer errors.
  Reopened r3's synthetic main.tex with `--existing-synthetic-project`;
  explicit Auto FINAL succeeded. Delivery/checkpoint/recovery were at 100%.
  Report SHA-256 `9e81a22500ec09f7141799a8a1c5a7e1dc7fdb87ee39fe188ac52b3ab22e4ab2`.
  Probe SHA-256 `7c8c95f13798eef790c3b6d939687901640131f5c13ad5be5e4c38f47eef634b`.

R4 verified Tab to tab bar, arrow-key pages, check/byte-detail reading,
default PDF-only choices, real native destination picker, default-No rejection
and explicit Yes publication. Both unconfirmed items were reviewed: Auto versus
the profile's pdflatex suggestion, and static coverage limits. Neither was
misreported as passing. `cancelled-delivery` remained absent. `delivery/`
contains only `main.pdf`, 38832 bytes, SHA-256
`9bc971472d36dc24a99c5f3fd28938abf8b4d89fe0994996a1e5dab4cc7c91d0`.

An actual unsaved source comment produced a 312-byte independent draft. Native
checkpoint selection, archive picker, restore review/target picker, default-No
cancel (target absent), explicit restore and separate new-window confirmation
were exercised. `keyboard.icstex-checkpoint` SHA-256:
`aebb07557de84710ff352849b4f15e474b6e01bc9ab2b96d3e17883e53d2e009`.
All three restored files match manifest lengths/hashes and original bytes.
Original and restored `main.tex` remain 265 bytes, SHA-256
`f141642cb5dfa0eeb2e73274cd2f125439c9cf8e58122e805d34d5cfc3dfc1ce`.
`drafts/source-0-0.txt` remains separate, SHA-256
`cde7672c0253983bed029d47d5e5885d95a80f6a68d3ecc966662a1af91fa9be`.
The new window visibly showed `restored/project/main.tex`, the draft and the
first-save guard. It was closed with Don't Save; original-window exit also
required that explicit synthetic-draft choice. No archive/draft was deleted.

Menu entries and the compile toolbar were activated through AX, not all by
keyboard. The first native Go To path needed AX field correction; subsequent
checkpoint/restore pickers used typeahead/name typing and KP_Enter. Do not label
the whole operating-system/menu path keyboard-only. The observer's source field
tracks the original window; the new-window path/contents are proved by CUA AX,
not that field. Main registered-window destruction is true; process exit and
the explicit new-window close additionally establish no QA window remains.

Scoped Cocoa AX selection-enumeration mitigation, CapsLock/font notices and two
TSM UI-server communication failures near exit remain recorded. Eleven retained
Python crash reports were unchanged; no new crash is observed. This is not
proof of historical crash causality or complete accessibility acceptance.

## Remaining finite work

Do not repeat successful creation/profile, ordinary FINAL/output or byte-restore
operations merely to increase coverage counts. The subsequent
[follow-up](v1-m6-recovery-migration-keyboard-verification-2026-09-12.md) closes
standalone Block entry, legacy-copy publication, 150% delivery/checkpoint/recovery
controls and three five-tier checks on its separately identified source.
Reuse its retained fixtures for:

- Independent migrated-window visibility after explicit open confirmation;
  publication and default-No cancellation already have evidence.
- Resolve the remaining keyboard-only menu/picker evidence boundary with a
  specific observation; do not infer a product defect from CUA routing alone.

R3 historical reliability disposition and R5 restricted/MCP LuaLaTeX decision
remain independent and open. No security relaxation or deferral was approved.
E1–E4 platform/storage/human/release gates are unchanged. This receipt does not
complete R2, M6, local V1 acceptance or release readiness.
