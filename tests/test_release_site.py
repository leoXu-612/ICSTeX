from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "website"
MANIFEST = ROOT / "release" / "release-manifest.json"


class ReleaseSiteTests(TestCase):
    def read_text(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_release_json_is_generated_and_current(self) -> None:
        result = subprocess.run(
            [sys.executable, "tools/update_release_site.py", "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_release_metadata_matches_the_manifest(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        release = json.loads((WEBSITE / "release.json").read_text(encoding="utf-8"))

        self.assertEqual(release["version"], manifest["version"])
        self.assertEqual(release["tag"], manifest["tag"])
        self.assertEqual(release["channel"], manifest["channel"])
        self.assertEqual(release["repository"], "leoXu-612/ICSTeX")
        self.assertFalse(release["github_release_published"])
        self.assertTrue(any(item["primary_download"] for item in release["assets"]))

    def test_static_site_has_no_local_or_development_urls(self) -> None:
        forbidden = ("localhost", "127.0.0.1", "file://", "/Users/", "C:\\\\Users\\\\")
        for path in WEBSITE.glob("*.js"):
            source = path.read_text(encoding="utf-8")
            for value in forbidden:
                self.assertNotIn(value, source, f"{value!r} leaked into {path.relative_to(ROOT)}")
        html = self.read_text("website/index.html")
        for value in forbidden:
            self.assertNotIn(value, html, f"{value!r} leaked into website/index.html")

    def test_structure_is_semantic_accessibile_and_release_driven(self) -> None:
        html = self.read_text("website/index.html")
        app = self.read_text("website/app.js")

        for element in ("<header", "<nav", "<main", "<section", "<footer", "lang=\"zh-Hans\""):
            self.assertIn(element, html)
        self.assertIn("skip-link", html)
        self.assertIn("release.json", app)
        self.assertIn("github_release_published", app)
        self.assertNotIn("2.1.0-beta.1", html)
        self.assertNotIn("2.1.0-beta.1", app)
        self.assertIn("prefers-reduced-motion", self.read_text("website/styles.css"))
        self.assertIn('aria-live="polite"', html)
        self.assertIn('href="vendor/pico.min.css"', html)

    def test_reused_product_assets_are_checked_in(self) -> None:
        html = self.read_text("website/index.html")
        for name in ("main-window.png", "block-console.png", "125-narrow.png", "icstex-mark.png"):
            self.assertTrue((WEBSITE / "assets" / name).is_file(), name)
            self.assertIn(f"assets/{name}", html)

    def test_local_pico_dependency_includes_its_license(self) -> None:
        pico = WEBSITE / "vendor" / "pico.min.css"
        license_file = WEBSITE / "vendor" / "PICO-LICENSE.md"
        self.assertTrue(pico.is_file())
        self.assertTrue(license_file.is_file())
        self.assertGreater(pico.stat().st_size, 50_000)
        self.assertIn("MIT License", license_file.read_text(encoding="utf-8"))

    def test_deployment_script_has_an_explicit_push_guard(self) -> None:
        script = ROOT / "tools" / "deploy_release_site.sh"
        result = subprocess.run(["bash", "-n", str(script)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        source = script.read_text(encoding="utf-8")
        self.assertIn("--prepare", source)
        self.assertIn("--push", source)
        self.assertIn("ICSTEX_RELEASE_SITE_PUSH=1", source)
