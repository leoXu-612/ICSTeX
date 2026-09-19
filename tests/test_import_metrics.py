from __future__ import annotations

import threading
import time
from unittest import TestCase

from app.core.import_metrics import ImportMetrics, ImportRecorder


class ImportMetricsTests(TestCase):
    def test_transaction_records_stages_with_durations(self) -> None:
        metrics = ImportMetrics()
        recorder = metrics.begin_transaction("t-1")
        recorder.step("drop_received")
        time.sleep(0.01)
        recorder.step("copy_finished", size="12")
        time.sleep(0.01)
        recorder.step("import_finished")

        summary = metrics.finish_transaction(recorder)

        stages = summary["stages"]
        self.assertIn("drop_received", stages)
        self.assertGreaterEqual(stages["copy_finished"], 0.009)
        self.assertEqual(stages["import_finished"], 0.0)

    def test_compile_counts_attributed_to_awaiting_transaction(self) -> None:
        metrics = ImportMetrics()
        recorder = metrics.begin_transaction("t-2")
        metrics.record_compile_request("asset_import")

        partial = metrics.finish_transaction(recorder)
        self.assertEqual(partial["compile_requested"], 1)
        self.assertEqual(partial["compile_started"], 0)

        metrics.record_compile_start("preview")
        metrics.record_compile_finish("preview")

        latest = metrics.latest_summary()
        assert latest is not None
        self.assertEqual(latest["compile_requested"], 1)
        self.assertEqual(latest["compile_started"], 1)
        self.assertEqual(latest["compile_coalesced"], 0)
        self.assertIn("compile_finished", latest["stages"])

    def test_coalesced_requests_are_counted(self) -> None:
        metrics = ImportMetrics()
        recorder = metrics.begin_transaction("t-3")
        metrics.record_compile_request("first")
        metrics.record_compile_request("second")
        metrics.record_compile_start("started-once")
        metrics.record_compile_finish("done")

        latest = metrics.latest_summary()
        assert latest is not None
        self.assertEqual(latest["compile_requested"], 2)
        self.assertEqual(latest["compile_started"], 1)
        self.assertEqual(latest["compile_coalesced"], 1)

    def test_full_index_scan_counter(self) -> None:
        metrics = ImportMetrics()
        recorder = metrics.begin_transaction("t-4")
        metrics.record_index_scan(full=True)
        metrics.record_index_scan(full=False)

        summary = metrics.finish_transaction(recorder)

        self.assertEqual(summary["full_index_scans"], 1)

    def test_format_summary_contains_required_fields(self) -> None:
        metrics = ImportMetrics()
        recorder = metrics.begin_transaction("t-5")
        recorder.step("drop_received")
        recorder.record("copy", 0.12)
        metrics.record_compile_request("asset_import")
        metrics.record_compile_start("preview")
        metrics.record_compile_finish("preview")

        metrics.finish_transaction(recorder)
        text = recorder.format_summary()

        self.assertIn("transaction=t-5", text)
        self.assertIn("compile requested: 1", text)
        self.assertIn("compile actually started: 1", text)
        self.assertIn("compile requests coalesced: 0", text)
        self.assertIn("copy=0.12s", text)

    def test_expired_awaiting_transaction_is_finalized(self) -> None:
        metrics = ImportMetrics()
        recorder = metrics.begin_transaction("t-6")
        metrics.record_compile_request("never-starts")
        metrics.finish_transaction(recorder)

        metrics.finalize_expired(max_age=0.0)

        latest = metrics.latest_summary()
        assert latest is not None
        self.assertEqual(latest["compile_requested"], 1)
        self.assertEqual(latest["compile_started"], 0)

    def test_record_compile_event_dispatches(self) -> None:
        metrics = ImportMetrics()
        recorder = metrics.begin_transaction("t-7")
        metrics.record_compile_event("request", "reason-a")
        metrics.record_compile_event("start", "preview")
        metrics.record_compile_event("finish", "preview")

        latest = metrics.latest_summary()
        assert latest is not None
        self.assertEqual(latest["compile_requested"], 1)
        self.assertEqual(latest["compile_started"], 1)

    def test_concurrent_recording_is_safe(self) -> None:
        metrics = ImportMetrics()
        recorder = metrics.begin_transaction("t-8")
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(50):
                    metrics.record_compile_request("x")
                    metrics.record_compile_start("x")
                    metrics.record_compile_finish("x")
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        metrics.finish_transaction(recorder)
        metrics.finalize_expired(max_age=0.0)

    def test_recorder_step_meta_is_stringified(self) -> None:
        recorder = ImportRecorder("t-9")
        recorder.step("source_validated", count=3)
        self.assertEqual(recorder.stages[-1].meta, {"count": "3"})
