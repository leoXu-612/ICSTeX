# Migrated-window confirmation, lifetime and activation

Native r2 established a focus defect: the confirmed migration window was visible
and alive, but closing the application-modal dialog reactivated the original
owner. A narrow post-modal activation fix now passes native r3: the copied Block
project is the active window, with keyboard focus in its search field. Original
and copied bytes remain unchanged; opening still does not authorize compilation.

## Activation repair and native red/green

Current application SHA-256:
`4e0720eb707fecce1394a7b5f20868be7ea9bd668ba56b615297c23afa267e54`.
Current app+tests SHA-256:
`ddf709d30299aa185630c6fc56ec290e085245d36651931c5a09425ab28a1d73`.
Branch/HEAD, environment and probe identity remain as recorded below.

Native r2 reused the retained copy through the real production modal wrapper.
CUA Tab/Space opened the separate confirmation, Return selected default No,
then a second confirmation used separately observed Shift-Tab/Space Yes.
At 63.519 seconds the dialog was already destroyed, the copied window was
visible/exposed but inactive, and the original owner was active. CUA continued
to return the original owner. This establishes activation failure, not a missing
window or a collection/lifetime failure. Exec 40617 exited 0 after explicit QA
finish: no errors, timeout or interruption; both tracked windows destroyed.
Report `/tmp/icstex-v1-migration-window-20260912-r2/report.json`, SHA-256
`f297e0827484c012b3ecbd3bc98ee3f250718a66736c0a3e38e116596f89d7cd`.
Probe exit 0 means clean observation/cleanup, not a passing focus assertion.

`show_project_migration` now raises and activates only a valid, explicitly opened
copy, after `dialog.exec()` and its cleanup have returned. It does not change
spawn ownership, confirmation defaults, cancellation, file checks or compilation.
The existing lifetime test now exercises the real production wrapper and asserts
that both activation requests target the new window after no modal remains.
A new cancellation test proves neither request occurs when no copy was opened.

- Baseline: 2 tests / 0.977s, one intended failure for missing activation;
  exec 87688 exit 1. Log `/tmp/icstex-v1-migration-activation-red-20260912-r1.log`,
  SHA-256 `2f3af03d0c3d436c50bf5356352cb50e9598f8ef037f2b356e3dcf72ea2befe5`.
- Fixed: 2 / 0.881s / OK, exec 22186 exit 0. Log
  `/tmp/icstex-v1-migration-activation-green-20260912-r1.log`, SHA-256
  `4ce373e1be2964dfcaae81b303277623e26aa9f18c21b6720ace2f05ff6e8d14`.
- Related migration/checkpoint/recovery/modal keyboard modules: 38 / 26.809s /
  OK, exec 55381 exit 0. Log
  `/tmp/icstex-v1-migration-activation-expanded-20260912-r1.log`, SHA-256
  `55dd119394b062ec1eadbad94d91d74dc8fb375581791219e4138424ceef8e40`.

Native r3 used the unchanged probe and retained copy/source, with the same
physical No-to-Yes sequence. At 49.551 seconds the dialog was destroyed and the
copied window was visible/exposed/active while the original owner was inactive.
CUA returned the Block window with focus on Search Block; a native screenshot
also showed the copied layout. No manual Raise action was used to obtain that
result. Explicit window close returned to the original owner; QA Finish then
ended exec 96010 with exit 0. Both tracked windows were destroyed, errors empty,
no timeout/interruption, source/copy unchanged and both app digests equal.
Report `/tmp/icstex-v1-migration-window-20260912-r3/report.json`, SHA-256
`c7f7f1c1b8084128dcda0faea3eeca312e71dfa662054c999ea0012b33c5e280`.
No publication, draft application or compilation was repeated. This closes the
observed native activation case, not OS/menu keyboard-only acceptance or R3.

Required full: 1588 / 313.379s / OK, exec 32984 terminal exit 0. Log
`/tmp/icstex-v1-migration-activation-full-20260912-r1.log`, SHA-256
`f39dc4c6aabf1c241fe805785f243193d3d6a0a54b776cbdc86d646f1a44cb96`.
Post-terminal app/app+tests digests match the current identities above;
compileall and diff checks pass. All handles are terminal and QA windows closed.
The test-triage skill guided the smallest failing scope, focused repair, native
confirmation and one required full regression, not repeated coverage sweeps.
The earlier 1587-test result below retains its pre-activation source identity.

## Earlier lifetime-only source and bounded evidence

Branch `codex/v1-development`, HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`;
index empty, shared changes preserved. Application digest remains
`da2b8d242bf75091e7ed81ce6b4cb66e545c2544225421e52aa6ed77f1ec52c5`.
Application plus tests digest is
`019169dd24d375f59e56f1568857fd6878979db4c94316628d17d5dc386a8fc5`.
The same sorted relative Python-path/NUL/bytes/NUL convention applies.
Environment: macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1.

The existing synthetic `legacy-keyboard-copy-100` from native modal r6 was reused:
no third migration publication or compilation was performed. A direct real
`open_migration_project` call verifies the twelve-file legacy copy, creates a
registered, visible MainWindow and binds its saved Block session. Both compile
authorization sets remain empty/false. Event processing and collection leave
the new window valid; explicit cleanup destroys both windows. Exec 78862 exit 0.

A second offscreen check exercises actual QMessageBox instances, default No,
Return cancellation, then Shift-Tab/Space Yes, the asynchronous identity recheck
and real dialog close. The independent window remains visible and native-valid
after DeferredDelete destroys the migration dialog. Exec 65485 exit 0. These
diagnostic commands returned their results directly; no standalone log file is
claimed for them. The test-triage skill guided this smallest discriminating
sequence; neither passing result is a native-window activation proof.

## Regression assertion and control

`tests/test_project_migration_gui.py` adds
`test_modal_no_then_keyboard_yes_keeps_new_window_after_dialog_disposal`.
Publication uses the existing fixture setup; the subsequent two QMessageBox
confirmations are real, not mocked. The test checks default/focused No, explicit
keyboard Yes, visible/registered new window, correct project binding, no implicit
compile/draft application, dialog native destruction, surviving original/new
windows, original raw bytes and original unsaved draft. Teardown now safely
handles this intentionally already-destroyed dialog.

- Focused: 1/0.625s/OK, exec 57509 exit 0. Log
  `/tmp/icstex-v1-migration-window-focused-20260912-r1.log`, SHA-256
  `b4c283a06b7b1cd26f4a7f58134fbb6bd7a9c2dd2db9e9df705e7c2ce2675e6c`.
- Hidden-window control: a process-local wrapper calls the real spawn method
  then hides only the new window. The new assertion fails at `new.isVisible()`:
  1/0.529s, one failure, exit 1. This proves detection of that control, not that
  the historical native run hid its window. Log
  `/tmp/icstex-v1-migration-window-hidden-negative-20260912-r1.log`, SHA-256
  `188903b27842e18cc61d57763b31374ed0892c04cd923cdfb22bd54ca1d1e607`.
- Expanded migration/checkpoint/recovery/modal keyboard scope: 37/24.662s/OK,
  exec 5264 exit 0. Log
  `/tmp/icstex-v1-migration-window-expanded-20260912-r1.log`, SHA-256
  `e8d4fe17712b41b5d4f919537be278031652379e5c9ea78c51230b945732e53f`.

Required full: 1587/280.723s/OK, exec 87633 terminal exit 0. Log
`/tmp/icstex-v1-migration-window-full-20260912-r1.log`, SHA-256
`c1f3e3d3c8379fda8dadf2559e0f89c8d33051540b314c47cda29fc7aa65f5b6`.
Compileall/probe syntax/diff checks pass; both Python tree digests match after
terminal completion. Both retained twelve-file migration copies pass the real
reader again; eleven retained Python crash reports are unchanged. All handles
in this investigation are terminal.

## Native observation boundary

`tools/probe_migration_window_visibility.py` prepares only the retained-copy
post-publication state, then invokes the real production modal wrapper and open
confirmation. It records all MainWindows, visibility/activation/exposure, project
binding and show/hide/close events, including windows not returned by CUA's active
window view. It does not generate keys, answer confirmation or compile.

Native r1, `/tmp/icstex-v1-migration-window-20260912-r1`, was launched once.
The first CUA call reported a newly locked Mac before any test key was sent.
The owned process received SIGINT and its same exec 22600 reached terminal
exit 1; `interrupted=true`, errors empty, no timeout, copy/source unchanged.
Owner Close/Hide and a final empty native window list were observed. The initial
report's `windows_destroyed=[]` is not a destruction assertion: windows had
already closed before final enumeration. The probe now retains observed window
references for a nonempty destruction check on the next run; that diagnostic
change has only syntax verification so far. Current probe SHA-256
`870e242bb7d048b3b0cff919ac2234439887021bb955848ce0f4c5050869ec8a`.
Report SHA-256
`da0e2f476e39667853796ac9d9ab645a00ae2de9faa8ada6241afcf6f9d613dc`.
No native opening/activation acceptance is claimed. Manual unlock was requested
once while background regression continued; no automatic unlock or retry loop.

Native r2/r3 above supersede the earlier pending activation observation.
Do not repeat publication, Block FINAL, checkpoint/restore, IME or PDF workflows.
OS/menu keyboard evidence, R3 retained reliability risk, R5 restricted-engine
decision and E1-E4 remain.
No commit/push, packaging, installed-app replacement, release or student edit.
Suggested commit only: `fix(gui): activate migrated copy after modal confirmation`.
