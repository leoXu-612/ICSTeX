# M6 formula coordinate boundaries and source-target fidelity

Ordinary-source formula selection and application now convert explicitly between
Qt UTF-16 offsets and Python character indexes. Non-BMP text before or inside a
formula no longer shifts package insertion, replacement or the returned cursor.
The live source target is checked before confirmation, retaining the formula
draft on external reload or target closure. This is not full M2/M6 acceptance.

## Source and boundaries

Authoritative repository, `codex/v1-development`, unchanged HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`, shared dirty worktree, empty index.
Baseline app: `61b4578c66fda33f78ddb63952ade35c7069c93e9947cc8fd18fbc318614ec8a`.
Final app: `489657f34516f5bfeee0934b84a26885e217e8ff3ea7cad05f3f1297819d0085`.
App+tests: `136e1892c4de31d04db0de8a2a40e97f7d58877238e90ab0784e161fc31ad59a`.
Digests use sorted relative Python paths, NUL, raw bytes, NUL. Python 3.12.6,
PySide6/Qt 6.11.1, macOS 26.6.1 arm64, offscreen.

Application files: new pure `app/core/text_positions.py`, coordinate contract
documentation in `app/core/formula_input.py`, and focused changes in
`app/gui/insertion_actions.py` / `app/gui/formula_dialog.py`. Tests extend
`tests/test_gui_editor.py` and add `tests/test_text_positions.py`.
The product probe is `tools/probe_formula_coordinates.py`.
No new dependency, wire-format field, OCR-worker lifetime change, blanket dialog
disposal, renderer implementation change or security-policy change. Only new
synthetic projects/settings; no foreground, student data, commit/push, packaging,
installed application or release action.

## Reproduction and repair

- Initial seven-test scope: 1.366s, seven failing assertions/subcases and one
  error, exec 13383 exit 1. Real editor selections after two non-BMP characters
  were rejected as incomplete. A valid Python plan inserted amsmath inside
  documentclass and replaced text outside the selected formula. EOF insertion
  failed; a stale empty range after truncation was accepted; target closure led
  to access of a deleted native editor. Actual external reload allowed stale
  formula application.
- Pure conversion now rejects out-of-range or split-surrogate offsets without
  rounding. Plans remain in Python indexes; tracked QTextCursors apply packages
  and replacement as one Undo. Both selection directions, non-BMP original/new
  bodies, inline EOF, previous Undo and exact surrounding source are covered.
- The source table validator is reused by formulas, checking captured revision,
  cursor/anchor, path/project, active target, mode, conflict and native validity.
  Failed confirmation leaves draft, preview and explanatory label visible; no
  new-source overwrite or force-rebase. Existing source-composition blocking,
  pending-command commit and idempotent Apply behavior remain covered.
- A separate source-mode wrapper test failed at cursor 23 instead of 25. Its
  source-editor clamp now uses UTF-16 length. This preserves the measured native
  cursor position; it does not claim all mode-switch selection semantics.
- First focused run after the coordinate repair: 58 / 4.459s, one fixture error.
  An older FakeDialog did not accept the new validation keyword. It now accepts
  and asserts the live guard, retaining its original replacement/cursor assertions.
  This setup correction is not hidden as a product regression fix.

Test-triage separated coordinate, stale-target, source-wrapper and fixture
failures. The new deleted-editor exception is not claimed to identify the old
timer crash or stylesheet object. Formula dialogs retain their previous lifetime
policy because asynchronous OCR ownership is outside this repair.

## Actual product evidence and verifier correction

Final probe r6, exec 19189 exit 0, uses actual unpatched FormulaDialog/buttons:
backward selection after an emoji comment, Cancel preserving source/selection,
source-mode replacement retaining an unknown macro and comment, package+formula
one Undo, independent earlier Undo, Redo, explicit Save, tab close/reopen and
real pdfLaTeX FINAL. Saved bytes and source cursor/scroll remain unchanged by
Save/compile. PDF text is `Before x + y after. 1`. A separate synthetic file is
externally reloaded during its modal editor; real confirmation is refused and
the source draft, preview and explanation remain until Cancel.

Artifacts: `/tmp/icstex-v1-formula-coordinates-r6/`. Inspected
`formula-final.png` and `formula-target-refused.png`. Final workspace shows
saved / pdfLaTeX / FINAL / current PDF. Unicode characters occur in PDF-source
comments; source tests also cover characters inside a formula, but this is not
an arbitrary Unicode-font rendering or native IME/clipboard/AX claim.

Earlier probe failures r1-r5 are retained, all exit 1. Source/Save/reopen/compile
had passed before their visual pixel check. R2 observes correctly rendered math
but only three pixels below lightness 100; one zoom clips the math (r3), an early
navigation attempt leaves it outside the viewport (r4), and centered 200% math
has zero pixels below 100 (r5). Screenshot measurement proves glyph minimum
lightness 119 while the adjacent blank control is 255. Therefore the old black-
pixel predicate cannot detect these visible gray glyphs. No product renderer was
changed to accommodate the test.

R6 retains document-text/source identity checks and uses a centered formula ROI
with an adjacent blank-paper negative control: 115 pixels below lightness 160,
zero in the blank region, 96.68% white in the formula ROI. This rejects blank or
solid-gray regions and is paired with direct image inspection. The old threshold
failures are not relabeled passes. The 200% view is pixelated; rendering-quality
and native/high-scale acceptance remain separate, not certified by this receipt.

Saved source SHA-256 `fcf3e7c5f49b88dfa6d10ca938104c7cd9dad5e0bd9b100db447c2ebf830ebc9`.
FINAL PDF SHA-256 `302ca81ae4cf6cb5d847a6007f11a16e06c87b8137047b5b33933218a5aa371d`.
Report SHA-256 `a5a444b553a68c8994315314c37a2659e681e3fdfcb9ba41880b578318c5173c`.
Probe script SHA-256 `a14b495a57791f07f4aaa9f83d4b291bfe6557eaebcd13a8bf7991dab84ebafc`.

## Verification

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_text_positions tests.test_formula_input \
  tests.test_gui_editor.FormulaSourceTargetTests tests.test_gui_editor.FormulaComposerTests \
  tests.test_gui_editor.TableDialogLifetimeTests tests.test_gui_editor.GeneratedInsertionTransactionTests \
  tests.test_block_editor_targets -v
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_gui_editor tests.test_project_file_ops tests.test_gui_submission_check \
  tests.test_gui_preview_pipeline tests.test_pdf_panel -v
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest discover -s tests
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 tools/probe_formula_coordinates.py \
  --output /tmp/icstex-v1-formula-coordinates-r6
git diff --check
```

Final focused: 133 / 5.788s / OK, exec 61139 exit 0. Expanded: 277 / 54.319s / OK.
Required full: 1550 / 145.308s / OK, sequential exec 30576 terminal exit 0; full
ran only after expanded exit 0. Post-terminal app/app+tests hashes match.
Compileall/diff pass. Final expanded/full logs have no Traceback, RuntimeError,
RuntimeWarning, fatal Python/SIGBUS/segmentation marker. Expected offscreen and
font-alias warnings remain; no new report among ten retained Python crashes.
All handles terminal; HEAD/index/held candidate feed unchanged.

Logs under `/tmp/`: `icstex-v1-formula-coordinates-red-r1.log`,
`icstex-v1-formula-wrapper-red-r1.log`, `icstex-v1-formula-coordinates-focused-r1.log`,
`icstex-v1-formula-coordinates-focused-r2.log`, `icstex-v1-formula-expanded-r1.log`,
`icstex-v1-formula-full-r1.log`, and `icstex-v1-formula-coordinates-r1.log` through
`icstex-v1-formula-coordinates-r6.log`.
Expanded log SHA `7d24bf359f3a87d9146b8317983b0f511ab0e823985ce3ac222074e9316fd99a`.
Full log SHA `7d9ecd3fd31f9f9714ce43116423dae07a52021bd7cb6ac382f7e2c9a3c136b1`.

## Next boundary and rollback

Next bounded action is R2 native Inspector Control+Tab/Control+Shift+Tab and
high-scale focus verification after one fresh control-channel check. Announce
foreground QA before starting; if unavailable, do not launch a waiting native
window or repeatedly poll the same locked state. R1 physical input, remaining
R3 native/timer/AX questions, R5 restricted LuaLaTeX, R6 and E1-E4 stay open.
No complete V1 or release-candidate recommendation.

Rollback only these conversion/target-validation/wrapper-coordinate hunks and
new regressions; preserve earlier table and IME work. Suggested commit only:
`fix(gui): preserve formula targets across UTF-16 boundaries`.
