# V1 M3: read-only material usage and content observations

Date: 2026-09-11 (Asia/Taipei). Local development source, not full M3 or release acceptance.

## Workflow and ownership

In an ordinary LaTeX project, open **图片** and select **检查素材使用（只读）**.
The **使用检查** tab distinguishes supported source locations, missing files,
content changes, possible same-content candidates, ambiguity and unused suggestions.
Selecting a result shows current/prior digests and locations; **定位所选引用位置**
rechecks the source content before navigating. Location counts are unique file/line
observations, not the number of times TeX executes an image command.

Each request captures the selected project, compile root, all open project buffers,
editor revisions and dependency generation. An unsaved child replaces its on-disk
uses; an unrelated .tex file outside this root's supported closure is not counted.
Edits, mode/tab changes, external events, cancel and close discard stale/late results.
Deliberate content-checked navigation preserves the report only if no other
invalidation occurred. There is one active worker and at most one latest request.
The timer compares in-memory identity only; typing does not launch a material scan.

Previous readable asset digests are bounded in-memory observations for this window
and root, with timestamps. They are not persisted SourceRecord baselines, imported
data snapshots, backup copies or evidence of experimental authenticity. A later
accepted check advances these observations; switching owner or closing discards
them. One matching digest is a possible candidate, not proof that a file moved.
No check moves files, rewrites references, deletes unused material, imports data,
saves source, starts compilation or requests network metadata.

The old thumbnail inventory remains **快捷浏览**. It now displays **使用待检查**
instead of the old approximate usage count, and its metadata index stays in memory.
GUI opening/refreshing neither loads nor saves `.icstex/asset-index.json`; existing
explicit AssetIndex persistence APIs and their tests are retained. Warm refresh
reuses the same record/metadata and is recorded as warm in import diagnostics.
The new health tab does not run that thumbnail/metadata scanner. Legacy standalone
image usage APIs retain their old approximation behavior; this is not a rewrite of
every old image reader or a native thumbnail race-hardening claim.

## Coverage, bounded reads and failure behavior

The core reuses static dependency locations, comment/verbatim masking and existing
safe source/hash/candidate-search helpers. Supported literal includegraphics,
includesvg and includepdf paths cover common image/SVG/PDF usage and a single
literal graphicspath declaration. Comments do not count; open buffers do not count
again from disk. Images are hashed as bytes, not decoded or validated as images.

Unsupported/dynamic path commands, multiple graphicspath scopes, ambiguous
extension candidates, nonstandard source inputs, unsafe/linked/internal paths,
unreadable inputs and exhausted limits keep coverage unknown. Incomplete static
coverage cannot establish a definite unused or missing verdict. Positive observed
locations and content differences may still be shown. A same-content candidate
can itself have no use under its new name; this never authorizes deletion.

Limits per pass: 4 MiB per source, 32 MiB source bytes, 64 MiB per asset, 256 MiB
asset bytes, 2,000 input/asset records, 2,000 directory entries and 10,000 static
references. Source and asset contents are reread before acceptance; assets use a
second separate 256 MiB budget, so total asset reads can reach 512 MiB and source
reads about 64 MiB plus growth sentinels. Missing candidates are checked for
reappearance. Changed observations are discarded, not returned as current success.
Directory enumeration and hashing reject observed links and internal paths using
the existing descriptor-anchored POSIX helpers. This is not an immutable filesystem
snapshot, hard I/O deadline, cloud-availability guarantee or native Windows reparse
race acceptance. M4/M5 still own consistent recovery and frozen delivery.

## Regression evidence

Initial orientation reproduced saved-source double counting, commented use,
graphicspath misses and stale disk use after an unsaved removal. Receipt:
`/tmp/icstex-v1-m3-material-orientation-red-r1.log`; exit 0 confirms the old defects.
New core and GUI tests first failed with missing implementations. Core/GUI coverage
now includes byte/entry limits, cancellation, unsafe paths, ambiguity, changed and
reappearing inputs, noncurrent drafts, stale navigation, close/late-result rejection,
one-active/latest scheduling, typing without usage scans and zero project writes.

- Earlier focused integration: 91 tests, 7.676 seconds, exit 0,
  `/tmp/icstex-v1-m3-material-focused-r2.log`.
- First full discovery: 1,223 tests, 368.431 seconds, exit 1, one failure,
  `/tmp/icstex-v1-m3-material-suite-r1.log`; exec `15407` is terminal. The old GUI
  test required a disk cache merely from refresh. Its replacement verifies the
  intentional no-write contract as well as same-index/record reuse and one metadata
  read. The stronger test exposed a real warm-scan diagnostic misclassification;
  `/tmp/icstex-v1-m3-material-memory-index-red-r1.log`, one test, exit 1. The GUI
  metric now uses actual cold/warm in-memory index ownership.
- Final focused integration: 109 tests, 9.786 seconds, exit 0,
  `/tmp/icstex-v1-m3-material-focused-r3.log`. This includes AssetIndex persistence,
  import diagnostics, material/citation/dependency and submission-check regressions.

Final app Python path/content SHA-256:
`cc506a5a59b3f4e187937ed4283650b53f6b7de817c7f249f7896b3f7e5fa61e`.
Compileall and whitespace checks passed. Full verbose discovery passed 1,223 tests
in 364.943 seconds, exit 0, on the same frozen app tree. Exec `96648` / PID `96374`
are terminal; receipt `/tmp/icstex-v1-m3-material-suite-r2.log`. The app hash was
rechecked unchanged after completion. No failed test, traceback, RuntimeError,
RuntimeWarning or fatal Python failure appeared. Offscreen/font warnings remain
separate from native acceptance; suite success does not close the M6 quality gaps.

## Actual window and FINAL evidence

`tools/probe_material_usage.py` creates a new synthetic project and isolated settings,
five real PNGs, a root and child source. Final-source run:

```bash
QT_QPA_PLATFORM=offscreen python3 tools/probe_material_usage.py \
  --output /tmp/icstex-v1-material-20260911-r4
```

Exit 0, `/tmp/icstex-v1-m3-material-product-r4.log`, exec `3179` terminal. Environment:
macOS 26.6.1 arm64, Python 3.12.6, Qt offscreen. Initial four referenced/one unused
assets and later changed/candidate/missing/present distinctions were verified.
Checks preserved every source/asset/cache byte and did not authorize compilation.
Only explicit fixture actions changed, renamed or deleted the synthetic images.

A separate explicit pdfLaTeX FINAL generated one page showing four colored images;
the rendered page was visually inspected. PDF SHA-256:
`ddb60095102d50de0b549316052306243bddf050f37afc84e080cd193845aed7`.
The existing compile action created its usual `.icstex/history` records; original
input bytes stayed unchanged. Later checks did not recompile the stale PDF or
change its build ID. Navigating to `chapters/child.tex:4` preserved page, zoom and
scroll state. An unsaved child removed its disk uses without saving; cancel left
source, assets and cache unchanged.

Actual queued watcher events can invalidate a just-completed check. The probe
observes that invalidation and explicitly retries, without suppressing events;
the three accepted refresh sequences took 1, 4 and 1 attempts. Its five-asset
measurement of 621.71 ms includes a deliberate 600 ms watcher-settle wait and is
not worker latency or a performance benchmark. This does not guarantee stable
results while external writes continue.

Five scale tiers and two requested sizes were exercised. The smaller 880x640
request clamps to the existing 1080x720 minimum. Control centers were reachable
through the outer scroll area; 100% controls and 150% detail captures were inspected.
At high scale/narrow width, text and columns still require scrolling and the central
Source/PDF area is cramped. This is not full readability, keyboard or arbitrary
narrow-screen acceptance. Evidence directory retains report.json, captures and PDF.

Probe r1 incorrectly treated the explicitly requested compile's existing history
writes as checker writes; its assertion was narrowed to preserve all original
inputs and allow only those history records. R2 exposed queued watcher invalidation;
r3/r4 record bounded explicit retries. These failures were not silently called passes.
R3 tested the earlier app hash `23fea509eddac01e2a35c1a940eebfabd8722a7747306decffbafa7fab6020b3`;
r4 repeats the product workflow after the warm-scan metric correction.

## Remaining gates and next slice

Native image/formula/material/citation, IME/AX, Windows and human usability checks
remain unaccepted; the last desktop observation required manual Mac unlock and
was not bypassed. Broad legacy inventory scan cost and Qt scale/lifecycle gaps
remain M6 work. At 05:04 this Mac reported 8,842.94 MiB swap use and load averages
1.63/2.66/3.38; suite elapsed time alone cannot isolate an application regression.

An independent real-dialog, synthetic-memory-only probe reproduced an existing
MergeDialog defect: accepting one conflict deletes a different cell in the same
row. Receipt `/tmp/icstex-v1-m3-merge-orientation-red-r1.log` confirms the loss; no
project was written. This is not fixed or accepted. The current workspace merge
button also does not apply through ProjectSession/Undo, and SourceRecord does not
contain a table baseline. The next technical-repair slice must preserve every cell,
use a genuine captured base and separately preview/confirm/CAS-guard one undoable
operation; it must not invent a baseline or turn status refresh into resynchronization.
Further adapter orientation confirms 5,001 synthetic CSV body rows silently become
5,000 (`/tmp/icstex-v1-m3-import-limit-orientation-r1.log`); existing IDs are also
position-based. Incomplete imports and ambiguous row identity must not enter a
supposedly safe merge. This is next-slice evidence, not a repaired import workflow.

M3 technical repair, M4 recovery, M5 frozen delivery and M6/M7 closeout remain open.
No stage completion, source commit/push, packaging, installed-app replacement,
credential, CI, website, signed feed, deployment or release change is claimed.

Suggested commit message only: `feat(materials): add bounded read-only usage and content checks`.
