"""Regression test for HIGH-015 — Slack alert must not block the event loop.

Before the fix ``SlackService.send_alert`` used the synchronous ``requests``
library with ``time.sleep`` back-off. Called from inside an ``async`` handler
(``trigger_alert`` in ``policy_engine/routes/policy_check.py:199``) it blocked
the uvicorn event loop for up to ``retry_attempts * timeout`` seconds when
Slack was degraded — exactly when alerts mattered most.

The fix offloads the network work to a thread executor when invoked from a
running event loop, so the calling coroutine returns control immediately
(fire-and-forget). Synchronous callers (Celery jobs, scripts) are unaffected.
"""

import asyncio
import time
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from policy_engine.models.alert import Alert, AlertSeverity
from policy_engine.services.slack_service import SlackService


def _make_alert() -> Alert:
    return Alert(
        id=str(uuid4()),
        agent_id="agent-1",
        alert_type="policy_violation",
        severity=AlertSeverity.HIGH.value,
        description="test",
        timestamp=datetime.utcnow(),
        organization_id=None,
    )


def _slow_post(*_args, **_kwargs):  # pragma: no cover - exercised via patch
    """Simulate a degraded Slack endpoint that takes ~0.6s to respond."""
    time.sleep(0.6)
    class _Resp:
        status_code = 200
        text = "ok"
    return _Resp()


def test_sync_caller_still_blocks_and_returns_bool() -> None:
    """Outside an event loop the call is fully synchronous (back-compat)."""
    svc = SlackService("https://hooks.slack.com/test")
    svc.retry_attempts = 1
    with patch("policy_engine.services.slack_service.requests.post", side_effect=_slow_post):
        start = time.monotonic()
        result = svc.send_alert(_make_alert())
        elapsed = time.monotonic() - start
    assert result is True
    assert elapsed >= 0.5, "sync caller should observe the full network latency"


def test_async_caller_does_not_block_event_loop() -> None:
    """Inside a running event loop ``send_alert`` returns fast."""
    svc = SlackService("https://hooks.slack.com/test")
    svc.retry_attempts = 1

    async def _run() -> float:
        with patch(
            "policy_engine.services.slack_service.requests.post",
            side_effect=_slow_post,
        ):
            start = time.monotonic()
            svc.send_alert(_make_alert())
            elapsed = time.monotonic() - start
            # Yield once so the executor-scheduled coroutine can settle without
            # leaking into other tests.
            await asyncio.sleep(0)
        return elapsed

    elapsed = asyncio.run(_run())
    assert elapsed < 0.2, (
        f"async caller blocked for {elapsed:.3f}s — Slack send was not offloaded"
    )
