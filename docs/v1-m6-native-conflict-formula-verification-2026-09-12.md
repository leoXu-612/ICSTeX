# M6 native external-conflict and formula input acceptance

2026-09-12. **The remaining R1 cases pass for this Mac's tested Pinyin input.**
A real external change preserves live composition and the local buffer; declining
overwrite keeps the external version, and Save As preserves the local Chinese
draft separately. Current-source formula visual/source modes preserve partial
conversion, cancel exactly, commit, Undo/Redo and accept by keyboard.

This closes these finite local R1 cases, not all input methods, native layout,
AX/VoiceOver, M6/V1 or release acceptance.

## Authority, source and environment

The user explicitly confirmed keyboard control on 2026-09-12. Only three isolated
synthetic windows were opened; all were closed at the end. No student project or
installed application was touched. The earlier paused/unattributed-key probe
remains untested and is not relabelled as this run.

Branch `codex/v1-development`, HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`; app before/after:
`489657f34516f5bfeee0934b84a26885e217e8ff3ea7cad05f3f1297819d0085`;
app+tests:
`136e1892c4de31d04db0de8a2a40e97f7d58877238e90ab0784e161fc31ad59a`.
No app/test/probe code changed in this slice; only synthetic external-conflict
bytes and verification/current-brief documentation changed.

macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1, Cocoa. Real desktop key
events used the configured Pinyin IME; no QTest/input-event injection occurred.
The keyboard-layout identifier was `com.apple.keylayout.PinyinKeyboard` before
and after. No input-source or system preference change was requested or made.
Desktop-generated native input is not a real-student usability result.

## Ordinary source: external change during composition

```sh
PYTHONFAULTHANDLER=1 python3 tools/probe_idle_composition.py \
  --output /tmp/icstex-v1-native-conflict-r1 \
  > /tmp/icstex-v1-native-conflict-r1.log 2>&1
```

Exec 65068 exits 0, timeout false, window destroyed. Observer SHA-256:
`27b91b3c8a65c3d8b89be8d1076c27ff2865f80fc0bfb68bb1a6a69ed9f96adc`.
It asserts the real default 800 ms save setting; automatic compilation is off for
this isolated scenario. No save/reload method is patched or manually flushed.

| Sequence | Verified evidence |
| --- | --- |
| Native `zhongwen`, then external disk edit through apply_patch | Only synthetic main.tex changes `base ` to `external-A `. The actual file watcher reports conflict; no reload handler was called by the fixture. Preedit `zhong wen`, source revision 3, cursor/anchor 65, scroll 0 and Undo steps 1 remain intact. |
| Hold and Escape | First continuous conflict/preedit segment has 22.185 s of recorded unchanged samples. Cancellation keeps original in-memory source, external disk bytes and conflict flag. |
| Native `zhongwen`, Space | Local committed text becomes `base 中文`; external disk remains `external-A `. Automatic saving is paused; zero save timeouts and zero compile starts. |
| Command+S, Return on default No | Actual conflict dialog explains overwrite vs Save As; No is focused by default. Declining keeps both versions and returns focus to the source editor. One Save action, no overwrite. |
| File → Save As, new `local-draft.tex` in the same synthetic project | Actual macOS save panel creates the new file. Final AX state identifies that file as saved, with the local Chinese text; original main.tex still contains the external version. |
| Native close | Window destruction and terminal process prove completion; no remaining test window/process. |

The first conflict snapshot is state 58 at 53.0671 s; cancellation is state 80,
commit state 113, declined Save state 128, saved-copy state 152. Continuous
samples are separate from the second composition: an initial scratch calculation
of 50.941 s spanned both sequences and is **not** a continuous-hold measurement.
The correct first-segment value above uses only event_count 8.

Post-terminal assertions verify every snapshot after conflict retains identical
external disk bytes/inode/mtime, including after Save As; both final files match
their exact expected text. The observer's fixed `disk` path remains main.tex
after Save As, so that field alone is not the new-file write evidence. Separate
file reads plus the saved-path native AX state prove the copied draft.

The save panel initially opened in the home directory. Command+Shift+G opened
its path sheet; CUA paste timed out with the path unchanged. Setting the observed
path/name AX fields and pressing Return/Save selected only the synthetic
directory. This is an actual native panel, not a claim that its path was typed
character-by-character or that the failed clipboard operation passed.

Report: `/tmp/icstex-v1-native-conflict-r1/report.json`, SHA-256
`e82ca6eaa4a263215126f095860d563200c7777684a17345df9d936d40edfd49`.
Log SHA-256:
`301ab8540327699daed995eb3962ca754fba589f15d6ba4a029024c9eee3d0e0`.
External main.tex:
`5a421cb3995de72ff5acb6bd79ed001cf23b795c737bc2b33e755553f4e129cd`.
Saved local-draft.tex:
`268379af2989eeec7ad82fd7f8eb9c9984c6f005d8ddac198044e065fde9cd4b`.
Eighteen actual IME events; one Save action; no compile starts or save timeouts.
No new FINAL or reopened-window claim is made by this conflict receipt.

## Formula visual and source modes

```sh
PYTHONFAULTHANDLER=1 python3 tools/probe_input_composition.py \
  --output /tmp/icstex-v1-formula-ime-visual-20260912-r1 \
  > /tmp/icstex-v1-formula-ime-visual-20260912-r1.log 2>&1

PYTHONFAULTHANDLER=1 python3 tools/probe_input_composition.py --source-mode \
  --output /tmp/icstex-v1-formula-ime-source-20260912-r1 \
  > /tmp/icstex-v1-formula-ime-source-20260912-r1.log 2>&1
```

Visual exec 96322 and source exec 13141 both exit 0, report passed true and
window_destroyed true. Observer SHA-256:
`e23931805d39fe5db255561ead4cc13347c812e16520f334d76f04803ff5b10c`.

Both actual dialogs start with `$x+$`. Native `zhongwen`, Left, Space produces
`中wen` as wholly preedit, with empty commitString. AX and native screenshots
show the composition warning and disabled Apply; both draft and LaTeX preview
remain `$x+$`. Escape returns exactly to the initial state.

A second `zhongwen`, Space commits `中文`. Native Command+Z restores `$x+$`,
Command+Shift+Z restores `$x+中文$`, and Command+Return accepts that exact plan.
Each mode records 20 actual IME events and seven state transitions, with the
original document snapshot preserved. All preedit states have Apply disabled
and unchanged source/draft; both return the expected final plan.

These are real FormulaDialog input/confirmation tests, not a new MainWindow
insertion, saved document or FINAL compile. Current-source target/coordinate and
Save/reopen/FINAL coverage remains in the separate
[formula-coordinate receipt](v1-m6-formula-coordinates-verification-2026-09-11.md).
No event here contains both nonempty commit and preedit. The synthetic combined
event regression remains distinct; this Mac's partial syllable conversion is not
misreported as such an event.

| Mode | Report SHA-256 | Log SHA-256 |
| --- | --- | --- |
| Visual | `44e4e780629ae439b01cc48ddce3024ee1f74819fbdf2d05abf664581fa77417` | `6b7ec4a95e43cba55a5531fda3f5e71b53ef4e98f9c3a69c6e1072a87d011ae8` |
| Source | `2ee542832c6bdab446441cb579e71a84135e6e1cb38bdd0f457d5a0de221bb72` | `8b2b5842d6f1c13c62a21423b9c878cf983b9b8a926a9fa2c4ee537dde0dde62` |

## Native warnings and regression boundary

Each process emits an IMKCFRunLoopWakeUpReliable mach-port warning. It is retained,
not called harmless or used to claim a cause. CUA observation after window close
times out; the exact live exec is then polled to terminal exit 0 and its report
confirms destruction. None was restarted because observation timed out.
The version-scoped AX guard remains active; this is not complete AX/VoiceOver
acceptance.

Required verification:

```sh
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest discover -s tests
git diff --check
```

Frozen full regression: **1550 tests / 169.147 s / OK**, exec 32613 terminal exit 0.
Log `/tmp/icstex-v1-native-conflict-formula-full-20260912-r1.log`, SHA-256
`9f410c6a7829d0f7e874dca166faf2c9bd2db11880c9554bc0413b761fad95a7`.
Post-terminal app/app+tests match the identities above; compileall/diff pass.
Ten retained September Python crash reports are unchanged in names/count.
HEAD/index remain unchanged and empty respectively; held feed SHA-256 remains
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
The full regression was required for the updated active agent brief; it is not
the proof of the native observations described above.

R1's finite tested local cases are addressed; do not repeat completed default-
save, Inspector or these three cases as the next work. R2 native citation/tool-
rail/scale and separate PDF quality, R3 historical causality/AX, R5 restricted
engine decision, R6 final reconciliation and external E1–E4 remain. No commit,
push, packaging, signing, installed-app replacement or release.
