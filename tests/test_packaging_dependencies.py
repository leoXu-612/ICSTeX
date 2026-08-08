from __future__ import annotations

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


_HELPER_PATH = Path(__file__).resolve().parents[1] / "packaging" / "install_build_dependencies.py"
_SPEC = importlib.util.spec_from_file_location("icstex_build_dependencies", _HELPER_PATH)
assert _SPEC is not None and _SPEC.loader is not None
build_dependencies = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_dependencies)


class PackagingDependencyTests(TestCase):
    def test_unreachable_loopback_proxy_is_removed_for_subprocess_only(self) -> None:
        source = {
            "HTTP_PROXY": "http://127.0.0.1:7897",
            "HTTPS_PROXY": "http://proxy.example:8080",
            "PATH": "example",
        }

        cleaned, removed = build_dependencies.sanitized_proxy_environment(
            source,
            probe=lambda _host, _port: False,
        )

        self.assertNotIn("HTTP_PROXY", cleaned)
        self.assertEqual(cleaned["HTTPS_PROXY"], "http://proxy.example:8080")
        self.assertEqual(cleaned["PATH"], "example")
        self.assertEqual(removed, ("HTTP_PROXY",))
        self.assertIn("HTTP_PROXY", source)

    def test_reachable_loopback_proxy_is_preserved(self) -> None:
        source = {"PIP_PROXY": "localhost:7897"}

        cleaned, removed = build_dependencies.sanitized_proxy_environment(
            source,
            probe=lambda host, port: host == "localhost" and port == 7897,
        )

        self.assertEqual(cleaned, source)
        self.assertEqual(removed, ())

    def test_local_pylatexenc_wheel_is_installed_before_requirements(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = root / "pylatexenc-2.10-py3-none-any.whl"
            wheel.touch()

            commands = build_dependencies.install_commands(root, "python")

        self.assertEqual(commands[0][-1], str(wheel))
        self.assertIn("--no-deps", commands[0])
        self.assertEqual(commands[1][-4:], ("-r", str(root / "requirements.txt"), "-r", str(root / "requirements-packaging.txt")))

    def test_invalid_loopback_proxy_value_is_left_for_pip_to_report(self) -> None:
        source = {"ALL_PROXY": "http://127.0.0.1:not-a-port"}

        cleaned, removed = build_dependencies.sanitized_proxy_environment(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(removed, ())

    def test_platform_build_scripts_use_dependency_helper(self) -> None:
        root = Path(__file__).resolve().parents[1]
        windows_script = (root / "packaging" / "build_windows.bat").read_text(encoding="utf-8")
        macos_script = (root / "packaging" / "build_macos.sh").read_text(encoding="utf-8")
        preflight_script = (root / "packaging" / "preflight.sh").read_text(encoding="utf-8")
        source_archive_script = (root / "packaging" / "build_source_archive.sh").read_text(encoding="utf-8")

        self.assertIn(r"python packaging\install_build_dependencies.py", windows_script)
        self.assertIn("platform.machine().lower()", windows_script)
        self.assertIn(r"ICSTeX-%APP_VERSION%-Windows-%WINDOWS_ARCH%.zip", windows_script)
        self.assertIn(r"ICSTeX-%APP_VERSION%-Windows-x64-Setup.exe", windows_script)
        self.assertNotIn(r"ICSTeX-%APP_VERSION%-Windows.zip", windows_script)
        self.assertIn("python3 packaging/install_build_dependencies.py", macos_script)
        self.assertIn("python3 -m PyInstaller packaging/ICSTeX.spec", macos_script)
        self.assertIn("packaging/install_build_dependencies.py", preflight_script)
        self.assertIn('WINDOWS_ARCH in x64 arm64', preflight_script)
        self.assertIn('Windows-$WINDOWS_ARCH.zip', preflight_script)
        self.assertIn("app tests packaging tools website docs", source_archive_script)
        self.assertIn("--exclude 'release.json'", source_archive_script)
        self.assertIn("release/*.md release/*-verification.txt", source_archive_script)
