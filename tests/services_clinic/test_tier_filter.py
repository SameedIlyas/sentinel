"""Tests for ``policy_engine.services.tier_filter`` dependencies.

Every clinic route depends on these gates. The tests use the FastAPI
TestClient to exercise the dependencies as actual HTTP middleware (the
behavior we care about), not isolated unit calls.
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from policy_engine.database import get_db
from policy_engine.models.organization import (
    Organization,
    TIER_CLINIC_BASIC,
    TIER_CLINIC_MULTI_SITE,
    TIER_CLINIC_STANDARD,
    TIER_ENTERPRISE,
)
from policy_engine.models.user import User
from policy_engine.services.tier_filter import (
    get_user_org,
    get_user_tier,
    require_clinic_tier,
    require_clinic_tier_with_baa,
    require_min_clinic_tier,
)

from tests.factories.clinic import make_clinic_admin, make_clinic_org


pytestmark = pytest.mark.clinic


def _make_test_app(db_session: Session) -> FastAPI:
    """Build a minimal FastAPI app exercising one route per gate."""
    app = FastAPI()
    router = APIRouter()

    @router.get("/tier")
    def read_tier(tier: str = Depends(get_user_tier)):
        return {"tier": tier}

    @router.get("/org")
    def read_org(org: Organization = Depends(get_user_org)):
        return {"org_id": org.id}

    @router.get("/clinic-only")
    def clinic_only(org: Organization = Depends(require_clinic_tier)):
        return {"org_id": org.id, "tier": org.tier}

    @router.get("/clinic-with-baa")
    def clinic_with_baa(org: Organization = Depends(require_clinic_tier_with_baa)):
        return {"baa": org.hipaa_baa_signed}

    @router.get("/multi-site-only")
    def multi_only(
        org: Organization = Depends(require_min_clinic_tier(TIER_CLINIC_MULTI_SITE))
    ):
        return {"tier": org.tier}

    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    return app


def _client_for_user(app: FastAPI, jwt: str) -> TestClient:
    c = TestClient(app, raise_server_exceptions=True)
    c.headers.update({"Authorization": f"Bearer {jwt}"})
    return c


# ── get_user_tier ──────────────────────────────────────────────────────


def test_get_user_tier_returns_clinic_standard(db_session) -> None:
    org = make_clinic_org(db_session, tier=TIER_CLINIC_STANDARD)
    _user, jwt = make_clinic_admin(db_session, org)
    app = _make_test_app(db_session)
    resp = _client_for_user(app, jwt).get("/tier")
    assert resp.status_code == 200
    assert resp.json() == {"tier": TIER_CLINIC_STANDARD}


def test_get_user_tier_returns_enterprise_for_org(db_session) -> None:
    org = make_clinic_org(db_session, tier=TIER_ENTERPRISE, baa_signed=False)
    _user, jwt = make_clinic_admin(db_session, org)
    app = _make_test_app(db_session)
    resp = _client_for_user(app, jwt).get("/tier")
    assert resp.json() == {"tier": TIER_ENTERPRISE}


# ── require_clinic_tier ────────────────────────────────────────────────


def test_require_clinic_tier_allows_clinic_standard(db_session) -> None:
    org = make_clinic_org(db_session, tier=TIER_CLINIC_STANDARD)
    _user, jwt = make_clinic_admin(db_session, org)
    resp = _client_for_user(_make_test_app(db_session), jwt).get("/clinic-only")
    assert resp.status_code == 200
    assert resp.json()["tier"] == TIER_CLINIC_STANDARD


def test_require_clinic_tier_blocks_enterprise(db_session) -> None:
    org = make_clinic_org(db_session, tier=TIER_ENTERPRISE, baa_signed=False)
    _user, jwt = make_clinic_admin(db_session, org)
    resp = _client_for_user(_make_test_app(db_session), jwt).get("/clinic-only")
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["error"] == "tier_required"
    assert detail["current_tier"] == TIER_ENTERPRISE
    assert TIER_CLINIC_BASIC in detail["required_tiers"]


# ── require_clinic_tier_with_baa ────────────────────────────────────────


def test_require_baa_allows_signed(db_session) -> None:
    org = make_clinic_org(db_session, tier=TIER_CLINIC_BASIC, baa_signed=True)
    _user, jwt = make_clinic_admin(db_session, org)
    resp = _client_for_user(_make_test_app(db_session), jwt).get("/clinic-with-baa")
    assert resp.status_code == 200
    assert resp.json() == {"baa": True}


def test_require_baa_blocks_unsigned(db_session) -> None:
    org = make_clinic_org(db_session, tier=TIER_CLINIC_BASIC, baa_signed=False)
    _user, jwt = make_clinic_admin(db_session, org)
    resp = _client_for_user(_make_test_app(db_session), jwt).get("/clinic-with-baa")
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["error"] == "baa_required"


# ── require_min_clinic_tier ────────────────────────────────────────────


@pytest.mark.parametrize(
    "tier, allowed",
    [
        (TIER_CLINIC_BASIC, False),
        (TIER_CLINIC_STANDARD, False),
        (TIER_CLINIC_MULTI_SITE, True),
    ],
)
def test_require_min_multi_site(db_session, tier: str, allowed: bool) -> None:
    org = make_clinic_org(db_session, tier=tier)
    _user, jwt = make_clinic_admin(db_session, org)
    resp = _client_for_user(_make_test_app(db_session), jwt).get("/multi-site-only")
    if allowed:
        assert resp.status_code == 200
    else:
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "tier_upgrade_required"


def test_require_min_blocks_enterprise(db_session) -> None:
    """Enterprise tier should be blocked because min is a clinic tier."""
    org = make_clinic_org(db_session, tier=TIER_ENTERPRISE, baa_signed=False)
    _user, jwt = make_clinic_admin(db_session, org)
    resp = _client_for_user(_make_test_app(db_session), jwt).get("/multi-site-only")
    # Enterprise fails the outer require_clinic_tier first.
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "tier_required"


# ── get_user_org for orphaned users ─────────────────────────────────────


def test_get_user_org_404_when_no_org(db_session) -> None:
    """A user with organization_id=None should get a 404 from get_user_org."""
    org = make_clinic_org(db_session, tier=TIER_CLINIC_STANDARD)
    user, jwt = make_clinic_admin(db_session, org)
    # Detach the user from the org (simulate orphaned user).
    user.organization_id = None
    db_session.commit()

    resp = _client_for_user(_make_test_app(db_session), jwt).get("/org")
    assert resp.status_code == 404
    assert "not attached to an organization" in resp.json()["detail"]
