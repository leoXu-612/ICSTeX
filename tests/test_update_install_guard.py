from __future__ import annotations

import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.core.update_install_guard import InstallationLease, UpdateInProgress, enter_installed_application


@unittest.skipUnless(sys.platform == "darwin", "macOS kernel installation protocol")
class InstallationGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = TemporaryDirectory()
        root = Path(__file__).resolve().parents[1]
        cls.helper = Path(cls.tools.name) / "ICSTeXInstallGuard"
        cls.installer_binary = Path(cls.tools.name) / "Fixture"
        for source, output in ((root / "packaging/native_updates/install_guard.c", cls.helper),
                               (root / "tests/fixtures/update_installer.c", cls.installer_binary)):
            subprocess.run(["xcrun", "clang", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(output)],
                           check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.tools.cleanup()

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bundle = self.root / "Fixture.app"
        macos = self.bundle / "Contents/MacOS"
        macos.mkdir(parents=True)
        shutil.copy2(self.installer_binary, macos / "Fixture")
        self.installer_path = self.bundle / "Contents/Frameworks/Sparkle.framework/Versions/B/Autoupdate"
        self.installer_path.parent.mkdir(parents=True)
        shutil.copy2(self.installer_binary, self.installer_path)
        framework = self.bundle / "Contents/Frameworks/Sparkle.framework"
        version = framework / "Versions/B"
        (version / "Resources").mkdir()
        shutil.copy2(self.installer_binary, version / "Sparkle")
        (version / "Resources/Info.plist").write_bytes(plistlib.dumps({
            "CFBundleExecutable": "Sparkle", "CFBundleIdentifier": "com.icstex.fixture.sparkle",
            "CFBundlePackageType": "FMWK", "CFBundleVersion": "1"}))
        (framework / "Versions/Current").symlink_to("B")
        (framework / "Sparkle").symlink_to("Versions/Current/Sparkle")
        (framework / "Resources").symlink_to("Versions/Current/Resources")
        for target in (self.installer_path, framework):
            subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(target)],
                           check=True, capture_output=True)
        (self.bundle / "Contents/Info.plist").write_bytes(plistlib.dumps({
            "CFBundleExecutable": "Fixture", "CFBundleIdentifier": "com.icstex.fixture",
            "CFBundlePackageType": "APPL", "CFBundleVersion": "1"}))
        subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(self.bundle)],
                       check=True, capture_output=True)
        self.leases = []
        self.processes = []

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()  # Only this test's synthetic subprocesses.
            process.wait(timeout=10)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        for lease in self.leases:
            if lease.process is not None:
                if lease.process.poll() is None:
                    lease.process.terminate()
                lease.process.wait(timeout=10)
                for stream in (lease.process.stdin, lease.process.stdout):
                    if stream is not None:
                        stream.close()
            lease.close()
        self.temp.cleanup()

    def lease(self, bundle=None, boot="test-boot"):
        lease = InstallationLease(bundle or self.bundle, directory=self.root, helper=self.helper, boot_id=boot)
        self.leases.append(lease)
        return lease

    def installer(self):
        process = subprocess.Popen([str(self.installer_path)], stdin=subprocess.PIPE)
        self.processes.append(process)
        return process

    def test_normal_instances_can_share_but_upgrade_requires_exclusion(self):
        first, second = self.lease(), self.lease()
        first.enter()
        second.enter()
        with self.assertRaises(UpdateInProgress):
            first.begin()
        third = self.lease()
        third.enter()  # Failed upgrade did not strand an exclusive lock.
        second.close()
        third.close()
        first.begin()
        with self.assertRaises(UpdateInProgress):
            self.lease().enter()
        first.finish()
        self.lease().enter()

    def test_different_paths_still_serialize_sparkle_bundle_identifier(self):
        first, second = self.lease(), self.lease(self.root / "Other.app")
        first.enter()
        second.enter()
        first.begin()
        with self.assertRaises(UpdateInProgress):
            second.begin()

    def test_lock_files_survive_version_change_and_alias_paths(self):
        alias = self.root / "Alias.app"
        alias.symlink_to(self.bundle, target_is_directory=True)
        first, alias_lease = self.lease(), self.lease(alias)
        first.enter()
        first.begin()
        with self.assertRaises(UpdateInProgress):
            alias_lease.enter()

    def test_native_guard_survives_host_descriptors_closing(self):
        first = self.lease()
        first.enter()
        first.begin()
        first.extracting()
        installer = self.installer()
        self.assertTrue(first.ready())
        first.close()
        late = self.lease()
        with self.assertRaises(UpdateInProgress):
            late.enter()
        installer.stdin.close()
        installer.wait(timeout=5)
        self.assertEqual(first.process.wait(timeout=5), 0)
        late.enter()

    def test_finished_ui_cycle_does_not_unlock_live_installer(self):
        first = self.lease()
        first.enter()
        first.begin()
        first.extracting()
        installer = self.installer()
        self.assertTrue(first.ready())
        first.finish()
        with self.assertRaises(UpdateInProgress):
            self.lease().enter()
        installer.stdin.close()
        installer.wait(timeout=5)
        self.assertEqual(first.process.wait(timeout=5), 0)
        first.finish()
        self.lease().enter()

    def test_real_bundle_rename_does_not_change_tracked_process_identity(self):
        first = self.lease()
        first.enter()
        first.begin()
        first.extracting()
        installer = self.installer()
        self.assertTrue(first.ready())
        replacement = self.root / "Replacement.app"
        shutil.copytree(self.bundle, replacement, symlinks=True)
        self.bundle.rename(self.root / "Old.app")
        replacement.rename(self.bundle)
        first.close()
        with self.assertRaises(UpdateInProgress):
            self.lease().enter()
        installer.stdin.close()
        installer.wait(timeout=5)
        self.assertEqual(first.process.wait(timeout=5), 0)
        self.lease().enter()

    def test_cancel_before_installer_creation_releases_after_native_cycle(self):
        first = self.lease()
        first.enter()
        first.begin()
        first.extracting()
        first.finish()
        self.assertEqual(first.process.wait(timeout=5), 0)
        first.finish()
        self.lease().enter()

    def test_killed_coordinator_cannot_admit_late_instance(self):
        first = self.lease()
        first.enter()
        first.begin()
        first.extracting()
        installer = self.installer()
        self.assertTrue(first.ready())
        first.process.kill()
        first.process.wait(timeout=5)
        first.close()
        late = self.lease()
        with self.assertRaises(UpdateInProgress):
            late.enter()
        installer.stdin.close()
        installer.wait(timeout=5)
        late.enter()  # Known exact installer identity is gone; bundle verifies.

    def test_interrupted_replacement_with_bad_signature_stays_blocked(self):
        first = self.lease()
        first.enter()
        first.begin()
        first.extracting()
        installer = self.installer()
        self.assertTrue(first.ready())
        with (self.bundle / "Contents/MacOS/Fixture").open("ab") as stream:
            stream.write(b"tamper")
        installer.kill()
        installer.wait(timeout=5)
        self.assertEqual(first.process.wait(timeout=5), 76)
        first.close()
        with self.assertRaises(UpdateInProgress):
            self.lease().enter()

    def test_unknown_interruption_recovers_only_after_reboot_and_integrity_check(self):
        first = self.lease()
        first.enter()
        first.begin()
        first.extracting()
        first.process.kill()
        first.process.wait(timeout=5)
        first.close()
        with self.assertRaises(UpdateInProgress):
            self.lease().enter()
        self.lease(boot="next-boot").enter()

    def test_symlink_lock_refused_without_touching_target(self):
        first = self.lease()
        first.close()
        gate = next(self.root.glob(".icstex-*.gate"))
        gate.unlink()
        target = self.root / "preserved.txt"
        target.write_text("preserve", encoding="utf-8")
        gate.symlink_to(target)
        with self.assertRaises(OSError):
            self.lease()
        self.assertEqual(target.read_text(), "preserve")

    def test_checking_journal_can_recover_without_reboot(self):
        first = self.lease()
        first.enter()
        first.begin()
        first.close()
        self.lease().enter()

    def test_development_entry_does_not_create_locks(self):
        with patch("app.core.update_install_guard.sys.frozen", False, create=True), \
             patch("app.core.update_install_guard.InstallationLease") as constructor:
            enter_installed_application()
        constructor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
