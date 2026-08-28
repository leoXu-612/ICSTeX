# FORCODEX.md

Timestamp: 2026-08-28 (bounded MCP 2.x concurrency acceptance)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
On `codex/icstex-mcp`, the optional stdio adapter now uses the official MCP 2.x
dispatcher and a core project-level concurrency coordinator. The existing
11-tool wire contract and startup grants remain authoritative. No package or
published release contains this source delta yet.

## Next Bounded Assignment

The next assignment is maintainer acceptance of D015/D016:

1. Review the one-root boundary, read/exclusive classifications, compile FIFO,
   stop cancellation, CAS/snapshot behavior and TeX paranoid I/O.
2. Register two distinct synthetic projects under separate MCP names. Start
   read-only, then grant only the compile/write capabilities needed for the
   acceptance case; never run an editable GUI session for those roots.
3. Treat multiple writable server processes for the same root as unsupported;
   use the focused cross-process tests only to verify fail-safe mutation locking.
4. If local OCR is in scope, install the existing pix2tex/RapidOCR runtimes
   through the app and review real candidate quality separately.
5. Rebuild or publish packages only under a separate explicit release assignment.

Do not trigger GitHub Actions, publish assets, add a network transport or daemon,
or broaden the 11-tool surface during acceptance.

## Required Context

- Operations: `AGENTS.md`
- Current truth: `docs/PROJECT_STATE.md`
- Security boundary: `SECURITY.md`
- Architecture decisions: `docs/DECISION_LOG.md` D003, D006, D007, D014-D016
- Priorities: `docs/ROADMAP.md`
- Memory lifecycle: `docs/MEMORY_MANAGEMENT.md`

## Handoff Rule

After maintainer acceptance, replace this brief with the next bounded assignment.
Put historical commands and results in `PROJECT_LOG.md`, not here.
