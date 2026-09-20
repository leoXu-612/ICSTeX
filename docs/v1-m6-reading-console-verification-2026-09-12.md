# Word Count and Submission Check keyboard visibility

Date: 2026-09-12. Local R2 slice, not complete M6/V1 or release acceptance.

## Result and source

Word Count now reveals Refresh on external/reverse focus entry. Submission
Check has a scrollable header/results/detail body with a usable inner splitter.
The shared focus container follows the selected result and the actual first/last
line or visible top line of a read-only text viewport. Home/End and internal
scroll changes queue the existing parent-owned timer; no text cursor, selection,
source, report identity or next-step authority is changed.

- Branch `codex/v1-development`, HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`.
- App SHA-256 `2b010b8a82c93eb3464cf19f18034f6f6bf64aa89a10c700f8cb142494c981eb`.
- App+tests SHA-256 `080baad60905030ffd80ae36e5e9ad716df2733b07218207c675a35c11bc2fd8`.
- Digest: sorted repository-relative Python paths, NUL, bytes, NUL; 207 app
  files and 326 app+tests files. Not an installed-app or release identity.

## Reproduction and tests

Two new actual MainWindow tests in `tests/test_ui_visual.py` exercise all five
scale tiers at 1080x720, a small console, expanded toolbox and synthetic files.
They invoke actual read-only count/check controllers, select every report row,
verify input identity, test forward/reverse focus and switch-away/re-entry.
Long-preview and detail Home/End assertions verify both the real inner scrollbar
endpoint and the first/last text-line rectangle in the actual visible region.
Save, compile and network mocks remain unused; next-step signal count is zero;
source text, cursor/scroll and original file bytes remain unchanged.

The first short-text test passed Word Count but missed external re-entry. r2
added that case: 2 tests / 2.619s / six failures, exec 71560 exit 1. Initial
scroll-wrapper repairs passed 2 / 2.735s and 298 / 73.992s, but native r1 then
showed the detail's last identity line clipped by the outer scroll area. The
old cursor-at-zero assertion did not prove a read-only document endpoint.
The strengthened long-text/expanded-toolbox r3 reproduced ten endpoint failures
in 2 / 2.762s, exec 67555 exit 1. These earlier greens are not final acceptance.

Final text-follow repair: 2 / 2.951s / OK, exec 12622 exit 0. After adding source
cursor/scroll invariants, expanded visual/submission/editor/PDF/citation suites:
298 / 76.936s / OK, exec 25489 terminal exit 0.

| Receipt under `/tmp/` | SHA-256 |
| --- | --- |
| `icstex-v1-reading-console-red-20260912-r2.log` | `991bdb960f78cdfbf4760fab255716f9da40a59142231c9e7cbe78a80d388945` |
| `icstex-v1-reading-console-red-20260912-r3.log` | `306207715f94a56cfd9f52e9c8d76bd83a69b3f3adeadf7bd20d0772ae0992e9` |
| `icstex-v1-reading-console-green-20260912-r2.log` | `a41beacb0b4eaceca7c7e588ee65af13c873709866bb5e15be8b3d10d96950d9` |
| `icstex-v1-reading-console-expanded-20260912-r2.log` | `4287f9a1d575984971fc7ac07889d69093449bfba765a91796c17fcfb51ea6ac` |

## Actual native follow-up

User confirmed foreground availability. Both probes used a fresh synthetic
project, explicitly absent toolchain paths, automatic compilation off and the
production MainWindow. CUA supplied actual keyboard actions; the observer did
not select, scroll, refresh, compile or synthesize native keys.

Command: `QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3 tools/probe_citation_layout.py --native-observe --readonly-console --output /tmp/icstex-v1-reading-console-native-20260912-r2`.
Probe SHA-256 `1ac8059276c4c66430a72b6fe48cf363590af56f4ba09246a74cd592b6864265`.

- r1 exposed nested text clipping at 100%; exec 56953 exit 0 records a completed
  observation, not a passing UI. Its report SHA-256 is
  `8ff5fa71055308b01a0e2a6b55dbacc4387e397d3a0e3fab525ccae7663f0860`.
- r2: exec 58087 terminal exit 0, 71 states, no observation errors, timeout or
  interruption, window destroyed. App hash matches before/after. Report:
  `/tmp/icstex-v1-reading-console-native-20260912-r2/report.json`, SHA-256
  `85f1116a6c3e8bd519e51641dec67d2a4d30d7f56170bf131470d4d8603155a0`.
- 100%: Word Count keyboard Refresh, Tab, End/Home and Shift+Tab passed;
  `native-0018/0019/0021.png` show last/first text and visible Refresh. The
  final child-source label was previously below the clipped view.
- 100%: actual check, Tab through the unactivated next-step button, Down to
  root evidence, Tab to detail and End/Home passed. `native-0033/0036/0037.png`
  prove selected row, full identity tail and first line; reverse traversal
  reaches visible Refresh in `native-0042.png`.
- 150% was chosen using the native View menu. Check Refresh, first/last result,
  detail End/Home and reverse Refresh pass in `native-0051/0052/0055/0056/0061.png`.
  Word Count Refresh, preview End/Home and reverse Refresh pass in
  `native-0067/0068/0070.png`. No splitter dragging was needed.
- Exactly two Word Count refreshes and two Submission Check refreshes; zero
  next-step actions, compile starts or compile authority. Original files and
  source buffers remain unchanged. Missing tool paths and missing citations
  correctly remain failures/unknowns, not successful-build evidence.
- Immediate focus-change observations can precede the queued layout reveal;
  the subsequent settled states above establish visibility. Inactive rows or
  hidden panels need not remain visible while a different target has focus.

## Bounds

Native r2 stderr retains the scoped selected-children mitigation, font alias
timing (70ms), IMK mach-port error, two `Cell requested for row 0 is out of bounds
for table with 0 rows! Resizing table model.` messages and two
`QTextCursor::setPosition: Position '125' out of range` warnings. Normal exit and
stable source buffers do not establish their cause or close R3 accessibility.

No installed app or student files were touched, and no Git mutation, packaging,
signing, installation, deployment or release was performed. Native stderr and
the existing scoped AX mitigation remain evidence limitations, not full VoiceOver
or IME acceptance. R3/R5 and E1–E4 remain open.

Required frozen full: 1565 tests / 222.776s / OK, exec 43957 terminal exit 0.
Log `/tmp/icstex-v1-reading-console-full-20260912-r1.log`, SHA-256
`b876a91acb920bfd6d99ac88b4c3f7aede2d54cb2942b6248b14d0063c992c5a`.
Post-terminal app/app+tests digests match. Compileall, probe syntax and diff
checks pass. Eleven retained Python crash reports remain unchanged; HEAD and
empty index are unchanged. Held candidate feed SHA-256 remains
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
All test/probe handles ended; no temporary native window remains.

Next bounded R2 action: inspect native keyboard reachability of PDF page/zoom/
fit-width controls using an existing hash-checked synthetic PDF, including the
disabled no-PDF state. Do not repeat these console cases or compile new content
merely to accumulate passes.

Suggested commit only: `fix(gui): reveal read-only console text and keyboard targets`.
