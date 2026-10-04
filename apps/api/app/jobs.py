"""Background job execution with a replaceable queue backend.

The PRD names Redis + Celery for the MVP but also requires that the queue system
be replaceable later (§8.17). To keep local development free of infrastructure
and keep tests deterministic, the queue is defined here behind a small
protocol:

* :class:`ThreadQueue` runs jobs on a background thread pool. This is the default.
* :class:`InlineQueue` runs jobs immediately on the calling thread. Tests use it
  so assertions never race the worker.
* :class:`RecordingQueue` captures submissions without executing them.

A Celery backend only needs to implement :class:`JobQueue` and be installed
with :func:`set_queue`. Nothing else in the application knows how jobs run.

Jobs are always recorded in the database before they are enqueued, so a queue
failure never loses the unit of work.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from .logging_config import get_logger
from typing import Callable, Protocol

logger = get_logger("jobs")

JobCallable = Callable[[], None]


class JobQueue(Protocol):
    """Minimal contract every queue backend must satisfy."""

    def enqueue(self, job_id: int, func: JobCallable) -> None: ...


class ThreadQueue:
    """Executes jobs on a small background thread pool."""

    def __init__(self, workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max(workers, 1), thread_name_prefix="adpilot-job")

    def enqueue(self, job_id: int, func: JobCallable) -> None:
        self._executor.submit(self._run, job_id, func)

    @staticmethod
    def _run(job_id: int, func: JobCallable) -> None:
        try:
            func()
        except Exception:  # noqa: BLE001 - a worker must never die silently
            logger.exception("background_job_failed", extra={"job_id": job_id})


class InlineQueue:
    """Executes jobs synchronously; deterministic for tests."""

    def enqueue(self, job_id: int, func: JobCallable) -> None:
        try:
            func()
        except Exception:  # noqa: BLE001 - surfaced through job state, not the queue
            logger.exception("inline_job_failed", extra={"job_id": job_id})


class RecordingQueue:
    """Stores jobs without running them so tests can assert on submissions."""

    def __init__(self) -> None:
        self.jobs: list[tuple[int, JobCallable]] = []

    def enqueue(self, job_id: int, func: JobCallable) -> None:
        self.jobs.append((job_id, func))

    def run_all(self) -> None:
        for _, func in list(self.jobs):
            func()
        self.jobs.clear()


_queue: JobQueue | None = None
_lock = threading.Lock()


def get_queue() -> JobQueue:
    """Return the active queue, creating the default thread queue on first use."""

    global _queue
    with _lock:
        if _queue is None:
            _queue = ThreadQueue()
        return _queue


def set_queue(queue: JobQueue | None) -> None:
    """Install a queue backend. Passing ``None`` restores the default."""

    global _queue
    with _lock:
        _queue = queue