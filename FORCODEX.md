# FORCODEX.md

Updated: 2026-09-15. This worktree freezes the macOS Beta 2 manual-download release.

## Scope

The user requested synchronizing the website's downloadable installation package.
Publish the already-verified macOS arm64 GUI application as version 2.1.0-beta.2,
with matching source tag, immutable DMG/ZIP, checksums and release documents.
The exact application source and executable identities are in release/BUILD_RECEIPT.json.

This is not the old signed r2 auto-update candidate. Do not publish an appcast,
embed a public update runtime, add an installation helper, modify Sparkle,
or claim that automatic upgrading is enabled. Windows stays on its historical
release; do not rename an ARM64 or old package to imply new platform support.

## Publication order and safety

Verify archive contents and signatures, freeze the source tag, upload a draft
GitHub prerelease, verify its assets, publish it, then update the existing Vercel
website. Preserve all Beta 1 assets and the installed local app.

Push only the new release tag, not a development branch: the existing workflows
are branch-push/PR workflows, and this release must not start GitHub Actions.
Never force-update a tag or overwrite a versioned asset. Do not upload local
diagnostic logs, screenshots, credentials, signing keys or student documents.
Use the established release manifest and website projection; do not invent a
second download protocol. Keep source-code snapshots distinct from installed
GUI support and list unbundled modules truthfully.

## Handoff

The release worktree is isolated from the user's dirty development checkout.
Do not reset, stash, clean or switch that checkout. Copy back only the verified
public release metadata and website changes needed for continued maintenance.
