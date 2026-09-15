# Security Policy

## Supported releases

Security fixes are provided for the latest published prerelease or stable
release. Older builds may no longer receive fixes.

## Reporting a vulnerability

Do not open a public issue containing exploit details or private document
content. Use GitHub's **Report a vulnerability** form in the repository's
Security tab. Include the affected version, reproduction steps, and the minimum
test fixture needed to demonstrate the issue.

ICSTeX is local-first. Never attach a real thesis, bibliography, PDF, log, or
screenshot when a reduced synthetic fixture can reproduce the problem.

## Compilation boundary

Published builds disable project-local latexmk configuration and TeX shell
escape. Projects that require executable build hooks are outside the supported
security boundary.

## Agent and Harness boundary

The optional stdio MCP server is bound to one canonical project root and starts
read-only. Host startup arguments, never tool-call fields, grant write, compile,
network, recognition, external input, trusted raw-LaTeX, and export authority.
Project writes require compare-and-swap hashes and retain byte-exact preimages.

In the current local-development source, restricted macOS compilation uses a
fail-closed OS sandbox in addition to relative entry/output paths, disabled shell
escape and ignored project latexmk hooks. A bounded kernel capability check must
pass before the compiler starts. Missing/failed isolation is an error, never an
unconfined retry. Inside that sandbox only, `openin_any=a` permits installed Lua
font-loader resources; `openout_any=p` remains enabled. Project contents and
installed TeX/system font resources are readable; only the active build output
and owned temporary directories are writable. Child processes inherit the
boundary and network access is denied. Existing hardlinked output files are
refused. The subprocess environment is a whitelist, not a copy of host secrets.

This backend supports standard `/usr/local/texlive` installations only. It uses
deprecated sandbox-exec and private SBPL rules: it is not a stable platform API,
App Sandbox entitlement, or a claim about a released/installed build. File
metadata is not confidential. Other toolchain layouts and auxiliary programs
without explicit verification are not accepted; see the current integration
receipt and D021. No writable project may be modified concurrently by an
external process. Kernel isolation does not protect against hostile changes by
another unsandboxed process with the same filesystem authority.

Non-macOS restricted compilation retains `openin_any=p` / `openout_any=p`; this
does not establish the same OS isolation or protect against TeX versions that
ignore input-name policy. Ordinary GUI compilation is unchanged. Do not expose
the server over a network transport or run a writable MCP session concurrently
with an editable GUI session for the same project.

Run concurrent projects as separately named stdio processes with distinct roots.
Multiple writable MCP processes for the same root are not a supported topology:
cross-process locks protect mutations and compilation, but bounded reads and
`stop` cancellation are coordinated only inside one server process.
