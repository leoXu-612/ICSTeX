# V1 M0 and partial M1 verification

This is a local source-development result, not a release or a completed M1-M6
workflow. The active acceptance ledger is `V1_IMPLEMENTATION_PLAN.md`; exact full
suite counts and timings belong to `PROJECT_STATE.md` and `PROJECT_LOG.md`.
The later FINAL-binding slice is documented separately in
`v1-m1-final-evidence-2026-09-10.md`; the observations below describe this earlier slice.

## Source and data boundaries

- Started from synchronized `release/2.1` HEAD
  `f03776e87c0f938421a70ff5b085db920f2d01d7`; all V1 changes remain uncommitted.
- M0 app Python path/content digest:
  `34c631d5f3c838a456b89033e73e015bf20c8a7112623b63edc47576b20da66d`.
  Samples: `data/v1/m0-response-baseline.json`.
- Final Block-inclusive native probe app Python path/content digest:
  `7af81592d3235997563f6b835511120e26a8291d17302bab20cf96b0af08f140`.
- Only newly created synthetic single-file, Chinese-path multi-file and Block
  projects were used. Existing-target fixture creation refuses overwrite. No
  student files, installed application, signed candidate or network release
  service were changed. No dependency installation or packaging was performed.

## Implemented and verified slice

| Area | Local evidence | Remaining boundary |
| --- | --- | --- |
| Ordinary source | Root/child capture, tool-path validation, saved state, existing FINAL/input matching, resource/citation locations, count mode and explicit target rules | Formal-log coverage and user-editable profile remain open |
| Async lifetime | One active worker plus latest pending request; cancel/close/model/root/engine/external invalidation; stale navigation refusal | This is a captured technical check, not continuous or academic certification |
| Block scope | Visible Block session selected over hidden source tab; model JSON compared with saved metadata; pure generated-source comparison; no save/assembly/compile | FINAL model/revision/purpose/build/dependency binding remains UNKNOWN |
| Metadata events | Explicit opt-in for three Block JSON files through existing polling watcher; preview/build files stay excluded; native external edit clears report | No new external-conflict writer or overwrite shortcut |
| Native presentation | Cocoa source window, real one-page ordinary FINAL, child citation navigation to line 4, same check panel in source tabs and Block bottom dock, five scales 90%-150% | Existing Block editor/inspector layout is still clipped at high scale; M2 is not accepted |
| Original bytes | Synthetic ordinary and Block originals restored and compared byte-for-byte after explicit fault injection | Not evidence about student projects or app installation |
| Welcome lifetime | Bound Qt slot replaces retained lambda; repeated deleted-page scale regression | Not proof of general AX, IME or native lifecycle stability |

The ordinary native case reports PASS for saved/root/toolchain/FINAL/PDF/static
resources/references/count, UNKNOWN for bounded coverage and N/A for an unset
word target. The Block case reports PASS for saved/model-generated/root/count,
but UNKNOWN for FINAL/PDF. Showing the previous source PDF in the shared Block
view is not treated as Block build evidence; display ownership is an open M2 seam.

## Reproduction

Run from the verified repository root with the existing local Python/TeX tools:

```bash
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
QT_QPA_PLATFORM=offscreen python3 tools/bench_response_pipeline.py --output /tmp/icstex-v1-baseline-new.json
QT_QPA_PLATFORM=cocoa python3 tools/probe_submission_check.py --output /tmp/icstex-v1-native-new
git diff --check
```

The native output directory must be NEW. Raw screenshots/logs remain local
because they include synthetic temporary paths and unredacted application logs.
Final native evidence directory for this round:
`/tmp/icstex-v1-native-20260910-m1-block-r3/`; its `report.json` and screenshots
were inspected. Its process exited 0, with no RuntimeError/RuntimeWarning or
traceback in that final run. Earlier native attempts are not substituted for it.

## Failures found and limits retained

- A first Block layout put two bottom docks beside one another. Native images
  exposed squeezed check content despite button geometry assertions. Tabifying
  the docks and checking available width improved the check area; this does not
  fix the surrounding Block workspace's pre-existing high-scale layout.
- A subsequent native run timed out waiting for a Block metadata change: the
  existing watcher suppressed all `.icstex` events. The initial synthetic event
  test was insufficient. Added narrow opt-in, tested default suppression and
  owner removal, then observed the actual native polling event in the final run.
- One focused navigation test raced an undelivered real file event. It now waits
  for the dependency generation change from the real observer instead of creating
  a second synthetic event. Production invalidation was not weakened to pass it.
- No macOS AX stress scan, IME interaction, Windows run, human first-use trial,
  project checkpoint restore, frozen delivery or installation acceptance occurred.
- M1 remains incomplete; M2-M6 are not implemented by this report. The separate
  Beta installation-lifetime exclusion and publication gates remain unchanged.
