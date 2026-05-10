"""Integration tests for /v1/clinic/baa — BAA acceptance + status."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from policy_engine.database import get_db
from policy_engine.main import app
from policy_engine.models.organization import (
    TIER_CLINIC_BASIC,
    TIER_CLINIC_STANDARD,
)
from tests.factories.clinic import make_clinic_admin, make_clinic_org


pytestmark = pytest.mark.clinic


def _authed(db_session, org):
    _user, jwt = make_clinic_admin(db_session, org)
    app.dependency_overrides[get_db] = lambda: db_session
    c = TestClient(app, raise_server_exceptions=True)
    c.headers.update({"Authorization": f"Bearer {jwt}"})
    return c


def test_baa_status_for_signed_clinic(db_session) -> None:
    org = make_clinic_org(db_session, tier=TIER_CLINIC_STANDARD, baa_signed=True)
    c = _authed(db_session, org)
    try:
        resp = c.get("/v1/clinic/baa/status")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["signed"] is True
    assert body["plan"] == TIER_CLINIC_STANDARD
    assert body["mode"] == "executed_bundled"  # standard tier uses bundled BAA
    assert body["can_self_accept"] is False  # only basic supports click-through


def test_baa_status_for_basic_unsigned_offers_click_through(db_session) -> None:
    org = make_clinic_org(db_session, tier=TIER_CLINIC_BASIC, baa_signed=False)
    c = _authed(db_session, org)
    try:
        resp = c.get("/v1/clinic/baa/status")
    finally:
        app.dependency_overrides.clear()
    body = resp.json()
    assert body["signed"] is False
    assert body["mode"] == "click_through"
    assert body["can_self_accept"] is True


def test_baa_accept_click_through_flips_signed(db_session) -> None:
    org = make_clinic_org(db_session, tier=TIER_CLINIC_BASIC, baa_signed=False)
    c = _authed(db_session, org)
    try:
        resp = c.post(
            "/v1/clinic/baa/accept",
            json={
                "organization_legal_name": "Acme Health LLC",
                "accepter_full_name": "Test Admin",
                "accepter_title": "Practice Manager",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["signed"] is True
    # Org row should reflect the accepted state and capture metadata.
    db_session.refresh(org)
    assert org.hipaa_baa_signed is True
    assert org.hipaa_baa_date is not None
    baa_meta = (org.settings or {}).get("baa") or {}
    assert baa_meta["source"] == "click_through"
    assert baa_meta["organization_legal_name"] == "Acme Health LLC"


def test_baa_accept_rejected_for_executed_bundled_tier(db_session) -> None:
    """Standard tier uses an executed BAA — click-through accept must 409."""
    org = make_clinic_org(db_session, tier=TIER_CLINIC_STANDARD, baa_signed=False)
    c = _authed(db_session, org)
    try:
        resp = c.post(
            "/v1/clinic/baa/accept",
            json={
                "organization_legal_name": "Anything",
                "accepter_full_name": "Anybody",
                "accepter_title": "Manager",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 409


def test_baa_accept_idempotent_when_already_signed(db_session) -> None:
    org = make_clinic_org(db_session, tier=TIER_CLINIC_BASIC, baa_signed=True)
    c = _authed(db_session, org)
    try:
        resp = c.post(
            "/v1/clinic/baa/accept",
            json={
                "organization_legal_name": "Foo",
                "accepter_full_name": "Bar",
                "accepter_title": "Baz",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["signed"] is True
