# FORCODEX.md

Timestamp: 2026-08-13 (bounded MCP interface acceptance)

This is Codex's current bounded brief. Replace it when the assignment changes;
do not append completed-task history.

## Current State

The verified source/artifact matrix is maintained in `docs/PROJECT_STATE.md`.
Version 2.1.0-beta.1 is a public GitHub prerelease with nine assets. The
repository is Public, the Vercel production website is READY and anonymously
accessible, and generated website metadata enables the verified GitHub download
URLs. Publication history was sanitized before visibility changed.

## Next Bounded Assignment

The local stdio MCP adapter and `icstex-control` Skill are implemented and
verified on `codex/icstex-mcp`. Tool schemas expose bounded enums and standard
read-only/destructive/open-world annotations; these remain hints, while core
grants and validation remain authoritative. The next assignment is maintainer
acceptance:

1. Review the MCP grant model, project-root boundary, CAS/snapshot behavior and
   TeX paranoid I/O before merging.
2. Install the optional SDK with `python3 -m pip install -e '.[agent]'`, register
   one real project read-only, then explicitly enable only the capabilities that
   acceptance needs.
3. If local OCR is part of acceptance, install the existing ICSTeX pix2tex and
   RapidOCR runtimes through the app and run real formula/text inference; current
   source tests cover fail-closed and candidate sanitization, not model quality.
4. Rebuild packages only under a separate explicit release assignment.

Do not trigger GitHub Actions, publish assets, add a remote daemon, or build a
general plugin system.

## Required Context

- Operations: `AGENTS.md`
- Current truth: `docs/PROJECT_STATE.md`
- Security boundary: `SECURITY.md`
- Architecture decisions: `docs/DECISION_LOG.md` D003, D006, D007, D014
- Priorities: `docs/ROADMAP.md`
- Website release gate: `docs/tasks/WEB_RELEASE_SITE_REFACTOR.md`
- Memory lifecycle: `docs/MEMORY_MANAGEMENT.md`

## Handoff Rule

After maintainer acceptance, replace this brief with the next bounded assignment.
Put historical commands, hashes, and results in `PROJECT_LOG.md`, not here.
