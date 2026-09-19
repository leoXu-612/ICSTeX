# FORCODEX.md

Timestamp: 2026-09-19 (reviewed merge closeout)

## Current Bounded Assignment

The user authorized merging pending PRs after local validation. Repair PR #3
is merged; finish workflow PR #2, then integrate modular-layout PR #1 against
the updated main. Preserve both feature behavior and the cancellation/file-safety
fixes when resolving conflicts; do not select an entire side blindly.

GitHub Actions is disabled and CI checks are not merge requirements. Use focused
and full local tests, record exact evidence, and do not re-enable workflows.
Main still requires PRs, resolved conversations and squash merge; no force-push,
deletion or bypass. Never use admin merge to bypass these remaining rules.

Preserve the dirty codex/v1-development checkout, release branches, existing
artifacts and student files. Do not bulk-import unpublished features, package,
deploy or replace the local application in this merge task.
