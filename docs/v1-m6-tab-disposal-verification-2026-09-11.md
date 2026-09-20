# M6 closed-tab disposal and native/wrapper distinction

Confirmed tab closure now schedules destruction of the removed editor and its
Qt children. Before the repair, 24 closed tabs remained as live native editors
inside the tab stack; after it, only the one open editor remains. Cancellation
and failed save retain the editor. This is a resource-lifetime repair, not a
claim to have explained every earlier native timer crash.

## Source and authority

Authoritative ICSTeX root, `codex/v1-development`, unchanged HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`; shared changes/index preserved.
Baseline app SHA-256:
`e65bac97cb0be2f1a68be509f502a17fea628b3c4d315292dc811b5a7a8e546f`.
Final app:
`890bbd2c2968cbd5de120a729cccb6bb0951d1f9af5d3a48db8fbcdfcb0fd514`.
Final app+tests:
`39f1a73e8c287e85bf8ef69b47052bdf55bfcaa681064815d31ceb2a72f86f50`.
Digests use sorted relative Python paths, NUL, raw bytes, NUL.

Python 3.12.6, PySide6/Qt 6.11.1, macOS arm64, offscreen. All source files and
settings in the tests are synthetic and temporary. No foreground/native-control
attempt this round: the last channel state reported locked. No user content,
installed app, Git mutation, packaging, security setting or release changed.

## R3 observation: native deletion is not wrapper collection

The test-triage skill guided a discriminating test of the five worker-side
wrapper finalizations seen in the previous receipt. Two independent signals
were recorded without retaining a native editor: `QObject.destroyed` with a
direct connection records native deletion; a weakref callback records Python
wrapper finalization. Records retain only labels/thread/phase values.

- Four existing fixtures (hidden panel, history refresh, open new window and
  panel edit burst) pass separately. After their normal close, explicit
  DeferredDelete delivery makes each native editor invalid on the GUI thread.
  Subsequent real worker GC finalizes all five wrappers; exit 0, exec 57779.
- The same original 131-test prefix was then run with these observers, without
  added event drains, GC calls or cleanup changes. It passes 131 / 16.593s,
  exec 33175 exit 0. All five worker-finalized wrappers have an earlier native
  destruction record on the GUI thread, matching the four fixture origins.

These runs establish that the observed five wrapper finalizations are not
evidence of new cross-thread native destruction. Instrumentation can change
timing, so this does not identify the earlier failing timer receiver or erase
its reports. Do not alter production GC or watcher behavior based on this
discarded inference. The earlier editor/gutter cycle repair retains its own
bounded red/control evidence.

## Independent closed-tab retention defect

`EditorTabManager.close_at` retired the tab's save/compile/watch ownership and
removed it from the visible tab widget and Python tab map. It did not dispose
of the removed widget. Qt explicitly documents that
[removeTab does not delete the page widget](https://doc.qt.io/qt-6/qtabwidget.html#removeTab).

The baseline synthetic probe keeps one initial editor, creates and explicitly
discards 24 further unsaved editors, each containing 1,000 synthetic lines.
After every close it delivers DeferredDelete and processes Qt events. Keeping
Python references allows `shiboken6.isValid` to test actual native lifetime,
not merely whether Python has collected a wrapper.

| Measurement | Baseline | Fixed source |
| --- | --- | --- |
| Visible/open tabs | 1 | 1 |
| Native LaTeXEditor descendants of tab stack | 25 | 1 |
| Closed editor objects still native-valid | 24 | 0 |
| Closed editors still valid after whole-window destruction | 0 | 0 |

Baseline corrected probe exits 0 (`tab-retention-baseline-r2`); fixed probe
exits 0 (`tab-retention-fixed-r1`). The initial r1 measured the same 25/24
retention but then asserted incorrectly that a new document template was empty,
exiting 1. R2 captures the actual initial text and uses finally cleanup; no
application change was made between the baseline probes. Neither is an RSS
benchmark or proof that every possible application allocation is released.

## Bounded repair and regression coverage

`app/gui/editor_tab_manager.py` calls `widget.deleteLater()` only after accepted
closure has removed the tab. It does not force deletion inside a close callback,
change the existing save questions or retire a compile manager shared by another
tab. Invalid tab indexes remain safe. No original-file write or extra compile
authorization is introduced.

Changes to `tests/test_gui_editor.py`:

- New actual-window test closes a background saved tab, then proves its editor,
  gutter and highlighter are native-invalid. The active editor, cursor/scroll,
  text, both original files' raw bytes and compile authorization are preserved.
- New named/unnamed save-failure test proves the tab/editor/draft remain alive,
  with original disk bytes and the existing save route preserved.
- Existing Cancel/Discard tests now cross the deferred-delete boundary and
  check native validity rather than only counting visible tabs.

Baseline red: 3 tests / 0.647s, Cancel passes and both accepted-close disposal
assertions fail, exec 58488 exit 1. Preliminary focused 41 / 6.063s passes;
after the additional save-failure regression, final focused scope is 42 /
6.408s / OK, exec 50604 exit 0. It includes WindowLifetimeTests, Cancel/Discard
and all GuiPdfStateTests, including shared-manager and late-result cases.

## Commands and evidence

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_gui_editor.WindowLifetimeTests \
  tests.test_gui_editor.GuiEditorTests.test_cancel_keeps_modified_tab_open \
  tests.test_gui_editor.GuiEditorTests.test_discard_closes_modified_tab_without_saving \
  tests.test_gui_editor.GuiPdfStateTests -v
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_gui_editor tests.test_project_file_ops \
  tests.test_gui_submission_check tests.test_gui_preview_pipeline tests.test_pdf_panel -v
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10 python3 -m unittest discover -s tests -v
git diff --check
```

Expanded: 254 / 49.498s / OK, explicit child exit 0. Required frozen full:
1524 / 140.927s / OK, explicit shell/tool exit 0. Both ran sequentially under
exec 57755, now terminal. Post-terminal source digests match; compileall/diff
pass. The retained crash inventory remains ten, no new report in this round.
HEAD, empty index and held candidate feed remain unchanged.

| Log under `/tmp/` | SHA-256 |
| --- | --- |
| icstex-v1-native-wrapper-boundary-r1.log | 1296f59bf0917179a5a544dda571ede2530ede554ae72fdb9149b6a6e2285328 |
| icstex-v1-native-wrapper-prefix-r1.log | 8b86174510aa580b11b208de4171c8b64b004517cb6aa322087008d0192e0344 |
| icstex-v1-tab-retention-baseline-r2.log | 1df4b7b1fee9b3c732d39c93b046446bbaaf795b8b85c4d527ab00e2f611cf0c |
| icstex-v1-tab-retention-red-r1.log | d815be50ca87eef33ad0df7e8efc7d0b7668f713858a75cf0bc2055d303292ab |
| icstex-v1-tab-retention-focused-r2.log | c94f2e64bd4306f41272cf407e427d42039831c1516751870d761c1590619f65 |
| icstex-v1-tab-retention-fixed-r1.log | 261c78634b73244bfb9f1c009c2d84844ce53693a878d45b25a2a819955134a3 |
| icstex-v1-tab-retention-expanded-r1.log | eead855c5601ac42db5faf9611c6df73095cff5a7ed434cdf78633d2028256bf |
| icstex-v1-tab-retention-suite-r1.log | e06c8e2f557d2835288e551b1b3846a493bd2d34cdd38d46e6f29b9ed17e55da |
| icstex-v1-table-dialog-retention-r1.log | bdca370a965f0d2017f68c5711eb0b1764f950ab844175e3faaa2d2b1bd03b77 |

## Remaining scope

Historical timer receivers and exact stylesheet-object identity remain unproven;
the scoped AX guard is not accessibility acceptance. Current-source native
focus/IME/layout, R5 restricted engine compatibility/security decision, R6 and
E1–E4 remain open. No complete V1 or release-candidate recommendation.

The next concrete local gap is **parent-owned TableDialog retention**. A final-
source probe calls the actual `window.insert_table()` six times. Its subclass
only schedules `reject()` at zero delay and then calls the real `QDialog.exec()`;
the existing production caller, event loop and parent ownership remain intact.
Each Cancel leaves source text unchanged; after DeferredDelete/event delivery,
all six rejected TableDialog children remain under the window (exit 0). No
application fix for this separate defect is included here. Audit disposal after
Cancel/accepted value extraction first; do not automatically change asynchronous
formula/OCR lifetime or presume an explanation for the old timer signal.
Do not repeat the resolved native-versus-wrapper observation or weaken global
cleanup/GC to obtain a pass. Native QA waits for a usable channel. All diagnostic
and regression handles in this round are terminal.

Rollback only the accepted-tab deletion and associated regression assertions;
preserve all other shared work. Suggested commit only:
`fix(gui): dispose editors after confirmed tab closure`.
