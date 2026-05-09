"""Tests for the Sentinel SDK shadow-AI self-reporter (Tier 3 Path C)."""
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from sentinel.sdk import shadow_ai as sdk_shadow


@pytest.fixture(autouse=True)
def _reset():
    sdk_shadow.reset_for_tests()
    yield
    sdk_shadow.reset_for_tests()


def test_split_host_and_port_url():
    host, port = sdk_shadow._split_host_and_port("https://api.openai.com/v1/chat")
    assert host == "api.openai.com"
    assert port == 443


def test_split_host_and_port_bare():
    host, port = sdk_shadow._split_host_and_port("api.openai.com")
    assert host == "api.openai.com"
    assert port == 443


def test_split_host_and_port_with_port():
    host, port = sdk_shadow._split_host_and_port("api.openai.com:8443")
    assert host == "api.openai.com"
    assert port == 8443


def test_split_host_and_port_empty():
    host, port = sdk_shadow._split_host_and_port("")
    assert host == ""
    assert port == 443


def test_is_provider_allowed_uses_lowercase():
    sdk_shadow.configure(allowed_providers={"OpenAI", "anthropic"})
    assert sdk_shadow.is_provider_allowed("openai") is True
    assert sdk_shadow.is_provider_allowed("OpenAI") is True
    assert sdk_shadow.is_provider_allowed("ANTHROPIC") is True
    assert sdk_shadow.is_provider_allowed("mistral") is False


def test_report_skips_when_provider_allowlisted():
    sdk_shadow.configure(
        api_url="http://stub.local",
        api_key="key",
        allowed_providers={"openai"},
    )
    posted = sdk_shadow.report_provider_call(
        provider_name="openai",
        endpoint="https://api.openai.com/v1/chat",
    )
    assert posted is False
    assert sdk_shadow._get_reporter().skipped_allowlisted == 1


def test_report_skips_when_not_configured():
    sdk_shadow.configure(
        api_url="",  # not configured
        allowed_providers=set(),
    )
    posted = sdk_shadow.report_provider_call(
        provider_name="mistral",
        endpoint="https://api.mistral.ai/v1/chat",
    )
    assert posted is False


def test_report_posts_when_provider_not_allowlisted():
    posted_calls: List[Dict[str, Any]] = []

    class _StubResponse:
        is_success = True
        status_code = 200
        text = "ok"

    class _StubClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None: ...
        def __enter__(self): return self
        def __exit__(self, *args: Any, **kwargs: Any) -> None: ...
        def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any]):
            posted_calls.append({"url": url, "headers": headers, "json": json})
            return _StubResponse()

    sdk_shadow.configure(
        api_url="http://stub.local",
        api_key="sk-1",
        allowed_providers={"openai"},
        department="ICU",
    )

    with patch("httpx.Client", _StubClient):
        posted = sdk_shadow.report_provider_call(
            provider_name="mistral",
            endpoint="https://api.mistral.ai/v1/chat",
            method="POST",
            user_agent="python-requests/2.31",
            bytes_transferred=2048,
        )

    assert posted is True
    assert len(posted_calls) == 1
    payload = posted_calls[0]["json"]
    assert payload["records"][0]["destination_host"] == "api.mistral.ai"
    assert payload["records"][0]["department"] == "ICU"
    assert posted_calls[0]["headers"]["X-API-Key"] == "sk-1"


def test_report_dedups_within_window():
    posted_calls: List[Any] = []

    class _StubResponse:
        is_success = True
        status_code = 200

    class _StubClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None: ...
        def __enter__(self): return self
        def __exit__(self, *args: Any, **kwargs: Any) -> None: ...
        def post(self, *args: Any, **kwargs: Any):
            posted_calls.append(kwargs.get("json"))
            return _StubResponse()

    sdk_shadow.configure(
        api_url="http://stub.local",
        api_key="sk-1",
        allowed_providers=set(),
        dedup_window_seconds=60.0,
    )

    with patch("httpx.Client", _StubClient):
        first = sdk_shadow.report_provider_call(
            provider_name="mistral",
            endpoint="https://api.mistral.ai/v1/chat",
        )
        second = sdk_shadow.report_provider_call(
            provider_name="mistral",
            endpoint="https://api.mistral.ai/v1/chat",
        )

    assert first is True
    assert second is False
    assert len(posted_calls) == 1
    assert sdk_shadow._get_reporter().skipped_dedup == 1


def test_disabled_logger_is_noop():
    posted_calls: List[Any] = []

    class _StubClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None: ...
        def __enter__(self): return self
        def __exit__(self, *args: Any, **kwargs: Any) -> None: ...
        def post(self, *args: Any, **kwargs: Any):
            posted_calls.append(kwargs.get("json"))
            class R:
                is_success = True
                status_code = 200
            return R()

    sdk_shadow.configure(
        api_url="http://stub.local",
        api_key="sk-1",
        allowed_providers=set(),
        enabled=False,
    )
    with patch("httpx.Client", _StubClient):
        result = sdk_shadow.report_provider_call(
            provider_name="mistral",
            endpoint="https://api.mistral.ai/v1/chat",
        )
    assert result is False
    assert posted_calls == []


def test_report_handles_server_5xx():
    class _Stub5xx:
        is_success = False
        status_code = 503
        text = "service unavailable"

    class _StubClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None: ...
        def __enter__(self): return self
        def __exit__(self, *args: Any, **kwargs: Any) -> None: ...
        def post(self, *args: Any, **kwargs: Any):
            return _Stub5xx()

    sdk_shadow.configure(
        api_url="http://stub.local",
        api_key="sk-1",
        allowed_providers=set(),
    )
    with patch("httpx.Client", _StubClient):
        result = sdk_shadow.report_provider_call(
            provider_name="mistral",
            endpoint="https://api.mistral.ai/v1/chat",
        )
    assert result is False
    assert sdk_shadow._get_reporter().failed_count == 1
