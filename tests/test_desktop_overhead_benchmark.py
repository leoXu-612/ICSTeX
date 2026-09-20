"""Statistical labels must match the benchmark sample count."""
from unittest import TestCase

from tools.bench_desktop_overhead import summary


class DesktopOverheadSummaryTests(TestCase):
    def test_five_startups_do_not_claim_a_tail_percentile(self):
        result = summary([8., 2., 6., 4., 10.])
        self.assertEqual(result["median_ms"], 6.)
        self.assertEqual(result["samples_ms"], [8., 2., 6., 4., 10.])
        self.assertNotIn("p95_ms", result)

    def test_thirty_interactions_keep_all_samples_and_nearest_rank_p95(self):
        samples = list(reversed(range(30)))
        result = summary(samples)
        self.assertEqual(result["n"], 30)
        self.assertEqual(result["p95_ms"], 28)
        self.assertEqual(result["samples_ms"], samples)
