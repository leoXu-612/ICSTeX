# macOS installation guard

The configured macOS build uses Sparkle 2.9.6 for download, signature validation
and replacement. ICSTeX's small native helper only retains installation leases
and observes the installer lifetime. It is not a daemon or a new installer.

## Protocol

1. The PyInstaller runtime hook acquires a shared lease before GUI or other
   application entry imports. The lock name is derived from the canonical bundle
   path and stored in `/Users/Shared`, not a per-user HOME directory.
2. A gate serializes entry and conversion to an exclusive installation lease.
   Other existing instances cause the update check to stop. A bundle-ID gate also
   prevents two installation copies from competing for Sparkle's launchd job.
3. Before extraction, the client journals the transaction and starts the native
   helper with the same open-file descriptions. Closing the GUI's descriptors
   cannot release the helper's locks.
4. The helper binds to this bundle's exact
   `Contents/Frameworks/Sparkle.framework/Versions/B/Autoupdate` executable and
   records its PID plus kernel start time. `kqueue`/`NOTE_EXIT`, not a timeout or
   a process-name poll, determines when the observed installer has exited.
5. Only after bundle signature-integrity verification does the helper clear the
   journal and release entry. A completed Sparkle UI cycle does not override a
   still-running installer, including an install-on-quit transaction.
6. If the helper is killed, the journal still blocks entry. An exact installer
   identity known to have ended can be recovered after integrity verification.
   An unknown handoff requires a Mac restart before integrity-based recovery.
   A damaged bundle needs a trusted complete installer; no automatic rollback is
   claimed.

The public signing key and HTTPS feed are fixed in the built application. The
helper neither contacts the network nor sends termination signals. Local test
programs deliberately interrupted by the test harness are not product behavior.
This is a cooperative file-safety protocol, not a defense against malicious local
users with filesystem write access. Old manual builds do not participate; the
first updater-enabled application must be installed manually with old instances
closed.

## Verification and scope

`tests/test_update_install_guard.py` exercises real kernel exclusion, late entry,
host exit, helper death, installer death, bundle rename, signature failure and
recovery. `tests/test_update_backends.py` checks the binding before native checks
and before the save/quit callback. The fixture framework is test-only.

The Beta 3 native acceptance used isolated application copies. The user confirmed
download and installation; the restarted binary matched the signed target, and
recursive content/symlink comparison matched the candidate. Native Sparkle
rejected a modified feed and archive. A stopped real Autoupdate process retained
exclusion after the host exited; killing the coordinator still blocked entry via
the journal. After the exact installer was killed, the intact old bundle recovered
and cold-launched. These tests did not edit student documents.

macOS arm64/user-owned writable application copies are the tested topology.
Lock paths are shared across login sessions, but switching live GUI login sessions
and all administrative installation layouts were not separately exercised.
Windows, Intel Mac, Developer ID signing, notarization and automatic rollback are
not covered by this release.

Release assets must be published and anonymously verified before deploying the
signed appcast. The public HTTPS client flow is a separate final delivery check;
a local signature check alone is not evidence that the public endpoint works.
