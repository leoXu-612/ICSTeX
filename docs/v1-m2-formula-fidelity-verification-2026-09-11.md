# V1 M2 formula replacement and paste fidelity

Local, uncommitted continuation after the authorized source checkpoint.
Focused and full discovery pass; native acceptance is waiting
for manual Mac unlock. M2-M6 and independent Beta gates remain incomplete.

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

The desktop tool explicitly reported that the Mac is locked and needs manual
unlock. No bypass was attempted. Image native r3 was stopped after the app source
changed; its first-picker observation does not complete image import acceptance.
After unlock, replay real image Cancel/import/error/FINAL and formula paste,
keyboard/Undo/source fallback in an isolated source window, then inspect actual
outputs. IME, AX stress, Windows and human usability are separate gates.

No staging, commit, push, branch rename, package, installed-app replacement,
credential, signing, deployment or publication was performed by this continuation.
