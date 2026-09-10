# M4 text-history safety and recovery: local verification

The previously reproduced manifest-path deletion and unchecked-content faults are
repaired within the existing single-source text-history workflow. This is not the
project-checkpoint GUI, automatic crash recovery, or complete M4 acceptance.

## Implemented boundary

`app/core/history.py` derives each new bucket from its source name and digest.
Manifest source/object paths are assertions, never authority to read or delete an
arbitrary path. Strict schema, IDs, membership, byte bounds, UTF-8 and SHA-256 are
checked before recovery. Known links are rejected before opening; POSIX directory
handles anchor object operations and observed identities are rechecked.

New writes use exclusive objects and staged manifest replacement under the existing
project lock. Retention checks owned candidates before publishing the new index
and removes only the derived objects whose observed identities still match.
Valid legacy buckets remain readable and are never automatically rewritten,
migrated or pruned. Distinct names and repeated same-content snapshots receive
distinct identities. A bad history record cannot turn a successful source save
into a failed source save; its warning and originals remain available.

GUI restoration only accepts a registered record for the selected source. It pauses
the prior save timer, shows file/time/digest and explicit unsaved-change semantics,
then rechecks source, editor revision, workspace, lifetime and history after
confirmation. Acceptance inserts one QTextCursor edit block, retaining Undo/Redo,
without scheduling Save or granting compilation. Cancel/refusal resumes only the
unchanged pre-existing save request; newer or closed work is not revived.

Core/GUI tests cover forged paths, digest changes, collisions, valid legacy reads,
links, replaced directories, failed publication, retention and confirmation changes
to content, target or window. The history panel reports unreadable metadata and
disables restoration rather than presenting it as an empty healthy history.

## Verification receipts

Final app Python path/content SHA-256:
`b2a8297c88089ac76925a8d55378b50d299694180bb7aa93641a263260392802`.
The hash covers sorted repository-relative app Python paths and bytes, each
separated by NUL, and was rechecked unchanged after the full regression.

- Required compileall passed. The tracked working diff passed `git diff --check`;
  staging all new files additionally reports trailing blank lines in
  `app/gui/blocks/source_status.py` and `tests/test_gui_material_usage.py`. These
  cosmetic lines are retained in the tested source, not silently called clean.
- History-focused discovery passed: `/tmp/icstex-v1-m4-history-focused-r5.log`.
- Final full verbose discovery passed, exit 0, exec `74919` / PID `15672` terminal:
  `/tmp/icstex-v1-m4-history-suite-r2.log`. Exact counts/timing are in the current
  state and project log. No test failure, traceback or Python runtime exception
  was found; offscreen/font messages are not native-platform acceptance.
- Final synthetic offscreen product probe r8 completed and wrote matching-source
  results under `/tmp/icstex-v1-history-restore-20260911-r8/`; log
  `/tmp/icstex-v1-m4-history-product-r8.log`. Actual confirmation and reopened FINAL
  screenshots were inspected. Cancel preserves all fixture bytes; altered valid
  UTF-8 history is refused; keyboard Undo/Redo restores both drafts; restore itself
  neither saves nor authorizes compilation. A separate explicit Save intentionally
  changes the synthetic source, followed by window reopen and explicit FINAL.
- The resulting one-page PDF contains `Recovered history` and the unchanged custom
  macro text. Its SHA-256 is
  `d1e9790b2448395adcd9f928bfa88ba33ba4208d3b2458c4971487fefa183040`.
  The inspected window shows saved/current FINAL, not a still-running build.
- The updated boundary probe on the final source records both prior unsafe
  observations as false and forged creation as refused, with the original source
  unchanged: `/tmp/icstex-v1-history-boundary-20260911-r3/result.json`.

The initial unsafe implementation and synthetic outside sentinel deletion are
preserved in the preceding checkpoint-core report. Red core and GUI regressions
failed before the repair; a final pre-open-link red test also failed before the
explicit leaf guard. The first full green run on app `cf83e36b` is superseded by
the final unchanged-source run above, not silently reused for the later guard.

Product-probe iteration limits are retained: r1 assumed a macOS message-box title
that Qt did not expose. The early successful workflow captured before PDF paint;
r3-r5 then undersampled thin glyphs with a stride-based pixel check despite visible
text. Full-pixel measurement and actual PDF text verification corrected the probe,
not the application renderer. Later capture waits for the coalesced workspace
FINAL label as well. The final r8 screenshots and PDF provide the accepted visible
evidence. Native message-box buttons remain the platform's Yes/No labels.

## Remaining limits and synchronization scope

New text-history indexes retain at most 40 entries, each at most 4 MiB UTF-8 text;
legacy metadata is bounded separately. Cleanup failures may leave unindexed old
objects, so this is not an unconditional total-disk quota. Text history does not
preserve original encoding/newline bytes; project-checkpoint core remains separate.
Moving a project may leave legacy absolute assertions invalid: originals are kept,
not automatically rebound. Arbitrary external writers can still race the final
check/syscall; no OS-wide compare-and-swap claim is made. Windows reparse races,
power loss, cloud storage, native IME/AX and broad usability remain unaccepted.
Some bounded history I/O remains synchronous. M4 GUI selection, actual source/Block
draft capture, reviewed new-directory restore and M5/M6 work are still outstanding.

The user explicitly requested the needed rename and source submission. The existing
`codex/v1-development` name already matches this work, so no further rename is
needed. This batch is a source-only checkpoint with `[skip ci]`; exact Git push
receipts belong in `PROJECT_STATE.md` and `PROJECT_LOG.md`. No package, installation,
version, release-branch, public feed, workflow, signing or publication change is
authorized by this synchronization.
