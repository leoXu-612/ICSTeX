# V1 M3: bounded read-only source status

Date: 2026-09-11 (Asia/Taipei). Local source only; M3 is not complete.

## Capability and limits

Block navigation's **来源** tab lists recorded paths, explicitly refreshed content
status and associated Blocks. Select a source to inspect the baseline/observed
SHA-256 and any same-content candidate. **定位所选关联 Block** uses existing session
selection; it does not edit tables, import, save, compile or update baselines.
The old **重新同步** action merely replaced the recorded digest; it did not merge
data and could hide source changes. It is removed from this read-only slice.
Technical repair still needs a separate diff/confirmation/CAS/Undo slice.

One active worker and one latest pending request bound explicit refreshes. Cancel,
source-record/project changes, session close and widget destruction discard late
results. Model refresh does not hash or scan files; Block-filter typing does not
rebuild source/layout panels. Dated results are observations: external changes
require another refresh. This is not a live or immutable project snapshot.

Core reuses SourceRecord, provenance IDs and the existing safe input opener/path
rules. Each batch has limits of 2,000 records, 2,000 enumerated entries, 64 MiB per
file and 256 MiB total reads. Growth detection may consume one sentinel byte before
rejecting the observation. Missing-source search runs once per batch, only for
same-extension CSV/XLSX; links, hidden/internal paths, build output and dependency
caches are excluded. Other missing formats, errors, instability, exceeded limits
and multiple candidates remain unknown. Matching content does not prove the
original file's identity, data authenticity or academic validity.

POSIX enumeration and input opening use no-follow directory descriptors.
Cancellation is cooperative, not a hard OS I/O deadline. Native Windows reparse
races, cloud-provider availability and arbitrary external replacement timing are
not accepted here. No project format, writer, MCP authority or release gate changes.

## Reproduction and tests

- Synthetic baseline probe `/tmp/icstex-v1-m3-source-boundary-red-r1.log` confirmed
  outside content read through a file link and `.git/config` hashing, both falsely
  returned as moved candidates. No real user data was used.
- Core red suite `/tmp/icstex-v1-m3-source-core-red-r2.log`, exit 1, reproduced
  unsafe paths, excluded candidates, ambiguity, invalid baselines and read-error
  failures; new bounded/cancel/batch APIs were not implemented yet.
- Additional checks cover directory-link replacement, FIFO refusal, stream cancel,
  file replacement/deletion, batch limits and the original path reappearing during
  search. That reappearance reproduced a false moved result before final recheck
  (`/tmp/icstex-v1-m3-source-races-red-r3.log`, exit 1). Earlier deletion fixtures
  were refined to inject changes during reading, not before safe open.
- Initial GUI fixture content was incomplete and correctly refused by the guarded
  writer. Using existing table/text content constructors corrected the fixture;
  this was not a source-status regression.
- Final focused command:

  ```bash
  QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest -v \
    tests.test_source_registry tests.test_source_status_gui \
    tests.test_block_console_integration tests.test_block_editor_targets
  ```

  82 tests passed in 2.311 seconds, exit 0. Receipt:
  `/tmp/icstex-v1-m3-source-focused-r2.log`. Tests cover no writes/compile, associated
  target mapping, one active/latest request, failure/cancel/close/destruction and
  stale project/record rejection. Fixtures explicitly dispose their own widgets.

## Final-source product evidence and regression

Frozen app Python path/content SHA-256:
`6c87ebcf98f88c87f1ae43a89ee79f34310ea69ee45fb4bcee3508fc4765e020`.

On macOS 26.6.1 arm64, an isolated offscreen probe generated four CSV sources and
tables, then externally changed/moved/deleted sources. Actual background checks
displayed `ok / changed / moved / missing`; navigation selected the changed
source's linked table. Every project file, source record and table stayed unchanged
by checking/navigation, with zero new Undo commands. Reloading preserved the
original baselines and table contents. The rendered panel was inspected, but it
is not a native screenshot or native stability acceptance.

Receipts: `/tmp/icstex-v1-m3-source-product-r3.log` (exit 0), and
`/tmp/icstex-v1-source-status-20260911-r3/{report.json,source-status-offscreen.png}`.
Probe r1 used a nonexistent SelectionManager.context accessor and failed; it was
corrected to the actual current accessor. R2 passed on the preceding layout; r3
verifies final column sizing/source identity. All artifacts remain local/synthetic.

Compileall and whitespace checks passed. Full verbose discovery passed 1,168 tests
in 477.939 seconds, exit 0, receipt `/tmp/icstex-v1-m3-source-suite-r1.log`.
Exec `70944` / PID `84015` are terminal. App hash was rechecked unchanged after
completion. No traceback, RuntimeError, RuntimeWarning, fatal Python failure or
test failure appeared. Elapsed time is not a universal performance/quality claim.

The last desktop observation requires manual Mac unlock; no bypass or native
acceptance is claimed. Font-alias/offscreen plugin warnings remain. M2 native
image/formula/IME, M3 native and ordinary-source citations/materials/technical
repair, M4/M5 recovery/frozen delivery and M6/platform/human checks remain open.
Beta installation/signing/distribution gates are unchanged. No staging, commit,
push, packaging, installed-app replacement or publication.

Suggested commit message only: `feat(blocks): add bounded read-only source status`.
