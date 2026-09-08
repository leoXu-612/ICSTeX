# FORCODEX.md

Timestamp: 2026-09-08 (source synchronization handoff)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
The local installed application contains the frozen response/preview, formula/
table and default-offline update-entry source. Its exact local build identity,
verification boundaries and rollback receipt are recorded in the state and log.
The product source is also synchronized to GitHub; public installation artifacts
remain unchanged. Native online update delivery is not
activated or accepted; its separate maintainer gates remain in
`docs/FORCODEX_UPDATES.md` and `packaging/UPDATES.md`.

## Active Bounded Assignment

The user-requested local installation and source repository synchronization are
complete. No further implementation, renaming, version change or release work
is assigned. Preserve the installed app, rollback copy, local-only screenshots
and existing commit history. Start a new bounded brief only for a new assignment.

Public installation packages and online updates remain separate release gates.
Do not activate an updater, access signing credentials, change repository
security/workflow settings or modify student content under this completed task.

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
