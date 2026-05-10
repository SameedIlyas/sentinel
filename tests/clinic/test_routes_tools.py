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
