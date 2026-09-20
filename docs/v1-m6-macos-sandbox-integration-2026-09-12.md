# Mac restricted compiler integration — 2026-09-12

The approved local Mac backend now runs the real LuaLaTeX/BibTeX chain with
read-only source and fail-closed OS isolation. A one-page Chinese/math/reference
PDF was produced and visually inspected. This is a source increment, not a
packaged application or complete V1/release acceptance.

## Scope and mechanism

User approved integration after the separate sandbox prototype and requested no
repetitive tests, with visible progress within five hours. Work began around
15:29 Asia/Taipei; the bounded target was 20:30. No VM/foreground control,
student document, installed app, TeX distribution, Git index/commit/remote,
dependency, signing or release was changed.

`app/core/macos_compiler_sandbox.py` is called only for macOS
`restricted_io=True` jobs in the shared compiler. Standard installed TeX Live
paths are validated. The process receives a whitelist environment, project and
distribution read access, current-output/owned-temp write access, exact allowed
executables and no network permission. The profile is passed directly in argv,
not loaded from a project-writable policy file. Each job checks actual kernel
read/write/symlink/exec and Cwd behavior on owned fixtures before yielding a
sandbox-wrapped command with `openin_any=a`; `openout_any=p`, `-norc` and
`-no-shell-escape` remain. Missing/failed guard returns PROCESS_START_FAILED,
never an unconfined fallback.

Existing multiple-hardlink output files are rejected before the guard. The
compiler preserves its captured engine/toolchain/restricted flag, checks stop
again after preparation, charges preparation to the existing deadline, and
retains process-group termination. Ordinary GUI I/O policy, source editing,
PDF ownership and MCP wire schema are unchanged. D021 records the decision.

## Source and environment

- Branch `codex/v1-development`, HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`;
  empty index, changes remain local and uncommitted.
- Final app tree SHA-256:
  `7009463b6f091f8d58f46fcfee3e08b03b3535fe9d89b0882ac7d3a133e87506`.
- Final app+tests tree SHA-256:
  `14093898a54aa926b992b20106c570c1d2f6a5899af2ab35b69c157b1467cbc4`.
- Digest uses sorted relative Python paths, NUL, file bytes, NUL. Tools/docs are
  not part of those digests. macOS 26.6.1 (25G76), arm64; installed TeX Live 2025,
  LuaHBTeX 1.21.0, latexmk 4.86a and BibTeX 0.99d.
- Probe `tools/probe_macos_compiler_sandbox.py` SHA-256:
  `ac8a0fe85713f04ab0f0ea586eed1e49e25eb2219c5d2d9188de2b64125fc47c`.
  Its individually selectable cases refuse to overwrite old evidence.

## Incremental evidence, not a replay of the prototype

Raw report locations, hashes, selected outputs and retained failures are in
[`data/v1/m6-macos-sandbox-integration-2026-09-12.json`](data/v1/m6-macos-sandbox-integration-2026-09-12.json).

| Check | Result and boundary |
| --- | --- |
| New adapter/compiler tests | Initial 42 tests passed in 11.446s. After added guards, 10 adapter tests exposed one test-fixture misuse of cancel_pending; using stop_current(timeout=0) passed the single affected test. Final suite below covers all final tests. |
| Real LuaLaTeX + BibTeX, r4 | SUCCESS, exit 0, 20.865s cold build; Chinese, formula, resolved [1], reference text. Original source/bib hashes unchanged; input evidence stable. One A4 page, 40661 bytes, PDF SHA-256 `6a9ebb1a46431ed8c6753e738be33354424c642e57c35607d8a726da6fe2eb43`. Poppler extraction and 100-dpi rendered page inspected: legible and unclipped. |
| Actual driver-profile OS controls, r2 | Project read/output write succeed; external read/write, source write, external/read and source/write symlinks, new hardlink creation, loopback TCP and unrelated child exec denied. No external traffic. |
| Pre-existing output hardlink, r1 → r2 | Readonly source inode could initially be opened for append through an existing output hardlink; no bytes written. New preflight refuses startup. Original preserved. |
| Real driver + Lua child stop, r3 | Readiness marker proves actual Lua execution. stop_current succeeds, worker idle, process group no longer exists; 0.0082s observed stop interval. This is a sample, not a latency guarantee. |
| pdfLaTeX and XeLaTeX integration, r1 each | Both SUCCESS, 0.414s / 0.847s, stable input evidence and preserved source; Xe PDF contains Chinese. These were on an earlier adapter tree, not relabelled final-source native tests. |
| Actual stdio MCP PDF export, r1 | Real server/session/export succeeds; original unchanged and response SHA-256 equals exported PDF, extracted expected text. Earlier adapter tree; final changes add the Cwd/executable and hardlink checks, not an MCP protocol change. |

Lua r4, boundary r2 and hardlink r2 use the final application code, with the
pre-final-test-fix app+tests digest
`dc245b3f571b2be324f332c08fcd6a66ac15531101ae512da655687e0429dd97`.
Cancellation r3 uses the final app+tests digest. Earlier pdf/Xe tests used
`71254a526c2a33c2587b10625392bb1d7a26105e71656b7e81e3369d8be4566e`;
stdio used `1d701042e43f6db4c05745f2eaeb04e14c0bf093c97d4dcd2d4466c7dedded80`.

### Retained failures and narrow corrections

- Lua r1: `/bin/sh` dispatches to `/bin/bash` on this Mac; the latter was absent
  from the exact executable list. Added that system executable only.
- Lua r2/r3: kpsewhich was needed for bibliography lookup, and Perl `Cwd::cwd`
  invokes `/bin/pwd`, unlike the working `getcwd`. The old undefined return
  directory broke latexmk's bibliography chdir/popd. Added exact kpsewhich/pwd
  entries and verified both Cwd APIs. A trial ancestor-directory read grant did
  not solve it and is absent from the final profile. No broad /bin exec grant.
- Stop r1 tested is_running before the worker started. Stop r2's readiness
  marker used a hidden `.latex_build` component rejected by TeX's output-name
  policy. The probe now waits for completion/readiness and uses an explicit
  owned non-hidden build directory. Product output policy was not weakened.
- The standalone prototype was not rerun. Passed GUI, keyboard, IME, old PDF
  workflows and VM routes were not repeated.

## Final source gate

Required compileall and diff checks passed. The single final full run completed:
1598 tests / 313.187s / OK, exec 15456 terminal exit 0.
Log `/tmp/icstex-v1-macos-sandbox-full-20260912-r1.log`, SHA-256
`358a6f5f32e1637aea70f004d2467e33e01c3b793d1cd5ecfa29e82aeda1ab95`.
Post-terminal app/app+tests digests match the frozen identities above; HEAD and
empty index unchanged. Retained Python crash-report count remains eleven.
All owned probe/full handles are terminal; no native QA window was opened.
By 15:52 Asia/Taipei, the bounded source result and required gate were complete,
well before 20:30. This does not assign a completion time to the remaining V1 gates.

## Remaining limitations

Only the installed standard TeX Live 2025 paths and listed engines/BibTeX were
exercised. Biber/PAR, custom installations, user-font collections, all projects,
TeX Live 2026 and other macOS releases are not accepted by this receipt. The
deprecated/private SBPL interface remains a release-support risk; the bounded
guard is not a security certification. File metadata and files inside the
declared project are not a confidentiality boundary. External concurrent
mutation of the same project/output is unsupported. No distribution-wide
resource write was attempted and no dependency was changed.

R5's tested Mac source chain is now usable, while backend shipping support and
unverified auxiliary-tool paths stay explicit. R2 OS/menu keyboard evidence,
R3 historical crash/AX disposition and E1–E4 are not closed by this increment.
No claim of full M2–M6/V1 completion, installed-build replacement or release.
