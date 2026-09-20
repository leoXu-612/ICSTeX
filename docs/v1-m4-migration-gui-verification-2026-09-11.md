# M4 selected-file migration review and separate opening

Status: focused, synthetic offscreen product checks and the earlier frozen-source
full regression passed. A later native follow-up also passed, with distinct source
identity below. This is local, unpublished source, not complete M4/M5/M6 or full
native/platform acceptance. The native follow-up does not validate all newer M5 code.

## Scope and source

- User workflow: File menu -> choose original directory -> select actual files ->
  inspect candidate bytes -> confirm a new outside directory -> verify retained
  evidence -> separately confirm opening in a new window. Neither copying nor
  opening grants compilation authority. Drafts are retained, not applied.
- Reuse: deterministic migration core, checkpoint candidate/read/publish rules,
  CaptureLease, recovery byte reader, existing source/Block window installation.
  Pure verification remains in `app/core/project_migration.py`; orchestration in
  `app/gui/project_migration_dialog.py`. The existing File action/signals and close
  guard connect the workflow. No writer or universal session rewrite.
- CaptureLease temporarily pauses related existing writes. Closing restores
  unchanged pre-existing autosave requests; it does not disable ordinary autosave
  permanently. Published bytes and captured drafts describe the reviewed instant,
  not subsequent edits in the original window.
- Opening verifies manifest files, drafts, decision fields, every retained legacy
  original, and regenerated candidate equality. Confirmation is followed by a
  second read and final identity checks. Unknown/changed/inconsistent evidence
  refuses opening. Digests establish consistency, not authenticity.
- If conversion replaces an old path such as main.tex, its old source draft is
  detached from that path in the new copy. Original target is retained in the
  decision report; subsequent recovery must use an independent explicit target.
  Old raw LaTeX stays verbatim and untrusted, deliberately absent from FINAL.
- Branch `codex/v1-development`; HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`.
  App Python path/content SHA-256:
  `d9756e68f9336be479fe4c59ec6955ff0ac0191dad468a42575e6687d34d007f`.
  Frozen app+tests SHA-256:
  `67494aa28692d7a3b4473a37b40fcf69a5500ad6ef9a4e344072abe287a3046d`.
- Environment: macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1. Every GUI
  check here used `QT_QPA_PLATFORM=offscreen`, isolated settings and synthetic
  files. No Cocoa window, desktop focus or physical mouse/keyboard action.

## Executed evidence

Focused command, exit 0: 21 tests, 3.931s; exec 69815 terminal.

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_block_migration tests.test_project_migration_gui tests.test_ui_visual.WorkbenchVisualSmokeTests.test_migration_review_and_open_controls_fit_large_font -v
```

Log: `/tmp/icstex-v1-m4-migration-gui-focused-r2.log`. Covers separate default-No
confirmation, cancellation, selection invalidation, omitted metadata refusal,
source/evidence changes during confirmation, independent source/Block drafts,
owner closing during a worker, one active reader, publication winning cancellation,
legacy draft target detachment and large-font scrollable control reachability.

Expanded command, exit 0: 131 tests, 34.606s; exec 86827 terminal.

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_block_migration tests.test_legacy_conversion tests.test_project_migration_gui tests.test_project_checkpoint tests.test_project_checkpoint_gui tests.test_project_recovery tests.test_project_recovery_gui tests.test_block_write_recovery tests.test_block_write_recovery_gui tests.test_layout tests.test_layout_renderer tests.test_ui_visual -v
```

Log: `/tmp/icstex-v1-m4-migration-gui-expanded-r1.log`. Required compileall and
`git diff --check` passed. Offscreen propagateSizeHints/font alias messages remain;
temporary fixture source-read warnings are not presented as native acceptance.

Product command, exit 0; exec 9323 terminal:

```bash
QT_QPA_PLATFORM=offscreen python3 tools/probe_project_migration_gui.py --output /tmp/icstex-v1-migration-gui-20260911-r4
```

Actual File actions, scrollable dialogs and default-No confirmation buttons are
driven by offscreen widget events. Directory paths are supplied to the dialog's
loader; native pickers are not exercised. Ordinary multi-file, current Block and
known legacy projects each complete publish -> cancel opening -> confirm opening
-> explicit FINAL -> close -> reopen -> explicit FINAL. Real PDF text and visible
viewport ink are checked. Original selected bytes, GBK/CRLF, separate drafts and
candidate bytes remain equal after both builds. Legacy left/right captions render;
untrusted unknown snippet text does not. No appearance equivalence to an old PDF
is claimed. Current-format copies preserve bytes; they do not convert documents.

Result and screenshots:
`/tmp/icstex-v1-migration-gui-20260911-r4/result.json`;
log `/tmp/icstex-v1-m4-migration-gui-product-r4.log`.

| Synthetic case | Selected output files | Opened and reopened FINAL SHA-256 |
| --- | ---: | --- |
| Ordinary multi-file | 5 | `89dd8361cbeb66c87b2ac7b1ce0ebc730d4c058248bcb5f4ab76b1ab3cf4f114` |
| Current Block | 8 | `2799fcd4e5b1603898cd540913d6475fb8f38b33e34006f793988c949b15bc25` |
| Known legacy | 12 | `c352bb6a847a25696e5928bcce4e62e701f4a9c7fb7502216c5bf46359d0f058` |

Matching PDF hashes here describe these runs, not cross-environment reproducibility.
Screenshots inspected: legacy opened model, candidate byte comparison and FINAL.
The compact PDF pane shows only a viewport; full caption text is checked through
QPdfDocument, not inferred from clipped screenshots.

## Failed probes retained

- r1 / exec 77624, exit 1: after migration closed, the Block owner's pre-existing
  500ms autosave resumed during subsequent copy compilation. Byte diff shows the
  owner's independent model draft was saved. The synthetic Block owner had not
  deferred autosave like source-owner fixtures. r2 onward sets its timer interval
  to one hour before editing; original-byte assertions are retained before and
  after builds. This is fixture isolation, not a production autosave change.
- r2 / exec 40528 and legacy-only r3 / exec 11677, exit 1: the shared probe's
  fixed scroll left black captions below the PDF viewport. The retained r3
  `legacy-failure.png` visibly renders the blue images (their darkest lightness
  is 102, outside the existing <100 ink predicate). A diagnostic attribute typo
  also obscured r3's final diagnostic; it is fixed. The shared helper now has an
  opt-in bounded actual scroll scan; pixel threshold and PDF text assertions are
  unchanged, and existing callers keep their default behavior. r4 passes all cases.

## Frozen full regression and remaining limits

```bash
nice -n 10 env QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
```

PASSED: 1384 tests in 1208.224s, OK / exit 0; exec 2446 / PID 47068 terminal and
closed. Log `/tmp/icstex-v1-m4-migration-gui-suite-r1.log`. App and app+tests hashes
listed above were verified unchanged after terminal completion, before applying
the subsequent M5 delivery-core increment. This result does NOT cover that newer
source. Live check after 36s confirmed nice 10; load then 8.87/9.05/9.95. Slow scale
tests remained active rather than being restarted on observation timeouts. This
full-run duration is not a performance acceptance result.

Native QA was paused for the initial runs and is now explicitly reauthorized.
The follow-up below does not provide Windows, full native IME/AX,
power-loss, real cloud placeholder or human usability acceptance. Only selected
locally readable files are covered; dependency and cloud completeness stay unknown.
Published-copy totals remain bounded; no in-place recovery or automatic journal
cleanup. The retired in-place migration runner remains a no-write refusal.

No commit, push, package, installed-app replacement, signing, deployment or release.
The local ignored Beta feed remains
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`;
installation-lifetime exclusion and all independent release gates stay open.

## Native follow-up after explicit foreground authorization

On 2026-09-11 the user explicitly allowed foreground window control again.
Changed only this probe and status/evidence documents, not app/ or tests/.
The default remains offscreen; native launch requires both `--native` and
`QT_QPA_PLATFORM=cocoa`. Bounded observer pauses permit real external AX reads.
Three mismatched-platform invocations refused before QApplication creation or
output-directory creation. No installed application or student project was used.

Source identity for this follow-up, unchanged before/after the run:

- App Python path/content SHA-256:
  `d4f6e35fdbd71f6a1b6eadac7817058e013e50cc47bbd066b2d4e0359524764c`.
- App+tests SHA-256:
  `89cc72ac67066e7dce6368e948ac1bda5b8b73777b3deb05ca3b0349595f22d3`.
- `tools/probe_project_migration_gui.py` SHA-256:
  `0426d09133ab839e180b7645e4b2dfa14bdb309c92a29b283b98be6452c14742`.

Focused command above passed again: 21 tests in 10.418s, OK, exit 0;
exec 15991 terminal, `/tmp/icstex-v1-m4-migration-native-focused-r1.log`.
Compileall and diff checks passed. Default offscreen multi-file product passed:
exec 22361 terminal, exit 0; `/tmp/icstex-v1-m4-migration-offscreen-r5.log`,
`/tmp/icstex-v1-migration-gui-offscreen-20260911-r5/result.json`.

```bash
QT_QPA_PLATFORM=cocoa python3 tools/probe_project_migration_gui.py --native --observe-ms 5000 --output /tmp/icstex-v1-migration-native-20260911-r1
```

PASSED, exit 0; exec 3227 / PID 54017 terminal and closed. Environment remains
macOS 26.6.1 arm64, Python 3.12.6, Qt 6.11.1, actual cocoa backend. Log:
`/tmp/icstex-v1-m4-migration-native-r1.log`; result and native widget screenshots:
`/tmp/icstex-v1-migration-native-20260911-r1/result.json` and its parent directory.

All three cases follow the actual File action, selected-byte review, default-No
publication confirmation, cancel opening, separately confirm opening, explicit
FINAL, close, reopen and explicit FINAL. Ordinary copying is additionally cancelled
before publication. Original bytes and independent owner drafts remain intact.
Legacy raw LaTeX stays untrusted; both image captions exist in the real PDF, while
the untrusted snippet does not. Model loading and preserved evidence were checked.

| Synthetic case | Files / drafts | Opened and reopened FINAL SHA-256 |
| --- | ---: | --- |
| Ordinary multi-file | 5 / 1 | `7cfb7f11cf4ac30cb81118cfbe3a46aa105f167b9ff1e602ab66633b93857e11` |
| Current Block | 8 / 1 | `0e1ab4c69528aea7c84ea94cc9ad068cd90af1a9ec1c7a95229b35797a406b0e` |
| Known legacy | 12 / 1 | `cd533f3f277d94bfc1a15ec88f0260d7201161f1ad2c968a5ff59526b7a933fe` |

Native screenshots inspected: ordinary byte review, ordinary FINAL, reopened
Block FINAL and legacy FINAL. The enlarged narrow Block PDF viewport clips some
text horizontally; complete expected text is checked using QPdfDocument, not
inferred from the screenshot. No old-document visual equivalence is claimed.

Five external CUA app/AX-tree reads returned during ordinary review, an ordinary
owner window, Block publication, legacy review and legacy FINAL. The version-scoped
selected-children mitigation was active. Python `.ips` inventory was the same four
existing files before and after this run, newest `Python-2026-09-11-093624.ips`;
no new Python crash report was observed. These samples do not prove full AX safety.
Stderr retains `IMKCFRunLoopWakeUpReliable` mach-port and missing `Sans-serif`
font-alias warnings. Neither is silently classified as fixed.

QTest drove only the probe's widgets; no physical keyboard/pointer or native
directory picker was tested. Full IME/AX, Windows, cloud placeholders, power-loss,
human usability and release remain unverified. The required full regression for
the newer M5 source was not run here; the earlier 1384-test result remains tied to
its original d9756e68 source. No full run is live. M5 caller integration remains next.
