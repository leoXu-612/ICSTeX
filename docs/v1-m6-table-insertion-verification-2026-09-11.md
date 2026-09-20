# M6 table lifetime, insertion transactions and stale-target protection

Ordinary-source table insertion now releases completed dialogs, groups required
packages and the table into one Undo, preserves earlier Undo history and refuses
a changed insertion target without discarding the open table draft. This closes
the reproduced table cases, not all M2/M6 or historical native crash acceptance.

## Source and scope

Authoritative repository, branch `codex/v1-development`, HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`; shared work and empty index preserved.
Prior verified app `890bbd2c2968cbd5de120a729cccb6bb0951d1f9af5d3a48db8fbcdfcb0fd514`.
Final app `61b4578c66fda33f78ddb63952ade35c7069c93e9947cc8fd18fbc318614ec8a`.
App+tests `f24bcd01113d0398c08c37950abe1e1e66772ac674e1656f7232432737210a0a`.
Digests use sorted relative Python paths, NUL, raw bytes, NUL.
Python 3.12.6, PySide6/Qt 6.11.1, macOS 26.6.1 arm64, offscreen.
Only synthetic files/settings were used. No foreground control, student edits,
Git mutation, packaging, installation, signing or release action.

Application changes are limited to `app/gui/insertion_actions.py` and
`app/gui/insert_panel.py`; regressions extend `tests/test_gui_editor.py`.
`tools/probe_table_insertion.py` exercises the actual unpatched dialog caller,
buttons, saved source and real pdfLaTeX output. No blanket asynchronous-dialog
deletion, OCR-worker change, global GC switch or security-policy change.

## Evidence-driven repairs

1. **Lifetime.** Previously six actual modal Cancel cycles retained six native
   TableDialog children. The first four-case baseline failed disposal on Cancel,
   acceptance and exec/value failure. The caller now extracts accepted immutable
   values before scheduling deletion in `finally`, guarded by `isValid` if the
   parent closed during the nested event loop. Tests retain Python wrappers and
   check native invalidity after DeferredDelete, not merely wrapper GC. The
   parent-closure fixture uses actual `window.close()` so controllers shut down.
2. **Undo and positioning.** Disposal alone exposed a failing one-Undo assertion:
   new package declarations remained. `ensure_packages` used `setPlainText`,
   destroying prior Undo and selections; it also mixed Python indexes with Qt
   UTF-16 positions. Nine-case red scope recorded 11 failing assertions/subcases.
   The shared helper now uses tracked QTextCursors, an explicit UTF-16 insertion
   coordinate and nested edit blocks. Block padding uses both selection bounds
   and Qt paragraph positions. Standalone diagnostic package fixes remain one
   Undo; existing packages, consecutive operations, inline cursor offsets,
   forward/backward selection, non-BMP comments/EOF and soft-wrap are covered.
3. **Target fidelity.** An actual external reload during the modal loop still
   accepted a stale table. Adding a header shifted the old cursor into
   `\documentclass`, and insertion split that command in the editor. The disk
   retained the external bytes because the synthetic fixture delayed autosave;
   this was not a safe accepted editing result. The first diagnostic r1 wrongly
   assumed reload preserved selection; it failed and is retained. Corrected r2
   observes selection clearing and proves the split command, without changing
   product code. Four target-refusal assertions then fail on baseline.
   The source caller now captures editor revision, cursor/anchor, path and
   project scope. Confirmation checks active target, native validity, mode and
   conflict state. A changed target keeps the dialog, grid/caption/label draft
   and copyable source preview open with an explanation; it does not rebase,
   force overwrite or silently abandon the draft. Cancel still disposes it.

The tests distinguish these defects from setup errors and historical Qt signals,
following test-triage. None is asserted to identify the old timer receiver or
exact stylesheet crash object. Formula/OCR lifecycle remains unchanged.

## Actual product workflow

Final-source probe r2 exits 0, exec 67845:

- Six actual Cancel cycles: no retained native dialog, unchanged original CRLF
  bytes, no compile authorization.
- Accepted table replaces the backward-selected synthetic Body. Header Value,
  numeric zero, caption Measured values, label and unknown custom macro survive.
  One source Undo removes both new packages and table; the next Undo restores
  the earlier independent edit. Two Redos restore both operations separately.
- Explicit Save preserves cursor/scroll; close/reopen reads the saved source.
  Explicit pdfLaTeX FINAL produces and renders one page with the macro text,
  header, zero and table caption. Compile leaves saved bytes and view unchanged.
- A separate synthetic file receives an actual external reload while its table
  dialog is open. The real OK button is refused; the original draft, visible
  explanation and copyable preview remain. Cancel closes and deletes the dialog.
  The external file and the earlier FINAL source are preserved.

Artifacts: `/tmp/icstex-v1-table-insertion-r2/`. Inspected images
`table-target-refused.png` and `table-final.png` show the retained draft/controls
and actual source/PDF. The final workspace reads saved / pdfLaTeX / FINAL /
current PDF. R1 took its image before the workspace label settled; r2 explicitly
waits for that state. This is offscreen widget/output evidence, not Cocoa,
physical input, IME, AX or real-student acceptance.

Saved source SHA-256 `49cbedce9e41e059cc49e80bc7caa4da9e9277f6a2c692ec17bb7f5282b61406`.
FINAL PDF SHA-256 `d46e39dd1edc739410ab901e37d8d95f12fc8abad76cfe204c4ed76161912874`.
Report SHA-256 `366bb622005cf1e9619bee5dd31da814b6a787945ede1c7544222749194e8c26`.
Probe script SHA-256 `c05714d60bf10ae28600a5bd9f2c7cb7a44959fb23e70cb84ea7b33d24484ecb`.

## Verification commands and results

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_gui_editor.TableDialogLifetimeTests \
  tests.test_gui_editor.GeneratedInsertionTransactionTests -v
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 tools/probe_table_insertion.py \
  --output /tmp/icstex-v1-table-insertion-r2
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_gui_editor tests.test_project_file_ops tests.test_gui_submission_check \
  tests.test_gui_preview_pipeline tests.test_pdf_panel -v
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest discover -s tests
git diff --check
```

Final focused: 14 / 2.020s / OK, exec 79904 exit 0. Final expanded:
268 / 51.853s / OK. Required final-source full: 1538 / 142.721s / OK.
Sequential exec 94339 is terminal, exit 0; the full command ran only after the
expanded command returned 0. Compileall and diff checks pass; post-terminal app
and app+tests digests match. All test/probe handles are terminal. The ten retained
Python crash reports, HEAD, empty index and held candidate feed are unchanged.
The earlier transaction-only source passed 13 focused, 264 expanded and 1534 full
tests before the separate target defect was discovered. Those results are not
relabeled as final-source coverage.

Retained logs under `/tmp/` include `icstex-v1-table-dialog-red-r1.log`,
`icstex-v1-table-dialog-lifetime-green-undo-red-r1.log`,
`icstex-v1-insertion-transaction-red-r1.log`, `icstex-v1-table-stale-target-r1.log`,
`icstex-v1-table-stale-target-r2.log`, `icstex-v1-table-target-red-r1.log`,
`icstex-v1-table-target-green-r1.log`, `icstex-v1-table-insertion-r2.log`,
`icstex-v1-insertion-expanded-r2.log`, and `icstex-v1-insertion-full-r2.log`.
Expected offscreen unsupported-size/keyboard warnings and missing Sans-serif font
alias warning are not native acceptance evidence.

Final expanded log SHA-256 `3816ddb8adf9bfa979562d1439416e05163080d70fb64a074c5428d95e24763e`.
Final full log SHA-256 `540b0ae31a2cc48b887c2d5b3fdeab041e93e035f4a16a77c555a668cfb4b832`.
No Traceback, RuntimeError, RuntimeWarning, fatal Python error, SIGBUS or
segmentation marker was found in final expanded/full/product logs. This is a
bounded log check, not a general native stability certificate.

## Remaining work and rollback

Next bounded background check: ordinary-source formula selection/application
coordinates after non-BMP text, using actual editor selection and preservation
assertions. The existing source/Qt coordinate boundary warrants a discriminating
test; no formula defect is declared proven by this table receipt. Preserve OCR
worker lifetime and earlier source-identified formula evidence.

R1/R2 physical IME/focus/high-scale, historical R3 timer/AX limitations, R5
restricted LuaLaTeX, R6 reconciliation and external E1-E4 remain open. No V1
completion or release-candidate recommendation. Rollback only the table guard/
disposal and shared insertion transaction/padding hunks plus their new tests;
preserve unrelated dirty-worktree changes. Suggested commit only:
`fix(gui): preserve table insertion history and reject stale targets`.
