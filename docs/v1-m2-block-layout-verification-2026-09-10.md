# V1 M2 Block layout and keyboard reachability

Local source only, 2026-09-10. This bounded slice retains the Block session,
widgets, shared PDF, command stack and guarded writer. It is not full M2 or
release acceptance. The uncommitted source remains on `release/2.1` above
`f03776e87c0f938421a70ff5b085db920f2d01d7`.

## Implemented behavior

- Button rows wrap whole controls; navigation, workspace tabs and the contextual
  inspector use scroll containers. Irrelevant inspector fields are hidden.
  Small/high-scale windows require scrolling, not simultaneous visibility.
- A wide center area displays the same editor and PDF side by side. A narrow
  area offers explicit editor/PDF switches without recreating or reparenting
  those widgets. Resizing preserves the focused pane; switching preserves the
  loaded PDF and zoom. The real Block Save/FINAL/Stop toolbar replaces unrelated
  Source actions while Block mode is active; the owned dialog retains its controls.
- The first MainWindow now registers with the scale manager it creates, so dock
  metrics as well as fonts are applied. Initial Block dock sizes are bounded;
  later mode toggles do not reset the user's dock geometry.
- Layout projection blocks edit signals: loading non-default gap/alignment/
  fallback values does not silently change the model or create Undo commands.
  The selected slot's weight now changes that slot once, preserves other slot
  fields and selection, and is undoable. No selected slot means a disabled weight
  control. Editing gap/fallback retains unedited fallback properties.
- The inspector retains Tab as text input. Physical Control+Tab moves to Apply;
  Control+Shift+Tab moves to alias. This only moves focus, never applies. Space
  on Apply commits one model command. Native local text Undo/Redo stays separate
  from the global Block command stack. The shortcut is described in the tooltip.

## Source identity and verification

App Python path/content SHA-256:
`ea723c4ae672e8504fa3213efbc83b228ca22e04ce9e2c0032d377b81e9adcea`.
Environment: macOS 26.6.1 arm64, Python 3.12.6, PySide6 6.11.1; native platform Cocoa.

Focused command, exit 0, 82 tests in 27.638 seconds:

```sh
QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest \
  tests.test_blocks_gui tests.test_block_console_integration \
  tests.test_gui_submission_check tests.test_ui_visual
```

Log: `/tmp/icstex-v1-m2-block-layout-focused-r6.log`. Assertions include complete
button geometry/no overlap, narrow scroll containment, first-window registration,
stable widget parents/focus/draft on resize, projection without model edits,
selected-slot weight/Undo, fallback preservation and keyboard navigation without
applying. Required compileall and diff whitespace checks passed. Full discovery
passed 1076 tests in 539.011 seconds, exit 0:
`QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest discover -s tests`.
Log: `/tmp/icstex-v1-m2-block-layout-suite-r1.log`. No Python traceback,
RuntimeError, RuntimeWarning or fatal Python error appeared; offscreen plugin
warnings remain. The app path/content digest was rechecked unchanged.

Native commands use disposable synthetic projects and isolated settings:

```sh
QT_QPA_PLATFORM=cocoa python3 -X faulthandler tools/probe_block_layout.py \
  --output /tmp/icstex-v1-native-20260910-m2-layout-accept-r6
QT_QPA_PLATFORM=cocoa python3 -X faulthandler tools/probe_block_close.py \
  --output /tmp/icstex-v1-native-20260910-m2-block-close-r5
QT_QPA_PLATFORM=cocoa python3 -X faulthandler tools/probe_workspace_flow.py \
  --output /tmp/icstex-v1-native-20260910-m2-workspace-r8
```

All three exited 0 with the source identity above. The layout probe covered five scale
tiers (90/100/110/125/150%) at 1080x720 and 1440x900. Each of four layout buttons,
eight table buttons and inspector Apply was scrolled fully into the viewport.
At 150%/1080 the center editor viewport was 111 logical pixels tall: reachable
by scrolling, not a claim that the entire editor fits at once. Geometry changes
caused no model commands, source writes or Block compilation. Selected screenshots
at 150%/1080, 100%/1440 and actual FINAL were inspected.

The serial keyboard run asserts its active window before entering input, verifies
local text Undo/Redo, literal Tab, Control+Tab focus and Space-to-Apply, then one
global Undo/Redo. Save does not compile. Explicit FINAL produces visible text
`Native keyboard draft`; repeated editor/PDF switching keeps document identity
and zoom. Returning to Source preserves its FINAL, cursor position 1300, nonzero
scroll value 45 and exact source bytes.

The same-source close probe repeats actual Save/Discard/Cancel, save/reopen,
external-conflict refusal and retained drafts, owned-dialog close, and late
callbacks without changing external bytes. Its one-page FINAL contains the saved
draft, SHA-256 `87f22e8dcbd2d5adde50a7ead402af9102828e92961d46d4b72534fd1c033550`;
`block-final.pdf` is retained in that evidence directory. Dispatch was 2.476 ms
with 86 GUI heartbeat ticks on this tiny sample, not a general performance claim.
The workspace probe also repeats Chinese project creation, actual FINAL/check,
byte-identical PDF export, second-window reopen without compiling and clean Block
close restoring Source controls. Its original synthetic source bytes are retained.

## Failed runs and limits

- The first offscreen red run reproduced width 726 exceeding requested 280 and
  projection changing middle/error to top/stackVertically. Separate property red
  tests reproduced the unselected weight control and lost fallback extension.
- An intermediate vertical editor/PDF arrangement left the editor with no usable
  body at high scale; the explicit narrow-pane switch replaced that attempt.
  A subsequent native run exposed duplicate compile controls consuming the small
  viewport; the main toolbar now owns these actions.
- Native r3 could not leave the multiline editor using the assumed Ctrl+Tab
  shortcut. The explicit physical-Control focus shortcut was added. Native r4's
  literal-Tab check assumed a separate text Undo group, which Qt legitimately
  coalesced; the probe now removes that character with Backspace after checking it.
  Native r5 lost active focus while another GUI test process was running. Its
  result is not accepted; r6 ran serially with explicit active/focused-window
  assertions. This does not establish the cause of arbitrary native focus loss.
- Unapplied inspector widget drafts are still not owned by ProjectSession dirty
  state. Selection/model refresh or close can discard them; close protection
  currently covers model changes, not every editor draft. This is the next M2
  safety slice and prevents claiming complete editing/close acceptance.
  A separate offscreen synthetic loaded-project reproduction returned
  `has_unsaved_changes == False` after entering `Unapplied synthetic draft`;
  `inspector.refresh()` restored `Synthetic analysis.` with no compiler created.
- Internal slot IDs and some technical labels remain visible. Readability and
  complete keyboard/IME workflows still need work. Scrolling reachability is not
  human usability or accessibility acceptance.
- Native font-alias warnings remain; the workspace probe also emits the known
  accessibility table-bounds warning. The three accepted native logs contain no
  Python traceback/RuntimeError/RuntimeWarning. The contemporaneous Python crash
  directory check found only the two earlier 13:40/13:47 reports, not a new report.
  This is not an AX stress or general no-crash guarantee. Earlier timer-dispatch SIGSEGV causality,
  IME/AX stress, Windows and human acceptance remain open. Source tests do not
  prove installation stability. Pending write journals are not M4 checkpoints;
  M3-M6 and frozen delivery remain incomplete.
- Full-suite duration increased from the preceding 389.469-second run to 539.011
  seconds. A read-only one-second `sample` of its live process showed the main
  thread in `QApplication.setStyleSheet`/Qt CSS work, with a 2.1 GB process
  footprint (2.2 GB peak). Receipt:
  `/tmp/icstex-v1-m2-block-layout-suite-sample-r1.txt`. These whole-suite conditions
  do not isolate a product regression, prove a leak or establish normal app
  performance. Keep this as an M6 investigation signal, not a passed performance
  target. The run completed without an interrupt or source changes.
- No commit, push, package, installed-app replacement, credentials, signing,
  deployment or publication. The independent Beta activation gate is unchanged.
