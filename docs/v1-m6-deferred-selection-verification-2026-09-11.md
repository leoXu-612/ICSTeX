# M6 deferred file selection and renewed timer-dispatch failure

Two file-tree callback defects are reproduced and repaired locally. A separate
native timer-dispatch SIGBUS occurred during expanded offscreen GUI regression;
its cause is **not resolved**. This is not complete M6/A12/V1 acceptance.

## Source and authority

Authoritative ICSTeX root, branch `codex/v1-development`, unchanged HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`. Shared changes and empty index are
preserved. Baseline app `c7e9859961795c2ec082583e9a7aad2fc2e0d60e859e614d784e4a5a4e09676f`.
Current app `da75a16945bbae46550b8fce5c207bba7077b6f82d1e72f322c5085e77664477`;
app+tests `a7eb74546e03b2345ebc8920de93253457eab314e58c1f87d5c231f227e640e6`.
Digests use sorted relative Python paths, NUL, raw bytes, NUL; app then tests.

The computer-use skill's initial Finder state request returned that the Mac was
locked. No native QA window, keyboard input or input-source change was started;
the channel was not repeatedly polled. Offscreen tests use isolated settings and
synthetic temporary files only. No Git mutation, package, installed-app change,
security-setting change, signing, deployment or release operation occurred.

## Reproduced callback defects and bounded repair

`ProjectFileController.perform_move` scheduled a context-free zero-delay callback
to select the moved path. Two tests on baseline prove different invalid owners:

1. Perform an actual safe synthetic rename, accept close, destroy the window at
   the deferred-delete boundary, then drain queued callbacks. The old callback
   accesses a deleted QFileSystemModel and raises RuntimeError.
2. Rename in project one, switch to project two and select its file before the
   queued callback runs. The old callback selects project one's moved path while
   the tree root is still project two.

Red: 2 tests / 0.543s / one error and one failed assertion, exit 1;
`/tmp/icstex-v1-file-selection-red-r1.log`, SHA-256
`1602a37471a5028f44931371b8e7e411c639e27e4b7c21da7c50d819291fba91`.

The callback now uses the window as its QTimer context and checks the captured
project root before selecting. Qt documents cancellation when the supplied
context has been destroyed in [QTimer singleShot](https://doc.qt.io/qt-6/qtimer.html#singleShot-4);
the [PySide6 overload](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QTimer.html#PySide6.QtCore.QTimer.singleShot)
is exercised directly by these tests. No timer interval, filesystem move guard,
reference policy, compiler ownership or source-save logic changed.

Both red tests pass afterward: 2 / 0.432s / exit 0,
`/tmp/icstex-v1-file-selection-green-r1.log`, SHA-256
`3dd7a1090d552f004543df8ee684a820922acfc29f5d2d52c95991911ea05c93`.
The positive actual-window rename case additionally checks selected destination,
unchanged root/editor/cursor/scroll, recent paths, source bytes and no compile
authorization. The broader rename/path/lifetime scope passed 17 / 2.365s,
exec 9161 exit 0; `/tmp/icstex-v1-file-selection-focused-r1.log`, SHA-256
`15f5354748833e6f51b9f1f536217a756adc3301611d74336e6130256efb911a`.
Only a blank line changed application source after this focused run.

## Expanded failure: current-source R3, not a green result

Expanded command:

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_gui_editor tests.test_project_file_ops \
  tests.test_gui_submission_check tests.test_gui_preview_pipeline tests.test_pdf_panel -v
```

Exec 38360 / PID 19769 ended at exit 138, **SIGBUS**. The last test is
`test_textcolor_completion_inserts_template_and_focuses_color`, at its
`QApplication.processEvents()` call; no complete expanded-suite result exists.
Log `/tmp/icstex-v1-file-selection-expanded-r1.log`, SHA-256
`7e4508197b78fd4d50a3620071df48d39ae5b2d5e6549978b251b5bacb8cb457`.

New report: `Python-2026-09-11-191921.ips`, incident
`F3FA2242-649E-4281-97A9-6BA012D89A95`, captured 19:19:18 +0800;
SHA-256 `87584f007eea91006477b8078479346cf012b16894e1e14f2999ff9e57e689d2`.
It records EXC_ARM_DA_ALIGN at 0x59 and QTimerInfoList::activateTimers +1268
below the signal/faulthandler frames. The two old September 10 reports instead
record SIGSEGV in QCoreApplication::sendEvent, also called by activateTimers
+1268. The installed arm64 QtCore UUID EBEA1591-A251-3C70-86C0-C3D0B7901B4B
matches all three reports. This confirms a recurring native dispatch area, not
the same failing QObject or a proved common cause. The new callback RuntimeError
and wrong-root assertion above do not explain this native memory fault.

Bounded diagnostics on unchanged source:

| Diagnostic question | Result |
| --- | --- |
| Does the completion test fail by itself? | 1 / 0.075s / exit 0; isolated test passes |
| Does FormulaComposer + GuiEditor still fail with all rename-named tests excluded? | 138 / 17.406s / exit 0; no reproduction, not proof rename causes it |
| Is the short rename/destroy/root-switch/completion sequence sufficient? | 20 repetitions, 80 / 6.256s / exit 0; no reproduction |
| Can LLDB capture the failing receiver? | System denied attach before tests ran; exit 1. No signing/security changes or bypass attempted |

Logs respectively: `/tmp/icstex-v1-timer-textcolor-isolated-r1.log`,
`/tmp/icstex-v1-timer-no-rename-control-r1.log`,
`/tmp/icstex-v1-timer-rename-sequence-r1.log`,
`/tmp/icstex-v1-timer-debugger-r1.log`. Their SHA-256 values are:

```text
95a17d380c6b0201f5fb7ed8383a7fb3d3039ddb95537d3f0da73c8761251c22
124661b4b3320bfcad8895d9012574dd1ac946b786af1fe197cb04e1b0e63170
d33c14cd4ea16a9c89258c4834f2ef840387a29a1fc70ae429c251929e5e0543
2b2722d3575e51adc81274df75a02cfc4b0a6dce45f68f88fc45364c29ed9221
```

These controls narrow the immediate reproduction question; they do not justify
removing assertions, blanket GC suppression, Qt patching, or a crash-free claim.
The test-triage skill guided the isolated/contrast sequence, not a product fix
for this SIGBUS. Qt's [6.11.1 timer implementation](https://raw.githubusercontent.com/qt/qtbase/v6.11.1/src/corelib/kernel/qtimerinfo_unix.cpp)
places event delivery inside activateTimers, but its source alone does not
identify the receiver that was invalid in this process.

## Required full and remaining work

Required frozen full:

```sh
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10 python3 -m unittest discover -s tests -v
git diff --check
```

1520 tests / 141.008s / OK, exec 36520, explicit shell/tool exit 0.
`/tmp/icstex-v1-file-selection-suite-r1.log`, SHA-256
`67a2564b80dcfdb2144e5640bdc6810e804916274dc00a5bf7acb6bfef176507`.
Post-terminal app/app+tests digests match; compileall/diff pass. This full log has
no Traceback, RuntimeError, RuntimeWarning, fatal Python or QObject/QThread
failure. That result does **not** erase the expanded SIGBUS or close R3.
The crash inventory remains eight after this full; all test/debugger handles are
terminal. HEAD and empty index remain unchanged; held candidate feed SHA-256 is
still `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

Next background work is bounded test-order/dispatch-lifetime isolation of this
current-source SIGBUS. Preserve the full failing command and controls. Do not
repeat full suites without a new diagnostic question. Native R1/R2 awaits a
usable unlocked control channel; R5 security/platform decision, R6 and external
E1–E4 remain separate. No local-source-complete or release-candidate claim.

Rollback only the context/root guard and associated regression assertions;
preserve all other shared changes. Suggested commit, not executed:
`fix(gui): bind deferred file selection to its window and project`.
