# M5 frozen submission core: integration in progress

Status: this is the initial core receipt, at the historical source hashes below.
The later real GUI/standalone Block integration passes expanded and synthetic
offscreen/native checks; its frozen full regression passed 1421 tests. Current evidence
is in `v1-m5-delivery-gui-verification-2026-09-11.md`. MCP portable export and
build-time tool binary versions remain open. Neither receipt is complete M5 or
closure of all defects in `v1-m5-delivery-audit-2026-09-11.md`.

## Implemented core contract

- `app/core/submission_delivery.py` binds the M1 report/input identity, saved
  project bytes, root/revision, actual FINAL job/build/engine/PDF, profile digest
  and word target/count mode. It captures existing and absent inputs, rechecks
  content and signatures, and requires the same report before acceptance and
  before publication. Unresolved write journals refuse delivery without cleanup.
- Default output in a new outside directory is only the chosen PDF filename.
  Source and report are independent opt-ins. Non-pass/non-not-applicable checks
  require explicit acknowledgement, not a fabricated all-clear status.
- Selected source files retain exact bytes under source/. User README/manifest
  paths remain there; generated instructions/report use a separate namespace.
  The selection must cover known build inputs. Known Block/profile metadata may
  be explicitly selected for Block reopening; personal history, drafts, hidden
  internals and known sensitive names remain excluded. Metadata retains original
  local references; filename filtering does not prove content is non-private.
- Report fields are allowlisted: relative paths, hashes, version/build identity,
  count mode/target, check statuses and unresolved limits. Diagnostic free text
  and absolute local paths are not serialized. Build-time tool binary versions
  were not captured; their report values remain explicitly unknown, not invented.
- `project_checkpoint.py` factors existing staging/readback/source-check/exclusive
  directory publication into `_publish_payloads`. Recovery still adds its exact
  prior manifest/README; delivery does not inherit those recovery files. Existing
  cleanup and no-overwrite rules remain. Candidate inventory accepts an explicit
  suffix set for submission; checkpoint defaults remain unchanged.
- Caller still must bind live GUI identity/cancellation and use existing protected
  save/FINAL actions. The core does not save, compile, grant trust, apply drafts,
  open windows or change MCP capability/wire/multi-writer rules.

## Source and checks

App Python path/content SHA-256:
`d4f6e35fdbd71f6a1b6eadac7817058e013e50cc47bbd066b2d4e0359524764c`.
App+tests SHA-256:
`89cc72ac67066e7dce6368e948ac1bda5b8b73777b3deb05ca3b0349595f22d3`.
macOS 26.6.1 arm64, Python 3.12.6, local XeLaTeX/TeXcount. All GUI-related tests
offscreen. Required compileall and `git diff --check` passed.

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_submission_delivery tests.test_submission_check tests.test_project_checkpoint tests.test_project_recovery tests.test_project_checkpoint_gui tests.test_project_recovery_gui tests.test_block_migration tests.test_block_write_recovery tests.test_block_write_recovery_gui tests.test_project_migration_gui -v
```

118 tests, 22.693s, OK / exit 0; exec 28469 terminal. Log:
`/tmp/icstex-v1-m5-delivery-core-focused-r6.log`. Covers independent output choices,
source/README/manifest/non-UTF8 fidelity, explicitly selected metadata, private
name variants, unknown/preview/failed/dirty FINAL, same-mtime external changes,
optional-file and absent-input races, changed profile/PDF/image, pending journals,
cancel/partial staging/occupied targets/links, forged payloads and checkpoint/
recovery/migration caller regressions.

```bash
QT_QPA_PLATFORM=offscreen python3 tools/probe_submission_delivery.py --output /tmp/icstex-v1-m5-delivery-core-20260911-r5
```

Exit 0, exec 62018 terminal; log `/tmp/icstex-v1-m5-delivery-core-product-r5.log`.
Result: `/tmp/icstex-v1-m5-delivery-core-20260911-r5/result.json`. Three synthetic
projects complete actual FINAL -> PDF-only delivery -> selected source/report ->
independent TeX compilation from the exported source -> checkpoint restoration ->
real restored FINAL. Selected Block metadata reopens with the real model loader.
PDF text and exact delivered bytes, source README/manifest and non-UTF8 bytes,
profile/count report and original/restored file bytes are checked. TeXcount is the
actual count mode in all three cases. Core API calls are not GUI confirmation proof.

| Case | Selected source files | Delivered PDF SHA-256 |
| --- | ---: | --- |
| Single file | 5 | `86b9472175b574d5b2998694f84d661a876f6a1cf1d091e349b2b94cd8b15415` |
| Multi-file | 8 | `b3f0ab7e2790ae385a51055a2cff0cc4e85df4fcacc2f4ec6ddc15d515696801` |
| Block | 11 | `23c60f6de1c330dcbc8e78ec214bda1e8704affe6f4aafd60e94b4a7464fb357` |

Recompiled/restored PDF hashes differ and are retained in result.json; expected
text, source bytes and delivery identity were checked. This is not a claim of
cross-environment or timestamp-independent byte reproducibility.

## Revisions and unclosed work

- Focused r1 failed only because its expected mode string was `python`, whereas
  the established WordCountResult value is `fallback`; corrected without changing
  count logic. Later coverage includes transient TeXcount shadow-path details:
  bind real count mode/numbers/warnings, not a disposable path in raw details.
- Early product r1/r2 did not actually select README/ordinary JSON because the
  reused checkpoint inventory excludes them. Their README/manifest flag alone
  was insufficient evidence. Broadened only submission's suffix selection,
  asserted their inclusion, and reran actual byte comparisons. r5 also explicitly
  includes and reopens known Block metadata, rather than silently defining every
  source package as generated TeX only.
- A new failing regression proved a dependency could appear after the second
  report but before acceptance. Added a final absence/path check: same test
  failed with `OSError not raised`, then passed in 0.159s. Late pending-journal
  creation has an analogous refusal test. This is not OS-atomic exclusion of
  arbitrary noncooperating external writers.
- At this core checkpoint, export defects remained open until actual GUI/MCP
  entrances used the required guarantees. Standalone Block has no guaranteed MainWindow parent;
  AgentWorkspace currently passes an existing empty staging directory to the old
  portable exporter. Preserve those contracts while repairing the guarantees.
- No full run was live at this core checkpoint. The preceding M4 GUI full, exec 2446 / PID 47068,
  passed 1384 tests in 1208.224s with matching post-run hashes; it finished before
  these M5 edits and does not validate them. Complete GUI/caller integration and
  the required final current-source regression before claiming this slice complete.
- This core receipt used background-only checks. The user later reauthorized
  foreground control; the separate M4 migration Cocoa follow-up did not validate
  M5's then-unconnected GUI/export entrances. Later GUI/native evidence and full-run
  state are in the linked GUI receipt, not retroactively part of this core result.
  Native pickers/IME/AX, Windows, power-loss, cloud-placeholder and human usability
  acceptance remain open. No Git
  commit/push, application packaging, installation replacement, signing or release.
