"""Tests for the Sentinel SDK drift logger (Tier 2 Sprint 5)."""
import json
import os
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from sentinel.sdk import drift_logger


@pytest.fixture(autouse=True)
def _reset_logger():
    drift_logger.reset_for_tests()
    yield
    drift_logger.reset_for_tests()


def test_log_inference_buffers_and_flushes_to_endpoint(tmp_path, monkeypatch):
    """A single batch POST is sent when flush() is called."""
    posted: List[Dict[str, Any]] = []

    class _StubResponse:
        is_success = True
        status_code = 200
        text = "ok"

    class _StubClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None: ...
        def __enter__(self): return self
        def __exit__(self, *args: Any, **kwargs: Any) -> None: ...
        def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any]):
            posted.append({"url": url, "headers": headers, "json": json})
            return _StubResponse()

    drift_logger.configure(
        api_url="http://stub.local",
        api_key="key-1",
        baseline_id="b-1",
        model_id="m-1",
        flush_max_records=1000,
        flush_interval_seconds=999.0,
        fallback_dir=str(tmp_path),
    )

    drift_logger.log_inference(
        features={"age": 65}, prediction=1,
        ground_truth=1, latency_ms=12.0, request_id="r-1",
    )
    drift_logger.log_inference(
        features={"age": 72}, prediction=0,
        ground_truth=0, latency_ms=14.5, request_id="r-2",
    )

    with patch("httpx.Client", _StubClient):
        flushed = drift_logger.flush()

    assert flushed == 2
    assert len(posted) == 1
    payload = posted[0]["json"]
    assert payload["baseline_id"] == "b-1"
    assert payload["model_id"] == "m-1"
    assert len(payload["records"]) == 2
    assert payload["records"][0]["features"] == {"age": 65}
    assert posted[0]["headers"]["X-API-Key"] == "key-1"


def test_log_inference_writes_fallback_when_unconfigured(tmp_path):
    drift_logger.configure(
        api_url="",  # unconfigured
        baseline_id="",
        fallback_dir=str(tmp_path),
    )
    drift_logger.log_inference(features={"x": 1.0}, prediction=1)
    drift_logger.flush()

    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    contents = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert len(contents) == 1
    assert contents[0]["features"] == {"x": 1.0}


def test_log_inference_writes_fallback_when_server_5xx(tmp_path):
    class _Stub5xx:
        is_success = False
        status_code = 500
        text = "internal error"

    class _StubClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None: ...
        def __enter__(self): return self
        def __exit__(self, *args: Any, **kwargs: Any) -> None: ...
        def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any]):
            return _Stub5xx()

    drift_logger.configure(
        api_url="http://stub.local",
        api_key="key-1",
        baseline_id="b-1",
        fallback_dir=str(tmp_path),
    )
    drift_logger.log_inference(features={"x": 1.0}, prediction=1)

    with patch("httpx.Client", _StubClient), \
         patch("sentinel.sdk.drift_logger.time.sleep", return_value=None):
        drift_logger.flush()

    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1


def test_disabled_logger_is_a_noop(tmp_path):
    drift_logger.configure(
        api_url="http://stub.local",
        baseline_id="b-1",
        enabled=False,
        fallback_dir=str(tmp_path),
    )
    drift_logger.log_inference(features={"x": 1.0}, prediction=1)
    flushed = drift_logger.flush()
    assert flushed == 0
    assert list(tmp_path.glob("*.jsonl")) == []


def test_4xx_response_is_terminal_and_writes_fallback(tmp_path):
    class _Stub4xx:
        is_success = False
        status_code = 400
        text = "bad request"

    class _StubClient:
        calls = 0

        def __init__(self, *args: Any, **kwargs: Any) -> None: ...
        def __enter__(self): return self
        def __exit__(self, *args: Any, **kwargs: Any) -> None: ...
        def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any]):
            type(self).calls += 1
            return _Stub4xx()

    drift_logger.configure(
        api_url="http://stub.local",
        baseline_id="b-1",
        fallback_dir=str(tmp_path),
    )
    drift_logger.log_inference(features={"x": 1.0}, prediction=1)

    with patch("httpx.Client", _StubClient):
        drift_logger.flush()

    # 4xx → no retries (single call, then fallback write)
    assert _StubClient.calls == 1
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1


def test_inference_record_payload_shape():
    record = drift_logger.InferenceRecord(
        features={"age": 65}, prediction=1, ground_truth=0,
        latency_ms=12.5, request_id="r-1",
    )
    payload = record.to_payload()
    assert payload["features"] == {"age": 65}
    assert payload["prediction"] == 1
    assert payload["ground_truth"] == 0
    assert payload["latency_ms"] == 12.5
    assert payload["request_id"] == "r-1"
    assert "timestamp" in payload
