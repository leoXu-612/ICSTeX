# V1 local implementation and acceptance

Updated: 2026-09-11. M0/M1 complete; M2 property-draft slice verified locally; full M2-M6 incomplete.
Active slice: M2 image import boundaries and bounded test-fixture disposal.
Full scope: `CODEX_V1_DEVELOPMENT_INSTRUCTIONS.md`, M1-M6 plus M7 readiness handoff.
No automatic commits/pushes, packages, installed-app changes, signing or publication.
Exception for this checkpoint only: on 2026-09-11 the user explicitly requested
the needed rename and source submission. The local branch was renamed to
`codex/v1-development`; retain the remote `release/2.1` and all release gates.
Run full validation, commit the existing V1 work and push only the development
branch with `[skip ci]`. This is not standing permission for later automatic pushes.

Current draft implementation stores only explicit property differences against a
captured target/base, with session-visible pending state but no automatic model
application or disk draft persistence. The Inspector retains pending text documents
across selection and offers a pending-draft list, Apply and confirmed Discard.
Applying one or an explicitly confirmed batch validates all bases before one Undo
command; newer re-entrant input remains pending. Save/close/FINAL distinguish
unapplied drafts and check confirmation revisions; read-only checking cannot pass
their saved state. Slot selection resolves its actual parent layout; pt gaps are
displayed in mm without changing an untouched gap. Focused checks and same-source
native property/layout/close runs and final frozen-source full regression have
passed. Detailed receipts and remaining defects are linked below.

Verified layout scope: retain widgets, session/selection, command stack and the
shared PDF widget. Wrap button rows, contain long forms in existing scroll areas,
and offer explicit editor/PDF switching when the same splitter is too narrow.
Keep both panes side by side when wide; resizing does not reparent their widgets.
Layout projection does not issue model commands; resizing preserves the editor
draft. The verified later property-draft slice protects unrelated model/selection
refresh. Minimum window sizes, all scale tiers,
keyboard focus/Undo, no implicit save/compile and Source/PDF ownership have local
evidence. Layout rollback is confined to these UI seams; no format/writer changes.

Current write/close contract: retain the existing Block ProjectSession and formats.
Save persists metadata and its corresponding managed generation without compiling.
Capture metadata/generated-file ownership before edits, reject externally changed
bytes, stage before/after bytes before replacing project files, and conditionally
roll back only files still equal to this writer's output. Preserve unresolved
recovery evidence and drafts; never call a partial write complete. Close asks for
Save/Discard/Cancel before shutting down either source or Block state. Reuse the
existing project lock, read boundaries and compile identity; no new topology,
universal session or release-helper change. Verify synthetic conflicts, write
faults, late timers, mode/window close and original bytes, then native behavior.
Earlier source-sync authorizations applied only to their own completed batches.
Keep `FORCODEX.md` and `BETA_ACTIVATION_HANDOFF.md` as the independent held Beta brief.

## Baseline and ownership

- Root verified with `pwd -P` and `git rev-parse --show-toplevel`: selected ICSTeX repository.
- V1 starting branch `release/2.1`, HEAD `f03776e87c0f938421a70ff5b085db920f2d01d7`.
  Tracked/untracked working tree was clean at V1 continuation start. The previous
  Beta source and development instructions are preserved in that baseline.
- macOS is locally available; Windows/native IME/AX/human usability acceptance
  must be recorded separately, not inferred from offscreen tests.
- The immediately preceding unchanged-source baseline passed required compileall
  and full tests; exact commands/count/timing are in the 2026-09-10 project log.
  `welcome_page.py` scale signal invoked deleted QLabel objects despite suite success.
- Beta installation-lifetime exclusion, late instances and forced interruption
  remain open. No source-only test or process scan closes those external gates.

## Capability delta and stage dependency

| Stage | Reuse verified source | Actual remaining work | Acceptance evidence |
| --- | --- | --- | --- |
| M0 | Existing response/PDF benchmarks; synthetic demo core | Baseline manifest, three workflow fixtures, measured targets, stale roadmap corrections | Fixture tests, source-identified benchmark, full baseline |
| M1 | `diagnostics`, `project_dependencies`, `word_count`, `pdf_state`, Environment Doctor | Read-only root-wide check model and UI, explicit statuses/evidence/input identity, invalidation/navigation | Core + multi-root GUI, no-write/no-compile tests, native source window |
| M2 after M1 | Toolboxes, project wizard, formula/table/image drafts, Block session | Cohesive workbench/onboarding; editable declarative profiles; keyboard/IME/scale acceptance | Synthetic first-use, cancel/Undo, all scale tiers, native focus checks |
| M3 after M1/M2 | BibTeX, `SourceRecord`, source registry and three-way table merge | Read-only usage/changes/citation health UI; bounded explicit repair preview when needed | Source-change linkage, conflict preservation, offline/cancel tests |
| M4 after M1 | `history` single-file snapshots, MCP byte preimages, Block repositories | Consistent versioned project checkpoints; separate drafts; verified restore to NEW directory; bounded retention and explicit migration | Byte/hash roundtrip, corruption/missing object/low disk/races/unknown version, no original writes |
| M5 after M1/M2/M3/M4 | FINAL compile/export guards and Block export | Frozen submission inputs/profile/count policy + opt-in source/report staging; preview and mixed-version rejection | Create/check/FINAL/export/reopen/restore end-to-end, external mutation faults |
| M6 throughout, close after M5 | Existing safety, async, GUI and compiler suites | Introduced regression fixes; lifecycle/performance/native/platform quality matrix | Full local suite, actual visible outcomes, repeatable measurements, platform/human gaps |
| M7 handoff only | Existing signed-update gates | Source/platform/artifact/signing/install/network/human readiness separated | No release recommendation until relevant required acceptance is proven |

Single-file `history.create_snapshot` writes decoded text; it is NOT a byte-exact
project checkpoint. `project_repository.save_project` writes multiple files
individually; its name/docstring is NOT proof of a consistent project transaction.
The existing Block session is not a universal ordinary-source session. D010 stays
Proposed unless real vertical-slice evidence requires and validates its promotion.

## Slice contract

M0 changes only fixtures/development evidence/docs. It uses disposable synthetic
single-file, Chinese-path multi-file (image/table/BibTeX), and real Block metadata
projects. Draft/external-conflict variants remain separate from disk; missing
assets are actually absent. Never reuse or transform student writing.

M1 implemented slice: a local user checks the current project's saved inputs and FINAL PDF.
Reuse existing parsers and build records; one focused Qt controller snapshots
immutable inputs and discards stale/late results. No new project writer/session
or network capability. Explicit refresh never saves/compiles. Navigation and any
user-requested Save/FINAL actions route through existing guards. Invalid input,
unsupported/dynamic resolution, cancellation and worker failure remain UNKNOWN
or FAIL, never PASS. Rollback is removal of the new read-only panel/controller
and its wiring; source formats and existing writing/compile paths do not change.

Ordinary-source checks now bind current root, editor revisions, dependency bytes,
engine/tool paths and existing FINAL state. The bounded worker exposes evidence
and static citation/resource navigation; editing, mode changes, external events,
cancel/close and late results invalidate the captured report.

Block checks now use the active Block project, not a hidden ordinary-source tab.
The captured model is compared with bounded, link-safe metadata reads and pure
LaTeX generation; it does not save, assemble or compile. The same panel moves to
a visible Block dock. Save state is a content comparison, not a retained reason
string. Block FINAL/PDF now bind actual revision/build/purpose/dependency/PDF
identity, verified with real native compilation. The later M2 guarded writer now
supports explicit Save/FINAL/Stop actions without force-overwriting discrepancies;
the check itself remains read-only. Interrupted writes are held for explicit M4
recovery, not silently resolved. Actual FINAL and
log acceptance evidence is in `v1-m1-final-evidence-2026-09-10.md`.

## Acceptance ledger (not complete merely because an old unit test exists)

| ID | Required scope | Planned local evidence / external gap |
| --- | --- | --- |
| A01 | Offline + missing TeX; open/check not compile authority | M1/M2 no-network/no-write/no-compile; editable missing-tool flow |
| A02 | root/child, tabs/windows/shared dependencies | M1/M5 result identity and navigation integration |
| A03 | Typing/external edits/late callbacks | M1/M5 stale-result rejection with content observations |
| A04 | Failed/cancelled/stopped/late builds | Existing compiler suite + M5 workflow regressions |
| A05 | PREVIEW/FINAL/SyncTeX/export | Existing split state + M1/M5 stale/preview rejection |
| A06 | Formula/table cancel/Undo/unknown macros | Existing draft tests + M2 native keyboard/regression |
| A07 | Buffer/disk and source three-way conflicts | M3/M4 faults preserving both sides |
| A08 | Checkpoint corruption/interruption/low space | M4 original and restored-byte assertions |
| A09 | Cloud/unreadable/migration | M4 explicit unknown + bounded copy verification; no cloud downloads |
| A10 | Dependencies/config change during delivery | M5 check/compile/export content identity fault injection |
| A11 | Paths/symlinks/malicious hooks | Existing boundary suites + M1/M4/M5 adversarial fixtures |
| A12 | IME/keyboard/scale/close lifetime | Local Cocoa/AX evidence separate from offscreen; Windows gap |
| A13 | MCP auth/protocol/concurrency | Existing MCP suites, unchanged topology and wire contract |
| A14 | Old/new formats; external ordinary TeX use | M4 version rejection and M5 external TeX fixture compile |
| A15 | Real installation/update/recovery | Not authorized here; release hold remains, checklist only |

## Performance method and completion tracking

Use `tools/bench_response_pipeline.py` first on the unchanged app baseline, saving
`docs/data/v1/m0-response-baseline.json`. It measures 4k/12k/40k-word synthetic
projects, GUI dispatch/completion and timer delay, visible panel input bursts,
asset scans and cold/warm/changed XeLaTeX builds. It is not human usability,
native display scanout, arbitrary macro coverage or Windows evidence.
Measured on macOS 26.6.1 arm64, Python 3.12.6, PySide6 6.11.1 and watchdog 6.0.0:
visible-outline editing median 0.230 ms / max 0.441 ms, one debounced update after
15 edits, zero image scans, and Word Count timer lateness 18.085 ms. Background
4k/12k/40k TeXcount medians were 121.187/348.032/1655.009 ms; structured fallback
medians were 54.131/218.575/1106.807 ms. The first eight-page XeLaTeX cold trial
took 2206.152 ms and its unchanged trial 64.145 ms. These are synthetic samples.

Comparable-machine M6 regression targets: no scans or check worker launch on
typing; visible-outline edit max below 2 ms, uncached count dispatch below 10 ms,
and GUI timer lateness below 50 ms. Treat timing overruns as investigation signals,
not universal claims or brittle CI assertions. Pending check work is bounded.
M6 repeats comparable
samples and adds dependency scans, memory, close/cancel and visible PDF evidence.

- [x] M0 baseline, fixtures, measured targets and verified roadmap drift closed.
- [x] M1 complete read-only vertical slice, core/GUI/native acceptance.
- [ ] M2 full workbench/onboarding/profile/editor acceptance.
- [ ] M3 materials/citations/provenance and safe technical repair acceptance.
- [ ] M4 project checkpoint/draft/restore/migration acceptance.
- [ ] M5 frozen submission and complete recovery workflow acceptance.
- [ ] M6 all applicable local quality checks and explicit external gaps.
- [ ] M7 readiness checklist; no automatic external release action.

The first M2 slice now provides editable/disableable local declarative profiles,
reused template/engine recommendations, directory suggestions, optional word
targets and static-check visibility. Profile identity participates in readiness
invalidation. Unknown schema, unsafe paths, oversize reads and external changes
fail closed. Saving does not apply a template/engine, create suggested directories,
compile or change source. The existing project lock is reused by a non-blocking
CAS writer; it is not protection against arbitrary external edits in the final
replacement syscall. Native/core/GUI evidence is in
`v1-m2-profile-verification-2026-09-10.md`; exact suite results are in state/log.

The second M2 slice implements Chinese-name creation and first-use guidance,
new-directory-only writes, template/profile validation before mutation, explicit
engine selection without compiling, and default new-window preservation of an
existing workspace. A full-width presentation row reuses cached tab/root state,
existing save/FINAL/export guards and navigation. Child source navigation keeps
canonical project scope. Block controls use actual session ownership; clean close
restores ordinary source controls and its FINAL. Target-to-profile navigation and
misleading legacy static-check status text are corrected. Focused and native
evidence, failed runs and exact limits are in
`v1-m2-workspace-verification-2026-09-10.md`; final full discovery passed.

The third M2 slice guards model/generated writes together, refuses external and
unknown-format conflicts, stages bounded recovery bytes, and asks explicit close
choices while pausing automatic writes. Save-close-reopen and asynchronous visible
FINAL are verified; stop no longer closes a session. Unknown table drafts remain
unchanged. Partial/staged journals intentionally block retry and are not accepted
checkpoints. Full/core/GUI/native evidence and the reproduced reopen defect are in
`v1-m2-block-close-verification-2026-09-10.md`.

The fourth M2 slice now has focused/native evidence for wrapped button rows,
scroll containment, first-window scaling, contextual fields and explicit narrow
editor/PDF switching. Projection no longer changes loaded layout properties;
selected-slot weight works through the existing command stack. Physical
Control+Tab leaves the multiline inspector without applying or consuming normal
Tab input. Five scales/two window sizes, actual FINAL and existing close/workspace
flows passed on the same app source. Full discovery passed. This is scoped layout/
keyboard evidence, not full editor-draft or M2 completion. See
`v1-m2-block-layout-verification-2026-09-10.md`.

The fifth M2 slice protects unapplied alias/text/heading/image and layout fields,
with target/base ownership, local text Undo and session-visible pending state.
Explicit Apply or a confirmed batch validates all bases before one model command.
Save/close/FINAL/checking distinguish pending properties; conflicts and newer
re-entrant input are retained. This remains memory-only, not M4 recovery or a
universal session/D010 promotion. The final frozen-source suite passed; see
`v1-m2-property-draft-verification-2026-09-11.md` for full/focused/native receipts.

The sixth M2 slice now keeps each table target explicit through editing, switching,
local Undo, Apply, Save and reopen. Live cell input is dirty before delegate commit;
no read-only/Save path silently projects the current table over the first registry
table. Table and alias batches preserve unedited opaque fields and validate every
base before one global command. Formula entry points share captured-target
validation; accepted stale/deleted input stays reviewable without overwriting.
The image picker now rejects changed targets before copying. A native-discovered
Enter/immediate-switch stale delegate commit warning was reproduced with two red
tests and fixed by finishing only the delegate's already-queued commit request.
The existing session, formats, writer and Source/PDF state remain authoritative.
170 focused tests and four same-source native probes passed. Full verbose discovery
passed 1122 tests in 996.164 seconds, exit 0, on app SHA-256
`caac75122b49f7a0e283cf1a8203a1beaa62d5d458b9c67ad21eb24abc1b1625`;
with its hash rechecked after completion. Receipt:
`/tmp/icstex-v1-m2-editor-targets-suite-r2.log`. The earlier full r1 was explicitly
superseded by the native-found source fix and terminated, not accepted. See
`v1-m2-editor-target-verification-2026-09-11.md` for exact scope and receipts.
The full-run handle `78934` / PID `71286` is terminal. It is not a running blocker.

Current slice contract: importing a chosen image must preserve source/existing
assets, remain inside the canonical project, and apply to the captured image row.
Reuse `safe_project_input`, the cooperating project lock, existing Block commands
and Inspector file picker. Keep import byte copying in the core module and errors/
selection in the Qt entry points; no general transaction, format or session change.
Staging plus exclusive publication avoids partial images and clobbering a filename
created during copying. POSIX directory descriptors reject observed links and
anchor writes; Windows reparse races and filesystems without exclusive publication
remain explicit acceptance limits, not silent replacement fallbacks.

Initial core red tests reproduced parent/dangling-link writes, partial-copy output,
filename clobbering and source-change success. Nine core checks now pass, including
directory replacement, failed publication and busy-lock refusal. Drag tests found
missing failure/closed-session guards and wrong coordinate-to-image-row routing;
the Qt entry point now reports failures and keeps the captured target. A new test
fixture initially dropped its borrowed QMimeData too early (exit 139); retaining
it fixes the fixture, and the same app then reaches the expected red assertions.
Do not confuse that fixture fault with earlier unresolved native crash causes.

The submission-check test fixture now explicitly deletes its own closed window.
An isolated eight-test disposal trial passed and left zero MainWindows / 7 widgets,
versus eight closed windows / 5518 widgets before the fix. Do not change application
window ownership based on this test-only result. Broader fixture cost remains to
measure in the next full run. Final focused integration passed. The actual native
picker cancellation reached the zero-mutation assertions; successful selection/
import did not complete. The owned synthetic probe was stopped for the user's
source-sync request, not accepted. Full snapshot validation passed, exit 0, in
`/tmp/icstex-v1-source-sync-20260911-tests-r1.log`; exec session `78503` is terminal.
Image details and exact source identity are in
`v1-m2-image-import-verification-2026-09-11.md`.
After this authorized checkpoint, resume real image picker/error/PDF acceptance,
then source-mode/unknown-macro fidelity and the remaining M2 keyboard/IME matrix.

M4/M5 still own consistent recovery/frozen delivery. Keep the earlier Qt crash
causal uncertainty, native IMK/table warnings, high-scale readability and
IME/AX/Windows/human gaps visible for M6. This full run also exceeded the preceding
suite duration; another one-second live sample showed Qt application stylesheet
work and 2.1 GB whole-suite footprint. M6 must isolate scaling/retained-window cost
with comparable samples, not equate functional success with performance pass or
declare a leak from a single whole-suite memory observation.
Use verbose discovery on the next full run to identify slow test cases without
changing assertions. Record machine load
and memory pressure before comparing timings; this run had substantial system
swap use, so elapsed time alone does not establish a patch-specific regression.
