# V1 M3: read-only ordinary-source citation health

Date: 2026-09-11 (Asia/Taipei). Local source only; not full M3 or release acceptance.

## User workflow and ownership

Open an ordinary LaTeX project, show the **引用** toolbox and choose **检查项目引用（只读）**.
The **引用检查** tab reports duplicate keys, missing citations, unparsed syntax,
known uses and unused-entry suggestions. Select a result and a location, then
choose **定位所选位置**. Locations retain project-relative file/line information;
navigation rechecks the captured content before using the line number.

The current compile root, selected project, open editor contents/revisions and
dependency generation own each report. An explicitly opened BibTeX draft is
checked instead of its disk version without saving it. Arbitrary tab/mode switches,
edits and external events invalidate results; deliberate content-checked report
navigation may retain the dated record. One active worker and one latest pending
request bound refreshes. Cancel/close reject late results. Typing does not launch
a new citation scan. Checking never saves, compiles, imports, rewrites, deletes or
requests network metadata. Existing DOI/arXiv import remains a separate explicit action.

The old conventional library remains a **快捷库**, not a complete project health
claim. Its read helper now uses bounded strict decoding and no-follow input rules;
it does not silently replace undecodable bytes. Creation/import authority is unchanged.

## Static coverage and limits

The core follows supported literal project input/include/subfile and bibliography/
addbibresource paths, reusing `static_dependencies` with a bounded captured reader.
Common single-citation commands support optional arguments, stars and comma-separated
keys. TeX comments, verbatim and macro definitions do not invent citation uses.
BibTeX entries retain repeated keys and raw fields, including strings/concatenation;
literal crossref/xref/xdata/related/entryset relations and nocite are considered uses.
No arbitrary TeX expansion, field-schema/metadata truth validation or distro search
is claimed. Missing distro classes/packages are not mislabeled as missing project
bibliographies; local style inputs still use the same bounded reader.

Manual bibliographies, aliases, sections/segments, conditional/dynamic definitions,
unsupported commands, malformed fields and nonstandard source suffixes keep
coverage unknown. This is a conservative supported-syntax observation, not a TeX
interpreter. Incomplete coverage cannot justify a definite missing/unused verdict.
Unused entries are suggestions, never an instruction or automatic action to delete.

Limits: 4 MiB per file, 32 MiB accepted input bytes per request, 2,000 static input
candidates, and bounded 10,000-item citation/entry, field and relation categories.
Parser issue lists are bounded with an explicit terminal limit issue. Disk inputs
are reread with their captured-size bounds before accepting the report; a growth
sentinel is permitted. Captured buffers and disk bytes have distinct SHA-256 input
identities. This detects observed changes; it is not an immutable snapshot, hard
I/O deadline, cloud availability guarantee or native Windows reparse-race acceptance.

Grammar reference: Oren Patashnik's author manual
[BibTeXing](https://www.openoffice.org/bibliographic/btxdoc.html), especially its
strings/concatenation, cross-reference and nocite sections and the distinction
between a percent sign in a database and a TeX comment. The real synthetic FINAL
below uses an escaped percent for correct rendered TeX text. CTAN PDF retrieval
was unavailable; the author manual's HTML mirror was read instead.

## Reproductions and regression

- Existing shortcut behavior: duplicate keys collapsed, optional-argument citations
  were missed, commented citations were counted and declared nondefault libraries
  were ignored. Synthetic receipt: `/tmp/icstex-v1-m3-citation-orientation-red-r1.log`.
  Its exit 0 confirms reproduction, not acceptance.
- Initial new syntax/core tests failed because the modules were not implemented.
  Boundary red tests later reproduced optional distro-input misclassification,
  empty-file recheck failure, false complete manual/scoped/alias coverage and the
  legacy helper reading links/replacing undecodable bytes. Receipt:
  `/tmp/icstex-v1-m3-citation-boundary-red-r1.log`, 27 tests, seven failures and one
  error. Its shell also ran tail, so the outer shell exit 0 is not a test pass.
- Focused core/GUI/dependency/helper tests: 36 passed in 1.434 seconds, exit 0,
  `/tmp/icstex-v1-m3-citation-focused-r2.log`.
- Broader integration, including existing editor panel and submission checks:
  80 tests passed in 9.495 seconds, exit 0,
  `/tmp/icstex-v1-m3-citation-integration-r2.log`. The preceding attempt also named
  a nonexistent test module and exposed macOS /var alias handling in the shortcut
  reader. The module invocation was corrected and only the selected directory
  normalized; bibliography leaf/nested links still remain rejected.

Frozen app Python path/content SHA-256:
`a12ade12f6d5573f99a03e83f8ef9e3b784538b5c0cfc4cbe520ba0ad9a84baf`.

Compileall and whitespace checks passed. Full verbose regression passed 1,200 tests
in 559.206 seconds, exit 0. Exec `33298` / PID `88960` are terminal; receipt
`/tmp/icstex-v1-m3-citation-suite-r1.log`. The app hash was rechecked unchanged after
completion. No test failure, traceback, RuntimeError, RuntimeWarning or fatal Python
failure appeared. Offscreen/font warnings remain separate from native acceptance.

The slow full-suite scale phase remains an M6 performance question. A one-second
sample of the confirmed live test process showed QApplication stylesheet work and
a 2.0 GiB process footprint; receipt `/tmp/icstex-v1-m3-citation-suite-sample-r1.txt`.
At 04:20 the system reported 8,817.81 MiB swap use and load averages 6.79/4.73/3.94.
These observations do not isolate a patch-specific slowdown or prove an app leak.

## Actual product and FINAL evidence

`tools/probe_citation_health.py` uses actual MainWindow/controller/core operations,
isolated settings and two synthetic projects. Final-source run:

```bash
QT_QPA_PLATFORM=offscreen python3 tools/probe_citation_health.py \
  --output /tmp/icstex-v1-citation-20260911-r3
```

Exit 0; receipt `/tmp/icstex-v1-m3-citation-product-r3.log`. Python 3.12.6,
macOS 26.6.1 arm64, Qt offscreen. The four-file check took 17.49 ms in this one
run; this is not a benchmark target or a large-project performance claim.
Verified missing/duplicate/unused distinctions, child line-2 navigation, BibTeX
buffer precedence, cancel and zero source-byte changes; checking did not authorize
compilation. Five scale tiers were rendered with two requested window sizes;
buttons were reachable through the existing outer scroll area. The 880x640 request
was clamped by the existing minimum to 1080x720. Narrow table columns still require
horizontal scrolling; this is not unrestricted narrow-screen/native acceptance.

The second project separately triggered an explicit actual FINAL. Its `.blg`
confirms BibTeX 0.99d (TeX Live 2025), four entries and no BibTeX warnings. Strings,
concatenation, crossref and nocite produced one PDF page. Extracted text includes
`100% original`, the child/parent relationship and the nocite-preserved book.
Source bytes stayed unchanged; the PDF page was rendered and visually inspected. PDF SHA-256:
`d9a5d659c8a3c4c5a39d9126bf67dd29154c6ba433774c2e715595728b52a811`.
Evidence directory contains `report.json`, scale/control captures, actual `.blg`
and `citation-final.pdf`. Captures were inspected; offscreen is not native proof.

Probe r1 mistakenly called the existing engine-change action, which explicitly
compiles, before asserting no compile authority; its first captures also omitted
the hidden toolbox. R2 used the existing `compile_after=False` seam and showed
the toolbox; r3 added top-control captures and escaped the fixture's percent for
the expected PDF text. These were probe corrections, not citation-check compilation.

## Open gates

The last desktop observation requires manual unlock. Native image/formula/citation,
IME/AX, Windows and human usability checks remain unaccepted. M3 material usage and
separate diff/confirmation/CAS/Undo repair, M4 consistent recovery, M5 frozen delivery
and M6 quality closeout remain open. M1 submission checks retain their existing
independent static rules; this panel does not silently replace the submission snapshot.
No universal session, authority format, package, installed app, credential, CI,
signed feed, website, release or Git remote mutation is part of this slice.

Suggested commit message only: `feat(citations): add bounded read-only project health checks`.
