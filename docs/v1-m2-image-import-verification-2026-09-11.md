# V1 M2 image import boundary checkpoint

Development source, 2026-09-11. The resumed native picker-to-FINAL flow now passes:
real Cancel, PNG selection/import, Undo/Redo, Save/readback, unsafe destination
rejection, GUI session reopen and a second FINAL. See the follow-up receipt below.
This bounded acceptance does not close M2-M6 or release gates.

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
- Real Finder drag, unknown-macro/source fidelity, IME,
  AX stress, Windows and human usability remain separate acceptance work.
- No app packaging, installed-app replacement, candidate-feed upload, signing,
  deployment, version change or release is authorized by this source checkpoint.

## Resumed native picker acceptance, 2026-09-11

The user reauthorized foreground control. `computer-use` was used through
NodeREPL and the bundled desktop interface to operate only the synthetic Python
QA app's actual Cocoa file panels. The installed ICSTeX app and student projects
were not opened or changed. This run does not mock QFileDialog return values.

The old probe now requires explicit `--native` and Cocoa, checks delete-on-close
instead of deleting a closed MainWindow twice, and actually reinstalls the saved
project as a fresh GUI ProjectSession before another explicit FINAL. Application
and test source are unchanged from the prior M5 version-label checkpoint.
One shared probe helper also restores its two-argument default-XeLaTeX call
compatibility; the previous increment had made the third argument required while
other GUI probes still called it with two. Signature binding is verified.

Command: `QT_QPA_PLATFORM=cocoa PYTHONFAULTHANDLER=1 python3
tools/probe_image_import.py --native --output
/tmp/icstex-v1-m2-image-import-native-r3`. Exec 79095 is terminal, exit 0.
Environment: macOS 26.6.1 arm64, Python 3.12.6, Qt/PySide6 6.11.1.
App SHA-256: `d7d57520c5a1a26044ed70457df5ecc79d839707c8475f6dddf5a954658e3219`.
Probe SHA-256: `6c62fed19e0c605002bd87019833120244bb66cf7903703d8652afde4190cec5`.

Verified observations:

- Real Cancel preserves all original project bytes, image selection, model,
  undo count and clean state; no image is added.
- Going directly to the PNG path initially visually selects it while Open is
  disabled. AX/click attempts did not make selection effective. Keyboard Down to
  the folder then Down to the PNG produces an enabled Open button and successful
  import. This is evidence of a working real keyboard path, not a proved cause
  of the earlier automation failure or a general Cocoa picker fix.
- The copied PNG bytes equal the chosen synthetic source; the original blue PNG
  and chosen green PNG are unchanged. Exactly one undo step restores/reapplies
  the model source. Explicit Save persists that relative path, without compiling.
- Explicit FINAL produces a visible green image in the actual PDF panel. After a
  synthetic destination-directory swap to a symlink, a third real picker returns
  the error `Image destination changed or contains a link; import refused`.
  Acknowledging it leaves model/undo/source/retained images and the outside folder
  unchanged. The probe restores its own temporary directory arrangement.
- Closing the Block project and opening a fresh GUI session from disk retains the
  selected image, starts clean and does not grant compilation implicitly. A new
  explicit FINAL again renders the green image. Both native window captures were
  visually inspected; the test window is destroyed and the process exits 0.

Artifacts under `/tmp/icstex-v1-m2-image-import-native-r3`:

| Artifact | SHA-256 |
| --- | --- |
| `report.json` | `8b0c4a18b43b6922465ed0b66d3d79a3f82813a1c75c9b027a5370d53cb9307f` |
| `image-import-final.pdf` | `311fd1c1f81a08e26440af284c5bde3ad1bb1e92b2ba2dee73d36019d620a458` |
| `reopened-image-final.pdf` | `eff3c5e96a3f9d73a55104f475f39cb96a1d34d7a36df7c22bbbfc81a1bda894` |
| `actual-image-final.png` | `7a1c84d6f43be62f1a8a77de4a163035794aeee67417b7412249497c7906ed88` |
| `reopened-image-final.png` | `7fd070f19241a575bdebb65da7c680785c7c1feae32995ead25710cd83488e45` |

Log: `/tmp/icstex-v1-m2-image-import-native-r3.log`, SHA-256
`49996364e15a07e856346fa55e84a450ca15ac1d88e656bf6f8ce7deaa4b426f`.
Different PDF hashes are not treated as a failure of cross-run byte reproducibility;
the requirement here is correct selected-image content in each actual FINAL.

No new Python crash report was observed. The existing version-scoped Qt Cocoa
selected-children guard remains active and logged; this does not establish full
AX/IME or resolve the old Qt stylesheet/timer crash causes. Desktop observation
ended with `App quit` after successful probe cleanup, not a native crash; an
intermediate NodeREPL variable error was automation-only and did not restart the
live probe or substitute its results.

Compileall, probe syntax checks and diff check pass. The follow-up required full
regression is TERMINAL/PASS: 1455 tests in 139.577s, OK / exit 0, exec 3225 / PID
75313, started 2026-09-11T06:41:04Z, nice 10 and PYTHONFAULTHANDLER=1. Log
`/tmp/icstex-v1-m2-image-import-followup-suite-r1.log`, SHA-256
`92bdeea6e5a4432026ebaaf1a021278440fba1582c3d44104ff02ff7a8190d77`.
Post-terminal app d7d57520 / app+tests 48066a6e hashes match the source freeze.
No new failure/traceback/RuntimeError was observed. All full/native handles are
closed; this duration is not a performance benchmark. The remaining next local
slice is native formula clipboard/keyboard/Undo fidelity, not a repeat of this
completed image flow.
