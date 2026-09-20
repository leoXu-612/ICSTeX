# M5 reviewed GUI delivery: integration in progress

Status: source/Block/standalone GUI integration passes focused, expanded, real
offscreen and native synthetic workflows. The frozen full regression passed:
1421 tests in 718.732s, exit 0, post-run hashes match. Subsequent Agent/MCP repairs
and shared FINAL cache follow-up are in `v1-m5-agent-export-verification-2026-09-11.md`;
this receipt covers the earlier GUI source, not those later changes. Build-time tool-version proof remains open;
this is not complete M5, V1, platform acceptance or release readiness.

## Implemented user workflow and boundaries

- File -> Prepare submission, File/PDF -> Export PDF, and Block workspace ->
  Export now share one actual review dialog. The independent Block dialog binds
  its own ProjectSession without pretending to be MainWindow. No GUI entrance
  calls the old portable copier or requests an immediate cached-PDF copy.
- Opening/reviewing never saves or compiles. Separate Save and FINAL buttons use
  existing source/Block guards and draft confirmation. After those actions the
  user explicitly refreshes review; a preview or cached record without actual
  FINAL evidence cannot become delivery. The old automatic-export queue is not
  part of this user-facing workflow.
- Default only PDF in a new outside directory. Source and report are independent
  opt-ins; source candidates start unchecked. The user reviews M1 status/reasons,
  filenames, byte counts, digests and bounded text/hex previews. Unknown checks
  require separate acknowledgement and remain unknown. The same immutable output
  payload function supplies preview and publication, preserving source README,
  manifest, encoding and optionally selected known Block metadata.
- CaptureLease reuses source save holds and existing Block pause/revision rules,
  with explicit standalone owners. Related dirty source buffers and competing
  dirty Block sessions cannot be mistaken for saved inputs. No universal session,
  writer topology, project format, MCP capability or wire change.
- One active worker; live changes cancel/invalidate review. No QWidget access in
  workers. Choice/target and live identity are rechecked after default-No confirmation,
  then disk bytes are rechecked during staged/exclusive publication. Cancel/owner
  close waits for worker cleanup; a publication that wins late cancellation is
  reported truthfully. Failures release holds and require a fresh review.

## Source and tests

App path/content SHA-256:
`b5bce3681839b945d31aad3852554fff460e0d336a89605ee3f6fc02fd782fcd`.
App+tests path/content SHA-256:
`9deda6dc8270279e5fae9f44e3a5376a6bb8883afcbf0fd53e22f5049c66f7ad`.
Branch codex/v1-development; HEAD remains 3bde2b5. Changes uncommitted.
Environment: macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1, local XeLaTeX.
Required compileall and diff checks passed.

Expanded command, 163 tests in 22.113s, OK / exit 0; exec 45657 terminal:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_submission_delivery tests.test_submission_check tests.test_submission_delivery_gui tests.test_pdf_panel tests.test_gui_submission_check tests.test_gui_preview_pipeline tests.test_gui_editor.GuiPdfStateTests tests.test_gui_editor.GuiEditorTests.test_export_and_reveal_pdf tests.test_gui_editor.GuiEditorTests.test_export_pdf_rejects_empty_and_reviews_stale_without_implicit_rebuild tests.test_project_checkpoint_gui tests.test_project_migration_gui tests.test_project_recovery_gui tests.test_block_write_recovery_gui tests.test_ui_visual.WorkbenchVisualSmokeTests.test_submission_delivery_controls_are_scroll_reachable_at_large_font -v
```

Log `/tmp/icstex-v1-m5-delivery-gui-expanded-r2.log`. Includes explicit choices,
exact preview/output bytes, missing/preview FINAL, current/peer drafts, stale
same-mtime child changes, root/choice/target changes, disk failure, cancellation,
standalone ownership/close holds, publication winning cancellation, existing
checkpoint/recovery/migration seams and scroll access with 12/18pt fonts.

Failure evidence was retained, not bypassed:

- Initial 12 GUI tests passed. The extended 14-test run then exposed a real delayed
  PDF callback after widget deletion: `_update_page_controls` accessed a deleted
  QPdfDocument. A targeted red test proved two callbacks after destruction (exit 1,
  `/tmp/icstex-v1-m5-pdf-lifetime-red-r1.log`). PdfPanel delayed reload/search/restore
  callbacks now use the owning QObject as QTimer context. The same regression and
  14 GUI tests passed, 15 tests in 2.364s, exec 93486 exit 0. No broad Qt AX claim.
- Expanded r1 had one assertion comparing a canonical `/private/var` root with
  a fixture's `/var` spelling. Expected root is now resolved, retaining exact root
  and per-tab PDF ownership assertions; r2 above passes.
- Old GUI tests asserting immediate cached-record copying/automatic FINAL queue
  were updated for explicit review and no implicit compile. Strong byte/failure/
  stale-input publication checks live in the new GUI/core tests and real product
  probe. The old copier's direct failure test is explicitly internal compatibility
  coverage, not evidence for the new user-facing route.

## Real synthetic product evidence

```bash
QT_QPA_PLATFORM=offscreen python3 tools/probe_submission_delivery_gui.py --output /tmp/icstex-v1-m5-delivery-gui-20260911-r2
QT_QPA_PLATFORM=cocoa python3 tools/probe_submission_delivery_gui.py --native --output /tmp/icstex-v1-m5-delivery-native-20260911-r1
```

Both exited 0 on the app hash above: offscreen exec 29435, native exec 96488 /
PID 58100, all terminal. Logs `/tmp/icstex-v1-m5-delivery-gui-product-r2.log` and
`/tmp/icstex-v1-m5-delivery-native-product-r1.log`; result.json in each output folder.
Earlier offscreen r1 also passed; r2 strengthens the driver to wait for the NEW
FINAL evidence object after each explicit compile instead of accepting old proof.

All four modes use real File/workspace actions and real dialog controls, protected
Save/FINAL, default-No cancel followed by confirm, PDF-only and selected source/
report delivery. Every previewed payload equals published bytes. Original selected
files stay unchanged; ordinary TeX recompiles independently from exported source;
selected Block metadata reopens; a checkpoint restores and compiles in a new directory.
PDF text is checked using QPdfDocument. This does not assert complete page-layout
approval or native file-picker/physical-keyboard use.

| Mode | Native delivered PDF SHA-256 | Source/report output file count |
| --- | --- | ---: |
| Single | `7cf5836166d720be2e16e1745c0ae9a214fcc702ced2bc40e1de6964e159b7c9` | 7 |
| Multi | `f346fdcf4b8153c0661caf608a47bd7636c1ccd74473b4f13e21b1aa4c242b86` | 10 |
| MainWindow Block | `6a9cbce6144c24d741f04b90cc58f775794b12b8260eb7a5f58d489988192c78` | 13 |
| Standalone Block | `8855893a11ffb1349839ea9a0cb329f5fc0b084f36976cc4a22f6aa49c3ef5bb` | 13 |

Native review and published-result screenshots inspected. One external AX read
returned the standalone preparation dialog. A second read timed out; the subsequent
process result confirmed normal exit 0. Do not count that timeout as a successful
AX sample or infer its cause. The four-file Python crash-report inventory was
unchanged. The existing version-scoped selected-children mitigation was active;
native log contains that explicit warning. Full IME/AX acceptance remains open.

## Completed full run and next work

```bash
nice -n 10 env QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
```

TERMINAL/PASS: exec 10341 / PID 58091, 1421 tests in 718.732s, OK / exit 0.
Started 2026-09-11T04:41:19Z (12:41:19 local), nice 10, load 2.12/3.20/5.56.
Log `/tmp/icstex-v1-m5-delivery-gui-suite-r1.log`, SHA-256
`ebf15d609c9df765f61d222c3d8fc244d549d941889a169a9465a082618b6e2c`.
The handle is closed and PID absent; do not restart/poll it. Both app and app+tests
hashes above were recomputed after terminal collection and match. Compileall and
diff check passed again. No Traceback/RuntimeError/failure record found in the log;
offscreen plugin warnings remain. Native product overlapped this full run, so its
718.732s duration is functional-test evidence, not performance acceptance.

Next finish the AgentWorkspace/MCP
portable-export contract (including its existing empty staging-directory caller),
current PDF content rechecks there, and actual build-time tool-version evidence.
Retain wire, capabilities, locks and GUI/MCP writer exclusion. The original audit's
old GUI driver assumes the retired save-dialog route and must not be rerun blindly
against this modal flow. Its portable-export defect receipts remain relevant.
While app/tests were frozen, a separate actual-AgentWorkspace probe also reproduced
post-FINAL input changes being accepted, late-existing PDF target overwrite,
private-name copying, README/manifest mismatch and mixed-source package publication.
Exec 5817 exited 0 because all defect assertions held, not because they were fixed.
Receipt: `v1-m5-delivery-audit-2026-09-11.md`, AgentWorkspace follow-up section.

Full M2-M6/native IME/AX/Windows/human/performance acceptance and independent Beta
installation/release gates remain open. No commit, push, package, installed-app
replacement, signing, deployment, upload or release.
