# M3 Cocoa synthetic follow-up

Before the user requested background-only work, the citation, material-usage and
source-repair synthetic product flows were run on Cocoa. These extend the earlier
offscreen evidence, not the product scope. All used app SHA-256
`bb899c986d4d5adb7fc30c3f618ad948319d7d94567c1c5317b42e57b059b75f`, macOS 26.6.1 arm64,
Python 3.12.6 and Qt 6.11.1, with the temporary selected-children guard described in
[the journal/native report](v1-m4-write-recovery-verification-2026-09-11.md).
Foreground/native QA was paused at that point. The user later explicitly
reauthorized isolated native work; current scope is in V1_IMPLEMENTATION_PLAN.md.
That later authorization does not broaden the evidence from the runs below.

## Final runs

All commands below terminated with exit 0 and generated `report.json` in a fresh
output directory. Only synthetic files and per-run settings were used.

```sh
QT_QPA_PLATFORM=cocoa PYTHONDONTWRITEBYTECODE=1 python3 tools/probe_citation_health.py \
  --output /tmp/icstex-v1-citation-native-20260911-r3
QT_QPA_PLATFORM=cocoa PYTHONDONTWRITEBYTECODE=1 python3 tools/probe_material_usage.py \
  --output /tmp/icstex-v1-material-native-20260911-r3
QT_QPA_PLATFORM=cocoa PYTHONDONTWRITEBYTECODE=1 python3 tools/probe_source_repair.py \
  --output /tmp/icstex-v1-source-repair-native-20260911-r2
```

Corresponding logs: `/tmp/icstex-v1-m3-citation-native-r3.log`,
`/tmp/icstex-v1-m3-material-native-r3.log`,
`/tmp/icstex-v1-m3-source-repair-native-r2.log`.

| Flow | Verified scope | Final PDF SHA-256 |
| --- | --- | --- |
| Citation | Duplicate/missing/unused distinctions, location navigation, unsaved BibTeX precedence, cancel/no writes/no compile authority, separate actual BibTeX FINAL, rendered page and citation text | `eec19c7f25f9ccc95f0cce536342f449e5125f689bacfe20aafd5d1e17595389` |
| Material | Changed/missing/moved candidates, unsaved child precedence, location/PDF viewport preservation, no check-driven writes/compile, stale FINAL, separate rendered image FINAL | `cb264963ef3d8250370df34d9b9ad49e5b008ba14a9c936f8c71503e673cf650` |
| Source repair | Real version/mapping/merge/confirmation dialogs, Cancel and external conflict preserve data, both associated tables applied together, one Undo restores model/source/draft, saved reload and rendered FINAL with values 12/11/21 | `d3fd16092180dfa8991d258cd162c0ee93c95fcd546116d64097753f1d6aa469` |

Citation and material controls were exercised across existing scale tiers and
requested normal/small dimensions; the minimum window clamps smaller requests.
Assertions scroll controls into view and verify their centers, not every control's
full bounds or universal readability. The inspected citation high-scale screenshot
shows horizontal scrolling/truncation, so full high-scale usability remains open.
Material r3 explicitly retried observed watcher invalidations before accepting its
stable changed-file report; it did not bypass invalidation or alter application code.
These timing samples overlap a loaded full-suite process and are not performance
benchmarks or evidence of isolated regressions.

## Evidence improvements and failures retained

Citation r1 exited normally but captured the PDF view before glyphs appeared. It
is not visible-PDF acceptance. Probe changes now wait for actual viewport ink,
check extracted PDF text, and wait for the workspace's completed-build next action
before capturing. Citation r2's inspected picture showed actual citation/reference
text; final r3 additionally checks the workspace header has left its transient
compiling state. Material r2's inspected picture showed the four expected colored
assets; final r3 includes the same rendered/text and completed-header checks.

Source-repair r1 reached a successful build but timed out waiting for visible PDF
ink because the narrow Block view was still on the editor page. The process exited
1 on its own; an attempted termination then reported no such process. It was not
killed successfully or accepted. R2 clicks the real View PDF toggle when present,
requires the panel to be visible, waits for rendered ink, verifies the repaired
table values and the completed workspace action, then captures. Its inspected
screenshot shows both tables with local 12, remote 11 and updated 21 preserved.
This fixes the verification script, not the application's rendering implementation.

External AX reads returned the citation compilation and source-repair Block
windows. A material AX read returned `AXError.cannotComplete`; subsequent process
inspection showed that probe had exited normally and there was no new Python crash
report. Do not count that read as successful AX acceptance or infer its exact cause.
Source-repair r2 stderr retains an IMK mach-port warning. No new Python `.ips` was
present at the post-run inspection; the older journal SIGBUS remains retained.

## Boundaries

Qt-driven button/keyboard events in real Cocoa windows are not physical input,
IME, VoiceOver, Windows or student usability acceptance. Selected-children AX
enumeration remains unavailable under the temporary guard. The source repair probe
reloads saved data through the real loader; it does not prove closing and reopening
that project through native file pickers. Static parsing limits, required retained
source baselines, large-table preview limits and all prior source-repair safety
constraints remain unchanged. No complete M3/M6 claim follows from these runs.

Current source/full-suite status is in PROJECT_STATE.md. No package, installed app,
Git commit/push, network lookup, deployment or release operation was performed.
