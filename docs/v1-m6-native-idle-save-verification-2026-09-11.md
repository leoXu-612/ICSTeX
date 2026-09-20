# M6 native source composition and default idle save

Current-source Cocoa input confirms that default automatic saving writes only
committed text while retaining a live Pinyin candidate, cursor and Undo history.
Cancelling that candidate does not write again. Native syllable conversion is
distinguished from a text commit; this receipt does not invent a combined
commit-plus-preedit event that the input method did not emit.

## Source, observer and authority

Branch `codex/v1-development`, HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`;
shared dirty worktree/index unchanged. App before/after both native runs:
`489657f34516f5bfeee0934b84a26885e217e8ff3ea7cad05f3f1297819d0085`.
App+tests remain `136e1892c4de31d04db0de8a2a40e97f7d58877238e90ab0784e161fc31ad59a`.
Only new `tools/probe_idle_composition.py` and documentation changed; no product
or test behavior was changed. Runtime: macOS 26.6.1 arm64, Python 3.12.6,
PySide6/Qt 6.11.1, Cocoa. New synthetic files and isolated settings only.

The observer constructs MainWindow directly with default preferences and asserts
the actual save debounce is 800 ms. Automatic compilation is explicitly disabled
for this synthetic save-only workflow. It observes native key/IME events,
document/committed source revision, all live preedit ranges, actual disk
bytes/inode/mtime, cursor/anchor/scroll/Undo, dirty/conflict state and the real
save timer's timeout signal. No input/save method is patched, no Qt input is
injected, and no save is manually flushed. Images are captured on state changes;
additional unchanged samples are retained roughly once per second.

The initial observer field `compile_created` means only that a CompileManager
object exists. Saving can create that object without running TeX. It is not a
compile-start observation and must not be used as one. The final observer names
it `manager_created` and separately listens to the real started signal. R1's raw
report is retained unchanged; that additional field is not retroactively added.

## Native r1: completed default-save case

```sh
QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3 tools/probe_idle_composition.py \
  --output /tmp/icstex-v1-native-idle-r1
```

Exec 29935 exits 0; native window destroyed, timeout false, zero manual Saves.
The probe's exit status means observation completed, not blanket acceptance.
Post-terminal assertions separately verify the evidence below against the raw
report and exact source/disk bytes. Native-window images 169 and 203 were viewed.

| Native sequence | Actual event/file evidence |
| --- | --- |
| Type `zhongwen`, Left, Space | Preedit becomes `中wen`, but commitString stays empty. Source/disk/identity/Undo remain original and no save timer runs. This partial-conversion state is sampled unchanged for 44.356 s. |
| Space, immediately `n`, `i` | The IME commits `中文`, then starts `n`/`ni` before the pending save is delivered. The actual 800 ms timer writes only `中文`, with `ni` still live. |
| Hold candidate, then Escape | Before/after the write, candidate, cursor/anchor 67, scroll 0, Undo steps 2 and source revision 4 match. Cancelling `ni` keeps the same bytes/inode/mtime, source revision and Undo; no new timer/write during a further 25.223 s sampled hold. |
| Command+Z, then Command+Shift+Z | Original source and then the Chinese commit return in order and each is automatically saved. Three real save timeouts total, zero manual Saves, final disk/editor exactly match the committed source. |

First commit is at 166.7986 s, first delivered save timeout at 167.8628 s:
1.0642 s elapsed on this instrumented host. The configured interval is 800 ms;
this is not an exact-latency performance guarantee. The timeout snapshot captures
the candidate before the workspace status label has necessarily repainted;
subsequent native AX state shows saved. No PDF/TeX render was requested, and the
synthetic project inventory contains only main.tex. No R1 compile-start signal
claim is made from the manager-created field.

There are fourteen native IME events, exactly one text commit (`中文`), and zero
events with both nonempty commit and preedit. Selecting `中` converted part of
the IME buffer but did not commit it to the document. The earlier event-level
combined-partial-commit regression remains valid; it is not relabelled as a
physically observed combined event. Apple documentation was consulted for
[Pinyin input](https://support.apple.com/guide/chinese-input-method/pinyin-simplified-cimpys11836/mac),
but these commit semantics are conclusions from the captured native events.

R1 source SHA-256: `268379af2989eeec7ad82fd7f8eb9c9984c6f005d8ddac198044e065fde9cd4b`.
Report: `30d2ad9d99727b12ea3478609374d94531177b985dc2c9c73c3c1d84c13b4c6c`.
Log `/tmp/icstex-v1-native-idle-r1.log`:
`6f4bd865e6952637b96505a4c721d25642f59812e2cae441632ff0619c9c6888`.
R1 observer: `6423fb299e8a3dc676ea0e1eb540d067e3f5c2917f27459beec12b30529af514`.

## Native r2: external-conflict case not exercised

A second isolated run was intended to check real external file changes while a
candidate remains after saving. Before any agent key command it received an
unattributed native `s` key at 1.2946 s; the synthetic source was automatically
saved. The input's origin is unknown. To avoid competing with possible user
typing, the agent closed this window and asked whether the keyboard was in use.
No external edit, candidate or conflict was generated, so this is not a pass or
failure of conflict protection. The existing Qt-event conflict evidence remains
separate and the native case remains open.

Exec 73055 / PID 42598 exits 0, window destroyed, timeout false, zero IME events
and zero compile-start signals. Saved `s` and its native event are retained,
not removed to manufacture a clean run. Both CUA close requests returned
timeoutReached after disappearance; terminal process/report evidence proves the
windows closed. No waiting native window remains. Input-source checks show the
same Pinyin source; this agent did not switch it.

R2 report: `56ab41e1a003081a1d552c40964df3d47b3c4dba6f4c2412a9e3a4e8d93fb4a5`.
Log `/tmp/icstex-v1-native-idle-r2.log`:
`43738bd62bcc82352c1e559086b3d338efb6baf05579dc75b04f27a9237d557f`.
Final observer: `27b91b3c8a65c3d8b89be8d1076c27ff2865f80fc0bfb68bb1a6a69ed9f96adc`.

## Scope and next evidence

Test-triage separates native partial conversion from actual document commitment,
manager creation from compilation, and interrupted test setup from a product
failure. No application fix was needed for r1. Required verification completed:

```sh
python3 -m compileall -q app tests packaging/install_build_dependencies.py
python3 -m py_compile tools/probe_idle_composition.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest discover -s tests
git diff --check
```

Full: 1550 tests / 281.502s / OK, exec 90745 explicit terminal exit 0.
Log `/tmp/icstex-v1-native-idle-full-r1.log`, SHA-256
`ebec68bac17372f87689dd6f37d649f92628296ba1a5b354d4c15295d36316aa`.
The live run was observed progressing, not restarted because it exceeded the
prior run's duration. Post-terminal app/app+tests hashes match. Compileall/probe
syntax/diff pass; no Traceback, RuntimeError, RuntimeWarning or fatal signal
marker in the full log. Ten retained crash reports and held feed remain unchanged.

The completed r1 default-save/cancel/Undo case should not be repeated. Next
native work needs a free keyboard: external file conflict during live composition,
then final-source formula partial-conversion/commit cases. R2 citation/tool-rail
navigation, historical R3/AX limits, R5/R6 and E1–E4 remain. This is not full
M6/V1, Windows, VoiceOver or release acceptance. No user document, installed app,
system setting, commit/push, package, signature, deployment or release changed.
