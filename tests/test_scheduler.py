"""Tests for the in-process scheduler used by Sprint 2 jobs."""
import asyncio

import pytest

from policy_engine.services.scheduler import Scheduler, reset_scheduler_for_tests


@pytest.fixture(autouse=True)
def _reset_scheduler():
    reset_scheduler_for_tests()
    yield
    reset_scheduler_for_tests()


@pytest.mark.asyncio
async def test_scheduler_runs_async_job_on_interval():
    counter = {"runs": 0}

    async def job():
        counter["runs"] += 1

    s = Scheduler()
    s.register("tick", interval_seconds=0.05, func=job, initial_delay_seconds=0.0)
    s.start()
    await asyncio.sleep(0.18)
    await s.stop()

    # At least 2 runs in 0.18s with 0.05s interval
    assert counter["runs"] >= 2


@pytest.mark.asyncio
async def test_scheduler_runs_sync_job_in_thread_pool():
    counter = {"runs": 0}

    def job():
        counter["runs"] += 1

    s = Scheduler()
    s.register("tick", interval_seconds=0.05, func=job)
    s.start()
    await asyncio.sleep(0.12)
    await s.stop()

    assert counter["runs"] >= 1


@pytest.mark.asyncio
async def test_scheduler_swallows_exceptions_and_continues():
    counter = {"runs": 0, "errors": 0}

    async def flaky_job():
        counter["runs"] += 1
        if counter["runs"] == 1:
            counter["errors"] += 1
            raise RuntimeError("boom")

    s = Scheduler()
    spec = s.register("flaky", interval_seconds=0.05, func=flaky_job)
    s.start()
    await asyncio.sleep(0.18)
    await s.stop()

    assert counter["runs"] >= 2  # ran again after the exception
    assert spec.error_count >= 1
    assert spec.last_error is None or spec.run_count > spec.error_count


@pytest.mark.asyncio
async def test_scheduler_stop_is_idempotent():
    s = Scheduler()
    await s.stop()  # not started → no-op

    s.register("noop", interval_seconds=10.0, func=lambda: None)
    s.start()
    await s.stop()
    await s.stop()  # second stop must not raise


@pytest.mark.asyncio
async def test_scheduler_disabled_jobs_do_not_run():
    counter = {"runs": 0}

    def job():
        counter["runs"] += 1

    s = Scheduler()
    s.register(
        "disabled", interval_seconds=0.01, func=job, enabled=False
    )
    s.start()
    await asyncio.sleep(0.05)
    await s.stop()

    assert counter["runs"] == 0


@pytest.mark.asyncio
async def test_scheduler_rejects_duplicate_registration():
    s = Scheduler()
    s.register("foo", 1.0, lambda: None)
    with pytest.raises(ValueError):
        s.register("foo", 1.0, lambda: None)


@pytest.mark.asyncio
async def test_scheduler_rejects_non_positive_interval():
    s = Scheduler()
    with pytest.raises(ValueError):
        s.register("foo", 0.0, lambda: None)
