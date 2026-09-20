# M6 response, dependency and native PDF measurements

Status: the reproduced 200-child GUI dependency-refresh delay is reduced by a
local path-check optimization. Focused tests, same-sample response probes and
three native PDF trials pass. Required full regression passed 1457 tests with
explicit exit 0; final app/tests hashes match after terminal.
This is not complete M6, native IME/AX/Windows/human acceptance or release readiness.

## Scope and source

Only synthetic temporary projects, isolated INI settings and named reports were
used. No student document, installed app, system setting, credential or release
was changed. Shared prior work remains uncommitted; HEAD is `3bde2b5`.

Final app SHA-256:
`e1bf4fa9720c84cae9bda909da55dd890103f85ec36561f3a3512500e6e647da`.
App+tests SHA-256:
`22fe3ad301b10219aedd3bd6d198b5341c89766c30438f08a23aa3ee4247649c`.
Sorted relative Python paths/NUL/raw bytes/NUL, app then tests. Each measurement
rechecks the app hash after completion. Environment: macOS 26.6.1 arm64,
Python 3.12.6, PySide6/Qt 6.11.1, watchdog 6.0.0, existing local XeLaTeX/latexmk.

## Measured problem and bounded repair

The dependency benchmark keeps roughly 4,000 synthetic words across 10, 50 or
200 child files, with explicit `.tex` inputs. It records core graph/hash costs
separately from the real GUI membership callback and a 10 ms timer. Each GUI
case has three repeated refreshes; files, cursor, scroll and compilation authority
must remain unchanged, and accepted close must destroy the actual Qt object.

| Child files | Before GUI callback range (ms) | After range (ms) | Before timer lateness (ms) | After lateness (ms) |
| --- | ---: | ---: | ---: | ---: |
| 10 | 8.067–11.395 | 4.116–4.678 | 1.265–2.212 | 0.313–1.307 |
| 50 | 26.000–30.420 | 12.839–13.274 | 16.163–20.582 | 2.915–3.342 |
| 200 | 72.218–76.238 | 46.376–46.549 | 62.352–66.847 | 36.470–36.656 |

The original 200-child result exceeded the 50 ms investigation threshold.
A separate cProfile diagnostic attributed 77 of 103 ms to 603 calls of
`safe_project_input`; `relative_to`/`is_relative_to` repeatedly constructed
ancestor paths. Profile instrumentation is not an acceptance timing sample.

The validator now compares path components and tracks depth for `..`, avoiding
those repeated ancestor constructions. Scope resolution, per-call link/junction
checks, rejection of traversed internal directories, generated suffixes, scope
root and escapes remain. Native `os.path.normcase` is retained for platform path
comparison; this is not Windows execution evidence. There is no path-safety
cache, new asynchronous topology, relaxed read primitive or changed source format.
Synchronous ownership and compilation-time child-save behavior stay intact.

New tests cover in-scope parent steps, escape-and-reentry refusal, component
prefix collisions, internal-directory traversal, generated paths and replacing
a previously safe directory with a link. Existing same-mtime input changes,
shared roots, source conflicts, late results and PDF ownership remain covered.

RSS is reported as current process KiB, including Qt/Python allocators and caches.
It is not a leak conclusion or an OS memory-return guarantee. The separate
accepted-close retention receipt remains authoritative for its larger lifecycle
sample; no link to the old stylesheet SIGSEGV is inferred.

## M0-comparable response and build work

`bench_response_pipeline.py` retains the M0 4k/12k/40k-word fixtures, repetition
counts, hidden and visible panel samples, five count requests, ignored-directory
case and three build trials. Additional cases are separate keys, not replacements
for the original metrics. OS caches were not flushed; host workload and thermal
state were not controlled. No benchmark overlapped our full/focused tests or
another benchmark. These are measured samples, not universal latency guarantees.

| Metric | M0 | Final source | Investigation target |
| --- | ---: | ---: | ---: |
| Visible outline edit median / max | 0.230 / 0.441 ms | 0.233 / 0.343 ms | max < 2 ms |
| Uncached Word Count dispatch max | 0.266 ms | 0.245 ms | < 10 ms |
| Word Count timer lateness | 18.085 ms | 7.482 ms | < 50 ms |
| Outline refreshes after 15 edits | 1 | 1 | coalesced |
| Asset scans for that edit burst | 0 | 0 | 0 |

With the submission-check panel visible, 15 edits launch zero immediate check,
count, graph or asset work. After debounce there is one count worker and one
dependency refresh, no check worker or asset scan, and the old check is invalidated.

Final source fallback medians for 4k/12k/40k words are 52.841/206.694/1054.226 ms;
TeXcount medians are 106.923/327.907/1510.166 ms. The earlier run was slower even
in unchanged count code. The relevant count/encoding/observation/tool modules
have no diff from the M0 Git baseline: do not attribute all between-run timing
variation or compiler changes to the path optimization.

Build samples now label purpose, `-g`, latexmk rules, API wall time and internal
duration. Median unchanged PREVIEW is 60.525 ms (no rules); unchanged FINAL is
801.313 ms (actual BibTeX/XeLaTeX/PDF work). Their cold medians are 1806.955 and
1789.884 ms. The old warm FINAL no-op is not equivalent to forced FINAL and is
not used to claim a regression or a speedup. This core PREVIEW case uses original
inputs; actual image proxies are measured separately below.

## Native visible PDF and harness correction

The existing stress fixture contains two deterministic 6000×4000 RGB images:
38,624,187-byte JPEG and 54,240,611-byte PNG. Three fresh temporary projects each
exercise cold PREVIEW, unchanged PREVIEW, cold FINAL, unchanged FINAL and edited
PREVIEW. The compiler and actual PDF viewport run on Cocoa. This is not a typical
student project or hardware/compositor presentation timing.

| Case | Median request-to-visible upper bound (ms) | Median process-exit-to-visible (ms) |
| --- | ---: | ---: |
| Cold PREVIEW | 1582.037 | 54.507 |
| Unchanged PREVIEW | 382.533 | 43.212 |
| Cold FINAL | 3063.109 | 440.417 |
| Unchanged FINAL | 2808.934 | 435.304 |
| Edited PREVIEW | 934.401 | 40.095 |

All 15 results show two pages, a rendered red image region, isolated output
trees and a displayed path matching the actual result. PREVIEW outputs are
about 4.56 MB; FINAL outputs about 92.79 MB. Cold proxy preparation is
619.018–669.207 ms; warm per-trial medians 42.151/61.059/47.127 ms. Proxy caches
are warm during the build cases, so the table is not complete cold application
startup. PDF hashes can vary with generated metadata; no cross-run byte identity
is promised. Three representative native captures were visually inspected.
Early-Paint screenshots can still show a transient workspace header; these are
visible-content timing evidence, not a separate final-header acceptance claim.

Native r1 (exec 6899, exit 1) completed trial 0, then trial 1 reached document
Ready but no Paint event before the 90-second probe deadline. Its finally block
also exposed the probe's context-free observation timer accessing a deleted
viewport. The computer-use skill observed actual native state; test-triage
separated the timeout from this teardown error. There was no new Python crash.

Only the harness was changed: repeated trials keep QApplication alive across
closing its last window, and the observation timer is bound to its QObject.
The application remains unchanged between native r1/r2. Native r2 (exec 16266,
exit 0) completes all three trials and destroys every window. This addresses the
benchmark's deliberate post-last-window continuation, not a product quit-policy
change or proof that the earlier unrelated stylesheet crash is fixed.

## Receipts and remaining boundaries

In-repository, inspectable numerical data (native screenshot paths removed):

- `data/v1/m6-response-before-2026-09-11.json` and `m6-response-2026-09-11.json`.
- `data/v1/m6-membership-before-2026-09-11.json` and `m6-membership-2026-09-11.json`.
- `data/v1/m6-pdf-2026-09-11.json`; native images remain local only under
  `/tmp/icstex-v1-m6-pdf-native-r2/trial-{0,1,2}`.

Focused: `QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 python3 -m unittest
tests.test_project_dependencies tests.test_gui_dependencies
tests.test_gui_preview_pipeline tests.test_gui_submission_check -v`.
58 tests / 11.252s / OK / exit 0, exec 33638; log
`/tmp/icstex-v1-m6-path-components-focused-r1.log`, SHA-256
`153bc6c6df55d2b89de9044f4e529d0d4a4637c70f1425bf327dd211bd23fd93`.
The nine core boundary tests also passed before the optimization; the red evidence
for this change is the measured delay, not a fabricated failing correctness test.

Final response exec 98350 and membership exec 40853 each exited 0. Native r2 raw
JSON SHA-256 `8d8c84a119a54b2ad129e1f973c03f3f79d9dd8d35ec8872fef9bd92dd2e4ccc`;
native log SHA-256 `1a4664dde2de97172e90a45d48ca06e10d795b3f98306500faf688959fd4774f`.
Compileall, probe syntax and diff checks pass. Required frozen full is terminal:
1457 tests / 138.295s / OK, exec 88033, explicit shell and tool exit 0. Log
`/tmp/icstex-v1-m6-response-suite-r1.log`, SHA-256
`d7867df7500aafa418fe194e898530b34181a36f54e8a3396f69ffad8b889c55`.
Command: `QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 nice -n 10 python3
-m unittest discover -s tests -v`. App and app+tests hashes still match after
terminal; no new Python crash report, all this slice's handles/windows closed.
The local candidate appcast remains SHA-256
`be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

Original stylesheet SIGSEGV, restricted LuaLaTeX initialization, full IME/AX,
Windows and real-user checks remain open. The scoped Cocoa selected-children
guard and font-alias warning remain. Next reconcile the complete A01–A14 local
acceptance matrix against current evidence and identify any remaining product
gap; M7 is a readiness checklist only. No Git, packaging/install/signing or
publication authority is added by these measurements.
