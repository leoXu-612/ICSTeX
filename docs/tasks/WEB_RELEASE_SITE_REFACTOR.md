# WEB-RS-001 - Release Website Visual and Information Refactor

Status: `QUEUED - RELEASE GATE`

Priority: `P0 before public Pages deployment`

Source: maintainer-provided deep research report, integrated on 2026-08-08.

## Objective

Refine the existing static Release Website into a quiet, precise and professional
entry point for ICSTeX 2.1 without rewriting release logic. On a mobile first
viewport, a student must be able to identify the product, current version,
Formula Intelligence positioning, macOS availability and the primary action.

GitHub Releases remains the artifact and release-metadata source of truth.
GitHub Pages is the intended public display target. Vercel may be used for
authenticated review, but it is not the release authority.

## Current Evidence and Conflicts

- `website/index.html` already uses Pico CSS, `config.js`, `app.js` and generated
  `release.json`; preserve that architecture.
- `id="download"` currently appears twice and must be reduced to one unique ID.
- The feature eyebrow contains a hard-coded `2.1 BETA 1`; release version and
  channel must continue to come from `data-release-*` bindings.
- The current page has more narrative density than the requested mobile-first
  release path. Windows status is necessary but must not compete with the macOS
  primary action.
- The current Vercel deployment is protected and marked `noindex`; public Pages,
  GitHub Release, tag and branch publication remain separately approval-gated.

## Non-Regression Boundaries

- Keep static HTML, local Pico CSS, `styles.css`, `config.js`, `app.js` and
  generated release metadata. Do not add React, Next.js, Tailwind, a Node build
  chain, analytics, remote fonts or runtime CDN dependencies.
- Preserve every existing `data-release-*` contract and the disabled-download
  behavior while `github_release_published` is false.
- Do not copy version, tag, channel, asset URL or publication state into HTML or
  JavaScript constants.
- Do not alter application source, packaging artifacts, release checksums, tag,
  GitHub Release or Pages state as part of this assignment.
- Preserve semantic HTML, keyboard navigation, visible focus, alt text, reduced
  motion and local-first privacy boundaries.

## WEB-001 - Mobile-First Hero

Suggested executor: Terra-class frontend implementation.

Writable files:

- `website/index.html`
- `website/styles.css`
- focused assertions in `tests/test_release_site.py`

Acceptance criteria:

- The H1 identifies ICSTeX and renders the current version through
  `data-release="version"`; it does not hard-code `2.1` or the full release tag.
- `Formula Intelligence` is visible as the product subtitle.
- The primary CTA remains `data-release-download="macos-primary"`, says Apple
  Silicon explicitly and remains disabled until verified release metadata enables
  it.
- One centered `assets/main-window.png` is the Hero product image. At 390 x 844,
  the product identity, dynamic version, subtitle, CTA and at least the leading
  edge of the screenshot are visible without horizontal scrolling.
- Every HTML ID is unique; `id="download"` occurs at most once.

## WEB-002 - Information and Visual Hierarchy

Suggested executor: Terra-class frontend implementation.

Writable files:

- `website/index.html`
- `website/styles.css`

Acceptance criteria:

- The page contains only these primary information groups: Hero, Release,
  Formula Editor, local OCR, Workspace, Local-first assurance and Beta limits.
- Windows x64 and ARM64 states remain available inside the Release group but are
  visually secondary to the verified macOS action.
- The layout uses a maximum content width of 1200 px, 16-18 px body text,
  `clamp(3rem, 7vw, 5rem)` for H1 and
  `clamp(6rem, 12vw, 10rem)` for major section spacing, unless a documented
  browser check proves a smaller value is needed to satisfy WEB-001.
- Use a neutral base with one functional accent. Preserve the accepted role-based
  Source Han Serif / SF Mono stack from Decision D011.
- Hero uses one main screenshot; each later feature group uses at most one
  relevant screenshot. Avoid decorative screenshot stacking and generic SaaS
  card grids.

## WEB-003 - Release Data Integrity

Suggested executor: release-data reviewer; do not depend on an unavailable model
name from the research report.

Writable files:

- `website/app.js` only if a binding defect is demonstrated
- `tests/test_release_site.py`
- generated `website/release.json` only through `tools/update_release_site.py`

Acceptance criteria:

- All existing `data-release-*`, document and download bindings continue to work.
- No version, tag, channel, asset URL or publication-state constant is duplicated
  in `index.html` or `app.js`.
- Download URLs resolve from generated Release metadata and point to the expected
  GitHub Release asset; unpublished downloads remain non-interactive.
- `python3 tools/update_release_site.py --check` and release consistency checks
  pass. Never hand-edit `website/release.json`.

## WEB-004 - QA and Deployment Handoff

Suggested executor: Terra-class UI QA with an independent release review.

Required artifacts:

- `docs/release-site-checklist.md`
- `release/release-site-changes.json`

Acceptance criteria:

- The checklist records WEB-001 through WEB-004 as pass/fail with evidence, not
  as self-asserted completion.
- The JSON lists modified, preserved and forbidden files/technologies and is
  parseable by Python's standard `json` module.
- Automated checks prove: zero duplicate IDs, correct dynamic download URL,
  alt text on content images, one H1, ordered heading hierarchy, skip link,
  `aria-live` for async release status and reduced-motion support.
- Browser evidence covers 1440 x 900 and 390 x 844. The mobile capture proves the
  WEB-001 first-viewport requirement and no horizontal overflow.
- Record Lighthouse Performance and Accessibility scores for both viewports.
  Numeric release thresholds are not invented by this task; any accepted gate
  must be added to this file before it is enforced.
- Run the commands below. Public GitHub Pages deployment remains blocked until
  the maintainer explicitly approves the guarded publish step.

```bash
python3 tools/update_release_site.py --check
python3 -m unittest tests.test_release_site
python3 -m compileall -q app tests packaging/install_build_dependencies.py
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
bash packaging/preflight.sh
```

## Completion and Handoff

WEB-RS-001 is complete only when all four subtasks pass, the required artifacts
exist, the full verification commands pass and a reviewer confirms that release
data behavior is unchanged. Commit each independently reviewable slice before
any Pages publication. Do not create or push a tag, Release, branch or deployment
without explicit maintainer authorization.
