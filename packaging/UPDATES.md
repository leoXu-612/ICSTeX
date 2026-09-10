# Native application update release handoff

This is a maintainer workflow, not an enabled service. Ordinary source runs and
builds are offline. It does not authorize publishing, credentials, key creation,
Developer ID signing, notarization, or replacing an installed application.

The client uses Sparkle 2.9.6 on macOS and WinSparkle 0.9.4 on Windows. Official
SDK URLs and exact release SHA-256 digests are pinned in `native_updates.py`.
The repository does not vendor the SDKs. Maintainer public configuration for
the macOS arm64 Beta candidate is in `release/updates/macos-arm64-beta.json`.
Its presence does not enable ordinary builds or establish activation acceptance.

## 1. Release prerequisites

Before enabling a runtime, establish a separately authorized release with:

- A new public version from `app/__init__.py`, a monotonically increasing positive
  release sequence below 2^31, and an immutable source/build receipt. Do not reuse
  the current Beta 1 identity for changed public binaries.
- One maintained HTTPS appcast per platform, process architecture and channel.
  A beta source version must use beta. Channels are fixed in the package; no
  in-app channel switching or automatic downgrade is implemented.
- Maintainer-controlled Ed25519 signing keys outside the repository and website.
  Only the 32-byte base64 public key enters the application. Do not generate or
  overwrite production keys as an incidental build step.
- Native installation acceptance on every advertised target. A library for a
  target is not proof that the application or installer supports that target.

See [Sparkle publishing](https://sparkle-project.org/documentation/publishing/)
and [WinSparkle publishing](https://winsparkle.org/guides/publishing-updates/).
Use the pinned SDK tools and their `--help` for signing commands; do not substitute
another SDK version without revalidating the adapter and signature policy.

## 2. Prepare a target-specific runtime

Provide a private working file containing **public configuration only**, with
exactly these fields. Angle-bracket values below are placeholders, not a usable
configuration; never ship the test fixture's synthetic public key.

```json
{
  "schema": 1,
  "version": "<exact app.__version__>",
  "release_sequence": 0,
  "channel": "beta",
  "platform": "darwin",
  "architecture": "arm64",
  "feed_url": "https://<verified-public-host>/<target>/<channel>/appcast.xml",
  "public_key": "<maintainer Ed25519 public key>"
}
```

Replace sequence `0` with the approved positive release sequence. Valid platform
values are `darwin` and `win32`; architecture is `arm64` or `x86_64`. The feed
must use public HTTPS on port 443 without embedded credentials, query or fragment.

Download the corresponding official SDK archive identified in `SDK_RELEASES`,
then run from the repository root, supplying actual absolute paths:

```bash
python3 packaging/native_updates.py \
  --archive /absolute/path/to/pinned-sdk-archive \
  --config /absolute/path/to/public-update-config.json \
  --output /absolute/path/to/new-runtime-directory
```

The script verifies the archive digest before extraction, compiles the macOS
bridge using Xcode Command Line Tools, and stages the matching DLL on Windows.
It preserves an existing output directory and records the SDK source/digest and
licenses. macOS bridge preparation must run on macOS. Nothing is published or
installed, and no signing identity is accessed.

## 3. Opt-in application build

Run the repository's required `bash packaging/preflight.sh` before a release
build. Set `ICSTEX_UPDATE_RUNTIME` only for the target build process, to the
prepared runtime directory, and use the existing platform PyInstaller spec.
The build Python platform/architecture must match the configuration. Windows
builds must use a Windows-local checkout, never macOS shared storage.

When the variable is absent, both specs retain their ordinary no-updater build.
Do not copy `app-update.json` into the source `app/assets` directory. Runtime
environment variables and project files cannot enable or redirect updates.

The macOS spec embeds `Sparkle.framework` and `ICSTeXUpdateBridge.dylib`, sets
`CFBundleVersion` to the numeric release sequence, and restores **ad-hoc local
signing only** after embedding. This output is not distribution-signed. Sign the
bridge, nested frameworks/XPC/helpers and final application in the order required
by [Sparkle's signing guide](https://sparkle-project.org/documentation/sandboxing/),
with correct hardened-runtime settings; then notarize and staple under a separate
authorized release. Never claim that `codesign --sign -` is Developer ID signing.

The Windows spec embeds the matching DLL. The client sets WinSparkle's numeric
build version from the release sequence. Existing `installer_windows.iss` still needs a
release-specific review: its x64 assumptions and fixed version cannot represent
an ARM64 installer or a new public release without changes. Verify stable AppId,
install location/scope, EXE version metadata, old-file cleanup, Authenticode and
file-occupancy handling before offering an installer. ZIP/MSI update payloads are
not supported by this adapter; it only starts a verified EXE with no feed-supplied
arguments. There is no silent-install flag or remote command fallback.

## 4. Publish assets, then native feeds

Use versioned GitHub Release full packages and a static HTTPS appcast host. Keep
the appcast entry, binary and website display derived from the same approved
release record; `website/release.json` is not an update feed. Upload and verify
assets anonymously before updating the matching platform/channel feed. Do not
overwrite a versioned asset or advertise a target whose acceptance failed.

For macOS, use Sparkle's signed archive and signed-appcast tooling. The embedded
policy requires a signed feed and verification before archive extraction, and
disables the signed-feed failure-expiration fallback. For Windows, sign every EXE
with WinSparkle's Ed25519 tooling and publish the signature in the appcast; HTTPS
protects metadata transport, but this adapter does not claim separately signed
Windows feed metadata. Keep notes plain and self-contained; do not add remote
release-note pages or `installerArguments`.

Use the release sequence as `sparkle:version` and the public display version as
`sparkle:shortVersionString`. ICSTeX separates channels by feed URL; omit
`sparkle:channel` tags in these feeds, including the beta feed, because the bridge
uses Sparkle's default channel selection within its fixed URL. Add explicit
`windows-x64` or `windows-arm64` enclosure identity for the corresponding Windows
target. Do not publish delta entries until separately accepted.

Verify numeric version ordering, minimum OS compatibility and architecture on
the actual installed client. Keep the old feed available during key/domain
migration; changing an unsigned remote setting must not replace the embedded
public key. If old trust cannot authenticate a bridge release, require manual
installation. All publishing is maintainer-run; do not trigger GitHub Actions.

## 5. Activation gate

Before public activation, test N to N+1 with real signed application packages on
each platform, using isolated documents and non-production test credentials:

- Check opt-in, no-update, offline, bad feed/package signatures and cancellation.
- Verify all-window Save/Cancel, unnamed files, external conflicts, active work,
  other application/MCP processes, and an instance starting after the GUI probe.
- Exercise disk/permission failures, UAC denial, occupied files, interruption and
  a new version that cannot launch. The native installer must prevent concurrent
  replacement; the GUI process scan is not an installation lock.
- Prove the final installed identity, cold launch and unchanged document content.
  Keep a trusted old installer and an external recovery procedure. Automatic
  rollback, cross-version unsaved-draft recovery and launch receipts are not
  implemented by the current client.

The existing user base needs one manual bootstrap installation. Unit tests,
SDK staging, a loaded bridge and a visible settings dialog do not establish a
working or recoverable public auto-update path.

## Candidate build versus published website

`release/release-manifest.json` and `website/release.json` continue to identify
the existing published download-page release until its replacement is accepted.
They do not acquire a new version merely because `app/__init__.py` advances.
`tools/release_prepare.py` and `verify_release_consistency.py --require-tag-at-head`
retain the source-version gate for preparing that release. The separate native
channel configuration binds the candidate's exact version and numeric sequence.

For the dedicated Beta key, use Sparkle's `--account com.icstex.app.beta` option.
Only the public key is checked in. The private key stays in the maintainer's
login Keychain; macOS access prompts and backup decisions remain human steps.
Do not deploy an unsigned candidate appcast or replace Beta 1 release assets.
Signed candidates whose activation gates remain open are also local-only:
keep them in ignored `release/updates/candidates/`, outside `website/`. A source
commit or push does not authorize copying them into the deployment tree.
