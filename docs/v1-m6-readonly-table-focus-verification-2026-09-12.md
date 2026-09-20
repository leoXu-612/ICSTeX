# M6 read-only workbench table focus sweep

Nine additional read-only tables reproduced the citation table's Tab focus
trap. Each now uses widget focus traversal while arrow selection remains intact.
This is a bounded background repair, **not native keyboard or full R2 acceptance**.
No foreground operation or unlock retry occurred in this follow-up.

## Scope and identities

The prior [native citation receipt](v1-m6-citation-keyboard-verification-2026-09-12.md)
established a real Tab/Shift+Tab trap and fixed two citation tables. Inspecting
the same read-only QTableWidget setup found nine other candidates. Only tables
whose existing edit policy is NoEditTriggers were changed; editable document,
formula, table-draft and mapping controls were not changed.

Branch `codex/v1-development`; HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`. Shared changes preserved.
Baseline app SHA-256
`4f83dd34551c6fcf6fd5912df54b690471dd5fc8678e7ffdf687b6c66f0a217a`.
Final app SHA-256
`1c577ced8fa231c679d200a4211fdb6cd7d4c93c58fa9e51596404853e51b7aa`;
app+tests
`50f3884907e67e54e3042b4d22de356bc11f3a420db22694a1a4b41e3fb0eb27`.
Digests hash sorted relative Python paths, NUL, raw bytes, NUL. They are not
release or installed-application identities.

| Changed surface | File / existing table |
| --- | --- |
| Outline, search, image inventory, material check, history, labels | `app/gui/project_panels.py`, six read-only tables |
| Project diagnostics | `app/gui/diagnostics_panel.py`, result table |
| Compiler errors | `app/gui/main_window_layout.py`, error table |
| Block sources | `app/gui/blocks/navigation_dock.py`, sources table |

The production change is nine `setTabKeyNavigation(False)` calls. Ownership,
signals, source revision, save/compile and permission controllers are unchanged.
Rollback is limited to these nine calls and the two added tests, not unrelated
shared hunks or the earlier citation repair.

## Red/green coverage

`test_read_only_workbench_tables_release_tab_focus_at_all_scales` opens the real
MainWindow with isolated settings and synthetic result rows. At 90/100/110/125/
150% and actual 1080x720 it checks ten main-window tables, including the two
already-fixed citation tables. Each must retain NoEditTriggers and Down/Up row
selection, then allow Tab and Shift+Tab to focus a different widget in the same
window without changing the cell text. No compile authorization is created.
This checks focus traversal, not complete text visibility or action activation.

`test_source_table_tabs_to_actions_without_changing_model_or_files` uses the
existing synthetic saved Block/source fixture. The real source table must Tab
to Refresh, reverse to the table, then reverse out. Block content, model revision
and project file bytes remain unchanged, with zero compile launches. This case
uses the default scale; it is not five-tier Block-source acceptance.

Initial red r1 had 80 intended traversal assertion failures and one fixture
AttributeError: ProjectSession exposes `_revision`, not `revision`. The fixture
was corrected before product edits. Its log is retained at
`/tmp/icstex-v1-readonly-tables-red-20260912-r1.log`, SHA-256
`b354395a53f435c1bd2864563d3dd54f57167115ebf4c91920264f92b72cf3bc`.

Corrected baseline red r2: exec 25269 exits 1, 2 tests / 1.258 s / 81 assertion
failures: eight unfixed main-window tables x five scales x two directions, plus
the Block source table. The two prior citation tables already pass. Log
`/tmp/icstex-v1-readonly-tables-red-20260912-r2.log`, SHA-256
`6fda7ff10f912f4a640372ba7b12c25a121ecbfe8d85aa007daa7316ff22b8db`.

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_ui_visual tests.test_source_status_gui tests.test_gui_citation_health \
  tests.test_gui_material_usage tests.test_gui_editor -v
```

Final focused: 273 tests / 52.890 s / OK, exec 81322 terminal exit 0.
`/tmp/icstex-v1-readonly-tables-focused-20260912-r1.log` SHA-256
`00ea92449eaeaa75c4a60076e6754cc4823a1dcf1200d38665cffc12f4f91df6`.
Existing formula/table editing, source/preview and material/source controllers
remain covered by their assertions; green tests do not establish native behavior.

Required frozen full, exec 90981 terminal exit 0:

```sh
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest discover -s tests
git diff --check
```

1554 tests / 159.894 s / OK. Full log
`/tmp/icstex-v1-readonly-tables-full-20260912-r1.log` SHA-256
`b4a08a526b836f90d9a17b15b0be9136ad85d54ac86be1ba722adaa5157fa26a`.
Post-terminal app/app+tests hashes match. No Traceback/RuntimeError/RuntimeWarning/
Fatal Python/ignored exception/QObject/QThread failure matches in that log;
offscreen-plugin/font warnings retained. Ten September Python crash reports,
HEAD and empty index unchanged. All test handles are terminal. Held candidate
feed SHA-256 remains
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

## Remaining boundary

The last actual desktop result remains the locked-Mac response recorded in the
prior receipt. This turn did not poll or operate the desktop and does not assert
a refreshed lock state. Native post-fix citation navigation, tool-rail keys,
all scale tiers and remaining action activation/visibility must still be tested
after manual unlock. Existing double-click actions were not changed into a new
keyboard activation policy by this Tab repair. Return/Enter activation is not
accepted merely because a table can now release focus.

No student content, network lookup, compile, installed-app replacement, Git
mutation, packaging or release operation. R3 historical/AX limitations, R5
maintainer decision, R6 and external E1-E4 remain unchanged.

Suggested commit only: `fix(gui): release focus from read-only workbench tables`.
