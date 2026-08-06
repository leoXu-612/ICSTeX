# FORCODEX.md

Timestamp: 2026-08-01 (fast-preview source delta verified)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
The source contains reviewed post-0.2.7 UI/PDF/font and dual preview/final-build
deltas, while all existing 0.2.7 artifacts predate those changes.

## Next Bounded Assignment

Only when explicitly requested:

1. Confirm the next release version; `0.2.8` is recommended over replacing 0.2.7.
2. Synchronize source, packaging, README, and CHANGELOG metadata.
3. Rebuild and verify the versioned macOS DMG and clean source archive.
4. Build and launch-test the same version from a Windows-local path.
5. Update `docs/PROJECT_STATE.md` and append one verified release result to
   `PROJECT_LOG.md`.

Freeze the currently verified feature set during that release task. Do not
claim that an existing 0.2.7 artifact contains any post-0.2.7 delta.

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
