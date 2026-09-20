# M4 reviewed project migration: core increment

Status: focused tests, synthetic filesystem/reopen/FINAL and final frozen-source
full regression pass. The subsequent migration GUI is not covered here. This is not
complete M4, V1, platform, native or release acceptance.

## Source and execution boundary

- Repository/physical cwd match the selected ICSTeX root.
- Branch `codex/v1-development`, HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`.
- App Python path/NUL/content/NUL SHA-256:
  `363673a32cbfa94e9e4007d82d9fb05d539883df46c8eae101ee8847919f52d2`.
- Frozen app+tests Python path/NUL/content/NUL SHA-256:
  `a32315d6dee15f9d0288fd99daacd8c9d9154b12ce529e583f08f24347956430`.
- Python 3.12.6, macOS 26.6.1 arm64; the product probe uses QCoreApplication and
  QPdfDocument, not a native window. All GUI regression uses offscreen.
- User's background-only instruction remains active. No foreground window,
  focus, mouse/keyboard automation, installed-app change or student data access.
- No commit/push/package/sign/deploy/release. The existing local-only Beta feed
  still hashes to `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

## Implemented core contract

`app/core/blocks/migration.py` converts only the known legacy envelope. Its two
historical version-1 plans are pure and independently repeatable; verified plan
markers do not skip the other plan. IDs use deterministic suffixes in the existing
ID shape, with zero creation-time components rather than fabricated timestamps.
Already migrated IDs survive. Known optional model defaults can be added without
dropping input values; original bytes retain the exact earlier representation.

Converted pairs keep Row layout; a containing Column also includes otherwise
unplaced Blocks, including raw snippets. Schema validation now accepts recursively
nested existing LayoutNode values, matching the existing model/solver/renderer.
It still rejects unknown fields and invalid nested children; no new document
format or universal layout model was introduced.

Unknown root fields are reported as unmapped and retained in original bytes.
New Blocks retain each legacy entry in `extensions.legacyInput`. Raw LaTeX text is
verbatim but `trusted=false`; generated TeX contains the existing blocked marker,
not executable snippet text. A successful synthetic FINAL therefore does NOT
mean these raw snippets were rendered or that the old document's appearance was
reproduced. This limitation must be explicit in the upcoming review UI.

`app/core/project_migration.py` captures a bounded selection in two byte passes
and rechecks identities. Ordinary/current Block copies preserve selected bytes;
known legacy conversion builds current metadata and generated TeX only in the
new candidate. Current Block metadata/generated-source conflicts, pending write
journals, missing selected Block images, ambiguous mixed metadata and unknown
formats are refused. The old in-place MigrationRunner refuses without even a
backup/log write; application callers were absent before this retirement.

Publication reuses checkpoint exclusive staging, readback, inventory validation,
source revalidation and no-overwrite directory publication. Targets must be
outside the original. Legacy copies additionally retain EVERY selected original
under `recovery-evidence/original/`; `decision.json` records relative paths,
digests, unmapped fields and paths regenerated in the copy. Drafts remain separate.
No operation moves originals, switches a window, grants trust or compiles.

Limits: input legacy JSON 4 MiB; selected/output files at most 2,000; independent
drafts at most 200; published files/evidence/drafts together at most 256 MiB.
The selection is not all dependencies, an independent backup guarantee, or proof
that cloud placeholders are downloaded. Unlisted data is not inspected or copied.
Two-pass/final observations are not an OS-atomic CAS against arbitrary writers;
power loss, Windows reparse races and real cloud-drive behavior remain unverified.

## Commands and evidence

```bash
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen python3 -m unittest \
  tests.test_legacy_conversion tests.test_block_migration tests.test_layout \
  tests.test_layout_renderer tests.test_project_checkpoint \
  tests.test_project_recovery tests.test_block_write_recovery -v
QT_QPA_PLATFORM=offscreen python3 tools/probe_project_migration.py \
  --output /tmp/icstex-v1-project-migration-20260911-r2
nice -n 10 env QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
git diff --check
```

Compileall, diff check, final focused/full runs and product r2 exited 0. Focused log:
`/tmp/icstex-v1-m4-migration-core-focused-r2.log`. The exact count/timing and full
run state are maintained in PROJECT_STATE.md. Product r2 result:
`/tmp/icstex-v1-project-migration-20260911-r2/result.json`.

| Synthetic case | Checked output | FINAL PDF SHA-256 |
| --- | --- | --- |
| Multi-file ordinary TeX | selected bytes, independent draft, actual compile and PDF text | `ee1f0cf73c8babb8915d9d6f7a66ebbde10261cea40e62c4ac77ab8d39d42804` |
| Current Block | exact copy, real model loader, FINAL text | `ef55342dd0d44252f73bbc8893785228cdcd4228d42453a39da46259e31dfd20` |
| Known legacy | original bytes/evidence, complete loader model, both image captions in FINAL; raw snippet blocked | `6b34c181f0168f4c565aabf37ba6dc4b09b9093dcb7690cdf4e61da708402b7c` |

Each generated PDF has one page. QPdfDocument text was checked; no visible GUI
or physical-screen rendering acceptance is claimed. Reinspection of each copied
project yields a byte-exact ordinary/current copy, not another legacy conversion.
Tests additionally exercise actual second publication, malformed metadata,
duplicate IDs/instances, same-mtime content changes, between-pass/late mutations,
cancellation, disk failure, occupied targets, links, journals and candidate tampering.

Initial red test log: `/tmp/icstex-v1-m4-legacy-conversion-red-r1.log` (converter
absent). The first implementation run exposed layout int/float normalization in
the strict preservation comparison; the layout-only comparison now accepts equal
schema-validated numeric values, without relaxing Block value preservation.
Product r1 exited 1 because its assertion expected the blocked marker at byte 0;
the renderer correctly puts the standard BEGIN wrapper first. Probe r2 asserts
the entire expected wrapped blocked file, then completes all three cases.
Historical gap probe remains marked pre-fix-only; it is not a current acceptance
command. All product/focused/full handles are terminal. Full run exec `98240`, PID
`42233`, log `/tmp/icstex-v1-m4-migration-core-suite-r1.log` exited 0; the frozen
app/tests hashes were rechecked unchanged after completion. A one-second live
sample during the slow profile scale test was in QApplication.setStyleSheet;
`/tmp/icstex-v1-m4-migration-core-suite-sample-r1.txt`. This is not a new causal
performance diagnosis. Startup load 6.40/7.87/9.18, memory free
30%, nice 10; elapsed time alone is not a performance result.

## Next implementation, not accepted yet

The frozen full-run outcome is collected. The next increment connects a File-menu workflow:
select original project and file inventory, inspect an immutable selected-byte
candidate, show all output paths/unmapped fields/blocked raw snippets and exact
before/after content, confirm a new external target, and separately confirm opening
the verified copy. Reuse CaptureLease, one active worker/cancellation and existing
window/Block install guards; preserve actual dirty drafts. Before opening, verify
both the candidate manifest and the separately retained migration decision/evidence.
Do not label the current core API as an available GUI feature. Native QA remains
paused; offscreen UI/keyboard/close-race tests can proceed in the next slice.
