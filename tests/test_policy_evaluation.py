"""Phase 2 — Test Coverage Retrofit: Policy Evaluation Pipeline.

Covers: routes/policy_check.py, services/policy_evaluation.py,
        services/alert_service.py (basic wiring), models/audit_log.py
"""
import uuid
from unittest.mock import patch


from policy_engine.models.alert import Alert
from policy_engine.models.audit_log import AuditLog
from policy_engine.models.policy import Policy, PolicyType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_access_policy(db_session, *, agent_id="*", blocked_tool="dangerous_tool",
                        policy_id=None) -> Policy:
    """Create and persist an ACCESS_CONTROL policy that blocks blocked_tool."""
    pid = policy_id or str(uuid.uuid4())
    policy = Policy(
        id=pid,
        name="Block Dangerous Tools",
        description="Blocks dangerous tool calls",
        policy_type=PolicyType.ACCESS_CONTROL,
        rules=[{
            "conditions": [{"field": "tool_name", "operator": "eq", "value": blocked_tool}],
            "action": "block",
            "description": "Block dangerous tools",
        }],
        applies_to=[agent_id],
        priority=10,
        enabled=True,
        created_by="admin",
    )
    db_session.add(policy)
    db_session.commit()
    return policy


def _make_allow_policy(db_session, *, agent_id="*", policy_id=None) -> Policy:
    """Create and persist an ACCESS_CONTROL policy that allows everything."""
    pid = policy_id or str(uuid.uuid4())
    policy = Policy(
        id=pid,
        name="Allow All",
        description="Allows all tool calls",
        policy_type=PolicyType.ACCESS_CONTROL,
        rules=[{
            "conditions": [{"field": "tool_name", "operator": "contains", "value": "safe"}],
            "action": "allow",
            "description": "Allow safe tools",
        }],
        applies_to=[agent_id],
        priority=1,
        enabled=True,
        created_by="admin",
    )
    db_session.add(policy)
    db_session.commit()
    return policy


def _policy_check_payload(agent_id: str, tool_name: str, **kwargs) -> dict:
    return {
        "agent_id": agent_id,
        "tool_name": tool_name,
        "arguments": kwargs.get("arguments", {"param": "value"}),
        "user_id": kwargs.get("user_id", "user-test-001"),
        "context": kwargs.get("context", {"agent_name": "Test Agent"}),
    }


# ---------------------------------------------------------------------------
# Task 2.2: Policy Check endpoint — authentication
# ---------------------------------------------------------------------------

def test_policy_check_requires_valid_api_key(client):
    """POST /v1/policy/check returns 4xx when no API key is provided."""
    resp = client.post(
        "/v1/policy/check",
        json=_policy_check_payload("some-agent", "read_file"),
    )
    assert resp.status_code in (401, 403, 422)


def test_policy_check_rejects_invalid_api_key(client):
    """POST /v1/policy/check returns 401 for a non-existent API key."""
    resp = client.post(
        "/v1/policy/check",
        json=_policy_check_payload("some-agent", "read_file"),
        headers={"X-API-Key": "not-a-real-key"},
    )
    assert resp.status_code == 401


def test_policy_check_rejects_mismatched_agent_id(authed_client):
    """Request agent_id that doesn't match the key's agent_id → 403."""
    c, _ = authed_client
    resp = c.post(
        "/v1/policy/check",
        json=_policy_check_payload("wrong-agent-id", "read_file"),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Task 2.2: Allow decision path
# ---------------------------------------------------------------------------

def test_allow_decision_with_no_policies(authed_client, db_session):
    """With no policies, every request is allowed by default."""
    c, agent_id = authed_client
    resp = c.post(
        "/v1/policy/check",
        json=_policy_check_payload(agent_id, "safe_read_file"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "allow"


def test_allow_decision_creates_audit_log(authed_client, db_session):
    """An allow decision must produce an AuditLog row."""
    c, agent_id = authed_client
    c.post(
        "/v1/policy/check",
        json=_policy_check_payload(agent_id, "safe_operation"),
    )
    log = db_session.query(AuditLog).filter(AuditLog.agent_id == agent_id).first()
    assert log is not None
    assert log.tool_name == "safe_operation"
    assert log.decision == "allowed"


# ---------------------------------------------------------------------------
# Task 2.2: Block decision path
# ---------------------------------------------------------------------------

def test_block_decision_when_policy_blocks_tool(authed_client, db_session):
    """A matching block policy returns decision=block."""
    c, agent_id = authed_client
    _make_access_policy(db_session, agent_id=agent_id, blocked_tool="dangerous_tool")

    resp = c.post(
        "/v1/policy/check",
        json=_policy_check_payload(agent_id, "dangerous_tool"),
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] == "block"


def test_block_decision_creates_audit_log(authed_client, db_session):
    """A block decision must produce an AuditLog with decision=blocked."""
    c, agent_id = authed_client
    _make_access_policy(db_session, agent_id=agent_id, blocked_tool="forbidden_tool")

    c.post(
        "/v1/policy/check",
        json=_policy_check_payload(agent_id, "forbidden_tool"),
    )
    log = db_session.query(AuditLog).filter(
        AuditLog.agent_id == agent_id,
        AuditLog.tool_name == "forbidden_tool",
    ).first()
    assert log is not None
    assert log.decision == "blocked"


def test_block_decision_triggers_alert(authed_client, db_session):
    """A block decision must create an Alert row in the database."""
    c, agent_id = authed_client
    _make_access_policy(db_session, agent_id=agent_id, blocked_tool="alert_trigger_tool")

    c.post(
        "/v1/policy/check",
        json=_policy_check_payload(agent_id, "alert_trigger_tool"),
    )
    alert = db_session.query(Alert).filter(Alert.agent_id == agent_id).first()
    assert alert is not None


def test_allow_decision_does_not_trigger_alert(authed_client, db_session):
    """An allow decision must NOT create a policy-violation Alert.

    Note: the first request auto-registers the agent (is_new_agent=True) which
    creates a 'new_agent' alert. The second request is the one we actually
    assert against — it must produce no additional policy-violation alert.
    """
    c, agent_id = authed_client
    # Warm up — registers agent, generates the new_agent alert
    c.post("/v1/policy/check", json=_policy_check_payload(agent_id, "warm_up"))
    # Count alerts after warm-up
    baseline = db_session.query(Alert).filter(Alert.agent_id == agent_id).count()

    # Second allow request — must not create any new alerts
    c.post("/v1/policy/check", json=_policy_check_payload(agent_id, "safe_tool"))
    after = db_session.query(Alert).filter(Alert.agent_id == agent_id).count()
    assert after == baseline, "Allow decision must not produce additional alerts"


# ---------------------------------------------------------------------------
# Task 2.2: Batch check
# ---------------------------------------------------------------------------

def test_batch_check_returns_list_of_responses(authed_client, db_session):
    """POST /v1/policy/check/batch returns a list of decisions."""
    c, agent_id = authed_client
    resp = c.post(
        "/v1/policy/check/batch",
        json=[
            _policy_check_payload(agent_id, "safe_op_1"),
            _policy_check_payload(agent_id, "safe_op_2"),
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2


def test_batch_check_respects_max_batch_size(authed_client):
    """Batch requests larger than 100 are rejected with 400."""
    c, agent_id = authed_client
    requests = [_policy_check_payload(agent_id, f"tool_{i}") for i in range(101)]
    resp = c.post("/v1/policy/check/batch", json=requests)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Task 2.2: Fail-safe on evaluation error
# ---------------------------------------------------------------------------

def test_fail_safe_returns_block_on_evaluation_error(authed_client):
    """If policy evaluation raises an exception, the response is still block."""
    c, agent_id = authed_client

    with patch(
        "policy_engine.routes.policy_check.PolicyEvaluationService.evaluate",
        side_effect=RuntimeError("simulated crash"),
    ):
        resp = c.post(
            "/v1/policy/check",
            json=_policy_check_payload(agent_id, "any_tool"),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "block"
    assert body.get("metadata", {}).get("fail_safe") is True


# ---------------------------------------------------------------------------
# Task 2.2: Alert deduplication
# ---------------------------------------------------------------------------

def test_alert_deduplication_within_5_minute_window(authed_client, db_session):
    """Two identical block events within 5 min should produce only ONE blocked_access Alert.

    The first request also triggers a new_agent alert (agent auto-registration).
    We filter to blocked_access type only to isolate the deduplication behaviour.
    """
    c, agent_id = authed_client
    _make_access_policy(db_session, agent_id=agent_id, blocked_tool="dup_tool")

    payload = _policy_check_payload(agent_id, "dup_tool")
    c.post("/v1/policy/check", json=payload)
    c.post("/v1/policy/check", json=payload)

    from policy_engine.models.alert import Alert as AlertModel
    block_alerts = (
        db_session.query(AlertModel)
        .filter(
            AlertModel.agent_id == agent_id,
            AlertModel.alert_type == "blocked_access",
        )
        .all()
    )
    assert len(block_alerts) == 1, "blocked_access alert must be deduplicated within 5-min window"


# ---------------------------------------------------------------------------
# Task 2.2: Slack integration (mocked)
# ---------------------------------------------------------------------------

def test_slack_notification_not_sent_when_no_webhook(authed_client, db_session, mock_slack):
    """Without a configured webhook, requests.post must NOT be called."""
    c, agent_id = authed_client
    _make_access_policy(db_session, agent_id=agent_id, blocked_tool="slack_test_tool")

    c.post(
        "/v1/policy/check",
        json=_policy_check_payload(agent_id, "slack_test_tool"),
    )
    mock_slack.assert_not_called()


# ---------------------------------------------------------------------------
# Task 2.2: Access control evaluator — tool matching
# ---------------------------------------------------------------------------

def test_access_control_evaluator_blocks_disallowed_tool(authed_client, db_session):
    """Evaluator blocks a tool that matches a block rule."""
    c, agent_id = authed_client
    _make_access_policy(db_session, agent_id=agent_id, blocked_tool="drop_table")

    resp = c.post(
        "/v1/policy/check",
        json=_policy_check_payload(agent_id, "drop_table"),
    )
    assert resp.json()["decision"] == "block"


def test_access_control_evaluator_allows_unmatched_tool(authed_client, db_session):
    """Evaluator allows a tool that does not match any block rule."""
    c, agent_id = authed_client
    _make_access_policy(db_session, agent_id=agent_id, blocked_tool="only_this_tool")

    resp = c.post(
        "/v1/policy/check",
        json=_policy_check_payload(agent_id, "completely_different_tool"),
    )
    assert resp.json()["decision"] == "allow"


# ---------------------------------------------------------------------------
# Task 2.2: PolicyEvaluationService cache methods
# ---------------------------------------------------------------------------


from policy_engine.services.policy_evaluation import PolicyEvaluationService
from policy_engine.models.schemas import PolicyCheckResponse


def _make_eval_service(db_session):
    """Create a PolicyEvaluationService with a disconnected Redis (forces fallback cache)."""
    svc = PolicyEvaluationService(db_session)
    svc.cache.redis = None  # force is_connected() → False
    return svc


def _make_check_response(decision="allow"):
    return PolicyCheckResponse(
        decision=decision,
        reason="test",
        masked_data=None,
        policy_ids=[],
        metadata={},
    )


def test_get_cache_stats_includes_fallback_size(db_session):
    """get_cache_stats() must include 'fallback_cache_size' key."""
    svc = _make_eval_service(db_session)
    svc._fallback_cache["k1"] = (_make_check_response(), __import__("datetime").datetime.utcnow())

    stats = svc.get_cache_stats()
    assert "fallback_cache_size" in stats
    assert stats["fallback_cache_size"] == 1


def test_clear_cache_empties_fallback(db_session):
    """clear_cache() must empty the in-memory fallback dict."""
    svc = _make_eval_service(db_session)
    svc._fallback_cache["x"] = (_make_check_response(), __import__("datetime").datetime.utcnow())

    svc.clear_cache()
    assert len(svc._fallback_cache) == 0


def test_cache_result_writes_to_fallback_when_redis_down(db_session):
    """_cache_result() writes to the fallback dict when Redis is disconnected."""
    svc = _make_eval_service(db_session)
    response = _make_check_response()

    svc._cache_result("test-key", response)
    assert "test-key" in svc._fallback_cache
    assert svc._fallback_cache["test-key"][0] is response


def test_get_from_fallback_cache_returns_valid_hit(db_session):
    """_get_from_fallback_cache() returns a cached entry that is within the TTL."""
    import datetime as dt
    svc = _make_eval_service(db_session)
    response = _make_check_response()
    svc._fallback_cache["k"] = (response, dt.datetime.utcnow())

    result = svc._get_from_fallback_cache("k")
    assert result is response


def test_get_from_fallback_cache_removes_expired_entry(db_session):
    """_get_from_fallback_cache() removes and returns None for expired entries."""
    import datetime as dt
    svc = _make_eval_service(db_session)
    response = _make_check_response()
    # Store entry with timestamp well in the past
    svc._fallback_cache["stale"] = (response, dt.datetime.utcnow() - dt.timedelta(minutes=10))

    result = svc._get_from_fallback_cache("stale")
    assert result is None
    assert "stale" not in svc._fallback_cache


def test_get_from_fallback_cache_returns_none_on_miss(db_session):
    """_get_from_fallback_cache() returns None when key is absent."""
    svc = _make_eval_service(db_session)
    assert svc._get_from_fallback_cache("no-such-key") is None


def test_invalidate_cache_clears_fallback_for_agent(db_session):
    """invalidate_cache(agent_id=...) clears the fallback dict."""
    svc = _make_eval_service(db_session)
    svc._fallback_cache["some-key"] = (_make_check_response(), __import__("datetime").datetime.utcnow())

    svc.invalidate_cache(agent_id="agent-001")
    assert len(svc._fallback_cache) == 0


def test_invalidate_cache_clears_fallback_for_policy(db_session):
    """invalidate_cache(policy_id=...) clears the fallback dict."""
    svc = _make_eval_service(db_session)
    svc._fallback_cache["some-key"] = (_make_check_response(), __import__("datetime").datetime.utcnow())

    svc.invalidate_cache(policy_id="policy-001")
    assert len(svc._fallback_cache) == 0


def test_invalidate_cache_clears_all_without_args(db_session):
    """invalidate_cache() with no args clears the fallback dict."""
    svc = _make_eval_service(db_session)
    svc._fallback_cache["k1"] = (_make_check_response(), __import__("datetime").datetime.utcnow())
    svc._fallback_cache["k2"] = (_make_check_response(), __import__("datetime").datetime.utcnow())

    svc.invalidate_cache()
    assert len(svc._fallback_cache) == 0


def test_cleanup_fallback_cache_removes_only_expired(db_session):
    """_cleanup_fallback_cache() removes expired entries but leaves valid ones."""
    import datetime as dt
    svc = _make_eval_service(db_session)
    valid_resp = _make_check_response("allow")
    stale_resp = _make_check_response("block")

    svc._fallback_cache["valid"] = (valid_resp, dt.datetime.utcnow())
    svc._fallback_cache["stale"] = (stale_resp, dt.datetime.utcnow() - dt.timedelta(minutes=10))

    svc._cleanup_fallback_cache()
    assert "valid" in svc._fallback_cache
    assert "stale" not in svc._fallback_cache


def test_warm_cache_for_agent_returns_count(db_session):
    """warm_cache_for_agent() returns the number of entries warmed (≥0)."""
    svc = PolicyEvaluationService(db_session)
    frequent_tools = [
        {"tool_name": "read_file", "arguments": {}, "user_id": "user-001"},
        {"tool_name": "list_files", "arguments": {}, "user_id": "user-001"},
    ]
    count = svc.warm_cache_for_agent("agent-warm-001", frequent_tools)
    assert isinstance(count, int)
    assert count >= 0
