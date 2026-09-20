"""Bounded in-process concurrency for the project-scoped MCP adapter.

The MCP SDK owns request dispatch and worker threads.  This module only
expresses ICSTeX's project consistency rules: bounded concurrent reads,
FIFO exclusive operations, and independently bounded heavy sidecars.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
import threading
import time
from typing import Iterator, Literal


ExclusiveKind = Literal["write", "compile"]


class AgentConcurrencyError(RuntimeError):
    """Base error for an operation rejected before workspace execution."""


class AgentOperationCancelled(AgentConcurrencyError):
    pass


class AgentQueueTimeout(AgentConcurrencyError):
    pass


@dataclass
class _ExclusiveRequest:
    sequence: int
    kind: ExclusiveKind
    cancelled: bool = False


class WorkspaceConcurrency:
    """Fair read/exclusive gate for one canonical project root.

    Readers may overlap up to ``max_readers``.  Exclusive operations are FIFO,
    block new readers once queued, and never overlap a reader or another
    exclusive operation.  Compile requests can be cancelled while queued so a
    concurrent ``compile_project(action="stop")`` cannot be followed by a
    previously waiting compile.
    """

    def __init__(
        self,
        *,
        max_readers: int = 4,
        max_recognition: int = 1,
        max_network: int = 1,
    ) -> None:
        if max_readers < 1 or max_recognition < 1 or max_network < 1:
            raise ValueError("concurrency limits must be positive")
        self._max_readers = max_readers
        self._condition = threading.Condition(threading.Lock())
        self._active_readers = 0
        self._active_exclusive: _ExclusiveRequest | None = None
        self._exclusive_queue: deque[_ExclusiveRequest] = deque()
        self._next_sequence = 1
        self._recognition = threading.BoundedSemaphore(max_recognition)
        self._network = threading.BoundedSemaphore(max_network)

    @contextmanager
    def read(self) -> Iterator[None]:
        """Enter one bounded, snapshot-consistent project read."""

        with self._condition:
            while (
                self._active_exclusive is not None
                or self._exclusive_queue
                or self._active_readers >= self._max_readers
            ):
                self._condition.wait()
            self._active_readers += 1
        try:
            yield
        finally:
            with self._condition:
                self._active_readers -= 1
                self._condition.notify_all()

    @contextmanager
    def exclusive(
        self,
        kind: ExclusiveKind = "write",
        *,
        timeout_seconds: float | None = None,
    ) -> Iterator[float | None]:
        """Enter a FIFO exclusive operation and yield its absolute deadline."""

        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        deadline = time.monotonic() + timeout_seconds if timeout_seconds is not None else None
        with self._condition:
            request = _ExclusiveRequest(self._next_sequence, kind)
            self._next_sequence += 1
            self._exclusive_queue.append(request)
            while True:
                if request.cancelled:
                    self._discard_queued(request)
                    self._condition.notify_all()
                    raise AgentOperationCancelled("编译请求已由 stop 取消，未启动编译。")
                if (
                    self._active_exclusive is None
                    and self._active_readers == 0
                    and self._exclusive_queue
                    and self._exclusive_queue[0] is request
                ):
                    self._exclusive_queue.popleft()
                    self._active_exclusive = request
                    break
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    self._discard_queued(request)
                    self._condition.notify_all()
                    raise AgentQueueTimeout("编译请求等待超时，未启动编译。")
                self._condition.wait(remaining)
        try:
            yield deadline
        finally:
            with self._condition:
                if self._active_exclusive is request:
                    self._active_exclusive = None
                self._condition.notify_all()

    def cancel_pending_compiles(self) -> int:
        """Cancel queued compile work without disturbing unrelated writes."""

        with self._condition:
            cancelled = 0
            for request in self._exclusive_queue:
                if request.kind == "compile" and not request.cancelled:
                    request.cancelled = True
                    cancelled += 1
            self._condition.notify_all()
            return cancelled

    @contextmanager
    def recognition(self) -> Iterator[None]:
        """Run one local OCR sidecar while participating as a project reader."""

        with self._recognition:
            with self.read():
                yield

    @contextmanager
    def network(self) -> Iterator[None]:
        """Run one explicit metadata request at a time."""

        with self._network:
            yield

    def _discard_queued(self, request: _ExclusiveRequest) -> None:
        try:
            self._exclusive_queue.remove(request)
        except ValueError:
            pass
