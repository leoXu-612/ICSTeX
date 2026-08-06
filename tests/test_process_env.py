from __future__ import annotations

import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.core.process_env import latex_subprocess_env


class ProcessEnvTests(TestCase):
    def test_rewrites_unsupported_macos_c_utf8_locale(self) -> None:
        with patch("app.core.process_env.sys.platform", "darwin"):
            with patch.dict("app.core.process_env.os.environ", {"LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}, clear=True):
                env = latex_subprocess_env()

        self.assertEqual(env["LC_ALL"], "en_US.UTF-8")
        self.assertEqual(env["LANG"], "en_US.UTF-8")

    def test_adds_common_mactex_path_for_packaged_app(self) -> None:
        with patch("app.core.runtime_paths.sys.platform", "darwin"):
            with patch.dict("app.core.process_env.os.environ", {"PATH": "/usr/bin:/bin"}, clear=True):
                env = latex_subprocess_env()

        self.assertIn("/Library/TeX/texbin", env["PATH"].split(":"))

    def test_preview_texinputs_prefix_preserves_existing_and_default_paths(self) -> None:
        overlay = Path("/tmp/project/.icstex/preview/assets")
        with patch.dict(
            "app.core.process_env.os.environ",
            {"TEXINPUTS": "/custom/tex"},
            clear=True,
        ):
            env = latex_subprocess_env(texinputs_prefix=overlay)

        parts = env["TEXINPUTS"].split(os.pathsep)
        self.assertEqual(parts[0], str(overlay.resolve()))
        self.assertEqual(parts[1], "/custom/tex")

    def test_preview_texinputs_keeps_default_search_when_unset(self) -> None:
        with patch.dict("app.core.process_env.os.environ", {}, clear=True):
            env = latex_subprocess_env(texinputs_prefix="/tmp/preview")

        self.assertTrue(env["TEXINPUTS"].endswith(os.pathsep))
