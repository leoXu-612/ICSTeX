# PDF keyboard controls: menu guards repaired, layout/zoom defects open

Date: 2026-09-12. R2 remains open; this is not a PDF usability or V1 pass.

## Source and bounded repairs

- Branch `codex/v1-development`, HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`.
- App SHA-256 `d243b3a491d918b76a1b57c657f08748e9ff67586486f882933797e097ca46fd`.
- App+tests SHA-256 `12894b9793f3052242800073de02da6c0e46411bbaa4f271a4137a1783f53be2`.
- Sorted relative Python path/NUL/bytes/NUL digest, 207 app / 326 app+tests files.

The PDF overflow menu formerly kept every action enabled and directly emitted
the underlying button's clicked signal. It could bypass disabled navigation,
export or reveal controls. Actions now mirror EnabledChange and call the real
button's guarded click method. A deliberately stale enabled action still cannot
emit a disabled button click. This preserves existing export/preview authority;
it does not introduce an export path or permission.

Native r1 showed that More was skipped by Tab and its default delayed-popup
button did not visibly open on ordinary activation. More now explicitly uses
StrongFocus and InstantPopup. Native r2 proves Tab/reverse Tab entry; QMenu key
events occurred, but popup visibility/selection was not established by the CUA
tree or screenshots. Do not call the whole native menu interaction accepted.

## Test evidence and its blind spots

`tests/test_pdf_panel.py` adds disabled-action synchronization, stale-action
click protection and native focus/popup configuration tests.
`tests/test_ui_visual.py` adds a real three-page Qt-generated PDF in MainWindow:
five scales, page Up/Down, Tab/Shift+Tab through core controls, zoom-mode/value
changes, PDF bytes and source preservation. No TeX compilation is used.

- r1: five menu-state failures plus a fixture error (new document is a template,
  not empty). The fixture now compares its actual initial text.
- r2: 3 tests / 1.206s / ten menu state/click failures, exec 18729 exit 1.
  A test-edit placement error in unreachable post-failure assertions was fixed
  before the green run; it was not another product defect.
- Initial guarded-menu source: 3 / 1.230s / OK and 286 / 68.460s / OK.
  Full 1568 / 220.055s / OK, exec 80266 exit 0, applies only to app `5733a380...`,
  not the final More-focus increment.
- Native-focus configuration red: 1 test fails, log r3. Final expanded PDF,
  visual, preview, editor and PDF export suites: 287 / 70.287s / OK,
  exec 19852 terminal exit 0.
- Required frozen full on the final hashes above: 1569 / 221.616s / OK,
  exec 5984 terminal exit 0; compileall succeeded before the suite.

The green five-scale test's visibleRegion predicate does not detect overlapping
splitter siblings. It also compared the stored custom zoomFactor rather than
the effective FitToWidth scale. Native evidence below contradicts broad claims
based on those predicates. Add non-overlap and effective-zoom/page-anchor red
tests next; do not simply repeat the existing green test.

| `/tmp/` receipt | SHA-256 |
| --- | --- |
| `icstex-v1-pdf-keyboard-red-20260912-r2.log` | `afffa148be913f2ff4f3b23dc32397287e44f976984da434f67fde6127fcb2f6` |
| `icstex-v1-pdf-keyboard-red-20260912-r3.log` | `95f623850ee6d62444f43439cfe0ed7a21d6aa9a83ff4198a9f5d8e8823ba2ec` |
| `icstex-v1-pdf-keyboard-green-20260912-r1.log` | `4b791a64d3c6ee58cc5baeb2b4047178fb41bcad859f93705f4021a68969a441` |
| `icstex-v1-pdf-keyboard-expanded-20260912-r2.log` | `6825d97fe3821177beec5ebeaf160991165bd5fa98d2c85249ef712187ecb258` |
| `icstex-v1-pdf-keyboard-full-20260912-r2.log` | `c98a944c35efe5657962089946df06d1aba2768084adf31155cde73bbde36da2` |

## Native observation

`tools/probe_pdf_keyboard.py --output /tmp/icstex-v1-pdf-keyboard-native-20260912-r2`
ran under Cocoa. The probe generated a labelled three-page PDF with QPdfWriter
so real page changes could be tested; the earlier formula sample has one page.
The explicit QA menu loads/clears only this fixture. It is setup, not a new
product PDF-opening workflow, compilation or submission artifact. Native keys
were supplied through CUA, not by the observer.

- Probe SHA-256 `bed678b50e7983f9959843033184f6558df286a83ff77883a8a19a1c0445dccb`.
- r1 report SHA-256 `d5c621d4d12acceeda7fa9af3d00f401f8a78d1c9dab069b18cfc195afb2b78a`;
  exec 93692 exit 0. More focus was absent. One Down key reached source after
  an assumed Tab target; text/files stayed unchanged, but that source cursor
  movement is not mislabelled as a PDF operation. Ctrl+Tab did not exit source;
  Shift+Tab did. All failed/partial observations are retained.
- r2 report SHA-256 `73eda655284a1769397389b51868e9dc5d9223c4c0347370ad719daf574df6c6`;
  exec 78498 exit 0. Window destroyed, no timeout/error, hashes unchanged.
  Fixture PDF SHA-256 `821f27126e4ff084ec442889984c7c95357b44e799e6c759f459a9b44a1eb419`.
- Empty preview core controls are disabled; menu actions match. More is reached
  by Tab and reverse Tab (`state-006/010.png`). After explicit fixture load,
  reverse Tab traverses Fit Width, Zoom In, Zoom Out and Page; Up actually
  reaches page 2 (`state-018.png`). Only fixture load and zoom-out actions were
  recorded; no export, reveal or compilation. Original source/PDF bytes remain.
- **Open overlap:** in the 1080x720 window with toolbox shown, source paints
  over the left part of PDF page input. Actual offscreen geometry confirms
  source `[0,0,430,h]`, PDF `[395,0,360,h]` for a 755px splitter: 35px overlap
  at 90/100/110/125%. At 150% the splitter is 730px, PDF x=370: 60px overlap.
  The 430+360 hard minima plus handle cannot fit. This is not a text-size fix.
- **Open zoom/page drift:** native page 2/FitToWidth/scroll y=486 becomes
  page 1/Custom/zoom 0.869565 after Zoom Out (`state-019/020.png`). A read-only
  offscreen reproduction confirms effective scale before = 0.5663866 while
  stored zoomFactor = 1.0; afterward effective scale = 0.869565, scroll still486.
  Thus the action enlarges the page and loses the current-page context.
- Stop before 150% native acceptance or further menu selection claims; resolve
  these failures first. Both probe windows are closed, all probe handles ended.

Stderr retains the scoped AX selected-children mitigation, font alias timing,
IMK mach-port and Caps Lock LED messages. No all-AX/IME or historical crash-cause
claim is made. No student files, installed app, Git, packaging or release changed.
Post-terminal app/app+tests digests match; compileall, probe syntax and diff
checks pass. HEAD, empty index, held feed and eleven retained Python crash
reports are unchanged. All test/probe processes ended; no native window remains.

## Next bounded action

Repair splitter overlap at the supported small window without silently hiding
panels or changing source text, then base zoom increments on the visible scale
and preserve a meaningful document/page anchor. Verify real first/middle/last
pages, both zoom directions and fit modes; recheck native 100%/150% and menu
selection after those fixes. R3/R5 and external E1–E4 remain open.

Suggested commit only: `fix(gui): guard PDF overflow actions and enable menu focus`.
