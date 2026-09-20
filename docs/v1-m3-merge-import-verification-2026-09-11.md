# V1 M3: merge candidate preservation and import fidelity

Date: 2026-09-11 (Asia/Taipei). Local source preparation, not complete linked-source repair.

## Scope and actual behavior

The existing three-way merge and its dialog now produce independent candidates.
Resolving multiple cells in one row preserves sibling cells, row order, sparse cell
absence, value types, explicit empty text and manual whitespace. Base/Remote/Local
inputs and the original MergeResult are not mutated. A new result cannot share
mutable rows, notes or merge arrays with those inputs. Duplicate row/column IDs or
unknown cell columns are refused before merging.

Remote-only changes preserve the complete remote table, including row deletion,
column attributes, headers, notes, merge regions and table identity; local-only or
identical changes preserve local. Concurrent cell edits can merge independently
when structure matches; independent appended rows also remain supported. When both
sides change and row/column structure, ordering or table metadata differ, the result
retains local and records an explicit whole-table conflict. The user must compare
the complete Base/Remote/Local alternatives and choose a whole table. It does not
guess row identity, silently resurrect deleted rows or combine structural edits
by position. An explicit whole-table choice does not combine the unchosen side;
the dialog says so and preserves both original inputs outside the candidate.

The dialog is named **合并候选预览（不应用）**. Changes to choices invalidate the
candidate. **更新差异预览** displays the full candidate and original conflict values;
only a fresh complete preview enables **确认候选（未应用）**. Cancel returns no new
candidate and leaves the inputs intact. Dynamic label text is plain text. JSON
previews are currently a technical inspection surface, not a finished student-facing
source-repair workflow. The dialog caps conflict controls at 200 and each preview
at 262,144 characters; incomplete previews cannot be confirmed. High-scale content
scrolls while preview/confirmation controls stay outside the scroll area.

The old workspace conflict button no longer says that table synchronization is
complete after merely accepting a dialog. Without an injected comparison it is
disabled with an explanation; confirmation is labelled as a candidate not yet
applied or saved. It still does not create a source comparison or push a
ProjectSession command. This slice deliberately does not claim real source-to-table
application, baseline advancement, target/source CAS or Undo integration.

## Import defects and bounded changes

CSV and XLSX adapters no longer return a truncated table when configured/default
row or column limits are exceeded. Defaults remain 5,000 body rows, 200 columns and
200 MiB source bytes; an optional header is separate from the body-row budget.
Selected XLSX ranges are checked by their dimensions, not by clipping absolute
end coordinates. Invalid row zero and ranges that cut through a merged region are
refused. Fully outside merge regions are excluded; contained regions are translated
to the selected range. CSV blank rows and values beyond a short header are retained.
Extra unnamed columns receive the existing generated column-name convention.

New imports now put the actual header in `row_000`, followed by the unchanged
`row_001` body-ID convention. Column labels alone are not rendered table headers:
the prior adapter discarded this row while the renderer treated the first data row
as the header. The fix follows the existing TableData/renderer contract; numeric
column validation allows header text but still warns on nonnumeric body text.
XLSX merge coordinates now follow `[first row, last row, first column, last column]`.
Existing persisted tables are not migrated or overwritten. Imported IDs remain
positional, not stable data keys; source mapping still needs explicit verification.

XLSX data and merge XML are read from the same captured workbook bytes, not separate
reads of a path that could change between them. The adapter bounds the compressed
read, compares observed descriptor size/time before and after capture, limits archive
members to 10,000 and declared expanded bytes to the source-byte limit, disables
external-link preservation, and exposes close/context-manager support. This is not
project-path authorization, cancellation, a frozen source-to-apply transaction or a
hard OS I/O deadline. Future GUI import must use the established authorized safe
input capture and recheck the source identity before application. The existing
CSV/XLSX type inference is not a byte-preserving data conversion; original source
bytes remain authoritative and must remain untouched.

## Red tests and focused regression

The previous memory-only probe confirmed that accepting one conflict deleted a
sibling cell. New tests additionally reproduced independent-input aliasing, lost
row deletions/metadata, unreported structural conflicts, sparse-cell loss, duplicate
identity acceptance, CSV truncation and short-header data loss. Initial receipt:
`/tmp/icstex-v1-m3-merge-import-red-r1.log` (25 tests, six failures, seven errors).
R2 added actual dialog and XLSX range checks; missing preview/context APIs and the
old dialog still failed. These are red evidence, not acceptance.

Two additional red tests reproduced omitted rendered headers and transposed XLSX
merge coordinates in `/tmp/icstex-v1-m3-import-fidelity-red-r1.log`. The numeric
body-warning test originally relied on the model's default one-header-row setting
while treating its only row as body. It now explicitly declares no header; another
test separately verifies allowed header text and rejected body text. The assertion
that invalid body data is diagnosed remains intact.

Final focused integration passed 113 tests in 4.720 seconds, exit 0, exec `23133` terminal:
`/tmp/icstex-v1-m3-merge-import-focused-r5.log`. It includes source merge, table import,
model/renderer, Block GUI/console integration, source status and the new visual
preview-control regression. Earlier focused r2/r3 each retained the old ambiguous
numeric-header assertion and failed; they are not the accepted result.

Frozen app Python path/content SHA-256:
`39f26a52093da449f06ddf32bf5610808b1e126616298c6a96b3abdb042c6cee`.
Compileall and whitespace checks passed. The preceding app tree
`35ac51334b10fb644497de670b3a01b6a03058dd61b7c9844759e862019ccec4`
passed 1,242 full tests in 363.395 seconds, exit 0, exec `51161` / PID `99944`
terminal, receipt `/tmp/icstex-v1-m3-merge-import-suite-r1.log`. A final red test
then showed that whole-table previews omitted the in-memory table identity;
`/tmp/icstex-v1-m3-merge-preview-identity-red-r1.log`. All previews now show that
identity and the cancel button is explicitly Chinese. Final full discovery passed
1,242 tests in 360.894 seconds, exit 0, on the new app tree. Exec `96245` / PID `1534`
are terminal; receipt `/tmp/icstex-v1-m3-merge-import-suite-r2.log`. The app hash was
rechecked unchanged after completion. No failed test, traceback, RuntimeError,
RuntimeWarning or fatal Python failure appeared. Offscreen/font warnings remain
separate from native acceptance; the earlier pass was not substituted for this run.

## Actual dialog and real FINAL

```bash
QT_QPA_PLATFORM=offscreen python3 tools/probe_source_merge.py \
  --output /tmp/icstex-v1-merge-import-20260911-r4
```

Final-source run exited 0, exec `36337` terminal, receipt
`/tmp/icstex-v1-m3-merge-import-product-r4.log`. Environment: macOS 26.6.1 arm64,
Python 3.12.6, Qt offscreen. The real dialog received mouse/key events, selected a
remote numeric cell and a manually edited second conflict in the same row, required
a fresh preview and returned an independent candidate. Sibling key/False values,
all row IDs, exact manual spaces and all three original models were preserved.
A second real dialog cancellation did not apply its preview.

Five UI scale settings rendered a 760x640 dialog; preview/confirmation control
centers remained reachable. The 150% capture was visually inspected: conflict
details require scrolling, JSON remains technical, and the table identity plus
Chinese cancellation are visible. This is not full student usability, IME/AX/native or narrow-screen
acceptance. Probe r1/r2 clicked the empty center portion of a wide radio widget,
leaving the original selection unchanged; both reached a failing result assertion.
R3 clicks the actual indicator and asserts selection immediately; r4 repeats it on
the final app tree. This was a probe interaction correction, not a silently accepted failed choice.

The script separately imports a real synthetic XLSX, verifies the header and both
body rows, and refuses oversize CSV. It then explicitly writes a disposable LaTeX
fixture from the candidate and imported table and triggers the ordinary MainWindow
FINAL action. This fixture generation is not source-link application. The actual
one-page pdfLaTeX PDF contains Key/Value/Note/Flag, A=11, B=21, reviewed note,
false/true, and the imported Quantity header with both 20/30 body rows. Extracted
text and the rendered page were inspected. Fixture source bytes stayed unchanged
by compilation. PDF SHA-256:
`7fc0a9d6e7a711b2a63e6c5101c3b080f6e740ddd565e5a2bc903ea86e2b0ad0`.
Report, captures, original synthetic XLSX and PDF remain under the evidence directory.

## Next integration and open gates

SourceRecord's existing schema has a source path/hash but no stored table baseline
or import mapping. A genuine Base must be recovered/captured from bytes matching
that recorded hash, not fabricated from current Local or changed Remote. Reuse the
existing SourceRecord status/navigation, ProjectSession, table draft ownership,
content projection and command stack. A real user operation must bind source and
target, make mapping visible, preview the differences, recheck both identities,
and apply one reversible command without discarding pending drafts. Missing base,
ambiguous positional mapping, external changes, cancel and close must preserve
both sides. No source-schema or universal-session migration was introduced here.

Native M2/M3 remains held by the last manual-unlock requirement. IME/AX, Windows,
human usability, broad M6 performance/lifecycle work, M4 consistent recovery and M5
frozen delivery remain incomplete. At 05:32 the host had 8,850.31 MiB swap use and
load averages 1.69/2.34/3.01; suite timing is not a patch-specific performance verdict.
No stage completion, Git mutation, package, installed-app replacement, credentials,
signing, website, CI, deployment or release action is part of this slice.

Suggested commit message only: `fix(blocks): preserve merge candidates and imported table content`.
