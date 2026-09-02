# FORCODEX.md

Timestamp: 2026-09-03 (bounded editor completion and figure-layout acceptance)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
The Word Count accuracy repair is preserved in its own local commit. The current
working delta fixes popup-selection completion and upgrades the normal source
mode's two-image insertion to horizontal, vertical and adjustable 2x2 layouts.
No package or published release contains these source changes yet.

## Next Bounded Assignment

The next assignment is maintainer acceptance of the editor and image-layout repair:

1. Reproduce `\text` completion, move from `\textbf{}` to `\textit{}`, and confirm
   Enter and Tab insert the highlighted candidate.
2. Insert horizontal, vertical and 2x2 layouts from the normal source workspace;
   verify individual widths, captions, copied assets and aspect-ratio preservation.
3. Confirm row-width overflow and partial asset-copy failures leave no malformed
   insertion or orphaned newly copied files.
4. Rebuild or publish packages only under a separate explicit release assignment.

Do not trigger GitHub Actions, publish assets, change the MCP wire contract or
add a new GUI/runtime dependency during acceptance.

## Required Context

- Operations: `AGENTS.md`
- Current truth: `docs/PROJECT_STATE.md`
- Security boundary: `SECURITY.md`
- Architecture decisions: `docs/DECISION_LOG.md` D002, D003 and D007
- Priorities: `docs/ROADMAP.md`
- Memory lifecycle: `docs/MEMORY_MANAGEMENT.md`

## Handoff Rule

After maintainer acceptance, replace this brief with the next bounded assignment.
Put historical commands and results in `PROJECT_LOG.md`, not here.
