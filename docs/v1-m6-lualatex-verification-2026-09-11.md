# M6 restricted LuaLaTeX diagnosis and visible failure diagnostics

R5's installed-engine failure is now diagnosed, and its missing GUI error has
been repaired. **Restricted LuaLaTeX compilation still fails on this host.**
This is not complete engine, A12/M6/V1 or release acceptance. No security policy,
system dependency, installed application, student document or release changed.

## Source and environment

Branch `codex/v1-development`, HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`; shared changes remain uncommitted.
Baseline app `43816cb0a8f221e5b1ffbf18f1cfe96bf98529ef7351be7d818cb752618d8b6d`.
Final app `bc2a7b3e00f62f2e0114d1cba4804a60844756c27ab6a6bfcf97a32e43e43f74`;
app+tests `e6279c2075db371aec0115eeeed20a483064bc09aff9a1168a5e959d1fcddb67`.
Digests use sorted relative Python paths, NUL, bytes, NUL, app then tests.

macOS 26.6.1 arm64, Python 3.12.6, PySide6/Qt 6.11.1; UI verification is
offscreen only. Installed `/Library/TeX/texbin` resolves TeX Live 2025;
latexmk 4.86a, LuaHBTeX 1.21.0 and luaotfload 3.29 (2024-12-03).
The detector's `existing-usable` means required executable paths exist, not
that every engine successfully compiles. No Tectonic compile/download was run.

## Local causal evidence

`tools/probe_lualatex_restricted.py` creates fresh synthetic projects, invokes
actual `CompileManager` FINAL builds, then isolates primitive Lua file reads.
It never installs packages, runs an unrestricted comparison or changes TeX
configuration. All three project sources remain byte-identical.

| Check under unchanged `openin_any=p`, `openout_any=p` | Observed result |
| --- | --- |
| pdfLaTeX FINAL, relative entry/output, `-norc`, `-no-shell-escape` | Success, PDF generated |
| XeLaTeX FINAL, same restrictions | Success, PDF generated |
| LuaLaTeX FINAL, same restrictions | `latex_error`, latexmk exit 12, no PDF |
| `kpsewhich -safe-extended-in-name` / primitive Lua `io.open`, absolute installed ScriptExtensions.txt | Exit 1 / `open=false` |
| Identical bytes copied only into the synthetic project, relative local-copy.txt | Exit 0 / `open=true` |
| Synthetic `../sentinel.txt` outside project | Exit 1 / `open=false` |
| Primitive Lua `status.shell_escape` | 0 |

The installed resource is present and readable by the diagnostic host process:
`/usr/local/texlive/2025/texmf-dist/tex/generic/unicode-data/ScriptExtensions.txt`,
SHA-256 `049117ce26b9769fe2749b06eef51a50a89faef4a97764dd2d81daa715980700`.
The installed `luaotfload-multiscript.lua` lines 69–71 call
`io.open(kpse.find_file("ScriptExtensions.txt"))`, then `f:read` without checking
the rejected open. Its line-70 nil-`f` error matches the actual failure log.
The synthetic copy is a diagnostic contrast, **not** a shipped workaround.
The original resource and synthetic sentinel/copy remain unchanged after reads.

This establishes the local restricted-read/loader mismatch, not a missing
Unicode file or student-source syntax error. The earlier no-`-g` run also
failed; forced FINAL is not its origin. It does not establish unrestricted
LuaLaTeX health, arbitrary Lua access safety, or other TeX releases' behavior.

The existing boundary matters: MCP compilation explicitly requests restricted
I/O; ordinary GUI managers default to `restricted_io=False`. Only the synthetic
GUI fixture is tightened to exercise this protected result through the normal
window pipeline. Neither production policy is changed. See SECURITY.md and
DECISION_LOG.md D015. The compiler's overly broad distribution-read comment is
corrected; there is no executable compiler change in this slice.

## Product repair and verification

Previously `CompileResult` reported failure but its errors were empty: the log
parser only handled `!` and TeX file/line errors. It now recognizes an exact
luaotfload fatal header and bounded details, joins its quoted detail's log wraps,
deduplicates repeated messages and stops before a subsequent error/traceback.
The loader's Lua line number is not assigned to the student's source.

The diagnostic explains the font component failure in Chinese, retains raw
detail, has no source location or automatic fix, and never changes the engine
or read restriction. Core tests cover header-only, non-error/quoted text,
duplicates and wrapped details; MainWindow regression retains the old PDF's
non-current state and leaves source bytes/cursor/scroll unchanged.

Final-source actual protected compile and offscreen MainWindow check:

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 \
  tools/probe_lualatex_restricted.py --verify-gui \
  --output /tmp/icstex-v1-lualatex-restricted-r5
```

Exec 92330 ended at exit 0. This means diagnostic assertions passed, **not**
LuaLaTeX compiled successfully. Workspace and PDF both settle to failure; one
visible Chinese diagnostic retains `multiscript.lua:70` and the nil-`f` detail.
Fix is disabled; source/model authority, cursor/scroll, engine and policy remain
unchanged. The probe expands its own diagnostic area/columns for inspection,
not production layout. Synthetic window cleanup runs; no foreground control.

Report `/tmp/icstex-v1-lualatex-restricted-r5/report.json`, SHA-256
`20a9f3c31bff13fbfe57ddca65c679010295e7ed78f8ce1d4a7811979c84ecb0`.
Inspected `diagnostic-window.png`, SHA-256
`4c565525126c1cf34773a20f79d225fc8e7160516fd84dffd60928e864d33a3c`.
Probe SHA-256 `b27383abf3486ab89c717c0b68382cdefab56c0282fe3e80f5a21bebe1052264`.

## Regression receipts and retained unsuccessful attempts

Fatal recognition first failed 3 assertions; the real wrapped-detail regression
then failed on the truncated path. Wrap red log
`/tmp/icstex-v1-lua-wrap-red-r1.log`, SHA-256
`f1488d34709c34278415b84ddc76048ef3f9ccdb1503f912f6a6ecc6a408360e`.
Focused command:

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_log_parser tests.test_diagnostics \
  tests.test_gui_editor.GuiPdfStateTests tests.test_compiler -v
```

91 tests / 15.561s / OK, exec 91383 exit 0; log
`/tmp/icstex-v1-lua-diagnostic-focused-r3.log`, SHA-256
`a926fe37b2f09f62360473c652fc89f52423f9f63d779ee86570be4e79ed395d`.
That run used app `1ae224b548e36afb8c94f6d5421d9e42075bff5ac4ac5371a60b2a3932e808ac`;
only the compiler comment changed afterward, with final-source checks below.

The latex-doctor restricted pdfTeX helper failed because it passed an absolute
temporary entry, which paranoid mode rejected. Its `/tmp/icstex-v1-latex-doctor-r1.log`
is not a pdfTeX product failure; the app's relative-entry probe passed. Initial
raw Lua r1 lacked INITEX catcode setup and had no completed read observations;
corrected r2 completed them on baseline app 43816cb0. GUI r3 assertions passed,
but screenshot preceded the workspace debounce and clipped the row. r4/r5 wait
for the settled state and verify row visibility. A first GUI unit assertion
incorrectly expected the export menu disabled; M5 intentionally opens review,
not direct publication. Its corrected assertion checks non-current PDF state,
not complete export acceptance. None of these earlier runs is relabelled.

Required commands:

```sh
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10 python3 -m unittest discover -s tests -v
git diff --check
```

Frozen final-source full: **1495 tests / 121.819s / OK**, exec 74763, explicit
shell/tool exit 0; `/tmp/icstex-v1-lua-diagnostic-suite-r2.log`, SHA-256
`3fe2103c6564fd236daebeb758c2114c49cb279dfe431c4831c7611f97e6d045`.
Post-terminal app/app+tests digests match; compileall/probe syntax/diff pass.
No Traceback/RuntimeError/RuntimeWarning/fatal failure in the full log; expected
offscreen warnings remain. The prior full r1 also passed 1495 / 121.879s at
exec 12544 exit 0, but the comment changed during it; it is not the frozen
final-source receipt. All this slice's process/probe handles are terminal.

The five prior September 10/11 Python crash reports remain unchanged in count
and names; no new crash was observed, not proof that their causes are fixed.
Held candidate feed SHA-256 remains
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.
Index is empty; HEAD unchanged. No installed/public artifact claim is added.

## Remaining boundary and next action

R5 diagnosis and error visibility are addressed locally; **engine compatibility
remains open**. Do not relax `openin_any`, redirect global TeX output, patch the
installed Lua loader, bundle distribution data or silently switch engines.
A compatibility change affecting D015 requires a bounded security/platform
decision and independent boundary tests; this slice does not make that decision.

Next safe background slice is R3's historical Qt crash triage/disposition. R2
physical Inspector focus after unlock, R1 remaining input/default idle-save
combinations and final-source formula partial commits remain. R6/M7 must retain
these gaps and E1–E4. No commit/push, package/install, signing or publication.
Rollback only this fatal parser/diagnostic, targeted tests/probe and comment;
preserve unrelated shared hunks. Suggested commit, not executed:
`fix(diagnostics): surface restricted LuaLaTeX font-loader failures`.
