from __future__ import annotations

import json
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "website"
MANIFEST = ROOT / "release" / "release-manifest.json"


class SiteHTMLInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.heading_levels: list[int] = []
        self.images: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if element_id := attributes.get("id"):
            self.ids.append(element_id)
        if len(tag) == 2 and tag.startswith("h") and tag[1].isdigit():
            self.heading_levels.append(int(tag[1]))
        if tag == "img":
            self.images.append(attributes)


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
        self.assertEqual(
            release["github_repository_public"],
            manifest["github_repository_public"],
        )
        self.assertEqual(
            release["github_release_published"],
            manifest["github_release_published"],
        )
        self.assertTrue(release["github_repository_public"])
        self.assertTrue(release["github_release_published"])
        self.assertTrue(any(item["primary_download"] for item in release["assets"]))

        primary = next(item for item in release["assets"] if item["primary_download"])
        expected_url = (
            f"https://github.com/{release['repository']}/releases/download/"
            f"{release['tag']}/{primary['name']}"
        )
        self.assertEqual(primary["download_url"], expected_url)

    def test_static_site_has_no_local_or_development_urls(self) -> None:
        forbidden = ("localhost", "127.0.0.1", "file://", "/Users/", "C:\\\\Users\\\\")
        for path in list(WEBSITE.glob("*.js")) + list(WEBSITE.rglob("*.html")):
            source = path.read_text(encoding="utf-8")
            for value in forbidden:
                self.assertNotIn(value, source, f"{value!r} leaked into {path.relative_to(ROOT)}")

    def test_structure_is_semantic_accessibile_and_release_driven(self) -> None:
        html = self.read_text("website/index.html")
        app = self.read_text("website/app.js")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        for element in ("<header", "<nav", "<main", "<section", "<footer", "lang=\"zh-Hans\""):
            self.assertIn(element, html)
        self.assertIn("skip-link", html)
        self.assertIn("release.json", app)
        self.assertIn("github_release_published", app)
        self.assertIn("github_repository_public", app)
        self.assertIn("release.release_name", app)
        self.assertIn('<span class="hero-title-version" data-release="version">', html)
        for value in (manifest["version"], manifest["tag"], "2.1 BETA 1"):
            self.assertNotIn(value, html)
            self.assertNotIn(value, app)
        self.assertIn("prefers-reduced-motion", self.read_text("website/styles.css"))
        self.assertIn('aria-live="polite"', html)
        self.assertIn('href="vendor/pico.min.css"', html)

    def test_platform_install_picker_is_keyboard_accessible_and_truthful(self) -> None:
        html = self.read_text("website/index.html")
        app = self.read_text("website/app.js")

        self.assertIn('role="tablist"', html)
        self.assertEqual(html.count('role="tab"'), 2)
        self.assertEqual(html.count('role="tabpanel"'), 2)
        for value in ("macos-dmg", "macos-zip", "windows-arm64"):
            self.assertIn(f'data-release-download="{value}"', html)
            self.assertIn(f'data-release-sha="{value}"', html)
        for key in ("ArrowLeft", "ArrowRight", "Home", "End"):
            self.assertIn(key, app)
        self.assertIn("history.replaceState", app)
        self.assertIn('window.addEventListener("hashchange"', app)
        self.assertIn("repositoryPublic && releasePublished", app)
        self.assertIn("Windows x64", html)
        self.assertIn("尚不可下载", html)
        self.assertNotIn('href="https://github.com', html)

    def test_html_ids_headings_and_images_are_accessible(self) -> None:
        for path in WEBSITE.rglob("*.html"):
            inspector = SiteHTMLInspector()
            inspector.feed(path.read_text(encoding="utf-8"))

            self.assertEqual(len(inspector.ids), len(set(inspector.ids)), path)
            self.assertEqual(inspector.heading_levels.count(1), 1, path)
            self.assertEqual(inspector.heading_levels[0], 1, path)
            for previous, current in zip(inspector.heading_levels, inspector.heading_levels[1:]):
                self.assertLessEqual(current - previous, 1, (path, inspector.heading_levels))
            for image in inspector.images:
                self.assertIn("alt", image, path)
                self.assertTrue(image.get("width"), (path, image))
                self.assertTrue(image.get("height"), (path, image))

    def test_information_groups_and_static_architecture_are_bounded(self) -> None:
        html = self.read_text("website/index.html")
        combined = "\n".join(
            (html, self.read_text("website/app.js"), self.read_text("website/styles.css"))
        ).lower()

        for element_id in ("download", "formula", "ocr", "workspace", "local", "limits"):
            self.assertIn(f'id="{element_id}"', html)
        for forbidden in ("react", "next.js", "tailwind", "fonts.googleapis.com"):
            self.assertNotIn(forbidden, combined)

        for readable_copy in (
            "选择你的电脑系统",
            "边看公式，边改 LaTeX",
            "源码、PDF 和项目结构放在同一个窗口",
            "你的论文默认留在自己的电脑里",
            "这是 Beta 版，还有这些限制",
        ):
            self.assertIn(readable_copy, html)
        for internal_copy in (
            "LOCAL-FIRST ASSURANCE",
            "边界写在下载之前",
            "长文档仍然可以被看清",
        ):
            self.assertNotIn(internal_copy, html)

    def test_reused_product_assets_are_checked_in(self) -> None:
        html = self.read_text("website/index.html")
        for name in ("main-window.png", "block-console.png", "icstex-mark.png"):
            self.assertTrue((WEBSITE / "assets" / name).is_file(), name)
            self.assertIn(f"assets/{name}", html)
        self.assertTrue((WEBSITE / "assets" / "125-narrow.png").is_file())

    def test_information_architecture_and_secondary_pages_exist(self) -> None:
        index = self.read_text("website/index.html")
        guide = self.read_text("website/guide/index.html")
        about = self.read_text("website/about/index.html")

        for page in (guide, about):
            self.assertIn('lang="zh-Hans"', page)
            self.assertIn('class="skip-link"', page)
            self.assertIn('id="main-content"', page)
            self.assertIn("../app.js", page)
            self.assertIn("../config.js", page)
        for value in ("Formula Intelligence", "使用指南", "理念", "PUBLIC BETA", "data-release-document=\"RELEASE_NOTES.md\""):
            self.assertIn(value, index)
        for value in ("功能一览", "安装与环境检查", "formula-editor", "formula-recognition", "compile-pdf", "Block 工作区", "常见问题"):
            self.assertIn(value, guide)
        for value in ("为什么有 ICSTeX", "本地优先", "容易理解", "兼容 LaTeX", "公开信", "徐铭华 敬上"):
            self.assertIn(value, about)

    def test_release_consistency_verifier_checks_all_pages(self) -> None:
        result = subprocess.run(
            [sys.executable, "tools/verify_release_consistency.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Release consistency PASS", result.stdout)

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
