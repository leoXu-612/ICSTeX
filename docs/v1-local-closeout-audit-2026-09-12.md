# V1 local closeout audit

Date: 2026-09-12. **The feature implementations exist, but local V1 acceptance
is not complete.** This audit replaces the unbounded “broader native coverage”
task with the finite keyboard workflow below. It neither reopens completed
checks nor waives reliability, engine, platform or release requirements.

## Scope and evidence checked

The original M0–M6 requirements, A01–A15 and stopping conditions in
`CODEX_V1_DEVELOPMENT_INSTRUCTIONS.md` were reread. The complete mapping remains
in [V1_ACCEPTANCE_MATRIX.md](V1_ACCEPTANCE_MATRIX.md); current source/test identity
and results remain in [PROJECT_STATE.md](PROJECT_STATE.md).

Read-only tree hashing matches the last frozen regression's application and
application-plus-tests digests. The retained full log still ends in `OK`; its
SHA-256 is `38411b2ec193bc8b7d01ecb7af4a1cd659c3825527c2dcf25791cf7174d9fd69`.
This was an identity check, not another test run. No application or test source,
dependency, system setting, installed application or student file changed.
No foreground window was opened during this audit.

The audit also read assertion bodies, not only test names:

- Submission checks compare original bytes and distinguish failed toolchain,
  unknown FINAL/static coverage and inapplicable targets. GUI refresh asserts
  no save, compile or network call.
- Checkpoint tests inject changed bytes with unchanged observations, cancellation,
  low space, corruption and existing/link targets; incomplete output is refused.
- Delivery tests verify PDF-only defaults, explicit source choices, byte-exact
  original README/encoding, report hashes, default-No confirmation and mutation
  refusal. Their direct `review()`/`perform()`/widget calls are **not** proof of
  keyboard traversal through the dialogs.

Retained product reports were opened and their hashes checked, including M3
repair, M4 migration, M5 core/GUI delivery, native navigation/console/PDF,
style-lifetime controls and the failed restricted LuaLaTeX case. In addition,
the actual files were re-read under:

- `/tmp/icstex-v1-m5-tool-versions-product-r1`: all three recorded delivery,
  external-source recompile, restored-PDF and report digests have matching files.
- `/tmp/icstex-v1-m5-final-native-20260911-r1`: all four workflows' PDF-only and
  source-package PDF digests have matching files.
- All seven retained submission reports in those directories: every declared
  output's length and SHA-256 matches its actual file.

These historical artifacts retain their own source identities. This audit does
not relabel them as freshly compiled outputs of the current tree, authenticate
tool binaries, certify every dependency or turn Qt-driven actions into physical
keyboard evidence. Local `/tmp` evidence is not a published or durable archive.

## Finite R2 remainder: keyboard completion of the three original workflows

Existing physical-input receipts close the tested source/Inspector/formula
Pinyin, conflict/Save As, citation/rail, outline/search/error/diagnostic location,
Word Count/submission-check reading and PDF-control cases. Five-tier layout
assertions and the respective source-identified native follow-ups remain valid.
Do not repeat them merely because other dialogs still need evidence.

The concrete gap is the **modal creation/delivery/recovery route**. Existing
end-to-end probes supply paths and invoke dialog methods or widget events;
the delivery/checkpoint/migration suites do not traverse the complete route by
Tab/Backtab and keyboard activation. This is missing evidence, not an assertion
that these controls are broken.

| Bounded case | Required actions and stop condition |
| --- | --- |
| R2a: first project to submission | On one synthetic ordinary project, enter creation fields, inspect/edit a local profile, save, explicitly run FINAL, open Prepare Submission, traverse PDF/source/report choices and actual source preview, cancel once, then confirm PDF-only output into a new destination. Exercise the real destination picker. Prove focus visibility, independent choices, cancel-zero-output and output bytes; no implicit save/compile or extra action. |
| R2b: recover a version | On that fixture, create a selected-byte checkpoint with an independent draft, choose a new restore directory, cancel once, restore, then explicitly open the copy. Exercise native destination selection and the separate open confirmation. Preserve the original project and keep drafts separate until explicit application. |
| R2c: distinct Block/migration controls | Reuse existing synthetic Block/known-legacy fixtures only for controls not covered by the ordinary route: standalone delivery entry and migration selection/review/cancel/new-copy/open confirmation. Do not redo all previously verified compile/export combinations or implement unknown formats. |

First add focused keyboard/geometry assertions for these actual dialogs at the
five existing scale tiers in a small window, without mocking away focus or
selection. Then use one announced native session for 100%/150% traversal and
actual pickers. The session ends with a per-case result, retained output and
all QA windows closed. A failure triggers only its smallest reproduction and
affected regression scope, not a new general UI sweep. These cases satisfy the
original keyboard/critical-control requirement; they do not add new features.

## Reliability and engine dispositions are separate

**R3 is a retained reliability risk, not another undefined coverage task.**
Window/tab/dialog disposal, weak gutter ownership, stale selection callbacks
and cyclic-widget stylesheet traversal have bounded fixes and controls. The
old timer receiver and exact historical stylesheet object remain unidentified.
Some retained crash reports are intentional baseline faults or invalid harness
setup, not post-fix failures; none may be deleted or silently counted as passes.
The latest green regression does not establish historical crash causality.

Further R3 investigation must name a discriminating observation of native
receiver identity/lifetime and its control before running. The earlier debugger
attachment denial is not authorization to alter system security, and is not
proof that every possible diagnostic is unavailable. No Qt upgrade, global GC
policy change or reliability waiver is authorized by this audit.

The macOS 26 / arm64 / Qt 6.11.1 Cocoa guard returns no selected-children value
for the affected AX attribute. Other attributes remain installed; this is a
documented accessibility limitation, not a repair of Qt's interface cache or
VoiceOver acceptance. Human/assistive-technology acceptance stays in E3.

**R5 is a known restricted-engine failure, not a general GUI compile failure.**
The retained synthetic protected/MCP run passes pdfLaTeX and XeLaTeX, but
LuaLaTeX exits with `latex_error` and no PDF: the installed luaotfload loader's
absolute distribution-resource read is denied. Local copied bytes are readable;
a parent sentinel remains denied. Fatal error display is repaired, compatibility
is not. Ordinary GUI compilation has a different default I/O policy.

D015 explicitly requires paranoid MCP I/O. Redirecting cache roots is not a
read-only exception because the tested output names are also admitted. Do not
relax that policy, replace the distribution or silently switch engines. A
maintainer must choose whether to commission a separate boundary-preserving
compatibility solution or explicitly accept/defer the restricted-engine
limitation; neither choice has been made. Deferral would be a recorded scope
decision, not a passing engine result.

## Handoff and completion boundary

R1 and R4 are addressed for their declared local cases. R2a–c are the next
finite executable work; R3 requires evidence-based risk disposition; R5 needs
the bounded decision above. R6's audit is complete, **local acceptance is not**.
Windows E1, real cloud/storage faults E2, human/VoiceOver E3 and separately
authorized release E4 remain outside this Mac's source-only proof.

The elapsed-time estimate given to the user applied to this closeout audit and
clear handoff, not a guarantee of all V1 or public-release acceptance. There is
no evidence-based fixed completion time for the unresolved R3 investigation or
R5 compatibility work. Report that uncertainty instead of repeatedly renewing
a “nearly done” percentage.

No commit, push, package, signing, install replacement or publication was
performed. Suggestions for a later authorized documentation commit:
`docs: bound V1 keyboard closeout and retain reliability and engine gates`.
