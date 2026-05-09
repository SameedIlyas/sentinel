"""Lightweight in-process scheduler for periodic background jobs.

Tier 2 Sprint 2 — replaces "must POST manually" pages with continuous
auto-ingestion. Implemented in pure asyncio to avoid pulling APScheduler
into the dependency tree just for two jobs.

Design:
  - A scheduler is a registry of `JobSpec` records, each with a callable and
    an interval (seconds). The callable can be sync or async; sync ones are
    offloaded to the default thread pool so they don't block the event loop.
  - `Scheduler.start()` spawns one supervisor coroutine that fans out to
    one looper-coroutine per job. Each looper sleeps `interval` seconds,
    runs the job, logs failures, and never propagates exceptions.
  - `Scheduler.stop()` cancels all tasks. Idempotent.
  - The first run of each job is delayed by `initial_delay_seconds` (default
    a small per-job stagger so concurrent first-runs don't thrash a cold
    process at startup).

This isn't durable across restarts — for the Tier 2 use cases (poll MLflow,
recompute risk scores nightly) that's fine. Durable delivery is a Tier 3
concern.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


JobCallable = Union[Callable[[], None], Callable[[], Awaitable[None]]]


@dataclass
class JobSpec:
    """A single scheduled job."""
    name: str
    interval_seconds: float
    func: JobCallable
    initial_delay_seconds: float = 0.0
    enabled: bool = True

    last_run_at: Optional[float] = field(default=None, init=False)
    last_error: Optional[str] = field(default=None, init=False)
    run_count: int = field(default=0, init=False)
    error_count: int = field(default=0, init=False)


class Scheduler:
    """Drop-in periodic-job scheduler. Single instance per process."""

    def __init__(self) -> None:
        self._jobs: Dict[str, JobSpec] = {}
        self._tasks: List[asyncio.Task] = []
        self._stopping = asyncio.Event()
        self._started = False

    def register(
        self,
        name: str,
        interval_seconds: float,
        func: JobCallable,
        *,
        initial_delay_seconds: float = 0.0,
        enabled: bool = True,
    ) -> JobSpec:
        """Register a job. May be called before or after start()."""
        if name in self._jobs:
            raise ValueError(f"Job already registered: {name}")
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")

        spec = JobSpec(
            name=name,
            interval_seconds=interval_seconds,
            func=func,
            initial_delay_seconds=max(0.0, initial_delay_seconds),
            enabled=enabled,
        )
        self._jobs[name] = spec

        if self._started and enabled:
            self._tasks.append(asyncio.create_task(self._run_loop(spec)))

        logger.info(
            "Scheduled job registered: name=%s interval=%ss enabled=%s",
            name, interval_seconds, enabled,
        )
        return spec

    def unregister(self, name: str) -> None:
        self._jobs.pop(name, None)

    def list_jobs(self) -> List[JobSpec]:
        return list(self._jobs.values())

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._stopping.clear()
        for spec in self._jobs.values():
            if spec.enabled:
                self._tasks.append(asyncio.create_task(self._run_loop(spec)))
        logger.info("Scheduler started with %d jobs", len(self._tasks))

    async def stop(self) -> None:
        if not self._started:
            return
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        # Drain so we don't leave dangling tasks
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()
        self._started = False
        logger.info("Scheduler stopped")

    async def _run_loop(self, spec: JobSpec) -> None:
        """Run a single job on its interval until cancelled."""
        if spec.initial_delay_seconds > 0:
            try:
                await asyncio.wait_for(
                    self._stopping.wait(),
                    timeout=spec.initial_delay_seconds,
                )
                return  # stopping
            except asyncio.TimeoutError:
                pass  # initial delay elapsed — fall through to first run

        while not self._stopping.is_set():
            await self._invoke_once(spec)
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=spec.interval_seconds
                )
                return  # stopping
            except asyncio.TimeoutError:
                continue  # interval elapsed — run again

    async def _invoke_once(self, spec: JobSpec) -> None:
        """Run the job exactly once. Never raises."""
        try:
            spec.last_run_at = time.time()
            spec.run_count += 1
            if inspect.iscoroutinefunction(spec.func):
                await spec.func()
            else:
                await asyncio.get_running_loop().run_in_executor(None, spec.func)
            spec.last_error = None
            logger.debug("Scheduled job completed: name=%s", spec.name)
        except Exception as exc:
            spec.error_count += 1
            spec.last_error = str(exc)
            logger.error(
                "Scheduled job %s failed: %s", spec.name, exc, exc_info=True
            )


# ---------------------------------------------------------------------------
# Module-level singleton — one scheduler per process
# ---------------------------------------------------------------------------

_default_scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    global _default_scheduler
    if _default_scheduler is None:
        _default_scheduler = Scheduler()
    return _default_scheduler


def reset_scheduler_for_tests() -> None:
    """Force-recreate the default scheduler. Test-only — never call in prod."""
    global _default_scheduler
    _default_scheduler = Scheduler()
