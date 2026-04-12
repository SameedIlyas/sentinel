"""Tests for Pydantic schema input validation constraints (Task 3.4)."""

import pytest
from pydantic import ValidationError

from policy_engine.models.schemas import (
    PolicyCheckRequest,
    PolicyCreate,
    PolicyUpdate,
    PolicyRule,
    PolicyRuleCondition,
    PolicyType,
    FIELD_LIMITS,
)


def _valid_check_request(**overrides) -> dict:
    base = {
        "agent_id": "agent-123",
        "user_id": "user-456",
        "tool_name": "read_file",
        "arguments": {"path": "/tmp/test.txt"},
    }
    base.update(overrides)
    return base


def _valid_rule() -> PolicyRule:
    return PolicyRule(
        conditions=[PolicyRuleCondition(field="tool_name", operator="eq", value="test")],
        action="allow",
    )


# ---------------------------------------------------------------------------
# PolicyCheckRequest — agent_id
# ---------------------------------------------------------------------------

def test_policy_check_rejects_agent_id_too_long():
    data = _valid_check_request(agent_id="a" * 129)
    with pytest.raises(ValidationError):
        PolicyCheckRequest(**data)


def test_policy_check_accepts_agent_id_at_max_length():
    data = _valid_check_request(agent_id="a" * 128)
    req = PolicyCheckRequest(**data)
    assert len(req.agent_id) == 128


def test_policy_check_rejects_invalid_agent_id_pattern():
    """agent_id must only contain alphanumerics, underscores, hyphens, and dots."""
    for bad in ["agent id", "agent@1", "agent/x", "agent<script>"]:
        data = _valid_check_request(agent_id=bad)
        with pytest.raises(ValidationError, match=""):
            PolicyCheckRequest(**data)


def test_policy_check_accepts_valid_agent_id_patterns():
    for good in ["agent-123", "agent_abc", "agent.v2", "AGENT123"]:
        req = PolicyCheckRequest(**_valid_check_request(agent_id=good))
        assert req.agent_id == good


# ---------------------------------------------------------------------------
# PolicyCheckRequest — tool_name / user_id
# ---------------------------------------------------------------------------

def test_policy_check_rejects_tool_name_too_long():
    data = _valid_check_request(tool_name="t" * 257)
    with pytest.raises(ValidationError):
        PolicyCheckRequest(**data)


def test_policy_check_rejects_user_id_too_long():
    data = _valid_check_request(user_id="u" * 129)
    with pytest.raises(ValidationError):
        PolicyCheckRequest(**data)


# ---------------------------------------------------------------------------
# PolicyCreate — rules / applies_to list limits
# ---------------------------------------------------------------------------

def test_policy_create_rejects_too_many_rules():
    rules = [_valid_rule() for _ in range(FIELD_LIMITS["rules_max_items"] + 1)]
    with pytest.raises(ValidationError):
        PolicyCreate(
            name="p",
            policy_type=PolicyType.ACCESS_CONTROL,
            rules=rules,
            applies_to=["*"],
        )


def test_policy_create_accepts_rules_at_limit():
    rules = [_valid_rule() for _ in range(FIELD_LIMITS["rules_max_items"])]
    policy = PolicyCreate(
        name="p",
        policy_type=PolicyType.ACCESS_CONTROL,
        rules=rules,
        applies_to=["*"],
    )
    assert len(policy.rules) == FIELD_LIMITS["rules_max_items"]


def test_policy_create_rejects_too_many_applies_to():
    applies = [f"agent-{i}" for i in range(FIELD_LIMITS["applies_to_max_items"] + 1)]
    with pytest.raises(ValidationError):
        PolicyCreate(
            name="p",
            policy_type=PolicyType.ACCESS_CONTROL,
            rules=[_valid_rule()],
            applies_to=applies,
        )


def test_policy_create_rejects_description_too_long():
    with pytest.raises(ValidationError):
        PolicyCreate(
            name="p",
            policy_type=PolicyType.ACCESS_CONTROL,
            rules=[_valid_rule()],
            applies_to=["*"],
            description="x" * (FIELD_LIMITS["description"]["max_length"] + 1),
        )


# ---------------------------------------------------------------------------
# PolicyUpdate — same list limits
# ---------------------------------------------------------------------------

def test_policy_update_rejects_too_many_rules():
    rules = [_valid_rule() for _ in range(FIELD_LIMITS["rules_max_items"] + 1)]
    with pytest.raises(ValidationError):
        PolicyUpdate(rules=rules)


def test_policy_update_rejects_too_many_applies_to():
    applies = [f"agent-{i}" for i in range(FIELD_LIMITS["applies_to_max_items"] + 1)]
    with pytest.raises(ValidationError):
        PolicyUpdate(applies_to=applies)


# ---------------------------------------------------------------------------
# FIELD_LIMITS sanity
# ---------------------------------------------------------------------------

def test_field_limits_constants_are_present():
    for key in ("agent_id", "tool_name", "user_id", "description", "rules_max_items", "applies_to_max_items"):
        assert key in FIELD_LIMITS, f"Missing FIELD_LIMITS key: {key}"
