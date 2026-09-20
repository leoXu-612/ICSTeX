# R5 LuaLaTeX compatibility research

2026-09-12. **No tested candidate provides working restricted LuaLaTeX.**
The user authorized boundary-preserving compatibility research. The installed
engine still fails with paranoid I/O; adding `--safer` is explicitly rejected
by luaotfload. Upstream TeX Live 2026 makes `openin_any` ineffective, so an
upgrade alone cannot be accepted as preserving the existing read-name policy.
No application code, installed distribution or production policy changed.

## Verified local observations

The latex-doctor skill's supplied detection scripts found the existing TeX Live
2025 toolchain: LuaHBTeX 1.21.0, Kpathsea 6.4.1 and luaotfload 3.29. Detection is
not compile acceptance. Its generic smoke runner was not used: it can download
Tectonic resources and does not preserve this probe's stricter compiler flags.
The test-triage skill guided a small synthetic reproduction, not another full
regression. No foreground control or student project was used.

Both candidate subprocess environments come from the actual restricted
`CompileManager._compile_environment`, with `openin_any=p` and `openout_any=p`.
They run in fresh synthetic directories with relative input names. Direct
engine calls do not exercise latexmk or the full MCP delivery workflow.

| Candidate | Actual LuaLaTeX outcome | Primitive local read/write | Primitive external read/parent write |
| --- | --- | --- | --- |
| Existing restrictions, no shell escape | Exit 255; luaotfload multiscript nil file handle; no PDF | Allowed / allowed | Denied / denied |
| Same restrictions plus `--safer --nosocket` | Exit 1; luaotfload rejects safer mode; no PDF | Denied / denied | Denied / denied |

The raw LuaHBTeX checks also reject an absolute installed Unicode-resource read
and its output-name predicate. The latter is a filename check only; no write to
the installed distribution was attempted. Shell escape is reported disabled.
The safer run disables `io.open`, including the positive local-read case. A
primitive probe returning zero does not mean that its compatibility candidate
passed. Both report `candidate_compatible: false`.

The owned parent sentinel, synthetic source bytes and three inspected installed
resources retain their hashes. These bounded observations are not proof of a
complete Lua sandbox, symlink confinement, or denied access through every API.

## Upstream fact and its implication

TeX Live's pinned commit
[`84c5597d60805634f5a4ee0aebf59c2c769488f3`](https://github.com/TeX-Live/texlive-source/commit/84c5597d60805634f5a4ee0aebf59c2c769488f3),
dated 2026-01-06, changes Kpathsea's input-name checks to succeed unconditionally
and documents that `openin_any` no longer has an effect. This is specifically
the input policy, not removal of `openout_any`. The maintainer's
[earlier explanation](https://tug.org/pipermail/tex-live/2025-December/051965.html)
identifies OS isolation as the relevant boundary for arbitrary-file reads.

Therefore setting the same environment variable after an upgrade would not
establish equivalent protection. No TeX Live 2026 binary was installed or run;
this is pinned upstream-source evidence, not a local 2026 runtime result.
Tool presence/version detection alone does not test effective read confinement.

## Bounded next decision, not an accepted design

Propose an isolated macOS compiler-sandbox prototype, outside the product and
using only synthetic projects. First assess the installed OS mechanisms; the
local Apple `sandbox-exec(1)` manual explicitly marks that command deprecated,
so a passing experiment with it would not establish a supported shipping design.
No new helper, service, dependency, app signing or system installation is part
of this proposal. Windows remains a separate acceptance obligation.

The target boundary is read-only access to selected project/TeX/font inputs,
write access only to dedicated job outputs and caches, and no network access.
Retain disabled project hooks, no shell escape, existing cancellation/timeouts
and output-identity checks. Test real compiler reads/writes, symlinks, attempted
child execution and cancellation with synthetic sentinels before considering
any engine-read-policy adjustment inside the isolated experiment. Unsupported
isolation must fail closed, never fall back to unrestricted compilation.

This changes which mechanism enforces the compiler's file boundary. Explicit
approval is needed for that prototype and any experimental policy adjustment;
current approval does not accept or replace D015. No claim is made that the
prototype will work, and no runtime guard-only refusal counts as compatibility.
Do not use cache-root overrides, copy distribution resources into projects,
patch the installed loader, silently switch engines or repeat rejected options.

## Evidence identity

Final observation report, retained byte-for-byte:
[m6-lualatex-compatibility-2026-09-12.json](data/v1/m6-lualatex-compatibility-2026-09-12.json).
SHA-256: `487b1f023208ac6fc2d1d86cf0d476e05c4331dd8aa2332401d1f5b31a7edd45`.
Commands, per-process outputs/timing, resource hashes and negative results are
inside that report. The ephemeral probe is
`/tmp/icstex-v1-lua-compatibility-20260912.py`, SHA-256
`ef250c0fb0b1e7d164dfd202f17f1087286b49291c4cc7dff329e07099caecef`.
Run: `QT_QPA_PLATFORM=offscreen python3 /tmp/icstex-v1-lua-compatibility-20260912.py /tmp/icstex-v1-lua-compatibility-20260912-r3`.
Exec 29815 ended exit 0: observations completed, neither candidate accepted.
Captured run log SHA-256:
`341adafc5532f0f22c8344334252038c4b8f809e1fe9b278c49dd49c903c93e4`.

Earlier r1 stopped on a trailing-parenthesis marker parser error; r2 stopped
on the observed safer local-read failure. The final parser records that failure
and rejects the candidate instead of treating safer mode as compatible. Both
earlier logs remain at the corresponding `/tmp/...-r1.log` and `-r2.log` paths;
neither is relabelled successful.

App SHA-256 before/after:
`4e0720eb707fecce1394a7b5f20868be7ea9bd668ba56b615297c23afa267e54`.
App+tests unchanged:
`ddf709d30299aa185630c6fc56ec290e085245d36651931c5a09425ab28a1d73`.
The preceding full-suite result remains applicable to those unchanged files;
this research is not a new full-suite run. Required syntax and diff checks pass.
No Git mutation, packaging, installed-app replacement, release, new task or
subagent. R5 remains open, independently of R2/R3 and external acceptance.
