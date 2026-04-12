"""Tests verifying PHI redaction in audit log arguments (Task 3.7).

Ensures that tool arguments containing PHI patterns (SSN, DOB, phone, email)
are redacted before being persisted in the audit log.
"""

import pytest
import re
from policy_engine.routes.policy_check import _redact_arguments
from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine


# ---------------------------------------------------------------------------
# Unit tests for _redact_arguments helper
# ---------------------------------------------------------------------------

def test_ssn_is_redacted_in_arguments():
    """SSN pattern in argument value must be replaced."""
    args = {"note": "Patient SSN is 123-45-6789"}
    result = _redact_arguments(args)
    assert "123-45-6789" not in result["note"]
    assert "REDACTED" in result["note"].upper() or result["note"] != args["note"]


def test_phone_is_redacted_in_arguments():
    """Phone number in argument value must be replaced."""
    args = {"contact": "Call 555-867-5309 for details"}
    result = _redact_arguments(args)
    assert "555-867-5309" not in result["contact"]


def test_email_is_redacted_in_arguments():
    """Email address in argument value must be replaced."""
    args = {"message": "Send to patient.john@example.com please"}
    result = _redact_arguments(args)
    assert "patient.john@example.com" not in result["message"]


def test_clean_arguments_pass_through_unchanged():
    """Arguments with no PHI must be returned unchanged."""
    args = {"action": "read_file", "path": "/tmp/report.pdf", "limit": 10}
    # _redact_arguments only processes string values; non-strings pass through
    result = _redact_arguments(args)
    assert result["action"] == "read_file"
    assert result["path"] == "/tmp/report.pdf"
    assert result["limit"] == 10


def test_non_string_values_pass_through():
    """Non-string argument values (int, list, dict) must be preserved as-is."""
    args = {
        "count": 42,
        "tags": ["phi", "test"],
        "meta": {"key": "value"},
    }
    result = _redact_arguments(args)
    assert result["count"] == 42
    assert result["tags"] == ["phi", "test"]
    assert result["meta"] == {"key": "value"}


def test_multiple_phi_patterns_redacted():
    """Multiple PHI items in one field are all redacted.

    Uses a phone number and email — both reliably matched by PHIRedactionEngine.
    (SSN regex excludes 9xx prefixes per HIPAA Safe Harbor, so we rely on
    other identifiers here.)
    """
    args = {
        "note": "Contact: 212-555-0100, Email: john.doe@clinic.example.com"
    }
    result = _redact_arguments(args)
    note = result["note"]
    assert "212-555-0100" not in note
    assert "john.doe@clinic.example.com" not in note


# ---------------------------------------------------------------------------
# Integration test: audit log written via authed_client contains no raw PHI
# ---------------------------------------------------------------------------

def test_audit_log_arguments_are_redacted_for_phi_patterns(authed_client, db_session):
    """PHI in tool arguments must not appear verbatim in the stored audit log."""
    from policy_engine.models.audit_log import AuditLog

    client, agent_id = authed_client

    phi_payload = {
        "agent_id": agent_id,
        "user_id": "user-test-phi",
        "tool_name": "send_message",
        "arguments": {
            "body": "Patient SSN 123-45-6789 DOB 01/01/1990",
            "recipient": "dr.smith@hospital.example.com",
        },
        "context": {},
    }

    response = client.post("/v1/policy/check", json=phi_payload)
    # Any policy decision is fine — we care about what got stored
    assert response.status_code == 200

    # Query the most recent audit log for this agent
    log = (
        db_session.query(AuditLog)
        .filter(AuditLog.agent_id == agent_id)
        .order_by(AuditLog.timestamp.desc())
        .first()
    )
    assert log is not None, "Audit log was not created"

    stored_args = log.arguments or {}
    body_stored = stored_args.get("body", "")
    recipient_stored = stored_args.get("recipient", "")

    # Raw PHI must not appear verbatim in stored arguments
    assert "123-45-6789" not in body_stored, (
        f"SSN found verbatim in audit log arguments: {body_stored!r}"
    )
    assert "dr.smith@hospital.example.com" not in recipient_stored, (
        f"Email found verbatim in audit log arguments: {recipient_stored!r}"
    )
