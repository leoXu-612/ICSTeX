# M6 citation layout and scrollable tool navigation

Bounded R2 layout evidence, not complete M2/M6/A12 or release acceptance.
All source windows use offscreen Qt with isolated settings and synthetic files;
no foreground operation, native IME/AX claim, student content, network lookup,
compilation, installed-app replacement or Git mutation occurred.

## Source and failures

Branch `codex/v1-development`, unchanged HEAD
`3bde2b5d25803262dedef89a081ee6ffbe2b6967`; shared modifications preserved.
Baseline app `75c177e002c371a26a469a37741ec19a9bf30069fb9f6d26da9838dfeb5fd42b`.
Final app `d25a13526e611621a2a13b8823ed7deaf2b0b39678a192c9dd1c9a612372ee6f`;
app+tests `ffc66e895c4161595561327f69f0b3c3203bc08f5e955ad7de04d8dd62550251`.
Digests use sorted relative Python paths, NUL, raw bytes, NUL; app then tests.
These are source identities, not package identities.

`tools/probe_citation_layout.py` runs the real MainWindow citation controller,
checks missing/known/unused citations, captures five scale tiers at requested
1120×820 and 880×640, and navigates to an actual synthetic child line without
changing file bytes or compile authorization. Small requests clamp to the
existing 1080×720 minimum; the receipt records actual dimensions.

Baseline `/tmp/icstex-v1-citation-layout-baseline-r1/report.json` SHA-256
`06a5a15a35c855fdfb56de916142d19eab875ec5f76cc401a09366de13618c3d`;
exec 46597 exit 0 is successful observation, **not layout acceptance**.
At 150%, the outer panel required 79 extra horizontal pixels and the locate
button did not fit its viewport. Timestamp QLabel minimum hints forced the
whole inactive/active tab stack wider than the dock. Table rules/keys were elided
without tooltips. Repeated same-row-count report replacement also left the
detail blank because selecting the already-selected first row emitted no change.
The targeted red r2 had 13 failed assertions; log
`/tmp/icstex-v1-citation-layout-red-r2.log`, SHA-256
`7a1a946ed683232c78bffe453ac118bfb32020cc8c02f5c8d95cdc521234cb2e`.

## Repair and evidence quality

- Reference action rows use the existing wrapping button layout. The entry is
  labelled “检查引用”; its tooltip and guide retain the read-only/no-network scope.
- Status stays a short wrapping summary. Full timestamp/root identity lives in
  the copyable, wrapping detail and status tooltip. Simply ignoring QLabel's
  minimum width was rejected after screenshots showed a clipped long token.
- Table status width/row height follow the current font; row numbers are hidden.
  Rule/key text can remain elided in the narrow table, with complete cell tooltips
  and selected issue/key detail. Long location text retains its full tooltip and
  internal list horizontal scrolling; this is not a no-scrolling guarantee.
- Clear selection under blocked table signals before replacing a report, then
  select the first row, so repeated refresh restores its detail and locations.
- The 72-pixel navigation rail now scrolls vertically. Focus events reveal the
  actual focused button, including Up/Down navigation across all nine tools.
  The widgets, indices, signals and project/compile ownership are unchanged.

An intermediate probe's viewport-only assertions were too weak: the viewport
itself extended below the window because the fixed navigation rail imposed a
483-pixel minimum. A locate button at window y=689 was 67 pixels tall, but only
31 pixels were actually visible. The final test/probe checks `visibleRegion()`
as well as viewport containment and text-size hints. Screenshots were inspected
again after repair; the full locate button and status summary are visible.
Old r1/r2 “fully visible” flags do not establish full-window visibility.

Final-source observation: exec 74593 exit 0,
`/tmp/icstex-v1-citation-layout-final-r1/report.json`, SHA-256
`ec55025698ed8a975b5dfc2560f52c2cc7f0baa78b771601d8c3aa71a3bd6c15`.
All ten layouts have zero outer horizontal overflow and fully unclipped action
buttons at or above their text-size hints. The bounded layout predicate passes;
navigation reaches `chapters/long-path-for-source-navigation/child.tex:2`, all
three source files are byte-identical, and no compile authority is created.
The source hash matches before/after. Screenshots include `status-150-880.png`,
`controls-150-880.png` and `health-150-880.png`. No physical keyboard or Cocoa
accessibility was exercised; native post-fix verification remains outstanding.

## Regression commands

```sh
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest \
  tests.test_ui_visual tests.test_gui_citation_health tests.test_citation_health \
  tests.test_gui_editor -v
```

227 tests / 40.502s / OK, exec 40534 exit 0;
`/tmp/icstex-v1-citation-layout-focused-r1.log`, SHA-256
`382660a7119a6e19a9b7348166d6308b3672ccb692e6165795701f253798467f`.
Required frozen full:

```sh
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10 python3 -m unittest discover -s tests -v
git diff --check
```

1508 tests / 139.135s / OK, exec 93978 reached explicit shell/tool exit 0;
`/tmp/icstex-v1-citation-layout-suite-r1.log`, SHA-256
`459131c5f24f5c9ef9259798f29a65b4b998e5b58316147a8a5a3633fc61ee5d`.
Post-terminal app/app+tests hashes match; compileall, probe syntax and diff pass
again. No Traceback/RuntimeError/RuntimeWarning/fatal or QObject/QThread failure
in the full log. The seven existing Python crash reports are unchanged, not
resolved by this layout test. All handles are terminal. HEAD/index remain
unchanged; held candidate feed remains
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

## Remaining R1 finding and next action

This inspection found a separate missed input boundary: CitationHealthController
still keys periodic reconciliation on Qt's document revision. On final source,
preedit changed that revision from 2 to 3 without changing text. The report was
retained immediately, then discarded by `reconcile()`. Files remained unchanged.
This is a verified **unfixed false invalidation**, not source data loss, and
qualifies the preceding idle-save receipt's immediate-notification result.
Log `/tmp/icstex-v1-citation-preedit-reconcile-r1.log`, SHA-256
`fa414b198198f275f71ce8ea57aacd2b5c67b293d2f158bf8bb4e7202c567070`.

Next bounded background work: repair this source identity boundary and audit
other direct document-revision consumers with preedit, actual commits, blocked
external reload, late-result and cross-tab regression. Do not suppress genuine
input changes or compare whole documents repeatedly on a periodic timer.
R1 physical composition, R2 native focus/layout, R3 historical timer/AX, R5
restricted LuaLaTeX, R6 reconciliation and external E1–E4 remain open.

Rollback is limited to ReferencesPanel presentation/selection and the tool rail
scroll/focus changes plus their tests. Do not revert unrelated shared hunks.
Suggested commit (not executed): `fix(gui): keep citation controls visible at high UI scale`.

Follow-up: the subsequent [source-identity receipt](v1-m6-source-identity-verification-2026-09-11.md)
records the bounded repair and new source identity. The failure above remains
the observation on this layout source, not a claim that the later fix is absent.
