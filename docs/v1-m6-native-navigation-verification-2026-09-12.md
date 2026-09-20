# M6 read-only navigation and native focus follow-up

Date: 2026-09-12. The user confirmed unlock and keyboard control. Cocoa testing
resumed successfully; the earlier locked-Mac response is not a current blocker.
This receipt covers bounded navigation repairs, not complete M6/V1, VoiceOver,
Windows or release acceptance. Only isolated synthetic projects were opened.

## Source and implementation

- Branch `codex/v1-development`, HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`.
  This increment is uncommitted; no push, packaging or installed-app replacement.
- Final app tree: `9b2f44f5d46bd7b2895a6c73ea8f19d1228495b80da9d91c41916d6de21d181b`.
- Final app+tests tree: `7b83ae9b6ab073d906a5875561f4a011c7f48744e756bdb8ccd0379ef91c2f64`.
  Digest is sorted repository-relative Python paths, NUL, bytes, NUL; 207 app
  files and 326 app+tests files. It is not a binary/build identity.
- `table_navigation.py` binds non-repeating, widget-scoped Return/Enter to the
  selected current cell's existing `cellActivated` route. Only outline, search,
  diagnostics and compiler-error location tables use it. No save, repair,
  restore, insert or delete action receives new activation authority.
- Scrollable panels reveal their focused descendants after focus/resize via a
  coalesced, parent-owned timer; the scroll container is not an inert Tab stop.
- The tool rail has one Tab entry at the selected tool and retains arrow-key
  selection. Its children have explicit order, with the focus proxy temporarily
  removed while setting that order. The sidebar is parented to the MainWindow
  before finalizing the chain. This matters because the independently passing
  compound-widget fixture did not reproduce the original top-level assembly.
  Qt documents proxy substitution in [setTabOrder](https://doc.qt.io/qt-6/qwidget.html#setTabOrder).

## Narrow red/green evidence

All logs below are retained under `/tmp/`; suffixes are not pass labels.

| Log | Result | SHA-256 |
| --- | --- | --- |
| `icstex-v1-table-activation-red-20260912-r1.log` | 2 tests, 8 positive activation failures; negative checks passed; exec 94241 exit 1 | `1a1b81d714ad443793b3bece25b41cbbd608968a742f8f5cd7f84fffcc6f6f37` |
| `icstex-v1-table-activation-focused-20260912-r1.log` | 2 / 1.840s / OK; exec 68418 exit 0 | `83bb31728d26012dc6e047a4c8d48ad1c5533c5e54eb43d0425716dd57126370` |
| `icstex-v1-native-focus-scroll-negative-20260912-r1.log` | Replacing only the new scroll class with QScrollArea yields five out-of-window failures; exec 53847 exit 1 | `c888fcf347ef87973e53501e8ea1e5e098352c2a5690f9a00ba341ea2a20e32e` |
| `icstex-v1-native-focus-entry-focused-20260912-r6.log` | 6 / 2.174s / OK; exec 80700 exit 0 | `6db7cdcdea57539d153d5bbb7df8a8868284ce69ea551fa622ef10d5cb03c8f2` |
| `icstex-v1-native-rail-order-red-20260912-r1.log` | Actual MainWindow forward entry leaves the selected panel; exit 1 | `ec600900cd4af2f2f57ea3402c53ff345137dfda49894fa5985c6623492ddffe` |
| `icstex-v1-native-rail-order-focused-20260912-r1.log` | MainWindow plus compound/arrow tests, 3 / 0.722s / OK; exec 97303 exit 0 | `24d7cea6d20b918d5fa4c07654c07a0675031b4648fd0a4ac48f609aa3b44aea` |
| `icstex-v1-navigation-expanded-20260912-r1.log` | 301 / 61.299s / OK; exec 65395 exit 0 | `7453a666bddc46516a58027723c537e6dacc11fd9e11a22cfce4c96278cabd54` |

The activation tests use actual outline/search results and labelled synthetic
diagnostic/error records. Both keys navigate exactly once through the real
controller to the expected file/line. Empty selection, empty tables, another
focused widget and auto-repeat do not activate. File bytes, clean buffers and
compile authority remain unchanged; save/compile calls fail the test if invoked.
Five-scale focus tests assert visible regions, not focus ownership alone. The
new scroll timer is destroyed with its container before queued work runs.

Earlier fixed-step tests incorrectly assumed identical Cocoa/offscreen TabBar
stops. A separate r2 fixture passed a null focus to QtTest and aborted (exit 134),
not a product pass. Its log SHA-256 is
`2bb7c16a0ef2ab97b839de54f30a5b78c60ee2c88ffb7bca3eab5a28b4176e70`.
`Python-2026-09-12-012424.ips` records SIGABRT in `QTest::sendKeyEvent` /
`qt_assert`, consistent with that log; SHA-256
`652057069fa4f16601bd7120dd628b6e4f9a24d3a82b42b9b18933570ade5a2f`.
The fixture now processes initial focus events and asserts a non-null target.
Ten older reports plus this eleventh report are retained; no claim of zero
crashes in this development sequence or closure of historical timer/AX causes.

## Actual Cocoa observations

Command for each fresh output directory:

```sh
QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3 tools/probe_citation_layout.py \
  --native-observe --output /tmp/icstex-v1-citation-native-navigation-20260912-rN
```

The observer does not generate keys, force focus/scroll after setup or run checks
itself. Actual CUA keyboard/AX actions, screenshots and recorded geometry are
reviewed separately. Every run below exited 0, destroyed its window, preserved
all synthetic file bytes, recorded no compile starts and kept its app hash
unchanged. An observation process exiting 0 is not an all-pass predicate.

| Run | App tree | Report SHA-256 | What was actually established |
| --- | --- | --- | --- |
| r4, exec 75394 | `51fdd72fefb98409ffadb19045571492f0af16854558026b025ab913620bfbfa` | `bb93618784e5634f2a1dcab8c18dd80feaa729392cdc51da796f8ac135b2019d` | Citation table traversal/Space child navigation worked. Rail was skipped; 150% Locate had focus but y=1049, outside the window. These are retained failures. |
| r5, exec 22975 | `bd391b4a4ef9317ee39bd949042465293c096d1ac2fb8a4ccc6cf936d7b36286` | `f4a18f57b36787c3092a264f9ca0310a1e62c4cd756258d0728196c0ef782093` | All nine rail tools reached and visible at 100%/150%; rail scroll 32→0. Locate visible at 90/100/110/125/150%; external reverse entry at 150% and Space→child:2 worked. Rail-to-panel order remained wrong. |
| r6, exec 14692 | Final tree above | `f390e1d2b81548a229ada317cba45bb3be71ba457f07c0293aa00dda7c91263b` | After parenting fix: Auto toggle ↔ selected rail ↔ first panel button; real check, Down/Up, table→detail→locations→Locate, 100%/150% visible Locate, external reverse entry, Space→child:2. |

Reports and screenshots are in the respective output directories. Useful r5
frames: `native-0042.png` (90%), `0044` (110%), `0060` (125%), `0064` (150%
last rail tool), `0072` (first tool after reverse traversal). r6 frames `0003`–
`0007` record rail entry/exit; `0020` is 100% Locate; `0022` is 150% after resize;
`0024`–`0026` show external focus with panel scroll 0 then Locate scroll 468;
`0027` is child line 2 after Space. Initial geometry before the queued scroll
is not counted as final visibility.

The final r6 source differs from r5 by the MainWindow parent at construction;
do not relabel r5's five-scale/nine-tool observations as a new final-source run.
The final-source offscreen scale/arrow suite and r6 targeted native follow-up
are complementary evidence, not full native layout coverage.

## Remaining scope

The four Return/Enter location routes have offscreen product regression, not
four-route native acceptance. Broader tools/actions and native 200% PDF quality
remain in R2. Citation-list Return is not declared accepted; explicit Tab to
Locate then Space is tested. R3 historical timer/stylesheet attribution and
scoped AX limitations, R5 restricted LuaLaTeX policy/toolchain decision and
external E1–E4 remain open. No student content, public feed or installed app was
changed.

## Final frozen regression

`python3 -m compileall -q app tests packaging/install_build_dependencies.py`
passed. Expanded command: `QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3
-m unittest tests.test_ui_visual tests.test_gui_editor tests.test_gui_citation_health
tests.test_gui_material_usage tests.test_source_status_gui tests.test_theme
tests.test_layout -v`.

Required full command: `QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3
-m unittest discover -s tests`. Result: **1560 / 174.959s / OK**, exec 67870
terminal exit 0. Log `/tmp/icstex-v1-navigation-full-20260912-r1.log`, SHA-256
`d1b4a9ea0e52b556b5d56bb00b13b9b56723812ef6c90ed39a073a3d6a765b49`.
Post-terminal app/app+tests hashes match the identities above. All test/native
handles ended; no live native probe remains. The eleven retained crash reports
are unchanged since the fixture-abort inspection. `git diff --check` passed;
HEAD and empty index are unchanged. Held feed SHA-256 remains
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
