# M6 workbench native input and standard Save shortcut

Local source only, 2026-09-11. The user reported the Mac unlocked after the
earlier [locked-screen observer attempt](v1-m6-ime-verification-2026-09-11.md).
This receipt extends actual workbench input evidence; it does not close the
remaining focus/partial-composition, AX, scale, platform or release requirements.

## Workflow and ownership

`tools/probe_workbench_composition.py` creates a real MainWindow with isolated
settings and a new synthetic project. Ordinary source uses a short ctexart file;
Block fixtures contain a text block, a one-cell target table and a separate
`untouched` table. The probe sets initial navigation and records native events,
widget text, current model, pending drafts, original file bytes and actions.
Desktop control, not the probe, types individual Pinyin keys, commits with Space,
uses Command+Z / Command+Shift+Z, types a second `ni` candidate and cancels with
Escape. The prior English input source is restored before saving/closing.

Block Apply and Save are separate user actions. The existing Block autosave may
run after explicit Apply; no claim is made that it must wait for manual Save
after the model is applied. Before Apply, observed model and disk bytes must
remain original. These are sampled state invariants, not filesystem tracing or
proof against an unobserved change that is immediately reverted.

The corrected observer requires the actual ordered text states, second candidate
and cancel, Apply/Save, exact saved text, preserved second table, no unexpected
Block compiler, unchanged app hash and destroyed window. Its counterexample
tests are not native evidence; the runs below supply actual event/file outcomes.

## Native runs after unlock

All use Cocoa on macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1. Command:

```bash
QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3 tools/probe_workbench_composition.py --kind KIND --output NEW_DIRECTORY
```

| Kind/run | Terminal result | Actual outcome and source |
| --- | --- | --- |
| ordinary r2 | exec 6177, exit 0 | 12 native IME events; exact `base 中文`, Undo/Redo/cancel, toolbar Save, cursor 62/scroll 0 unchanged on save; app d8175978 |
| Inspector r1 | exec 31688, exit 1 | Input/draft/Apply and actual saved bytes were correct, but the probe watched the hidden source Save QAction instead of Block Save; save count 0 makes this receipt incomplete, not a pass |
| table r1 | exec 88803, exit 0 | Real double-click cell delegate, cursor to end, 12 IME events, local Undo/Redo/cancel, Return retains table draft, Apply then Command+S; target saved and second table untouched; app d8175978 |
| Inspector r2 | exec 72390, exit 0 | 12 IME events; original model/disk before Apply, exact target after Apply/Command+S, second table untouched, no compiler created; app d8175978 |
| ordinary r3 | exec 54390, exit 0 | Same full input sequence, now Command+S alone triggers source Save once and writes exact bytes; current app 40842d93 |

For ordinary r2, source text stayed original during preedit even though Qt's
textChanged handling marked the tab dirty and displayed pending-save/stale UI.
This is not evidence of an early disk write. The configured probe save debounce
was one hour, so these observations do not test the default idle-save interval.

Reports are `report.json` beneath these local directories (logs are the same
directory name with `.log` appended):

| Directory | Raw report SHA-256 |
| --- | --- |
| `/tmp/icstex-v1-ime-workbench-ordinary-r2` | `ec26abf28be03b08b3b1062745623e4b892302c701549fca98bb62b7a83f1b86` |
| `/tmp/icstex-v1-ime-workbench-inspector-r1` | `81f5ef969e8c69b469f62a1957e1f9d0a3417689593ffbe8eedde7ff727dc4ce` |
| `/tmp/icstex-v1-ime-workbench-table-r1` | `6ac6ab2fdb9ea1533925ed45cb0e3afcc334cea9ed2b63dee15cf2a755977606` |
| `/tmp/icstex-v1-ime-workbench-inspector-r2` | `b84e7fd104ffe085569b27852d1d2ebf1ae839d4aec5a0609950ef666eb919f6` |
| `/tmp/icstex-v1-ime-workbench-ordinary-r3` | `f5c4537f579c663a68cad1c12a9ab2236df1d5f9e8b78b202ac9772d1e92e6af` |

Ordinary r2/Inspector r1 used observer SHA-256
`071a620ed094adb0c99d2ee18ad0fcdd1bd0bc166b7f91e881ba2348ef836fba`.
For subsequent runs the observer connects the mode-specific Save QAction and
also records actual key/modifier events; SHA-256
`b507789cc49bc6b017c0547a04ab9dba329c5116ff009b3cb5579ada9e7da279`.
The 11 existing receipt-counterexample tests passed again after this probe fix.
The first Inspector record is preserved, not edited to invent a Save count.

Screenshots inspected show actual preedit/Chinese text in all three editors and
the final source saved state. The scoped AX selected-children mitigation hides
the live table delegate from parts of the AX tree; its visible screenshot and
actual QExpandingLineEdit events supplement, not repair, that missing AX coverage.
After actual close, CUA returned `-10005: timeoutReached`; each separate process
was then confirmed terminal with `window_destroyed=true`. The UI tool error alone
was not treated as a successful close or a crash. Existing font/IMK warnings
remain, with no new Python crash report in the five-file inventory.

## Product defect: ordinary source Save had no shortcut

In ordinary r2, Command+S did not trigger Save; the toolbar button did. Inspection
confirmed `window.save_action` had no shortcut. The Block QAction already had its
own Ctrl+S binding (Command+S on Cocoa), so it is not an application-wide keyboard
delivery failure. No custom key interception or new save path is required.

`app/gui/main_window_actions.py` now assigns `QKeySequence.StandardKey.Save` to
the existing source Save action. Existing visible-mode enable/disable logic and
protected save/conflict handling remain authoritative. The only application-code
increment in this follow-up is that assignment.

`tests/test_gui_editor.py::WorkbenchShortcutTests` verifies an actual key sequence
saves the source once without moving cursor/scroll or granting compile authority,
and switches between Block/source without activating the hidden mode's action.
The first source test failed with zero saves, exec 85991 / exit 1; log
`/tmp/icstex-v1-save-shortcut-red-r1.log`, SHA-256
`7426b2e6dbc196f8b00931a856083418dee9ca437b460e00ec90dee2a4bc9eb7`.
After the assignment it passed, exec 60484 / exit 0. Expanded shortcut/check/
Block safety scope: 38 tests / 14.349s / exit 0, exec 63983; log
`/tmp/icstex-v1-save-shortcut-focused-r1.log`, SHA-256
`f4f2b07f7d1a5289f607a3f4a9e17ed022dec072a71ce95394c4b5fb49cc5fd0`.

Frozen application SHA-256:
`40842d9379ff458173f175b07198d32a207296922214dd6d72880464584b6946`.
App+tests SHA-256:
`9a056619d84f3d3ad02a33946df18c3f567eb1c45597ba4475c585fb0b356a8b`.
Older Block native receipts retain app d8175978; they are not relabelled as
40842d93. The new mode-routing regression checks the shortcut interaction.

Required full command `QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10
python3 -m unittest discover -s tests -v` completed: **1484 tests / 251.103s / OK**,
exec 53862, explicit `unittest_exit_code=0` and tool exit 0. Log
`/tmp/icstex-v1-save-shortcut-suite-r1.log`, SHA-256
`ae8d98f630207b60da7c83ea09178bce0572349a6a1b4d899491aa6d71852ff3`.
Both source digests matched after terminal. Compileall, probe syntax and diff
checks passed, index remains empty and the held candidate feed hash is unchanged.
All native and test handles in this receipt are closed. The earlier intermittent
compiler-fixture failure and old Qt crash causes are not thereby proven repaired.

## Remaining local focus defect

Inspector Control+Tab left focus in QPlainTextEdit in both native runs. In r2,
the observer recorded ShortcutOverride key 16777217 (Tab), modifiers 268435456
(Qt Meta/physical Control), but no corresponding Tab KeyPress to the editor.
The existing filter only moves focus on KeyPress; therefore the observed run
did not reach that branch. This identifies the missing event boundary, **not**
the ultimate Cocoa cause or a verified fix. The Apply button was clicked to
finish the separate input/save workflow; this does not pass keyboard navigation.
Do not change the shortcut or claim a repair without a focused reproduction and
real native focus follow-up. Other focus/partial-commit combinations, default
idle-save composition, high-scale citation readability and R3–R6 remain open in
`V1_ACCEPTANCE_MATRIX.md`. No complete A12/M6 or release recommendation.

No Git mutation, packaging, installed-app replacement, signing, deployment,
release, student-file edit or system settings change. Suggested future commit:
`fix(gui): restore standard source save shortcut` (not performed).
