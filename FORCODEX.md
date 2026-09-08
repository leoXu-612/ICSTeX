# FORCODEX.md

Timestamp: 2026-09-08 (source repository synchronization)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
The local installed application contains the frozen response/preview, formula/
table and default-offline update-entry source. Its exact local build identity,
verification boundaries and rollback receipt are recorded in the state and log.
Public release artifacts remain unchanged. Native online update delivery is not
activated or accepted; its separate maintainer gates remain in
`docs/FORCODEX_UPDATES.md` and `packaging/UPDATES.md`.

## Active Bounded Assignment

The user explicitly authorized appropriate renaming, committing and GitHub
remote synchronization of the accumulated changes. Inspect names and retain
them unless a concrete mismatch requires correction. Preserve the existing
commit history and target the current `release/2.1` upstream without force push.

Review the tracked and untracked scope, run required source checks, and commit
only project source, documentation, tests and synthetic verification evidence.
Exclude local build outputs, backups, credentials and student material. Verify
the remote branch against the final local commit before reporting completion.

Do not create a release, upload installation packages, change the version or
activate an updater. Keep GitHub Actions untriggered using the existing
skip-CI commit convention; do not alter repository security or workflow
settings. Preserve the installed app, rollback copy and unrelated working-tree
edits. MCP contracts, student LaTeX, runtime dependencies, Developer ID
credentials and notarization remain outside this assignment.

## Required Context

- Operations: `AGENTS.md`
- Current truth: `docs/PROJECT_STATE.md`
- Security boundary: `SECURITY.md`
- Architecture decisions: `docs/DECISION_LOG.md` D003, D005, D007, D013, D014, D017, D018, D019 and D020
- Priorities: `docs/ROADMAP.md`
- Memory lifecycle: `docs/MEMORY_MANAGEMENT.md`

## Handoff Rule

Start a new bounded brief only after a new assignment. Put historical commands
and results in `PROJECT_LOG.md`; keep measured limitations explicit.
