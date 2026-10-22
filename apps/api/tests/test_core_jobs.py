"""Tests for the replaceable job queue.

The queue is behind a protocol so a Celery backend can replace it. What
matters here is that installing a backend is enough to change how jobs run, and
that a failing job never takes the worker down with it.
"""

from __future__ import annotations

from app.core import jobs


def test_the_inline_queue_runs_the_job_immediately() -> None:
    """The inline backend executes on the calling thread, so nothing races."""
    queue = jobs.InlineQueue()
    calls: list[int] = []

    queue.enqueue(1, lambda: calls.append(1))

    assert calls == [1]


def test_the_recording_queue_does_not_run_the_job() -> None:
    """The recording backend captures the submission for later."""
    queue = jobs.RecordingQueue()
    calls: list[int] = []

    queue.enqueue(7, lambda: calls.append(7))

    assert calls == []
    assert [job_id for job_id, _ in queue.jobs] == [7]


def test_running_the_recorded_jobs_executes_them() -> None:
    """``run_all`` executes what was captured and clears the queue."""
    queue = jobs.RecordingQueue()
    calls: list[int] = []
    queue.enqueue(1, lambda: calls.append(1))
    queue.enqueue(2, lambda: calls.append(2))

    queue.run_all()

    assert calls == [1, 2]
    assert queue.jobs == []


def test_a_failing_inline_job_does_not_propagate() -> None:
    """A job that raises is logged and contained, not raised at the caller."""
    queue = jobs.InlineQueue()

    def boom() -> None:
        raise RuntimeError("job exploded")

    queue.enqueue(1, boom)


def test_the_default_queue_is_installed_on_first_use() -> None:
    """Asking for a queue when none is installed creates the default."""
    jobs.set_queue(None)
    try:
        assert isinstance(jobs.get_queue(), jobs.ThreadQueue)
    finally:
        jobs.set_queue(None)


def test_an_installed_queue_is_the_one_returned() -> None:
    """Installing a backend is enough to change how jobs run."""
    queue = jobs.RecordingQueue()
    jobs.set_queue(queue)
    try:
        assert jobs.get_queue() is queue
    finally:
        jobs.set_queue(None)
