# M2 local declarative profile slice

This is a local-source slice, not complete M2 or a release. Full test results
belong to `PROJECT_STATE.md` and `PROJECT_LOG.md`; later slices remain in
`V1_IMPLEMENTATION_PLAN.md`.

## Implemented user workflow

Open an ordinary or Block project and choose **File / Project Profile** (Chinese
UI: 文件 → 项目配置…). The dialog targets the visible Block project rather than
the hidden ordinary source tab. It can record an existing reference template,
engine recommendation, relative directory suggestions, optional word limits and
static check visibility. It does not replace a template, create directories,
change compilation settings, save source, compile or access the network.
No school or IB limits are invented. Disabling keeps all fields for later use.

The read-only submission check loads the profile in its worker and includes its
content identity. Configured word limits affect the existing effective-body-word
comparison. Engine recommendations are compared with the selected engine, not
silently applied. Disabled optional checks display N/A, not PASS; saved-input,
FINAL, PDF and formal-log guards remain. Invalid configuration and unknown
versions produce UNKNOWN, including an unknown word-target status.

## File and concurrency boundary

The only configuration file is `.icstex/project-profile.json`, version 1 with
format `icstex-project-profile`. Fields are explicitly enumerated; unknown fields,
scripts/hooks, duplicate keys, invalid types, unsafe directory suggestions and
oversize input are rejected. Read size is bounded to 64 KiB and reads are
rechecked; reading a missing profile creates nothing. Strict UTF-8 and existing
no-follow scoped reads are reused.

Explicit saving compares the captured original content, writes a same-directory
temporary, flushes/fsyncs, compares again and atomically replaces one file. On
POSIX the temporary and replacement are anchored to an opened non-symlink
metadata directory. Failures clean the temporary and preserve the original.
Unknown versions cannot be overwritten from this dialog. Conflicts keep the
draft widgets intact and ask the user to cancel/reopen rather than silently
retry against a newer version.

The existing MCP reentrant project lock was extracted without changing its root
key, lock-file location, platform primitives or MCP authority. Profile saves use
its non-blocking path, so a busy cooperating writer cannot freeze the dialog.
The lock is not a lock on arbitrary external editors; before/after comparisons
do not establish a frozen project transaction. M4/M5 still own checkpoints and
immutable submission inputs. No new MCP operation or concurrent-writer policy
is introduced.

Watcher opt-in is limited to the exact profile metadata file and does not enable
other hidden metadata, preview or build-output events. A profile event cancels
the current check without scheduling a replacement on the typing path.

## Native evidence

Final native command:

```bash
QT_QPA_PLATFORM=cocoa python3 tools/probe_project_profile.py --output /tmp/icstex-v1-native-20260910-m2-profile-r3
```

Exit 0 on macOS 26.6.1 arm64, Python 3.12.6, Cocoa. App Python path/content digest:
`cc34365cc2dc294c1888bd06321be785a423eadb70c4d6b9821edfc2a5778da4`.
Only disposable synthetic Chinese-path projects and isolated settings were used.

- A real one-page FINAL PDF was generated before editing configuration. Its
  bytes/build identity and the original synthetic source bytes stayed unchanged.
  Source cursor and scroll remained unchanged.
- Keyboard Escape cancelled without creating a profile; typing a limit and
  activating Save with Space persisted it. A real metadata file event removed
  the old check, and the next check showed the configured limit failing while
  the unchanged actual FINAL evidence still passed.
- An external winning edit remained on disk while the conflicting dialog kept
  its distinct draft and displayed a failure. Disabling kept the configured
  value but returned the target check to N/A.
- Native screenshots cover 90/100/110/125/150% scale, scrolled lower fields,
  visible Save/Cancel buttons, the actual target failure and the conflict.
  These images were inspected; raw images/logs stay local because they contain
  temporary paths and unredacted output.

The final native output contained no traceback, RuntimeError, RuntimeWarning,
IMK message or Qt table out-of-bounds warning. This absence is not AX/IME stress,
Windows or human usability acceptance.

## Remaining M2 work

This dialog is not a complete unified workbench/onboarding flow. Project creation
still needs Unicode-name and failure-path work; Block engine/navigation/inspector
layout and close/conflict behavior remain open. Template/engine/directory fields
are recommendations, not permission to convert or overwrite an existing project.
Direct word-target navigation and coherent status messaging can be integrated
with the next workspace slice. Profile identity must also enter M5 delivery.
No commit, push, packaging, installation, signing or release action occurred.
