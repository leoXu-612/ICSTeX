from itertools import product
from unittest import TestCase

from app.core.build_events import automatic_build_purpose
from app.core.compiler import BuildPurpose


class AutomaticBuildAdmissionTests(TestCase):
    def test_all_permission_and_preference_combinations(self) -> None:
        for enabled, authorized, preview in product((False, True), repeat=3):
            with self.subTest(enabled=enabled, authorized=authorized, preview=preview):
                expected = None
                if enabled and authorized:
                    expected = BuildPurpose.PREVIEW if preview else BuildPurpose.FINAL
                self.assertEqual(automatic_build_purpose(
                    enabled=enabled, authorized=authorized, fast_preview=preview,
                ), expected)
