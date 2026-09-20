# PDF layout and viewport repairs

Date: 2026-09-12. Local bounded repair; not complete V1 or release acceptance.

## Final source

- Branch `codex/v1-development`, HEAD `3bde2b5d25803262dedef89a081ee6ffbe2b6967`.
- App SHA-256 `08de3e1c73ea586268873b99d67a6be3197198e372490033f987b35dc8377663`.
- App+tests SHA-256 `c1bd2ca4016ca6fd4aa09a36eb1a4368e90a89ee2df29b66aed9263168919408`.
- Sorted relative Python path/NUL/bytes/NUL digest: 207 app / 326 app+tests files.

The source/PDF wrappers now use their content-derived minimum-size hints rather
than impossible fixed 430+360px minima. Five-scale tests check sibling
non-overlap, pane bounds and every ancestor of the core PDF controls at 1080x720
with the toolbox open. They do not rely on visibleRegion alone.

Zoom increments use the effective displayed scale, including logical DPI.
Page geometry follows Qt's integer per-page sizes, spacing and widest-page
centering, including mixed-size documents. Ordinary zoom and Fit Width preserve
the reading point; Fit Page explicitly centers the whole current page.
A parent-owned one-shot timer compensates for scrollbar-induced viewport
resizing. Page/coordinate navigation, load, clear and destruction cancel it.
Jumping to an already-selected page also resets its actual scroll position.
No source, compiler, export authority or PDF renderer implementation was changed.

The geometry was checked against
[Qt 6.11.1 QPdfView](https://raw.githubusercontent.com/qt/qtwebengine/v6.11.1/src/pdfwidgets/qpdfview.cpp),
especially calculateDocumentLayout and the current-page line at 40% viewport
height. This is the inspected dependency implementation, not a universal Qt API
guarantee; the tests also inspect actual rendered pixels and navigator outcomes.

## Red/green evidence

- Initial red r1: 2 tests/1.495s, 18 failures plus one fixture error: the scale
  manager was read before MainWindow installed it. The interpreter teardown
  emitted a deleted-QPdfDocument callback warning; explicit loaded-panel cleanup
  removes that fixture teardown path, not a claim about historical R3 causes.
- Geometry red r2: 1/1.712s, five failures, exec 92988 exit 1: 35px sibling
  overlap at 90–125%, 60px at 150%.
- Focused intermediate runs preserve failures for scrollbar viewport resizing
  and same-page navigator jumps. The mode setup is settled before navigation;
  the production jump now positions the actual page even if its number matches.
- Final focused r5: 16/7.271s/OK, exec 90193 terminal exit 0. This includes all
  PdfPanel tests and two actual MainWindow layout/keyboard cases.
- Rendered red-marker widths/heights change in both zoom directions in three
  modes on a mixed-size three-page PDF. These pixel assertions independently
  constrain scale calculations. First/middle/last page and reading-point tests
  cover both directions; navigation/load/clear/destruction reject late anchors.
- Native r2 exposed a further Fit Page defect: keeping the old point clipped
  the page bottom. A new whole-page-bounds predicate failed on all three pages
  (1/1.751s, exec 68006 exit 1), then passed after explicit page centering.
- Final expanded PDF/visual/preview/editor/export suites: 291/77.035s/OK.
  Sequential exec 78234 then completed the required frozen full:
  1573/231.650s/OK, terminal exit 0. Full log SHA-256
  `38411b2ec193bc8b7d01ecb7af4a1cd659c3825527c2dcf25791cf7174d9fd69`.
  Post-terminal source hashes match; compileall/probe syntax/diff pass.
  HEAD, empty index, held candidate feed and eleven retained crash reports are
  unchanged. All test/probe handles are terminal; no native test window remains.

Final focused log SHA-256
`ef3c3514d36decb0162e139441b6e5e69c4a8d95a2d095c828ff1e66f66d6a3a`;
expanded log SHA-256
`09819b9c533b9f4f402a926ea9c4f956593bc6677b972919ce260ab9f28617ac`.

The earlier app `8d07aba81c6ed6f1b5ac2046a353cb09965bb7e68ff188b9ee389111bc5e7acd`
passed 291/75.913s expanded (exec 42589) and 1573/257.699s full (exec 82627).
Those results predate Fit Page centering and are not the final-source full pass.

## Native evidence and observation limits

All runs use the isolated production MainWindow and a labelled QPdfWriter
three-page fixture. The QA loading menu is harness setup, not a product workflow
or LaTeX FINAL. CUA supplies actual keys; the probe records but does not generate
native input. All three windows were closed and processes exited 0, without
errors, interruption or timeout; original PDF/source bytes and source buffer
remain unchanged. No export, reveal or compilation occurred.

| Run under `/tmp/icstex-v1-pdf-geometry-native-20260912-` | Process | Report SHA-256 |
| --- | --- | --- |
| r1 | 28201 exit 0 | `44aa3228076c1b1f44c03d6e9c47e5cb811ec74c484cf610160e8ea2a46bd7f3` |
| r2 | 33108 exit 0 | `aa2f8f673e6285dde5287d87583aae94978d7e6230001e605a3d0e82363f6691` |
| r3 | 74670 exit 0 | `d2c6343f0ada9bb6e737315914416e93db6ec45bfaa314384591bd3ed04b4fa8` |

r1/r2 retain the intermediate app hash above. Physical 100%/150% page, zoom-out,
zoom-in, Fit Width and More selection have action/focus/scale records. At 100%,
page 2 changes from effective 0.5193277 to 0.4515893 and back without page drift.
At 150%, page 3 actual before/after screens show shrinking without page change.
The final r2 Fit Page screen retains the bottom-clipping failure, not a pass.

The combined CUA AX/screenshot call sometimes returned an older image while
the AX values updated. A normal QApplication.exec observer and settled widget
grabs were added; the combined-call issue still occurred. Separate getScreenshot
then returned current page/scale images. Do not attribute the stale screenshot
to the app or to the former event loop without further evidence. More popup
images are recorded separately because a main-window screenshot excludes them.

r3 applies to the final app hash: native More/arrow/Return selects Fit Page for
page 2 at 100% and page 3 at 150%. Separate current CUA screenshots show the
whole page inside the viewport in both cases. Final 150% state is
`r3/state-017-settled.png`, page 3, FitInView, scroll y=356; r2's failing value
was y=315. All core controls remain unoccluded. This final run tests the centering
increment; it does not relabel r2's zoom actions as new-source executions.

Final probe SHA-256 `9692efa269d3b13e8a296af78b93d9e3e3da111a27e59284c1bd3e0a0f802847`.
AX selected-children mitigation, font alias, IMK and Caps Lock messages remain
recorded. No full VoiceOver, HiDPI, historical-crash-causality or release claim.

## Next action

Close the completed PDF-specific defect rows using this evidence. Reconcile the
original M2/M6 requirements against existing receipts and list only concrete
missing mandatory cases; do not keep an unbounded 'broader native coverage'
placeholder or repeat accepted console/IME cases. R3 reliability disposition,
R5 protected LuaLaTeX security/toolchain decision and E1–E4 remain separate.
No automatic commit/push/package/install replacement/release.

Suggested commit only: `fix(gui): preserve PDF viewport and prevent pane overlap`.
