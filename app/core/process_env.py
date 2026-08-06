from __future__ import annotations

import os
from pathlib import Path
import sys

from app.core.runtime_paths import augmented_path


MACOS_UTF8_LOCALE = "en_US.UTF-8"
UNSUPPORTED_MACOS_LOCALES = {"C.UTF-8", "C.utf8"}


def latex_subprocess_env(*, texinputs_prefix: str | Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = augmented_path(env.get("PATH", ""))
    if texinputs_prefix is not None:
        prefix = str(Path(texinputs_prefix).expanduser().resolve()).replace("\\", "/").rstrip("/")
        existing = env.get("TEXINPUTS", "")
        # The trailing empty component retains kpathsea's default search path.
        env["TEXINPUTS"] = f"{prefix}{os.pathsep}{existing}" if existing else f"{prefix}{os.pathsep}"
    if sys.platform == "darwin":
        for key in ("LC_ALL", "LC_CTYPE", "LANG"):
            if env.get(key) in UNSUPPORTED_MACOS_LOCALES:
                env[key] = MACOS_UTF8_LOCALE
    return env
