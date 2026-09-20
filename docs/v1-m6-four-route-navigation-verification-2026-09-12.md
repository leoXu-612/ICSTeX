# M6 four-route keyboard navigation follow-up

Current follow-up: the later r3 run completed error/diagnostic Return actions;
the [console/PDF receipt](v1-m6-console-pdf-native-verification-2026-09-12.md)
records its separate source identity and newly found console clipping. The
failed/locked runs below remain historical partial evidence, not passes.

Date: 2026-09-12. **Partial native coverage, not four-route acceptance.** Actual
keyboard input verified outline and search navigation before the Mac locked
again. Diagnostics and compiler errors were not exercised. No student files,
installed application, compilation, Git mutation or release operation was used.

## Observed native result

```sh
QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3 tools/probe_citation_layout.py \
  --native-observe --readonly-navigation \
  --output /tmp/icstex-v1-four-route-native-20260912-r1
```

The labelled fixture contains two real source headings and one search match.
Diagnostics and compiler-error records are explicitly synthetic navigation
inputs, not the output of a compiler or project check. Search was triggered
through the actual UI; the observer did not initiate it or inject navigation.
Table cells, current/selected rows, focus, activation and resulting source
file/line are recorded. A focus frame alone is not counted as selection.

App tree before/after the native run:
`9b2f44f5d46bd7b2895a6c73ea8f19d1228495b80da9d91c41916d6de21d181b`.
Loaded probe SHA-256:
`df5986673fe9aea3ac6e010c9bfbdd47e6429a14252c68dd759f114e481a2bcf`.
Report SHA-256:
`c6dcef7ffe91384ab8802ed2fb55bc05319d851b6e9f1b07e4f0c17f3462340b`.

| Route | Actual action and result |
| --- | --- |
| Outline | Tab through rail/Refresh into the real outline, Down selects Second, Return emits once and moves the source cursor to `main.tex:5` at 43.3226s. |
| Search | Real query `navigationneedle` returns one child result. Tab gives focus without a selected row; Return does nothing, as intended by the empty-selection guard. Space selects the current row; Return emits once and opens `chapters/long-path-for-source-navigation/child.tex:3` at 334.6911s. |
| Diagnostics | Two labelled records were populated, but native activation was not performed. |
| Compiler errors | Two labelled records were populated, but native activation was not performed. |

The clipboard tool timed out waiting for acknowledgment, but a subsequent AX
read showed the correct query already present. It was not pasted twice. A later
CUA attempt to select the error tab returned an explicit locked-Mac error; the
last observed bottom tab remains Log, with only two activation records. No
further foreground calls or new native window followed that lock response.

The same live process, exec 22952 / PID 74112, was observed until its existing
600-second deadline. It wrote the partial report, closed/destroyed its window
and exited **1**, with `timeout=true`, `read_only=true`, no observer exceptions,
zero compile starts and no compile authority. Every recorded file-byte check
passes. This is preserved partial evidence, not an overall native pass.
Actual Return uses Qt's Return route; native numeric-keypad Enter is not claimed.

## Follow-up source and tests

Only the four table tooltips changed in `project_panels.py`,
`diagnostics_panel.py` and `main_window_signals.py`: arrows move, Space selects
the current row, Return/Enter locates, Tab changes control. The source guide
explains the single-result case. The selection guard and activation logic are
unchanged; no save/compile/repair behavior is newly authorized.

`ReadOnlyNavigationShortcutTests.test_single_search_result_can_be_selected_with_space_before_return`
uses one real search result: empty selection refuses Return; Space selects;
Return navigates exactly once; source bytes and compile authority are unchanged.
Its baseline has four missing-hint assertions, not four broken location routes.
Red log `/tmp/icstex-v1-single-result-selection-red-20260912-r1.log`, exit 1,
SHA-256 `97fc37743924b7b80ad08eeb8adafebc463bd76b7f632439f88d9d0eb7b24f8c`.
Final focused command covers `tests.test_gui_editor.ReadOnlyNavigationShortcutTests`
and the MainWindow rail-order test: **4 / 1.108s / OK**, exec 70086 exit 0.
Log `/tmp/icstex-v1-four-route-focused-20260912-r2.log`, SHA-256
`033752dea4727bc146daeec28faea8a067e03b3e872a31213241ac2459e06f43`.

The probe additionally preserves a partial report on KeyboardInterrupt and
refuses a successful result. An explicitly marked offscreen/mock interruption
fixture verifies this branch and window destruction; its platform precondition
is mocked solely for that test. It is **not native evidence**. Report
`/tmp/icstex-v1-four-route-interruption-fixture-20260912-r1/report.json`, SHA-256
`dcb4cdd5e7b33690b584d6916737229d87bb9f4c1d073fc17e548c3ede9606c4`.
Final probe SHA-256:
`83d824d6cbc68760f46e009980352c35d58049daaa5d54460719a17eadfb00c2`.

Current app tree:
`60e50d6fbefd94a09fbb3ffbd1f652e3bc3cc8f6fffc2873396088d7723492c0`.
App+tests:
`907f675326dead46d546436036f9bfdb06bd7088c4d9de6168c928f73b2af6ba`.
These are sorted relative Python path/NUL/bytes/NUL digests. The current app
differs from the native run only in the four explanatory tooltips; do not
relabel the older native run with this hash. Compileall and probe py_compile
pass. Required `QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest
discover -s tests` completed **1561 / 164.006s / OK**, exec 71950 terminal exit 0.
Log `/tmp/icstex-v1-four-route-full-20260912-r1.log`, SHA-256
`accf27559fc3b214e8d2e8157fa1a16a247699fbb0aaf829fed4ff0a939d2a8d`.
Post-terminal tree digests match; diff check passes. Eleven retained Python
crash reports are unchanged. All test/probe handles are terminal, with no live
native observation process. HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`,
empty index and held feed SHA-256
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`
are unchanged. No commit, push, packaging, install replacement or publication.

## Fresh unlock follow-up: control unavailable before input

After the user's next unlock confirmation, r2 launched the same labelled
synthetic fixture on app `60e50d6f` with probe `83d824d6`. The first CUA
`getApp("Python")` call still returned "The Mac is locked and automatic unlock
could not unlock it." This is the control service's reported state, not a claim
that the user did not unlock the visible desktop. No subsequent foreground
call was attempted and no keys or navigation actions were sent.

Only the identified r2 probe process (PID 76832, exec 16200) received SIGINT.
The observer retained `/tmp/icstex-v1-four-route-native-20260912-r2/report.json`,
destroyed its window and exited **1**. It records `interrupted=true`,
`timeout=false`, `window_destroyed=true`, `read_only=true`, no observation
exceptions, keys, actions, compile starts or compile authority. Before/after
app digests match. Report SHA-256:
`0e50a3d837288241e1a4101f2465a9a4c7213f41203cf366ca62714659e2482d`.
No probe remains running and the eleven retained crash reports are unchanged.
No application/test source changed, so this did not repeat the previously
completed 1561-test regression. This is an interrupted setup, not new native
acceptance. The remaining routes/PDF need a usable unlocked control session.

On the next automatic continuation, a read-only `ioreg -n Root -d 1 -l`
check, filtered to session boolean fields, returned
`kCGSSessionOnConsoleKey=Yes` and `CGSSessionScreenIsLocked=Yes`.
Thus the OS session also reported locked at that later observation; the earlier
CUA error is not the only evidence. No desktop-control retry or test window was
started. No probe/full-suite process remained live. Recomputed app/app+tests
digests and the prior full-suite log hash match the identities above; the log
still records 1561 / 164.006s / OK. These are identity checks, not a new run.
The unchanged remaining local gates require native access or a separate
security/toolchain decision; rerunning completed tests would not close them.

## Next action and boundaries

After a new manual unlock, announce a fresh synthetic window and verify the
remaining diagnostics/error keyboard activation, then the separate native 200%
PDF observation. Do not restart the completed outline/search or earlier
citation/rail/Inspector/Pinyin cases merely to accumulate passing counts.
R3 historical timer/stylesheet attribution and scoped AX limitations, R5
restricted LuaLaTeX policy/toolchain decision and E1–E4 are unchanged.
