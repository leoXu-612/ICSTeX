# M6 Inspector focus routing and process-tree test readiness

This is a bounded local-source receipt, not complete A12/M6/V1 or release
acceptance. The [acceptance matrix](V1_ACCEPTANCE_MATRIX.md) retains the original
M0–M7/A01–A15 scope. No commit/push, package, installed-app replacement, signing,
deployment, release, student documents or system settings were involved.

## Source and scope

Branch `codex/v1-development`, HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`; shared uncommitted changes retained.
Baseline app `40842d9379ff458173f175b07198d32a207296922214dd6d72880464584b6946`.
Current app `43816cb0a8f221e5b1ffbf18f1cfe96bf98529ef7351be7d818cb752618d8b6d`;
app+tests `4d775d7adbd81fa40e0314282336c3f5eb8871896d57aee46a770c871e145d54`.
Digest convention: sorted relative Python paths, NUL, raw bytes, NUL; app then
tests for the combined digest. This is not an artifact or binary identity.
Environment: macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1;
tests use offscreen, the interrupted native attempt used Cocoa.

The only application change in this slice is Inspector focus routing. Existing
draft/model/save/compile ownership, source Save repair and pending shared work
remain intact. Compiler changes in the Git diff predate this slice; this slice
changes only its process-tree test fixture, not production timeout behavior.

## R2 focus repair and remaining native boundary

The previous [workbench receipt](v1-m6-workbench-input-verification-2026-09-11.md)
captured actual physical Control+Tab as `ShortcutOverride` with Qt Meta on Cocoa,
but no corresponding editor `KeyPress`; focus remained in the content editor.
Current baseline code still accepted the override but moved focus only during
KeyPress. This identifies the failed event boundary, not the full Qt/IME cause.

`BlockInspector` now registers two `QShortcut` objects owned by the content
editor, using `WidgetShortcut` context and disabled auto-repeat. Activation only
scrolls to and focuses Apply or Alias; it never applies, saves or compiles.
Physical Control uses Qt Meta on macOS as before; other platforms use Qt Control.
Normal Tab/Undo/IME handlers are not replaced. This uses the documented
[Qt shortcut dispatch and context](https://doc.qt.io/qt-6/qshortcut.html) rather
than changing focus during the shortcut-override query.

Regression evidence:

- `test_focus_shortcut_routes_before_native_text_key_consumption` suppresses
  widget KeyPress after shortcut dispatch, modelling the observed boundary.
  Both directions failed on the original code. New routing passes forward,
  Shift+Tab and Backtab while draft/model/files and compile authority stay intact.
- `test_inspector_focus_shortcuts_preserve_draft_and_are_widget_scoped` drives
  a real MainWindow's QWindow route at 100%/150%, verifies visible focus targets,
  normal Tab and local Undo/Redo, no model/file change, and no activation from
  Alias or the hidden Inspector in source mode. It is offscreen, not physical IME.
- The older `tests/test_blocks_gui.py` assertion now waits for window activation
  and sends shortcut keys through QWindow rather than directly to an editor.
  Its original focus/text/model/Undo assertions are retained.
- The observation-only workbench probe additionally records the exact content/
  alias/apply focus role. Its existing IME pass predicate is **not** a focus-pass
  predicate; a later native focus receipt must explicitly inspect those roles.

Native baseline attempt exec 63025 / PID 99831 used a new synthetic project in
`/tmp/icstex-v1-focus-baseline-r1`. Computer Use reported the Mac locked before
any native input. SIGINT entered fixture cleanup and the process ended with
explicit exit 130; no completed JSON receipt exists. Do not mark this as a
native product failure/pass or wait on the closed handle. No input-source switch
was performed. Current-source physical forward/backward navigation after Pinyin
commit/cancel, visible target, explicit Apply/Save and close remain **unverified**.

## R4 ready descendant, real timeout and negative control

The old one-second test could time out before the fake driver spawned its child;
the TIMEOUT outcome alone did not establish descendant termination. Adding a
1.2-second startup delay reproduced its exact missing `grandchild.pid` failure.
This demonstrates a fixture timing mechanism, not proof of the historical host
scheduling cause.

The fixture now waits up to ten seconds for the real child to write its own PID,
then verifies that it is alive and belongs to the driver process group before
returning from the test-only Popen seam. Production `communicate(timeout=1.0)`
and group termination still run against real processes. After TIMEOUT the test
must observe the child absent **before** cleanup. Startup delay is no longer
mistaken for coverage of an engine that never existed.

A test-only three-second post-kill pipe-drain bound prevents a broken terminator
from waiting for the child's natural 30-second exit and falsely passing. The
negative control replaces only termination with driver-only termination: the
drain times out, CompileManager reports INTERNAL_ERROR, and the helper's required
TIMEOUT assertion fails. The negative-control test asserts that rejection and
captures the expected TimeoutExpired log. Cleanup then kills/reaps the owned
group; cleanup cannot establish the earlier assertion. Windows retains its
existing skip because this fixture tests POSIX process groups.

R4's local fixture-readiness and false-green-detection work is implemented with
focused evidence. It does not change application cancellation policy, certify
arbitrary process trees or close the separate Qt crashes.

## Commands and results

Focus red: 1 test / 2 direction failures / exit 1,
`/tmp/icstex-v1-inspector-focus-red-r1.log`, SHA-256
`df954e0cdd4138752d6048d13769d8f6f593fc289911654e525463f3561debba`.
Focus expanded: 78 tests / 4.684s / OK / exec 13774 exit 0,
`/tmp/icstex-v1-inspector-focus-focused-r3.log`, SHA-256
`4dec9280faed8b858ab4fb271ac79cf130ec45b5a25119a1a9315206ddb1788b`.

Startup-delay red: 1 test / FileNotFoundError / exit 1,
`/tmp/icstex-v1-process-tree-ready-red-r1.log`, SHA-256
`a740df0e072555c89a906a87e5e302ff48a8b889f013d6ee4d3a33ef18087f0a`.
Final combined focused command:

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_compiler tests.test_gui_editor.WorkbenchShortcutTests \
  tests.test_block_property_drafts tests.test_blocks_gui \
  tests.test_input_composition tests.test_block_editor_targets \
  tests.test_workbench_composition_evidence -v
```

124 tests / 15.503s / OK / exec 55326 exit 0;
log `/tmp/icstex-v1-focus-readiness-focused-r1.log`, SHA-256
`1fa986c0d839c3c2a5cd675f5e8da6cf468234e11c1ebc8faf2c0af052ebe571`.

Intermediate fixture issues remain recorded: green-r1 had an inactive/direct-
dispatch old focus test; integration r1 initially assumed a different Qt typing
Undo grouping. Extended focus r2 waited in QMessageBox during fixture cleanup;
live sample confirmed closeEvent→warning→QDialog::exec, then the owned process
was stopped (exec 50552 exit 143). Cleanup now cancels synthetic source save
timers/dirty flags. No product close guard was weakened. The first negative
control expected a thrown exception, but CompileManager correctly converts it
to INTERNAL_ERROR; the final test checks that actual rejection contract.

Required compileall, probe syntax and diff checks pass. Frozen full regression:

```sh
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10 python3 -m unittest discover -s tests -v
git diff --check
```

1488 tests / 123.977s / OK, exec 16530 closed with explicit shell and tool exit 0.
Log `/tmp/icstex-v1-focus-readiness-suite-r1.log`, SHA-256
`bf124e4c6d0871e43ba72763ba533438dfa99e3bf6957f93184da9f6c90b5d63`.
Post-terminal app/app+tests hashes match; compileall/diff pass again. No
Traceback/RuntimeError/RuntimeWarning/fatal failure in this full log; expected
offscreen plugin warnings remain. Python crash inventory remains the same five
September 10/11 files; absence of a new crash does not fix their historic causes.
Held candidate feed remains
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
All this round's handles are terminal. No native post-fix or installed-app claim.

## Next work and rollback boundary

After unlock, launch a new isolated Inspector probe and verify actual Control+Tab
and Control+Shift+Tab focus roles without unintended Apply/model/disk changes,
then explicit Apply/Save/close. Do not reuse old terminated handles or call the
IME predicate alone proof of focus navigation. R1 input/default-save combinations,
R2 remaining keyboard/high-scale citation review, R3 Qt crash disposition and R5
restricted LuaLaTeX remain; R6 reconciles them before a local acceptance decision.
The independent Beta installation/release gates and external E1–E4 remain open.

Rollback is limited to the Inspector shortcut registration/methods and these
targeted tests/probe observations; do not revert unrelated shared hunks.
Suggested commit (not executed): `fix(gui): route Inspector focus through scoped shortcuts`.
