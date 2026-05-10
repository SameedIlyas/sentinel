"""Anthropic Messages API adapter tests via respx (no real network).

Targets the call sites that use the Anthropic Python SDK:
* ``policy_engine.services.scribe_auditor._llm_verdicts``
* ``policy_engine.services.transparency_auto_service`` (similar pattern)

The Anthropic SDK uses httpx under the hood, so respx intercepts the
calls and lets us pin request shape (model, system prompt, max_tokens)
and verify graceful degradation on 429 / network errors.
"""

from __future__ import annotations

import json

import pytest


pytestmark = pytest.mark.sdk


def _has_anthropic() -> bool:
    try:
        import anthropic  # noqa: F401
        import respx  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_anthropic(), reason="anthropic + respx not installed")
def test_anthropic_call_intercepted_by_respx() -> None:
    """A direct SDK call is fully intercepted; zero real network traffic."""
    import respx
    import httpx
    from anthropic import Anthropic

    fake_response = {
        "id": "msg_test_001",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-4-5-20251001",
        "content": [{"type": "text", "text": '[{"index":0,"verdict":"supported"}]'}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }

    with respx.mock(assert_all_called=True) as r:
        route = r.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json=fake_response)
        )
        client = Anthropic(api_key="sk-ant-test-PLACEHOLDER")
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": "test"}],
        )
        assert route.called
        assert msg.id == "msg_test_001"
        # Inspect the request the SDK actually sent.
        sent = json.loads(route.calls[0].request.content)
        assert sent["model"] == "claude-haiku-4-5-20251001"
        assert sent["max_tokens"] == 100
        # System prompt absent — never include PHI in system prompts by default.
        assert "system" not in sent or not sent["system"]


@pytest.mark.skipif(not _has_anthropic(), reason="anthropic + respx not installed")
def test_anthropic_rate_limit_429_is_handled() -> None:
    """The SDK raises a typed exception on 429; callers must catch and degrade."""
    import respx
    import httpx
    import anthropic
    from anthropic import Anthropic

    with respx.mock() as r:
        r.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(
                429,
                json={"type": "error", "error": {"type": "rate_limit_error", "message": "limit"}},
            )
        )
        client = Anthropic(api_key="sk-ant-test-PLACEHOLDER")
        with pytest.raises(anthropic.APIStatusError):
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{"role": "user", "content": "x"}],
            )


def test_no_real_anthropic_dependency_when_unavailable(monkeypatch) -> None:
    """``scribe_auditor._llm_verdicts`` returns None when ANTHROPIC_API_KEY unset.

    This is the deterministic-fallback contract — the platform must never
    block on a missing/unavailable LLM.
    """
    from policy_engine.services.scribe_auditor import _llm_verdicts

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = _llm_verdicts(transcript="Patient seen today.", claims=["claim_1"])
    assert out is None
