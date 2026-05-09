"""Phase 2 — Test Coverage Retrofit: Alert and Slack Service.

Covers: services/alert_service.py, services/slack_service.py
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


from policy_engine.models.alert import Alert, AlertSeverity
from policy_engine.models.schemas import PolicyType
from policy_engine.services.alert_service import AlertService
from policy_engine.services.slack_service import SlackService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_alert(db_session, *, agent_id="agent-alert-test",
                alert_type="blocked_access",
                severity=AlertSeverity.HIGH,
                minutes_ago: int = 0) -> Alert:
    """Insert a pre-existing Alert directly into the DB."""
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    alert = Alert(
        id=str(uuid.uuid4()),
        timestamp=ts,
        severity=severity,
        alert_type=alert_type,
        agent_id=agent_id,
        description="Test alert",
        acknowledged=False,
    )
    db_session.add(alert)
    db_session.commit()
    return alert


# ---------------------------------------------------------------------------
# Task 2.5: create_alert
# ---------------------------------------------------------------------------

def test_create_alert_persists_to_db(db_session):
    """create_alert() must persist the alert row to the database."""
    svc = AlertService(db_session)
    alert = svc.create_alert(
        severity=AlertSeverity.HIGH,
        alert_type="blocked_access",
        agent_id="agent-persist-test",
        description="Tool was blocked",
    )
    assert alert is not None
    assert alert.id is not None

    stored = db_session.query(Alert).filter(Alert.id == alert.id).first()
    assert stored is not None
    assert stored.agent_id == "agent-persist-test"


def test_create_alert_returns_none_when_dedup_fires(db_session):
    """create_alert() returns None when a duplicate exists within the window."""
    svc = AlertService(db_session)
    _make_alert(db_session, agent_id="agent-dup", alert_type="blocked_access", minutes_ago=1)

    result = svc.create_alert(
        severity=AlertSeverity.HIGH,
        alert_type="blocked_access",
        agent_id="agent-dup",
        description="Second identical alert",
        auto_deduplicate=True,
    )
    assert result is None


# ---------------------------------------------------------------------------
# Task 2.5: deduplication timing
# ---------------------------------------------------------------------------

def test_deduplication_returns_none_within_window(db_session):
    """An alert within the 5-minute window is deduplicated (returns None)."""
    svc = AlertService(db_session, deduplication_window_seconds=300)
    _make_alert(db_session, agent_id="agent-time-test", alert_type="blocked_access",
                minutes_ago=2)

    result = svc.create_alert(
        severity=AlertSeverity.HIGH,
        alert_type="blocked_access",
        agent_id="agent-time-test",
        description="Should be deduped",
    )
    assert result is None


def test_deduplication_creates_new_alert_after_window(db_session):
    """An alert outside the dedup window should be created as a new row."""
    svc = AlertService(db_session, deduplication_window_seconds=60)
    # Seed an alert that is 5 minutes old — outside the 60-second window
    _make_alert(db_session, agent_id="agent-outside-window", alert_type="blocked_access",
                minutes_ago=5)

    result = svc.create_alert(
        severity=AlertSeverity.HIGH,
        alert_type="blocked_access",
        agent_id="agent-outside-window",
        description="Should be a new alert",
    )
    assert result is not None


def test_deduplication_disabled_always_creates(db_session):
    """With auto_deduplicate=False, two identical alerts are both created."""
    svc = AlertService(db_session)
    _make_alert(db_session, agent_id="agent-no-dedup", alert_type="blocked_access",
                minutes_ago=1)

    result = svc.create_alert(
        severity=AlertSeverity.HIGH,
        alert_type="blocked_access",
        agent_id="agent-no-dedup",
        description="No dedup",
        auto_deduplicate=False,
    )
    assert result is not None


# ---------------------------------------------------------------------------
# Task 2.5: severity classification
# ---------------------------------------------------------------------------

def test_severity_classification_returns_critical_for_new_agent(db_session):
    """classify_severity returns CRITICAL for new agent events."""
    svc = AlertService(db_session)
    severity = svc.classify_severity(
        policy_type=PolicyType.ACCESS_CONTROL,
        decision="allow",
        is_new_agent=True,
    )
    assert severity == AlertSeverity.CRITICAL


def test_severity_classification_returns_high_for_block_decision(db_session):
    """classify_severity returns HIGH (or CRITICAL) for blocked financial actions."""
    svc = AlertService(db_session)
    severity = svc.classify_severity(
        policy_type=PolicyType.FINANCIAL,
        decision="block",
        is_new_agent=False,
    )
    assert severity in (AlertSeverity.HIGH, AlertSeverity.CRITICAL)


def test_severity_classification_critical_for_data_protection_block(db_session):
    """classify_severity returns CRITICAL for blocked data-protection events."""
    svc = AlertService(db_session)
    severity = svc.classify_severity(
        policy_type=PolicyType.DATA_PROTECTION,
        decision="block",
        is_new_agent=False,
    )
    assert severity == AlertSeverity.CRITICAL


def test_severity_classification_medium_for_require_approval(db_session):
    """classify_severity returns MEDIUM for require_approval decisions."""
    svc = AlertService(db_session)
    severity = svc.classify_severity(
        policy_type=PolicyType.ACCESS_CONTROL,
        decision="require_approval",
        is_new_agent=False,
    )
    assert severity == AlertSeverity.MEDIUM


# ---------------------------------------------------------------------------
# Task 2.5: determine_alert_type
# ---------------------------------------------------------------------------

def test_determine_alert_type_returns_none_for_allow(db_session):
    """determine_alert_type returns None for allow decisions (no alert needed)."""
    svc = AlertService(db_session)
    alert_type = svc.determine_alert_type(
        policy_type=PolicyType.ACCESS_CONTROL,
        decision="allow",
        tool_name="read_file",
        is_new_agent=False,
    )
    assert alert_type is None


def test_determine_alert_type_returns_new_agent_for_new_agent(db_session):
    """determine_alert_type returns 'new_agent' when is_new_agent=True."""
    svc = AlertService(db_session)
    alert_type = svc.determine_alert_type(
        policy_type=PolicyType.ACCESS_CONTROL,
        decision="allow",
        tool_name="any_tool",
        is_new_agent=True,
    )
    assert alert_type == "new_agent"


def test_determine_alert_type_blocked_access(db_session):
    """determine_alert_type returns 'blocked_access' for blocked ACCESS_CONTROL."""
    svc = AlertService(db_session)
    alert_type = svc.determine_alert_type(
        policy_type=PolicyType.ACCESS_CONTROL,
        decision="block",
        tool_name="read_file",
        is_new_agent=False,
    )
    assert alert_type == "blocked_access"


def test_determine_alert_type_data_protection_violation(db_session):
    """determine_alert_type returns 'data_protection_violation' for blocked DATA_PROTECTION."""
    svc = AlertService(db_session)
    alert_type = svc.determine_alert_type(
        policy_type=PolicyType.DATA_PROTECTION,
        decision="block",
        tool_name="export_records",
        is_new_agent=False,
    )
    assert alert_type == "data_protection_violation"


# ---------------------------------------------------------------------------
# Task 2.5: should_trigger_alert
# ---------------------------------------------------------------------------

def test_should_trigger_alert_true_for_block(db_session):
    svc = AlertService(db_session)
    assert svc.should_trigger_alert(decision="block") is True


def test_should_trigger_alert_true_for_require_approval(db_session):
    svc = AlertService(db_session)
    assert svc.should_trigger_alert(decision="require_approval") is True


def test_should_trigger_alert_true_for_new_agent(db_session):
    svc = AlertService(db_session)
    assert svc.should_trigger_alert(decision="allow", is_new_agent=True) is True


def test_should_trigger_alert_false_for_allow(db_session):
    svc = AlertService(db_session)
    assert svc.should_trigger_alert(decision="allow", is_new_agent=False) is False


# ---------------------------------------------------------------------------
# Task 2.5: Slack service — format and send
# ---------------------------------------------------------------------------

def _make_alert_obj():
    """Create a mock Alert object for Slack format tests (avoids SQLAlchemy instrumentation)."""
    alert = MagicMock()
    alert.id = str(uuid.uuid4())
    alert.timestamp = datetime.now(timezone.utc)
    alert.severity = AlertSeverity.HIGH.value
    alert.alert_type = "blocked_access"
    alert.agent_id = "agent-slack-test"
    alert.description = "Dangerous tool was blocked"
    alert.audit_log_id = None
    alert.acknowledged = False
    return alert


def test_slack_message_format_includes_severity_and_agent():
    """_format_message must include severity and agent in the payload."""
    svc = SlackService()
    alert = _make_alert_obj()
    msg = svc._format_message(
        alert=alert,
        agent_name="My Agent",
        policy_violated="Block Dangerous Tools",
        action_attempted="dangerous_tool",
    )
    payload_str = str(msg)
    assert "HIGH" in payload_str.upper() or "high" in payload_str.lower()
    assert "My Agent" in payload_str


def test_slack_send_returns_true_on_200(mock_slack):
    """send_alert returns True when the webhook returns HTTP 200."""
    mock_slack.return_value.status_code = 200
    alert = _make_alert_obj()
    svc = SlackService(webhook_url="https://hooks.slack.com/test")
    result = svc.send_alert(alert=alert)
    assert result is True


def test_slack_send_returns_false_with_no_webhook():
    """send_alert returns False and does not raise when no webhook is configured."""
    svc = SlackService()
    alert = _make_alert_obj()
    result = svc.send_alert(alert=alert)
    assert result is False


def test_slack_retry_on_network_failure(mock_slack):
    """send_alert retries up to retry_attempts times on network failure."""
    import requests

    mock_slack.side_effect = requests.exceptions.ConnectionError("network down")
    alert = _make_alert_obj()
    svc = SlackService(webhook_url="https://hooks.slack.com/test")
    svc.retry_delay_seconds = 0  # no real sleep in tests
    result = svc.send_alert(alert=alert)

    assert result is False
    assert mock_slack.call_count == svc.retry_attempts


def test_slack_does_not_raise_on_permanent_failure(mock_slack):
    """send_alert must never raise — even if all retries fail."""
    import requests

    mock_slack.side_effect = requests.exceptions.Timeout("timeout")
    alert = _make_alert_obj()
    svc = SlackService(webhook_url="https://hooks.slack.com/test")
    svc.retry_delay_seconds = 0

    # Must not raise
    result = svc.send_alert(alert=alert)
    assert result is False


# ---------------------------------------------------------------------------
# Coverage gap: acknowledge_alert + get_alert (lines 112–156)
# ---------------------------------------------------------------------------

def test_acknowledge_alert_marks_as_acknowledged(db_session):
    """acknowledge_alert() sets acknowledged=True and records acknowledged_by."""
    svc = AlertService(db_session)
    alert = _make_alert(db_session, agent_id="agent-ack-001")

    result = svc.acknowledge_alert(alert.id, acknowledged_by="user-admin-001")

    assert result is not None
    assert result.acknowledged is True
    assert result.acknowledged_by == "user-admin-001"
    assert result.acknowledged_at is not None


def test_acknowledge_alert_returns_none_for_unknown_id(db_session):
    """acknowledge_alert() returns None when the alert_id doesn't exist."""
    svc = AlertService(db_session)
    result = svc.acknowledge_alert("nonexistent-alert-id", acknowledged_by="user-1")
    assert result is None


def test_get_alert_returns_alert_by_id(db_session):
    """get_alert() returns the Alert object for a known ID."""
    svc = AlertService(db_session)
    alert = _make_alert(db_session, agent_id="agent-get-001")

    result = svc.get_alert(alert.id)
    assert result is not None
    assert result.id == alert.id


def test_get_alert_returns_none_for_unknown_id(db_session):
    """get_alert() returns None for an ID that doesn't exist."""
    svc = AlertService(db_session)
    result = svc.get_alert("totally-unknown-id")
    assert result is None


def test_create_alert_returns_none_on_db_error(db_session):
    """create_alert() returns None and doesn't raise when the DB commit fails."""
    svc = AlertService(db_session)

    with patch.object(db_session, "commit", side_effect=Exception("DB write failed")):
        result = svc.create_alert(
            severity=AlertSeverity.HIGH,
            alert_type="blocked_access",
            agent_id="agent-db-error",
            description="Should not persist",
            auto_deduplicate=False,
        )

    assert result is None


def test_classify_severity_returns_low_for_allow_non_new_agent(db_session):
    """classify_severity returns LOW for allow decision on non-new agent."""
    svc = AlertService(db_session)
    severity = svc.classify_severity(
        policy_type=PolicyType.ACCESS_CONTROL,
        decision="allow",
        is_new_agent=False,
    )
    assert severity == AlertSeverity.LOW


def test_determine_alert_type_approval_required(db_session):
    """determine_alert_type returns 'approval_required' for require_approval decision."""
    svc = AlertService(db_session)
    alert_type = svc.determine_alert_type(
        policy_type=PolicyType.FINANCIAL,
        decision="require_approval",
        tool_name="process_payment",
        is_new_agent=False,
    )
    assert alert_type == "approval_required"


def test_determine_alert_type_high_transaction(db_session):
    """determine_alert_type returns 'high_transaction' for blocked payment tools."""
    svc = AlertService(db_session)
    alert_type = svc.determine_alert_type(
        policy_type=PolicyType.FINANCIAL,
        decision="block",
        tool_name="process_payment",
        is_new_agent=False,
    )
    assert alert_type == "high_transaction"


def test_determine_alert_type_blocked_financial_action(db_session):
    """determine_alert_type returns 'blocked_financial_action' for non-payment financial blocks."""
    svc = AlertService(db_session)
    alert_type = svc.determine_alert_type(
        policy_type=PolicyType.FINANCIAL,
        decision="block",
        tool_name="generate_report",
        is_new_agent=False,
    )
    assert alert_type == "blocked_financial_action"


# ---------------------------------------------------------------------------
# Coverage gap: Slack non-200 + send_test_message (lines 80, 228–283)
# ---------------------------------------------------------------------------

def test_slack_send_returns_false_on_non_200(mock_slack):
    """send_alert returns False when webhook returns a non-200 status code."""
    mock_slack.return_value.status_code = 400
    mock_slack.return_value.text = "Bad Request"
    alert = _make_alert_obj()
    svc = SlackService(webhook_url="https://hooks.slack.com/test")
    svc.retry_attempts = 1  # one attempt, no retry
    result = svc.send_alert(alert=alert)
    assert result is False


def test_slack_send_test_message_returns_true_on_200(mock_slack):
    """send_test_message returns True when webhook returns HTTP 200."""
    mock_slack.return_value.status_code = 200
    svc = SlackService(webhook_url="https://hooks.slack.com/test")
    result = svc.send_test_message()
    assert result is True
    mock_slack.assert_called_once()


def test_slack_send_test_message_returns_false_with_no_webhook():
    """send_test_message returns False when no webhook is configured."""
    svc = SlackService()
    result = svc.send_test_message()
    assert result is False


def test_slack_send_test_message_returns_false_on_non_200(mock_slack):
    """send_test_message returns False when webhook returns non-200."""
    mock_slack.return_value.status_code = 500
    mock_slack.return_value.text = "Internal Server Error"
    svc = SlackService(webhook_url="https://hooks.slack.com/test")
    result = svc.send_test_message()
    assert result is False


def test_slack_send_test_message_returns_false_on_exception(mock_slack):
    """send_test_message returns False and doesn't raise on network error."""
    import requests as _requests
    mock_slack.side_effect = _requests.exceptions.ConnectionError("down")
    svc = SlackService(webhook_url="https://hooks.slack.com/test")
    result = svc.send_test_message()
    assert result is False
