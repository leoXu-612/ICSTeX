# M6 current-source native Inspector focus follow-up

The repaired Inspector shortcuts now pass actual Cocoa input: physical
Control+Tab reaches Apply and Control+Shift+Tab reaches Alias, before and after
Pinyin editing and at 150% UI scale. Navigation alone preserves the unapplied
draft, model and disk. This closes that specific R2 failure, not all R1/R2/M6.

## Identity and scope

The user reported the computer awake and authorized continuing native tests.
The channel operated a new isolated Python MainWindow; no old locked handle was
reused. Initial Finder lookup returned cgWindowNotFound, not a locked desktop.
Branch `codex/v1-development`, HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`;
shared uncommitted work and empty index preserved. App SHA-256 before/after:
`489657f34516f5bfeee0934b84a26885e217e8ff3ea7cad05f3f1297819d0085`.
App+tests `136e1892c4de31d04db0de8a2a40e97f7d58877238e90ab0784e161fc31ad59a`.
macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1, Cocoa. No application,
test or probe source changed during this native follow-up.

```sh
QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3 tools/probe_workbench_composition.py \
  --kind inspector --output /tmp/icstex-v1-focus-native-r2
```

Exec 58955 / PID 38006 ended at explicit exit 0. The probe creates/navigates the
synthetic fixture, observes events/state and cleans up; desktop keys perform
editing, focus movement, Apply and Save. No Qt key injection supplies the native
claims. Source Save debounce remains one hour: not default-800-ms evidence.

## Observed sequence and invariants

Actual keys form `zhong wen`, Space commits `中文`, Command+Z removes it,
Command+Shift+Z restores it, and a second `ni` candidate is cancelled with Escape.
Twelve native input-method events and ordered editor states are retained.
The preexisting Simplified Chinese Pinyin input source was not switched;
read-only input-source checks before and after matched.

The report's `passed` field checks IME/draft/save/close, not focus. Focus evidence
additionally uses these one-based states, actual ShortcutOverride key/modifier
events and observed desktop actions:

| State pair | Actual native action/context | Recorded result |
| --- | --- | --- |
| 7 / 9 | Control+Tab / Control+Shift+Tab from content, initially 100% | Apply / Alias; text/model `base `, files unchanged, zero Apply/Save |
| 25 / 27 | Same directions after Chinese commit, Undo/Redo and candidate cancellation, 100% | Apply / Alias; draft `base 中文`, model `base `, files unchanged, zero Apply/Save |
| 29 / 31 | Same directions after actual View → UI Scale → 150% | Apply / Alias; same draft/model/disk invariants |
| 33–36 | Alias Tab → content, Control+Tab → Apply, Space, Command+S | One explicit Apply then one explicit Save; model/saved target exactly `base 中文` |

The 150% setting is recorded in isolated `inspector.ini`. Inspected native-window
state-029/state-031 captures show visible Apply/Alias and their respective focus
outlines. Forward navigation scrolls Inspector to its target. Header content may
lie above the viewport; the entire sidebar is not claimed to fit simultaneously.
The probe requests 1320×900 logical size and captures 2640×1800 device pixels.
Only fixture UI settings changed, not installed-app or OS settings.

Before explicit Apply every sampled model/file state is original. After Apply,
existing Block autosave writes the model; subsequent Command+S is also observed
once. This does not claim Block saving waits for manual Save after Apply. The
separate `untouched` table remains exact, no compiler is created, and the observer
reloads the final project to check saved content. Sampled invariants are not
filesystem tracing against unobserved transient writes.

Closing the window produced CUA timeoutReached after it disappeared; the separate
process/report confirms exit 0, `window_destroyed=true`, `timeout=false`. The UI
timeout alone was not used as close/crash evidence. No waiting window/session
remains. Ten retained Python crash reports are unchanged.

## Evidence and remaining boundary

Directory `/tmp/icstex-v1-focus-native-r2/`; log
`/tmp/icstex-v1-focus-native-r2.log`. SHA-256:

- Report: `94df0996a30b7b30603d12d533313cf7a532b436e99761b2ea65dfcab4f2e4b0`
- Log: `e482a2631255d09c0bec293a2c022877f1bf91248684c6d1b8174e12215811a9`
- Probe script: `566716a80e68274c8fb126bef5651e67a5dd5b19a2935c78c5861cad42edb44f`
- Isolated settings: `f6b73c88660c9ae259ab9278da6e886b7637e8f0702967a9d196c565c24839d0`
- State 29 image: `2fe8b703244ba112fdf1d679a1adb75a511a9cf173542745fdf3ead9f7a06c42`
- State 31 image: `1eaa2fb3b37758392e5791861da0554c05b999826d85560d8895e8694d53367d`

Unchanged source retains preceding 133 focused, 277 expanded and required 1550
full passes in the [formula receipt](v1-m6-formula-coordinates-verification-2026-09-11.md).
Compileall/diff pass again; source hashes, HEAD/index and held feed unchanged.
No commit/push, package, installation, release, student document, security setting
or input-source mutation.

R1 current-source partial commits/default idle-save remain, as do R2 native
citation/tool-rail keyboard navigation and broader layout. Inspector 100%/150%
is not all scale tiers, VoiceOver or Windows. Old timer/AX limits, restricted
LuaLaTeX decision, R6 and E1–E4 remain independent. Next bounded work is R1 source
physical partial commit/default 800 ms save and remaining-candidate preservation,
using the actual default rather than this probe's one-hour override. Do not
repeat this completed Inspector sequence.
