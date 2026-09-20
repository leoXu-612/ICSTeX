# M5 build-time version labels

Status: driver/engine version labels are captured from actual FINAL stdout and
retained in the immutable reviewed report. Focused tests and three real synthetic
compile/delivery/restore workflows and the required frozen full regression pass.
This bounded slice is closed; it does not complete M5/M6 or release acceptance.

## Scope and evidence boundary

`app/core/build_tool_versions.py` performs a pure parse of at most 64 Ki characters
of fresh process stdout. It accepts only the initial latexmk startup banner and
the expected engine's first command/startup boundary, or a direct engine's first
nonempty line. It retains allowlisted program names, bounded numeric version
tokens and recognized distribution labels, not raw output or local paths.
Unrecognized wrappers, wrong engines, missing/cut-off banners and missing older
build evidence remain unknown. Document-body banners cannot replace the initial
engine version. PREVIEW does not populate FINAL evidence.

CompileManager captures these labels with the existing request key/revision and
build id. FinalBuildEvidence retains the immutable value; submission review and
publication share the same report bytes and reject changed proof. No additional
tool execution, cached `.log` lookup, network, save, new grant or MCP wire field
is introduced. The initial parser red run failed because the module did not yet
exist; six parser cases subsequently passed, followed by the integration suite.

These are **self-reported labels**, not authenticated executable identity. A
process can write arbitrary stdout. In particular, latexmk resolves child
executables itself; configured tool paths do not prove which child binary ran.
The existing configured `toolchain` names therefore remain separate from
`build_tool_versions`. Auxiliary tools (including BibTeX/Biber and converters),
fonts and packages are not version-attested or bundled. Unknown versions do not
become passes and cannot be filled from the environment at report export time.

Rollback is confined to this new parser, optional internal result/evidence field,
report metadata and their tests/probe. Existing input/PDF guards, FINAL `-g`,
PREVIEW caching, source bytes, GUI lifecycle and prior M4/M5 changes are preserved.

## Verification

Environment: macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1, local TeX Live
2025. Only synthetic projects under `/tmp` were used. No foreground window was
needed for this core/report-only change; no native, Windows or human acceptance
is claimed by this run.

Source app SHA-256:
`d7d57520c5a1a26044ed70457df5ecc79d839707c8475f6dddf5a954658e3219`.
Source app+tests SHA-256:
`48066a6e4cbb26176dc0ce213fea8ade3dfaa91235c64d0c31fd154b6ffb38bc`.
Convention: sorted relative Python paths/NUL/raw bytes/NUL, app then tests.
HEAD is `3bde2b5`; these and preceding increments remain uncommitted.

- Focused: `QT_QPA_PLATFORM=offscreen python3 -m unittest
  tests.test_build_tool_versions tests.test_compiler tests.test_submission_delivery
  tests.test_submission_check tests.test_submission_delivery_gui -v`.
  94 tests in 8.026s, exit 0, exec 78727. Log
  `/tmp/icstex-v1-m5-tool-versions-focused-r1.log`, SHA-256
  `f39e3a29d41cee824f280af07cf814e07086246d4df8cfec054942dfa36684e3`.
  Covers one actual compiler process only, stdout versus cached log/stderr,
  immutable FINAL/revision versus PREVIEW, safe tokens/limits/unknowns, no
  export-time subprocess, reviewed/published equality and changed-proof refusal.
- Product: `QT_QPA_PLATFORM=offscreen python3 tools/probe_submission_delivery.py
  --output /tmp/icstex-v1-m5-tool-versions-product-r1`, exec 76869, exit 0.
  Single and multi/BibTeX compile with pdfLaTeX, Block with XeLaTeX. Each completes
  PDF-only delivery, selected raw-source/report publication, PDF text/byte checks,
  independent source recompilation and checkpoint restore/recompilation. Originals
  remain byte-identical. Report excludes the local project path and output hashes
  match the delivered bytes. Result
  `/tmp/icstex-v1-m5-tool-versions-product-r1/result.json`, SHA-256
  `c956a30bf39036f6b14775d33eecd9d8e8ff354c53290547c42590d84ca18a3d`.
- Actual reported labels: latexmk `4.86a`; pdfTeX
  `3.141592653-2.6-1.40.27`; XeTeX `3.141592653-2.6-0.999997`, TeX Live 2025.
  The multi-file build exercises BibTeX but does not claim its version was
  captured. Lua engine parsing has synthetic coverage, not live acceptance;
  the previously recorded restricted LuaLaTeX initialization failure remains.
- Compileall and diff check pass before source freeze. Full command:
  `QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10 python3 -m unittest
  discover -s tests -v`, exec 21755 / PID 73377, started 2026-09-11T06:28:39Z.
  Log `/tmp/icstex-v1-m5-tool-versions-suite-r1.log`; TERMINAL/PASS:
  1455 tests in 111.922s, OK, exit 0. Log SHA-256:
  `9d815a2f23705e92e398a6f53a812b0eb8dadba4ac06aff1500bdf9c0bc4eba6`.
  Both source hashes match after terminal; compileall/diff pass. No new
  traceback/RuntimeError/failure or Python crash report observed. Existing Qt
  offscreen plugin notices are not native GUI acceptance. All handles are closed.

Next: perform the remaining M2-M6 local acceptance audit, starting with the native image-picker
cancel/import/conflict/save/reopen/FINAL gap. Original Qt stylesheet SIGSEGV,
full AX/IME, Windows, performance, human usability and independent Beta release
gates remain open. No commit, push, packaging, install, signing or publication.
