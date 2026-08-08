# FORCODEX.md

Timestamp: 2026-08-08 (2.1.0-beta.1 publication gate)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
Version 2.1.0-beta.1 source now enforces the accepted D014 local execution
boundary and passes the current full suite. macOS arm64, clean source, and
Windows ARM64 assets were rebuilt from the hardened source and verified within
their documented scopes. The repository remains Private; no remote release
branch, tag, Release or Pages deployment has been pushed.

## Next Bounded Assignment

Complete the public-release gate for the hardened 2.1.0-beta.1 candidate:

1. Keep Windows x64 and Setup marked unavailable unless a real x64/Inno Setup
   environment becomes available; never relabel ARM64.
2. Keep `release/release-manifest.json` and `website/release.json` generated and
   checksum-consistent as artifacts change.
3. Keep the locally verified `WEB-RS-001` website gate unchanged except for
   generated metadata updates. Preserve release-data logic; do not hard-code
   version metadata or treat Vercel as the release authority.
4. Before visibility changes, resolve the known low-sensitivity personal paths
   still present in Git history. Then push the final branch/tag, create the
   GitHub prerelease and deploy Pages through the guarded release process.

Do not add product features or reuse the stale unversioned Windows ZIP.

## Required Context

- Operations: `AGENTS.md`
- Current truth: `docs/PROJECT_STATE.md`
- Release decision: `docs/DECISION_LOG.md` D008
- Preview/final build decision: `docs/DECISION_LOG.md` D012
- Priorities: `docs/ROADMAP.md`
- Website release gate: `docs/tasks/WEB_RELEASE_SITE_REFACTOR.md`
- Memory lifecycle: `docs/MEMORY_MANAGEMENT.md`

## Handoff Rule

After verified completion, replace this brief with the next bounded assignment.
Put historical commands, hashes, and results in `PROJECT_LOG.md`, not here.
