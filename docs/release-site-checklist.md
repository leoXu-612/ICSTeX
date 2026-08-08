# WEB-RS-001 Release Site Verification

Date: 2026-08-08 (Asia/Taipei)

Scope: local static-site refactor only. No branch/tag push, GitHub Release,
GitHub Pages publication, or Vercel deployment was performed.

## Gate Results

| Gate | Result | Evidence |
| --- | --- | --- |
| WEB-001 Mobile-first Hero | PASS | Codex in-app browser at 390 x 844: `scrollWidth == innerWidth == 390`; dynamic version bottom 206 px, primary CTA bottom 386 px, and Hero screenshot starts at 466 px. The CTA says Apple Silicon and remains `aria-disabled="true"` while the Release is unpublished. |
| WEB-002 Information and visual hierarchy | PASS | `main` contains exactly seven primary sections; one H1; macOS is the default platform and Windows remains secondary until selected; maximum content width, H1 scale, section spacing, neutral palette, functional blue accent, and role-based type stacks are asserted in the focused site tests. |
| WEB-003 Release data integrity | PASS | `python3 tools/update_release_site.py --check` passed. Ten focused tests confirm generated metadata, exact GitHub asset URL, dynamic name/version/SHA bindings, private/unpublished download behavior, and absence of hard-coded release constants. |
| WEB-004 QA and handoff | PASS | Browser checks passed at 390 x 844 and 1440 x 900 with no horizontal overflow or console errors. Desktop Lighthouse: Performance 100, Accessibility 100. Mobile Lighthouse: Performance 98, Accessibility 100. Best Practices and SEO were 100 at both viewports. |

## Automated Accessibility and Structure Evidence

- All HTML IDs are unique; `id="download"` appears once.
- One H1 is present and heading levels do not skip.
- Content images have non-empty alt text and explicit width/height.
- A skip link and an `aria-live="polite"` Release-status region are present.
- Reduced-motion rules are present; focus indicators and 48 px interactive targets
  remain visible.
- No remote font, runtime CDN, analytics, React, Next.js, Tailwind, or Node build
  chain was introduced.

All required commands passed: generated metadata check, 10 focused Release-site
tests, `compileall`, 720-test offscreen suite, and `packaging/preflight.sh`.

## Platform Installation and 404 Gate

- macOS and Windows are implemented as keyboard-operable tabs with Left/Right,
  Home and End support; `#panel-macos` and `#panel-windows` restore the selected
  platform.
- macOS exposes DMG and ZIP choices; Windows distinguishes unavailable x64 from
  the ARM64 developer Beta. Each available local artifact displays its generated
  SHA-256 and platform-specific installation steps.
- GitHub CLI verified that `leoXu-612/ICSTeX` is Private. The remote has neither
  `release/2.1` nor `v2.1.0-beta.1`, and the Release-by-tag API returns 404.
- `github_repository_public` and `github_release_published` now jointly gate
  downloads. At the current state, the browser exposes zero outbound GitHub or
  download URLs, preventing users from being sent to a known 404.
- The Codex GitHub Connector still returns 404 for this private repository while
  the locally authenticated GitHub CLI can read it. This is a connector-access
  limitation, separate from the absent Tag and Release.

## Lighthouse Detail

| Viewport | Performance | Accessibility | Best Practices | SEO | FCP | LCP | TBT | CLS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 390 x 844 | 98 | 100 | 100 | 100 | 1.4 s | 2.4 s | 0 ms | 0.008 |
| 1440 x 900 | 100 | 100 | 100 | 100 | 0.3 s | 0.5 s | 0 ms | 0.002 |

Lighthouse scores are recorded evidence, not a newly invented release threshold.

## Review Boundary

The browser review confirmed the generated Release name `Formula Intelligence`,
version `2.1.0-beta.1`, disabled unpublished CTA, seven-section hierarchy, and
zero console errors. GitHub Releases remains the artifact authority; publication
still requires explicit maintainer approval.
