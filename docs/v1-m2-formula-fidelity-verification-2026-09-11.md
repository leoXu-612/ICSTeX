# V1 M2 formula replacement and paste fidelity

Local, uncommitted continuation after the authorized source checkpoint.
Original focused/full discovery and the resumed real Cocoa clipboard/keyboard
flow pass. A misleading invalid-draft message found natively is fixed with a red
regression and focused/native reruns. The new source's required full r2 is
terminal/OK with explicit exit 0; see the current receipt below. M2-M6 and
independent Beta gates remain incomplete.

## Reproduced behavior and fix

`app/core/formula_input.py` previously validated the new draft only for insertion.
A valid existing `$x$` selection allowed a replacement plan containing `$x$$`,
an unclosed comment, nested envelope delimiters or an ambiguous empty dollar pair.
The existing pure recognizer now validates the proposed text for replacement as
well. This does not reject unknown commands merely because their meaning is not
known; safe comments, body whitespace and custom macros are preserved.

`app/gui/math_editor_widget.py` collapsed pasted newlines/tabs and stripped body
whitespace before recognizing its wrapper. A pasted comment could consequently
consume following TeX or its closing delimiter. Paste now recognizes the actual
input and retains the exact body. If the existing math tree cannot round-trip
that body, its existing literal Text node is used instead of changing source.
The dialog remains a draft; explicit Apply, original-selection ownership, Undo
and Cancel still use the existing paths. No parser rewrite or new source format.

## Verification

Frozen app Python path/content SHA-256:
`0c430570de459bea98fd81452a122e3af3a09a24f7f3365c68c0ac0794014ea5`.
Compileall and whitespace checks pass. Focused receipt:
`/tmp/icstex-v1-m2-formula-fidelity-focused-r1.log`.

```sh
QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest -v \
  tests.test_formula_input tests.test_formula_tree tests.test_math_editor_widget \
  tests.test_gui_editor.FormulaComposerTests tests.test_block_editor_targets
```

New assertions cover every existing wrapper, invalid replacement refusal, disabled
Apply, explicit-Apply refusal, Undo recovery, source-mode rejection of a lossy
projection, unknown macros/comments/whitespace, source Undo/Cancel, exact pasted
LF/CRLF/CR/tab text in the widget, noncanonical script order and wrapped/unwrapped
paste. These are core and offscreen observations, not native clipboard or IME
acceptance. Qt text widgets may normalize line endings in their displayed text;
the widget's raw LaTeX return value and source-file encoding behavior are distinct.

Red receipts: `/tmp/icstex-v1-m2-formula-fidelity-red-r1.log` and
`/tmp/icstex-v1-m2-formula-fidelity-red-r2.log`.
The first source-fallback fixture incorrectly assumed every unknown command must
force source mode; the existing tree preserved that fixture exactly. The revised
fixture includes script order that cannot round-trip, and its original-text,
source Undo and Cancel assertions pass on the unchanged application. The actual
replacement and paste failures were separately reproduced before the fixes.

Full discovery passed with exit 0; its process is terminal and the source hash was
rechecked unchanged. Receipt: `/tmp/icstex-v1-m2-formula-fidelity-suite-r1.log`.
Counts/status belong in project state and the append-only historical log.

A separate disposable offscreen dialog/real compiler integration exited 0:

```sh
QT_QPA_PLATFORM=offscreen python3 -X faulthandler /tmp/icstex-v1-formula-final-probe.py
```

It pasted a wrapped body with a custom macro, a comment containing otherwise
significant delimiters, and following-line math. The actual accepted edit plan
was placed in a synthetic document defining that macro, then compiled through
`CompileManager` with pdfLaTeX and FINAL. Input bytes remained unchanged. Extracted
and visually inspected PDF content is `Formula result: x + a + b + z`.
PDF SHA-256: `33258250942ef69afd8a2b195a9924b901f2c4d7696582e4c84b3526fdc0f008`.
The one-page PDF, rendered inspection PNG and report remain in
`/tmp/icstex-v1-formula-final-20260911-r1`; the log is
`/tmp/icstex-v1-m2-formula-final-r1.log`. These are local disposable evidence,
not installed-app or native-screen observations. A font-alias warning remains.

## Remaining work

The earlier desktop check reported the Mac locked; no bypass was attempted.
Foreground control was later explicitly reauthorized. The resumed image flow now
passes real Cancel/import/error/FINAL and GUI reopen; its independent receipt is
in `v1-m2-image-import-verification-2026-09-11.md`. Formula real clipboard/keyboard/
Undo/source fallback is now covered by the follow-up below. IME, AX stress,
Windows and human usability remain separate gates; desktop-generated input is not
a real student's usability or input-method acceptance.

No staging, commit, push, branch rename, package, installed-app replacement,
credential, signing, deployment or publication was performed by this continuation.

## Native clipboard follow-up and message repair

`tools/probe_formula_clipboard.py --native` opens one isolated source window and
three actual FormulaDialog instances on Cocoa. The computer-use skill drives
native clipboard paste, Command+Z/Shift+Z and the visible Apply/Cancel/mode controls
through NodeREPL. The probe only observes dialog state; it never calls the paste
method, fakes clipboard text or synthesizes QTest editing keys. It uses the real
MainWindow formula action and insertion controller, not a directly applied fake
plan. Setup selects exact synthetic formulas; no student source is involved.

Verified in both native r1 and final r2:

- Appending a dollar through the clipboard invalidates the visual draft and
  disables Apply. Undo restores the valid draft. A second paste keeps the exact
  wrapped body's custom macro, comment containing delimiters, LF and tab. Local
  Undo/Redo restores both versions. Cancel preserves disk bytes, document text,
  selected range and nonzero source scroll position; no compile grant is issued.
- Explicit Apply inserts the exact body into the selected formula. One native
  document Undo restores the whole original document and one Redo reapplies it;
  neither saves. An unknown/noncanonical script seed stays in source mode.
  Pasting a source draft then requesting visual mode retains that exact source
  when projection would reorder script syntax. One source Undo restores the seed.
  Invalid source disables Apply; Cancel retains the already accepted document.
- A separate explicit Save writes the expected bytes; an actual pdfLaTeX FINAL
  produces the visible text `Formula result: x + a + b + z` and the fallback
  expression. Save/compile preserve source cursor and scroll. Final r2 waits for
  the workspace header to leave its transient compiling state before capturing
  `FINAL · PDF 已是最新`. The final native screenshot was visually inspected.

Native r1 (exec 39747 / PID 76797, exit 0) exposed a message defect: an invalid
visual draft displayed "formula valid, reselect the source" despite the original
selection being intact. The `test-triage` skill's narrow classification workflow
separates this product message assertion from tool timeouts and transient capture
timing. This repository uses unittest, not Xcode/SwiftPM. The strengthened
`FormulaComposerTests.test_visual_replacement_cannot_apply_an_ambiguous_new_envelope`
fails before repair (exec 13577, exit 1; one assertion failure). FormulaDialog now
checks whether the rendered draft itself is a recognized envelope before blaming
selection ownership. Invalid drafts say to fix the draft; valid-draft/stale-selection
behavior is unchanged. No parser, serialization, authority or source-edit rule is
weakened. Rollback is this message classification and its assertions only.

Native r2 command:

```sh
QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3 tools/probe_formula_clipboard.py \
  --native --output /tmp/icstex-v1-m2-formula-clipboard-native-r2
```

Exec 90551 / PID 77614 terminated with exit 0; all native windows were destroyed.
Environment: macOS 26.6.1 arm64, Python 3.12.6, Qt/PySide6 6.11.1, local pdfLaTeX.
Final app SHA-256: `e4e978cb79d3321462bbe52d6597195ff1a0da13f93df7273a7d75887a635baf`.
Final app+tests SHA-256: `1627c79866b811f38951d7ec5995ea43bfc548067ac88abcec7b95513e6784a3`.
Probe SHA-256: `b21ca70eb4b8ec4050fa93c011a6f117d92b2c5deda525d12a240f1fac4d21c0`.

Artifacts under `/tmp/icstex-v1-m2-formula-clipboard-native-r2`:

| Artifact | SHA-256 |
| --- | --- |
| `report.json` | `aeb7048b8e5dd6b104c9706ca51f7fcef6888ffb62913312004071252371b0b2` |
| `formula-final.pdf` | `b1e6cafe7ad15a9cfd9d2b3c40c03cfd4222d34373c89523ca93fa57adc8ecdf` |
| `formula-final.png` | `b705567088e2fa36a18fa304cfaef2021b79d439808f261554afc91734cc45b0` |
| saved synthetic `main.tex` | `d06a52762e3fe30594bf4cf3e5769c01d2bfa55800b0d8629d2a6e09ce198ec7` |

Log `/tmp/icstex-v1-m2-formula-clipboard-native-r2.log`, SHA-256
`c0442438a8231b29b31e0eb3854ef512e22a239e1894b0c1a2471d44cfc10968`.
The original r1 report/PDF remain with their older source and transient header;
they are not relabeled as final r2 acceptance.

Focused: 138 tests in 2.501s, OK / exit 0, exec 83091. Command:
`QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_formula_input
tests.test_formula_tree tests.test_math_editor_widget
tests.test_gui_editor.FormulaComposerTests tests.test_block_editor_targets -v`.
Log `/tmp/icstex-v1-m2-formula-native-followup-focused-r1.log`.
Focused log SHA-256:
`ce686f9edb9853e9073111ea0ebba889c03646baa12f79b0292e31ad78cd8289`.
Compileall, probe syntax and diff checks pass. Required full r1 (exec 17107 /
PID 78543, started 2026-09-11T07:00:09Z) completed its log with 1455 tests in
140.216s / OK, and the process is gone. Log:
`/tmp/icstex-v1-m2-formula-native-followup-suite-r1.log`, SHA-256
`fc4144c2e0c929621a125bad24c743487dffc8c9779afb6151301823d0d525c3`.
Post-run app/test hashes match. Handle collection returned empty output without
an exit code, then the handle was unavailable; exit 0 is not inferred from that
tool response. A same-source r2 ran as exec 12954 to obtain an explicit exit
receipt, with no concurrent benchmark or native probe:

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10 \
  python3 -m unittest discover -s tests -v \
  > /tmp/icstex-v1-m2-formula-native-followup-suite-r2.log 2>&1
```

The shell wrapper prints and returns unittest's captured exit code. This bounded
repeat repairs an evidence-collection gap, not a test assertion or app failure.
R2 is terminal: 1455 tests in 142.032s / OK, `unittest_exit_code=0` and tool
exit 0. Log SHA-256:
`115838854933191983decfaec2d3ea48ef021d5670bd1ce129dcbabc45815d30`.
App and app+tests hashes above still match after terminal; compileall/diff pass.
All test/native handles are closed and the five-file Python crash inventory is
unchanged. No complete native lifecycle, IME, AX or platform claim follows.

The desktop clipboard helper repeatedly timed out waiting for its read
acknowledgement; actual dialog observations show each requested paste arrived
exactly once, and saved bytes prove the final content. No paste was blindly
retried. The helper's clipboard-restoration mechanism was used, but unrelated
clipboard contents were not read/recorded or independently restoration-tested.
One r2 startup observation raced process registration; the same live handle was
reobserved, not restarted. `App quit` after final clicks matched successful probe
cleanup. No new Python crash report was observed. Existing scoped AX guard,
font-alias and r1 TSM keyboard-service warnings remain; no complete IME/AX claim.
