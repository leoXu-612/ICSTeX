"""Build-bound native updater configuration; no networking or installation code."""
from __future__ import annotations

import base64
import binascii
import csv
from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
import platform
import subprocess
import sys
from urllib.parse import urlsplit

from app import __version__


CONFIG_NAME = "app-update.json"
CHECK_INTERVAL_SECONDS = 24 * 60 * 60
SUPPORTED_TARGETS = {("darwin", "arm64"), ("darwin", "x86_64"),
                     ("win32", "arm64"), ("win32", "x86_64")}


class UpdateConfigurationError(ValueError):
    pass


def process_architecture(machine: str | None = None) -> str:
    value = (machine if machine is not None else platform.machine()).lower()
    return {"aarch64": "arm64", "amd64": "x86_64"}.get(value, value)


def validate_feed_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise UpdateConfigurationError("invalid_feed")
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        valid = (parsed.scheme == "https" and host and parsed.port in (None, 443)
                 and not parsed.username and not parsed.password
                 and not parsed.query and not parsed.fragment)
    except ValueError as exc:
        raise UpdateConfigurationError("invalid_feed") from exc
    if not valid or host == "localhost" or host.endswith((".localhost", ".local")):
        raise UpdateConfigurationError("invalid_feed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise UpdateConfigurationError("invalid_feed")
    return value


@dataclass(frozen=True)
class UpdateConfiguration:
    version: str
    release_sequence: int
    channel: str
    target_platform: str
    architecture: str
    feed_url: str
    public_key: str

    @classmethod
    def from_dict(cls, value: object) -> "UpdateConfiguration":
        if not isinstance(value, dict) or type(value.get("schema")) is not int or value["schema"] != 1:
            raise UpdateConfigurationError("invalid_schema")
        keys = {"schema", "version", "release_sequence", "channel", "platform",
                "architecture", "feed_url", "public_key"}
        if set(value) != keys:
            raise UpdateConfigurationError("invalid_fields")
        if not all(isinstance(value[name], str) for name in
                   ("version", "channel", "platform", "architecture", "feed_url", "public_key")):
            raise UpdateConfigurationError("invalid_field_type")
        sequence = value["release_sequence"]
        if type(sequence) is not int or not 0 < sequence < 2**31:
            raise UpdateConfigurationError("invalid_release_sequence")
        if not isinstance(value["version"], str) or value["version"] != __version__:
            raise UpdateConfigurationError("version_mismatch")
        if value["channel"] not in ("stable", "beta"):
            raise UpdateConfigurationError("invalid_channel")
        if value["channel"] == "stable" and "-" in value["version"]:
            raise UpdateConfigurationError("prerelease_in_stable")
        if (value["platform"], value["architecture"]) not in SUPPORTED_TARGETS:
            raise UpdateConfigurationError("unsupported_target")
        key = value["public_key"]
        try:
            valid_key = isinstance(key, str) and len(base64.b64decode(key, validate=True)) == 32
        except (ValueError, binascii.Error):
            valid_key = False
        if not valid_key:
            raise UpdateConfigurationError("invalid_public_key")
        return cls(value["version"], sequence, value["channel"], value["platform"],
                   value["architecture"], validate_feed_url(value["feed_url"]), key)

    def as_dict(self) -> dict:
        return {"schema": 1, "version": self.version,
                "release_sequence": self.release_sequence, "channel": self.channel,
                "platform": self.target_platform, "architecture": self.architecture,
                "feed_url": self.feed_url, "public_key": self.public_key}


def read_update_configuration(path: Path) -> UpdateConfiguration:
    if path.stat().st_size > 16384:
        raise UpdateConfigurationError("config_too_large")
    return UpdateConfiguration.from_dict(json.loads(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class UpdateAvailability:
    config: UpdateConfiguration | None
    reason: str = ""
    library_path: Path | None = None

    @property
    def available(self) -> bool:
        return self.config is not None and self.library_path is not None and not self.reason


def installed_update_availability() -> UpdateAvailability:
    """Never discover updater code/configuration from a project, CWD or environment."""
    if not getattr(sys, "frozen", False):
        return UpdateAvailability(None, "development_build")
    config_path = Path(__file__).resolve().parents[1] / "assets" / CONFIG_NAME
    if not config_path.is_file():
        return UpdateAvailability(None, "not_configured")
    try:
        config = read_update_configuration(config_path)
    except (OSError, ValueError, TypeError):
        return UpdateAvailability(None, "invalid_config")
    if (config.target_platform, config.architecture) != (sys.platform, process_architecture()):
        return UpdateAvailability(None, "wrong_target")
    if sys.platform == "darwin":
        contents = Path(sys.executable).parent.parent
        if contents.name != "Contents" or contents.parent.suffix != ".app":
            return UpdateAvailability(None, "not_installed")
        library = contents / "Frameworks" / "ICSTeXUpdateBridge.dylib"
    else:
        library = Path(sys._MEIPASS) / "updates" / "WinSparkle.dll"
    if not library.is_file():
        return UpdateAvailability(config, "missing_runtime")
    return UpdateAvailability(config, library_path=library)


def automatic_check_due(last_attempt: float, now: float) -> bool:
    # A future saved timestamp (clock correction) must not suppress checks forever.
    return last_attempt <= 0 or now < last_attempt or now - last_attempt >= CHECK_INTERVAL_SECONDS


def other_installed_instances(*, run=subprocess.run) -> bool:
    """Conservatively refuse replacement while another installed GUI is running.

    This only inspects process identities; it never signals or terminates them.
    A failed probe raises rather than treating an unknown state as safe.
    """
    if not getattr(sys, "frozen", False):
        return False
    import os
    executable = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        result = run(["/bin/ps", "-ww", "-axo", "pid=,comm="], capture_output=True, text=True,
                     timeout=5, check=True)
        seen_self = False
        for line in result.stdout.splitlines():
            fields = line.strip().split(None, 1)
            if len(fields) != 2 or not fields[0].isdigit():
                continue
            pid = int(fields[0])
            if pid == os.getpid():
                seen_self = True
            if pid != os.getpid() and Path(fields[1]).resolve() == executable:
                return True
        if not seen_self:
            raise RuntimeError("Current application missing from process probe")
        return False
    if sys.platform == "win32":
        system_root = Path(os.environ["SystemRoot"])
        if not system_root.is_absolute():
            raise RuntimeError("Invalid Windows system directory")
        tasklist = system_root / "System32" / "tasklist.exe"
        result = run([str(tasklist), "/FI", f"IMAGENAME eq {executable.name}", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True, timeout=5, check=True,
                     creationflags=0x08000000)
        seen_self = False
        for fields in csv.reader(result.stdout.splitlines()):
            if len(fields) < 2 or fields[0].casefold() != executable.name.casefold():
                continue
            if int(fields[1]) != os.getpid():
                return True
            seen_self = True
        if not seen_self:
            raise RuntimeError("Current application missing from process probe")
        return False
    raise RuntimeError("Unsupported native updater platform")
