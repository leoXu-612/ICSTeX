# macOS arm64 Beta activation handoff

Updated: 2026-09-10. Status: source synchronized; public activation on hold.

Keychain authorization is complete. No additional signing action is currently
needed from the maintainer. The dedicated `com.icstex.app.beta` key remains in
the local Keychain; no private key was exported. Do not repeat the earlier r1
signing command: r2 is the current candidate.

## Publication blocker

The unchanged gate in `packaging/UPDATES.md` requires native installation
exclusion, including another application/MCP instance starting after the GUI
process probe. ICSTeX currently probes before handoff but holds no installation
lock after the host exits. Sparkle 2.9.6's
[termination-monitoring implementation](https://github.com/sparkle-project/Sparkle/blob/2.9.6/Sparkle/InstallerProgress/InstallerProgressAppController.m#L319-L325)
selects the first running application and explicitly notes the late-instance
and other-login-session limitations. This does not prove a corrupt installation
occurred; it prevents claiming that the required exclusion is established.

A bounded implementation decision is needed for installation-lifetime exclusion
and startup coordination. Do not silently add a custom installer/helper, patch
the pinned SDK, change supported multi-instance behavior, or weaken the gate.
The Vercel/GitHub architecture and Ed25519 trust model remain unchanged.

## Current signed candidate

- Directory: `dist/ICSTeX-2.1.0-beta.2-macos-arm64-candidate-r2/`.
- Application: `ICSTeX.app`; archive: `ICSTeX-2.1.0-beta.2-macos-arm64.zip`.
- Archive length: 56,211,122 bytes.
- Archive SHA-256: `342c0300a6d7dc82d087aaee0703576996666678c01b6b01f163c16574b1061f`.
- Executable SHA-256: `86dac5d20b468325dc147e21795324040241310898e353218b4279c586b4f9c3`.
- App input tree: 211 files; SHA-256 `d48056f79629e13a861d9082751075134f63c854032408c19bb0e695566d5474`
  using sorted relative path + NUL + contents + NUL, excluding `__pycache__`.
- Public version/sequence: `2.1.0-beta.2` / `210002`; bundle ID `com.icstex.app`.
- Target: arm64, declared minimum macOS 13.0; only this Mac was runtime-tested.
- Deep strict ad-hoc signing passed; no Developer ID signature or notarization.
- Public configuration: `release/updates/macos-arm64-beta.json`.
- Signed local-only feed: `release/updates/candidates/macos-arm64-beta-r2.appcast.xml`;
  SHA-256 `be57a732b6532e3247916530bdc688b7e05b1cd4ec0457b216a5020250140c03`.

The feed was moved byte-for-byte out of the website deployment tree on
2026-09-10 and is ignored by Git. Its eventual deployment path remains
`website/updates/macos/arm64/beta/appcast.xml`, only after activation acceptance.

Both the archive and the exact feed bytes were independently verified against
the embedded Ed25519 public key. The feed remains local and references a GitHub
asset that has not been published. Do not deploy it yet. The older r1 candidate
is preserved, superseded, and not a release asset.

## Verified scope and recovery limits

The detailed matrix is in
[`beta-update-verification-2026-09-09.md`](beta-update-verification-2026-09-09.md).
Native QA used isolated application copies and synthetic documents. An older
bootstrap at sequence 210001 installed the exact signed r2 archive at 210002,
relaunched automatically, and passed cold launch and a full bundle checksum
comparison. Feed/package tampering, cancellation, no-update, all-window save
guards, a pre-existing same-path process, low disk and read-only location were
also exercised. A deliberately non-launching signed QA build demonstrated no
automatic rollback; restoring a preserved complete old bundle passed checksum,
code-signature and cold-launch checks.

Late-starting-instance races, forced installer interruption, and public HTTPS
feed/asset delivery are not accepted. UAC/Windows scenarios are out of scope.
External-conflict and active-work guards have automated coverage, not a new
native fault-injection result in this round. No student document was opened or
edited. The installed `/Applications/ICSTeX.app` was not replaced.

## External state and next step

The user approved production publication only after acceptance. The existing
Vercel connector is usable; its expired local CLI token is not a blocker.
Preview `dpl_7KCFhWRVwYtSdbS2WdUyavEFqobJ` is READY in the original project at
[the preview URL](https://website-9jgkbdafm-leoxuminghua-7962s-projects.vercel.app).
It contains the existing website and cache headers, with no appcast. The
production deployment and GitHub `v2.1.0-beta.1` release remain unchanged.

After an explicitly bounded exclusion/startup decision, implement and test that
change, rebuild and re-sign if application bytes change, and repeat the relevant
native gates. Only then publish immutable GitHub prerelease assets, verify their
public bytes, deploy the signed appcast, and verify the actual client over HTTPS.
Keep Windows activation, GitHub Actions, Developer ID signing and notarization
outside this task. Source and handoff changes were synchronized to
`origin/release/2.1` at `fef3731` on 2026-09-10 under separate user authorization;
the signed appcast and application archives were excluded. This source push
does not authorize public update activation or new release assets.
