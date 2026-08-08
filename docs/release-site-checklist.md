# WEB-RS-001 Release Site Verification

Date: 2026-08-08 (Asia/Taipei)

Scope: local static-site refactor only. No branch/tag push, GitHub Release,
GitHub Pages publication, or Vercel deployment was performed.

## Gate Results

| Gate | Result | Evidence |
| --- | --- | --- |
| WEB-001 Mobile-first Hero | PASS | Codex in-app browser at 390 x 844: `scrollWidth == innerWidth == 390`; dynamic version bottom 206 px, primary CTA bottom 386 px, and Hero screenshot starts at 466 px. The CTA says Apple Silicon and remains `aria-disabled="true"` while the Release is unpublished. |
| WEB-002 Information and visual hierarchy | PASS | `main` contains exactly seven primary sections; one H1; Windows status is a secondary native `details`; maximum content width, H1 scale, section spacing, neutral palette, functional blue accent, and role-based type stacks are asserted in the focused site tests. |
| WEB-003 Release data integrity | PASS | `python3 tools/update_release_site.py --check` passed. Nine focused tests confirm generated metadata, exact GitHub asset URL, dynamic name/version bindings, unpublished download behavior, and absence of hard-coded release constants. |
| WEB-004 QA and handoff | PASS | Browser checks passed at 390 x 844 and 1440 x 900 with no horizontal overflow or console errors. Desktop Lighthouse: Performance 100, Accessibility 100. Mobile Lighthouse: Performance 97, Accessibility 100. Best Practices and SEO were 100 at both viewports. |

## Automated Accessibility and Structure Evidence

- All HTML IDs are unique; `id="download"` appears once.
- One H1 is present and heading levels do not skip.
- Content images have non-empty alt text and explicit width/height.
- A skip link and an `aria-live="polite"` Release-status region are present.
- Reduced-motion rules are present; focus indicators and 48 px interactive targets
  remain visible.
- No remote font, runtime CDN, analytics, React, Next.js, Tailwind, or Node build
  chain was introduced.

All required commands passed: generated metadata check, 9 focused Release-site
tests, `compileall`, 719-test offscreen suite, and `packaging/preflight.sh`.

## Lighthouse Detail

| Viewport | Performance | Accessibility | Best Practices | SEO | FCP | LCP | TBT | CLS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 390 x 844 | 97 | 100 | 100 | 100 | 1.4 s | 2.6 s | 0 ms | 0.008 |
| 1440 x 900 | 100 | 100 | 100 | 100 | 0.3 s | 0.5 s | 0 ms | 0.002 |

Lighthouse scores are recorded evidence, not a newly invented release threshold.

## Review Boundary

The browser review confirmed the generated Release name `Formula Intelligence`,
version `2.1.0-beta.1`, disabled unpublished CTA, seven-section hierarchy, and
zero console errors. GitHub Releases remains the artifact authority; publication
still requires explicit maintainer approval.
