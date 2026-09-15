# ICSTeX Project State

Updated: 2026-09-15. This is the current published macOS release snapshot.
Historical checkpoints remain in Git history and PROJECT_LOG.md; the delivery
receipt is in `docs/BETA3_DELIVERY.md`.

## Product and Source State

ICSTeX remains local research-writing infrastructure for ICC students. The current
macOS arm64 release is `2.1.0-beta.3`, sequence `210003`, from immutable source tag
`v2.1.0-beta.3` / `81b1672d162de2128374e9cdb9a7c20b00a95110`.
The application Python-tree digest is
`500675e9aa6246deef355bc68a80080d740ad121f6672916ddb4c34595e37a9d`;
app/tests digest is `dd4f11148084a95d87b55c16b8d62b10d6e40f2bb26670cbb46040ba02aa34a8`.
The final unchanged-source preflight passed 1758 tests in 302.583 seconds.
Non-fatal Qt/temporary-fixture diagnostics were retained, not declared fixed.

This release retains the prior writing, quick-preview, PDF-lifetime, formula,
citation and layout work. The Beta 3 product delta is the configured updater and
installation-lifetime protocol; it does not change the compilation engine or
claim a new performance improvement.

## Online Update State

The installation guard is implemented and native interruption/late-entry checks
have passed. With the local fixture server stopped, an isolated lower-sequence
client enabled automatic checks, found Beta 3 through the production HTTPS feed,
downloaded after confirmation, installed after confirmation and relaunched.
The actual new process existed before UI inspection. Its executable digest and
recursive bundle contents/symlinks matched the signed release candidate.

GitHub prerelease `388996893` contains eight assets. Both installers were
downloaded anonymously with HTTP 200 and matching SHA-256 values.
The website and signed feed are live on the original Vercel project; production
`dpl_7P7UsiCcEtNRYbuanZkyy8WJDpba` is READY with its aliases applied.
The public entry is <https://ics-tex.vercel.app>.
Exact archive identities, links and verification scope are in BETA3_DELIVERY.

The user must opt into automatic checks once. Download and installation remain
separate confirmations. Unconfigured source/manual builds remain offline.
Old Beta 1/Beta 2 manual packages need one manual bootstrap installation.
The old r2 update candidate is historical and must not be republished or relabelled.

## Architecture and Non-Regression Boundaries

- Keep pure rules in `app/core`, PySide6 orchestration in `app/gui`; core must not import GUI.
- Keep MainWindow as a compatibility facade and preserve root/build/revision guards.
- Saving and compilation preserve source cursor/scroll. Same-document PDF reload preserves view state.
- Stale output must be explicit. Background work must not replace another root's PDF or indicators.
- Preserve local files, strict decoding, atomic replacement, project paths and user-owned content.
- Do not silently upload student documents, logs or screenshots.
- Use Sparkle for download/validation/replacement. The installation helper only owns leases,
  process-exit observation and fail-closed recovery; see UPDATE_INSTALLATION_GUARD.
- Keep new release identities immutable; updates do not authorize future releases,
  credential changes, private-key export, CI execution or unrelated project edits.

## Current Limits and Next Work

There is no active coding assignment after delivery; wait for concrete user feedback.
No Windows or Intel Mac release, Developer ID signature, Apple notarization,
automatic rollback, full administrative-installation coverage or complete
VoiceOver/IME acceptance is claimed. Existing historical native-crash leads are
not declared comprehensively resolved. Independent MCP/OCR worker modules not
included in the GUI package remain listed in release/BUILD_RECEIPT.json.
Important projects and trusted old applications require independent backups.
