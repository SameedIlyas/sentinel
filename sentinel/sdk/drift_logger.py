"""Sentinel SDK: client-side drift logger.

Tier 2 Sprint 5 — let inference servers log every prediction with its
features and outcome, so the Sentinel platform can compute PSI / KS / FPR
drift continuously instead of waiting for a manual `POST /drift/measure`.

Usage:
    from sentinel.sdk import drift_logger

    drift_logger.configure(
        api_url="https://sentinel.example.com",
        api_key="sk_...",
        baseline_id="db_abc123",
    )

    drift_logger.log_inference(
        features={"age": 67, "wbc": 12.4, "creatinine": 1.6},
        prediction=1,
        ground_truth=None,             # filled later when the label arrives
        latency_ms=14.0,
        request_id="req-9c1ad03",
    )

The logger batches in memory (default 1000 records or 60 seconds, whichever
comes first) and POSTs them to /v1/clinical/drift/log-batch. Failures are
retried up to 3 times with backoff; persistent failures fall back to a
ring-buffered file under /tmp/sentinel-drift-buffer/ for offline replay.

Pure stdlib + httpx (already a project dependency). No new heavy deps.
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inference-record dataclass
# ---------------------------------------------------------------------------

@dataclass
class InferenceRecord:
    """One model inference, ready for batch POST."""
    features: Dict[str, Any]
    prediction: Any
    ground_truth: Optional[Any] = None
    latency_ms: Optional[float] = None
    request_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_payload(self) -> Dict[str, Any]:
        return {
            "features": self.features,
            "prediction": self.prediction,
            "ground_truth": self.ground_truth,
            "latency_ms": self.latency_ms,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class DriftLoggerConfig:
    api_url: str = ""
    api_key: str = ""
    baseline_id: str = ""
    model_id: str = ""
    flush_max_records: int = 1000
    flush_interval_seconds: float = 60.0
    request_timeout_seconds: float = 5.0
    fallback_dir: str = ""
    enabled: bool = True


# ---------------------------------------------------------------------------
# Batcher — single global instance per process, lazy started
# ---------------------------------------------------------------------------

class _DriftBatcher:
    def __init__(self, config: DriftLoggerConfig) -> None:
        self._config = config
        self._queue: Queue = Queue()
        self._buffer: List[InferenceRecord] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_flush = time.monotonic()

        # Track post outcomes for tests / ops dashboards
        self.posted_count = 0
        self.failed_count = 0
        self.fallback_count = 0

    @property
    def config(self) -> DriftLoggerConfig:
        return self._config

    def update_config(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

    def submit(self, record: InferenceRecord) -> None:
        if not self._config.enabled:
            return
        if self._thread is None:
            self._start()
        self._queue.put(record)

    def flush(self, *, blocking: bool = True) -> int:
        """Drain the queue and POST any pending records. Returns count flushed."""
        with self._lock:
            self._buffer.extend(self._drain_queue())
            count = len(self._buffer)
            if not count:
                return 0
            sent = self._post_batch(self._buffer)
            self._buffer = [] if sent else self._buffer
            self._last_flush = time.monotonic()
            return count if sent else 0

    def shutdown(self) -> None:
        """Stop the background thread and flush remaining records."""
        if self._thread is None:
            return
        self._stop.set()
        try:
            self.flush()
        except Exception:
            logger.warning("drift_logger flush during shutdown failed", exc_info=True)
        self._thread.join(timeout=5.0)
        self._thread = None

    # ── private ────────────────────────────────────────────────────────────

    def _start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="sentinel-drift-logger", daemon=True,
        )
        self._thread.start()
        atexit.register(self.shutdown)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                record = self._queue.get(timeout=1.0)
                with self._lock:
                    self._buffer.append(record)
            except Empty:
                pass

            now = time.monotonic()
            buffer_full = len(self._buffer) >= self._config.flush_max_records
            time_due = (
                (now - self._last_flush) >= self._config.flush_interval_seconds
                and self._buffer
            )
            if buffer_full or time_due:
                try:
                    with self._lock:
                        self._buffer.extend(self._drain_queue())
                        if self._buffer:
                            sent = self._post_batch(self._buffer)
                            if sent:
                                self._buffer = []
                            self._last_flush = now
                except Exception:
                    logger.error("drift_logger loop error", exc_info=True)

    def _drain_queue(self) -> List[InferenceRecord]:
        records: List[InferenceRecord] = []
        while True:
            try:
                records.append(self._queue.get_nowait())
            except Empty:
                break
        return records

    def _post_batch(self, records: List[InferenceRecord]) -> bool:
        """POST batch to server. Returns True on success, False (and writes
        fallback) on failure."""
        if not (self._config.api_url and self._config.baseline_id):
            logger.debug(
                "drift_logger not fully configured; falling back to disk "
                "(records=%d)", len(records),
            )
            return self._write_fallback(records)

        try:
            import httpx  # local import — sentinel SDK doesn't otherwise need httpx
        except ImportError:
            return self._write_fallback(records)

        url = self._config.api_url.rstrip("/") + "/v1/clinical/drift/log-batch"
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["X-API-Key"] = self._config.api_key
        payload = {
            "baseline_id": self._config.baseline_id,
            "model_id": self._config.model_id or None,
            "records": [r.to_payload() for r in records],
        }

        for attempt in range(3):
            try:
                with httpx.Client(timeout=self._config.request_timeout_seconds) as client:
                    resp = client.post(url, headers=headers, json=payload)
                if resp.is_success:
                    self.posted_count += len(records)
                    return True
                # 4xx → don't retry (bad request)
                if 400 <= resp.status_code < 500:
                    logger.warning(
                        "drift_logger server rejected batch: %s %s",
                        resp.status_code, resp.text[:200],
                    )
                    self.failed_count += len(records)
                    self._write_fallback(records)
                    return False
            except Exception as exc:
                logger.warning("drift_logger POST attempt %d failed: %s", attempt + 1, exc)
            time.sleep(min(2 ** attempt, 5.0))

        self.failed_count += len(records)
        self._write_fallback(records)
        return False

    def _write_fallback(self, records: List[InferenceRecord]) -> bool:
        """Persist records to disk so they're not lost when the server is unreachable."""
        path = self._config.fallback_dir or os.path.join(
            os.path.expanduser("~"), ".sentinel", "drift_buffer"
        )
        try:
            os.makedirs(path, exist_ok=True)
            file_path = os.path.join(
                path, f"drift-batch-{uuid.uuid4().hex}.jsonl"
            )
            with open(file_path, "w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r.to_payload()) + "\n")
            self.fallback_count += len(records)
            logger.info("drift_logger wrote %d records to %s", len(records), file_path)
            return True
        except Exception as exc:
            logger.error("drift_logger fallback write failed: %s", exc)
            self.failed_count += len(records)
            return False


# ---------------------------------------------------------------------------
# Module-level convenience API — single global batcher
# ---------------------------------------------------------------------------

_batcher: Optional[_DriftBatcher] = None
_batcher_lock = threading.Lock()


def _get_batcher() -> _DriftBatcher:
    global _batcher
    with _batcher_lock:
        if _batcher is None:
            _batcher = _DriftBatcher(DriftLoggerConfig())
    return _batcher


def configure(
    *,
    api_url: str = "",
    api_key: str = "",
    baseline_id: str = "",
    model_id: str = "",
    flush_max_records: int = 1000,
    flush_interval_seconds: float = 60.0,
    request_timeout_seconds: float = 5.0,
    fallback_dir: str = "",
    enabled: bool = True,
) -> None:
    """Configure the global drift logger.

    Call once at startup, or pass `api_url=""` to disable.
    """
    _get_batcher().update_config(
        api_url=api_url,
        api_key=api_key,
        baseline_id=baseline_id,
        model_id=model_id,
        flush_max_records=flush_max_records,
        flush_interval_seconds=flush_interval_seconds,
        request_timeout_seconds=request_timeout_seconds,
        fallback_dir=fallback_dir,
        enabled=enabled,
    )


def log_inference(
    *,
    features: Dict[str, Any],
    prediction: Any,
    ground_truth: Optional[Any] = None,
    latency_ms: Optional[float] = None,
    request_id: Optional[str] = None,
) -> None:
    """Submit one inference record. Non-blocking; batched server-side."""
    record = InferenceRecord(
        features=features,
        prediction=prediction,
        ground_truth=ground_truth,
        latency_ms=latency_ms,
        request_id=request_id,
    )
    _get_batcher().submit(record)


def flush() -> int:
    """Force-flush any buffered records. Returns the number flushed."""
    return _get_batcher().flush()


def shutdown() -> None:
    """Tear down the background batcher. Idempotent. Called atexit by default."""
    _get_batcher().shutdown()


def reset_for_tests() -> None:
    """Test-only helper to reset the global batcher between tests."""
    global _batcher
    with _batcher_lock:
        if _batcher is not None:
            _batcher.shutdown()
        _batcher = None
