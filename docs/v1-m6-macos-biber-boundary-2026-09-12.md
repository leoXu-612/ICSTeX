# Mac Biber bootstrap boundary — 2026-09-12

The installed Biber 2.20 starts normally outside the compiler sandbox, but its
universal-binary bootstrap is blocked by the current exact executable policy.
The product's actual LuaLaTeX/biblatex/Biber chain therefore fails closed. This
is a newly measured compatibility gap, not a missing Command Line Tools install
and not a failure of the previously accepted BibTeX chain.

## Scope and unchanged baseline

This follows the user's Mac-first/no-repeated-tests direction and M6's remaining
auxiliary-tool check. Only one new biblatex fixture was compiled, then the
failure was reduced to Biber --version and exact dependency invocations. No
previous BibTeX, GUI, IME, menu, prototype or full-suite workflow was replayed.
No application or unittest source changed; existing full 1598/313.187s/OK is
reused with matching live digests, not described as a new run.

- App: `7009463b6f091f8d58f46fcfee3e08b03b3535fe9d89b0882ac7d3a133e87506`.
- App+tests: `14093898a54aa926b992b20106c570c1d2f6a5899af2ab35b69c157b1467cbc4`.
- HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`, branch
  `codex/v1-development`; shared changes remain uncommitted, index empty.
- macOS 26.6.1 arm64; existing TeX Live 2025. Selected developer directory is
  `/Applications/Xcode.app/Contents/Developer`; the CommandLineTools directory
  also exists. No install or xcode-select change was performed.

## Discriminating evidence

The new `lua-biber` mode in `tools/probe_macos_compiler_sandbox.py` uses
`ctexart`, `biblatex[backend=biber,style=numeric]` and one synthetic book entry.
The shared compiler returns LATEX_ERROR / exit 12 in 17.591s. LuaLaTeX produces
an incomplete PDF with an unresolved citation, but Biber fails and the result
is **not** accepted as a successful FINAL. Source/bib hashes and captured input
evidence remain stable; no formal PDF export is claimed.

Its message claims Command Line Tools are missing. A reduced startup control
uses the same installed binary, a whitelist environment and owned temporary
state, no document or bibliography input:

| Invocation | Result |
| --- | --- |
| Installed Biber --version, outside isolation | Exit 0, 24.420s, `biber version: 2.20` |
| Same --version within current sandbox | Exit 255, 0.131s, misleading Command Line Tools message / errno 1 |
| `/usr/bin/xcode-select -p` within current sandbox | Exit 71, execvp Operation not permitted |
| `/usr/bin/lipo -archs <installed biber>` within current sandbox | Exit 71, execvp Operation not permitted |

The trusted --version control is diagnostic only; the product did not acquire
an unconfined Biber or TeX fallback. Both version checks share a disposable
runtime directory that is removed by the context manager. No relaxed TeX
input policy was used to compile a document outside OS isolation.

Read-only `file`, `otool -L` and `strings` inspection of the installed binary
shows x86_64/arm64 slices, the literal xcode-select command, `/usr/bin/lipo`,
thin-binary extraction and custom-Perl exec error paths. The successful startup
produces 3868 owned temporary files, including `thin/biber`, an extracted
`biber` interpreter and `libperl.dylib`. Thus permitting xcode-select alone
would not establish a complete or safe Biber runtime. This is an inference
from the binary and observed runtime inventory, not a completed fix.

Raw report references, digests and selected results are retained in
[`data/v1/m6-macos-biber-boundary-2026-09-12.json`](data/v1/m6-macos-biber-boundary-2026-09-12.json),
SHA-256 `904dd3bc9dc32ddb9b72b4e35e7ebf4fba40d3b8cc79458c1dc13610fd2064fd`.
All three process handles reached terminal states: compile exec 99902 exit 1
because its success assertion detected the expected compatibility failure;
runtime diagnosis exec 89576 exit 0; dependency diagnosis shell exit 0 with
both denied child exit codes recorded. No owned test process or GUI window remains.

## Decision needed before changing the runtime boundary

D021 permits installed exact executables and excludes executable project/output
paths. Biber needs extracted native code and libraries. Do not solve this by
allowing arbitrary writable temporary code, unconfined document processing,
installing/upgrading tools, or silently substituting BibTeX for Biber.

Proposed bounded next slice, pending explicit approval: prepare the installed
Biber runtime from trusted binary bytes in a separate restricted phase with no
project input; then expose the verified runtime read-only, allowing only its
exact needed programs/libraries to the document compile sandbox. Project source
stays read-only, output scope and no-network policy stay intact, and failure
must still refuse compilation. Prototype the actual loader/write requirements
before integrating; if these constraints cannot hold, report the limitation.
No persistent service, installed-app replacement or dependency installation.

R2 OS/menu keyboard proof still needs a human or a genuinely usable different
input route; the newly inspected keyboard tool belongs to iOS Simulator, not
the host Mac, so it was not used. R3 retains its previously described historical
receiver/AX evidence limits; no new discriminating observation was found and
no blind lifecycle regression was run. These separate requirements are not waived.

Changed only the existing incremental probe, added `tools/probe_biber_runtime.py`
and this evidence/documentation. Both probes pass py_compile; diff check passes.
Probe hashes: `6df8f3bd5575a0ad65d86184acc4d181d15e79092e2b8de75b2c64451a5a8b8e`
and `a1973a2c3ed4c76c2e6b31eea01132dfd9ed2e3be95d351db4311ab84929e5ee` respectively.
No source completion, Biber compatibility, full V1 or release claim.
