# AGENTS.md

This file contains the operational rules for any coding agent working on
**ICSTeX**. Read it before changing the project.

## Start Here

1. Run `git rev-parse --show-toplevel` and `pwd -P`; confirm both identify the
   current `ICSTeX` repository root.
2. Read `docs/PROJECT_STATE.md` for the current verified source and artifact state.
3. Read the active bounded assignment for the current agent: `FORCODEX.md`,
   `FORCLAUDE.md`, or `FORDEEPSEEK.md`.
4. For architecture/product work, read `docs/ROADMAP.md` and
   `docs/DECISION_LOG.md`.
5. Use `MEMORY.md` only for durable reminders and `PROJECT_LOG.md` only for
   historical evidence.

Document roles, precedence, promotion, and retirement rules are defined in
`docs/MEMORY_MANAGEMENT.md`.

If the current directory is a legacy or backup copy, stop before editing and
relaunch from the Git repository root.

## Product Boundary

ICSTeX is local research-writing infrastructure for ICC students. Preserve these
boundaries:

- Chinese-first and student-friendly; retain clear terms such as LaTeX, BibTeX,
  SyncTeX, PDF, and Word Count.
- Local files and local compilation are the default.
- Never silently upload `.tex`, `.bib`, PDF, log, or screenshot content.
- Network metadata lookup must remain explicit and user-triggered.
- Prefer deterministic local rules before AI or network features.
- Never modify a user's thesis, IA, EE, or report text unless explicitly asked.
- Do not bundle MacTeX, TeX Live, or MiKTeX.

## Architecture Rules

- Keep pure parsing, state, path, diagnostic, and text rules in `app/core`.
- Keep PySide6 widgets, dialogs, signals, and visual orchestration in `app/gui`.
- `app/core` must not import `app/gui`.
- Keep `MainWindow` as a compatibility facade and evolve it incrementally through
  focused controllers; do not rewrite stable workflows wholesale.
- Preserve root-scoped compile/PDF state and build-id/revision guards.
- Use relative project paths for images and BibTeX wherever possible.

The authoritative architecture map and non-regression boundaries live in
`docs/PROJECT_STATE.md`; long-term reasons live in `docs/DECISION_LOG.md`.

## Required Commands

Run the app:

```bash
python3 -m app
```

Before reporting any source or agent-instruction change as complete:

```bash
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
```

Before packaging or sharing a build:

```bash
bash packaging/preflight.sh
```

For GUI changes, add or update focused tests in `tests/test_gui_editor.py`,
`tests/test_pdf_panel.py`, or `tests/test_ui_visual.py`. For pure rules, add tests
to the relevant core test module.

## File and State Safety

- Saving or compiling must not move the source cursor or scroll position.
- PDF reload should preserve page, zoom, and viewport when it is the same document.
- Failed builds retain the last successful PDF only with an explicit stale state.
- Background builds must not replace the active tab's PDF or indicators.
- Word Count must identify precise `texcount` versus Python fallback mode.
- Strict decoding and same-directory atomic replacement protect user files.
- Do not manually edit generated `build/`, `dist/`, `.app`, or `__pycache__/` files.

## Packaging Rules

- `app/__init__.py` is the application-version source used by packaging.
- Distribute versioned artifacts; do not rename an older artifact to represent new
  source.
- Build Windows artifacts from a Windows-local path, never `C:\Mac\...` shared
  storage.
- Use `packaging/install_build_dependencies.py` for packaging dependencies; it
  handles unreachable loopback proxies without changing system proxy settings.
- macOS signing, architecture, and notarization claims must match inspected
  artifacts exactly.
- Run packaging only for an explicit release task.

## Documentation Discipline

- Replace stale current facts in `docs/PROJECT_STATE.md`; do not append history there.
- Append one verified result to `PROJECT_LOG.md`; do not edit older entries.
- Record an enduring architecture choice in `docs/DECISION_LOG.md`.
- Keep future priorities and completion conditions in `docs/ROADMAP.md`.
- Replace active briefs instead of accumulating completed-task narratives.
- Do not put exact test counts or current artifact status in `AGENTS.md` or
  `MEMORY.md`.

## Repository Cautions

- Determine repository state from live Git checks. If a check fails, verify the
  current path and known authoritative repository path before asking for
  clarification; ask only if the target repository remains ambiguous. Do not
  initialize or replace a repository to work around a failed check.
- Preserve unrelated user or agent changes in the shared workspace.
- Never use destructive reset/checkout workflows without explicit approval.
- Use ASCII in code unless a file already contains Chinese UI strings.
