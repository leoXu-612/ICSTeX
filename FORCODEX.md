# FORCODEX.md

Timestamp: 2026-08-08 (2.1.0-beta.1 public-release preparation)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
Version 2.1.0-beta.1 is frozen; macOS arm64 and Windows ARM64 beta artifacts
are verified within their recorded scopes. The static release website is locally
verified, but no remote branch, tag, Release or Pages deployment has been pushed.

## Next Bounded Assignment

Complete the public-release gate for the frozen 2.1.0-beta.1 candidate:

1. Build Windows x64 from matching source in a Windows-local directory and
   verify launch, toolchain detection and source-to-PDF with a real TeX install.
2. Generate the x64 Setup EXE only with an x64 host and Inno Setup; never relabel
   the ARM64 ZIP as a generic Windows artifact.
3. Keep `release/release-manifest.json` and `website/release.json` generated and
   checksum-consistent as artifacts change.
4. Keep the locally verified `WEB-RS-001` website gate unchanged except for
   generated metadata updates. Preserve release-data logic; do not hard-code
   version metadata or treat Vercel as the release authority.
5. Only after explicit maintainer approval and restored external credentials,
   push the release branch/tag, create a GitHub prerelease and deploy Pages via
   the guarded process in `docs/release-process.md`.

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
