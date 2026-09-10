# V1 M2 image import boundary checkpoint

Development source, 2026-09-11. Focused tests passed; native picker-to-FINAL
acceptance is incomplete. This checkpoint does not close M2-M6 or release gates.

## Implemented scope

`app/core/blocks/asset_import.py` reuses the cooperating project lock and existing
safe-path rules. It validates the opened source, stages copied bytes, flushes them,
checks observed source identity and publishes without replacing an existing name.
POSIX directory descriptors anchor writes and reject observed internal links or
directory replacement. Cleanup removes only the owned stage. Existing filename
collisions choose a new name; source and previous assets are retained.

`app/gui/blocks/navigation_dock.py` maps drop coordinates into the actual list
viewport, captures the image target once, and rejects closed/stale targets or
copy failures. Failed items do not update the model; earlier successful items in
a batch remain explicit partial successes. No whole-batch rollback is claimed.

`tests/test_gui_submission_check.py` and the navigation fixture explicitly dispose
of their own closed Qt objects. The isolated disposal trial removes retained test
windows; this is not a change to application window ownership or an app-leak fix.

## Evidence

App Python path/content SHA-256:
`5acfce28d24ebcb2fe9b87ba56cfc9bb9f47d68e7e26d8b452db3affe599cce5`.
Required compileall and `git diff --check` pass. Focused integration receipt:
`/tmp/icstex-v1-m2-asset-import-focused-r1.log`.
The command is:

```sh
QT_QPA_PLATFORM=offscreen python3 -X faulthandler -m unittest -v \
  tests.test_block_asset_import tests.test_block_editor_targets \
  tests.test_block_property_drafts tests.test_block_session_safety \
  tests.test_block_console_integration tests.test_blocks_gui \
  tests.test_gui_submission_check tests.test_ui_visual tests.test_blocks \
  tests.test_table_model
```

Core checks cover internal/dangling links, failed copy/publication, concurrent
filename creation, source changes, swapped directories, invalid source and a
busy project lock. Navigation checks cover actual-row routing, closed sessions,
missing files and ordinary insertion. Terminal counts and full-regression status
are maintained in `PROJECT_STATE.md` and the historical log.

The initial new drop-test helper released a QMimeData borrowed by QDropEvent.
Its exit 139 generated `Python-2026-09-11-021658.ips`; the inspected stack reached
`Sbk_QDropEventFunc_mimeData`. Keeping the MIME object alive allowed the unchanged
application to reach expected red assertions. After the application fix, focused
tests passed. This fixture defect does not resolve the earlier timer-dispatch
crash's uncertain cause. Red receipts remain local:
`/tmp/icstex-v1-m2-asset-import-red-r1.log` and
`/tmp/icstex-v1-m2-asset-drop-red-r2.log`.

`tools/probe_image_import.py` uses only disposable synthetic projects and isolated
settings. Actual Cocoa picker Cancel reached zero-mutation assertions. The next
real picker showed the synthetic PNG but its Open button remained disabled;
successful import, Undo/Save/reopen, error handling and FINAL were not completed.
The owned process was stopped on the user's source-sync request. Receipt:
`/tmp/icstex-v1-m2-image-import-native-r2.log`. This is not native acceptance;
do not substitute a mocked picker return value when resuming that gate.

## Remaining limits

- Windows native reparse races are unverified. POSIX filesystems without supported
  exclusive hard-link publication fail closed; no replacement fallback is used.
- Source identity checks are observed metadata checks, not a cryptographically
  frozen snapshot or exclusion against arbitrary external writers.
- Real Finder drag, picker success/error/PDF, unknown-macro/source fidelity, IME,
  AX stress, Windows and human usability remain separate acceptance work.
- No app packaging, installed-app replacement, candidate-feed upload, signing,
  deployment, version change or release is authorized by this source checkpoint.
