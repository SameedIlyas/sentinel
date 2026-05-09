"""Tests for Tier 3 Shadow AI batch ingest + vendor adapters."""
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pytest

from policy_engine.domain.admin.shadow_ai import (
    AI_PROVIDER_DOMAINS,
    assess_phi_risk,
    detect_ai_provider,
    is_allowlisted,
    score_confidence,
)
from policy_engine.models.shadow_ai import (
    ShadowAIAllowlist,
    ShadowAIDetectionModel,
)
from policy_engine.services.shadow_ai_ingest import (
    FlowRecord,
    ingest_flow_records,
    ingest_vendor_payload,
    parse_aws_vpc_flow_logs,
    parse_cloudflare_logpush,
    parse_zscaler_siem,
)


# ---------------------------------------------------------------------------
# Domain — expanded provider list
# ---------------------------------------------------------------------------

def test_provider_list_covers_major_vendors():
    expected_keys_present = {
        "api.openai.com", "claude.ai", "api.anthropic.com",
        "gemini.google.com", "api.mistral.ai", "api.deepseek.com",
        "api.groq.com", "api.perplexity.ai", "api.cohere.com",
        "openrouter.ai", "x.ai",
    }
    missing = expected_keys_present - set(AI_PROVIDER_DOMAINS.keys())
    assert not missing, f"missing providers: {missing}"


def test_detect_ai_provider_subdomain_match():
    assert detect_ai_provider("foo.api.openai.com") == "openai"
    assert detect_ai_provider("api.openai.com") == "openai"
    assert detect_ai_provider("legitimate.example.com") is None


def test_detect_ai_provider_handles_empty():
    assert detect_ai_provider("") is None
    assert detect_ai_provider(None) is None  # type: ignore[arg-type]


def test_assess_phi_risk_clinical_dept_elevates_to_high():
    assert assess_phi_risk("api.openai.com", 443, "ICU") == "high"
    assert assess_phi_risk("api.openai.com", 443, "marketing") == "medium"
    assert assess_phi_risk("api.openai.com", 80, "ICU") == "low"
    assert assess_phi_risk("not-ai.example.com", 443, "ICU") == "none"


def test_score_confidence_is_bounded():
    assert 0.0 <= score_confidence() <= 1.0
    high = score_confidence(
        bytes_transferred=4096, method="POST", user_agent="python-requests/2.31",
        repeated_in_window=10, department="ICU",
    )
    low = score_confidence(bytes_transferred=10, method="GET")
    assert high > low
    assert high <= 1.0


# ---------------------------------------------------------------------------
# Vendor parsers
# ---------------------------------------------------------------------------

def test_parse_cloudflare_logpush_jsonl():
    payload = "\n".join([
        json.dumps({
            "ClientIP": "10.1.2.3",
            "ClientRequestHost": "api.openai.com",
            "ClientRequestMethod": "POST",
            "ClientRequestUserAgent": "python-requests/2.31",
            "EdgeResponseBytes": 2048,
            "DestinationPort": 443,
            "EdgeStartTimestamp": "2026-05-09T12:00:00Z",
        }),
        json.dumps({
            "ClientIP": "10.1.2.4",
            "ClientRequestHost": "example.com",
            "ClientRequestMethod": "GET",
            "EdgeResponseBytes": 100,
        }),
    ])
    records = parse_cloudflare_logpush(payload)
    assert len(records) == 2
    assert records[0].destination_host == "api.openai.com"
    assert records[0].source_ip == "10.1.2.3"
    assert records[0].bytes_transferred == 2048
    assert records[0].method == "POST"
    assert records[0].timestamp is not None


def test_parse_cloudflare_logpush_list_form():
    payload = [
        {"ClientRequestHost": "claude.ai", "EdgeResponseBytes": 512},
        {"ClientRequestHost": "", "EdgeResponseBytes": 0},  # skipped
        "not-a-dict",
    ]
    records = parse_cloudflare_logpush(payload)
    assert len(records) == 1
    assert records[0].destination_host == "claude.ai"


def test_parse_cloudflare_logpush_wrapped():
    payload = {"events": [{"ClientRequestHost": "api.anthropic.com"}]}
    records = parse_cloudflare_logpush(payload)
    assert len(records) == 1


def test_parse_zscaler_siem():
    payload = {
        "logs": [
            {
                "host": "api.openai.com",
                "user_ip": "10.0.0.1",
                "dst_port": 443,
                "method": "POST",
                "bytes_out": 8192,
                "user_dept": "Cardiology",
            }
        ]
    }
    records = parse_zscaler_siem(payload)
    assert len(records) == 1
    rec = records[0]
    assert rec.destination_host == "api.openai.com"
    assert rec.bytes_transferred == 8192
    assert rec.department == "Cardiology"


def test_parse_aws_vpc_flow_logs_v2_text():
    line = (
        "2 123456789012 eni-abc 10.0.0.1 1.2.3.4 12345 443 6 10 5000 "
        "1700000000 1700000060 ACCEPT OK"
    )
    records = parse_aws_vpc_flow_logs(line)
    assert len(records) == 1
    rec = records[0]
    assert rec.source_ip == "10.0.0.1"
    assert rec.destination_host == "1.2.3.4"
    assert rec.destination_port == 443
    assert rec.bytes_transferred == 5000


# ---------------------------------------------------------------------------
# Ingest pipeline
# ---------------------------------------------------------------------------

def _record(host: str, **kwargs: Any) -> FlowRecord:
    return FlowRecord(destination_host=host, **kwargs)


def test_ingest_creates_detection_for_known_provider(db_session):
    outcome = ingest_flow_records(
        db_session,
        [_record("api.openai.com", source_ip="10.0.0.5", bytes_transferred=2048,
                 method="POST", user_agent="python")],
    )
    assert outcome.received == 1
    assert outcome.classified_as_ai == 1
    assert outcome.detections_created == 1
    assert outcome.detections_deduped == 0

    detections = db_session.query(ShadowAIDetectionModel).all()
    assert len(detections) == 1
    d = detections[0]
    assert d.ai_provider == "openai"
    assert d.confidence_score >= 0.5
    assert d.phi_risk_level == "medium"


def test_ingest_drops_non_ai_hosts_silently(db_session):
    outcome = ingest_flow_records(
        db_session,
        [_record("example.com"), _record("github.com")],
    )
    assert outcome.received == 2
    assert outcome.classified_as_ai == 0
    assert outcome.detections_created == 0
    assert db_session.query(ShadowAIDetectionModel).count() == 0


def test_ingest_dedupes_within_window(db_session):
    rec = _record("api.openai.com", source_ip="10.0.0.5", bytes_transferred=1024)

    first = ingest_flow_records(db_session, [rec])
    second = ingest_flow_records(db_session, [rec])

    assert first.detections_created == 1
    assert second.detections_created == 0
    assert second.detections_deduped == 1
    assert db_session.query(ShadowAIDetectionModel).count() == 1


def test_ingest_skips_allowlisted_hosts(db_session):
    db_session.add(ShadowAIAllowlist(
        id=str(uuid.uuid4()),
        host_pattern="*.openai.com",
        approved_at=datetime.utcnow(),
        organization_id=None,
        created_at=datetime.utcnow(),
    ))
    db_session.commit()

    outcome = ingest_flow_records(
        db_session,
        [_record("api.openai.com", source_ip="10.0.0.5")],
    )
    assert outcome.classified_as_ai == 1
    assert outcome.allowlisted == 1
    assert outcome.detections_created == 0


def test_ingest_expired_allowlist_does_not_skip(db_session):
    db_session.add(ShadowAIAllowlist(
        id=str(uuid.uuid4()),
        host_pattern="*.openai.com",
        approved_at=datetime.utcnow() - timedelta(days=10),
        expires_at=datetime.utcnow() - timedelta(days=1),  # already expired
        organization_id=None,
        created_at=datetime.utcnow() - timedelta(days=10),
    ))
    db_session.commit()

    outcome = ingest_flow_records(
        db_session,
        [_record("api.openai.com", source_ip="10.0.0.5")],
    )
    assert outcome.allowlisted == 0
    assert outcome.detections_created == 1


def test_ingest_clinical_department_high_phi_risk(db_session):
    outcome = ingest_flow_records(
        db_session,
        [_record(
            "api.openai.com", source_ip="10.0.0.5",
            department="ICU", bytes_transferred=2048, method="POST",
        )],
    )
    assert outcome.detections_created == 1
    detection = db_session.query(ShadowAIDetectionModel).first()
    assert detection.phi_risk_level == "high"


def test_ingest_vendor_cloudflare(db_session):
    payload = [{
        "ClientRequestHost": "api.anthropic.com",
        "ClientIP": "10.0.0.7",
        "ClientRequestMethod": "POST",
        "EdgeResponseBytes": 4096,
        "DestinationPort": 443,
    }]
    outcome = ingest_vendor_payload(
        db_session, vendor="cloudflare", payload=payload,
    )
    assert outcome.detections_created == 1


def test_ingest_vendor_unsupported_returns_error(db_session):
    outcome = ingest_vendor_payload(
        db_session, vendor="random_vendor", payload={},
    )
    assert outcome.detections_created == 0
    assert any("unsupported_vendor" in e for e in outcome.errors)


# ---------------------------------------------------------------------------
# Endpoint coverage
# ---------------------------------------------------------------------------

def test_ingest_endpoint_canonical_records(authed_client):
    client, _agent_id = authed_client
    resp = client.post(
        "/v1/admin/shadow-ai/ingest",
        json={
            "records": [
                {
                    "destination_host": "api.openai.com",
                    "destination_port": 443,
                    "source_ip": "10.1.1.1",
                    "bytes_transferred": 2048,
                    "method": "POST",
                    "user_agent": "python-requests/2.31",
                    "department": "ICU",
                },
                {
                    "destination_host": "github.com",  # not AI — dropped
                    "destination_port": 443,
                },
            ]
        },
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["received"] == 2
    assert body["classified_as_ai"] == 1
    assert body["detections_created"] == 1


def test_ingest_endpoint_vendor_cloudflare(authed_client):
    client, _agent_id = authed_client
    resp = client.post(
        "/v1/admin/shadow-ai/ingest/vendor",
        json={
            "vendor": "cloudflare",
            "payload": [{
                "ClientRequestHost": "api.openai.com",
                "ClientIP": "10.1.2.3",
                "ClientRequestMethod": "POST",
                "EdgeResponseBytes": 1024,
            }],
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["vendor"] == "cloudflare"
    assert body["detections_created"] == 1


def test_ingest_endpoint_vendor_unsupported_returns_400(authed_client):
    client, _agent_id = authed_client
    resp = client.post(
        "/v1/admin/shadow-ai/ingest/vendor",
        json={"vendor": "splunk", "payload": []},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "unsupported_vendor"


def test_ingest_endpoint_validates_min_records(authed_client):
    client, _agent_id = authed_client
    resp = client.post("/v1/admin/shadow-ai/ingest", json={"records": []})
    assert resp.status_code == 422


def test_is_allowlisted_handles_empty():
    assert is_allowlisted("", []) is False
    assert is_allowlisted("api.openai.com", []) is False
    assert is_allowlisted("api.openai.com", ["*.openai.com"]) is True
    assert is_allowlisted("api.openai.com", [None]) is False  # type: ignore[list-item]
