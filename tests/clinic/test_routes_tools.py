"""Integration tests for /v1/clinic/tools — the most-used clinic route.

Covers CRUD, PHI free-text rejection, BAA gating, and tier gating.
"""

from __future__ import annotations

import pytest

from policy_engine.models.clinic import (
    ClinicAiTool,
    ClinicAiToolCategory,
    ClinicAiToolRisk,
)
from policy_engine.models.organization import TIER_CLINIC_BASIC, TIER_ENTERPRISE


pytestmark = pytest.mark.clinic


# ── Happy path ─────────────────────────────────────────────────────────


def test_list_tools_empty(clinic_authed_client) -> None:
    client, _org, _user = clinic_authed_client
    resp = client.get("/v1/clinic/tools")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_tool_201(clinic_authed_client, db_session) -> None:
    client, org, _user = clinic_authed_client
    payload = {
        "name": "Acme Scribe",
        "vendor": "Acme AI",
        "category": "ambient_scribe",
        "purpose": "General clinical note formatting.",
        "handles_phi": False,
        "risk_level": "low",
        "notes": "Reviewed monthly.",
    }
    resp = client.post("/v1/clinic/tools", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Acme Scribe"
    assert body["org_id"] == org.id
    assert body["risk_level"] == "low"
    assert body["status"] == "active"
    # Persisted.
    rows = db_session.query(ClinicAiTool).filter(ClinicAiTool.org_id == org.id).all()
    assert len(rows) == 1


def test_create_tool_then_get_returns_same_row(clinic_authed_client) -> None:
    client, _org, _user = clinic_authed_client
    create = client.post(
        "/v1/clinic/tools",
        json={"name": "Foo Helper", "vendor": "Foo Co"},
    )
    assert create.status_code == 201
    tool_id = create.json()["id"]
    fetched = client.get(f"/v1/clinic/tools/{tool_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == tool_id


def test_get_unknown_tool_404(clinic_authed_client) -> None:
    client, _org, _user = clinic_authed_client
    resp = client.get("/v1/clinic/tools/does-not-exist")
    assert resp.status_code == 404


def test_update_tool_200(clinic_authed_client) -> None:
    client, _org, _user = clinic_authed_client
    create = client.post(
        "/v1/clinic/tools",
        json={"name": "Acme V1"},
    )
    tool_id = create.json()["id"]
    upd = client.put(
        f"/v1/clinic/tools/{tool_id}",
        json={"name": "Acme V2", "risk_level": "medium"},
    )
    assert upd.status_code == 200
    assert upd.json()["name"] == "Acme V2"
    assert upd.json()["risk_level"] == "medium"


def test_delete_tool_204(clinic_authed_client) -> None:
    client, _org, _user = clinic_authed_client
    create = client.post("/v1/clinic/tools", json={"name": "Throwaway"})
    tool_id = create.json()["id"]
    rm = client.delete(f"/v1/clinic/tools/{tool_id}")
    assert rm.status_code == 204
    assert client.get(f"/v1/clinic/tools/{tool_id}").status_code == 404


# ── PHI free-text rejection ────────────────────────────────────────────


@pytest.mark.parametrize(
    "field,value",
    [
        ("notes", "Patient SSN: 555-44-3333 oh no"),
        ("purpose", "Used for DOB 1985-03-14 lookup"),
        ("vendor", "support@acmeai.com"),
        ("notes", "MRN: 123456789012345"),
    ],
)
def test_create_tool_rejects_phi_in_freetext(
    clinic_authed_client, field: str, value: str
) -> None:
    """phi_text_check.reject_if_phi_present must fire BEFORE persistence."""
    client, _org, _user = clinic_authed_client
    payload = {"name": "Test Tool", field: value}
    resp = client.post("/v1/clinic/tools", json=payload)
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert detail["error"] == "phi_in_freetext"
    assert detail["field"] == field
    # The matched substring must NOT echo back to the client.
    assert value not in detail["message"]


def test_update_tool_rejects_phi(clinic_authed_client) -> None:
    client, _org, _user = clinic_authed_client
    create = client.post("/v1/clinic/tools", json={"name": "Clean Tool"})
    tool_id = create.json()["id"]
    bad = client.put(
        f"/v1/clinic/tools/{tool_id}",
        json={"notes": "Patient phone is (555) 867-5309"},
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["error"] == "phi_in_freetext"


# ── Tier + BAA gating ──────────────────────────────────────────────────


def test_create_tool_blocked_for_enterprise(
    db_session, make_clinic_org_factory
) -> None:
    """Enterprise tier hits the require_clinic_tier_with_baa gate first."""
    from fastapi.testclient import TestClient
    from policy_engine.database import get_db
    from policy_engine.main import app
    from tests.factories.clinic import make_clinic_admin

    org = make_clinic_org_factory(tier=TIER_ENTERPRISE, baa_signed=False)
    _user, jwt = make_clinic_admin(db_session, org)

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        c = TestClient(app, raise_server_exceptions=True)
        c.headers.update({"Authorization": f"Bearer {jwt}"})
        resp = c.post("/v1/clinic/tools", json={"name": "X"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "tier_required"


def test_create_tool_blocked_when_baa_unsigned(
    db_session, make_clinic_org_factory
) -> None:
    from fastapi.testclient import TestClient
    from policy_engine.database import get_db
    from policy_engine.main import app
    from tests.factories.clinic import make_clinic_admin

    org = make_clinic_org_factory(tier=TIER_CLINIC_BASIC, baa_signed=False)
    _user, jwt = make_clinic_admin(db_session, org)

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        c = TestClient(app, raise_server_exceptions=True)
        c.headers.update({"Authorization": f"Bearer {jwt}"})
        resp = c.post("/v1/clinic/tools", json={"name": "X"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "baa_required"


def test_list_tools_isolates_by_org(
    db_session, make_clinic_org_factory
) -> None:
    """A clinic admin should only see their own org's tools."""
    from fastapi.testclient import TestClient
    from policy_engine.database import get_db
    from policy_engine.main import app
    from tests.factories.clinic import make_clinic_admin, make_clinic_tool

    org_a = make_clinic_org_factory(slug="a-clinic")
    org_b = make_clinic_org_factory(slug="b-clinic")
    make_clinic_tool(db_session, org_a, name="Tool from A")
    make_clinic_tool(db_session, org_b, name="Tool from B")
    _user_a, jwt_a = make_clinic_admin(db_session, org_a)

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        c = TestClient(app, raise_server_exceptions=True)
        c.headers.update({"Authorization": f"Bearer {jwt_a}"})
        resp = c.get("/v1/clinic/tools")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()]
    assert "Tool from A" in names
    assert "Tool from B" not in names


# ── Audit trail (HIPAA §164.312(b)) ────────────────────────────────────


def test_create_tool_writes_audit_log(clinic_authed_client, db_session) -> None:
    """HIPAA audit: every CRUD action writes an audit_logs row."""
    from policy_engine.models.audit_log import AuditLog

    client, org, user = clinic_authed_client
    before = db_session.query(AuditLog).count()
    resp = client.post("/v1/clinic/tools", json={"name": "Audited Tool"})
    assert resp.status_code == 201
    after = db_session.query(AuditLog).count()
    assert after == before + 1
    log = db_session.query(AuditLog).order_by(AuditLog.timestamp.desc()).first()
    assert log.tool_name == "clinic.tool.create"
    assert log.user_id == user.id
    assert log.organization_id == org.id


# ── PRD.v2.md §6.8.2 — model training status fields ────────────────────


def test_enums_exposed() -> None:
    """Schemas expose ClinicAiToolModelTrainingStatus + PracticeOptOutState."""
    from policy_engine.models.clinic import (
        ClinicAiToolModelTrainingStatus,
        ClinicAiToolPracticeOptOutState,
    )

    assert set(s.value for s in ClinicAiToolModelTrainingStatus) == {
        "unknown",
        "no_training",
        "trains_on_customer_data",
        "opt_out_available",
    }
    assert set(s.value for s in ClinicAiToolPracticeOptOutState) == {
        "not_applicable",
        "required_not_set",
        "required_and_set",
        "verified",
    }


def test_create_with_training_status_201(clinic_authed_client) -> None:
    client, _org, _user = clinic_authed_client
    payload = {
        "name": "ChatGPT (free)",
        "vendor": "OpenAI",
        "model_training_status": "trains_on_customer_data",
        "practice_opt_out_state": "not_applicable",
    }
    resp = client.post("/v1/clinic/tools", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["model_training_status"] == "trains_on_customer_data"
    assert body["practice_opt_out_state"] == "not_applicable"
    assert body["opt_out_verified_at"] is None
    assert body["opt_out_verified_by_user_id"] is None


def test_staff_cannot_mark_verified(
    db_session, make_clinic_org_factory
) -> None:
    """HEALTH-5 / PRD.v2.md §6.8.2.a — only Admin may set 'verified'."""
    from fastapi.testclient import TestClient
    from policy_engine.database import get_db
    from policy_engine.main import app
    from policy_engine.models.user import UserRole
    from tests.factories.clinic import make_clinic_admin

    org = make_clinic_org_factory()
    # Make a non-admin (compliance_officer) user.
    _user, jwt = make_clinic_admin(
        db_session, org, role=UserRole.COMPLIANCE_OFFICER, username="staff_user"
    )

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        c = TestClient(app, raise_server_exceptions=True)
        c.headers.update({"Authorization": f"Bearer {jwt}"})
        resp = c.post(
            "/v1/clinic/tools",
            json={
                "name": "Some Tool",
                "model_training_status": "opt_out_available",
                "practice_opt_out_state": "verified",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422, resp.text
    assert "Admin" in resp.text or "verified" in resp.text


def test_admin_marks_verified_stamps_provenance(
    clinic_authed_client, db_session
) -> None:
    """PRD.v2.md §6.8.2.a — Admin-set verified must stamp provenance."""
    from policy_engine.models.clinic import ClinicAiTool

    client, _org, user = clinic_authed_client
    create = client.post(
        "/v1/clinic/tools",
        json={
            "name": "Audited Verified Tool",
            "model_training_status": "opt_out_available",
            "practice_opt_out_state": "required_and_set",
        },
    )
    assert create.status_code == 201
    tool_id = create.json()["id"]
    upd = client.put(
        f"/v1/clinic/tools/{tool_id}",
        json={"practice_opt_out_state": "verified"},
    )
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert body["practice_opt_out_state"] == "verified"
    assert body["opt_out_verified_at"] is not None
    assert body["opt_out_verified_by_user_id"] == user.id
    row = (
        db_session.query(ClinicAiTool).filter(ClinicAiTool.id == tool_id).first()
    )
    assert row.opt_out_verified_by_user_id == user.id


def test_alert_emitted_once_in_30d_window(clinic_authed_client, db_session) -> None:
    """PRD.v2.md §6.8.2.c — flipping back and forth within 30d emits once."""
    from policy_engine.models.alert import Alert

    client, org, _user = clinic_authed_client
    # 1) Create with trains_on_customer_data → one alert.
    resp1 = client.post(
        "/v1/clinic/tools",
        json={
            "name": "Bouncer Tool",
            "model_training_status": "trains_on_customer_data",
        },
    )
    assert resp1.status_code == 201
    tool_id = resp1.json()["id"]
    n_after_create = (
        db_session.query(Alert)
        .filter(
            Alert.organization_id == org.id,
            Alert.alert_type == "clinic.tool.trains_on_data",
            Alert.agent_id == tool_id,
        )
        .count()
    )
    assert n_after_create == 1
    # 2) Flip to no_training, then back to trains_on_customer_data — still 1.
    client.put(
        f"/v1/clinic/tools/{tool_id}",
        json={"model_training_status": "no_training"},
    )
    client.put(
        f"/v1/clinic/tools/{tool_id}",
        json={"model_training_status": "trains_on_customer_data"},
    )
    n_after_flip = (
        db_session.query(Alert)
        .filter(
            Alert.organization_id == org.id,
            Alert.alert_type == "clinic.tool.trains_on_data",
            Alert.agent_id == tool_id,
        )
        .count()
    )
    assert n_after_flip == 1


def test_validator_blocks_verified_without_context() -> None:
    """Review CRITICAL #1 — validator fail-closed on missing context.

    Constructing ``ToolCreate(practice_opt_out_state=VERIFIED)`` directly
    (without ``model_validate(..., context={'current_user': ...})``) must
    raise so that no test/seed/background-task can silently write an
    unverified VERIFIED row.
    """
    from pydantic import ValidationError

    from policy_engine.models.clinic import ClinicAiToolPracticeOptOutState
    from policy_engine.routes.clinic.tools import ToolCreate, ToolUpdate

    with pytest.raises(ValidationError) as exc_info:
        ToolCreate(
            name="X",
            practice_opt_out_state=ClinicAiToolPracticeOptOutState.VERIFIED,
        )
    msg = str(exc_info.value)
    assert "admin" in msg.lower(), msg

    # Same guard on ToolUpdate.
    with pytest.raises(ValidationError) as exc_info:
        ToolUpdate(
            practice_opt_out_state=ClinicAiToolPracticeOptOutState.VERIFIED,
        )
    assert "admin" in str(exc_info.value).lower()

    # Non-VERIFIED values still construct cleanly with no context — the
    # trivial-construct path must keep working.
    ok = ToolCreate(name="Y")
    assert ok.practice_opt_out_state == (
        ClinicAiToolPracticeOptOutState.NOT_APPLICABLE
    )


def test_alert_emitted_after_window(clinic_authed_client, db_session) -> None:
    """After the 30-day window elapses, the same tool may re-alert once."""
    from datetime import datetime, timedelta

    from policy_engine.models.alert import Alert

    client, org, _user = clinic_authed_client
    resp1 = client.post(
        "/v1/clinic/tools",
        json={
            "name": "Window Tool",
            "model_training_status": "trains_on_customer_data",
        },
    )
    assert resp1.status_code == 201
    tool_id = resp1.json()["id"]
    # Backdate the existing alert beyond the 30-day window.
    older = datetime.utcnow() - timedelta(days=31)
    alert = (
        db_session.query(Alert)
        .filter(
            Alert.organization_id == org.id,
            Alert.alert_type == "clinic.tool.trains_on_data",
            Alert.agent_id == tool_id,
        )
        .first()
    )
    assert alert is not None
    alert.timestamp = older
    db_session.commit()
    # Now flip to no_training and back; a fresh alert is allowed.
    client.put(
        f"/v1/clinic/tools/{tool_id}",
        json={"model_training_status": "no_training"},
    )
    client.put(
        f"/v1/clinic/tools/{tool_id}",
        json={"model_training_status": "trains_on_customer_data"},
    )
    fresh = (
        db_session.query(Alert)
        .filter(
            Alert.organization_id == org.id,
            Alert.alert_type == "clinic.tool.trains_on_data",
            Alert.agent_id == tool_id,
            Alert.timestamp > older,
        )
        .count()
    )
    assert fresh == 1
