# M5 Agent/MCP export: bounded repairs and remaining provenance gap

Status: the original five AgentWorkspace export defects have focused red/green,
actual synthetic Agent/MCP and frozen full-regression evidence. A further warm
FINAL cache substitution defect is repaired and passes focused, actual PDF and
Cocoa GUI verification. Its new full run crashed in Qt stylesheet application;
an unchanged-source diagnostic rerun passed 1444 tests, but the crash remains
undiagnosed. This is not full M5/M6 or release acceptance.
Subsequent closed-window retention diagnosis/repair is recorded separately in
`v1-m6-window-lifetime-verification-2026-09-11.md`; its green tests do not establish
that retention caused the original SIGSEGV. This receipt retains its own source.
Build-time tool-version evidence, full platform/native/human acceptance and all
independent Beta release gates also remain open.

## Implemented scope

- PDF export uses the actual `CompileResult`, FINAL job identity, captured input
  observations and current PDF bytes. It no longer reconstructs proof from the
  wire dictionary or blindly copies a path. Saved root/profile/Block metadata
  context is captured and rechecked, including previously absent files. Pending
  Block write journals refuse export before compile or assembly.
- Exact PDF bytes are staged, fsynced and read back, then current inputs/PDF and
  authorization/stop intent are checked before exclusive publication. A late
  existing file or symlink is preserved. The short existing compile lock orders
  cancellation against publication; it is not held over compilation or reads.
- The portable exporter captures bounded source/material bytes, filters known
  private names, virtual environments, history and caches, and rejects partial
  inventories, key markers and detected changes. Original README, manifest,
  encoding and line endings are preserved. Generated metadata lives under
  `.icstex-package/`; old root aliases are emitted only when unoccupied.
- The existing Python empty-staging-directory contract is retained explicitly;
  nonempty or late-created targets are not overwritten. MCP uses the stricter
  absent-target mode and the shared owned-stage/exclusive publisher directly.
  Existing empty staging directories can change inode; this is not an inode
  preservation or OS-atomic external-writer guarantee.
- Auto engine selection honors existing declared Magic engines and recognizes
  only the exact saved generated Block root for the established XeLaTeX default.
  Persisted partial/default DocumentTheme overrides are accepted without relaxing
  full theme-template validation or allowing unknown formats/fields.
- Existing MCP tool names, parameter/result fields, capability gates, project
  lock, compile cancellation and GUI/MCP write exclusion are retained. This
  legacy package API does not provide the GUI's per-file review, M1 check report
  or a privacy/academic certification. No source content is uploaded.

## Source and environment

macOS 26.6.1 arm64; Python 3.12.6; PySide6/Qt 6.11.1. Synthetic projects only,
with local TeX tools and no installed-app, student-file or release mutation.

Agent-only frozen app SHA-256:
`4f78576603a4788a0c5937f893b5f9a6e06ec8fc099f9bde86e8525bbcc4d6f8`.
Agent-only frozen app+tests SHA-256:
`ed851a3b7287f8afea8a34d268d2be6c25ec6cdff7744e87db8eabc2055761b3`.
The digest feeds sorted relative Python paths, NUL, raw bytes, NUL, app then tests.
HEAD remains `3bde2b5d25803262dedef89a081ee6ffbe2b6967`; changes are local and
uncommitted, with no automatic commit/push authority in this development task.

## Test receipts

Required compileall passed before the freeze. Expanded focused regression:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_export_package tests.test_agent_export_integrity tests.test_agent_workspace tests.test_agent_concurrency tests.test_mcp_server tests.test_project_checkpoint tests.test_submission_delivery tests.test_demo tests.test_theme -v
```

129 tests in 8.301s, OK, exec 20354 terminal/exit 0. Log:
`/tmp/icstex-v1-m5-agent-export-expanded-r2.log`.
Shared GUI/checkpoint/recovery/migration/delivery regression: 68 tests in 11.650s,
OK, exec 37255 terminal/exit 0; log
`/tmp/icstex-v1-m5-agent-shared-gui-r1.log`.

Earlier red receipts are retained: six PDF tests reproduced unsafe behavior;
package red run had three failures in eight tests. Initial implementation r1
self-deadlocked by reacquiring the non-reentrant compile lock; PID 61631 was
terminated, exit 143, and is not counted as a pass. A locked-only intent check
removed the nested acquisition. Actual Block export then exposed Auto/pdfLaTeX
selection and overly strict persisted-theme validation; both were fixed and
rerun. Logs retain these failures, not just the final green runs.

Required full regression: exec 44063 / PID 64609, started
`2026-09-11T05:32:28Z`, nice 10:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
```

TERMINAL/PASS: 1443 tests in 392.115s, OK, exit 0. Log
`/tmp/icstex-v1-m5-agent-export-suite-r1.log`, SHA-256
`9392561dac8c9b69112d1f872c15eded52044046c1544258cc97379d20087a38`.
Both source hashes matched after terminal collection. No Traceback/RuntimeError/
failure record found; offscreen warnings retained. This handle is closed and
covers the Agent-only source, not the later compiler correction.

## Actual product and stdio MCP evidence

`tools/probe_agent_delivery.py --output /tmp/icstex-v1-m5-agent-delivery-20260911-r5`
finished with exec 5409 / exit 0 on the frozen source above. Result SHA-256:
`2f7da95c2bb4e23a4b40ad6b0420d4a4f694a0691a811cd0f77ff99a302584f9`.
Probe SHA-256:
`49f76cfa23d76193f913a548167fb0a4290a5eb1b979450a1e18b65088071d48`.

Single-file, multi-file and Block projects completed actual FINAL/PDF export,
source export, exact manifest/source-byte checks and independent exported-source
XeLaTeX recompilation with expected PDF text. Actual post-FINAL input mutation,
late target creation and source changes during package staging were refused.
Synthetic private-name placeholders were excluded; no real keys were read.

Actual stdio MCP calls for ordinary and Block projects checked default compile
denial, explicit compile grants, PDF/package export, inspect, existing-target
refusal and the unchanged 11-tool schema. Expected denial error logs are not
unexpected test failures. Different independent-build PDF bytes are not treated
as a reproducibility failure or claimed identical across environments.

The shared four-case GUI probe also finished: exec 47846 / PID 64872 / exit 0,
result `/tmp/icstex-v1-m5-agent-shared-delivery-gui-20260911-r1/result.json`.
All four actual offscreen Save/FINAL/review/cancel/PDF-only/source-report flows
preserved originals and matched previewed/delivered bytes; exported sources and
restored checkpoints recompiled. This run is not Cocoa/IME/AX/native-picker or
Windows acceptance. Its generated limitation string about MCP refers to the
separate acceptance boundary, not proof that the old copier is still present.

## Warm-FINAL cache defect and bounded repair

While app/tests were frozen, `tools/probe_final_cache_identity.py` built two valid
synthetic PDFs, replaced the expected project's cached PDF with the unrelated
one, retained the original mtime, and called actual AgentWorkspace PDF export.
The export succeeded with `UNRELATED SYNTHETIC PAPER` in the delivered PDF.
This is a defect receipt, not an acceptance pass:
`/tmp/icstex-v1-m5-final-cache-20260911-r1/result.json`, SHA-256
`e71c35f21184b50f8dc86504e4a1ec7e3c677363b7cbe947ef9be3507d6eb707`.

Root cause: FINAL invokes latexmk with ordinary incremental-cache behavior.
Capturing matching source/PDF hashes after a no-op driver run does not prove that
the PDF was produced from those inputs. This affects the shared compiler, not
just MCP. Next repair must preserve PREVIEW caching, timeout/stop behavior and
the current output paths while ensuring FINAL actually rebuilds. Local latexmk
help and the [upstream manual](https://tug.ctan.org/support/latexmk/latexmk.pdf)
document `-g` as running each rule at least once; unlike `-gg`, it does not request
a preliminary clean. The compiler now inserts `-g` only for latexmk FINAL;
direct-engine calls and PREVIEW remain unchanged. No output-directory cleanup,
failure suppression, project hooks or shell escape was added. This trades a
true FINAL rebuild for warm-driver no-op speed; it is not a cross-environment
reproducibility or adversarial external-writer guarantee.

Current app SHA-256:
`d0a7012904829a786d3d21aa7950abfda7d4fc441afc9ac440bb9dea494f5ac6`.
Current app+tests SHA-256:
`85806c1ce44006ed4178d8fc9c3f29706c7c632cdf263f6a82d8b87493283a4e`.
One new command regression failed before the fix and passes after it, covering
FINAL/PREVIEW and direct/latexmk drivers without weakening safety flags or
deleting cached output. Focused compiler/toolchain/Agent/concurrency/delivery/
check regression: 130 tests in 6.498s, OK, exec 68509 / exit 0; log
`/tmp/icstex-v1-m5-final-cache-focused-r1.log`. Compileall and diff check passed.

Actual Agent/stdio acceptance r6 repeated the three project workflows and both
MCP routes on the new source: exec 35389 / exit 0, result
`/tmp/icstex-v1-m5-agent-delivery-20260911-r6/result.json`, SHA-256
`eb2eba3903946bcf4f7ff7123dda82d82bcfe06ebd6efebf99200a6dfa883dc6`.
The original two-PDF probe r2 now exports `EXPECTED SYNTHETIC PAPER`, not the
substituted unrelated PDF. Stronger `--expect-fixed` r3 also changes the source
with the same byte length and mtime and verifies `REVISION SYNTHETIC PAPER`:

- pdfLaTeX result `/tmp/icstex-v1-m5-final-cache-pdflatex-20260911-r3/result.json`,
  SHA-256 `46e88247077e2a0b708a1169f87335266c95d7e5845faa9477ac0921ce5531ce`.
- XeLaTeX result `/tmp/icstex-v1-m5-final-cache-xelatex-20260911-r3/result.json`,
  SHA-256 `9438775252aa7edc26552018cfd60e204f78fa49f80ed943416b4ba7ed735e16`.
- LuaLaTeX fails in local `luaotfload-multiscript.lua:70` initialization under
  restricted I/O. An otherwise equivalent direct latexmk command **without**
  `-g` also exits 12 with engine returncode 255; baseline log
  `/tmp/icstex-v1-m5-lualatex-no-force-r1.log`. It is not a passed engine case or
  evidence that the new flag caused the failure. No system TeX repair, relaxed
  I/O policy or package installation was attempted. Combined three-engine exec
  22443 ends exit 1 because this case fails; two produced results above are
  bounded successes, not an overall green three-engine run.

Current Cocoa product verification: all four single/multi/main Block/standalone
Block flows passed, with actual Save/FINAL/review/cancel/publication, exact bytes,
external-source recompilation and checkpoint recovery/recompilation. Exec 83942 /
PID 66842 ends exit 0, source digest matches, result
`/tmp/icstex-v1-m5-final-native-20260911-r1/result.json`, SHA-256
`90e2a37b87409c56e382ea82a846d051fb65f909d51844a654e3ecb537cd0227`.
Published multi-source and standalone PDF screenshots were inspected. The windows
closed; no AX scan, physical input or full-page layout acceptance was performed.
The existing narrow Cocoa AX mitigation warning remains.

## Full-regression native crash: open quality gate

Final-source full r1, exec 51729 / PID 66375, exits 139, not a pass. Log
`/tmp/icstex-v1-m5-final-cache-suite-r1.log`, SHA-256
`e41595fcf58eb8a57bc40b087473e605c2dbaf6347d49730923af462ea26b865`.
Last test was `test_ui_scale.ScaleManagerTests.test_font_scales_from_base_without_drift`.
The new crash report `Python-2026-09-11-134542.ips` identifies PID 66375, SIGSEGV /
EXC_BAD_ACCESS at 0x30, QtWidgets and `Sbk_QApplicationFunc_setStyleSheet` on the
main thread. This is the offscreen full-test process, not the successful Cocoa
product process. Matching app/tests hashes were rechecked after both terminal
results. Earlier source's green full run does not close this new observation.

The unchanged-source full rerun completed with `PYTHONFAULTHANDLER=1`, nice 10,
exec 99478 / PID 67357, started 2026-09-11T05:46:57Z; log
`/tmp/icstex-v1-m5-final-cache-suite-r2.log`. TERMINAL/PASS: 1444 tests in
390.908s, OK, exit 0. Log SHA-256
`e3b6687155c54eca1326f98c4dd0e875e73461b20ce536727ef8639c88be569b`.
Both current source hashes match after terminal collection; compileall and
diff checks pass again. No Traceback/RuntimeError/failure record was found in
the rerun; offscreen warnings remain. The five-report Python crash inventory
has no further addition after the r1 report. No full/native process remains
active; all known handles are closed. Isolated `tests.test_ui_scale` also passes
9 tests in 1.523s, exec 38656 /
exit 0, log `/tmp/icstex-v1-m5-scale-isolated-r1.log`.
Do not poll/restart these completed handles. A green rerun alone is not proof
of a diagnosed/fixed native lifecycle bug; the M6 gate remains open.

The immediate diagnostic boundary is Qt application-wide stylesheet repolish
with a long-lived shared test QApplication. Earlier whole-suite runs had retained
widgets and expensive stylesheet work; this is a candidate for controlled
isolation, not an established cause. The crash has not been reproduced by the
isolated scale module. Do not disable scale assertions, install a global Qt patch
or label it a production memory leak from this evidence alone.

Read-only Git verification after these checks confirmed HEAD and remote
`codex/v1-development` both at `3bde2b5d25803262dedef89a081ee6ffbe2b6967`,
remote `release/2.1` at `f03776e87c0f938421a70ff5b085db920f2d01d7`.
Index remains empty; later changes are uncommitted. Ignored signed candidate
feed SHA-256 remains
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
No commit/push, package/install, signing/deployment/release or student-file edit.
