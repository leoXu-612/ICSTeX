from __future__ import annotations

import base64
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app import __version__
from app.core.app_updates import (UpdateConfiguration, UpdateConfigurationError,
                                  automatic_check_due, installed_update_availability,
                                  other_installed_instances,
                                  process_architecture, read_update_configuration,
                                  validate_feed_url)


def update_config(**overrides) -> UpdateConfiguration:
    value = {
        "schema": 1, "version": __version__, "release_sequence": 101,
        "channel": "beta", "platform": "darwin", "architecture": "arm64",
        "feed_url": "https://updates.example.org/macos-arm64/beta/appcast.xml",
        "public_key": base64.b64encode(bytes(range(32))).decode("ascii"),
    }
    value.update(overrides)
    return UpdateConfiguration.from_dict(value)


class UpdateConfigurationTests(unittest.TestCase):
    def test_configuration_round_trip(self):
        config = update_config()
        self.assertEqual(UpdateConfiguration.from_dict(config.as_dict()), config)

    def test_release_identity_must_match_source(self):
        for changes in ({"version": "1.0"}, {"release_sequence": 0},
                        {"release_sequence": True}, {"release_sequence": 2**31},
                        {"channel": "nightly"}, {"platform": "linux"},
                        {"architecture": "universal"}, {"public_key": "not-a-key"},
                        {"public_key": base64.b64encode(b"short").decode("ascii")}):
            with self.subTest(changes=changes), self.assertRaises(UpdateConfigurationError):
                update_config(**changes)

    def test_beta_not_published_to_stable(self):
        with self.assertRaises(UpdateConfigurationError):
            update_config(channel="stable")

    def test_unknown_fields_are_rejected(self):
        with self.assertRaises(UpdateConfigurationError):
            update_config(installer_command="arbitrary command")

    def test_invalid_schema_and_field_types_are_rejected(self):
        for changes in ({"schema": True}, {"schema": "1"}, {"platform": []},
                        {"channel": {}}, {"architecture": ["arm64"]}, {"public_key": None}):
            with self.subTest(changes=changes), self.assertRaises(UpdateConfigurationError):
                update_config(**changes)

    def test_https_public_feed_only(self):
        for value in ("http://example.org/a.xml", "file:///tmp/appcast.xml",
                      "https://user:pass@example.org/a.xml", "https://localhost/a.xml",
                      "https://host.local/a.xml", "https://127.0.0.1/a.xml",
                      "https://[::1]/a.xml", "https://example.org:8443/a.xml",
                      "https://example.org/a.xml?token=secret", "https://example.org/a.xml#fragment"):
            with self.subTest(value=value), self.assertRaises(UpdateConfigurationError):
                validate_feed_url(value)

    def test_development_start_never_reads_config_or_loads_code(self):
        with patch("app.core.app_updates.sys.frozen", False, create=True), \
                patch("app.core.app_updates.read_update_configuration") as read:
            self.assertEqual(installed_update_availability().reason, "development_build")
            read.assert_not_called()

    def test_wrong_target_is_unavailable(self):
        with patch("app.core.app_updates.sys.frozen", True, create=True), \
                patch("app.core.app_updates.sys.platform", "win32"), \
                patch("pathlib.Path.is_file", return_value=True), \
                patch("app.core.app_updates.read_update_configuration", return_value=update_config()):
            self.assertEqual(installed_update_availability().reason, "wrong_target")

    def test_missing_config_is_not_latest_version(self):
        with patch("app.core.app_updates.sys.frozen", True, create=True), \
                patch("pathlib.Path.is_file", return_value=False):
            self.assertEqual(installed_update_availability().reason, "not_configured")

    def test_config_size_is_bounded(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(" " * 17000)
            with self.assertRaises(UpdateConfigurationError):
                read_update_configuration(path)

    def test_architecture_uses_process_not_installer_guess(self):
        self.assertEqual(process_architecture("AMD64"), "x86_64")
        self.assertEqual(process_architecture("aarch64"), "arm64")
        self.assertEqual(process_architecture("x86_64"), "x86_64")

    def test_checks_are_daily_and_recover_from_clock_correction(self):
        self.assertTrue(automatic_check_due(0, 100))
        self.assertFalse(automatic_check_due(100, 101))
        self.assertTrue(automatic_check_due(100, 86500))
        self.assertTrue(automatic_check_due(200, 100))


class UpdateInstanceProbeTests(unittest.TestCase):
    def test_source_process_does_not_query_process_list(self):
        run = Mock()
        with patch("app.core.app_updates.sys.frozen", False, create=True):
            self.assertFalse(other_installed_instances(run=run))
        run.assert_not_called()

    def test_macos_compares_full_executable_path_and_requires_self(self):
        executable = "/Applications/ICSTeX.app/Contents/MacOS/ICSTeX"
        with patch("app.core.app_updates.sys.frozen", True, create=True), \
                patch("app.core.app_updates.sys.platform", "darwin"), \
                patch("app.core.app_updates.sys.executable", executable), patch("os.getpid", return_value=101):
            for output, expected in ((f"101 {executable}\n202 /other/ICSTeX\n", False),
                                     (f"101 {executable}\n202 {executable}\n", True)):
                run = Mock(return_value=SimpleNamespace(stdout=output))
                self.assertEqual(other_installed_instances(run=run), expected)
                self.assertEqual(run.call_args.args[0], ["/bin/ps", "-ww", "-axo", "pid=,comm="])
            with self.assertRaises(RuntimeError):
                other_installed_instances(run=Mock(return_value=SimpleNamespace(stdout="")))
            with self.assertRaises(OSError):
                other_installed_instances(run=Mock(side_effect=OSError("process lookup failed")))

    def test_windows_checks_other_pids_without_a_shell_or_path_lookup(self):
        with patch("app.core.app_updates.sys.frozen", True, create=True), \
                patch("app.core.app_updates.sys.platform", "win32"), \
                patch("app.core.app_updates.sys.executable", "/fixture/ICSTeX.exe"), \
                patch.dict("os.environ", {"SystemRoot": "/Windows"}), patch("os.getpid", return_value=101):
            for output, expected in (( '\"ICSTeX.exe\",\"101\"\n', False),
                                     ('\"ICSTeX.exe\",\"101\"\n\"icstex.exe\",\"202\"\n', True)):
                run = Mock(return_value=SimpleNamespace(stdout=output))
                self.assertEqual(other_installed_instances(run=run), expected)
                self.assertEqual(run.call_args.args[0][0], "/Windows/System32/tasklist.exe")
                self.assertNotIn("shell", run.call_args.kwargs)
            with self.assertRaises(RuntimeError):
                other_installed_instances(run=Mock(return_value=SimpleNamespace(stdout="INFO: no tasks")))


class UpdatePackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / "packaging" / "native_updates.py"))

    def test_unsigned_or_tampered_sdk_is_rejected_before_extract(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "sdk.zip"
            path.write_bytes(b"not the pinned native SDK")
            output = Path(temporary) / "runtime"
            with self.assertRaises(ValueError):
                self.helpers["prepare_runtime"](path, update_config(), output)
            self.assertFalse(output.exists())

    def test_sparkle_security_and_offline_defaults_are_explicit(self):
        info = self.helpers["sparkle_plist"](update_config())
        self.assertEqual(info["CFBundleVersion"], "101")
        self.assertTrue(info["SURequireSignedFeed"])
        self.assertTrue(info["SUVerifyUpdateBeforeExtraction"])
        self.assertEqual(info["SUSignedFeedFailureExpirationInterval"], 0)
        for key in ("SUEnableAutomaticChecks", "SUAutomaticallyUpdate", "SUAllowsAutomaticUpdates",
                    "SUEnableSystemProfiling", "SUShowReleaseNotes", "SUEnableJavaScript"):
            self.assertIs(info[key], False)

    def test_default_packaging_remains_without_updater_runtime(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(self.helpers["runtime_from_environment"](), (None, None))
        self.assertEqual(self.helpers["runtime_datas"](None), [])
