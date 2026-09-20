# M6 editor/gutter cycle and timer-dispatch follow-up

The editor's owning Python back-reference from its gutter is removed. Two
baseline lifetime assertions fail and then pass; a pending-highlighter editor
collected by a worker crashes on baseline, while the weak-gutter control and
fixed-source 20-cycle probe pass. The original expanded GUI command now passes.
This does not identify every receiver in the historical timer crash reports or
complete native M6/A12 acceptance.

## Scope and source

Authoritative ICSTeX root, branch `codex/v1-development`, unchanged HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`. Existing shared changes and empty
index are preserved. Baseline app SHA-256:
`da75a16945bbae46550b8fce5c207bba7077b6f82d1e72f322c5085e77664477`.
Fixed app:
`e65bac97cb0be2f1a68be509f502a17fea628b3c4d315292dc811b5a7a8e546f`.
Fixed app+tests:
`5d3f32cfe17840a80f9167a7e35d6d50da2cf99a9e9be2b3b5a854ca3be8ad2b`.
Digests use sorted relative Python paths, NUL, bytes, NUL.

Environment: macOS arm64, Python 3.12.6, PySide6/Qt 6.11.1; offscreen,
isolated test settings and synthetic files. No student documents, external
uploads, Git mutation, packaging, installed-app replacement or security changes.
One current native-control inventory request returned `Mac is locked`; no
native test window was launched. Prior physical-input receipts retain their
original source identities, not this patch's identity.

## Discriminating observations

The test-triage skill guided prefix replay and controls rather than repeated
full-suite attempts. An initial diagnostic import used a nonexistent helper and
exited 1 before tests (`/tmp/icstex-v1-timer-prefix-gc-r1.log`); it is not product
evidence. The corrected replay loads the same five modules as the failed
expanded command, flattens their suites in loader order and runs the 131-case
prefix through `GuiEditorTests.test_textcolor_completion_inserts_template_and_focuses_color`.
A `gc.callbacks` observer records generation, current test and Python frames,
without changing collection thresholds or disabling GC.

That replay (exec 38729) again crashes at completion's `processEvents`, exit
139. `Python-2026-09-11-193542.ips`, incident
`96EF44C5-6436-4AAD-A66A-559BE6378462`, records SIGSEGV at 0x33 through
`QCoreApplicationPrivate::notify_helper`, `sendEvent`, `activateTimers`.
The log also shows natural GC starting inside watchdog polling threads.
This is evidence of background Python collection, not proof of which native
receiver failed or that its C++ destructor ran on that worker.

A second observer attached direct `destroyed` callbacks to constructed editors,
windows and selected dialogs. It passed 131 / 17.957s, exec 26260 exit 0, and
recorded no off-GUI destruction among those observed objects. Signal observers
change lifetime/timing; this negative run does not disprove the failure.

The smaller isolated control is equivalent to:

```python
application = QApplication([])
gc.collect()
editor = LaTeXEditor(r"\textc")
observed = weakref.ref(editor, record_finalization_thread)
editor.close()
del editor
worker = threading.Thread(target=gc.collect)
worker.start()
worker.join(5)
application.processEvents()
```

Only the following experimental conditions changed:

| Condition on baseline application | Observed result |
| --- | --- |
| Show editor and drain events before close/release | Wrapper survives release, finalizes on worker; exit 0 |
| Do not drain initial highlighter events | Wrapper survives release, finalizes on worker; SIGSEGV, exit 139 |
| Same pending-event case, replace only `editor.line_number_area.editor` with `weakref.proxy(editor)` | Wrapper finalizes immediately on GUI thread before worker; exit 0 |

The small failing run produced `Python-2026-09-11-193919.ips`, incident
`01B50D9A-EFE1-45C4-81BF-86F0E76F98F3`. Its native stack contains
`mainThreadDeletionHandler` / Python pending calls, not the original timer
dispatch stack. This supports repairing a dangerous lifetime cycle, but is not
an exact stack-equivalent reproduction of the earlier SIGBUS. Do not claim
that Shiboken never schedules deletion back to the main thread.

Qt documents [GUI thread affinity and object lifetime](https://doc.qt.io/qt-6/threads-qobject.html).
Python's [weak references](https://docs.python.org/3/library/weakref.html) do not
keep their referent alive. The concrete local control, not these general rules
alone, establishes the editor/gutter cycle and the change in release behavior.

## Repair and regression assertions

`app/gui/latex_editor.py` changes only `LineNumberArea.editor` to a weak proxy.
Qt's existing parent still owns the gutter; live size/paint forwarding is
unchanged. No global GC policy, watcher threading, timer interval, queued work,
source text, input-method behavior, save/compile guard or document ownership
format changes. No persistent keepalive cache or Qt-library patch is introduced.

Two new `WindowLifetimeTests` assert:

- An unowned editor with pending Qt work releases immediately on the GUI thread,
  without requiring cyclic GC; the test cleans a failing baseline on the GUI
  thread rather than leaving it for a later worker.
- A Qt-parented editor survives dropping the external Python reference, still
  paints its gutter with the correct width/text, then releases when its parent
  is destroyed. Thus the repair does not remove Qt ownership or kill live editors.

Baseline red: 2 / 0.135s, both fail, exit 1. Fixed focused window lifetime,
editor/gutter smoke and completion: 9 / 1.983s / OK, exec 8322 exit 0.
Fixed-source pending-event release -> real worker GC -> event dispatch passes
20 cycles; every observed wrapper finalizes on the GUI thread before the worker.

The exact originally failed expanded command:

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_gui_editor tests.test_project_file_ops \
  tests.test_gui_submission_check tests.test_gui_preview_pipeline tests.test_pdf_panel -v
```

passes 252 / 59.446s / OK, exec 38659 explicit exit 0. The old failed command
and reports remain evidence; this is not a blanket absence-of-crashes claim.

After the full, two disposable processes replayed the same 131-test prefix with
identical weakref-only editor-finalization observers. The control restored only
the old strong gutter backlink after construction; no repository source changed.
Both exited 0 (exec 88596; each child status printed explicitly): fixed
16.565s, strong control 15.903s. The fixed run observed 21 GUI / 5 worker wrapper
finalizations before its end marker; the control observed 17 / 6. These are
Python wrapper finalizations, **not** native QObject deletion observations.
The five shared worker cases come from hidden-panel, history-refresh,
open-new-window and panel-edit-burst fixtures whose windows are closed; their
native objects may already have been deleted. Do not call that a new unsafe
native deletion without checking the C++ lifetime separately. Neither prefix
run reproduces the original signal, so the gutter fix alone is not proved to
explain it. The exact original-prefix causal link remains open.

## Evidence ledger

All logs below are under `/tmp/`; report hashes identify retained macOS reports.

| Filename | SHA-256 |
| --- | --- |
| icstex-v1-timer-prefix-gc-r2.log | 1358d63099026d5ddf302a303f386241e22523e5f9712f6bc39a1fe552a98b5b |
| icstex-v1-timer-lifetime-observer-r1.log | 224183d86f506d5650216d1b83e940912f6d348875a2fb46f4308d923e9e127d |
| icstex-v1-timer-worker-gc-r1.log | c4eba0f5409310108f68026c9c8ba571b0e84e1a7f0eb500b5ffeedcf84f778a |
| icstex-v1-timer-worker-gc-pending-r1.log | 5dae068778d2a5a14fd3b5db6d27fc3f1294b5e13738104f14cbfa2e5415fec3 |
| icstex-v1-timer-worker-weak-gutter-r1.log | 3187cda9aa03326c888fc3ae47def336404e874358df2afdfcd1ae875a23a485 |
| icstex-v1-gutter-lifetime-red-r1.log | 725ee3fe945f859be5164ae98828752bb92a35f662bbe1378d81f62aff393597 |
| icstex-v1-gutter-lifetime-focused-r1.log | c2a7f4b42ccf31c224439cccba7c26d5d55ec9171cb49e782591b8189b1ea970 |
| icstex-v1-gutter-lifetime-expanded-r1.log | 9b86db4ef63a6862310709ad6d13be26968da09b16ac6064e40116e92f5342f6 |
| icstex-v1-gutter-worker-cycles-r1.log | df7731d629ae8309e0f95dcfa0bdcbdb4a74d9c455be046695c9eb3487cf6c6d |
| icstex-v1-gutter-prefix-control-0-r1.log | a011a6bc163a407b19087656f3e7416618cecb661e665d275a6fbeb2e7a19b13 |
| icstex-v1-gutter-prefix-control-1-r1.log | 44c84706d0c3464607ea00e99a7eb9f799b36ddbcccc272927b0166c79a271a2 |
| Python-2026-09-11-193542.ips | 8117e1041d2d36c622f574b8dde8d87efd8d0d7699238deaa5a6b1cc2fdce332 |
| Python-2026-09-11-193919.ips | 87f333b27989de376de65e3af07944d44a3839d88e90266f0da24aa4ba48606a |

## Required full and next boundary

Required frozen full: 1522 / 143.802s / OK, exec 9432 explicit shell/tool exit 0.
`/tmp/icstex-v1-gutter-lifetime-suite-r1.log`, SHA-256
`9c62a8df7e2bbded731c4daa44db670be67e77035b180857230b0437444ccfae`.
Post-terminal app/app+tests digests match; compileall and diff checks pass.
The full log has no fatal Python, Traceback, RuntimeError/RuntimeWarning or
QObject/QThread failure. The retained crash inventory is ten after the full,
with the two baseline diagnostics above added this round, not fixed-source
full-run crashes. HEAD/index/held candidate feed are unchanged.

R3's editor/gutter cycle has bounded causal evidence; exact historical timer
receivers, stylesheet-object identity and scoped AX limitations remain distinct.
The next discriminating background check is to separate already-deleted Qt
objects' wrapper recycling from pending native deletion in the identified
closed-window fixtures, recording the actual deferred-delete boundary and thread.
Do not repeat the now-terminal pair blindly or globally alter test cleanup/GC.
R1/R2 current-source physical composition/focus/layout need a usable native
control channel. R5 engine/security decision, R6 reconciliation and E1–E4 are
still open. No complete V1 or release-candidate recommendation.
All handles in this round are terminal. The final prefix pair added no report;
post-pair source/HEAD/index/held candidate checks retain their verified identity.

Rollback only the gutter weak reference and its two regression tests; preserve
all other shared changes. Suggested commit only:
`fix(gui): avoid owning editor cycles in the line-number gutter`.
