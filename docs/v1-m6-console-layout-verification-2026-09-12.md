# M6 console layout and visible keyboard focus repair

Date: 2026-09-12. The diagnostic clipping recorded in the
[native console/PDF receipt](v1-m6-console-pdf-native-verification-2026-09-12.md)
is repaired in the local source. All five UI scales pass focused visible-target
tests; actual Cocoa 100%/150% traversal and collapse/expand also pass without
dragging the splitter. This is bounded console acceptance, not complete M6,
VoiceOver, all-tool native coverage or release readiness.

## Change and boundary

- `app/gui/main_window_layout.py`: a QTabWidget subclass owns one coalesced,
  single-shot layout timer. Expanded consoles request their minimum hint after
  tab/size changes, within the existing splitter constraints. Collapsing hides
  the tab content, keeps the 36-pixel header, and restores the expanded pane;
  hidden content cannot retain a clipped keyboard target. Collapse state is
  explicit visibility, not an unreliable height threshold.
- `app/gui/diagnostics_panel.py`: the existing diagnostic header/table are
  placed in the existing focus-aware scroll container. The table keeps a
  usable internal height while the outer pane can scroll on short screens.
- `app/gui/insert_panel.py`: item views reveal their current cell rather than
  centering the entire oversized view. A queued reveal can follow selected-row
  changes. Timers/slots retain QObject ownership; no new background thread or
  unowned single-shot callback is introduced.
- `tests/test_ui_visual.py`: two real MainWindow tests cover 90/100/110/125/150%,
  forward/reverse Tab, selected-row visible regions/window containment,
  collapse/resize/reopen, source cursor/scroll/text/file preservation and no
  compile authority. `tools/probe_citation_layout.py` additionally records
  console sizes/collapse, diagnostic scroll and visible current cells.

No parsing, saving, compiling, repair authority, Return selection guard, PDF
renderer, installed application or student file is changed. At high scale,
the current target is revealed by scrolling; not all controls must fit at once.
Intentional pane resizing can clamp a short document's scrollbar to its range;
this does not promise identical viewport geometry across user resizing.

## Red/green and expanded tests

The first test attempt failed during fixture setup because it accessed the
scale manager before constructing MainWindow: two AttributeErrors, not product
failures. Moving that setup after construction preserved the actual assertions.

Baseline r2: **2 tests / 2.876s / 10 failures**, exec 80702 exit 1: five selected
row visibility failures and five expectations that collapsed content is hidden.
Log `/tmp/icstex-v1-console-layout-red-20260912-r2.log`, SHA-256
`e86bdc73460baa09766924b26619dbe1a3ea9ff9f3df62c3a8e7842fc10c184c`.
The initial fixture-error log is retained separately as r1.

The same focused command on the repair passes **2 / 2.184s / OK**, exec 97551
exit 0. Log `/tmp/icstex-v1-console-layout-green-20260912-r1.log`, SHA-256
`50ca7df08d0b4ba65f54a0c91c2237fba2a55544ee44f5fe6d98ece41b20e0e2`.

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_ui_visual tests.test_gui_editor tests.test_pdf_panel \
  tests.test_gui_citation_health -v
```

Expanded **269 / 63.964s / OK**, exec 33576 exit 0. This includes existing
console-header, window lifetime, source/PDF state, readonly navigation and
citation-focus assertions. Log
`/tmp/icstex-v1-console-layout-expanded-20260912-r1.log`, SHA-256
`dfadbc8cdb305325466856935cb75eca52a7e920c1f2c7f2b751873b5b4dfb3c`.

## Actual Cocoa follow-up

```sh
QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3 tools/probe_citation_layout.py \
  --native-observe --readonly-navigation \
  --output /tmp/icstex-v1-console-layout-native-20260912-r1
```

On the actual 1080×720 test window, native keys reach Check from the toolbar,
Tab enters the diagnostic table, Down selects the second row and Shift+Tab
returns to the visible Check button. At 100%, rows and buttons fit after the
automatic pane allocation; no splitter drag is used. Native collapse/expand
keeps the title bar and allows reverse entry from source to the selected row.

The native View menu changes UI Scale to 150%. The selected row remains visible;
Shift+Tab reveals the complete Check button by scrolling back to the top. Tab,
Up/Down and Return still work; one activation at 147.2955s reaches synthetic
`chapters/long-path-for-source-navigation/child.tex:4`. Collapse/expand and
reverse entry again expose the full focused button. Check/Fix are not invoked.

Representative retained states:

| State | Evidence |
| --- | --- |
| `native-0008.png` | 100%, Check focused and fully visible, console 281/244. |
| `native-0010.png` | 100%, selected diagnostic cell visible. |
| `native-0014.png` | Collapsed content hidden, console header height 36. |
| `native-0019.png` | 150%, selected diagnostic visible, outer scroll 26. |
| `native-0021.png` | 150%, Check focused, scroll returned to 0. |
| `native-0023.png` | 150%, row-key traversal reveals selected cell, scroll 52. |
| `native-0028.png` | 150%, collapsed header retained, content hidden. |

The native close button destroys the window. Its subsequent CUA read times out
because the window is gone; exec **86860 ends with exit 0**, no probe timeout,
interruption or observer exception. Source bytes remain identical and there
are zero compile starts/authority. One navigation activation is recorded.
Report SHA-256:
`2ea43d16243e38adad55bab69672319dc329e99543afab0f9bcecba969002fad`.
Loaded probe SHA-256:
`4d57786d0188683507487501929501fec8f65f37c1b2161c74da7c4da2ca9cb4`.

Native stderr still reports the scoped AX mitigation, font alias timing, IMK
mach-port and Caps Lock LED messages. Their causes are not inferred from a
normal exit; this is not warning-free AX/IME acceptance.

## Frozen source and final regression

App tree SHA-256:
`d73dbdf30e6301a289c99468980282e4bf6bafa8f7cb2fa3182e0d769766f07a`.
App+tests SHA-256:
`dd236693d317e64ec95435665ba65fb777a79ad01e68d3617d3ee3b8a9a45c5f`.
Native before/after app identities match. Digests use sorted relative Python
paths followed by NUL, file bytes and NUL. Compileall and diff check pass.

Mandatory `QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest
discover -s tests` completed **1563 / 195.995s / OK**, exec 72051 terminal exit 0.
Log `/tmp/icstex-v1-console-layout-full-20260912-r1.log`, SHA-256
`f471c659c231d4bbb30ddd299e6deadf7aa5dfec7d079a888f02e6d2f3097712`.
Post-terminal app/app+tests digests match. Eleven retained Python crash reports
are unchanged; all handles are terminal and the native window is destroyed.
HEAD remains `3bde2b5d25803262dedef89a081ee6ffbe2b6967`, index empty, held feed
SHA-256 `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03` unchanged.
No commit/push, package, installed replacement or publication occurred.

Next R2 slice: inspect remaining Word Count/Submission Check console targets
at small size/high scale, without inferring their full native acceptance from
this diagnostic-table fix. R3/R5 and external platform/human/release gates
remain explicit. The local-source goal remains active, not complete.

Suggested commit only: `fix(gui): keep console keyboard targets visible at all scales`.
