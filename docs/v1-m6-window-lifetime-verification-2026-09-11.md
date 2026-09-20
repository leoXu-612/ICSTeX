# M6 accepted-window-close lifetime verification

Status: accepted-close retention is reproduced and repaired. Focused/expanded
tests, repeated offscreen close/scale diagnostics and Cocoa close/delivery
workflows pass. The current required full regression passed 1446 tests. The earlier
Qt stylesheet SIGSEGV has **not** been causally reproduced or proven fixed;
this is not complete M6, V1, platform/IME/AX/human acceptance or release readiness.

## Evidence and mechanism

Existing MainWindow accepted close retires compilation, watchers and analysis
controllers and unregisters the application window. Reopening that retired
object is not a supported workflow. However, without delete-on-close, its Qt
widgets and Python/controller references can remain alive after the user closes
the window. A long-lived QApplication continues styling those hidden objects.

`tools/probe_qt_style_lifecycle.py` creates only empty windows with isolated INI
settings. The old source's 3 batches of 8 confirmed closes retain all 24 closed
MainWindow wrappers and 15,275 widgets after explicit GC/deferred-event handling.
The explicit `deleteLater` control retains no closed MainWindow and 611 widgets
for its one surviving window. Neither natural nor forced-GC-during-StyleChange
diagnostic reproduced the earlier native SIGSEGV. The retention observation is
therefore a separate reproducible defect, not a proved crash explanation.

| Observation | Source / mode | Closed MainWindows after final GC | Total widgets |
| --- | --- | ---: | ---: |
| Original behavior | d0a70129 / close, 24 windows | 24 | 15,275 |
| Destruction control | d0a70129 / explicit delete, 24 windows | 0 | 611 |
| Repaired behavior | 2f8d15e0 / close, 24 windows | 0 | 611 |
| Repaired native behavior | 2f8d15e0 / Cocoa close, 6 windows | 0 | 610 |

These are bounded synthetic observations. `max_rss` is a process high-water mark,
not current allocated memory or proof of all resources being returned to the OS.
Per-scale timings explain diagnostic cost but are not performance acceptance:
some follow-up runs overlap tests, samples are few, and complete project/editor
load is absent. No percentage performance improvement is claimed.

The first diagnostic mislabeled GC inside snapshot formatting as `gc_in_scale`;
its recorded stack names identify that mistake. The probe phase label was fixed
before later runs. The original object counts and final explicit-GC retention
observation are unchanged by that labeling error. Forced GC is fault injection,
not normal-use evidence.

## Bounded repair and regression coverage

- MainWindow sets Qt's standard `WA_DeleteOnClose`. Destruction follows accepted
  close; an ignored close keeps the live window and drafts. The existing guards,
  saved-file handling, checkpoint holds and controller shutdown order remain.
  Accepted close also unregisters the window from UiScaleManager immediately.
- The two new tests fail before the repair and pass after it. They prove actual
  new-window registration, destruction of the closed window/PDF child at the
  event boundary, survival/continued scaling of another window, and Cancel
  preserving the unsaved source/controller before later explicit Discard.
- One existing submission-check test cleanup processed events and then called
  `deleteLater` on the now-destroyed window. Expanded r1 reported two teardown
  errors, not failed product assertions. Cleanup now asserts accepted close and
  actual destruction instead of deleting twice; no behavioral assertion was
  removed or weakened.
- No global GC suppression, Qt binary patch, OS setting, new dependency, project
  format, source-writing behavior or multi-process policy change was introduced.
  Rollback is the new window attribute/unregister and corresponding lifetime
  assertions, not the user's pre-existing M4/M5 changes.

Qt documents accepted/ignored close and delete-on-close in the
[QCloseEvent reference](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QCloseEvent.html).
The `test-triage` skill informed failure classification and focused-scope checks;
this project continues to use unittest, not Xcode or SwiftPM.

## Test and source receipts

Environment: macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1. No student
project, installed app, signing key, package or release was touched.

Current app SHA-256:
`2f8d15e03061a54fa7780ec07d8dde7164a661123286bece4d00b13a5f63e16d`.
Current app+tests SHA-256:
`aa139cd92b649c2669a0a771bc2b099829e86afa3a21dd27ce4aa43b358c2552`.
Digest convention remains sorted relative Python paths/NUL/raw bytes/NUL, app
then tests. HEAD is still `3bde2b5`; later source work remains uncommitted.

- Red: `tests.test_gui_editor.WindowLifetimeTests`, 2 tests / 2 failures,
  exec 22320 / exit 1; `/tmp/icstex-v1-m6-window-lifetime-red-r1.log`.
- Initial focused: lifetime, source/Block close cancellation and scale,
  13 tests in 4.741s, exec 98451 / exit 0;
  `/tmp/icstex-v1-m6-window-lifetime-focused-r1.log`.
- Expanded r1: 244 tests in 48.239s, 2 teardown errors as explained above,
  exec 65091 / exit 1. Expanded r2: 244 tests in 47.455s, OK, exec 83090 /
  exit 0; `/tmp/icstex-v1-m6-window-lifetime-expanded-r2.log`.
  Modules: gui_editor, ui_scale, submission_delivery_gui, project_migration_gui,
  gui_submission_check and gui_preview_pipeline.
- The final test refinement uses actual `spawn_window()` registration rather
  than two unrelated constructors. The same lifetime module passes again,
  `/tmp/icstex-v1-m6-window-lifetime-focused-r2.log`; the app source is unchanged.
- Required compileall and diff check passed before the full source freeze.
  Required full regression runs with offscreen, PYTHONFAULTHANDLER=1 and nice 10,
  exec 85117 / PID 70795, started 2026-09-11T06:09:14Z, log
  `/tmp/icstex-v1-m6-window-lifetime-suite-r1.log`.
  TERMINAL/PASS: 1446 tests in 113.088s, OK, exit 0. Log SHA-256
  `f27b899cbbce984e1280fda80e2f022eaff309abb30f9ab50b8352e22e188931`.
  Both app/tests hashes match after terminal collection; compileall/diff pass
  again. No Traceback/RuntimeError/failure record or new Python crash report.
  No concurrent native probe during this full run; elapsed time is still not an
  application performance benchmark. The handle is closed; do not restart it.

## Diagnostic and native receipts

All listed diagnostic/product and full handles have ended, exit 0. No known
test/native process remains active. Before/after native Python crash inventories contain the
same five reports, including the earlier `Python-2026-09-11-134542.ips`.

- Original close: exec 82196; result
  `/tmp/icstex-v1-m6-style-close-20260911-r1/result.json`, SHA-256
  `703bafa7957ba397a4c1796af0e76085667da17ecc6e0b4dce756f9d9f9db281`.
- Explicit-delete control: exec 18852; result
  `/tmp/icstex-v1-m6-style-delete-20260911-r1/result.json`, SHA-256
  `e2cec6ee62d168369d516f5be3e0686a8fef63354e7ca7bcb07169f76c8bf57e`.
- Fixed close: exec 82257; result
  `/tmp/icstex-v1-m6-style-close-20260911-r2/result.json`, SHA-256
  `a200d2bd5f710dd4e27ea187fbf08f4c0a8c658347f61749996c8919ef5038ae`.
- Forced-GC old/fixed diagnostics: exec 3825 / 33657; result directories
  `/tmp/icstex-v1-m6-style-forced-20260911-r1` and `...-r2`. Neither crashes;
  the fixed run retains no closed MainWindow despite 12 in-style full collections.
- Cocoa lifecycle: exec 23874 / PID 70508, `--native --windows 3 --cycles 2
  --expect-released`; result
  `/tmp/icstex-v1-m6-style-native-20260911-r1/result.json`, SHA-256
  `b3c73a46587988b2f0f6e9ca222619fd7cd4c71462185528046a371a464af715`.
  The surviving window screenshot was inspected after 6 actual close operations
  and repeated scaling. No AX scan or physical keyboard/IME task was performed.
- Cocoa delivery: exec 59032 / PID 70518, existing actual GUI probe;
  `/tmp/icstex-v1-m6-close-delivery-native-20260911-r1/result.json`, SHA-256
  `1127fcf12b1c86201dda7b5aaa9590fb287df2240761d92d73245809886faad8`.
  Single/multi/main Block/standalone Block complete Save/FINAL/review/Cancel/
  PDF-only/source-report publication, byte checks, independent source recompile
  and checkpoint restore/recompile. Original bytes remain unchanged; the Block
  published-package screenshot was inspected. Both native probes overlap briefly,
  so they do not establish independent focus or latency acceptance. All windows
  have closed, with no new traceback or Python crash report observed.

Final diagnostic script SHA-256:
`15718f4f4348ba7381e24d7b7f48c3918ed771713b978ad0ddaaf2dac9bb01c9`.
Native QA used the purpose-built in-process Qt test harness, not external desktop
input automation. Full focus, IME and assistive-technology use remain untested.

## Remaining work

The earlier whole-suite stylesheet SIGSEGV remains unexplained. Retention repair
and green runs cannot certify all native object lifetimes. Preserve that risk
through the remaining M6 matrix; do not repeatedly rerun a full suite without a
new diagnostic question. M5 build-time tool-version evidence and the uncompleted
M2-M6 native/platform/human matrix remain separate required work. Beta installation
lifetime exclusion and release authorization remain independent and unchanged.
