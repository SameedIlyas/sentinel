"""Tests for the WebSocket ticket pattern (CRIT-013).

Key contract:
- Tickets are opaque (CSPRNG, no PII) and single-use (GETDEL semantics).
- POST /v1/ws/ticket requires a normal Authorization header — never URL
  credentials — and returns a fresh ticket + TTL.
- The WebSocket route closes with code 4401 on missing / expired / used
  ticket.
- The ticket store falls back to an in-memory dict in dev/tests but
  refuses to start in production with that fallback.
"""
from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient

from policy_engine.auth.jwt_utils import create_access_token, get_password_hash
from policy_engine.database import get_db
from policy_engine.main import app
from policy_engine.models.organization import Organization
from policy_engine.models.user import User, UserRole
from policy_engine.services import ws_ticket_store
from policy_engine.services.ws_ticket_store import (
    TICKET_TTL_SECONDS,
    WSTicketStore,
    _InMemoryStore,
    ensure_production_safe,
    reset_ws_ticket_store_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_store():
    """Each test starts with a fresh, in-memory-only ticket store."""
    reset_ws_ticket_store_for_tests()
    yield
    reset_ws_ticket_store_for_tests()


def _make_org(db_session, name: str) -> Organization:
    org = Organization(
        id=str(uuid.uuid4()),
        name=name,
        slug=name,
        tier="enterprise",
    )
    db_session.add(org)
    db_session.commit()
    return org


def _make_user(db_session, org: Organization) -> tuple[User, str]:
    u = User(
        id=str(uuid.uuid4()),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"u_{uuid.uuid4().hex[:8]}@test.local",
        password_hash=get_password_hash("x"),
        role=UserRole.ORG_ADMIN,
        full_name="ws-ticket probe",
        is_active=True,
        organization_id=org.id,
    )
    db_session.add(u)
    db_session.commit()
    token = create_access_token(
        {"user_id": u.id, "username": u.username, "role": u.role.value, "org_id": org.id}
    )
    return u, token


def _client(db_session) -> TestClient:
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Store-level unit tests (no FastAPI)
# ---------------------------------------------------------------------------

class TestInMemoryStore:
    def test_setex_then_getdel_returns_value(self):
        store = _InMemoryStore()
        store.setex("t1", "user-1", ttl_seconds=30)
        assert store.getdel("t1") == "user-1"

    def test_getdel_is_single_use(self):
        store = _InMemoryStore()
        store.setex("t2", "user-2", ttl_seconds=30)
        assert store.getdel("t2") == "user-2"
        # Replay must fail — the entry was popped on first read.
        assert store.getdel("t2") is None

    def test_expired_ticket_returns_none(self):
        store = _InMemoryStore()
        store.setex("t3", "user-3", ttl_seconds=0)
        time.sleep(0.01)
        assert store.getdel("t3") is None

    def test_unknown_ticket_returns_none(self):
        assert _InMemoryStore().getdel("no-such-ticket") is None


class TestWSTicketStore:
    def test_issue_returns_unique_tickets(self):
        store = WSTicketStore(redis_client=None)
        a = store.issue("u")
        b = store.issue("u")
        assert a != b
        # Tickets are URL-safe base64 — no slashes, no plus, no equals.
        assert "/" not in a and "+" not in a

    def test_consume_returns_user_id_once(self):
        store = WSTicketStore(redis_client=None)
        t = store.issue("user-x")
        assert store.consume(t) == "user-x"
        # Replay must fail — single-use.
        assert store.consume(t) is None

    def test_empty_or_none_ticket_rejected(self):
        store = WSTicketStore(redis_client=None)
        assert store.consume(None) is None
        assert store.consume("") is None

    def test_issue_requires_user_id(self):
        store = WSTicketStore(redis_client=None)
        with pytest.raises(ValueError):
            store.issue("")

    def test_unknown_ticket_rejected(self):
        store = WSTicketStore(redis_client=None)
        assert store.consume("ticket-not-issued") is None


# ---------------------------------------------------------------------------
# Production safety guard
# ---------------------------------------------------------------------------

class TestProductionSafety:
    def test_ensure_production_safe_no_op_in_dev(self, monkeypatch):
        monkeypatch.setattr(
            "policy_engine.services.ws_ticket_store.settings",
            type("S", (), {"APP_ENV": "development", "REDIS_URL": "redis://x"})(),
            raising=True,
        )
        # No exception → dev paths must be allowed to use the fallback.
        ensure_production_safe()

    def test_ensure_production_safe_raises_in_prod_on_fallback(self, monkeypatch):
        # Pretend we're in production and Redis is unreachable.
        monkeypatch.setattr(
            "policy_engine.services.ws_ticket_store.settings",
            type("S", (), {"APP_ENV": "production", "REDIS_URL": "redis://nope"})(),
            raising=True,
        )
        monkeypatch.setattr(
            ws_ticket_store, "_build_redis_client", lambda: None
        )
        reset_ws_ticket_store_for_tests()
        with pytest.raises(RuntimeError, match="in-memory fallback"):
            ensure_production_safe()


# ---------------------------------------------------------------------------
# HTTP-level: POST /v1/ws/ticket
# ---------------------------------------------------------------------------

class TestTicketEndpoint:
    def test_post_ticket_requires_auth(self, db_session):
        """Unauthenticated callers must not receive a ticket. The exact
        status code depends on which middleware rejects first (CSRF or
        auth) — what matters is the request is refused with a 4xx."""
        try:
            with _client(db_session) as c:
                r = c.post("/v1/ws/ticket")
            assert r.status_code in (401, 403), r.text
        finally:
            app.dependency_overrides.clear()

    def test_post_ticket_returns_opaque_token_and_ttl(self, db_session):
        org = _make_org(db_session, "org")
        _, token = _make_user(db_session, org)

        try:
            with _client(db_session) as c:
                r = c.post(
                    "/v1/ws/ticket",
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert r.status_code == 200, r.text
            body = r.json()
            assert "ticket" in body and isinstance(body["ticket"], str)
            assert len(body["ticket"]) >= 40, "ticket too short for entropy"
            assert body["expires_in"] == TICKET_TTL_SECONDS
        finally:
            app.dependency_overrides.clear()

    def test_post_ticket_returns_fresh_token_each_call(self, db_session):
        org = _make_org(db_session, "org")
        _, token = _make_user(db_session, org)

        try:
            with _client(db_session) as c:
                r1 = c.post(
                    "/v1/ws/ticket",
                    headers={"Authorization": f"Bearer {token}"},
                )
                r2 = c.post(
                    "/v1/ws/ticket",
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert r1.status_code == 200 and r2.status_code == 200
            assert r1.json()["ticket"] != r2.json()["ticket"]
        finally:
            app.dependency_overrides.clear()

    def test_ticket_is_single_use_at_store_level(self, db_session):
        """End-to-end: mint a ticket, consume it, replay fails."""
        org = _make_org(db_session, "org")
        _, token = _make_user(db_session, org)

        try:
            with _client(db_session) as c:
                r = c.post(
                    "/v1/ws/ticket",
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert r.status_code == 200
            ticket = r.json()["ticket"]

            store = ws_ticket_store.get_ws_ticket_store()
            assert store.consume(ticket) is not None  # first use ok
            assert store.consume(ticket) is None  # replay rejected
        finally:
            app.dependency_overrides.clear()
