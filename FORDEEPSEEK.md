# FORDEEPSEEK.md

Timestamp: 2026-08-06 (Asia/Taipei)

This is DeepSeek's current bounded assignment. Replace it when the assignment
changes; do not append completed-task history.

## Status

`QUEUED - DO NOT IMPLEMENT YET`

Activation requires both conditions:

1. The maintainer explicitly tells DeepSeek to start `DS-001`.
2. `docs/PROJECT_STATE.md` records a clean 0.2.8 release boundary, or the
   maintainer explicitly authorizes feature work before that release completes.

Until activation, DeepSeek may read the listed files and report conflicts, but
must not modify source, tests, version metadata, release documents, or artifacts.

## Assignment DS-001 - Formula Composer Core Contract

### Objective

Implement the first reviewable 0.2.9 slice for a source-first visual formula
composer: deterministic, pure-Python formula representation, safe wrapper
parsing/rendering, selection-aware template edits, and focused tests. LaTeX text
remains the only source of truth; this slice does not create the visual UI.

### Required Reading

1. `DEEPSEEK.md`
2. `AGENTS.md`
3. `docs/PROJECT_STATE.md`
4. `docs/ROADMAP.md`
5. `docs/DECISION_LOG.md` D003, D005, D006, D007, D008, and proposed D013
6. `app/core/latex_insertions.py`
7. `app/gui/insertion_actions.py`, especially `insert_equation()` and
   `insert_snippet()`
8. `app/gui/latex_editor.py`, especially selection replacement and Undo handling
9. `tests/test_latex_insertions.py` and the relevant formula/editor tests in
   `tests/test_gui_editor.py`

### Writable Scope

- Create `app/core/formula_input.py`.
- Create `tests/test_formula_input.py`.
- Modify `app/core/__init__.py` only if an export is demonstrably required.

Any other file requires maintainer approval before editing. Preserve unrelated
workspace changes; this workspace is not a Git repository.

### Required Behavior

- Define small immutable domain types for formula mode, formula draft, parsed
  envelope, template edit result, and final text edit plan.
- Support exact-selection recognition and rendering for the MVP wrappers:
  `$...$`, `\(...\)`, `\[...\]`, `equation`, and `equation*`.
- Reject incomplete, ambiguous, multi-formula, or structurally unsafe selections;
  do not guess a replacement range.
- Preserve the selected formula body exactly when the wrapper is unchanged,
  including whitespace, comments, custom macros, and unknown commands.
- Provide deterministic selection-aware edits for at least fraction, square
  root, superscript, subscript, sum, integral, and one Greek-symbol insertion.
- Return edit plans and required package names as data. Do not mutate an editor,
  file, preamble, settings object, PDF state, or compile state.
- Keep the module free of PySide6, `app/gui`, filesystem I/O, subprocesses,
  networking, MathLive, QtWebEngine, and TeX compilation.
- Document canonicalization explicitly: changing formula mode may intentionally
  regenerate the outer wrapper, but must not silently rewrite the body.

### Out of Scope

- Formula dialog, dock, palette widgets, preview rendering, MathLive, WebChannel,
  QtWebEngine, matrices, `cases`, `align`, OCR, AI input, or natural language.
- Package injection into the document, cursor/scroll changes, Undo integration,
  compilation, PDF state, version bumping, packaging, or release work.
- Updates to `docs/PROJECT_STATE.md`, `PROJECT_LOG.md`, `CHANGELOG.md`,
  `docs/ROADMAP.md`, or this brief. The reviewer promotes verified results.

### Acceptance Criteria

- Focused tests cover every supported wrapper and template, empty bodies,
  selection replacement, escaped delimiters, comments, unknown macros, malformed
  input, ambiguous input, and exact body round trips.
- Invalid input returns an explicit non-applicable/error result and never a
  best-effort destructive replacement.
- `app/core/formula_input.py` imports neither PySide6 nor `app.gui`.
- Existing tests remain unchanged unless a pre-existing assertion is objectively
  incorrect and the maintainer approves the change.
- These commands pass from the authoritative root:

```bash
python3 -m unittest tests.test_formula_input
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
```

### Handoff Contract

Stop and request direction if the requested behavior requires editing outside
the writable scope or changing an Accepted decision. On completion, report:

```text
## Changes Made
## Files Modified
## Testing
## Potential Issues
## Suggested Commit Message
```

Include exact commands and failures. Do not claim GUI integration or 0.2.9
completion; the expected result is only `DS-001` ready for Codex review.
