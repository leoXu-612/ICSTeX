# WEB-RS-002 - Release Website Content and Information Architecture

Status: `COMPLETE - VERIFIED LOCALLY`

Source: `deep-research-report (3).md`, executed 2026-08-09.

## Scope

This slice implements the presentation layer only. GitHub Release metadata, asset
URLs, SHA-256 values and publication logic remain release-data responsibilities.
No React, runtime framework, Node build chain, remote font, analytics or workflow
was added.

## Delivered

- Homepage navigation now exposes 功能、使用指南、理念、下载和 GitHub.
- Homepage hero identifies ICSTeX, the current dynamically injected version,
  Formula Intelligence and the macOS Apple Silicon primary action.
- Release/download information remains data-driven and includes a final Beta CTA.
- Formula, local recognition and Block workspace sections link to relevant guides.
- `website/guide/index.html` provides a factual feature catalog, installation,
  workflow, formula, OCR, compile/PDF, workspace and FAQ guidance.
- `website/about/index.html` provides the short philosophy, three principles and
  the founder letter; the source text is preserved in `docs/product/`.
- `docs/website/IA.md` freezes page order and content boundaries.
- `docs/website/RELEASE_PRESENTATION_CONTRACTS.md` records protected DOM bindings.
- `tools/verify_release_consistency.py` now validates every HTML page's release
  bindings, IDs, headings, image dimensions and hard-coded release constants.

## Evidence

```text
python3 tools/update_release_site.py --check       PASS
python3 tools/verify_release_consistency.py        PASS
python3 -m unittest tests.test_release_site        12 passed
compileall                                         PASS
QT_QPA_PLATFORM=offscreen ...                      733 passed
bash packaging/preflight.sh                        PASS (733 passed)
```

Playwright browser evidence:

- Homepage: 390, 430, 1024, 1280 and 1440 px widths; no horizontal overflow.
- Guide/About: dynamic release version loads; no horizontal overflow.
- Platform tabs: hash deep-link, ArrowLeft/ArrowRight/Home, and download URLs work.
- First keyboard Tab focuses the skip link; no console warnings or errors observed.

## Deployment boundary

The static site can be deployed directly to the existing Vercel production project.
GitHub Actions workflows must not be triggered for this slice. GitHub Releases
remains the artifact source of truth.
