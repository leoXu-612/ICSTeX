# V1 local implementation and acceptance

Updated: 2026-09-11. M0/M1 complete; M2 property-draft slice verified locally; full M2-M6 incomplete.
Active slice: M4 interrupted Block-write recovery and explicit migration remain next. Reviewed recovered-draft resumption passed focused, actual offscreen product and final frozen-source full regression; all run handles are terminal, with receipts in PROJECT_STATE.md. The explicitly authorized increment was pushed as 9360f86 and its full remote hash verified; codex/v1-development already matches the scope and needed no further rename. Prior checkpoints c521041 and 1b1f371 remain preserved. This is not complete M4 acceptance or standing push authority. Native M2/M3 acceptance still waits for manual Mac unlock.
Full scope: `CODEX_V1_DEVELOPMENT_INSTRUCTIONS.md`, M1-M6 plus M7 readiness handoff.
No automatic commits/pushes, packages, installed-app changes, signing or publication.
Exception for this checkpoint only: on 2026-09-11 the user explicitly requested
the needed rename and source submission. The local branch was renamed to
`codex/v1-development`; retain the remote `release/2.1` and all release gates.
Full validation passed and the existing V1 checkpoint was committed and pushed
only to the development branch with `[skip ci]`; the remote SHA was verified.
The source identity and receipt are in `PROJECT_STATE.md` and `PROJECT_LOG.md`.
This is not standing permission for later automatic pushes.
The user's renewed request to rename and submit was fulfilled for the later local
batch as source checkpoint `c521041`, with the remote hash verified. The branch
name already matches its V1 scope; no product, artifact or release-branch rename
was needed. This second checkpoint also grants no standing automatic-push authority.

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

On this continuation the Mac is locked; the desktop tool explicitly requires
manual unlock. Do not bypass it. Image probe r3 reached only its first real picker
and was explicitly stopped when the formula-source fix superseded its app tree
(PID `78939`, exec `20497`, log `/tmp/icstex-v1-m2-image-import-native-r3.log`).
It is not accepted or a running blocker; after unlock, launch one new final-source
probe and operate its actual picker.
Independent local M2 contract: replacing a selected formula must validate the new
envelope as well as the original range. Reuse the pure `final_edit_plan` recognizer
and the existing dialog's invalid-plan/Undo handling; no parser broadening, source
normalization, document conversion or writer change. Red tests cover ambiguous
replacement delimiters and comments; unknown macros, comments and whitespace must
remain exact through source fallback/Undo/Cancel. Rollback is limited to this
planning guard and its focused tests. A second red reproduction showed visual
paste folding comment newlines into spaces and thus changing TeX meaning. Keep
paste body bytes intact; if the existing tree cannot round-trip that pasted body,
reuse its literal Text fallback. Do not rewrite the parser or normalize source.
Native keyboard acceptance stays separate.
The focused formula/tree/widget/dialog/Block-target suite passed. Required full
verbose discovery passed on frozen app SHA-256
`0c430570de459bea98fd81452a122e3af3a09a24f7f3365c68c0ac0794014ea5`,
exec `84388` is terminal, log `/tmp/icstex-v1-m2-formula-fidelity-suite-r1.log`.
See `v1-m2-formula-fidelity-verification-2026-09-11.md` for reproductions and limits.

Read-only M3 orientation identified existing reuse seams: `SourceRecord` plus
`Block.provenance.sourceId`, `check_source`, the existing Sources tab, ordinary
References/Images panels, dependency snapshots and bounded readiness workers.
An independent synthetic probe confirmed `_locate_by_hash` follows a file link
outside the project and hashes `.git/config`, reporting both as moved candidates.
Receipt: `/tmp/icstex-v1-m3-source-boundary-red-r1.log`. No real user data was used.
Code inspection also found unbounded search and hashing on model refresh.
The existing resync action only advances the recorded hash; it is not a three-way
data merge. These observations led to the current source-status slice, not full
M3 functionality. Keep source status read-only and expose affected Blocks;
technical repair remains a separately previewed/confirmed/CAS-protected action.
M3 first-slice contract: users explicitly inspect recorded source status and find
affected Blocks without changing source records, baselines or data. Reuse safe
input opening/path rules, SourceRecord and provenance IDs; add bounded/cancellable
stream hashing and source lookup. Unreadable, incomplete, changed-during-read or
ambiguous results remain unknown. Qt owns one active worker plus one latest request,
discards stale/closed results, and never scans during model refresh. Replace the
misleading hash-only resync action with read-only status/details/navigation; actual
technical repair remains later. Tests cover links/internal paths, limits, failures,
no model/metadata writes, cancellation, late results and affected-target mapping.
Rollback is confined to source-status core/controller/navigation seams; no project
format, authority, writer, MCP or release boundary changes.

The source-status slice now implements the above contract; 82 focused tests and
the actual offscreen four-source refresh/navigation/reopen probe pass with no
project bytes, source baselines or table edits changed. Full verbose discovery
passed 1168 tests in 477.939 seconds, exit 0, on app SHA-256
`6c87ebcf98f88c87f1ae43a89ee79f34310ea69ee45fb4bcee3508fc4765e020`,
unchanged after completion. Exec `70944` / PID `84015` are terminal, receipt
`/tmp/icstex-v1-m3-source-suite-r1.log`; do not restart it. Native acceptance remains held by
manual unlock. See `v1-m3-source-status-verification-2026-09-11.md` for exclusions,
byte/entry limits and failed-fixture qualifications. The next independent local
slice is ordinary-source citation health/usage;
source technical merge remains separate and not authorized by a refresh.

Independent orientation for that next slice reproduced existing citation gaps:
duplicate keys collapse in `bib_keys`, optional-argument citations are missed,
commented citations are counted, and `bib_text_for_tab` ignores an explicitly
declared nondefault bibliography path. Synthetic-only receipt:
`/tmp/icstex-v1-m3-citation-orientation-red-r1.log` (exit 0 means reproductions
confirmed, not acceptance). No citation source was changed during the frozen
source-status full run. Reuse `static_dependencies`, bounded strict input reads,
the current ReferencesPanel and existing navigation. Implemented contract: explicit
read-only citation health with file/line usage and duplicate/malformed/missing/
unused distinctions, captured root/buffer ownership and late-result rejection.
Unknown/dynamic or incomplete inputs cannot imply complete unused/missing checks;
unused entries are suggestions, never deleted. Keep DOI/arXiv lookup explicit,
do not auto-import or normalize BibTeX, and keep repair/insert authority separate.

The citation slice now includes core syntax/health, the focused controller and
ReferencesPanel integration. Explicit checks follow supported declared libraries
and captured editor drafts, expose locations/limits/unknown coverage, and guard
navigation against stale bytes. The old shortcut library now reads safely and
does not claim project completeness. Final app SHA-256 is
`a12ade12f6d5573f99a03e83f8ef9e3b784538b5c0cfc4cbe520ba0ad9a84baf`.
Focused 36 tests and the 80-test broader integration pass. The actual offscreen
synthetic panel checked duplicate/missing/unused entries, navigated the child,
used an unsaved BibTeX draft and cancelled with zero source writes/compile authority.
A separate explicit BibTeX FINAL produced one verified page. See
`v1-m3-citation-health-verification-2026-09-11.md` for exact limits and probe corrections.
Full discovery passed 1,200 tests in 559.206 seconds, exit 0; exec `33298` / PID
`88960` are terminal, receipt `/tmp/icstex-v1-m3-citation-suite-r1.log`. The app
hash was rechecked unchanged after completion. Do not restart that completed run.
The next independent local slice is ordinary-source material usage/status;
source technical merge remains separately previewed/confirmed and reversible.
Do not count this panel as replacing M1 static checks or completing all M3.

Read-only material orientation now reproduces four existing inventory gaps:
the active saved source is counted twice, commented includegraphics is counted,
graphicspath-based use is missed, and removed unsaved draft use remains counted
from disk. Synthetic receipt `/tmp/icstex-v1-m3-material-orientation-red-r1.log`,
exit 0 confirms these observations, not a fix. No app source changed during the
citation full run. Reuse ImagesPanel, static dependency locations, existing safe
reads and root/buffer ownership. Keep thumbnail size/mtime caches separate from
content identity; do not make an explicit read-only usage check save AssetIndex.
The material slice now shows supported literal includegraphics/includesvg/includepdf
locations, missing/unknown and content-change status, noncurrent-buffer precedence
and dated in-memory prior observations. It reuses bounded static source and asset
hash reads, rejects observed unsafe/internal paths, and bounds active/pending work.
Typing and the health tab do not run legacy inventory usage scans. Shortcut metadata
stays cached in memory without project cache I/O; warm scans retain correct metrics.
Cancellation/edits/external changes/close reject old results; content-checked
navigation preserves the actual PDF view. It never moves, rewrites or deletes files.

The first full run terminated with one obsolete disk-cache assertion (1223 tests,
368.431 seconds, exit 1; exec `15407`, receipt
`/tmp/icstex-v1-m3-material-suite-r1.log`). The strengthened replacement checks
record/metadata reuse and zero writes, then exposed a warm-scan metric error that
is now fixed. Final focused integration passed 109 tests in 9.786 seconds, exit 0;
actual offscreen product r4 passed on app SHA-256
`cc506a5a59b3f4e187937ed4283650b53f6b7de817c7f249f7896b3f7e5fa61e`.
The final frozen-source full run passed 1,223 tests in 364.943 seconds, exit 0;
exec `96648` / PID `96374` are terminal, receipt
`/tmp/icstex-v1-m3-material-suite-r2.log`. The app hash was rechecked unchanged
after completion; do not restart this completed run. See
`v1-m3-material-usage-verification-2026-09-11.md` for byte limits,
separate verification passes, real watcher retries, UI/FINAL receipts and native gaps.

M3 technical-repair orientation confirmed a blocking defect: the real MergeDialog
accepting one conflict deleted an untouched sibling cell in that row.
The synthetic memory-only orientation receipt
`/tmp/icstex-v1-m3-merge-orientation-red-r1.log` confirms this, not a fix. Preserve
whole rows/cell metadata and original merge inputs before integration. Current
workspace merge UI at that point only changed a label; the later separate source-repair entry now applies a real command.
SourceRecord has no table base snapshot: inspect existing import/snapshot seams,
never invent a base from current local or changed remote. A real repair requires
separate diff preview, confirmation, captured target/source identity checks and
one Undo, with cancel/conflicts preserving both sides. Keep table/source formats,
the existing session and authority gates; broader format changes require evidence.
Import orientation also confirms CSV input with 5,001 body rows returns 5,000
without a truncation error (`/tmp/icstex-v1-m3-import-limit-orientation-r1.log`,
synthetic in-memory only). Existing import adapters assign row/column IDs by
position. Before using them for repair, reject incomplete imports and make the
mapping explicit; position IDs alone do not prove identity after inserted rows.
CSV/XLSX readers and merge structure handling need targeted tests before any
user-confirmed source-to-table application.

The current fix now returns independent merge candidates, preserves sibling cells,
types/whitespace and complete chosen table metadata, and refuses duplicate identities.
Both-sided structural/order differences become explicit whole-table choices instead
of silently losing/deleting/resurrecting content. The dialog requires a fresh complete
preview before candidate confirmation; no source/session mutation is implied, and
the workspace no longer labels this as applied synchronization. CSV/XLSX limits
reject partial output, short headers/blank rows retain data, and actual header rows
and XLSX merge coordinates follow the existing renderer contract. Persisted tables
are not automatically migrated. Focused and real offscreen dialog/FINAL checks pass;
first full exec `51161` / PID `99944` passed and is terminal. A final preview-identity
red test led to displaying table IDs and Chinese cancellation. Final app SHA-256 is
`39f26a52093da449f06ddf32bf5610808b1e126616298c6a96b3abdb042c6cee`;
focused/product and the final frozen-source full run passed. Exec `96245` / PID
`1534` are terminal, receipt `/tmp/icstex-v1-m3-merge-import-suite-r2.log`, with
the app hash rechecked unchanged. Do not restart either completed full run.
Details: `v1-m3-merge-import-verification-2026-09-11.md`.

The source-repair integration now obtains Base from captured bytes matching the
recorded digest and requires explicit import options, complete column mapping and
a unique row key. It reviews ALL linked tables before advancing their shared source
record. A final raw-content preview precedes source rehash/target/draft checks and
one command; Undo restores the original models/record and consumed table drafts.
Original source files stay untouched. Exact unmodeled content is retained through
the existing projection seam, and normal guarded persistence remains authoritative.
Sources/Block schemas and compile permissions are unchanged. Actual synthetic UI,
cancel, external source conflict, apply/Undo/Redo, saved reload and FINAL passed.
The mapping control geometry was fixed after screenshot inspection; final-source
focused/product checks passed. Cancellation stress also exposed overlapping retry
workers, now limited to one active read per session even after dialog cancellation.
Final full exec `53595` / PID `7114` passed and is terminal on unchanged app hash `aebdfa7b`; the earlier
full exec `12034` (passed, terminal) and `51781` (deliberately stopped after the
source changed, terminal exit 143) are not final-source acceptance.
Details: `v1-m3-source-repair-verification-2026-09-11.md`.

M4 core implementation now captures explicitly selected original bytes into a
versioned, bounded archive, with separate supplied draft payloads and relative
identities. Every file is read twice and rechecked before exclusive publication.
Restore fully validates objects, stages under an explicit incomplete name, performs
byte/inventory/identity readback and publishes a NEW container with project/ and
separate drafts/. macOS exclusive directory rename was exercised against a target
created at publication time. No source overwrite, model application, compiler launch,
network access, writable MCP authority or legacy history pruning is involved.
The 25 focused cases and real ordinary/Block filesystem reload/FINAL probe pass.
Final full discovery passed 1289 tests in 366.453 seconds, exit 0; exec 1766 /
PID 10802 are terminal, and app hash 71ff3988 was rechecked unchanged afterward.
Earlier full 72702 / PID 10326
was deliberately stopped, terminal exit 143, before the final incomplete-directory
README clarification; it is not final acceptance. Details and all limits:
`v1-m4-checkpoint-core-verification-2026-09-11.md`.

The required history audit reproduced outside-project deletion via forged manifest
paths and acceptance of changed valid UTF-8 history. The bounded repair now derives
source-specific buckets and object paths, validates content digests and manifest
membership, and confines retention to verified owned objects. Valid legacy buckets
are read-only. GUI confirmation rechecks the captured editor and history; accepted
restoration is one undoable unsaved change, without Save or compilation. Synthetic
Cancel, tamper refusal, Undo/Redo, explicit Save, reopen and visible FINAL passed.
See `v1-m4-history-safety-verification-2026-09-11.md` and the current state for final
source-identified regression receipts and remaining race/platform limits.

The File menu and History panel now expose explicit file selection, actual
source/Block draft capture and reviewed restore into a new directory. A GUI-owned
lease pauses cooperating writes and automatic compilation while capturing; newer
input invalidates the result. Restore binds to the reviewed manifest, leaves
originals unchanged and never applies drafts or switches projects implicitly.
Published results remain visible even when publication wins a late cancellation.
Final focused/product/full runs passed on unchanged app hash `11b95515`; all full
run handles are terminal. Details and source-identified receipts:
`v1-m4-checkpoint-gui-verification-2026-09-11.md` and `PROJECT_STATE.md`.

Reviewed recovery-copy resumption now verifies all manifest-listed saved/draft
bytes again after confirmation and creates a separate editor window. Source drafts
load as one undoable edit; Block state and unapplied fields remain separate, with
live table cells reopening through the existing editor. The first explicit save
releases an initial automatic-write hold; saved-byte conflict guards remain active.
Original projects and independent draft files are not overwritten. See
`v1-m4-recovered-drafts-verification-2026-09-11.md` for frozen-source evidence,
probe failures and limits. Next M4 work is pending Block journal recovery and
explicit migration; preserve incomplete journals instead of deleting them to
enable writes. No in-place restore, cloud-availability guarantee, native/Windows
or power-loss acceptance is implied.
M3 still needs retained source versions and scalable previews. The latest user
request authorizes this source checkpoint only; it does not open release gates or
grant standing automatic-push permission.

M4/M5 still own consistent recovery/frozen delivery. Keep the earlier Qt crash
causal uncertainty, native IMK/table warnings, high-scale readability and
IME/AX/Windows/human gaps visible for M6. An earlier editor full run exceeded its preceding
suite duration; another one-second live sample showed Qt application stylesheet
work and 2.1 GB whole-suite footprint. M6 must isolate scaling/retained-window cost
with comparable samples, not equate functional success with performance pass or
declare a leak from a single whole-suite memory observation.
Use verbose discovery on the next full run to identify slow test cases without
changing assertions. Record machine load
and memory pressure before comparing timings; this run had substantial system
swap use, so elapsed time alone does not establish a patch-specific regression.
