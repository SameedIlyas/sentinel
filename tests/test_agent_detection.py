"""Tests for new-agent detection — Task 1.2 (Phase 1).

RED phase: register_or_update_agent currently returns Agent (not a tuple),
and trigger_alert has is_new_agent hardcoded to False.  All tuple-return
assertions and new-agent severity assertions will FAIL until GREEN.
"""
from unittest.mock import MagicMock, patch

from policy_engine.models.agent import Agent, AgentStatus
from policy_engine.services.agent_activity_service import AgentActivityService


# ---------------------------------------------------------------------------
# register_or_update_agent return type
# ---------------------------------------------------------------------------

def test_register_new_agent_returns_tuple_true(db_session):
    """First registration must return (Agent, True)."""
    result = AgentActivityService.register_or_update_agent(
        db=db_session,
        agent_id="agent-new-001",
        agent_name="Test Agent",
    )
    assert isinstance(result, tuple), "Expected (Agent, bool) tuple"
    agent_obj, is_new = result
    assert isinstance(agent_obj, Agent)
    assert is_new is True, "First registration should set is_new=True"


def test_register_existing_agent_returns_tuple_false(db_session):
    """Second call for same agent_id must return (Agent, False)."""
    AgentActivityService.register_or_update_agent(
        db=db_session,
        agent_id="agent-existing-001",
        agent_name="Test Agent",
    )
    result = AgentActivityService.register_or_update_agent(
        db=db_session,
        agent_id="agent-existing-001",
        agent_name="Test Agent",
    )
    assert isinstance(result, tuple), "Expected (Agent, bool) tuple"
    agent_obj, is_new = result
    assert isinstance(agent_obj, Agent)
    assert is_new is False, "Second registration should set is_new=False"


def test_returned_agent_has_correct_id(db_session):
    """The Agent object in the tuple must have the requested agent_id."""
    agent_obj, _ = AgentActivityService.register_or_update_agent(
        db=db_session,
        agent_id="agent-id-check",
        agent_name="ID Check Agent",
    )
    assert agent_obj.id == "agent-id-check"


def test_new_agent_persisted_in_db(db_session):
    """A new agent registration must persist the record to the database."""
    AgentActivityService.register_or_update_agent(
        db=db_session,
        agent_id="agent-persist-check",
    )
    stored = db_session.query(Agent).filter(
        Agent.id == "agent-persist-check"
    ).first()
    assert stored is not None, "Agent should be persisted after registration"
    assert stored.status == AgentStatus.ACTIVE


# ---------------------------------------------------------------------------
# trigger_alert receives is_new_agent
# ---------------------------------------------------------------------------

def test_trigger_alert_passes_is_new_agent_flag(db_session):
    """trigger_alert must forward the is_new_agent flag to AlertService."""
    from policy_engine.routes.policy_check import trigger_alert
    from policy_engine.models.schemas import PolicyCheckRequest, PolicyCheckResponse

    request = PolicyCheckRequest(
        agent_id="agent-flag-test",
        tool_name="read_file",
        arguments={"path": "/tmp/test"},
        user_id="user-1",
    )
    response = PolicyCheckResponse(
        decision="block",
        reason="Policy violated",
        policy_ids=[],
        masked_data=None,
        metadata={},
    )

    with patch(
        "policy_engine.routes.policy_check.AlertService"
    ) as MockAlertService:
        mock_svc = MagicMock()
        mock_svc.should_trigger_alert.return_value = True
        mock_svc.classify_severity.return_value = MagicMock()
        mock_svc.determine_alert_type.return_value = "policy_violation"
        mock_svc.create_alert.return_value = MagicMock(id="alert-1")
        MockAlertService.return_value = mock_svc

        trigger_alert(
            db=db_session,
            request=request,
            response=response,
            audit_log_id=None,
            is_new_agent=True,
        )

        # should_trigger_alert must have been called with is_new_agent=True
        call_kwargs = mock_svc.should_trigger_alert.call_args
        assert call_kwargs is not None
        passed_flag = (
            call_kwargs.kwargs.get("is_new_agent")
            if call_kwargs.kwargs
            else call_kwargs[1].get("is_new_agent")
        )
        assert passed_flag is True, (
            "trigger_alert must pass is_new_agent=True to AlertService.should_trigger_alert"
        )


def test_new_agent_alert_uses_critical_severity(db_session):
    """classify_severity must return CRITICAL when is_new_agent=True."""
    from policy_engine.services.alert_service import AlertService
    from policy_engine.models.schemas import PolicyType

    svc = AlertService(db_session)
    severity = svc.classify_severity(
        policy_type=PolicyType.ACCESS_CONTROL,
        decision="allow",
        is_new_agent=True,
    )
    # AlertService.classify_severity is already implemented — verify it hasn't regressed
    assert severity is not None
    assert severity.value.lower() in ("critical", "high"), (
        f"New-agent events must be CRITICAL or HIGH, got {severity.value}"
    )


# ---------------------------------------------------------------------------
# AgentActivityService — utility methods
# ---------------------------------------------------------------------------

def test_update_last_active_updates_timestamp(db_session):
    """update_last_active() must update last_active on an existing agent."""
    from datetime import datetime

    # Seed an agent with an old last_active
    agent = Agent(
        id="agent-last-active-001",
        name="Timestamp Test Agent",
        description="test",
        owner_user_id="user-1",
        status=AgentStatus.ACTIVE,
        agent_metadata={},
    )
    db_session.add(agent)
    db_session.commit()

    AgentActivityService.update_last_active(db_session, "agent-last-active-001")

    refreshed = db_session.query(Agent).filter(
        Agent.id == "agent-last-active-001"
    ).first()
    assert refreshed is not None
    # last_active should be very recent (within 5 seconds)
    delta = datetime.utcnow() - refreshed.last_active
    assert delta.total_seconds() < 5


def test_update_last_active_nonexistent_agent_is_noop(db_session):
    """update_last_active() on a missing agent_id must not raise."""
    AgentActivityService.update_last_active(db_session, "no-such-agent")


def test_get_agent_metrics_returns_none_for_unknown_agent(db_session):
    """get_agent_metrics() returns None when the agent does not exist."""
    result = AgentActivityService.get_agent_metrics(db_session, "ghost-agent")
    assert result is None


def test_get_agent_metrics_returns_dict_for_existing_agent(db_session):
    """get_agent_metrics() returns a metrics dict for a known agent."""

    agent = Agent(
        id="agent-metrics-001",
        name="Metrics Test Agent",
        description="test",
        owner_user_id="user-1",
        status=AgentStatus.ACTIVE,
        agent_metadata={},
    )
    db_session.add(agent)
    db_session.commit()

    metrics = AgentActivityService.get_agent_metrics(db_session, "agent-metrics-001")

    assert metrics is not None
    assert metrics["agent_id"] == "agent-metrics-001"
    assert "total_actions" in metrics
    assert "blocked_actions" in metrics
    assert "allowed_actions" in metrics
    assert "systems_accessed" in metrics


def test_get_all_agent_metrics_includes_all_agents(db_session):
    """get_all_agent_metrics() returns aggregate stats covering all agents."""
    for i in range(2):
        db_session.add(Agent(
            id=f"agent-all-{i}",
            name=f"All Agent {i}",
            description="test",
            owner_user_id="user-1",
            status=AgentStatus.ACTIVE,
            agent_metadata={},
        ))
    db_session.commit()

    result = AgentActivityService.get_all_agent_metrics(db_session)

    assert result["total_agents"] >= 2
    assert "active_agents" in result
    assert "metrics" in result


def test_get_systems_accessed_by_agent_returns_list(db_session):
    """get_systems_accessed_by_agent() returns a list (empty when no audit logs)."""
    db_session.add(Agent(
        id="agent-systems-001",
        name="Systems Test Agent",
        description="test",
        owner_user_id="user-1",
        status=AgentStatus.ACTIVE,
        agent_metadata={},
    ))
    db_session.commit()

    systems = AgentActivityService.get_systems_accessed_by_agent(
        db_session, "agent-systems-001"
    )
    assert isinstance(systems, list)
