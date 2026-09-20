# M5 delivery audit and next bounded implementation

Status: five export gaps were reproduced at the historical source hash below.
Later GUI/standalone Block entry replacement passes expanded and real offscreen/
native checks and its frozen 1421-test full regression; see
`v1-m5-delivery-gui-verification-2026-09-11.md`. The subsequent Agent/MCP repairs
and newly found shared FINAL cache defect are tracked in
`v1-m5-agent-export-verification-2026-09-11.md`. No M5 completion or release claim.
This original audit ran while M4 GUI's app/tests were frozen for full regression.
It changed only synthetic projects, a probe and documentation. Its GUI driver
expects the retired save-dialog route; do not rerun it blindly against the new
modal preparation workflow. Its Agent private copy/compiler seams also changed;
use the new acceptance probe rather than blindly rerunning the old defect driver.
Original observations below are retained as evidence for the stated old source.

## Evidence

```bash
QT_QPA_PLATFORM=offscreen python3 tools/probe_submission_delivery_gaps.py --output /tmp/icstex-v1-m5-export-gaps-20260911-r1
```

Exit 0 / exec 50142 terminal means the probe observed all five defects it asserts;
it is NOT an acceptance test. Log `/tmp/icstex-v1-m5-export-gaps-r1.log`, full result
`/tmp/icstex-v1-m5-export-gaps-20260911-r1/result.json`.
App SHA-256 `d9756e68f9336be479fe4c59ec6955ff0ac0191dad468a42575e6687d34d007f`
matched before and after. Same macOS/Python/Qt environment as the migration GUI
report; offscreen widgets only, no native picker/desktop focus or physical input.

| Gap | Actual reproduction | Current mechanism |
| --- | --- | --- |
| Stale PDF before watcher delivery | A real ordinary MainWindow compiled a synthetic multi-file project to FINAL. Its child then changed with original mtime retained. Before processing queued watcher events, actual `window.export_pdf()` accepted and copied the old PDF. | PdfExportController checks cached PdfBuildRecord freshness/revision, not current dependency bytes or FinalBuildEvidence during atomic copy. Flushing only considers open dirty tabs. |
| Implicit sensitive/unselected files | Synthetic `signing.pem`, `id_ed25519`, `.venv/cache.txt` all appeared in portable output. Contents were obvious non-secret placeholders, not real keys. | Block export recursively selects allowed-looking files without an inclusion review. Its directory/name exclusions do not cover these cases. |
| Source README overwritten | Exported manifest's README hash did not match the exported README bytes. | export_package hashes copied user README.md, then overwrites the same path with generated instructions. |
| Previous delivery altered on failure | Injected disk-full after first copy left new a.tex beside the old manifest in an existing target. | Files are copied directly into an existing destination before completion, with no isolated publication. |
| Mixed-version source package | Source a/b changed after a was copied; export succeeded with old a and new b. | Per-file destination hashes do not verify one stable source version across the operation. |

The stale exported PDF SHA-256 was
`70a43a69b8d61deb0733939f5ad6ae788d96fae9a190dde4c55e2f7650a259d2`.
This proves a pre-notification export gap, not general watcher failure. Portable
faults are actual core exports with controlled copy-boundary faults; the Block
GUI call to that exporter was inspected, not separately driven by this probe.

Relevant seams:

- `app/gui/main_window.py`: source destination selection -> `pdf_export.request_export`.
- `app/gui/pdf_export_controller.py`: current/PREVIEW/FINAL and pending-build guards,
  then `_copy_atomic`; no content identity recheck at publication.
- `app/gui/document_lifecycle.py`: `flush_root_documents` handles owned open buffers;
  not a complete reread of every on-disk dependency.
- `app/core/blocks/export_package.py` and `app/gui/blocks/workspace_widget.py`:
  recursive portable copying and the direct Block export entry.
- `app/core/build_evidence.py`: actual build job/purpose/input/PDF observations.
- `app/core/submission_check.py` and its GUI controller: identified read-only report,
  saved state, profile and word-count mode; not export authorization by itself.
- `app/core/project_checkpoint.py`: selected-byte reads and safe staged publication;
  checkpoint payloads/drafts are not a submission package or complete dependency proof.

The later core preparation/publication increment is now under validation in
`app/core/submission_delivery.py`. That does not yet repair the original callers.
Additional caller found during implementation: `app/core/agent_workspace.py`
`_export_artifact_locked` calls the portable exporter inside an already-created
temporary directory, then renames it to the authorized export target. Preserve
its wire shape, capability gates, project lock and GUI/MCP exclusion while fixing
content/publication guarantees. The standalone Block dialog is another GUI caller;
do not assume every workspace has a MainWindow parent.

## Slice contract (core started; actual entrances still pending)

User task: explicitly prepare a submission from a saved, current successful FINAL,
review included files and unresolved checks, then create a new local delivery.
Default output is only the selected formal PDF. Source bundle and report are
separate opt-ins. No upload, autosave-as-consent, student rewriting or application
packaging. Preparation must work for ordinary LaTeX and saved Block projects.

Reuse the actual FINAL evidence and existing protected save/build commands. Add a
focused pure frozen-delivery model and publisher, then the minimum GUI coordinator.
Do not promote D010 or replace preview/compiler/session architecture. Bind the
saved byte selection, required dependencies, root/revision, job/build/purpose,
engine/tool identity, profile, count mode/target, check identity and output PDF.
Re-read content before acceptance and before final publication; cached freshness,
mtime and a cooperative GUI pause are insufficient. PREVIEW/failed/stale/unknown
FINAL evidence must never authorize formal output. Cancellation/conflict preserves
the previous delivery and original project, including independent drafts.

Keep source bytes exact and source files usable without ICSTeX. Display inclusion
selection and unresolved dependencies; exclude private-key/token material, logs,
Git internals, environments, caches, personal history and unselected files. Do not
silently add every checkpoint metadata/draft path to a submission source bundle.
Stage generated reports/instructions outside the source tree so README or manifest
names cannot overwrite selected user files. Report only relative paths and explicit
version/tool/input/output/check evidence plus unconfirmed items, not local absolute
user paths or a claim of academic correctness. State external fonts/toolchain limits.

The existing direct PDF and Block portable export entries must share the new
invariants or safely route to the reviewed workflow; adding a safe new button while
leaving these accepted-output paths unsafe does not close the reproduced gaps.
Do not silently break compatibility or implement only a generic archive utility.

Acceptance (the frozen M4 run has now ended successfully):

1. Turn each reproduced gap into a focused failing regression for its actual seam,
   then implement content binding, explicit selection and staged publication.
2. Cover child/image/profile/PDF mutation with same mtime; changes during capture,
   copy and confirmation; malicious paths/links; unknown evidence; cancel, occupied
   targets and simulated partial writes. Originals and previous deliveries stay exact.
3. Drive actual preparation UI from saved/unsaved/stale/preview states, explicit
   save/FINAL where needed, PDF-only default and independent source/report opt-ins.
4. Run ordinary single/multi-file and Block create/check/FINAL/deliver/reopen/restore
   synthetic flows, and compile selected ordinary source outside ICSTeX. Inspect
   actual exported PDF and report/source contents; do not infer delivery from a hash.
5. Required focused, compileall, frozen full and diff checks, source hashes and
   documented failures. Current native GUI receipts are in the later GUI report;
   full IME/AX and Windows remain separately unverified. The earlier background-only
   restriction has since been explicitly lifted.

## AgentWorkspace follow-up on the GUI-verified source

```bash
nice -n 10 python3 tools/probe_agent_delivery_gaps.py --output /tmp/icstex-v1-m5-agent-export-gaps-20260911-r1
```

Exec 5817 terminal, exit 0: all five defect assertions held. This is NOT repair or
acceptance. Log `/tmp/icstex-v1-m5-agent-export-gaps-r1.log`; result
`/tmp/icstex-v1-m5-agent-export-gaps-20260911-r1/result.json`, SHA-256
`2630e89095fd3032a251ad2c8679cf526792a9e2e9de9df28d8bd02a4dd05aa2`.
Probe SHA-256 `34533fc4406c72b3ae0e556035be0de7972b88df3b6f05388bc4a607b26b974b`.
App SHA-256 `b5bce3681839b945d31aad3852554fff460e0d336a89605ee3f6fc02fd782fcd`
matched before/after. Only synthetic temporary files and tool/docs edits; no GUI.

Actual `AgentWorkspace.export_artifact` calls, retaining its real project lock and
export-root/compile grants, demonstrated:

- A real successful FINAL followed by a same-size/same-mtime child edit inside a
  controlled post-compile hook still exported the old PDF. Its SHA-256 was
  `d4b47f1e6c4e8c42aa1560d158b0d135b91f560a5507fad5235466416a5b2835`.
  `_compile_project_run` currently reduces CompileResult to the wire dictionary;
  the export path then copies without using current input/PDF evidence.
- A synthetic prior PDF created after the initial target-absence check, just at
  `_atomic_copy` entry, was overwritten. The current final `os.replace` is not
  no-overwrite publication. This is a controlled boundary fault, not a claim of
  testing every OS race or filesystem.
- The real package caller's already-created empty staging directory is accepted;
  `signing.pem`, `id_ed25519` and `.venv/cache.txt` synthetic placeholders appear
  in the published result. No real key material was read.
- Actual returned manifest disagrees with the overwritten source README bytes.
- Changing source a/b after copying a produces a published package with old a and
  new b. The caller's outer staging does not establish a consistent source version.

This probe does not traverse stdio MCP transport and is not new protocol/auth
acceptance. The caller's outer staging already separates intermediate copy failure
from its final target; do not misreport the direct legacy copier's partial-output
defect as a proven overwrite of an existing nonempty AgentWorkspace directory.
Preserve wire fields, grants, lock/stop coordination and existing empty-stage
compatibility while closing these concrete content and publication gaps.

No commits, pushes, application builds, signing, installation changes or release.
