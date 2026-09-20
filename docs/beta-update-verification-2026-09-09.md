# macOS arm64 Beta update verification — 2026-09-09

Result: signed native delivery works in an isolated test, but public activation
is not accepted. The remaining installation-exclusion gate is a release hold,
not a signing/authentication problem.

## Candidate and test setup

Current release candidate: `2.1.0-beta.2`, sequence `210002`, arm64,
`dist/ICSTeX-2.1.0-beta.2-macos-arm64-candidate-r2/`. Exact source/archive/feed
identities are in `BETA_ACTIVATION_HANDOFF.md`. The immutable archive was signed
with official Sparkle 2.9.6 tooling, then archive and feed signatures were
verified independently using the configured Ed25519 public key. No private key
was read/exported for independent verification.

Private QA builds used a lower sequence (`210001`), explicit temporary INI
preferences, and one fixed `http://127.0.0.1:18429/appcast.xml` exception in copied
QA source. The test server bound only to loopback and served only prepared feeds
and archives. Public application source/configuration remained HTTPS-only; r2
contains the fixed production HTTPS URL, not this exception. The target archive
served during successful replacement was byte-identical to r2. No student
project was used. First-pass failure tests predated the r2 progress-window fix;
the native signature/installer policy was unchanged.

## Native acceptance matrix

| Case | Observation | Boundary |
| --- | --- | --- |
| Opt-in | Automatic checking displayed off in fresh QA settings and r2 | No background auto-install |
| Retrieval failure | HTTP 503 produced Sparkle's retrieval-error alert; no archive request | Not a full offline/network-loss matrix |
| Invalid feed | Same-length XML tampering produced the explicit improperly-signed-feed alert | Native rejection before archive download |
| Invalid archive | A response byte was changed without altering declared length; Sparkle rejected the package | Original signed archive untouched |
| No update | QA client sequence 210002 against signed feed sequence 210002 reported up to date | Private numeric-sequence fixture |
| Cancel download | Slow loopback download cancelled; client returned to usable state | Fixed obscured native progress first |
| All-window Cancel | Synthetic named/unnamed windows stayed open after cancelling Save prompt | Real native install callback |
| Cancel Save As | Cancelling unnamed-document file picker retained all windows and stopped handoff | No student files |
| Save and install | Unnamed document saved; 210001 bootstrap replaced by exact signed r2 at 210002 | See identity evidence below |
| Pre-existing process | A second frozen same-path process blocked installation through the actual callback | Does not cover a late-starting process |
| Low disk | 240 MB APFS fixture with about 24 MiB free failed installation safely; old bundle unchanged | Manual cold restart succeeded; no automatic recovery claim |
| Read-only location | Native engine rejected updating a read-only mounted app before download | Not a test of every ACL/permission failure |
| New version cannot launch | Deliberate signed QA build exited 86; installed bundle matched that broken build and no app remained running | No automatic rollback occurred |
| External recovery | Preserved broken installation, restored complete trusted bootstrap, verified full checksum and code signature, then cold-launched visible UI | Manual complete-bundle recovery only |
| Late instance / concurrent replacement | Not accepted; current probe and upstream monitoring do not establish required exclusion | Release blocker |
| Forced installer interruption | Not exercised | Still required before activation |
| Public HTTPS delivery | No release asset or signed production feed was published | Not tested |

External-conflict, compile/export/OCR active-work, worker-thread shutdown and
window-state guards retain automated coverage. This report does not convert
that coverage into native installation fault-injection results. Windows/UAC
tests, Developer ID signing, notarization, and macOS 13 runtime testing were
outside this arm64/on-this-Mac acceptance.

## Source fix and artifact evidence

Native QA exposed a Qt settings window obscuring Sparkle progress. Manual checks
now hide that settings window; while a native session exists, the button becomes
“查看更新进度” and re-focuses it without resetting the scheduled attempt or install
state. Automatic checks still do not re-enter an active session. Added three
controller regressions and updated visual coverage. Required full preflight
passed 965 tests in 215.812 seconds before r2 packaging. Existing welcome-page
scale/deleted-QLabel warnings remain, without failing the suite.
The final handoff preflight also passed 965 tests in 246.461 seconds; candidate
source and signature checks remained unchanged. Published Beta 1 website
consistency passes; the stricter source-version release gate correctly fails
while that published manifest still differs from the unreleased Beta 2 source.

During real replacement, the native installer automatically relaunched the
updated application before any UI automation selected it. Full recursive
checksum/symlink comparison against the candidate bundle reported no differences,
and deep strict code-signature verification passed. A separate quit/fresh-launch
cycle displayed the UI. The updated candidate uses production preferences;
recent-project labels were visible, but no listed student project was opened.

Synthetic named document SHA-256 remained
`7df99ea97d0ee296f8858fc8462b8a15df58b8d446f65df131f69a4b51e6dbdc`.
Saved unnamed content and its expected fixture both hashed to
`99790baa4db23a7c2b0e9ec0f8585ee02a915955f61f9a7b5eb5d8523be3ffc7`.

## Installation-exclusion finding

The adapter delegates `updaterShouldRelaunchApplication` to the GUI save/probe
callback and delegates termination back to Qt. It does not retain a shared
installation exclusion across host exit. Upstream Sparkle 2.9.6
[selects one application to monitor](https://github.com/sparkle-project/Sparkle/blob/2.9.6/Sparkle/InstallerProgress/InstallerProgressAppController.m#L319-L325)
and identifies limitations for another instance starting later and for other
logged-in users. The inspected `os_unfair_lock` in the installer protects its
XPC connection bookkeeping, not proof of the required app/install exclusion.

This is source evidence of an unmet proof obligation, not a reproduced corrupt
update. Repeating a process scan cannot close the race after the host exits.
Do not weaken `packaging/UPDATES.md` to publish this candidate. A bounded decision
is required before changing startup policy, introducing a helper, or modifying
the pinned native engine.

## Retained evidence and cleanup

Local build/preflight/server logs, signature verification output, synthetic
documents, and private QA scripts/configs are retained under the r2 candidate's
`verification/` directory. `source-inputs.zip` preserves the frozen app/packaging
inputs (SHA-256 `8b2377feb7682b6bd74db669c46b049e9cfd37e0db011a88c2e6d55755a0df04`;
archive integrity check passed). Raw logs are local-only because they contain machine
paths; no screenshot or log was uploaded. Temporary broken packages are not
public release candidates. Test applications/server were stopped and the APFS
fixture was detached. The original installed application and existing public
release/production deployment were not changed.
