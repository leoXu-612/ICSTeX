# FORCODEX.md

Timestamp: 2026-08-09 (2.1.0-beta.1 post-release boundary)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
Version 2.1.0-beta.1 is a public GitHub prerelease with nine assets. The
repository is Public, the Vercel production website is READY and anonymously
accessible, and generated website metadata enables the verified GitHub download
URLs. Publication history was sanitized before visibility changed.

## Next Bounded Assignment

Maintain the post-release boundary for 2.1.0-beta.1:

1. Keep Windows x64 and Setup marked unavailable unless a real x64/Inno Setup
   environment becomes available; never relabel ARM64.
2. Do not replace published assets without a new versioned candidate and full
   checksum, packaging, and website regeneration.
3. Preserve GitHub Releases as the artifact authority and Vercel as static
   hosting only; do not hand-edit `website/release.json`.
4. Do not manually run or retry GitHub Actions until the maintainer explicitly
   requests CI diagnosis. Record user-reported post-release failures before
   changing the published branch or assets.

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
