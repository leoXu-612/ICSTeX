# FORCODEX.md

Timestamp: 2026-08-29 (bounded Word Count accuracy acceptance)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
On `codex/icstex-mcp`, Word Count now fixes the reproduced Chinese punctuation,
repeated-include, inline-formatting, accent-macro, `%TC:ignore`, inline-verbatim,
footnote and cycle-timeout errors. The change preserves the existing
`WordCountResult` and MCP wire fields. No package or published release contains
this source delta yet.

## Next Bounded Assignment

The next assignment is maintainer acceptance of the Word Count repair:

1. Compare several representative Chinese, English and mixed-language student
   projects against their manually reviewed visible text and TeXcount output.
2. Confirm that repeated includes are intentional in those projects and that
   `%TC:ignore` regions match the student's expected scope.
3. Treat course-specific inclusion rules as a future profile decision; do not
   hard-code one IA/EE policy into the shared counter during acceptance.
4. Rebuild or publish packages only under a separate explicit release assignment.

Do not trigger GitHub Actions, publish assets, change the MCP wire contract or
add a new parsing dependency during acceptance.

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
