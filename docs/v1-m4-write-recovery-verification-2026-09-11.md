# M4 interrupted Block-write recovery and native crash mitigation

This local increment provides explicit before/after/current review and recovery
to a new directory, retaining all conflict evidence. Focused and actual offscreen
and Cocoa product checks pass on the source below. The final full regression also
passed; completion/count/terminal-handle evidence belongs to PROJECT_STATE.md.
This is not complete M4, V1 or accessibility acceptance. No source push, package,
installed-app replacement, version, workflow, website, feed or release change.

## Contract and implementation

- `app/core/blocks/write_recovery.py` reads the existing writer's pending manifest
  and byte objects with bounded, strict format/digest/path checks. Extra, missing,
  corrupt, linked or non-managed journal objects refuse recovery without cleanup.
  Selected current files and absent transaction targets are read twice and their
  identities rechecked; confirmation and final publication reread the bound set.
- Every changed path requires an explicit version choice. There is no default
  conflict winner. The candidate must load known metadata and preserve matching
  generated source bytes. Incoherent combinations fail; no regeneration is used
  to conceal a conflict. Other selected files come from CURRENT disk: the pending
  journal is not a complete historical project snapshot or authenticated history.
- The checkpoint module's existing staged writes, byte readback, inventory check
  and exclusive new-directory publication are shared. Output contains `project/`,
  separate `drafts/`, and `recovery-evidence/`: journal objects, all available current
  conflict versions and a relative-path choice/digest report. Nothing repairs,
  deletes or unlocks the original pending journal. The target must be outside the
  original project and nonexistent. Failed or cancelled staging cleans only owned
  temporary output; publication winning late cancellation stays visibly available.
- `BlockWriteRecoveryDialog` is reached through the real File action. Its capture
  lease pauses cooperating automatic writes/compilation and captures actual source
  and Block drafts separately. New input invalidates confirmation. Background I/O
  is bounded to one worker; busy close waits for cancellation, not a hidden write.
  Recovery never auto-switches projects, applies drafts or starts compilation.

Limits: at most 2000 selected paths including journal targets; each before/after
object 4 MiB, their combined bytes 64 MiB, and total publication payload including
evidence/drafts 256 MiB. Checkpoint draft/file limits also apply. Preview text is
bounded independently and never defines the stored bytes. Selected filename lists
do not prove full dependency closure or cloud availability. POSIX directory handles
and repeated content observations do not provide OS-level CAS against arbitrary
external writers; Windows races, power loss and cloud placeholders remain untested.

## Source and reproducible checks

App Python path/content SHA-256:
`bb899c986d4d5adb7fc30c3f618ad948319d7d94567c1c5317b42e57b059b75f`.
Sorted `app/**/*.py` plus `tests/**/*.py` path/NUL/content/NUL identity at full-run start:
`bc83709bd8828fb6dbe4021206bf0a8179ebdbf5af86c56b70ee424e961664d0`.
Environment: macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1.
Git base `3bde2b5`; all changes in this increment remain uncommitted.

Focused command (exit 0):

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest \
  tests.test_macos_accessibility tests.test_block_write_recovery \
  tests.test_project_checkpoint tests.test_project_recovery \
  tests.test_block_write_recovery_gui \
  tests.test_ui_visual.WorkbenchVisualSmokeTests.test_cocoa_guard_precedes_editor_ui_construction \
  tests.test_ui_visual.WorkbenchVisualSmokeTests.test_interrupted_write_review_actions_fit_large_font -v
```

Receipt: `/tmp/icstex-v1-m4-journal-guard-focused-r2.log`. Covers real writer child
termination via `os._exit(73)` after its first managed-file replacement (not normal
rollback), external winner preservation, strict journal/path corruption checks,
absent targets, explicit choices, inconsistent model refusal, source changes during
review/publication, cancellation, occupied output, disk failure, independent GUI
draft capture and late cancellation/publication. The guard wiring test first failed
before the constructor call was added; `/tmp/icstex-v1-m6-ax-guard-red-r1.log` is the
retained red receipt, not acceptance. Mock runtime tests never patch the test host's
actual Objective-C methods.

Actual product commands (both exit 0):

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 tools/probe_block_write_recovery.py \
  --output /tmp/icstex-v1-write-recovery-20260911-r2
QT_QPA_PLATFORM=cocoa PYTHONDONTWRITEBYTECODE=1 python3 tools/probe_block_write_recovery.py \
  --output /tmp/icstex-v1-write-recovery-native-20260911-r2 --observe-ms 10000
```

Logs: `/tmp/icstex-v1-m4-write-recovery-product-r2.log` and
`/tmp/icstex-v1-m4-write-recovery-native-r2.log`. Both output directories have
`result.json`, actual review/confirmation screenshots and opened/reopened PDF views.
The probe uses synthetic projects only. It clicks real No/Yes buttons, uses keyboard
version choices, keeps the dirty owner document, and separately opens each recovered
Block copy and explicitly runs FINAL before and after close/reopen. Original project
and pending bytes stay unchanged. PDF extracted text contains the selected version;
within each copy the opened/reopened PDF hashes match. Different runs need not yield
byte-identical PDFs. Directory paths are supplied to actual dialogs; native file
pickers and physical keyboard/IME operation are not automated by this probe.

The native after-opened screenshot was inspected: FINAL banner and restored text
are visible, but the enlarged narrow PDF viewport clips the line. It proves rendered
output, not whole-page readability. Text assertions inspect the actual Qt PDF
document. Full native readability, keyboard, IME and human usability remain separate.

## Cocoa failure and narrow temporary mitigation

Native r1 exited 138 / SIGBUS, PID 30522; its output has no completed result.json.
Keep `/tmp/icstex-v1-m4-write-recovery-native-r1.log` and DiagnosticReports
`Python-2026-09-11-093624.ips`. Main-thread frames pass through AXCopyHierarchy,
AppKit array-attribute access and libqcocoa offset `0x87794`. Installed arm64 method
inspection located `accessibilitySelectedChildren` at `0x876bc`, and disassembly
places the fault return address after a child-interface virtual call. This matches
the selected-item validity call in the [Qt 6.11.1 Cocoa source](https://github.com/qt/qtbase/blob/v6.11.1/src/plugins/platforms/cocoa/qcocoaaccessibilityelement.mm).
The IMK mach-port and modal-session warnings in r1 are recorded observations, not
proof that reentrant confirmation caused the memory fault.

`app/gui/macos_accessibility.py` now installs a process-local nil-returning callback
only for this selector, only on macOS 26 / arm64 / Qt 6.11.1 / cocoa, after checking
the actual method encoding `@16@0:8`. MainWindow calls it before editor UI creation.
It requires the GUI thread, retains the callback/runtime for process lifetime, is
idempotent, and logs unavailable ABI/runtime rather than silently claiming success.
Offscreen and other runtime versions do not load or mutate Objective-C through it.
The guard explicitly makes selected-children enumeration unavailable; it does not
repair Qt's stale interfaces, disable all accessibility or prove VoiceOver support.

A separate actual Cocoa runtime inspection verified this selector's implementation
changed, while inspected children/role/title/parent implementations stayed the same;
a second installation was idempotent and the replacement returned nil. During native
r2, repeated external AX tree reads returned recovery and Block FINAL window content.
The process terminated normally and no newer Python crash report was present at
the post-run inspection. These are bounded observations, not a guarantee against
all AX crashes. R2 stderr did not repeat r1's IMK/modal-session warnings. The earlier
unrelated Qt timer crash and full M6 accessibility/IME matrix remain open. No installed
framework, system accessibility setting or other application was modified.

## Remaining work

The frozen-source full regression has completed with an unchanged app/test digest.
Next implement explicit migration into a verified copy, preserving raw
originals and rejecting unknown formats; retain M2/M3 native and larger-data gaps,
M5 frozen delivery, M6 performance/AX/IME and the independent Beta release gates.
