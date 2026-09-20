# macOS Beta 3 update delivery

Verified on 2026-09-15. This supersedes the historical Beta 2 activation hold;
the old Beta 2 candidate and published manual release are not repurposed.

## Published identity

- Application: `2.1.0-beta.3`, release sequence `210003`, macOS arm64.
- Immutable source tag: `v2.1.0-beta.3`, commit
  `81b1672d162de2128374e9cdb9a7c20b00a95110`.
- GitHub prerelease: <https://github.com/leoXu-612/ICSTeX/releases/tag/v2.1.0-beta.3>,
  release ID `388996893`; eight uploaded assets, including the two installers.
- Website: <https://ics-tex.vercel.app>.
- Signed feed: <https://website-phi-beryl-92.vercel.app/updates/macos/arm64/beta/appcast.xml>.
- Production deployment: `dpl_7P7UsiCcEtNRYbuanZkyy8WJDpba`, READY, aliases applied.

DMG: 65,266,837 bytes, SHA-256
`15f9736cd7cc94902f1192b0beabfccd8e1981a9f16e564d221fb0cbafb5247a`.

ZIP: 56,747,305 bytes, SHA-256
`5cf1413c257d1a6bb9c81dbe23e99a6a44821d5c8d6b5e7bbe926e1f8a65d341`.

Application executable SHA-256:
`fa4a83f83829a367c5760ccfe1a3f66776752212d3444fbd59c9b342f8f92ad4`.
Complete build scope is in `release/BUILD_RECEIPT.json`.

## Accepted checks

- Required compileall and final packaging preflight passed on unchanged source;
  source/test receipt is retained locally. Existing non-fatal Qt/temporary-fixture
  diagnostics were not relabelled as zero warnings.
- Bundled modules, entry, startup hook, resources, architecture and deep/strict
  code-signature integrity match the frozen source/candidate. The previously
  excluded independent MCP/OCR modules remain explicitly listed.
- Native Sparkle rejected modified feed and archive bytes. Real installer and
  coordinator interruption retained exclusion after host exit; a known-ended
  installer and intact old bundle recovered and cold-launched. See
  `UPDATE_INSTALLATION_GUARD.md` for exact scope and limitations.
- Both public installer URLs were downloaded anonymously with HTTP 200; bytes
  matched local files, release metadata and GitHub's server-side digests.
- With the local fixture server stopped, an isolated lower-sequence bootstrap
  opted into automatic checks and discovered this release via the production
  HTTPS feed. After explicit download and installation confirmation, Sparkle
  replaced it with sequence `210003` and relaunched it. The new process existed
  before UI inspection, its executable digest matched, and recursive file/symlink
  comparison matched the signed candidate exactly. Its native writing window and
  ready LaTeX environment appeared normally.
- The real website displayed Beta 3 with matching DMG/ZIP URLs and SHA-256 values;
  no browser console error was observed. The Windows-new-version link remained
  unavailable. The older “only literature lookup uses the network” sentence was
  corrected to include explicitly enabled updates and optional-component installs.

No student documents were opened or edited for these acceptance checks. No
private signing key was exported. Application replacement remains user-confirmed;
the default automatic-check preference remains off.

## Remaining distribution limits

This is an ad-hoc-signed, non-notarized Apple Silicon Beta. No new Windows or
Intel Mac package, Developer ID release, automatic rollback or universal
installation-permission guarantee is claimed. Old manual builds need one manual
bootstrap installation before in-app updates can be used. These are documented
product limits, not an unimplemented online-update path.
