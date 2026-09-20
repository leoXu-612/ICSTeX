# M4 reviewed recovered-draft resumption

The working source can resume explicitly selected source or Block drafts from a
verified recovery copy in a new editing window. It preserves original projects and
independent draft files. This is a bounded M4 increment, not automatic crash
recovery, interrupted-write recovery, format migration or complete V1 acceptance.

## Workflow and preservation

The File menu exposes `审阅恢复副本并继续草稿…`; a successful checkpoint restoration
also offers `审阅恢复草稿并继续编辑…`. The user chooses the container containing
`project/`, `drafts/` and `manifest.json`. A bounded background reader validates
every listed file and draft against recorded sizes/digests, reads them twice and
checks directory/file identities. Unlisted files are outside this verification.
Known links, incomplete containers, missing or changed bytes and unknown formats
are refused without writing. This is not archive authentication or an OS-wide
transaction against arbitrary external writers.

Drafts default to unchecked, with read-only bounded previews. Confirmation defaults
to No and triggers another full read bound to the reviewed manifest. Cancellation
and owner close wait for the active reader and cannot open a late result. Only one
review worker runs per dialog. A copy already open in an application window is
refused to avoid parallel editing authorities.

Source drafts are inserted into new editors from captured bytes as one undoable
edit. Known saved text targets retain encoding and a saved-byte conflict baseline;
unbound drafts require Save As. Block sessions establish their writer from saved
metadata before installing the recovered model and pending property drafts. The
existing Inspector and table editor can resume pending input without applying it
to the model. Source and Block drafts cannot be mixed in one selection; multiple
drafts for the same target require a single choice. Unselected drafts stay intact.

Both modes pause automatic writes/compilation until the first explicit successful
save. Subsequent saves use existing guards; changed source baseline bytes refuse
overwrite and preserve the draft. Restored Block models start a new editing
history: prior command stacks are not reconstructed, while new Apply/Undo/Redo
works normally. Save updates the recovered project, never the original project
or independent draft files. After saving, open `project/` normally; its changed
bytes no longer match the original recovery manifest. Recover another fresh copy
to review a different original draft choice.

## Implementation and tests

- `app/core/project_recovery.py` owns immutable copy reads, strict draft/model
  parsing and selection rules; it does not import GUI code or write files.
- `app/gui/project_recovery_dialog.py` owns review/confirmation and the new-window
  transition. Existing source/Block save coordinators enforce the first-save hold.
- Table/Inspector seams reopen recovered live-cell input without implicit apply.
- Core, GUI and visual regressions cover tampering, cancellation, changes between
  read passes, unknown metadata, competing windows, external winners, Undo/Save,
  actual Inspector/live-cell input and large-font review controls.

The actual persisted DocumentTheme supports empty/partial override dictionaries.
An early parser incorrectly required a fully populated theme schema; focused r1
failed on valid sessions. Validation now follows the persisted contract and exact
round-trip equality, without adding defaults or normalizing existing JSON.
The failed receipt remains `/tmp/icstex-v1-m4-recovery-resume-focused-r1.log`.
Later focused r2/r3 and final r4 passed; exact counts/timings and final full-suite
status belong to `PROJECT_STATE.md` and `PROJECT_LOG.md`.

Frozen app Python path/content SHA-256:
`305fb3dbb5f6f8accfb3ebda55eab249c185b90f0c1787a7a38d79eb3728efbc`.
Final focused receipt: `/tmp/icstex-v1-m4-recovered-drafts-focused-r4.log`.
Full receipt: `/tmp/icstex-v1-m4-recovered-drafts-suite-r1.log`, passed with exit 0;
exec `70159` / PID `25486` are terminal and the app hash was rechecked unchanged.
This full run took substantially longer than its predecessor in UI scale tests.
A one-second live sample found `QApplication.setStyleSheet` work; receipt
`/tmp/icstex-v1-m4-recovered-drafts-suite-r1-ui-sample.txt`. It does not isolate a
patch-specific regression or prove a leak. Functional success is not performance
acceptance; M6 still owns the controlled comparison and lifecycle investigation.

## Actual synthetic product evidence

`tools/probe_recovered_drafts.py` drives actual File actions, checkpoint/recovery
dialogs and confirmation buttons. Final r3 exited successfully on the frozen app
hash above, with output under `/tmp/icstex-v1-recovered-drafts-20260911-r3/` and log
`/tmp/icstex-v1-m4-recovered-drafts-product-r3.log`. It verifies cancellation with
zero project writes, no implicit save/apply, resumed editing, Undo/Redo, explicit
Save and fresh-window reload followed by a separately requested FINAL build.
Original projects and independent draft bytes remain unchanged.

Both resumed and reopened ordinary PDFs contain `Recovered source working text.`
and share SHA-256
`42d53b935f774ff47c1e1aee42bb6548d28afa201558ae022b412e12b7840913`.
Both Block PDFs contain `Recovered Block editing draft.` and share SHA-256
`6ca07bfb414fdc1727a16a1403a6423cce4eab93c9699f085a8e925951828e5b`.
The review, resumed Block editor and reopened PDF-view screenshots were inspected;
ordinary draft text is independently checked by PDF extraction, not inferred from
the partially visible page. The Block screenshot shows the recovered text.

Product r1 generated the Block PDF but waited for visible ink while the compact
workspace was still on the editor page. Product r2 reached the reopened PDF, but
its short viewport and zoom placed the text below view. Observation confirmed the
page/text existed; the probe now selects the actual PDF button and scrolls the
actual viewport. App code and the ink threshold were unchanged for these fixes.
Both failed logs/output directories remain local as r1/r2; they are not passing
product receipts and do not establish a renderer repair.

## Remaining boundaries

Only synthetic data and offscreen GUI were used. Native directory pickers were
not automated; paths were supplied to actual dialogs. Native IME/AX, Windows,
human acceptance, cloud availability, arbitrary external-writer races and power
loss are not covered. Interrupted Block journals and explicit legacy migration
remain next M4 work; M5 frozen delivery and M6 lifecycle/performance work remain
outstanding. No dependency, project format, MCP authority, version, package,
installed application or release change is part of this increment. The user
separately authorized its source submission; remote synchronization is recorded
only after a successful push and live hash verification.
