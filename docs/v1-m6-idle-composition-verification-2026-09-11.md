# M6 ordinary-source composition and default idle save

This is a local Qt-event/save regression receipt, not physical IME, complete
R1/R2/M6/V1 or release acceptance. All files are disposable synthetic fixtures.
No student content, system settings, installed app or release artifact changed.
No Git mutation, packaging, signing, deployment or publication was performed.

## Source and reproduced failures

Branch `codex/v1-development`, HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`; shared changes retained.
Baseline app SHA-256
`f71ec949f96011e0c510bd1d953d2b5e56e53d0597e6106ca577a77d236f6ab4`.
Final app
`75c177e002c371a26a469a37741ec19a9bf30069fb9f6d26da9838dfeb5fd42b`;
app+tests
`fd872bfdd810a28b57874dd6604576920abcc1b2a71d3210688bc19117e19a2c`.
Digest convention remains sorted relative Python paths, NUL, bytes, NUL;
app then tests for the combined digest. These are source, not artifact identities.

A standalone Qt observation showed that preedit updates emit `textChanged` and
increment `QTextDocument.revision()` while `toPlainText()` is unchanged. Even
`contentsChange` reported replacement of a block, so neither that signal nor the
Qt revision alone establishes a committed source edit.

Four actual-MainWindow tests failed on the unchanged application baseline:

- Preedit and cancellation caused two actual atomic writes of unchanged source.
- Candidate changes/cancellation restarted an already pending committed save.
- Partial commit saved correctly, but cancelling the remaining candidate wrote
  the same source a second time.
- After the committed part was saved, an external edit was treated as a clean
  reload instead of preserving the active candidate as a conflict.

Red r2: 4 tests / 5.723s / 4 failures / exec 56453 exit 1;
`/tmp/icstex-v1-idle-composition-red-r2.log`, SHA-256
`bd67735658c576e3463bd15c5ba8bba248d54b5e9bd712e990d0f5e80d56fd15`.
Red r1 also exposed a test setup error: opening a document does not eagerly
create a compile manager. The authorized-auto-compile test now explicitly
creates its own manager; no product behavior was changed for that setup.

## Bounded repair and assertions

`LaTeXEditor.sourceTextChanged` forwards normal text edits and compares actual
text before/after native `inputMethodEvent`. Qt's own signals, composition,
cursor and Undo handling remain intact. MainWindow source consumers now use
this signal, so preedit-only layout changes do not dirty the tab, invalidate its
PDF/checks or schedule save/compile. Full-text comparison occurs only at the IME
boundary; ordinary keystrokes do not gain a text snapshot.

Selection removal is deliberately not filtered out merely because the event has
an empty `commitString`: Qt removes a selected range when composition begins.
That is an actual document change and retains native Undo behavior. This repair
does not redefine native selection/cancellation semantics or promise that every
IME event is byte-neutral until a final candidate is accepted.

External reload treats an active native preedit as protected local editing,
even after its committed portion was saved and dirty flags cleared. It uses the
existing conflict/confirmation path. Own-save echoes still preserve the editor.
Atomic writing, encoding, root ownership, compile authorization and the default
800 ms debounce are unchanged.

Five MainWindow regressions use real default timers and atomic temporary-file
writes. They cover no-write/no-compile/no-invalidation on candidate cancellation,
partial committed bytes only, unchanged cursor/scroll and live candidate after
save/own watcher echo, local Undo/Redo, unchanged pending timer identity, external
conflict refusal and inactive-tab source/save/PDF ownership. Three additional
editor tests cover source notifications, consecutive partial commits, UTF-16
replacement/deletion, native selected-range removal, Undo and signal-blocked
reload. Existing source/preview/check/formula tests remain required.

The first green integration assertion assumed an empty Undo stack, but a fresh
MainWindow already had one formatting step before any IME event. Direct inspection
showed the same step count before preedit and after cancellation; the test now
requires that captured count to remain unchanged, not a fabricated empty stack.

Expanded r1 and a diagnostic rerun exposed a fixture timing assumption: after
`qWait(1000)`, the 800 ms timer was still active with `remainingTime() == 0`, dirty
true and conflict false. The test had inspected bytes before the queued timeout
was delivered. Final committed-save tests observe the real `timeout` signal and
matching clean disk state within a bounded event loop; they do not manually
flush, change the debounce or weaken byte/ownership assertions. Diagnostic log:
`/tmp/icstex-v1-idle-composition-diagnostic-r1.log`, SHA-256
`ed774a8b7dbbf3a42b8e378378b8e00494a6cf3beb78f98e34160a997036b17e`.

## Verification and remaining scope

Follow-up evidence in the [citation layout receipt](v1-m6-citation-layout-verification-2026-09-11.md)
qualifies the immediate-notification result above: periodic citation reconciliation
still uses Qt document revision and invalidates on candidate-only changes.
That separate path was not covered by this slice's mocked immediate-invalidation
assertion and remains unfixed R1. The actual save/byte/candidate results stand.

Final focused command:

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_gui_editor tests.test_input_composition tests.test_gui_preview_pipeline \
  tests.test_gui_submission_check tests.test_formula_input -v
```

280 tests / 47.244s / OK; exec 51524 exit 0.
`/tmp/icstex-v1-idle-composition-focused-r2.log`, SHA-256
`003b2654ce96d63662f33b5cfb3674e77dce6eaa33f01660d2681e05e454ed02`.
Intermediate 10-test event/save run passed before the timing-fixture improvement;
it is not the final frozen receipt.

Required frozen-source verification:

```sh
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10 python3 -m unittest discover -s tests -v
git diff --check
```

1505 tests / 131.638s / OK; exec 95354 reached explicit shell/tool exit 0.
`/tmp/icstex-v1-idle-composition-suite-r1.log`, SHA-256
`53feb2fa4dcdc68db7f8f6abd61bdacc92e4658c968ae19e4f1cf6df695d5d12`.
Post-terminal app/app+tests hashes match the final source above. Compileall and
diff checks pass again. No Traceback, RuntimeError, RuntimeWarning, fatal or
QObject/QThread destruction failure was found in the full log. Existing
offscreen plugin messages remain; they are not native UI evidence.

The seven existing September 10/11 Python crash reports are unchanged: five
historical reports, the intentional style-GC red, and the invalid Qt-module-
unloading harness from the preceding slice. This turn added no report and does
not resolve their unrelated historical causes. All test handles are terminal.
HEAD/index unchanged; held feed SHA-256 remains
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

The user reported unlock, but the Computer Use state request still returned
"Mac is locked". No new native probe window or physical input was started, and
no input source was changed. R2 physical Inspector Control+Tab and
Control+Shift+Tab, current-source physical default-save/partial-composition and
formula focus cases remain open. The earlier native observer disables idle save;
its receipt must not be relabelled as default-800-ms evidence.

Next bounded background work is R2 high-scale citation review; R1 physical
composition/focus tests require a usable control channel.
R3 historical timer cause/AX, R5 restricted LuaLaTeX compatibility, R6 reconciliation
and external platform/human/release gates remain as listed in the acceptance
matrix. Rollback scope is only this source signal/external-preedit condition and
these targeted tests; do not revert other shared changes.

Suggested commit (not executed):
`fix(editor): separate IME preedit from source autosave changes`.

Follow-up: [read-only source identity](v1-m6-source-identity-verification-2026-09-11.md)
addresses the later periodic/cached Qt-revision false invalidation. It does not
expand this original default-timer receipt into physical IME acceptance.
