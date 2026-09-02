from __future__ import annotations

import threading
import time
from unittest import TestCase

from app.core.agent_concurrency import AgentOperationCancelled, AgentQueueTimeout, WorkspaceConcurrency


class WorkspaceConcurrencyTests(TestCase):
    def test_reads_overlap_but_never_exceed_configured_capacity(self) -> None:
        concurrency = WorkspaceConcurrency(max_readers=4)
        start = threading.Barrier(6)
        release = threading.Event()
        four_entered = threading.Event()
        state_lock = threading.Lock()
        active = 0
        maximum = 0
        completed = 0

        def read() -> None:
            nonlocal active, maximum, completed
            start.wait()
            with concurrency.read():
                with state_lock:
                    active += 1
                    maximum = max(maximum, active)
                    if active == 4:
                        four_entered.set()
                release.wait(2)
                with state_lock:
                    active -= 1
                    completed += 1

        threads = [threading.Thread(target=read) for _ in range(5)]
        for thread in threads:
            thread.start()
        start.wait()
        self.assertTrue(four_entered.wait(2))
        with state_lock:
            self.assertEqual(active, 4)
            self.assertEqual(completed, 0)
        release.set()
        for thread in threads:
            thread.join(3)

        self.assertEqual(completed, 5)
        self.assertEqual(maximum, 4)

    def test_queued_writer_blocks_later_reader_until_exclusive_finishes(self) -> None:
        concurrency = WorkspaceConcurrency(max_readers=2)
        first_reader_entered = threading.Event()
        release_first_reader = threading.Event()
        writer_entered = threading.Event()
        release_writer = threading.Event()
        late_reader_entered = threading.Event()

        def first_reader() -> None:
            with concurrency.read():
                first_reader_entered.set()
                release_first_reader.wait(2)

        def writer() -> None:
            with concurrency.exclusive():
                writer_entered.set()
                release_writer.wait(2)

        def late_reader() -> None:
            with concurrency.read():
                late_reader_entered.set()

        reader_thread = threading.Thread(target=first_reader)
        writer_thread = threading.Thread(target=writer)
        late_reader_thread = threading.Thread(target=late_reader)
        reader_thread.start()
        self.assertTrue(first_reader_entered.wait(1))
        writer_thread.start()
        self._wait_for_queued(concurrency, 1)
        late_reader_thread.start()
        self.assertFalse(late_reader_entered.wait(0.05))

        release_first_reader.set()
        self.assertTrue(writer_entered.wait(1))
        self.assertFalse(late_reader_entered.wait(0.05))
        release_writer.set()
        self.assertTrue(late_reader_entered.wait(1))
        for thread in (reader_thread, writer_thread, late_reader_thread):
            thread.join(2)

    def test_exclusive_operations_start_in_fifo_order(self) -> None:
        concurrency = WorkspaceConcurrency()
        first_entered = threading.Event()
        release_first = threading.Event()
        order: list[str] = []

        def exclusive(name: str, hold: bool = False) -> None:
            with concurrency.exclusive():
                order.append(name)
                if hold:
                    first_entered.set()
                    release_first.wait(2)

        first = threading.Thread(target=exclusive, args=("first", True))
        second = threading.Thread(target=exclusive, args=("second",))
        third = threading.Thread(target=exclusive, args=("third",))
        first.start()
        self.assertTrue(first_entered.wait(1))
        second.start()
        self._wait_for_queued(concurrency, 1)
        third.start()
        self._wait_for_queued(concurrency, 2)
        release_first.set()
        for thread in (first, second, third):
            thread.join(2)

        self.assertEqual(order, ["first", "second", "third"])

    def test_stop_cancels_queued_compile_but_preserves_waiting_write(self) -> None:
        concurrency = WorkspaceConcurrency()
        active_entered = threading.Event()
        release_active = threading.Event()
        compile_cancelled = threading.Event()
        write_completed = threading.Event()

        def active_compile() -> None:
            with concurrency.exclusive("compile"):
                active_entered.set()
                release_active.wait(2)

        def queued_compile() -> None:
            try:
                with concurrency.exclusive("compile"):
                    self.fail("cancelled compile entered the exclusive section")
            except AgentOperationCancelled:
                compile_cancelled.set()

        def queued_write() -> None:
            with concurrency.exclusive():
                write_completed.set()

        active = threading.Thread(target=active_compile)
        compile_thread = threading.Thread(target=queued_compile)
        write_thread = threading.Thread(target=queued_write)
        active.start()
        self.assertTrue(active_entered.wait(1))
        compile_thread.start()
        self._wait_for_queued(concurrency, 1)
        write_thread.start()
        self._wait_for_queued(concurrency, 2)

        self.assertEqual(concurrency.cancel_pending_compiles(), 1)
        self.assertTrue(compile_cancelled.wait(1))
        release_active.set()
        self.assertTrue(write_completed.wait(1))
        for thread in (active, compile_thread, write_thread):
            thread.join(2)

    def test_compile_queue_timeout_does_not_enter_exclusive_section(self) -> None:
        concurrency = WorkspaceConcurrency()
        with concurrency.exclusive():
            started = time.monotonic()
            with self.assertRaises(AgentQueueTimeout):
                with concurrency.exclusive("compile", timeout_seconds=0.02):
                    self.fail("timed out compile entered the exclusive section")
            self.assertLess(time.monotonic() - started, 0.5)

    def test_recognition_and_network_limits_are_independent(self) -> None:
        concurrency = WorkspaceConcurrency(max_recognition=1, max_network=1)
        recognition_entered = threading.Event()
        network_entered = threading.Event()
        release = threading.Event()

        def recognize() -> None:
            with concurrency.recognition():
                recognition_entered.set()
                release.wait(2)

        def network() -> None:
            with concurrency.network():
                network_entered.set()
                release.wait(2)

        recognition_thread = threading.Thread(target=recognize)
        network_thread = threading.Thread(target=network)
        recognition_thread.start()
        network_thread.start()
        self.assertTrue(recognition_entered.wait(1))
        self.assertTrue(network_entered.wait(1))
        release.set()
        recognition_thread.join(2)
        network_thread.join(2)

    def _wait_for_queued(self, concurrency: WorkspaceConcurrency, expected: int) -> None:
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            with concurrency._condition:
                if len(concurrency._exclusive_queue) >= expected:
                    return
            time.sleep(0.005)
        self.fail(f"expected at least {expected} queued exclusive operation(s)")
