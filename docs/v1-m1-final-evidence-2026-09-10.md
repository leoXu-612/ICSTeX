# M1 actual FINAL evidence and read-only acceptance

Local source only. This follows the first-slice report
`v1-m0-m1-verification-2026-09-10.md`; it does not certify M2-M6 or any release.
Current suite results are recorded in `PROJECT_STATE.md` and `PROJECT_LOG.md`.

## Mechanism and ownership

`CompileManager` captures bounded known project inputs immediately before an
actual FINAL job and rechecks them after it. The previous successful FLS extends
the initial set; newly discovered recorder inputs cannot retroactively prove
pre-build bytes and therefore require a new compile. Missing/changed/unreadable
inputs leave evidence incomplete. The FINAL PDF itself is hashed before the
completion callback, and the check worker verifies that hash again.

The immutable result view binds actual job root, purpose, source revision,
dependency generation, engine, toolchain paths, build id, input observations,
outcome and PDF digest. It carries parsed errors and common reference/rerun
warnings rather than an unbounded mutable console log. Ordinary-source evidence
is accepted only through the existing manager-ownership check and kept in a
bounded per-window cache. An old CURRENT marker without actual evidence cannot
produce a PASS result.

The existing Block session now sends its model revision to the manager, receives
queued results on its Qt thread, and accepts each actual job once. A late older
result, duplicate notification or result delivered after close is ignored.
Block readiness additionally compares current model metadata and generated
source against disk; neither the last displayed PDF nor a hidden source tab's
state is used as proof. PREVIEW does not replace the retained FINAL evidence.

Block output is no longer inserted into the ordinary-source PDF state. Entering
Block mode clears an unrelated source PDF; background Block results do not
replace the source view. Current Block PDF display uses its own result identity
and explicitly asks for input checking. Ordinary export/SyncTeX actions are
disabled in Block mode until M5 connects the guarded Block delivery workflow.
This does not change the saved project format or introduce a universal session.
D010 remains Proposed.

## Actual local evidence

Final native probe:
`/tmp/icstex-v1-native-20260910-m1-final-r2/`.
App Python path/content SHA-256:
`4a4e58ca20356a22000d86a9a45fa81b0adf68566411368b68c85e1dd8a55116`.
The process exited 0 on macOS 26.6.1 arm64, Python 3.12.6, Cocoa.

- Ordinary Chinese-path multi-file fixture: real one-page FINAL, child citation
  navigation to line 4, saved/input/PDF/log/count checks PASS, and input changes
  invalidate the old report. Bounded coverage stays UNKNOWN; absent word target
  remains N/A.
- Real Block fixture: XeLaTeX one-page FINAL with matching model revision, stable
  known input observations and PDF digest. Exactly one completion notification.
  FINAL/PDF/log/model-generated checks PASS after the explicit compile.
- External Block metadata events invalidate the captured result. Editing a
  generated child without changing the model revision fails both generated-source
  consistency and FINAL readiness. Synthetic originals are restored and compared
  byte-for-byte. Checks themselves do not save, assemble, compile or upload.
- Both check presentations were exercised at 90/100/110/125/150% UI scale. Native
  images were inspected; this is not acceptance of the surrounding Block editor's
  known high-scale clipping or of IME/AX behavior.
- Core/GUI faults include changed/removed/newly recorded inputs, replaced PDF,
  stale log/revision/engine, PREVIEW isolation, failed later FINAL, duplicate and
  closed-session callbacks, two-window isolation, and stopping during the new
  pre-build capture without a late TeX process launch.

The final native run had no traceback, RuntimeError, RuntimeWarning, Qt table
out-of-bounds warning or IMK message. Other runs and platforms are not inferred
from that absence. Raw images/logs remain local because they include temporary
paths and unredacted application output.

## Boundaries for subsequent stages

- Before/after observations prove the sampled known input view, not an immutable
  whole-project build sandbox. M5 must compile/export against a frozen submission
  snapshot and revalidate delivery, including external mutation faults.
- Arbitrary TeX macro behavior and academic/IB compliance are not certified.
  User-editable word targets and optional check settings belong to M2 profiles;
  the unset target remains explicitly N/A until configured.
- Block save/assembly writers and their existing pending-save behavior are not
  replaced here. M2/M4 must complete close/conflict/draft recovery; M1 provides no
  direct overwrite shortcut for a model/disk discrepancy.
- Block's layout/inspector and top-level engine/navigation controls still need
  cohesive M2 work. Windows, IME, AX stress and human first-use acceptance remain
  separate from this source/native read-only slice.
- No commit, push, packaging, installation, signing or public activation occurred.
  The independent Beta installation-lifetime exclusion gate is unchanged.
