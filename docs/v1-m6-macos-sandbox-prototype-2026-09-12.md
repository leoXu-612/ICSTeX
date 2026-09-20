# R5 macOS compiler-isolation prototype

2026-09-12. **The authorized temporary prototype compiles both Latin/math and
Chinese-path/CJK samples while its tested OS file boundaries remain enforced.**
This is not a product integration, complete sandbox audit or release acceptance.
The current application and D015 are unchanged; protected product LuaLaTeX
compatibility remains open until the real compile workflow is adapted and tested.

## Scope and mechanism

The user explicitly permitted the temporary Mac sandbox and input-policy
experiment after directing Mac-first work. No VM, foreground UI, student file,
installed app, TeX installation, dependency, signing or release operation was used.
The latex-doctor detector confirmed the existing TeX Live 2025/LuaHBTeX 1.21.0
toolchain; no generic downloading smoke runner was used. Test-triage guided
small discriminating controls. The PDF skill was used only to inspect generated
test PDFs with text extraction and rendered-page review, not to edit a document.

The prototype launches children through the installed `/usr/bin/sandbox-exec`
with deny-default rules. It imports only Apple's local `dyld-support.sb`, not
the broader `system.sb`. Project inputs, TeX, system libraries and selected
system font directories are read-only. Only fresh job output/cache/temp trees
are writable. There is no network or fork allowance; executable paths are limited
to the test Perl interpreter and existing LuaHBTeX binary. All other inherited
file descriptors are closed; stdin is null and stdout/stderr are captured.
The child environment is a small explicit set, with HOME and caches redirected
to the temporary job rather than exposing unrelated host environment values.

File metadata remains readable; this prototype does not promise metadata/path
privacy. Installed TeX resource bytes were read and hashed but never opened for
writing. Owned synthetic source files exercise the equivalent read-only rule.
The process-launch and socket tests use only `/usr/bin/true` and an ephemeral
loopback listener in the probe itself; no data is sent to an external host.

Apple's installed `sandbox-exec(1)` manual labels the command deprecated, and
the imported profile labels its rules private interfaces subject to change.
These are concrete shipping risks, not resolved by a passing local experiment.
The exact tested host is macOS 26.6.1 arm64; no other OS release is accepted.

## Positive and negative controls

The unconfined control opens only owned test files for append and writes no
source/private bytes. It establishes that the denied operations would otherwise
be available to the same account. Kernel checks finish before the isolated
engine's `openin_any` is changed from `p` to `a`; `openout_any=p`, disabled shell
escape and disabled Lua sockets remain. No TeX process runs with relaxed input
policy outside the sandbox.

| Observation | Unconfined owned-data control | OS-isolated result |
| --- | --- | --- |
| Project and installed TeX resource reads | Allowed | Allowed |
| Dedicated output write | Allowed | Allowed |
| External sentinel read/write-open | Allowed | Denied |
| Input symlink to external sentinel read | Allowed | Denied |
| Source write-open, including symlink from output directory | Allowed | Denied |
| External sentinel via `/System/Volumes/Data` alias | Allowed | Denied |
| TCP connection to owned loopback listener | Connected | Denied, operation not permitted |
| Attempted `/usr/bin/true` child | Exit 0 | Launch denied |

Actual LuaHBTeX with isolated `openin_any=a` then confirms readable local and
distribution inputs, writable output, denied external/symlink reads and denied
source/external write-open. It reports shell escape disabled. These direct
engine checks, not environment variable presence alone, establish the observed
boundary. They do not cover every file API, network protocol or resource attack.

## Compilation and termination results

- Latin/math: LuaLaTeX exit 0 in 7.283 s, one page, 26,769 bytes.
  PDF SHA-256 `3123812f20f00b1b9de8dd4aba7aa58380e67429dcb71ed7dad29289d82de19c`.
- Chinese input filename and `ctexart` with installed Fandol fonts: exit 0 in
  4.035 s, one A4 page, 41,449 bytes.
  PDF SHA-256 `0132644b3938dc51cf25042c9ac281a1576205965856fabd3d8a145085736633`.
- Both pages were extracted and rendered with system Poppler, then visually
  inspected. Expected text, Chinese glyphs and the superscript equation are
  readable, without blank output or clipping. This is synthetic layout evidence,
  not all-font, interactive-PDF or real-student document acceptance.
- An isolated LuaHBTeX loop emits its readiness marker, exceeds the probe's
  one-second deadline and is terminated by the existing
  `CompileManager._terminate_process`; final return code -15, 1.006 s.
  Pipes drain and the owned process is terminal. This tests the termination helper,
  not GUI cancellation or a latexmk descendant tree. No product timeout changed.

The final probe (exec 40967) is terminal exit 0. All owned input hashes and the
inspected installed resource hash match. App+tests before/after remain
`ddf709d30299aa185630c6fc56ec290e085245d36651931c5a09425ab28a1d73`;
the preceding full-suite result is unchanged-source evidence, not rerun here.
Compileall and diff checks pass.

Earlier observations remain distinct: the minimal bootstrap profile caused
`true` to abort in dyld/libignition (exit 134); adding Apple's dyld-support import
allowed it to start. This does not isolate one specific missing bootstrap rule.
Crash report `true-2026-09-12-151654.ips`, SHA-256
`892a03350aa4f27c14d87110e5879328c355e4316efa0e5eb30a624847235bbe`,
is a prototype launch failure, not another ICSTeX/Python R3 crash. Full r1 passed
the boundary checks but failed on denied `/Library/Fonts` enumeration. Granting
that directory read-only produced the r2 Latin PDF; r3 adds alias, write-symlink,
CJK and termination observations. No earlier failure is relabelled a pass.

## Retained evidence and next decision

- [Raw final report](data/v1/m6-macos-sandbox-prototype-2026-09-12.json), SHA-256
  `24dabe27f0a15976340f75acbe8c2e0b2300816df09cb69c5d78c44e4859b6a2`.
- [Exact prototype text](data/v1/m6-macos-sandbox-prototype-2026-09-12.py.txt),
  SHA-256 `2621ed96acdb34f57fe4305de7a2c717ed714317eb50952189a0818365c387af`.
  It is retained as documentation, never imported by the product.
- Runtime directory `/tmp/icstex-macos-sandbox-prototype-20260912-r3` holds
  per-process stdout/stderr, the actual profile and test PDFs/PNGs. Profile
  SHA-256 `a10aa437f9b94f469f6557ea0dfd60ddda77f1f7a386ab7b10ae3cafcfe3ecf9`;
  parent log SHA-256 `f48458ad75f11e8ead3f44c6c715710f95d708fdecd01e8f72989ad2cc63a705`.
- Reproduction uses the retained script in a new empty temporary output path:
  `QT_QPA_PLATFORM=offscreen python3 /tmp/icstex-macos-sandbox-prototype-20260912.py /tmp/icstex-macos-sandbox-prototype-20260912-r3`.
  The recorded output path already exists and must not be overwritten.

The next decision is the product isolation backend and its support policy,
not another repetition of these samples. The current profile deliberately denies
forks and therefore is not a drop-in latexmk/BibTeX driver profile. Product
integration must handle only the required tool descendants, real project inputs,
FINAL/PREVIEW ownership, build evidence and cancellation, with fail-closed
capability checks and no unisolated fallback. The deprecated command/private
profile dependency cannot silently become a supported shipping contract.
Any formal adapter/helper implementation requires the separate bounded decision;
the granted prototype scope does not authorize production security changes.
