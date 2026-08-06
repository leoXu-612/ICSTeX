# FORCLAUDE.md

Timestamp: 2026-07-14 (documentation architecture established)

This is Claude's current bounded handoff. Replace it when the assignment changes.

## Current State

The 2026-07-13 review/UI/font delta is complete and verified. Its durable source
state and release boundary are now maintained in `docs/PROJECT_STATE.md`; the
completed engineering details remain in `PROJECT_LOG.md`.

Existing 0.2.7 artifacts do not contain that source delta.

## Next Bounded Assignment

Only when explicitly requested, prepare one matching next release across macOS,
source transfer, and Windows. Confirm the version first; `0.2.8` is recommended.
Do not silently replace 0.2.7 or rebuild from `C:\Mac\...` shared storage.

## Required Context

1. `AGENTS.md`
2. `docs/PROJECT_STATE.md`
3. `docs/DECISION_LOG.md` D008
4. Relevant packaging README files

## Handoff Rule

Replace this file with the exact next assignment and concise accepted result.
Append completed verified work to `PROJECT_LOG.md`; do not accumulate a second
historical handoff here.
