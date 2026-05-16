"""Regression test for HIGH-016 — fail-safe response must not echo str(exc).

When policy evaluation raises an unexpected exception the handler in
``policy_engine/routes/policy_check.py`` builds a fail-safe response that
blocks the action. The previous implementation embedded ``str(e)`` verbatim
into both ``reason`` and ``metadata['error']`` — leaking ORM column names,
file paths, and even raw connection strings to third-party AI agents that
call ``/v1/policy/check``.

This test asserts the response shape is preserved (decision/policy_ids/
masked_data/metadata.fail_safe still present) but the sensitive substring
is gone. A stable ``error_id`` is exposed so operators can still correlate
with the server-side log line.
"""

from unittest.mock import patch


SECRET_FRAGMENT = "host=internal-db.prod.local user=app password=hunter2"


def _payload(agent_id: str) -> dict:
    return {
        "agent_id": agent_id,
        "tool_name": "safe_tool",
        "arguments": {"param": "value"},
        "user_id": "user-test-001",
        "context": {"agent_name": "Test Agent"},
    }


def test_failsafe_response_does_not_leak_exception_string(authed_client):
    """A raised exception's str() must not appear in the JSON response."""
    client, agent_id = authed_client

    def _boom(self, request):  # noqa: ARG001 - signature match
        raise RuntimeError(SECRET_FRAGMENT)

    with patch(
        "policy_engine.services.policy_evaluation.PolicyEvaluationService.evaluate",
        new=_boom,
    ):
        resp = client.post("/v1/policy/check", json=_payload(agent_id))

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Shape preserved
    assert body["decision"] == "block"
    assert body["policy_ids"] == []
    assert body["masked_data"] is None
    assert body["metadata"]["fail_safe"] is True

    # Sensitive substring must not leak in any returned field
    serialized = repr(body)
    assert SECRET_FRAGMENT not in serialized
    assert "hunter2" not in serialized
    assert "RuntimeError" not in serialized

    # Operator-correlation id must be present so server logs can be matched
    assert "error_id" in body["metadata"]
    assert isinstance(body["metadata"]["error_id"], str)
    assert len(body["metadata"]["error_id"]) >= 8
