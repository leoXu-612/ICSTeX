# M6 IME-neutral source identity for read-only consumers

Bounded R1 source repair, not complete M2/M6/A12 or native IME acceptance.
Tests use offscreen Qt, isolated settings and disposable synthetic documents.
No foreground operation, student-file change, network lookup, Git mutation,
packaging, installed-app replacement or release operation occurred.

## Source and reproduced failure

Branch `codex/v1-development`, unchanged HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`; shared changes preserved.
Baseline app `d25a13526e611621a2a13b8823ed7deaf2b0b39678a192c9dd1c9a612372ee6f`.
Final app `c7e9859961795c2ec082583e9a7aad2fc2e0d60e859e614d784e4a5a4e09676f`;
app+tests `c317ad7e93f462154fff59bbc67185e33279ea3ec6f0f89a9e9ba097e186e4bf`.
Digests use sorted relative Python paths, NUL, raw bytes, NUL; app then tests.
They identify the uncommitted source, not a package or published version.

The preceding layout receipt reproduced candidate-only Qt revision 2→3 with
unchanged source and a citation report discarded by periodic reconciliation.
Four added regressions failed on that baseline: citation, material and submission
reports were discarded; Word Count's key changed despite unchanged text.
`/tmp/icstex-v1-source-identity-red-r1.log`, 4 tests / 0.604s / 4 failures,
SHA-256 `42813473eaa7fab690c7b60fd9e5e02a7de0421dfdea1c871179c0f3d124c59c`.
This is false invalidation, not observed source loss. The earlier immediate
notification fix did not cover periodic or cached revision consumers.

## Repair and invariants

- `LaTeXEditor.source_revision` is an editor-local monotonic edit identity.
  Document `contentsChange` advances it for real non-IME content events, including
  while editor signals are blocked during reload. Qt revision is not offset or
  reused, so reset/reload and edit→Undo cannot recreate a previous identity.
- At the existing input-method boundary, only an actual plain-text change
  advances the counter, once and before `sourceTextChanged`. Candidate updates
  and cancellation alone do not. Native partial commits, UTF-16 reconversion,
  deletion and removal of an existing selection remain genuine edits with Undo.
- Citation health, material usage, submission checks (including scoped source
  buffers in Block mode), Word Count and project-panel caches use that identity.
  Reading a key does not copy or compare the entire document. The existing IME
  boundary comparison is retained, not moved into a periodic timer.
- This counter is not a byte digest: non-IME document changes can invalidate
  conservatively. Existing disk hashes, dependency generations, root/tab owners,
  build identity, cancellation and late-result guards remain in place.
- The two remaining raw Qt revision consumers are intentionally unchanged:
  history restore and checkpoint `CaptureLease` are write/capture transactions,
  not read-only presentation caches. Their conservative revision/content-event
  cancellation, including blocked-signal edits, is not weakened by this repair.

## Regression evidence

The smallest post-fix scope passed 9 tests / 0.715s, exec 93886 exit 0;
`/tmp/icstex-v1-source-identity-first-r1.log`, SHA-256
`2bec6dc9b0fc1516c0694253cf3fb444445a2b852fa76ad7d3aaec3ec94f2eaa`.
Expanded test development retained two distinct fixture failures, not new product
fixes: r1 omitted `_quick_key(root)`'s argument; r2 incorrectly expected a magic
comment alone to make a file a related child. The final fixture includes the
child in the synthetic root and explicitly checks the existing root resolver.
The root ownership/security rule was not changed.

Final focused command:

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_input_composition tests.test_gui_editor \
  tests.test_gui_citation_health tests.test_citation_health \
  tests.test_gui_material_usage tests.test_material_usage \
  tests.test_gui_submission_check tests.test_submission_check -v
```

285 tests / 38.527s / OK, exec 25148 exit 0;
`/tmp/icstex-v1-source-identity-focused-r3.log`, SHA-256
`05ed166f5bb1fb8287354ae137e26d5204bd0fb49f5c963e2ceca3a8f324e96c`.

Assertions exercise actual MainWindow/controller reports and worker callbacks:
candidate/update/cancel keep reports and buffer identity, actual commits clear
them, a late preedit result is accepted, and a blocked edit→Undo rejects an old
result even when text returns. Word Count reuses the unchanged cached snapshot
without launching a worker or reading editor text. Blocked reload and inactive
related-tab edits change all four report/count keys without borrowing active-tab
dirty flags. Ordinary source notifications observe the new counter before their
callbacks, without full-text reads on normal insert/Undo/Redo. Existing actual
800 ms idle-save, file-conflict, root/dependency, worker-close and PDF tests pass.

Required frozen full:

```sh
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10 python3 -m unittest discover -s tests -v
git diff --check
```

1518 tests / 140.039s / OK, exec 4947, explicit shell/tool exit 0;
`/tmp/icstex-v1-source-identity-suite-r1.log`, SHA-256
`0bfca036f7d2217fbd5931043d17e2f6e73126c238fe0d23a186b9894f40783d`.
Runtime: Python 3.12.6, PySide6 6.11.1. Post-terminal source digests match;
compileall and diff checks pass. No Traceback, RuntimeError, RuntimeWarning,
fatal Python or QObject/QThread failure was found in this full log. The seven
existing September 10/11 Python crash reports are unchanged; that does not
resolve their distinct historical causes. All test handles are terminal.
HEAD and empty index remain unchanged; held candidate feed SHA-256 remains
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

## Scope still open

This closes the reproduced R1 read-only source-identity defect locally. It does
not replace current-source physical focus/partial-composition/default-save or
formula partial-commit evidence. No Computer Use request or native window was
started this round; the previous locked-channel observation is historical, not a
new statement about the current screen. R2 native focus/layout, R3 historical
timer/AX boundaries, R5 restricted LuaLaTeX compatibility and E1–E4 remain as
listed in the acceptance matrix. R6 must retain those distinctions in handoff.

Rollback scope is only this editor-local counter and five read-only consumer
key changes with their tests; preserve the preceding source-notification and all
other shared changes. Suggested commit (not executed):
`fix(editor): keep read-only source identity stable during IME preedit`.
