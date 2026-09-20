# M4 selected-file checkpoint core: local verification

This slice implements byte-exact checkpoint creation, full archive inspection and
verified restore into a NEW container directory. It is a core API, not yet a
user-facing checkpoint workflow or complete M4 recovery. Ordinary/Block GUI draft
capture, recovery review, migration guidance and native/platform acceptance remain.
The separate legacy-history audit below found a real existing unsafe path boundary.
This report preserves that checkpoint's evidence; the later bounded repair is
recorded in `v1-m4-history-safety-verification-2026-09-11.md`. M4 as a whole remains
incomplete at that stage because its project-checkpoint GUI and wider acceptance
were outstanding.

Later GUI capture/review evidence is in `v1-m4-checkpoint-gui-verification-2026-09-11.md`.
The core-stage limitations below describe this earlier receipt, not the latest UI.

## Scope and implementation

- `app/core/project_checkpoint.py`: explicit selected paths, content-addressed
  byte objects, a versioned manifest and separate UTF-8 draft objects. No Qt, MCP
  authority, source writes, compiler launch, network request or project switching.
- `tests/test_project_checkpoint.py`: byte roundtrips, adversarial manifests,
  source/staging changes, cancellation, I/O failure, publication races and a real
  subprocess killed during restore. Test files are disposable synthetic data.
- `tools/probe_project_checkpoint.py`: ordinary multi-file and Block fixtures,
  original-byte/draft verification, Block repository reload and separately explicit
  synthetic FINAL compilation of each restored copy. This is not GUI/native QA.
- `tools/probe_history_boundaries.py`: a temporary-data orientation probe of the
  old history implementation. Its zero exit means observations recorded, not passed
  safety acceptance. It is deliberately separate from the regression suite.

Each explicit creation retains one new user-selected output. There is no automatic
history growth, pruning, replacement, scheduled backup or cloud synchronization.
Older checkpoint files remain under the user's control; no deletion policy is
silently imposed. A checkpoint beside the project is not an independent backup.

Capture reads saved files as raw bytes, retaining encoding, BOMs, newline bytes,
empty files and unknown metadata without reserializing their contents. It freezes
the selection, reads every file twice, compares content hashes and observed file
identities, validates the staged archive, then checks every selected identity again
before exclusive file publication. This detects observed instability, not an OS
transaction against arbitrary external writers. Only selected files are covered;
new/unselected files and external TeX/font dependencies are not implied complete.

The archive is a bounded ZIP_STORED container, not application packaging. Its
manifest contains format/version, capture time, relative paths, sizes and SHA-256
identities. Draft objects have explicit IDs, kind and optional relative target;
they never replace their target's saved bytes. `block-state` is an opaque UTF-8
recovery payload at this core seam, not authority to load/apply an arbitrary model.
No student document format is converted and no existing Block format is changed.

Restore validates the whole archive before creating staging. It writes exclusively
under `.icstex-restore.incomplete-<id>`, reads files back, performs another complete
byte/identity verification, rejects unlisted entries, and rechecks the archive.
Only then is the staging directory atomically published without replacing an
existing target. The result contains `project/`, separate `drafts/` when present,
the manifest and an explanatory README. The README explicitly says an incomplete
directory is not accepted even when that file has already been written.

macOS uses the SDK-declared `renameatx_np(..., RENAME_EXCL)`; the actual local race
test confirms refusal even when an empty target appears immediately before rename.
Linux has a fail-closed `renameat2(RENAME_NOREPLACE)` branch; Windows uses its
no-replace rename behavior. Those platforms were not run here. Unsupported exclusive
publication fails rather than falling back to `replace`. POSIX input/restore writes
use no-follow directory descriptors. The Windows observed-link checks are not a
claim of race-proof native reparse-point handling.

The new module does not reuse the legacy absolute-path history manifest. It reuses
the established safe input opener and byte-preimage/exclusive-publication patterns.
The MCP permission model, Block writer, compile identity and release trust remain
unchanged. Existing pending Block write journals are not automatically recovered.

## Bounds and failure behavior

- 1–2,000 selected disk files; at most 200 separately supplied drafts.
- 64 MiB per disk file, 16 MiB per draft, 256 MiB combined logical content and
  4 MiB manifest. Limits count repeated references as logical restored content.
- Relative paths are at most 4,096 UTF-8 bytes and 32 components. Traversal,
  absolute/drive paths, known Windows device names, case/Unicode aliases, file vs
  directory collisions and links are refused. This is not full Windows acceptance.
- Git/VCS internals, environments, caches and personal `.icstex` histories are
  excluded. The `.icstex` exception is limited to selected Block metadata and the
  existing project profile. Content is not scanned to certify absence of secrets;
  selection remains explicit and nothing is uploaded.
- Duplicate/unknown archive members or JSON fields, unsupported archive versions,
  compressed/encrypted entries, bad/missing objects and digest/size mismatches fail.
  A hash is integrity evidence, not authentication or academic-data provenance.
- Cancel checks occur between reads/objects and before publication. Hard I/O and
  an individual filesystem write are not preemptible. No background worker is added
  by the core itself. GUI cancellation/ownership remains a separate implementation.
- Normal failure removes only owned staging where fd-safe cleanup is available.
  A replaced directory/file is preserved, not mistaken for this operation's output.
  Hard termination or unsupported cleanup may leave a clearly named incomplete
  artifact for explicit inspection. No original or existing destination is replaced.
- File data is flushed/fsynced before publication. This is not a tested power-loss,
  volume-loss, remote-filesystem or iCloud guarantee; permissions/ACLs/timestamps and
  arbitrary filesystem attributes are not backed up.

## Reproductions and verification receipts

Initial red discovery failed because the new core module did not exist. Once the
first implementation was present, three concrete race tests failed: an earlier
restored file could change before publication; a substituted archive could be
published; cleanup could remove a substituted directory. Ownership checks and final
byte rechecks now address all three. Receipt:
`/tmp/icstex-v1-m4-checkpoint-races-red-r1.log`. Its shell also ran `tail`, so the
shell exit was 0 even though the recorded unittest result was three failures.

A subsequent test reproduced an unlisted file being included in the restored tree.
Exact final inventory validation now refuses it. That red run actually exited 1:
`/tmp/icstex-v1-m4-checkpoint-core-r2.log` (19 tests, one failure).

Final app Python path/content SHA-256:

`71ff39885c237665a25cf801947aa20dc58194b489c8ab7283a5a67e7d4ea933`

Commands and current results:

- `python3 -m compileall -q app tests packaging/install_build_dependencies.py`:
  exit 0.
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p test_project_checkpoint.py -v`:
  25 tests, 0.139 seconds, exit 0; no skips on this Mac.
  `/tmp/icstex-v1-m4-checkpoint-focused-r5.log`.
- `python3 tools/probe_project_checkpoint.py --output /tmp/icstex-v1-checkpoint-20260911-r3`:
  exit 0, exec `59850` terminal. `/tmp/icstex-v1-m4-checkpoint-probe-r3.log` and
  the retained directory's `result.json` contain source identity and artifacts.
- Required full verbose discovery passed on this final app tree: 1,289 tests,
  366.453 seconds, exit 0. Exec `1766` / PID `10802` are terminal; receipt
  `/tmp/icstex-v1-m4-checkpoint-suite-r2.log`. The app hash was rechecked unchanged
  after completion. No failed tests or Python exceptions/RuntimeWarnings were found;
  existing offscreen/font warnings remain separate from native acceptance.
- `git diff --check`: exit 0. Git index remains empty, HEAD/upstream remain
  `e5cd13273ee6de326bc629e65c0752a9f474848e`, and the held candidate feed digest is
  unchanged. No version, workflow, packaging, website or Beta-brief edits were made.
- Earlier full r1 was explicitly stopped before the final README clarification:
  exec `72702` / PID `10326`, terminal exit 143. It is not final-source acceptance
  or an unexplained application crash. Earlier core/probe receipts are superseded.

Environment: Python 3.12.6, macOS 26.6.1 arm64, local filesystem. At full-run start,
load averages were 1.84/1.80/2.03 and swap use was about 8,832 MiB. Small synthetic
capture/restore timings are observations only, not a large-project performance claim.

The final filesystem probe covers a six-file ordinary project and a nine-file
Block project, including Chinese paths, GBK/CRLF bytes, an empty bibliography,
images, Block metadata/generated source and 2/3 separate drafts. Every selected
original/restored byte and draft payload matches. Both restored projects compile
through a separately invoked FINAL; original inputs remain unchanged afterward.
The Block repository reload matches original registry/layout. No GUI screenshot or
native interaction is claimed; the previous Mac-unlock boundary remains.
The actual FINAL PDF SHA-256 values are
`1f30c9c938efbfe6f47ccadf8e1a166042991e003b7effa57fb9a59fccc59582`
(ordinary) and `c76cdc98500b5d180b2f6bc6eee3ac2434956486f994fd1dbe0a2148377c20d6`
(Block). These are the real generated artifacts, not a byte-reproducibility promise.

## Legacy history audit: unresolved, next bounded repair

The synthetic orientation probe confirms two pre-existing faults in `history.py`:
valid UTF-8 tampering is returned without verifying the recorded digest, and a
forged manifest's absolute `snapshot_path` is followed by retention pruning, deleting
a sentinel outside the synthetic project. The original synthetic source remains
unchanged. This is a real unsafe path boundary, not merely a theoretical concern.

Receipt: `/tmp/icstex-v1-m4-history-boundary-orientation-r1.log` and
`/tmp/icstex-v1-history-boundary-20260911-r1/result.json`, exit 0 for reproduction.
The unchanged legacy module SHA-256 is
`1116245126e6a4b4b12e88c691e66e8bf516318581c17c7f2bbedcbb96670e4a`.
Inspection also confirms `InsertionActions.restore_history_snapshot` reads a path
directly after confirmation instead of using a bounded, owned, hash-checked record.

Next repair must bind old history reads/deletes to the expected source bucket,
refuse untrusted paths/links and content mismatches, preserve existing valid history,
and check current editor ownership through the confirmation flow. Do not reuse the
old path trust or convert it into automatic project restore. After that bounded
repair, connect explicit checkpoint selection, captured source/Block drafts, preview,
cancel/close guards and restore-to-new-directory review in the existing UI seams.

No Git staging/commit/push/branch mutation, application package, installed-app
replacement, credential access, CI, website, signing or release change occurred.
The independent Beta installation-lifetime gate and all earlier shared edits remain.

Suggested later commit message, only with separate authorization:
`feat: add byte-exact project checkpoint and restore core`.
