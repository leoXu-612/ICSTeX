# ICSTeX Durable Memory

This file contains only compact, cross-task reminders. It is not the current
project state, roadmap, decision history, or task log.

## Authoritative Context

- Workspace: `<HOME>/Desktop/Codex/ICS-Project-/ICSTeX`
- The old `Codex_Latex编译器` tree is rollback-only context.
- Current verified facts: `docs/PROJECT_STATE.md`
- Future priorities: `docs/ROADMAP.md`
- Long-term decisions: `docs/DECISION_LOG.md`
- Completed history: `PROJECT_LOG.md`
- Context lifecycle: `docs/MEMORY_MANAGEMENT.md`

## Durable Product Memory

- ICSTeX is local research-writing infrastructure for ICC students, not a generic
  cloud editor.
- It targets IA, EE, laboratory reports, coursework essays, and similar work.
- Chinese-first UX, local compilation, privacy, truthful status, and safe file
  handling take priority over feature count.
- LaTeX distributions remain external prerequisites.
- Network metadata lookup is explicit opt-in; no implicit network or AI behavior.

## Durable Architecture Memory

- Pure rules belong in `app/core`; PySide6 orchestration belongs in `app/gui`.
- `MainWindow` is a compatibility facade over focused controllers; evolve it in
  small tested slices.
- Compile managers and PDF freshness are owned by normalized compile root.
- Revisions and build ids, not mtimes, guard stale/background results.
- Strict decode and atomic same-directory replace protect user source files.
- Word Count must always identify `texcount` versus fallback behavior.

## High-Risk Boundaries

- Never modify a user's paper without explicit permission.
- Never let a background/root-child result replace another root's PDF or UI state.
- Never present an old or differently built artifact as containing newer source.
- Windows packaging must run from a Windows-local path.
- Generated build and distribution contents are not source-of-truth files.

## Maintenance

Do not add exact versions, test counts, artifact hashes, dated task narratives, or
active assignments here. Promote accepted decisions to `docs/DECISION_LOG.md`,
replace current facts in `docs/PROJECT_STATE.md`, and append completed evidence to
`PROJECT_LOG.md`.
