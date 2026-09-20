# V1 M6 / A12 input composition verification

Date: 2026-09-11, Asia/Taipei. Local source work only; not full A12, V1 or
release acceptance. No Git mutation, packaging, installed-app replacement,
network import, student document, new dependency or system input-source setup.

## User task and repair boundary

Enter Chinese through a configured input method in the formula editor without
losing the committed text, confusing preedit with source, or applying an
unfinished candidate. Preserve the existing formula tree, isolated draft,
source-mode fallback, explicit Apply and document-level revision checks.

The live `MathEditorWidget` inherited QWidget's default input-method handler
and did not opt into input methods. A real `QInputMethodEvent` with a Chinese
commit was rejected and left `x+` unchanged. The red regression is
`test_input_method_commit_is_inserted_once_and_undoable`.

The repair is confined to `app/gui/math_editor_widget.py` and the existing
`FormulaDialog` integration. It enables input methods, exposes the current
mathematical slot as surrounding text, uses atomic object characters for
structural nodes, and preserves other slots and unknown commands. UTF-16
positions are translated without splitting surrogate pairs. Preedit and its
format/cursor attributes are painted separately; they do not enter LaTeX or
undo history. A selection replacement remains one undo, while successive
commits have distinct undo records. Unfinished composition blocks Apply and
mode changes in both visual and source mode; the input method, not the app,
chooses what gets committed. No compiler, file writer or document format changed.

This follows the documented custom-widget composition contract in
[Qt QInputMethodEvent](https://doc.qt.io/qt-6/qinputmethodevent.html) and
[QWidget inputMethodQuery](https://doc.qt.io/qt-6/qwidget.html#inputMethodQuery).
These API references are not evidence of native acceptance.

## Focused regression evidence

Command scope:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest \
  tests.test_input_composition tests.test_math_editor_widget \
  tests.test_gui_editor.FormulaComposerTests \
  tests.test_block_property_drafts tests.test_block_editor_targets -v
```

- Initial 5-test red: the visual commit rejection was a product defect. The
  separate assertion that QPlainTextEdit emits no `textChanged` during preedit
  was a fixture assumption: Qt emits it for layout changes even though source
  text and undo remain unchanged. The test now verifies those actual invariants.
- A selection fixture initially expected two left-arrow operations from the
  structured end-of-slot boundary to select two characters. It selected one;
  setup now accounts for that existing boundary and still requires exactly `bc`.
- 109 focused tests passed, 2.337 seconds, shell/tool exit 0 (exec 97037).
  Log `/tmp/icstex-v1-ime-focused-r6.log`, SHA-256
  `bc1808ad3975b510ed5c36afccbc47675a7230747ece9ca4ddb690f0b785d2bb`.
- Further event-level testing reproduced an overly broad undo group for a
  selected replacement followed by two partial commits. One undo incorrectly
  restored `old` instead of the first committed `中`. The new red test failed
  before repair; after clearing the selection merge marker at each commit,
  63 formula/widget tests passed, 1.055 seconds, exit 0 (exec 96822).
  Red log `/tmp/icstex-v1-ime-partial-red.log`, SHA-256
  `6627c2784c70dbfcbf117fc725151cd45f6758dba6163f84ea213ea6b260d277`;
  green log `/tmp/icstex-v1-ime-partial-green.log`, SHA-256
  `5528570e1de163c546d8133bfe30bb241e0e5a9f3ac1379edcbe75515a8a9ed0`.

Coverage includes ordinary source composition/cancel/reconversion, Block
Inspector refresh/local undo/no model or disk writes, an actual QLineEdit table
delegate's pending draft and target switch, formula source/visual Apply guards,
preedit rendering attributes/caret rectangle, surrogate-pair replacement,
unknown-node preservation, selection replacement and partial-commit undo.
Synthetic events are not native input-method or full accessibility evidence.

## Actual Cocoa input-method observations

`tools/probe_input_composition.py` creates only an isolated formula dialog. An
event filter observes real native InputMethod events; it never generates input,
pastes, chooses a candidate, applies or dismisses the dialog. Desktop control
used individual physical key presses, the already-configured Pinyin input
source, Space to commit, Undo/Redo buttons, Escape to cancel a second candidate,
then explicit Apply. The previous direct-English input source was restored.

Platform: macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1, Cocoa.
The existing version-scoped selected-children AX guard remained active; no
system Qt patch or accessibility-policy change was made.

| Probe | Terminal result | Source identity and receipt |
| --- | --- | --- |
| Initial visual r1 | exit 0, exec 38643 | app `4bddf8b5`; `/tmp/icstex-v1-ime-native-r1/` |
| Source mode r1 | exit 0, exec 68664 | app `b6da0987`; `data/v1/ime-native-source-2026-09-11.json` |
| Visual r2 | exit 0, exec 94644 | app `b6da0987`; `data/v1/ime-native-visual-2026-09-11.json` |

Each latter run observed 12 native composition events: eight Pinyin preedit
updates, the commit `中文`, two updates for `ni`, and an empty cancel event.
Both showed `x+` throughout the first preedit, `x+中文` on commit, `x+` after
one Undo, then `x+中文` after Redo and after cancelling the second candidate.
Apply returned exactly `$x+中文$`; the original document string was unchanged.
The dialogs were destroyed and the processes exited 0. The desktop tool's
final `App quit` response was followed by these process/receipt checks, not
treated as a failure or as completion on its own.

The app hash before/after both latter runs was
`b6da0987b666734b4a91df0cd04d2b481f44b334b53ceaa9429bbcf5643fe80f`.
Local raw visual receipt SHA-256:
`78dead0ec16307c97df4120959658fcfa3244ce76193f44886a312d069898aa7`.
Local raw source receipt SHA-256:
`fa85808b994f31b45c35191a2a1c90b18562f652856681ed61054c9fd762cf69`.
Local `state-*.png` files and returned native screenshots show preedit and
committed Chinese. Candidate-window geometry itself was not independently
captured; these are app-window observations, not a full IME UI matrix.

The later partial-commit undo repair changes the final app hash; these earlier
native receipts are not relabelled as final-source results. That additional
history case currently has synthetic event-level red/green coverage.

Warnings retained: IMK mach-port messaging, CapsLock LED handling, and a missing
`Monospace` font alias (78–92 ms in the visual runs). No new Python crash report
was found after these native runs. The prior timer/stylesheet/AX crashes are
not thereby proven resolved. Real Block/table IME, other input methods,
Windows, VoiceOver, focus-change combinations and human usability remain open.
This probe verifies draft/plan behavior, not a new Chinese-font FINAL compile.

## Frozen full regression

First full: 1470 tests, 142.519 seconds, TERMINAL/FAIL, exec 47785, exit 1.
One error in `test_timeout_kills_entire_process_tree`: after the one-second
timeout, the fixture's `grandchild.pid` did not exist. The expected TIMEOUT
assertion had already passed; child-tree verification was not reached. A
startup/scheduling explanation is plausible but not established. No compiler
or test assertion was changed to hide it. Isolated rerun: 1 test, 1.012 seconds,
exit 0, exec 94941; not proof that the intermittent failure is repaired.
Failed full SHA-256: `8fb826928400e5389d0e1a8659fd4784ae08382ca3885f1db447cb32a10dff24`.

Final app `d8175978f5d47186440a6ccd8abb9b785e4b128b301ea2c79cbecf8c6965550b`;
app+tests `0e85d64636b7c8fb436b24c4cd02b17de58e2ba64c1d05179cae0923141cc324`.
Convention: sorted relative Python paths + NUL + bytes + NUL, app then tests.
Second full: 1471 tests, 138.051 seconds, TERMINAL/PASS, exec 39883, explicit
shell/tool exit 0. Log `/tmp/icstex-v1-ime-suite-r2.log`, SHA-256
`e38e894ad123f4bab5316ca6e253f7a224fd2fdfb47793cb32f3e745bdd96971`.
Both source hashes match after terminal. Required compileall and diff checks
passed. No new Python crash report was found; all native/full/focused handles
are terminal. Do not poll or restart these closed handles.

## Workbench observer and locked-screen follow-up

The next native ordinary-editor process (exec 41820, PID 92341) was confirmed
live before desktop control was attempted. CUA returned that the Mac was locked
and automatic unlock had failed; no further desktop interaction was attempted.
The process reached its own 600-second deadline, cleaned up its synthetic window
and exited 1 (`native_exit_code=1`). It received zero InputMethod events, recorded
zero Save/Apply actions and preserved the synthetic source exactly. This is an
environment-blocked, incomplete run, not a product IME failure or acceptance.
No input-source switch took place, so no input-source restoration was necessary.

Raw report: `/tmp/icstex-v1-ime-workbench-ordinary-r1/report.json`, SHA-256
`2502905e8d781ef79c83e7c62683fa11eb528aa08f478b4975ea07e88971d037`.
Log: `/tmp/icstex-v1-ime-workbench-ordinary-r1.log`. It records app d8175978
unchanged before/after. The original probe bytes had SHA-256
`3557e1f6bc2c001270a4b0b40999600ebfc84fc6df65e04806c8c0dd73fa31c4`.
Do not rerun this closed handle or call its zero-input result successful.

While the desktop was unavailable, counterexamples exposed flaws in this new
probe's acceptance predicate. Repeated committed snapshots before Undo could be
counted as Redo; candidate cancellation, draft/model/disk boundaries, explicit
Block Apply and unrequested Block compilation were not required. These were
**probe defects**, not newly reproduced application data-loss bugs. test-triage
kept that distinction and used the small scope before the full suite.

`tools/probe_workbench_composition.py` now requires an ordered commit→Undo→Redo
state sequence, a separately observed second candidate and cancellation, unchanged
committed text during preedit/cancel, no observed early file/model change, explicit
Block Apply and Save, exact final bytes, destroyed window and unchanged app hash.
It counts the actual table Apply button, rereads the current session registry,
tracks QLineEdit preedit from real events and schedules QObject-bound post-event
snapshots. It does not synthesize input, choose candidates or save/apply for the
user. Passing these bounded observations is not full focus/IME/AX acceptance.

Regression `tests/test_workbench_composition_evidence.py` checks constructed
receipts, not native input. Initial 11 tests had 9 failures, exec 74482 / exit 1;
log `/tmp/icstex-v1-workbench-evidence-red-r1.log`, SHA-256
`cd4f3ae06cbaafb735382c904315c1c8468a87dced1a6a362ccd8a69c6ef74f4`.
After repair all 11 pass, exec 83495 / exit 0, 0.001s; log
`/tmp/icstex-v1-workbench-evidence-green-r1.log`, SHA-256
`60f1b44e6e974f9d5d825cb24b4fe006fb40c9aac6ab0ca671772d2507b86257`.
Expanded composition/formula/Block scope: 121 tests / 5.171s / exit 0,
exec 86686; `/tmp/icstex-v1-workbench-evidence-focused-r1.log`, SHA-256
`d248b0e1afdc0b5e1c63ab319b6d1046089bfd61b2cf2c6c64ab59cdd175e8a8`.
The corrected probe SHA-256 is
`071a620ed094adb0c99d2ee18ad0fcdd1bd0bc166b7f91e881ba2348ef836fba`.
At this locked-screen checkpoint the new native observation path had not run.
The application itself was not changed by this observer-only follow-up. The user
subsequently unlocked the Mac; actual workbench outcomes, the mode-specific Save
observer correction and the later product Save-shortcut repair are recorded in
`v1-m6-workbench-input-verification-2026-09-11.md` with separate source identities.

Frozen full follow-up: 1482 tests / 257.308s / OK, exec 20957, explicit
`unittest_exit_code=0` and tool exit 0. Command:

```bash
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10 python3 -m unittest discover -s tests -v
```

Log `/tmp/icstex-v1-workbench-evidence-suite-r1.log`, SHA-256
`3290618b83fcc11ba8ea65d27c5e03be65d1bf760634d7753ee51fa70cf729b7`.
App remains d8175978; app+tests now
`2e01d70c6a5623c75be57997bef61dbb671729111ae61cd90f9b42d39d771584`.
Both hashes match before/after terminal. Compileall, probe syntax and diff checks
pass. The same five earlier Python crash reports remain; no new report appeared.
All handles from this follow-up are terminal. Suite duration is not a performance
benchmark, and the older intermittent compiler fixture cause is still unproven.

## Remaining work

The requirement-to-evidence inventory now lives in `V1_ACCEPTANCE_MATRIX.md`;
continue its explicit local R1–R6 items, including final-source native
partial-commit/focus follow-up. A12 is now partially backed
by actual Pinyin events but remains incomplete. M7 is a readiness handoff only;
all independent installation-lifetime, platform and publication gates remain.

Suggested commit (not performed): `fix(gui): preserve formula input-method composition and undo`
