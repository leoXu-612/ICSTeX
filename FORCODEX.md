# FORCODEX.md

Timestamp: 2026-09-03 (bounded project-file toolbox acceptance)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
The current local source adds a stable project-root file tree, explicit
current/new-window `.tex` opening, `.tex` and image drag handling, guarded
rename/move operations and deterministic multi-window registration. Referenced
paths and paths involved in an active compile fail closed. No package or public
release contains this source delta yet.

## Next Bounded Assignment

The next assignment is maintainer acceptance of the project-file toolbox:

1. Open a folder containing nested `.tex`, `.bib` and image files; confirm the
   tree remains rooted at the selected folder while child documents open.
2. Double-click and drag `.tex` files into the source area; use the context menu
   to open one in a separate window and verify `Ctrl+Shift+N` creates a window.
3. Drag a project image into a saved editor and verify the existing safe import
   path inserts a relative `\includegraphics` reference.
4. Rename or move an unreferenced file inside the project; confirm open tabs,
   watchers and recent-file entries follow the new path.
5. Attempt to move a referenced path and a path involved in an active compile;
   both must be rejected without filesystem mutation.
6. Rebuild or publish packages only under a separate explicit release assignment.

Do not trigger GitHub Actions, publish assets, change the MCP wire contract,
silently rewrite LaTeX references, or add a new GUI/runtime dependency during
acceptance.

## Required Context

- Operations: `AGENTS.md`
- Current truth: `docs/PROJECT_STATE.md`
- Security boundary: `SECURITY.md`
- Architecture decisions: `docs/DECISION_LOG.md` D003, D005, D007, D014 and D017
- Priorities: `docs/ROADMAP.md`
- Memory lifecycle: `docs/MEMORY_MANAGEMENT.md`

## Handoff Rule

After maintainer acceptance, replace this brief with the next bounded assignment.
Put historical commands and results in `PROJECT_LOG.md`, not here.
