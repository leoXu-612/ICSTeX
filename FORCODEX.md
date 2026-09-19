# FORCODEX.md

Timestamp: 2026-09-19 (CI process-stop repair)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current Bounded Assignment

Repair the CI failures blocking workflow PR #2 in codex/ci-process-stop, based
on main. Preserve process-exit assertions, bounded waits and cache/file safety.
Verify child-process pipe retention and timeout-budget exhaustion before fixing
the existing stop path. Make process fixtures portable rather than skipping them.

The cancelled Windows run also exposed PDF-state fixture handle retention and
cache deletion before closing its viewer; scope includes these observed CI blockers.
Do not rewrite PDF rendering, loosen assertions, install TeX on runners or bypass
the six-check main ruleset. Run focused and full local tests, then all hosted jobs.
Use a separate repair PR and only merge through green required checks; then resume
the workflow PR. Preserve the unrelated dirty development checkout and releases.

## Required Context

- Operations: `AGENTS.md`
- Current truth: `docs/PROJECT_STATE.md`
- Release decision: `docs/DECISION_LOG.md` D008
- Preview/final build decision: `docs/DECISION_LOG.md` D012
- Priorities: `docs/ROADMAP.md`
- Memory lifecycle: `docs/MEMORY_MANAGEMENT.md`

## Handoff Rule

After verified completion, replace this brief with the next bounded assignment.
Put historical commands, hashes, and results in `PROJECT_LOG.md`, not here.
