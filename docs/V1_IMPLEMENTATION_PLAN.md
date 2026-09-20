# V1 local implementation and acceptance

Updated: 2026-09-12. M0/M1 verified; M2–M6 are not fully accepted.
The Mac source stage is closed by the user's explicit scope adjustment:
"按 Mac 源码阶段性交付收尾，未完成验收留到后续".
This document retains the implementation evidence and deferred acceptance under
CODEX_V1_DEVELOPMENT_INSTRUCTIONS.md; it is no longer an autonomous work brief.
Keep FORCODEX.md and BETA_ACTIVATION_HANDOFF.md as the independent held Beta brief.

Completed user-selected delivery: the ordinary Mac writing source handoff.
Defer Biber support in the Agent/MCP restricted compile path; do not continue
its runtime design or make its approval a prerequisite for this source handoff.
See `MAC_WRITING_HANDOFF.md` for the existing source entry point and limitations.
The diagnosed Biber bootstrap failure remains recorded in
`v1-m6-macos-biber-boundary-2026-09-12.md`, not fixed or accepted. Application/tests
and their full gate are unchanged. Keep the ordinary GUI compile policy, existing
sandbox and fail-closed behavior; no executable-temp or unconfined fallback.

## Current authorization and source

The user has now directed Mac-first completion and stopped VM work. Do not
operate the Windows VM or advance E1 unless the user explicitly resumes that
work. Keep Windows acceptance deferred, not removed from the original scope.
Await the next user Goal before any further implementation or acceptance work;
do not automatically resume deferred checks or start performance changes.
R2 OS/menu evidence and R3 reliability risks stay explicit, without blind test
replays. R5 Biber development is deferred by the user's subsequent choice;
earlier R5 approvals below do not approve the proposed two-stage runtime.
Production release support remains separate.

Keyboard control was explicitly confirmed again on 2026-09-12. Prefer background
work; announce isolated native QA, use synthetic data and close test windows.
Do not touch student documents or the installed app. No automatic Git mutation,
packaging, signing, installation, deployment, release, new tasks or subagents.
Earlier rename/source-push grants applied to their own completed checkpoints,
not later increments. Current branch codex/v1-development, HEAD 3bde2b5;
subsequent local changes remain uncommitted and the index is empty.
The user explicitly authorized the temporary Mac sandbox and its isolated
input-policy experiment. It now passes bounded OS/engine controls, Latin and
Chinese-path/CJK compilation, rendered PDF review and termination. See
`v1-m6-macos-sandbox-prototype-2026-09-12.md`. The earlier compatibility research
retains its failures. The user subsequently approved integrating the backend into
the restricted Mac compile chain, with fail-closed behavior and no repetitive
testing. The bounded target is a runnable, verified Mac source increment by
2026-09-12 20:30 Asia/Taipei, not all V1 acceptance or a packaged release.
Use focused new adapter tests, actual driver/engine/bibliography/export checks,
and one final frozen-source full regression. Do not replay unchanged prototype,
GUI/IME or VM checks. D021 records the local-development security decision.
The actual LuaLaTeX/BibTeX chain, OS denial controls and driver/engine stop now
pass. See `v1-m6-macos-sandbox-integration-2026-09-12.md`; the single final full
gate passed (1598 / 313.187s / OK), with post-terminal source identities intact.
The bounded result was complete by 15:52, before the 20:30 target.
Biber and the deprecated backend's shipping support remain
unaccepted, not silently promoted by these bounded results.

Current app SHA-256:
`7009463b6f091f8d58f46fcfee3e08b03b3535fe9d89b0882ac7d3a133e87506`.
App+tests:
`14093898a54aa926b992b20106c570c1d2f6a5899af2ab35b69c157b1467cbc4`.
Directory Tab, skipped combos, combo Return implicitly confirming the parent,
and skipped delivery/migration tab bars have focused red/green evidence.
Standalone Block tab-bar StrongFocus now has five-tier red/green and native
100%/150% actual delivery-entry evidence. The new actual confirmation/disposal
test and hidden-window control pass their intended outcomes. Native r2 then
proved that the new window stayed behind its original owner. Post-modal raise/
activation now has focused red/green and native r3 acceptance; cancellation
does not request activation. Latest full and related regression identities
are authoritative in `PROJECT_STATE.md`; see
`v1-m6-migration-window-verification-2026-09-12.md` for exact evidence.
Post-terminal hashes, compileall/diff pass. Earlier native creation/profile
100%/150%, source/report review/cancel, ordinary PDF-only publication and
checkpoint/independent-draft/new-window recovery have scoped evidence.
Menu/compile AX activation and one picker field correction are not keyboard-only
proof. Current native r6 adds 150% Block FINAL/review/cancel, legacy-copy
publication at 100%/150% and 150% checkpoint/recovery controls. Migrated independent
window activation is now verified in its bounded r3 follow-up; OS/menu
keyboard-only evidence remains open.
All test/probe handles are terminal; no QA window remains. HEAD/empty index and
eleven retained crashes unchanged. See
`v1-m6-recovery-migration-keyboard-verification-2026-09-12.md` for source identities,
outputs and limitations; earlier modal/native receipts retain their own source.
Prior PDF geometry/native receipts
retain their own identities and need not be replayed.

Prior native r6 on app 9b2f44f5 confirms toolbar/rail/panel order, citation
navigation and 100%/150% Locate; earlier r4/r5 retain their failures and source
identities. Expanded 301 and full 1560 pass in
`v1-m6-native-navigation-verification-2026-09-12.md`, not on the new tooltip tree.

Prior eleven-table focus sweep, app 1c577ced / app+tests 50f38849, retains 81
baseline assertion failures, 273 focused green and 1554 / 159.894s full green in
`v1-m6-readonly-table-focus-verification-2026-09-12.md`; it was offscreen evidence.

Prior citation repair, app 4f83dd34 / app+tests 2f9a46c2:
native citation result-table Tab/Shift+Tab trapped focus in cells.
Both read-only citation tables now use widget focus traversal; arrow row selection
is retained. Two baseline red tests and 46 / 3.663s focused green pass; the final
offscreen five-tier layout/navigation probe passes. Native r2 recorded the actual
failure with intact source files and zero compile starts. Post-fix r3 could not
begin physical actions because CUA reported a newly locked Mac; that process was
interrupted and is terminal exit 130, not acceptance. Receipt:
`v1-m6-citation-keyboard-verification-2026-09-12.md`.
That citation tree's required full: 1552 / 152.832s / OK, exec 74555 terminal exit 0;
`/tmp/icstex-v1-citation-native-focus-full-20260912-r1.log`. Post-terminal
app/app+tests identities match; compileall/probe syntax/diff pass. Ten crash
reports, HEAD/empty index and held feed unchanged; all probe handles terminal.

Prior formula/source native receipts below retain app 489657f3 / tests 136e1892,
not the new citation-focus tree. Final formula/coordinate/table/Block focused:
133 / 5.788s / OK, exec 61139 exit 0.
Expanded 277 / 54.319s and required frozen full 1550 / 145.308s pass;
sequential exec 30576 is terminal exit 0; full ran only after expanded exit 0.
`/tmp/icstex-v1-formula-full-r1.log`. Post-terminal digests match;
compileall/diff pass. Ten retained crash reports unchanged; all handles terminal.
HEAD/index/held candidate unchanged. After the user's wake notification, a new
isolated Cocoa Inspector probe completed on these same hashes (exec 58955 exit 0).
Physical forward/reverse shortcuts reach Apply/Alias before/after Pinyin and at
100%/150%, preserve unapplied draft/model/disk, then keyboard Apply/Save/close
pass. Input source unchanged and test window destroyed in that run.
Receipt: `v1-m6-inspector-native-focus-verification-2026-09-11.md`.

Prior native increment: the user resolved keyboard contention on 2026-09-12.
Actual external-file change during Pinyin preserves the candidate and local
buffer; cancel/Chinese commit/Save-No preserve the external bytes, and native
Save As keeps the local draft separately. Exec 65068 exits 0. Current-source
visual/source formula partial conversion, cancel, commit, keyboard Undo/Redo
and Command+Return pass (execs 96322/13141 exit 0). All windows destroyed;
app/tests unchanged. R1 is addressed for the tested local Pinyin cases, not all
input methods. Receipt: `v1-m6-native-conflict-formula-verification-2026-09-12.md`.
The older unattributed-key run remains untested, not relabelled as this result.
That tree's required full repeat: 1550 / 169.147s / OK, exec 32613 terminal exit 0;
`/tmp/icstex-v1-native-conflict-formula-full-20260912-r1.log`. Post-terminal
app/app+tests match; compileall/diff, unchanged ten crash reports, HEAD/empty
index and held feed verified. The next active action is R2 below.

Earlier source repair: formula selection/application converts Python/UTF-16
coordinates explicitly, including package insertion, replacement, EOF and returned
cursor. Source-wrapper changes use Qt length. Formula confirmation now reuses
the captured source-target guard and preserves the draft on external reload or
target closure. Actual offscreen Cancel/Apply/Undo/prior-history/save/reopen/FINAL
and external-target refusal pass in r6, exec 19189 exit 0. Earlier pixel-check
failures are retained: measured glyph lightness 119 was excluded by the old <100
predicate. Formula-versus-blank ROI verification corrects that fixture; a visibly
pixelated 200% offscreen view is not native rendering-quality acceptance.
Receipt: `v1-m6-formula-coordinates-verification-2026-09-11.md`.

Previous source repair: completed TableDialogs are disposed after value extraction
or cancellation/failure. Package and snippet changes share one Undo and retain
prior history, tracked selections and UTF-16 positioning. A further actual modal
external reload split documentclass at the stale cursor; confirmation now guards
the captured source/target and retains the dialog draft plus copyable preview.
Actual offscreen Cancel/accept/Undo/prior-history/save/reopen/FINAL and changed-
target refusal pass on final source, exec 67845 exit 0. This is not native input,
AX or original timer-cause acceptance.
Receipt: `v1-m6-table-insertion-verification-2026-09-11.md`.

Previous source repair: accepted tab closure deletes its removed Qt editor at
the deferred event boundary. Twenty-four closed tabs no longer leave 24 live
editors in the stack. Cancel and named/unnamed save failure retain drafts;
active-document bytes/viewport and shared compile/PDF ownership remain intact.
The five background wrapper collections have been matched to earlier native
GUI-thread destruction in both focused fixtures and the original 131-case prefix;
they are not new native cross-thread deletion evidence. A separate parent-owned
TableDialog cancel-retention defect was reproduced and subsequently fixed above.
Receipt: `v1-m6-tab-disposal-verification-2026-09-11.md`.

Previous source repair: LineNumberArea now has a weak reference to its editor,
removing the owning Python cycle without changing Qt parent ownership. Baseline
assertions prove both unowned wrapper retention and retention after parent
deletion; both pass afterward. A baseline pending-event/worker-GC probe crashes,
while replacing only that back-reference passes; the final-source repeated
probe and original expanded command pass. No global GC suppression or Qt patch.
Exact historical timer receivers and native/AX acceptance remain unproven.
Receipt: `v1-m6-gutter-lifetime-verification-2026-09-11.md`.

Previous source repair: a context-free post-move tree selection accessed a deleted
QFileSystemModel after close and selected an old path after a project switch.
Two baseline failures prove both. The callback now has window lifetime context
and captured-root validation, with unchanged filesystem/compiler/save guards.
Normal actual-window rename retains selection, recent paths, bytes and viewport.
This repair does not explain the new expanded-suite native timer SIGBUS.
Receipt: `v1-m6-deferred-selection-verification-2026-09-11.md`.

Previous source repair: LaTeXEditor has a monotonic source identity independent of
IME-only Qt layout revision changes. Five read-only consumers retain reports and
cached source during preedit/cancel. Actual commits, partial edits, Undo/Redo,
blocked reload and inactive related-tab changes still reject old identities.
No full-document polling was added. History/checkpoint transaction guards retain
their stricter Qt revision/content-event checks. Four baseline failures and
actual controller/late-callback/cache tests plus the frozen full pass.
Receipt: `v1-m6-source-identity-verification-2026-09-11.md`.

Previous source repair: citation status/identity presentation no longer widens the
dock; wrapping actions and full cell/location tooltips retain complete values.
Repeated same-row report replacement restores detail/locations. The fixed-height
tool rail is now scrollable and follows Up/Down focus across all nine tools.
Five-tier normal/minimum-window offscreen observations verify true visible regions,
not just containment in a viewport that itself extends beyond the window. Actual
read-only child navigation and original bytes pass; final-source probe exec 74593
exit 0. No native UI operation; physical focus/layout remains pending.
Receipt: `v1-m6-citation-layout-verification-2026-09-11.md`.

Previous source repair: ordinary-source notifications distinguish actual text
changes from native preedit layout updates. Default 800 ms idle-save preserves
committed text, live candidates, cursor/Undo and source-tab ownership; cancellation
does not rearm a timer or immediately invalidate through that notification. A
later observation on that source proved periodic citation reconciliation still
invalidated on preedit-only Qt revision; the source-identity repair above now
closes that reproduced read-only defect, not the remaining physical R1 cases.
External edits during live
composition use existing conflict protection, including after a partial save.
Four baseline failures, editor-event and actual-default-timer regression exist.
Qt selection removal at composition start remains an actual Undo-able source
edit. This does not redefine native selection semantics. User reported unlock,
but the control channel still reported locked; no native window/input started.
Receipt: `v1-m6-idle-composition-verification-2026-09-11.md`.

Previous source repair: UiScaleManager retains a local live-widget snapshot during
synchronous font/style dispatch. A controlled cyclic-widget GC event reproduced
QtWidgets SIGSEGV on baseline; a held-wrapper control and the application fix
both prevent it. No global GC change, ownership change or persistent widget cache.
Final-source real StyleChange subprocess, 24-window offscreen natural/forced-GC
and six-window Cocoa checks pass; native windows closed. The exact historical
stylesheet object and separate timer-dispatch causes are not proven fixed.
Receipt: `v1-m6-style-gc-verification-2026-09-11.md`.

Previous source repair: luaotfload fatal headers and quoted log wraps now enter
the error/Chinese diagnostic panel, without a student location or automatic fix.
Actual final-source restricted compile and offscreen settled-window r5 pass the
diagnostic assertions, not engine compilation. The installed absolute Unicode
resource is present but Lua io.open is denied under paranoid I/O; identical
project-local bytes are readable and the parent sentinel remains denied.
Restricted LuaLaTeX compatibility is still open. Security/dependencies and the
GUI default I/O policy are unchanged; the compiler change is a comment only.
Receipt: `v1-m6-lualatex-verification-2026-09-11.md`.

Previous source repair: Inspector Control+Tab/Control+Shift+Tab use content-widget
scoped QShortcut dispatch, not the missing native KeyPress. Event-boundary red/
green and 100%/150% actual-MainWindow offscreen focus/draft/Undo/routing checks
pass. The earlier locked native attempt was cleaned up, exec 63025 exit 130;
the newer current-source native pass is recorded above. No input-source change.
Repair receipt: `v1-m6-focus-readiness-verification-2026-09-11.md`.

Previous product repair: ordinary source Save had no shortcut. It now uses the
standard Save sequence through the existing action; real Command+S writes the
expected Chinese source with unchanged cursor/scroll. Focused actual-key/mode-
routing tests and native ordinary r3 pass. No compiler or save path was rewritten.
Receipt: `v1-m6-workbench-input-verification-2026-09-11.md`.

Previous repaired gap: custom visual formula input-method events were ignored.
Visual and source-mode composition now keep preedit separate, refuse premature
Apply/mode switches and preserve undo. Ordinary source, Inspector and actual
table delegate event-level tests cover draft/target/no-write invariants.
Actual Cocoa Pinyin commit/cancel/Undo/Redo/Apply passed in both formula modes
on app b6da0987. The final d8175978 additionally fixes selected partial commits'
undo boundary; that extra case has event-level red/green, not a relabelled
same-source native receipt. Details: `v1-m6-ime-verification-2026-09-11.md`.
The first full had a missing grandchild.pid fixture error. R4 now has an explicit
real-child readiness gate and a post-kill drain bound, with slow-start red/green
and a driver-only-termination negative control. Application timeouts are unchanged;
the old host scheduling cause is not claimed proven. Focused and frozen full pass.

## Closed source stage and retained acceptance work

The requirement/evidence inventory is `V1_ACCEPTANCE_MATRIX.md`, including
M0–M7/A01–A15 and finite local R1–R6 versus external E1–E4. It is not an all-pass
certificate. Keep its outstanding rows current instead of restarting old slices.

**Closed stage: ordinary Mac writing source handoff; incomplete acceptance deferred.**
The user explicitly confirmed this closeout scope on 2026-09-12. The launch route,
capabilities and risks are in `MAC_WRITING_HANDOFF.md`. The source was launched
at the user's request and its native welcome/toolchain-ready state was observed;
this is not full human acceptance, an installed update or an R2/R3 waiver.
Application/test hashes remain unchanged; no accepted tests were replayed for
closeout. The records below retain outstanding requirements, not instructions
to continue this Goal. Await the user's next assignment.
The previous R5 LuaLaTeX/BibTeX source increment is complete; the distinct Biber
chain fails closed and remains deferred, not accepted via its BibTeX result.
The [original-requirement audit](v1-local-closeout-audit-2026-09-12.md) is complete.
The [modal receipt](v1-m6-modal-keyboard-verification-2026-09-12.md) now adds actual
creation/profile keyboard operations, ordinary PDF-only output, checkpoint and
independent-draft recovery with native pickers and explicit confirmations.
Do not recreate those outputs. Standalone Block keyboard entry, 150% delivery/
checkpoint/recovery controls and legacy-copy publication now have native evidence.
Focused five-tier RecoveryDraftDialog, post-migration source/open controls and
standalone Block tab-bar traversal pass; see the
[follow-up receipt](v1-m6-recovery-migration-keyboard-verification-2026-09-12.md).
Native r5/r6 and the subsequent window probes are terminal and windows are closed.
The retained copy was reused, not republished. After manual unlock, native r2
proved the new window was alive/visible but inactive behind the original owner.
The production modal wrapper now raises/activates the explicitly opened copy
after its modal scope ends; No/cancel still requests no activation. Focused
red/green, related regression and native r3 confirm the repaired transition.
See `v1-m6-migration-window-verification-2026-09-12.md`.
Do not rerun this closed window case. The remaining OS/menu keyboard evidence
cannot be inferred from AX menu clicks: CUA previously routed menu keys to the
underlying Qt window. A human keyboard check or a demonstrably different usable
control route is needed; do not repeatedly send the same keys or change OS
keyboard settings without authority. R3 needs an identified discriminating
observation or maintainer risk disposition, not another blind regression loop.
R5's subsequently approved source integration now produces a Chinese/math/BibTeX
PDF through actual latexmk/LuaLaTeX, preserves source/input evidence, enforces
the revised driver-profile denial controls and terminates the real process tree.
Actual stdio export has staged integration evidence. D021 permits this local
backend; missing/failed isolation refuses compilation. See
`v1-m6-macos-sandbox-integration-2026-09-12.md`. Do not replay the prototype or
closed actual-chain checks. Biber/PAR, alternate installations and the deprecated
command/private profile's shipping support remain unaccepted.
The existing Windows 11 VM is running, but the read-only guest environment
check cannot execute: prlctl exec requires Pro/Business, and CUA still reports
noWindowsAvailable for coordinates after Raise; one Ctrl+Escape did not produce
a visible Start menu. No terminal or product test started. The user subsequently
stopped VM work in favor of Mac-first completion. Do not repeat this
route, upgrade the license or change VM settings. This does not prove
a guest/product defect or current Python/Qt/TeX availability. E1 remains open.
Do not add optional polish or restart accepted source/console/PDF/IME cases.
R3 historical risk disposition, R5's unverified support scope and external E1–E4
remain separate. The five-hour target applies to the bounded Mac source increment,
not these other gates; this finite audit does not complete local V1 acceptance.
Word Count/Submission Check are now covered by five-tier long-text tests and
physical 100%/150% refresh/results/detail/reverse-focus checks. Do not repeat
them, diagnostic collapse/navigation, four-route or R1 cases merely to accumulate
passes. No live window/process remains; announce the next native window.
See `v1-m6-pdf-geometry-verification-2026-09-12.md`. Earlier clipped/locked
runs retain their own evidence and are not relabelled passes.

Previously, the user confirmed unlock and CUA resumed actual keyboard control.
Citation detail/list/Locate, Space child
navigation, rail arrows and focused-button scaling have bounded native evidence.
Native follow-up exposed offscreen focus and an incorrectly assembled focus
chain; both are repaired. Final-source r6 confirms toolbar ↔ rail ↔ panel and
100%/150% Locate, including external reverse entry. r5 retains its own five-tier
and nine-tool observations; do not relabel them as final-source native results.
See `v1-m6-native-navigation-verification-2026-09-12.md`. No live native test
window remains. Announce any new native window and preserve files.

R1's remaining local Pinyin cases passed on 2026-09-12: real external conflict
during composition, cancel without overwrite, Chinese commit plus explicit
Save-No, and native Save As with both versions preserved. Current-source formula
visual/source modes preserve partially converted preedit, disable confirmation,
cancel exactly, commit Chinese, Undo/Redo and accept by keyboard. Receipt:
`v1-m6-native-conflict-formula-verification-2026-09-12.md`. The returned formula
plan is verified; these isolated dialogs are not a new whole-window insertion/
FINAL run. No combined nonempty commit/preedit event was emitted; event-level
coverage remains distinct. Do not repeat these cases, default-save or Inspector
100%/150% focus as the next action.

R2 includes bounded eleven-table traversal repairs and four read-only Return/
Enter activation routes (outline/search/diagnostics/compiler errors). Their
positive and negative offscreen controller tests pass; native diagnostics/error
Return actions now also pass for the labelled fixtures. The single-result selection hint explicitly
includes Space, without weakening the empty-selection guard. Do not expand keyboard activation to repair,
restore or insertion controls. Citation navigation and the tested rail/scale
cases above need not be restarted; only their OS/menu keyboard-only evidence
remains open, not the already verified modal controls or outputs.
The separate 200% native PDF sample was inspected and is readable; its previous
offscreen pixelation cause remains unproven. Current source-table/formula target, Unicode,
package/Undo and lifecycle repairs have bounded evidence; do not restart them
or blanket-delete OCR workers.

R3 retains historical timer receivers/exact stylesheet-object uncertainty and
the scoped Cocoa AX selected-children limitation. The five observed wrappers
were collected after native GUI-thread destruction; that is not original-crash
causality. Further timer work needs a new discriminating test, not blind full
repeats. R4 fixture readiness and false-green detection are addressed locally.

R5's tested Mac LuaLaTeX/BibTeX source path is implemented under D021, with
fail-closed startup and explicit limits in the integration receipt. The earlier
research/prototype keep their own failures and identities; no distribution-cache
path override is treated as a read-only allowlist. Preserve the installed
distribution, ordinary GUI policy and all remaining D014/D015 authority gates.

M2 image/formula clipboard, M3 citation/material/repair, M4 recovery/migration
and M5 GUI/Agent delivery evidence remain indexed. R6's original-requirement
audit is complete; its seven-state checklist does not assert source completion.
No full A12/M6/V1 or release-
candidate recommendation: Windows, other input methods, VoiceOver/human and
independent installation/upgrade/publication gates remain explicit.

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

The stage notes below retain earlier baseline/specification and slice receipts.
Their old “next”, lock-screen and completion statements are historical, not the
current assignment. Use only the active brief above and V1_ACCEPTANCE_MATRIX.md
for current work; exact historical results remain in PROJECT_LOG.md and linked receipts.

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

At that earlier image continuation the Mac was locked; no bypass was attempted.
This is historical, not the current control state. Image probe r3 reached only its first real picker
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
probe failures and limits. The subsequent journal slice is described below;
explicit migration remains next. Preserve incomplete journals instead of deleting them to
enable writes. No in-place restore, cloud-availability guarantee, native/Windows
or power-loss acceptance is implied.
M3 still needs retained source versions and scalable previews. The latest user
request authorizes this source checkpoint only; it does not open release gates or
grant standing automatic-push permission.

Interrupted-write recovery reuses the existing bounded before/after journal,
strict metadata readers and checkpoint staging/publication. The user reviews each
changed file and chooses before/after/current with no default winner; combinations
must preserve a known loadable Block model and its matching generated source.
Unchanged selected files come from current disk, so this is not a full historical
snapshot. Output is exclusively published outside the original as project/, drafts/
and recovery-evidence/ containing all changed-file alternatives and decisions.
Confirmation rechecks input and window-draft identities; cancellation and failures
preserve originals and a late successful publication remains visible. It neither
clears the original pending journal nor grants compile authority. Focused and
actual offscreen/Cocoa before/after reopen/FINAL and final full regression pass.
See `v1-m4-write-recovery-verification-2026-09-11.md`.

The initial Cocoa product run crashed through AX selected-children enumeration.
On macOS 26 arm64 / Qt 6.11.1 / cocoa only, a temporary process-local replacement
returns nil for that single selector; it is installed before MainWindow UI creation
and checked for the observed Objective-C ABI. Repeated native tree reads and the
complete recovery probe then terminated normally. This explicitly degrades that
selection attribute, not all accessibility, and does not close full M6 AX/IME or
the earlier unrelated Qt crash. Reassess/remove it when the runtime changes.
Rollback is limited to this selector guard and constructor call; do not patch
installed Qt files, global accessibility settings or another app.

Read-only migration orientation has now exercised the old runner on disposable
legacy fixtures. `tools/probe_legacy_migration_gaps.py` reproduced original-file
replacement, a non-byte-exact backup, independent runs producing different IDs,
shared plan versions skipping an unapplied migrator, rewriting unknown future
formats, and successful output rejected by the real BlockStore loader. Receipt:
`/tmp/icstex-v1-m4-migration-orientation-r1.log`; exit 0 confirms defects, not a fix.
No application entry called MigrationRunner; that in-place API now refuses all
writes. The new core retains raw selected originals, builds a deterministic known
conversion, and uses the existing complete-model parser and checkpoint publisher.
Current ordinary/Block projects are copied byte-for-byte; unknown formats and
pending journals refuse. Focused, background synthetic triple FINAL and frozen
full regression pass. Receipt: `v1-m4-migration-core-verification-2026-09-11.md`.
The following GUI increment is under offscreen validation and must preview a
deterministic known-format conversion, validate the complete current Block model
in a NEW copy, and ask separately before switching. Reuse checkpoint capture and
exclusive publication, current serializers and existing open/close guards; no
new document format, in-place replace, silent cloud transfer or compile authority.
Test identical-input identity, unknown fields/versions, second-run behavior,
source races/cancellation/disk failure, original-byte retention and actual reopen/
FINAL. The prior frozen-source full regression is now terminal; migration can
proceed without invalidating that receipt. Directory migration of current ordinary/Block projects
must also use explicit selected-byte copying, not a move or implicit format upgrade.

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
