# FORCODEX.md

Timestamp: 2026-09-03 (bounded command-completion catalog acceptance)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
The verified MCP, Word Count, popup-selection, image-layout and 68-template
completion catalog are locally merged into `release/2.1`. The catalog adds
`pageref` label lookup and maps color/math completions to the existing
missing-package diagnostics. No package or published release contains this
source delta yet.

## Next Bounded Assignment

The next assignment is maintainer acceptance of the command-completion expansion:

1. Type `\text` and verify the exact `\text{}`, bold, italic, color and remaining
   text variants are visible within the bounded popup.
2. Type `\textc`, accept `\textcolor{}{}`, and verify the cursor lands in the
   first argument; direction-key selection must still insert the highlighted row.
3. Smoke-test structure, reference, citation, math, unit, project-composition and
   bibliography prefixes; `\pageref{...}` must suggest known labels.
4. Verify `\textcolor` without `xcolor` and `\text` without `amsmath` produce the
   existing one-click package fix, while documents already declaring the package
   remain warning-free.
5. Rebuild or publish packages only under a separate explicit release assignment.

Do not trigger GitHub Actions, publish assets, change the MCP wire contract, add
a language server or add a new GUI/runtime dependency during acceptance.

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
