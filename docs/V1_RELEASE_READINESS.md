# V1 release readiness — historical stage snapshot (2026-09-12)

> This is a frozen stage record, not the current work queue. Use
> [PROJECT_STATE.md](PROJECT_STATE.md) for current source/installed/published state
> and [BETA3_DELIVERY.md](BETA3_DELIVERY.md) for the later Beta 3 update delivery.
> Beta 3 packaging, online distribution and installation-guard acceptance occurred
> after this snapshot; do not reopen them solely because the old rows below say pending.
> This does not waive the separately unverified V1, native-platform or student-trial scope.

Updated: 2026-09-12. **Local source acceptance is incomplete; no release-candidate
recommendation is made.** The original-requirement closeout audit is complete;
R2a–c keyboard evidence, R3 reliability disposition and R5's unverified support scope
remain open. This checklist separates the seven states required by
[the development instructions](CODEX_V1_DEVELOPMENT_INSTRUCTIONS.md). It does not
authorize packaging, signing, installation, publication or Git changes.

The user explicitly prioritized ordinary Mac writing on 2026-09-12 and deferred
Agent/MCP restricted Biber support. The [source handoff](MAC_WRITING_HANDOFF.md)
does not depend on that deferred feature. R2/R3 and the release gates below are
not waived; this is not a stable-build or complete-V1 acceptance statement.
The user subsequently confirmed closing the Goal as a Mac source stage handoff,
with incomplete acceptance deferred. That stage is complete under the adjusted
scope; the original acceptance and release checklist below remains open.

## Tested source identity

- Branch: `codex/v1-development`; HEAD:
  `3bde2b5d25803262dedef89a081ee6ffbe2b6967`.
- Application Python tree SHA-256:
  `7009463b6f091f8d58f46fcfee3e08b03b3535fe9d89b0882ac7d3a133e87506`.
- Application plus tests Python tree SHA-256:
  `14093898a54aa926b992b20106c570c1d2f6a5899af2ab35b69c157b1467cbc4`.
- Tree digest: sorted repository-relative `*.py` paths, each followed by NUL,
  file bytes and NUL. It is not an archive or installed-application identity.
- The latest Mac restricted-compiler increment is recorded in the
  [integration receipt](v1-m6-macos-sandbox-integration-2026-09-12.md).
  Its single final full gate passed (1598 / 313.187s / OK, terminal exit 0),
  with post-terminal matching hashes, compileall and diff checks. Previous window
  receipts retain their own source and are not relabelled as newer native runs.
  [Keyboard follow-up](v1-m6-recovery-migration-keyboard-verification-2026-09-12.md)
  records the standalone tab-bar repair, native 100%/150% entry, 150% delivery/
  recovery controls, legacy-copy publication and remaining window/menu evidence.
- Read-only remote verification on 2026-09-11 found the development branch at
  the same HEAD and `release/2.1` at
  `f03776e87c0f938421a70ff5b085db920f2d01d7`. Subsequent worktree changes are
  **uncommitted and not pushed**; the index is empty. Matching HEADs do not mean
  this tested tree is present on GitHub.

At this snapshot the application version was `2.1.0-beta.2`. “V1” is the development work
name, not a new public version or permission to relabel an older artifact.
Historical product receipts retain their own source identities; a newer full
unit pass does not turn them into newer native runs.

## Seven separate acceptance states at the snapshot date

| State | Verified position | What prevents closure |
| --- | --- | --- |
| 1. Source completion | M0/M1 verified; M2–M5 implementations and bounded product evidence exist. M6 includes input, source identity, export integrity, lifetime repairs and the tested restricted Mac LuaLaTeX/BibTeX chain. | Applicable local acceptance remains open: R2a–c OS/menu keyboard proof and R3 reliability disposition; R5 auxiliary-tool/backend support limits remain explicit. No claim that all M1–M6 requirements pass. |
| 2. Platform acceptance | macOS source has distinct offscreen, Qt-driven Cocoa and physical-input receipts; tested Pinyin, source/Inspector, navigation, console and PDF cases have bounded results. | Audited modal workflow/destination-picker evidence and AX limits; matching Windows path/font/IME/clipboard/scale/locking/engine tests E1. No platform scope reduction inferred. |
| 3. Artifact generation | No artifact was built for the current V1 worktree. The independent Beta r2 candidate is identified in the held handoff. | Maintainer version/platform selection, explicit packaging authority, preflight and a new source-bound build. Never rename the old r2 archive to represent this tree. |
| 4. Signing and notarization | No signing or notarization was performed for this tree. Historical r2 has ad-hoc application signing and verified Ed25519 update bytes, not Developer ID or notarization. | Separately authorized signing identities, inspected exact artifact and any required notarization. Do not repeat or export the existing Keychain key. |
| 5. Install and upgrade verification | Historical isolated r2 upgrade/cold-launch/manual-bundle-recovery evidence exists; it is not current-source installation acceptance. | Installation-lifetime exclusion, late instances and forced interruption remain open, as do relevant platform gates. A process scan is not an installation lock; manual recovery is not automatic rollback. |
| 6. Online distribution | No current-worktree asset or feed was published by this task. The signed candidate feed remains local and outside the website deployment tree. | Source acceptance plus separate publication authority and actual immutable asset/feed HTTPS verification. Historical public-state snapshots are not refreshed production acceptance. |
| 7. Real-user acceptance | No student participants, completion rates or usability results are asserted. | Maintainer-arranged student tasks and accessibility/VoiceOver evaluation E3, with actual help required and observed outcomes. Synthetic fixtures are not participants. |

The authoritative implementation-to-evidence mapping and finite IDs are in
[V1_ACCEPTANCE_MATRIX.md](V1_ACCEPTANCE_MATRIX.md); current capabilities and
limits are in [PROJECT_STATE.md](PROJECT_STATE.md). The independent
[Beta activation handoff](BETA_ACTIVATION_HANDOFF.md) retains its own artifact,
trust and installation gates. Its older remote/deployment facts are historical
snapshots, not live observations made for this checklist.

## Historical remaining decisions and evidence (not a current task queue)

- **R2 — finite modal keyboard workflows:** the [closeout audit](v1-local-closeout-audit-2026-09-12.md)
  identifies creation/profile, delivery, checkpoint/restore and distinct
  Block/migration controls, including real destination selection. The
  [modal receipt](v1-m6-modal-keyboard-verification-2026-09-12.md) now adds actual
  creation/profile 100%/150%, ordinary PDF-only delivery and separate-draft
  recovery/new-window results. Focused five-tier RecoveryDraftDialog and
  post-migration traversal now pass in the
  [follow-up receipt](v1-m6-recovery-migration-keyboard-verification-2026-09-12.md).
  Unlock was confirmed and native r5/r6 completed. Standalone Block tab-bar
  repair, actual 100%/150% delivery entry, 150% FINAL/review/cancel and checkpoint/
  recovery controls, plus legacy publication at 100%/150%, now have evidence.
  Native r2 proved that the confirmed copy was visible/alive but inactive behind
  its original owner. Post-modal raise/activation now passes focused red/green
  and native r3, while cancellation requests no activation. The original and
  copied bytes remain unchanged; no implicit compile. See the
  [window receipt](v1-m6-migration-window-verification-2026-09-12.md).
  All window probes are terminal; the initially locked r1 remains interrupted,
  not passed. OS/menu keyboard-only evidence still needs a usable control route
  or human check; repeated CUA key routing is not product failure evidence.
  Native pickers in r6 used keyboard without AX value correction;
  AX menu entry still is not pure keyboard proof. The following
  tested navigation/console/PDF cases need not be restarted. Unlock was confirmed and actual Cocoa
  input resumed. Citation traversal/Space child navigation, focus scrolling and
  rail arrows/scaling have bounded evidence; final-source r6 confirms the
  repaired toolbar ↔ rail ↔ panel sequence and 100%/150% Locate. r5's five-tier
  and nine-tool observations retain their own source identity.
  [Native navigation receipt](v1-m6-native-navigation-verification-2026-09-12.md).
  Four read-only Return/Enter location routes pass offscreen product tests;
  actual outline/search and subsequent error/diagnostic Return paths now have
  source-identified native evidence. The initially clipped diagnostic table is
  now repaired: five scales pass offscreen, native 100%/150% keyboard targets
  and collapse/expand pass without dragging. Word Count/Submission Check now
  pass five-tier long-text tests and native 100%/150% refresh, result/detail
  endpoints and reverse focus, with no next-step action or compilation. The
  separate 200% native synthetic PDF sample is readable without
  obvious blocky pixelation; not all fonts/HiDPI/zoom or a new FINAL claim.
  Those runs exited 0 and destroyed their windows.
  [Console/PDF follow-up](v1-m6-console-pdf-native-verification-2026-09-12.md).
  [Console layout repair](v1-m6-console-layout-verification-2026-09-12.md).
  [Reading console repair](v1-m6-reading-console-verification-2026-09-12.md).
  PDF disabled-menu/focus, pane overlap, effective-fit zoom/page drift and
  Fit Page bottom clipping now have bounded repairs. Actual More selection and
  final-source 100%/150% whole-page display are observed. The original-requirement
  audit is complete; only OS/menu keyboard evidence remains open for R2.
  Do not replay completed modal controls or start an open-ended coverage sweep.
  [PDF geometry receipt](v1-m6-pdf-geometry-verification-2026-09-12.md). Do not
  repeat closed R1/default-save/Inspector cases; announce and close new QA.
- **R3 — reliability:** retain the scoped AX guard and historical unresolved
  timer/stylesheet attribution. Bounded fixes have evidence; neither unrelated
  green tests nor repeated full suites prove a historical crash cause. The
  native 200% sample is now readable, but the earlier offscreen pixelation cause
  is not established and no renderer change was made.
- **R5 — restricted MCP engine:** the D021-authorized [Mac source integration](v1-m6-macos-sandbox-integration-2026-09-12.md)
  now compiles Chinese/math/BibTeX through actual latexmk/LuaLaTeX. Staged stdio
  export, final-application denial controls and actual process-tree stop pass.
  Missing/failed isolation refuses compilation; ordinary GUI policy is unchanged.
  A subsequent [Biber check](v1-m6-macos-biber-boundary-2026-09-12.md) now proves
  bootstrap failure under the exact executable policy: xcode-select/lipo and
  extracted native runtime need a bounded design, not a new installation.
  The user has deferred this Biber feature in favor of the ordinary Mac GUI.
  Restricted preparation/read-only-runtime integration is not an active approval
  blocker for that handoff and is not authorized for implementation.
  Other toolchain layouts and macOS/TeX versions remain unverified.
  The deprecated command/private profile dependency is not a shipping contract.
  Earlier research still rejects safer mode and upgrade-only as fixes.
  [Read-only name-policy checks](v1-m6-lualatex-policy-review-2026-09-11.md)
  exclude redirecting Lua cache roots to the distribution as a read-only fix:
  those overrides also admit output names. No actual write was attempted.
- **E1–E4 — external gates:** matching Windows, real cloud/volume/power failures,
  human evaluation and release work remain explicit. Listing external gaps is
  not a substitute for completing still-applicable local acceptance.

R6's audit and finite-gap handoff are complete, not local source acceptance. A final local
source-completion statement requires the original stopping conditions: M1–M6
implementation, applicable acceptance, no unclosed introduced data-corruption,
wrong-export or permission regression, accurate current documentation and
explicit external gaps. Only then may the local-source and formal-release
states be reported separately as complete and pending, respectively.
